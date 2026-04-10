from app.events import clear_events, get_events, push_event


def test_push_and_get_events():
    incident_id = "test-123"
    push_event(incident_id, {"event": "stage", "data": {"stage": "ingest"}})
    push_event(incident_id, {"event": "done", "data": {"id": incident_id}})
    events = get_events(incident_id)
    assert len(events) == 2
    assert events[0]["event"] == "stage"
    assert events[1]["event"] == "done"
    clear_events(incident_id)
    assert get_events(incident_id) == []


def test_get_events_unknown_id_returns_empty():
    assert get_events("nonexistent") == []
