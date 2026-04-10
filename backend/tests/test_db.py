from sqlalchemy import text
from sqlmodel import select

from app.db import init_db
from app.models import Incident


async def test_insert_and_query_incident(db_session):
    inc = Incident(
        title="DB test",
        description="Testing persistence",
        category="payment",
        severity_hint="high",
        reporter_email="test@example.com",
    )
    db_session.add(inc)
    await db_session.commit()
    await db_session.refresh(inc)

    result = await db_session.exec(select(Incident).where(Incident.id == inc.id))
    found = result.one()
    assert found.title == "DB test"
    assert found.status == "submitted"


async def test_incident_phase3_columns_persisted(db_session):
    inc = Incident(
        title="Col test",
        description="desc",
        category="payment",
        severity_hint="high",
        reporter_email="a@b.com",
        severity="P1",
        classified_category="payment",
        affected_services='["PaymentProcessor"]',
        search_paths='["src/PaymentProcessor/"]',
    )
    db_session.add(inc)
    await db_session.commit()
    await db_session.refresh(inc)

    result = await db_session.exec(select(Incident).where(Incident.id == inc.id))
    found = result.one()
    assert found.severity == "P1"
    assert found.classified_category == "payment"
    assert found.affected_services == '["PaymentProcessor"]'  # raw DB string
    assert found.search_paths == '["src/PaymentProcessor/"]'  # raw DB string


async def test_wal_mode_enabled(tmp_path):
    from sqlalchemy.ext.asyncio import create_async_engine

    db_path = tmp_path / "test.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    await init_db(engine)
    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA journal_mode"))
        mode = result.scalar()
    await engine.dispose()
    assert mode == "wal"


async def test_init_db_migrates_missing_columns(tmp_path):
    from sqlalchemy.ext.asyncio import create_async_engine

    db_path = tmp_path / "migrate.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.execute(text(
            "CREATE TABLE incident ("
            "id TEXT PRIMARY KEY, "
            "title TEXT NOT NULL, "
            "description TEXT NOT NULL, "
            "category TEXT NOT NULL, "
            "severity_hint TEXT NOT NULL, "
            "reporter_email TEXT NOT NULL DEFAULT '', "
            "status TEXT NOT NULL DEFAULT 'submitted', "
            "created_at TEXT NOT NULL"
            ")"
        ))

    await init_db(engine)

    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA table_info(incident)"))
        columns = {row[1] for row in result.fetchall()}

    assert "severity" in columns
    assert "root_cause_hypothesis" in columns
    assert "linear_id" in columns
    assert "resolved_at" in columns

    await engine.dispose()


async def test_get_session_yields_async_session():
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.db import get_session

    async for session in get_session():
        assert isinstance(session, AsyncSession)
        break
