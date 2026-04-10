from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.main import app
from app.models import Incident, IncidentStatus


@pytest.fixture
async def seeded_client() -> AsyncIterator[AsyncClient]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSession(engine) as session:
        session.add(Incident(
            title="Payment timeout",
            description="Checkout fails",
            category="payment",
            severity_hint="high",
            status=IncidentStatus.TRIAGED,
            severity="P0",
            triage_duration_ms=1200,
        ))
        session.add(Incident(
            title="Catalog slow",
            description="Pages load slowly",
            category="catalog",
            severity_hint="medium",
            status=IncidentStatus.RESOLVED,
            severity="P2",
            triage_duration_ms=800,
        ))
        await session.commit()

        async def _override() -> AsyncIterator[AsyncSession]:
            yield session

        app.dependency_overrides[get_session] = _override
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c
        app.dependency_overrides.clear()

    await engine.dispose()


@pytest.mark.asyncio
async def test_stats_returns_aggregate_data(seeded_client: AsyncClient) -> None:
    resp = await seeded_client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_incidents"] == 2
    assert data["by_severity"]["P0"] == 1
    assert data["by_severity"]["P2"] == 1
    assert data["by_status"]["triaged"] == 1
    assert data["by_status"]["resolved"] == 1
    assert data["avg_triage_duration_ms"] > 0
