import asyncio
from collections import defaultdict
from typing import Any

_MAX_EVENTS_PER_INCIDENT = 50
_buffer: dict[str, list[dict[str, Any]]] = defaultdict(list)
_subscribers: dict[str, list[asyncio.Queue[dict[str, Any] | None]]] = defaultdict(list)


def push_event(incident_id: str, event: dict[str, Any]) -> None:
    buf = _buffer[incident_id]
    buf.append(event)
    if len(buf) > _MAX_EVENTS_PER_INCIDENT:
        del buf[: len(buf) - _MAX_EVENTS_PER_INCIDENT]
    for queue in _subscribers[incident_id]:
        queue.put_nowait(event)


def get_events(incident_id: str) -> list[dict[str, Any]]:
    return list(_buffer.get(incident_id, []))


def clear_events(incident_id: str) -> None:
    _buffer.pop(incident_id, None)
    _subscribers.pop(incident_id, None)


def subscribe(incident_id: str) -> asyncio.Queue[dict[str, Any] | None]:
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    _subscribers[incident_id].append(queue)
    return queue


def unsubscribe(incident_id: str, queue: asyncio.Queue[dict[str, Any] | None]) -> None:
    subs = _subscribers.get(incident_id, [])
    if queue in subs:
        subs.remove(queue)


def complete(incident_id: str) -> None:
    for queue in _subscribers.get(incident_id, []):
        queue.put_nowait(None)
