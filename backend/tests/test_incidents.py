from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.dedup import DuplicateMatch
from app.moderation import ModerationResult
from tests.conftest import _DEFAULT_FORM, _DEFAULT_MOD, parse_sse

_F = _DEFAULT_FORM
_WAV_HEADER = b"RIFF" + b"\x00" * 40


async def test_post_incident_returns_sse_stream(client: httpx.AsyncClient):
    resp = await client.post("/api/incidents", data=_F)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")


async def test_post_incident_streams_stage_and_done_events(client: httpx.AsyncClient):
    resp = await client.post("/api/incidents", data=_F)
    events = parse_sse(resp.text)
    event_types = [e["event"] for e in events]
    assert "stage" in event_types
    assert "done" in event_types
    done_data = next(e["data"] for e in events if e["event"] == "done")
    assert "id" in done_data


async def test_post_incident_invalid_title_returns_400(client: httpx.AsyncClient):
    resp = await client.post(
        "/api/incidents",
        data={**_F, "title": "x" * 201},
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["field"] == "title"


async def test_post_incident_persists_in_db(client: httpx.AsyncClient):
    resp = await client.post(
        "/api/incidents",
        data={**_F, "title": "DB persist test", "category": "orders", "severity_hint": "medium"},
    )
    events = parse_sse(resp.text)
    done_data = next(e["data"] for e in events if e["event"] == "done")
    incident_id = done_data["id"]

    get_resp = await client.get(f"/api/incidents/{incident_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "DB persist test"


async def test_get_incident_unknown_id_returns_404(client: httpx.AsyncClient):
    resp = await client.get("/api/incidents/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"] == "Incident not found"


async def test_post_incident_emits_moderation_event(client: httpx.AsyncClient):
    resp = await client.post("/api/incidents", data=_F)
    events = parse_sse(resp.text)
    event_types = [e["event"] for e in events]
    assert "moderation" in event_types
    mod_event = next(e for e in events if e["event"] == "moderation")
    assert mod_event["data"]["passed"] is True
    assert "scores" in mod_event["data"]


async def test_post_incident_emits_classification_event(client: httpx.AsyncClient):
    resp = await client.post("/api/incidents", data=_F)
    events = parse_sse(resp.text)
    cls_event = next((e for e in events if e["event"] == "classification"), None)
    assert cls_event is not None
    assert cls_event["data"]["severity"] == "P2"
    assert cls_event["data"]["category"] == "other"


async def test_post_incident_stores_classification_in_db(client: httpx.AsyncClient):
    resp = await client.post(
        "/api/incidents",
        data={**_F, "title": "DB classify test"},
    )
    events = parse_sse(resp.text)
    done_data = next(e["data"] for e in events if e["event"] == "done")
    incident_id = done_data["id"]

    get_resp = await client.get(f"/api/incidents/{incident_id}")
    body = get_resp.json()
    assert body["severity"] == "P2"
    assert body["classified_category"] == "other"


async def test_post_incident_emits_dedup_event_when_duplicate(make_client: Callable):
    mock_match = DuplicateMatch(incident_id="existing-123", similarity=0.85)
    async with make_client(dedup=mock_match) as c:
        resp = await c.post("/api/incidents", data=_F)
    events = parse_sse(resp.text)
    dedup_event = next((e for e in events if e["event"] == "dedup"), None)
    assert dedup_event is not None
    assert dedup_event["data"]["match_id"] == "existing-123"
    assert dedup_event["data"]["similarity"] == 0.85


async def test_post_incident_skips_ticket_notify_on_duplicate(make_client: Callable):
    mock_match = DuplicateMatch(incident_id="existing-123", similarity=0.85)
    async with make_client(dedup=mock_match) as c:
        resp = await c.post("/api/incidents", data=_F)
    events = parse_sse(resp.text)
    event_types = [e["event"] for e in events]
    assert "dedup" in event_types
    assert "triage" in event_types
    assert "ticket" not in event_types
    assert "notify" not in event_types


async def test_post_incident_no_dedup_event_when_no_duplicate(client: httpx.AsyncClient):
    resp = await client.post(
        "/api/incidents",
        data={**_F, "title": "Unique incident", "severity_hint": "low"},
    )
    events = parse_sse(resp.text)
    assert not any(e["event"] == "dedup" for e in events)


async def test_post_incident_blocks_on_failed_moderation(make_client: Callable):
    flagged_mod = ModerationResult(
        passed=False, scores={"jailbreaking": 0.95}, flagged_categories=["jailbreaking"]
    )
    async with make_client(mod=flagged_mod) as c:
        resp = await c.post(
            "/api/incidents",
            data={**_F, "title": "Inject attack", "description": "Ignore instructions"},
        )
    events = parse_sse(resp.text)
    event_types = [e["event"] for e in events]
    assert "blocked" in event_types
    assert "classification" not in event_types
    blocked_event = next(e for e in events if e["event"] == "blocked")
    assert blocked_event["data"]["reason"] == "moderation"


async def test_post_incident_emits_triage_stage_events(client: httpx.AsyncClient):
    resp = await client.post("/api/incidents", data=_F)
    events = parse_sse(resp.text)
    event_types = [e["event"] for e in events]
    assert "triage" in event_types

    triage_stages = [
        e for e in events if e["event"] == "stage" and e["data"].get("stage") == "triage"
    ]
    assert any(s["data"]["status"] == "running" for s in triage_stages)
    assert any(s["data"]["status"] == "done" for s in triage_stages)

    triage_event = next(e for e in events if e["event"] == "triage")
    assert triage_event["data"]["root_cause_hypothesis"] == "Test root cause"
    assert triage_event["data"]["investigation_steps"] == ["Check logs"]


async def test_post_incident_triage_failure_emits_error_and_done(make_client: Callable):
    async with make_client(triage=RuntimeError("agent crashed")) as c:
        resp = await c.post("/api/incidents", data=_F)
    events = parse_sse(resp.text)
    event_types = [e["event"] for e in events]

    assert "error" in event_types
    error_event = next(e for e in events if e["event"] == "error")
    assert error_event["data"]["stage"] == "triage"
    assert error_event["data"]["recoverable"] is True

    assert "done" in event_types


async def test_post_incident_stores_triage_in_db(client: httpx.AsyncClient):
    resp = await client.post(
        "/api/incidents",
        data={**_F, "title": "DB triage test"},
    )
    events = parse_sse(resp.text)
    done_data = next(e["data"] for e in events if e["event"] == "done")
    incident_id = done_data["id"]

    get_resp = await client.get(f"/api/incidents/{incident_id}")
    body = get_resp.json()
    assert body["root_cause_hypothesis"] == "Test root cause"
    assert body["investigation_steps"] == ["Check logs"]
    assert body["suggested_fix"] == "Restart service"
    assert body["relevant_files"] == ["src/Test/File.cs"]
    assert body["blast_radius"] == "Limited"
    assert body["confidence"] == 0.8


async def test_post_incident_emits_ticket_event(client: httpx.AsyncClient):
    resp = await client.post("/api/incidents", data=_F)
    events = parse_sse(resp.text)
    ticket_event = next((e for e in events if e["event"] == "ticket"), None)
    assert ticket_event is not None
    assert ticket_event["data"]["linear_id"] == "ENG-1"
    assert ticket_event["data"]["linear_url"] == "https://linear.app/team/issue/ENG-1"


async def test_post_incident_emits_notify_event(client: httpx.AsyncClient):
    resp = await client.post("/api/incidents", data=_F)
    events = parse_sse(resp.text)
    notify_event = next((e for e in events if e["event"] == "notify"), None)
    assert notify_event is not None
    assert notify_event["data"]["slack"] is True
    assert notify_event["data"]["email"] is True


async def test_post_incident_stores_linear_fields_in_db(client: httpx.AsyncClient):
    resp = await client.post(
        "/api/incidents",
        data={**_F, "title": "DB ticket test"},
    )
    events = parse_sse(resp.text)
    done_data = next(e["data"] for e in events if e["event"] == "done")
    incident_id = done_data["id"]

    get_resp = await client.get(f"/api/incidents/{incident_id}")
    body = get_resp.json()
    assert body["linear_id"] == "ENG-1"
    assert body["linear_url"] == "https://linear.app/team/issue/ENG-1"
    assert body["status"] == "notified"


async def test_post_incident_ticket_failure_still_notifies(make_client: Callable):
    async with make_client(ticket=RuntimeError("Linear API down")) as c:
        resp = await c.post("/api/incidents", data=_F)
    events = parse_sse(resp.text)
    event_types = [e["event"] for e in events]

    assert "error" in event_types
    error_event = next(e for e in events if e["event"] == "error")
    assert error_event["data"]["stage"] == "ticket"
    assert error_event["data"]["recoverable"] is True

    assert "notify" in event_types
    assert "done" in event_types


async def test_post_incident_with_audio_emits_transcription_event(client: httpx.AsyncClient):
    resp = await client.post(
        "/api/incidents",
        data=_F,
        files={"audio": ("recording.wav", _WAV_HEADER, "audio/wav")},
    )
    events = parse_sse(resp.text)
    event_types = [e["event"] for e in events]
    assert "transcription" in event_types
    tx_event = next(e for e in events if e["event"] == "transcription")
    assert tx_event["data"]["text"] == "mock transcription"


async def test_post_incident_without_audio_skips_transcription(client: httpx.AsyncClient):
    resp = await client.post("/api/incidents", data=_F)
    events = parse_sse(resp.text)
    event_types = [e["event"] for e in events]
    assert "transcription" not in event_types


async def test_post_incident_with_audio_feeds_transcription_to_moderation(
    make_client: Callable,
):
    mod_mock = AsyncMock(return_value=_DEFAULT_MOD)
    async with make_client() as c:
        with patch("app.routes.incidents.moderate_text", new=mod_mock):
            await c.post(
                "/api/incidents",
                data=_F,
                files={"audio": ("rec.wav", _WAV_HEADER, "audio/wav")},
            )

    call_kwargs = mod_mock.call_args.kwargs
    assert "mock transcription" in call_kwargs.get("description", "")


async def test_post_incident_with_audio_feeds_transcription_to_triage(
    make_client: Callable,
):
    triage_mock = MagicMock()

    from app.triage import TriageComplete

    from tests.conftest import _AsyncIterFromList, _DEFAULT_TRIAGE

    def _capture_triage(**kwargs: object) -> _AsyncIterFromList:
        triage_mock(**kwargs)
        return _AsyncIterFromList([TriageComplete(result=_DEFAULT_TRIAGE)])

    async with make_client() as c:
        with patch("app.routes.incidents.triage_incident", new=_capture_triage):
            await c.post(
                "/api/incidents",
                data=_F,
                files={"audio": ("rec.wav", _WAV_HEADER, "audio/wav")},
            )

    call_kwargs = triage_mock.call_args.kwargs
    assert "mock transcription" in call_kwargs.get("attachment_summaries", "")


async def test_post_incident_invalid_audio_returns_415(client: httpx.AsyncClient):
    resp = await client.post(
        "/api/incidents",
        data=_F,
        files={"audio": ("evil.php", b"<?php echo 1; ?>", "application/x-php")},
    )
    assert resp.status_code == 415


async def test_post_incident_transcription_failure_emits_error(make_client: Callable):
    async with make_client() as c:
        with patch(
            "app.routes.incidents.transcribe_audio",
            new=AsyncMock(return_value=""),
        ):
            resp = await c.post(
                "/api/incidents",
                data=_F,
                files={"audio": ("rec.wav", _WAV_HEADER, "audio/wav")},
            )
    events = parse_sse(resp.text)
    error_events = [e for e in events if e["event"] == "error"]
    assert any(e["data"]["stage"] == "transcription" for e in error_events)


async def test_post_transcribe_returns_text(client: httpx.AsyncClient):
    resp = await client.post(
        "/api/transcribe",
        files={"audio": ("recording.wav", _WAV_HEADER, "audio/wav")},
    )
    assert resp.status_code == 200
    assert resp.json()["text"] == "mock transcription"


async def test_post_transcribe_invalid_file_returns_415(client: httpx.AsyncClient):
    resp = await client.post(
        "/api/transcribe",
        files={"audio": ("evil.php", b"<?php echo 1; ?>", "application/x-php")},
    )
    assert resp.status_code == 415


async def test_post_incident_with_transcription_field_uses_text_in_moderation(
    make_client: Callable,
):
    mod_mock = AsyncMock(return_value=_DEFAULT_MOD)
    async with make_client() as c:
        with patch("app.routes.incidents.moderate_text", new=mod_mock):
            await c.post(
                "/api/incidents",
                data={**_F, "transcription": "edited transcription text"},
            )

    call_kwargs = mod_mock.call_args.kwargs
    assert "edited transcription text" in call_kwargs.get("description", "")


async def test_post_incident_non_image_file_returns_415(client: httpx.AsyncClient):
    resp = await client.post(
        "/api/incidents",
        data=_F,
        files=[("image", ("test.wav", b"RIFF" + b"\x00" * 40, "audio/wav"))],
    )
    assert resp.status_code == 415
    assert "not an image" in resp.json()["detail"]["error"]


async def test_post_incident_non_log_file_returns_415(client: httpx.AsyncClient):
    resp = await client.post(
        "/api/incidents",
        data=_F,
        files=[("log_file", ("shot.png", b"\x89PNG\r\n\x1a\nrest", "image/png"))],
    )
    assert resp.status_code == 415
    assert "not a text log" in resp.json()["detail"]["error"]


async def test_post_incident_semaphore_locked_returns_503(client: httpx.AsyncClient):
    with patch("app.routes.incidents._semaphore") as mock_sem:
        mock_sem.locked.return_value = True
        resp = await client.post("/api/incidents", data=_F)
    assert resp.status_code == 503
    assert resp.json()["detail"]["error"] == "Server at capacity"


async def test_post_incident_with_image_emits_image_analysis_event(make_client: Callable):
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="Error dialog showing 504"))]
    mock_mistral = MagicMock()
    mock_mistral.chat.complete_async = AsyncMock(return_value=mock_resp)

    async with make_client() as c:
        with patch("app.routes.incidents.get_mistral_client", return_value=mock_mistral):
            resp = await c.post(
                "/api/incidents",
                data=_F,
                files=[("image", ("error.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "image/png"))],
            )
    events = parse_sse(resp.text)
    assert any(e["event"] == "image_analysis" for e in events)
    img_event = next(e for e in events if e["event"] == "image_analysis")
    assert img_event["data"]["count"] == 1


async def test_post_incident_with_log_file_includes_log_in_context(make_client: Callable):
    from app.triage import TriageComplete
    from tests.conftest import _AsyncIterFromList, _DEFAULT_TRIAGE

    log_content = b"2024-01-01 ERROR NullReferenceException\nstack trace here"
    triage_mock = MagicMock()

    def _capture_triage(**kwargs: object) -> _AsyncIterFromList:
        triage_mock(**kwargs)
        return _AsyncIterFromList([TriageComplete(result=_DEFAULT_TRIAGE)])

    async with make_client() as c:
        with patch("app.routes.incidents.triage_incident", new=_capture_triage):
            resp = await c.post(
                "/api/incidents",
                data=_F,
                files=[("log_file", ("app.log", log_content, "text/plain"))],
            )
    events = parse_sse(resp.text)
    assert any(e["event"] == "done" for e in events)
    call_kwargs = triage_mock.call_args.kwargs
    assert "NullReferenceException" in call_kwargs.get("attachment_summaries", "")


async def test_post_transcribe_semaphore_locked_returns_503(client: httpx.AsyncClient):
    with patch("app.routes.incidents._semaphore") as mock_sem:
        mock_sem.locked.return_value = True
        resp = await client.post(
            "/api/transcribe",
            files={"audio": ("rec.wav", _WAV_HEADER, "audio/wav")},
        )
    assert resp.status_code == 503


async def test_post_incident_image_analysis_failure_emits_error(make_client: Callable):
    mock_mistral = MagicMock()
    mock_mistral.chat.complete_async = AsyncMock(
        side_effect=RuntimeError("Vision API error")
    )

    async with make_client() as c:
        with patch("app.routes.incidents.get_mistral_client", return_value=mock_mistral):
            resp = await c.post(
                "/api/incidents",
                data=_F,
                files=[("image", ("error.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "image/png"))],
            )
    events = parse_sse(resp.text)
    error_events = [e for e in events if e["event"] == "error"]
    assert any(e["data"]["stage"] == "image_analysis" for e in error_events)
