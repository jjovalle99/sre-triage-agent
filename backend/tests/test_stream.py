import httpx

from tests.conftest import parse_sse


async def test_stream_unknown_id_returns_404(client: httpx.AsyncClient):
    resp = await client.get("/api/incidents/00000000-0000-0000-0000-000000000000/stream")
    assert resp.status_code == 404


async def test_stream_replays_events_for_completed_incident(client: httpx.AsyncClient):
    post_resp = await client.post(
        "/api/incidents",
        data={
            "title": "Stream test",
            "description": "Test replay",
            "category": "payment",
            "severity_hint": "low",
            "reporter_email": "test@example.com",
        },
    )
    events = parse_sse(post_resp.text)
    done_data = next(e["data"] for e in events if e["event"] == "done")
    incident_id = done_data["id"]

    stream_resp = await client.get(f"/api/incidents/{incident_id}/stream")
    assert stream_resp.status_code == 200
    assert stream_resp.headers["content-type"].startswith("text/event-stream")
    replayed = parse_sse(stream_resp.text)
    replayed_types = [e["event"] for e in replayed]
    assert "stage" in replayed_types
    assert "done" in replayed_types
