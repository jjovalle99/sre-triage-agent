from uuid import UUID

from app.models import Incident, IncidentRead


def test_incident_defaults():
    inc = Incident(
        title="Test incident",
        description="Something broke",
        category="payment",
        severity_hint="high",
        reporter_email="test@example.com",
    )
    assert isinstance(inc.id, UUID)
    assert inc.status == "submitted"
    assert inc.created_at is not None


def test_incident_has_phase3_nullable_columns():
    inc = Incident(
        title="t",
        description="d",
        category="payment",
        severity_hint="high",
        reporter_email="a@b.com",
    )
    assert inc.severity is None
    assert inc.classified_category is None
    assert inc.affected_services is None
    assert inc.search_paths is None


def test_incident_read_serializes_to_json():
    inc = Incident(
        title="Test incident",
        description="Something broke",
        category="payment",
        severity_hint="high",
        reporter_email="test@example.com",
    )
    read = IncidentRead.model_validate(inc, from_attributes=True)
    data = read.model_dump(mode="json")
    assert data["title"] == "Test incident"
    assert data["category"] == "payment"
    assert isinstance(data["id"], str)


def test_incident_has_phase4_triage_fields():
    inc = Incident(
        title="t",
        description="d",
        category="payment",
        severity_hint="high",
        reporter_email="a@b.com",
    )
    assert inc.root_cause_hypothesis is None
    assert inc.investigation_steps is None
    assert inc.suggested_fix is None
    assert inc.relevant_files is None
    assert inc.blast_radius is None
    assert inc.confidence is None
    assert inc.triage_duration_ms is None


def test_incident_has_phase5_linear_fields():
    inc = Incident(
        title="t",
        description="d",
        category="payment",
        severity_hint="high",
        reporter_email="a@b.com",
    )
    assert inc.linear_id is None
    assert inc.linear_url is None


def test_incident_read_includes_linear_fields():
    inc = Incident(
        title="t",
        description="d",
        category="payment",
        severity_hint="high",
        reporter_email="a@b.com",
        linear_id="abc-123",
        linear_url="https://linear.app/issue/ENG-42",
    )
    read = IncidentRead.model_validate(inc, from_attributes=True)
    assert read.linear_id == "abc-123"
    assert read.linear_url == "https://linear.app/issue/ENG-42"


def test_incident_has_phase7_resolved_at_field():
    inc = Incident(
        title="t",
        description="d",
        category="payment",
        severity_hint="high",
        reporter_email="a@b.com",
    )
    assert inc.resolved_at is None


def test_incident_read_includes_resolved_at():
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    inc = Incident(
        title="t",
        description="d",
        category="payment",
        severity_hint="high",
        reporter_email="a@b.com",
        resolved_at=now,
    )
    read = IncidentRead.model_validate(inc, from_attributes=True)
    assert read.resolved_at == now
    data = read.model_dump(mode="json")
    assert data["resolved_at"] is not None


def test_incident_read_decodes_triage_json_fields():
    inc = Incident(
        title="t",
        description="d",
        category="payment",
        severity_hint="high",
        reporter_email="a@b.com",
        investigation_steps='["step1", "step2"]',
        relevant_files='["src/File.cs"]',
        root_cause_hypothesis="root cause",
        confidence=0.85,
    )
    read = IncidentRead.model_validate(inc, from_attributes=True)
    assert read.investigation_steps == ["step1", "step2"]
    assert read.relevant_files == ["src/File.cs"]
    assert read.root_cause_hypothesis == "root cause"
    assert read.confidence == 0.85
