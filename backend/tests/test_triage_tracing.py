from unittest.mock import MagicMock, patch

from claude_agent_sdk import AssistantMessage, ResultMessage
from claude_agent_sdk.types import TextBlock
from opentelemetry.sdk.trace import TracerProvider

from app.triage import triage_incident
from tests.conftest import CollectingExporter, collect_async

_VALID_OUTPUT = {
    "root_cause_hypothesis": "Connection pool exhaustion",
    "investigation_steps": ["Check logs"],
    "suggested_fix": "Increase pool size",
    "relevant_files": [],
    "blast_radius": "Limited",
    "confidence": 0.85,
    "severity": "P1",
    "affected_services": ["PaymentProcessor"],
}


def _make_result_msg() -> MagicMock:
    msg = MagicMock(spec=ResultMessage)
    msg.is_error = False
    msg.structured_output = _VALID_OUTPUT
    msg.duration_ms = 1000
    msg.content = []
    return msg


async def test_llm_span_created_with_usage(
    otel_collector: tuple[CollectingExporter, TracerProvider],
) -> None:
    exporter, provider = otel_collector

    assistant = AssistantMessage(
        content=[TextBlock(text="Analyzing...")],
        model="claude-sonnet-4-6",
        usage={"input_tokens": 1500, "output_tokens": 200},
    )

    async def fake_query(**_: object) -> object:
        yield assistant
        yield _make_result_msg()

    with (
        patch("app.triage._tracer", provider.get_tracer("test")),
        patch("app.triage.query", fake_query),
    ):
        await collect_async(
            triage_incident(
                title="t",
                description="d",
                search_paths=[],
                affected_services=[],
                severity="P2",
                category="other",
                eshop_dir="/app/eshop",
            )
        )

    provider.force_flush()
    llm_spans = [
        s
        for s in exporter.spans
        if dict(s.attributes or {}).get("openinference.span.kind") == "LLM"
    ]
    assert len(llm_spans) == 1
    attrs = dict(llm_spans[0].attributes or {})
    assert attrs["llm.model_name"] == "claude-sonnet-4-6"
    assert attrs["llm.token_count.prompt"] == 1500
    assert attrs["llm.token_count.completion"] == 200
    assert attrs["llm.token_count.total"] == 1700


async def test_multiple_turns_produce_multiple_llm_spans(
    otel_collector: tuple[CollectingExporter, TracerProvider],
) -> None:
    exporter, provider = otel_collector

    turn1 = AssistantMessage(
        content=[TextBlock(text="Turn 1")],
        model="claude-sonnet-4-6",
        usage={"input_tokens": 1000, "output_tokens": 100},
    )
    turn2 = AssistantMessage(
        content=[TextBlock(text="Turn 2")],
        model="claude-sonnet-4-6",
        usage={"input_tokens": 2000, "output_tokens": 300},
    )

    async def fake_query(**_: object) -> object:
        yield turn1
        yield turn2
        yield _make_result_msg()

    with (
        patch("app.triage._tracer", provider.get_tracer("test")),
        patch("app.triage.query", fake_query),
    ):
        await collect_async(
            triage_incident(
                title="t",
                description="d",
                search_paths=[],
                affected_services=[],
                severity="P2",
                category="other",
                eshop_dir="/app/eshop",
            )
        )

    provider.force_flush()
    llm_spans = [
        s
        for s in exporter.spans
        if dict(s.attributes or {}).get("openinference.span.kind") == "LLM"
    ]
    assert len(llm_spans) == 2
    attrs_1 = dict(llm_spans[0].attributes or {})
    attrs_2 = dict(llm_spans[1].attributes or {})
    assert attrs_1["llm.token_count.prompt"] == 1000
    assert attrs_2["llm.token_count.prompt"] == 2000
    assert attrs_2["llm.token_count.completion"] == 300


async def test_no_llm_span_when_usage_is_none(
    otel_collector: tuple[CollectingExporter, TracerProvider],
) -> None:
    exporter, provider = otel_collector

    assistant = AssistantMessage(
        content=[TextBlock(text="No usage here")],
        model="claude-sonnet-4-6",
    )

    async def fake_query(**_: object) -> object:
        yield assistant
        yield _make_result_msg()

    with (
        patch("app.triage._tracer", provider.get_tracer("test")),
        patch("app.triage.query", fake_query),
    ):
        await collect_async(
            triage_incident(
                title="t",
                description="d",
                search_paths=[],
                affected_services=[],
                severity="P2",
                category="other",
                eshop_dir="/app/eshop",
            )
        )

    provider.force_flush()
    llm_spans = [
        s
        for s in exporter.spans
        if dict(s.attributes or {}).get("openinference.span.kind") == "LLM"
    ]
    assert len(llm_spans) == 0
