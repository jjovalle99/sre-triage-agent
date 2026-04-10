from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import EventSourceResponse
from fastapi.sse import ServerSentEvent

from app.events import get_events

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


async def _get_buffered_events(incident_id: UUID) -> list[dict[str, Any]]:
    events = get_events(str(incident_id))
    if not events:
        raise HTTPException(status_code=404, detail={"error": "Incident not found"})
    return events


BufferedEvents = Annotated[list[dict[str, Any]], Depends(_get_buffered_events)]


@router.get("/{incident_id}/stream", response_class=EventSourceResponse)
async def stream_incident(
    events: BufferedEvents,
) -> AsyncIterator[ServerSentEvent]:
    for event in events:
        yield ServerSentEvent(
            data=event.get("data"),
            event=event.get("event"),
        )
