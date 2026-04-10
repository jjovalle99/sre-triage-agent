import hashlib
import hmac
import json
import time
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.deps import AppDeps, get_app_deps
from app.main import app
from app.models import Incident, IncidentStatus


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _make_payload(
    identifier: str = "ENG-1",
    state_type: str = "completed",
    resolver: str = "Alice",
) -> dict:
    return {
        "action": "update",
        "type": "Issue",
        "actor": {"name": resolver, "email": "alice@co.com"},
        "data": {
            "identifier": identifier,
            "state": {"type": state_type, "name": "Done"},
        },
        "updatedFrom": {"stateId": "old-id"},
        "webhookTimestamp": int(time.time() * 1000),
    }


@pytest.fixture
async def webhook_client() -> AsyncIterator[tuple[httpx.AsyncClient, AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSession(engine) as session:
        incident = Incident(
            title="Payments down",
            description="Checkout fails",
            category="payment",
            severity_hint="high",
            reporter_email="reporter@example.com",
            status=IncidentStatus.NOTIFIED,
            linear_id="ENG-1",
            linear_url="https://linear.app/issue/ENG-1",
        )
        session.add(incident)
        await session.commit()
        await session.refresh(incident)

        async def _override_session() -> AsyncIterator[AsyncSession]:
            async with AsyncSession(engine) as s:
                yield s

        mock_deps = AppDeps(http_client=AsyncMock(spec=httpx.AsyncClient))

        async def _override_deps() -> AppDeps:
            return mock_deps

        app.dependency_overrides[get_session] = _override_session
        app.dependency_overrides[get_app_deps] = _override_deps
        transport = ASGITransport(app=app)
        with (
            patch("app.routes.webhooks.send_resolution_email", new=AsyncMock()),
            patch("app.routes.webhooks.post_resolution", new=AsyncMock()),
        ):
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as c:
                yield c, session
        app.dependency_overrides.clear()

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


SECRET = "whsec_test_secret"


@pytest.mark.asyncio
async def test_webhook_valid_resolution(webhook_client: tuple[httpx.AsyncClient, AsyncSession]) -> None:
    client, _ = webhook_client
    payload = _make_payload()
    body = json.dumps(payload).encode()
    sig = _sign(body, SECRET)

    with patch.dict("os.environ", {"LINEAR_WEBHOOK_SECRET": SECRET}):
        resp = await client.post(
            "/api/webhooks/linear",
            content=body,
            headers={"Linear-Signature": sig, "Content-Type": "application/json"},
        )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_webhook_invalid_signature(webhook_client: tuple[httpx.AsyncClient, AsyncSession]) -> None:
    client, _ = webhook_client
    body = json.dumps(_make_payload()).encode()

    with patch.dict("os.environ", {"LINEAR_WEBHOOK_SECRET": SECRET}):
        resp = await client.post(
            "/api/webhooks/linear",
            content=body,
            headers={"Linear-Signature": "invalid", "Content-Type": "application/json"},
        )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_webhook_non_resolution_returns_200(webhook_client: tuple[httpx.AsyncClient, AsyncSession]) -> None:
    client, _ = webhook_client
    payload = _make_payload(state_type="started")
    body = json.dumps(payload).encode()
    sig = _sign(body, SECRET)

    with patch.dict("os.environ", {"LINEAR_WEBHOOK_SECRET": SECRET}):
        resp = await client.post(
            "/api/webhooks/linear",
            content=body,
            headers={"Linear-Signature": sig, "Content-Type": "application/json"},
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
