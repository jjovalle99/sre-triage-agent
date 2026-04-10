import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "sqlite+aiosqlite:///data/incidents.db"
)

if DATABASE_URL.startswith("sqlite") and ":memory:" not in DATABASE_URL:
    db_path = DATABASE_URL.split("///")[-1]
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

_engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


_MIGRATION_COLUMNS = [
    # Phase 3
    "severity TEXT",
    "classified_category TEXT",
    "affected_services TEXT",
    "search_paths TEXT",
    # Phase 4
    "root_cause_hypothesis TEXT",
    "investigation_steps TEXT",
    "suggested_fix TEXT",
    "relevant_files TEXT",
    "blast_radius TEXT",
    "confidence REAL",
    "triage_duration_ms INTEGER",
    # Phase 5
    "linear_id TEXT",
    "linear_url TEXT",
    # Phase 7
    "resolved_at TEXT",
]


async def init_db(engine: AsyncEngine | None = None) -> None:
    eng = engine or _engine
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA busy_timeout=5000"))
        result = await conn.execute(text("PRAGMA table_info(incident)"))
        existing = {row[1] for row in result.fetchall()}
        for col_ddl in _MIGRATION_COLUMNS:
            col_name = col_ddl.split()[0]
            if col_name not in existing:
                await conn.execute(
                    text(f"ALTER TABLE incident ADD COLUMN {col_ddl}")
                )


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSession(_engine) as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
