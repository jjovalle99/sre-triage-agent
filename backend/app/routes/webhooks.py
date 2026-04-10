import asyncio
import json
import logging
import os
from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import APIRouter, HTTPException, Request
from sqlmodel import select

from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import SessionDep
from app.deps import AppDepsDep
from app.email import send_resolution_email
from app.models import Incident, IncidentStatus
from app.slack import post_resolution
from app.webhook import InvalidSignature, ReplayedRequest, check_replay, parse_resolution, verify_signature

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["webhooks"])


async def _mark_resolved(session: AsyncSession, incident: Incident) -> int:
    now = datetime.now(UTC)
    incident.status = IncidentStatus.RESOLVED
    incident.resolved_at = now
    session.add(incident)
    await session.commit()
    await session.refresh(incident)
    created = incident.created_at.replace(tzinfo=UTC) if incident.created_at.tzinfo is None else incident.created_at
    return int((now - created).total_seconds() / 60)


async def _send_resolution_notifications(
    http_client: httpx.AsyncClient,
    *,
    incident: Incident,
    resolver: str,
    ttr_minutes: int,
) -> None:
    slack_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    resend_key = os.environ.get("RESEND_API_KEY", "")
    from_addr = os.environ.get("RESEND_FROM_EMAIL", "")

    coros = []

    if slack_url and incident.linear_url:
        coros.append(
            post_resolution(
                http_client,
                webhook_url=slack_url,
                title=incident.title,
                resolver=resolver,
                ttr_minutes=ttr_minutes,
                ticket_url=incident.linear_url,
            )
        )

    if resend_key and from_addr and incident.reporter_email:
        import resend

        resend.api_key = resend_key
        coros.append(
            send_resolution_email(
                to=incident.reporter_email,
                from_addr=from_addr,
                title=incident.title,
                resolver=resolver,
                ttr_minutes=ttr_minutes,
                ticket_url=incident.linear_url or "",
            )
        )

    if coros:
        results = await asyncio.gather(*coros, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                _log.warning("Resolution notification failed: %s", r)


@router.post("/webhooks/linear")
async def linear_webhook(
    request: Request,
    session: SessionDep,
    deps: AppDepsDep,
) -> dict[str, str]:
    body = await request.body()
    secret = os.environ.get("LINEAR_WEBHOOK_SECRET", "")

    if secret:
        signature = request.headers.get("Linear-Signature", "")
        try:
            verify_signature(body=body, signature=signature, secret=secret)
        except InvalidSignature:
            raise HTTPException(status_code=401, detail="Invalid signature")

    payload = json.loads(body)

    timestamp = payload.get("webhookTimestamp")
    if timestamp and secret:
        try:
            check_replay(timestamp)
        except ReplayedRequest:
            raise HTTPException(status_code=401, detail="Replayed request")

    resolution = parse_resolution(payload)
    if resolution is None:
        return {"status": "ignored"}

    result = await session.exec(
        select(Incident).where(Incident.linear_id == resolution.identifier)
    )
    incident = result.one_or_none()
    if incident is None:
        return {"status": "ignored"}

    if incident.status == IncidentStatus.RESOLVED:
        return {"status": "already_resolved"}

    ttr_minutes = await _mark_resolved(session, incident)

    await _send_resolution_notifications(
        deps.http_client,
        incident=incident,
        resolver=resolution.resolver_name,
        ttr_minutes=ttr_minutes,
    )

    return {"status": "resolved"}


@router.post("/incidents/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    session: SessionDep,
    deps: AppDepsDep,
) -> dict[str, str | int]:
    try:
        uid = UUID(incident_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Incident not found")

    result = await session.exec(select(Incident).where(Incident.id == uid))
    incident = result.one_or_none()
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    if incident.status == IncidentStatus.RESOLVED:
        return {"status": "already_resolved"}

    ttr_minutes = await _mark_resolved(session, incident)

    await _send_resolution_notifications(
        deps.http_client,
        incident=incident,
        resolver="Manual",
        ttr_minutes=ttr_minutes,
    )

    return {"status": "resolved", "ttr_minutes": ttr_minutes}
