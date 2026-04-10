from collections.abc import Callable

import structlog.testing

from app.logging import setup_logging
from tests.conftest import _DEFAULT_FORM


_F = _DEFAULT_FORM


async def test_pipeline_emits_structured_logs_per_stage(
    make_client: Callable,
) -> None:
    setup_logging(json_logs=False)
    with structlog.testing.capture_logs() as logs:
        async with make_client() as client:
            resp = await client.post("/api/incidents", data=_F)
            assert resp.status_code == 200

    stage_logs = [entry for entry in logs if entry.get("event") == "stage_complete"]
    stage_names = [entry["stage"] for entry in stage_logs]
    assert "moderation" in stage_names
    assert "classification" in stage_names
    assert "triage" in stage_names
    assert "ticket" in stage_names
    assert "notify" in stage_names

    for entry in stage_logs:
        assert "duration_ms" in entry
        assert isinstance(entry["duration_ms"], int)
