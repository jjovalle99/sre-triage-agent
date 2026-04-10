import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import Incident

_WINDOW_MINUTES = 30
_THRESHOLD = 0.7
_TITLE_WEIGHT = 0.6
_SERVICE_WEIGHT = 0.4
_MAX_CANDIDATES = 100


@dataclass(frozen=True)
class DuplicateMatch:
    incident_id: str
    similarity: float


def _similarity(
    title_a: str,
    title_b: str,
    services_a: list[str],
    services_b_raw: str | None,
) -> float:
    title_sim = SequenceMatcher(None, title_a.lower(), title_b.lower()).ratio()
    services_b: list[str] = json.loads(services_b_raw) if services_b_raw else []
    set_a, set_b = set(services_a), set(services_b)
    if set_a or set_b:
        service_sim = len(set_a & set_b) / len(set_a | set_b)
    else:
        service_sim = 0.0
    return _TITLE_WEIGHT * title_sim + _SERVICE_WEIGHT * service_sim


async def find_duplicate(
    *,
    session: AsyncSession,
    title: str,
    affected_services: list[str],
    exclude_id: str | None = None,
) -> DuplicateMatch | None:
    """Find a recent incident similar to the given title + services."""
    cutoff = datetime.now(UTC) - timedelta(minutes=_WINDOW_MINUTES)
    result = await session.exec(
        select(Incident)
        .where(Incident.created_at >= cutoff)
        .order_by(Incident.created_at.desc())  # ty: ignore[unresolved-attribute]
        .limit(_MAX_CANDIDATES)
    )
    candidates = result.all()
    best: DuplicateMatch | None = None
    for candidate in candidates:
        if exclude_id and str(candidate.id) == exclude_id:
            continue
        score = _similarity(
            title, candidate.title, affected_services, candidate.affected_services
        )
        if score > _THRESHOLD and (best is None or score > best.similarity):
            best = DuplicateMatch(incident_id=str(candidate.id), similarity=score)
    return best
