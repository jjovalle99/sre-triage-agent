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


async def test_find_duplicate_no_service_overlap_lowers_score(db_session):
    existing = Incident(
        title="Payment timeout on checkout",
        description="desc",
        category="payment",
        severity_hint="high",
        reporter_email="a@b.com",
    )
    db_session.add(existing)
    await db_session.commit()

    result = await find_duplicate(
        session=db_session,
        title="Payment timeout on checkout",
        affected_services=[],
    )
    assert result is None


async def test_find_duplicate_picks_highest_similarity(db_session):
    better = Incident(
        title="Payment timeout on checkout",
        description="desc",
        category="payment",
        severity_hint="high",
        reporter_email="a@b.com",
        affected_services='["PaymentProcessor"]',
    )
    better.created_at = datetime.now(UTC) - timedelta(seconds=10)
    db_session.add(better)
    await db_session.commit()

    worse = Incident(
        title="Payment timeout error on the checkout page is broken",
        description="desc",
        category="payment",
        severity_hint="high",
        reporter_email="a@b.com",
        affected_services='["PaymentProcessor"]',
    )
    db_session.add(worse)
    await db_session.commit()

    result = await find_duplicate(
        session=db_session,
        title="Payment timeout on checkout",
        affected_services=["PaymentProcessor"],
    )
    assert result is not None
    assert result.incident_id == str(better.id)


async def test_find_duplicate_excludes_self(db_session):
    existing = Incident(
        title="Payment timeout on checkout",
        description="desc",
        category="payment",
        severity_hint="high",
        reporter_email="a@b.com",
        affected_services='["PaymentProcessor"]',
    )
    db_session.add(existing)
    await db_session.commit()
    await db_session.refresh(existing)

    result = await find_duplicate(
        session=db_session,
        title="Payment timeout on checkout",
        affected_services=["PaymentProcessor"],
        exclude_id=str(existing.id),
    )
    assert result is None
