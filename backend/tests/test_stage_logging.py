import structlog
import structlog.testing

from app.logging import setup_logging
from app.observability import stage_span


async def test_stage_span_emits_structlog_event() -> None:
    setup_logging(json_logs=False)
    with structlog.testing.capture_logs() as logs:
        async with stage_span("moderation", model="mistral-moderation-2603"):
            pass

    stage_logs = [entry for entry in logs if entry.get("stage") == "moderation"]
    assert len(stage_logs) == 1
    log = stage_logs[0]
    assert log["model"] == "mistral-moderation-2603"
    assert "duration_ms" in log
    assert log["duration_ms"] >= 0


async def test_stage_span_records_error() -> None:
    setup_logging(json_logs=False)
    with structlog.testing.capture_logs() as logs:
        try:
            async with stage_span("triage", model="claude-sonnet-4-6"):
                raise ValueError("boom")
        except ValueError:
            pass

    stage_logs = [entry for entry in logs if entry.get("stage") == "triage"]
    assert len(stage_logs) == 1
    assert stage_logs[0]["error"] == "boom"


async def test_stage_span_accepts_extra_attrs() -> None:
    setup_logging(json_logs=False)
    with structlog.testing.capture_logs() as logs:
        async with stage_span("classification", model="mistral-medium-latest") as ctx:
            ctx["tokens"] = 500
            ctx["cost_usd"] = 0.001

    stage_logs = [entry for entry in logs if entry.get("stage") == "classification"]
    assert len(stage_logs) == 1
    assert stage_logs[0]["tokens"] == 500
    assert stage_logs[0]["cost_usd"] == 0.001
