import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("MISTRAL_API_KEY", "test-key")
os.environ.setdefault("PHOENIX_COLLECTOR_ENDPOINT", "")
os.environ.setdefault("LINEAR_API_KEY", "lin_api_test")
os.environ.setdefault("LINEAR_TEAM_ID", "test-team-id")
os.environ.setdefault("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
os.environ.setdefault("RESEND_API_KEY", "re_test")
os.environ.setdefault("RESEND_FROM_EMAIL", "incidents@test.com")

from collections.abc import AsyncIterator, Callable, Iterator, Sequence
from unittest.mock import AsyncMock, MagicMock, patch

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult, ReadableSpan

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.classification import ClassificationResult
from app.db import get_session
from app.dedup import DuplicateMatch
from app.deps import AppDeps, get_app_deps
from app.linear import LinearIssue
import stamina

from app.main import app, limiter
from app.moderation import ModerationResult
from app.triage import TriageComplete, TriageResult

limiter.enabled = False
stamina.set_testing(True)

class CollectingExporter(SpanExporter):
    def __init__(self) -> None:
        self.spans: list[ReadableSpan] = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS


def make_tracer_provider(exporter: CollectingExporter) -> TracerProvider:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider


@pytest.fixture
def otel_collector() -> Iterator[tuple[CollectingExporter, TracerProvider]]:
    exporter = CollectingExporter()
    provider = make_tracer_provider(exporter)
    yield exporter, provider
    provider.force_flush()
    provider.shutdown()


_DEFAULT_ISSUE = LinearIssue(
    id="mock-id",
    identifier="ENG-1",
    url="https://linear.app/team/issue/ENG-1",
)


def parse_sse(text: str) -> list[dict]:
    import json

    events = []
    current_event = None
    current_data = None
    for line in text.split("\n"):
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: "):
            current_data = line[6:].strip()
        elif line == "" and current_event is not None and current_data is not None:
            try:
                data = json.loads(current_data)
            except json.JSONDecodeError:
                data = current_data
            events.append({"event": current_event, "data": data})
            current_event = None
            current_data = None
    return events


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSession(engine) as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


_DEFAULT_MOD = ModerationResult(passed=True, scores={"jailbreaking": 0.01}, flagged_categories=[])
_DEFAULT_CLS = ClassificationResult(
    severity="P2",
    category="other",
    affected_services=[],
    search_paths=[],
    urgency_reasoning="test",
    requires_deep_analysis=False,
)
_DEFAULT_TRIAGE = TriageResult(
    root_cause_hypothesis="Test root cause",
    investigation_steps=["Check logs"],
    suggested_fix="Restart service",
    relevant_files=["src/Test/File.cs"],
    blast_radius="Limited",
    confidence=0.8,
    severity="P2",
    affected_services=[],
    duration_ms=500,
)

_DEFAULT_FORM = {
    "title": "Payment timeout",
    "description": "Checkout fails with 504",
    "category": "payment",
    "severity_hint": "high",
    "reporter_email": "sre@example.com",
}


def mock_httpx_client(response_json: dict) -> tuple[AsyncMock, MagicMock]:  # type: ignore[type-arg]
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = response_json

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client, mock_response


async def collect_async(agen):  # type: ignore[no-untyped-def]
    items = []
    async for item in agen:
        items.append(item)
    return items


class _AsyncIterFromList:
    def __init__(self, items: list, exc: Exception | None = None) -> None:  # type: ignore[type-arg]
        self._items = items
        self._exc = exc
        self._idx = 0

    def __aiter__(self):  # type: ignore[no-untyped-def]
        return self

    async def __anext__(self):  # type: ignore[no-untyped-def]
        if self._exc is not None:
            raise self._exc
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item


def _make_triage_mock(triage: TriageResult | Exception):  # type: ignore[type-arg]
    if isinstance(triage, Exception):
        def _failing(**kwargs):  # type: ignore[no-untyped-def]
            return _AsyncIterFromList([], exc=triage)
        return _failing

    def _success(**kwargs):  # type: ignore[no-untyped-def]
        return _AsyncIterFromList([TriageComplete(result=triage)])
    return _success


@pytest.fixture
def make_client(
    db_session: AsyncSession,
) -> Callable:  # returns async context manager yielding AsyncClient
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _factory(
        *,
        mod: ModerationResult = _DEFAULT_MOD,
        cls: ClassificationResult = _DEFAULT_CLS,
        dedup: DuplicateMatch | None = None,
        triage: TriageResult | Exception = _DEFAULT_TRIAGE,
        ticket: LinearIssue | Exception = _DEFAULT_ISSUE,
    ) -> AsyncIterator[httpx.AsyncClient]:
        async def _override_session() -> AsyncIterator[AsyncSession]:
            yield db_session

        ticket_mock = (
            AsyncMock(side_effect=ticket)
            if isinstance(ticket, Exception)
            else AsyncMock(return_value=ticket)
        )

        mock_deps = AppDeps(http_client=AsyncMock(spec=httpx.AsyncClient))

        async def _override_deps() -> AppDeps:
            return mock_deps

        app.dependency_overrides[get_session] = _override_session
        app.dependency_overrides[get_app_deps] = _override_deps
        transport = ASGITransport(app=app)
        with (
            patch(
                "app.routes.incidents.moderate_text",
                new=AsyncMock(return_value=mod),
            ),
            patch(
                "app.routes.incidents.classify_incident",
                new=AsyncMock(return_value=cls),
            ),
            patch(
                "app.routes.incidents.find_duplicate",
                new=AsyncMock(return_value=dedup),
            ),
            patch("app.routes.incidents.get_mistral_client", return_value=MagicMock()),
            patch(
                "app.routes.incidents.triage_incident",
                new=_make_triage_mock(triage),
            ),
            patch("app.routes.incidents.create_issue", new=ticket_mock),
            patch("app.routes.incidents.post_incident", new=AsyncMock()),
            patch("app.routes.incidents.send_incident_email", new=AsyncMock()),
            patch(
                "app.routes.incidents.transcribe_audio",
                new=AsyncMock(return_value="mock transcription"),
            ),
            patch("app.routes.incidents.get_oncall_engineer", return_value="TestEngineer"),
        ):
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as c:
                yield c
        app.dependency_overrides.clear()

    return _factory


@pytest.fixture
async def client(make_client: Callable) -> AsyncIterator[httpx.AsyncClient]:
    async with make_client() as c:
        yield c
