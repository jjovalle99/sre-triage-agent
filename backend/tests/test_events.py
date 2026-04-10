from app.events import clear_events, complete, get_events, push_event, subscribe, unsubscribe


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


def test_buffer_overflow_trims_to_max():
    incident_id = "overflow-test"
    for i in range(55):
        push_event(incident_id, {"event": f"e{i}", "data": {}})
    events = get_events(incident_id)
    assert len(events) == 50
    assert events[0]["event"] == "e5"
    clear_events(incident_id)


def test_subscribe_receives_pushed_events():
    incident_id = "sub-test"
    queue = subscribe(incident_id)
    push_event(incident_id, {"event": "test", "data": {"x": 1}})
    event = queue.get_nowait()
    assert event is not None
    assert event["event"] == "test"
    clear_events(incident_id)


def test_unsubscribe_removes_queue():
    incident_id = "unsub-test"
    queue = subscribe(incident_id)
    unsubscribe(incident_id, queue)
    push_event(incident_id, {"event": "after", "data": {}})
    assert queue.empty()
    clear_events(incident_id)


def test_complete_sends_none_to_subscribers():
    incident_id = "complete-test"
    queue = subscribe(incident_id)
    complete(incident_id)
    sentinel = queue.get_nowait()
    assert sentinel is None
    clear_events(incident_id)
