from datetime import UTC, datetime, timedelta

from app.dedup import find_duplicate
from app.models import Incident


async def test_find_duplicate_returns_none_when_no_incidents(db_session):
    result = await find_duplicate(
        session=db_session,
        title="Payment timeout",
        affected_services=["PaymentProcessor"],
    )
    assert result is None


async def test_find_duplicate_returns_match_for_similar_title(db_session):
    existing = Incident(
        title="Payment processing timeout on checkout",
        description="desc",
        category="payment",
        severity_hint="high",
        reporter_email="a@b.com",
        affected_services='["PaymentProcessor"]',
    )
    db_session.add(existing)
    await db_session.commit()

    result = await find_duplicate(
        session=db_session,
        title="Payment timeout on checkout",
        affected_services=["PaymentProcessor"],
    )

    assert result is not None
    assert result.incident_id == str(existing.id)
    assert result.similarity > 0.7


async def test_find_duplicate_ignores_old_incidents(db_session):
    old = Incident(
        title="Payment timeout on checkout",
        description="desc",
        category="payment",
        severity_hint="high",
        reporter_email="a@b.com",
    )
    old.created_at = datetime.now(UTC) - timedelta(minutes=31)
    db_session.add(old)
    await db_session.commit()

    result = await find_duplicate(
        session=db_session,
        title="Payment timeout on checkout",
        affected_services=[],
    )
    assert result is None
