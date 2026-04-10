import enum
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from pydantic import BaseModel, model_validator
from sqlmodel import Field, SQLModel


class Category(str, enum.Enum):
    PAYMENT = "payment"
    CATALOG = "catalog"
    ORDERS = "orders"
    AUTH = "auth"
    INFRASTRUCTURE = "infrastructure"
    OTHER = "other"


class SeverityHint(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    TRIAGING = "triaging"
    TRIAGED = "triaged"
    TRIAGE_FAILED = "triage_failed"
    TICKET_CREATED = "ticket_created"
    NOTIFIED = "notified"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"


class Incident(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    title: str = Field(max_length=200, sa_column=sa.Column(sa.String(200), nullable=False))
    description: str = Field(max_length=5000, sa_column=sa.Column(sa.Text, nullable=False))
    category: str = Field(sa_column=sa.Column(sa.String(50), nullable=False))
    severity_hint: str = Field(sa_column=sa.Column(sa.String(50), nullable=False))
    reporter_email: str = Field(default="", sa_column=sa.Column(sa.String(254), nullable=False, server_default=""))
    status: str = Field(
        default=IncidentStatus.SUBMITTED,
        sa_column=sa.Column(sa.String(50), nullable=False, server_default="submitted"),
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=sa.Column(sa.DateTime, nullable=False),
    )
    severity: str | None = Field(default=None, sa_column=sa.Column(sa.String(10), nullable=True))
    classified_category: str | None = Field(
        default=None, sa_column=sa.Column(sa.String(50), nullable=True)
    )
    affected_services: str | None = Field(
        default=None, sa_column=sa.Column(sa.Text, nullable=True)
    )
    search_paths: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    root_cause_hypothesis: str | None = Field(
        default=None, sa_column=sa.Column(sa.Text, nullable=True)
    )
    investigation_steps: str | None = Field(
        default=None, sa_column=sa.Column(sa.Text, nullable=True)
    )
    suggested_fix: str | None = Field(
        default=None, sa_column=sa.Column(sa.Text, nullable=True)
    )
    relevant_files: str | None = Field(
        default=None, sa_column=sa.Column(sa.Text, nullable=True)
    )
    blast_radius: str | None = Field(
        default=None, sa_column=sa.Column(sa.Text, nullable=True)
    )
    confidence: float | None = Field(
        default=None, sa_column=sa.Column(sa.Float, nullable=True)
    )
    triage_duration_ms: int | None = Field(
        default=None, sa_column=sa.Column(sa.Integer, nullable=True)
    )
    linear_id: str | None = Field(
        default=None, sa_column=sa.Column(sa.String(100), nullable=True)
    )
    linear_url: str | None = Field(
        default=None, sa_column=sa.Column(sa.String(500), nullable=True)
    )
    resolved_at: datetime | None = Field(
        default=None, sa_column=sa.Column(sa.DateTime, nullable=True)
    )


_JSON_LIST_FIELDS = frozenset({
    "affected_services", "search_paths", "investigation_steps", "relevant_files",
})
_SCALAR_FIELDS = frozenset({
    "id", "title", "description", "category",
    "severity_hint", "reporter_email", "status",
    "created_at", "severity", "classified_category",
    "root_cause_hypothesis", "suggested_fix",
    "blast_radius", "confidence", "triage_duration_ms",
    "linear_id", "linear_url", "resolved_at",
})


class IncidentRead(BaseModel):
    id: UUID
    title: str
    description: str
    category: str
    severity_hint: str
    reporter_email: str
    status: str
    created_at: datetime
    severity: str | None = None
    classified_category: str | None = None
    affected_services: list[str] | None = None
    search_paths: list[str] | None = None
    root_cause_hypothesis: str | None = None
    investigation_steps: list[str] | None = None
    suggested_fix: str | None = None
    relevant_files: list[str] | None = None
    blast_radius: str | None = None
    confidence: float | None = None
    triage_duration_ms: int | None = None
    linear_id: str | None = None
    linear_url: str | None = None
    resolved_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _decode_json_fields(cls, data: dict) -> dict:  # type: ignore[type-arg]
        if not isinstance(data, dict):
            raw = {}
            for f in _JSON_LIST_FIELDS:
                val = getattr(data, f, None)
                if val is not None:
                    raw[f] = json.loads(val) if isinstance(val, str) else val
            return raw | {
                k: getattr(data, k)
                for k in _SCALAR_FIELDS
                if hasattr(data, k)
            }
        for f in _JSON_LIST_FIELDS:
            val = data.get(f)
            if isinstance(val, str):
                data[f] = json.loads(val)
        return data
