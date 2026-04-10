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


@pytest.fixture
async def resolve_client() -> AsyncIterator[tuple[httpx.AsyncClient, Incident]]:
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
                yield c, incident
        app.dependency_overrides.clear()

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_manual_resolve_succeeds(resolve_client: tuple[httpx.AsyncClient, Incident]) -> None:
    client, incident = resolve_client
    resp = await client.post(f"/api/incidents/{incident.id}/resolve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"


@pytest.mark.asyncio
async def test_manual_resolve_not_found(resolve_client: tuple[httpx.AsyncClient, Incident]) -> None:
    client, _ = resolve_client
    resp = await client.post("/api/incidents/00000000-0000-0000-0000-000000000000/resolve")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_manual_resolve_already_resolved(resolve_client: tuple[httpx.AsyncClient, Incident]) -> None:
    client, incident = resolve_client
    await client.post(f"/api/incidents/{incident.id}/resolve")
    resp = await client.post(f"/api/incidents/{incident.id}/resolve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "already_resolved"
