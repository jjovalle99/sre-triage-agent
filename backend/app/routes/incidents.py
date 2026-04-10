import asyncio
import base64
from html import escape as html_escape
import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

import httpx
import structlog
from openinference.semconv.trace import OpenInferenceSpanKindValues, SpanAttributes
from opentelemetry import context, trace

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import EventSourceResponse
from fastapi.sse import ServerSentEvent
from sqlmodel import select

from app.classification import classify_incident
from app.db import SessionDep
from app.deps import AppDepsDep
from app.dedup import find_duplicate
from app.email import send_incident_email
from app.events import complete, push_event
from app.linear import create_issue
from app.mistral import get_mistral_client
from app.moderation import moderate_text
from app.models import Incident, IncidentRead, IncidentStatus
from app.observability import stage_span
from app.oncall import get_oncall_engineer
from app.slack import post_incident
from app.transcription import TRANSCRIPTION_TAG, AudioUpload, transcribe_audio
from app.triage import TriageComplete, TriageEvent, TriageResult, triage_incident
from app.validation import validate_fields, validate_file_magic

_log = structlog.get_logger()
_tracer = trace.get_tracer(__name__)

router = APIRouter(prefix="/api", tags=["incidents"])

_semaphore = asyncio.Semaphore(3)


async def _validated_form(
    title: Annotated[str, Form()],
    description: Annotated[str, Form()],
    category: Annotated[str, Form()],
    severity_hint: Annotated[str, Form()],
    reporter_email: Annotated[str, Form()] = "",
    transcription: Annotated[str, Form()] = "",
) -> dict[str, str]:
    validate_fields(
        title=title,
        description=description,
        category=category,
        severity_hint=severity_hint,
        reporter_email=reporter_email,
    )
    if _semaphore.locked():
        raise HTTPException(
            status_code=503,
            detail={"error": "Server at capacity", "retry_after": 5},
            headers={"Retry-After": "5"},
        )
    return {
        "title": title,
        "description": description,
        "category": category,
        "severity_hint": severity_hint,
        "reporter_email": reporter_email,
        "transcription": transcription,
    }


ValidatedForm = Annotated[dict[str, str], Depends(_validated_form)]


_MAX_AUDIO_BYTES = 25 * 1024 * 1024


async def _read_and_validate_audio(audio: UploadFile, *, required: bool) -> AudioUpload | None:
    if audio.size and audio.size > _MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail={"error": "Audio exceeds 25MB limit"})
    content = await audio.read()
    if not content:
        if required:
            raise HTTPException(status_code=400, detail={"error": "Empty audio file"})
        return None
    file_type = validate_file_magic(content, audio.filename or "audio")
    if file_type != "audio":
        raise HTTPException(status_code=415, detail={"error": "File is not audio"})
    return AudioUpload(content=content, filename=audio.filename or "audio")


async def _validated_audio(audio: UploadFile | None = None) -> AudioUpload | None:
    if audio is None:
        return None
    return await _read_and_validate_audio(audio, required=False)


ValidatedAudio = Annotated[AudioUpload | None, Depends(_validated_audio)]


@dataclass(frozen=True)
class FileUpload:
    content: bytes
    filename: str


async def _validated_images(image: list[UploadFile] = File(default=[])) -> list[FileUpload]:
    results = []
    for img in image:
        content = await img.read()
        if not content:
            continue
        file_type = validate_file_magic(content, img.filename or "image")
        if file_type != "image":
            raise HTTPException(status_code=415, detail={"error": f"File '{img.filename}' is not an image"})
        results.append(FileUpload(content=content, filename=img.filename or "image"))
    return results


ValidatedImages = Annotated[list[FileUpload], Depends(_validated_images)]


async def _validated_logs(log_file: list[UploadFile] = File(default=[])) -> list[FileUpload]:
    results = []
    for lf in log_file:
        content = await lf.read()
        if not content:
            continue
        file_type = validate_file_magic(content, lf.filename or "log.txt")
        if file_type != "log_file":
            raise HTTPException(status_code=415, detail={"error": f"File '{lf.filename}' is not a text log"})
        results.append(FileUpload(content=content, filename=lf.filename or "log.txt"))
    return results


ValidatedLogs = Annotated[list[FileUpload], Depends(_validated_logs)]


def _emit(incident_id: str, event: str, data: dict[str, Any]) -> ServerSentEvent:
    push_event(incident_id, {"event": event, "data": data})
    return ServerSentEvent(data=data, event=event)


def _triage_result_to_dict(result: TriageResult) -> dict[str, Any]:
    return {
        "root_cause_hypothesis": result.root_cause_hypothesis,
        "investigation_steps": result.investigation_steps,
        "suggested_fix": result.suggested_fix,
        "relevant_files": result.relevant_files,
        "blast_radius": result.blast_radius,
        "confidence": result.confidence,
        "severity": result.severity,
        "affected_services": result.affected_services,
        "duration_ms": result.duration_ms,
    }


def _persist_triage(incident: Incident, result: TriageResult) -> None:
    incident.root_cause_hypothesis = result.root_cause_hypothesis
    incident.investigation_steps = json.dumps(result.investigation_steps)
    incident.suggested_fix = result.suggested_fix
    incident.relevant_files = json.dumps(result.relevant_files)
    incident.blast_radius = result.blast_radius
    incident.confidence = result.confidence
    incident.triage_duration_ms = result.duration_ms
    incident.severity = result.severity
    incident.affected_services = json.dumps(result.affected_services)
    incident.status = IncidentStatus.TRIAGED


async def _required_audio(audio: UploadFile) -> AudioUpload:
    result = await _read_and_validate_audio(audio, required=True)
    assert result is not None
    return result


RequiredAudio = Annotated[AudioUpload, Depends(_required_audio)]


@router.post("/transcribe")
async def transcribe(audio_upload: RequiredAudio) -> dict[str, str]:
    if _semaphore.locked():
        raise HTTPException(
            status_code=503,
            detail={"error": "Server at capacity", "retry_after": 5},
            headers={"Retry-After": "5"},
        )
    async with _semaphore:
        mistral = get_mistral_client()
        text = await transcribe_audio(
            mistral, audio_bytes=audio_upload.content, filename=audio_upload.filename
        )
    return {"text": text}


@router.post("/incidents", response_class=EventSourceResponse)
async def create_incident(
    deps: AppDepsDep,
    session: SessionDep,
    form: ValidatedForm,
    audio_upload: ValidatedAudio = None,
    image_uploads: ValidatedImages = [],
    log_uploads: ValidatedLogs = [],
) -> AsyncIterator[ServerSentEvent]:
    async with _semaphore:
        _root_span = _tracer.start_span("incident.pipeline")
        _root_span.set_attribute(
            SpanAttributes.OPENINFERENCE_SPAN_KIND,
            OpenInferenceSpanKindValues.CHAIN.value,
        )
        _root_ctx = trace.set_span_in_context(_root_span)
        _root_token = context.attach(_root_ctx)
        try:
            incident = Incident(
                title=form["title"],
                description=form["description"],
                category=form["category"],
                severity_hint=form["severity_hint"],
                reporter_email=form["reporter_email"],
            )
            incident_id = str(incident.id)
            _root_span.set_attribute("incident.id", incident_id)
            _root_span.set_attribute(
                SpanAttributes.INPUT_VALUE,
                json.dumps({
                    "title": form["title"],
                    "description": form["description"],
                    "category": form["category"],
                    "severity_hint": form["severity_hint"],
                }),
            )
            _root_span.set_attribute(SpanAttributes.INPUT_MIME_TYPE, "application/json")
            structlog.contextvars.bind_contextvars(incident_id=incident_id)

            yield _emit(incident_id, "stage", {"stage": "ingest", "status": "running"})

            session.add(incident)
            await session.commit()
            await session.refresh(incident)

            yield _emit(incident_id, "stage", {"stage": "ingest", "status": "done"})

            mistral = get_mistral_client()
            audio_context = ""
            provided_transcription = form.get("transcription", "").strip()

            if audio_upload:
                yield _emit(incident_id, "stage", {"stage": "transcription", "status": "running", "model": "voxtral-mini-latest"})
                transcription = await transcribe_audio(
                    mistral, audio_bytes=audio_upload.content, filename=audio_upload.filename
                )
                if not transcription:
                    yield _emit(
                        incident_id,
                        "error",
                        {"stage": "transcription", "error": "Transcription failed", "recoverable": True},
                    )
                else:
                    audio_context = f"{TRANSCRIPTION_TAG}: {transcription}"
                    yield _emit(incident_id, "transcription", {"text": transcription})
                yield _emit(incident_id, "stage", {"stage": "transcription", "status": "done"})
            elif provided_transcription:
                audio_context = f"{TRANSCRIPTION_TAG}: {provided_transcription}"

            image_context = ""
            if image_uploads:
                yield _emit(incident_id, "stage", {"stage": "image_analysis", "status": "running", "model": "mistral-small-latest"})
                try:
                    content_chunks: list[dict[str, str]] = [
                        {"type": "text", "text": "Describe these screenshots from an SRE incident. Focus on error messages, status codes, stack traces, or any technical details visible. Label each image."},
                    ]
                    for img in image_uploads:
                        encoded = base64.standard_b64encode(img.content).decode("utf-8")
                        ext = img.filename.rsplit(".", 1)[-1].lower()
                        mime = "image/png" if ext == "png" else "image/jpeg"
                        content_chunks.append({"type": "image_url", "image_url": f"data:{mime};base64,{encoded}"})

                    resp = await mistral.chat.complete_async(
                        model="mistral-small-latest",
                        messages=[{"role": "user", "content": content_chunks}],
                        max_tokens=500 * len(image_uploads),
                    )
                    image_desc = resp.choices[0].message.content if resp.choices else ""
                    image_context = f"[Image analysis ({len(image_uploads)} image(s))]: {image_desc}"
                    yield _emit(incident_id, "image_analysis", {"text": image_desc, "count": len(image_uploads)})
                    yield _emit(incident_id, "stage", {"stage": "image_analysis", "status": "done"})
                except Exception as exc:
                    _log.warning("image_analysis_failed", error=str(exc))
                    yield _emit(incident_id, "error", {"stage": "image_analysis", "error": str(exc), "recoverable": True})
                    yield _emit(incident_id, "stage", {"stage": "image_analysis", "status": "done"})

            log_context = ""
            if log_uploads:
                chars_per_log = 4000 // max(len(log_uploads), 1)
                log_parts = []
                for lf in log_uploads:
                    try:
                        log_text = lf.content.decode("utf-8")[:chars_per_log]
                        log_parts.append(f"[Log attachment ({lf.filename})]:\n{log_text}")
                    except UnicodeDecodeError:
                        _log.warning("log_decode_failed", filename=lf.filename)
                log_context = "\n\n---\n\n".join(log_parts)

            attachment_parts = [p for p in (audio_context, image_context, log_context) if p]
            attachment_summaries = "\n\n".join(attachment_parts)

            description_with_context = incident.description
            if attachment_summaries:
                description_with_context = f"{incident.description}\n\n{attachment_summaries}"

            yield _emit(incident_id, "stage", {"stage": "moderation", "status": "running", "model": "mistral-moderation-2603"})
            async with stage_span("moderation", model="mistral-moderation-2603"):
                mod_result = await moderate_text(
                    mistral, title=incident.title, description=description_with_context
                )
            yield _emit(
                incident_id,
                "moderation",
                {"passed": mod_result.passed, "scores": mod_result.scores},
            )
            yield _emit(incident_id, "stage", {"stage": "moderation", "status": "done"})

            if not mod_result.passed:
                incident.status = IncidentStatus.TRIAGE_FAILED
                session.add(incident)
                await session.commit()
                await session.refresh(incident)
                done_data = _incident_to_dict(incident)
                _root_span.add_event("stage_failed", {"stage": "moderation", "reason": "blocked"})
                _root_span.set_attribute(
                    SpanAttributes.OUTPUT_VALUE, json.dumps(done_data),
                )
                _root_span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, "application/json")
                _root_span.set_attribute("pipeline.outcome", "blocked")
                _root_span.set_status(trace.StatusCode.OK)
                yield _emit(
                    incident_id,
                    "blocked",
                    {
                        "reason": "moderation",
                        "flagged_categories": mod_result.flagged_categories,
                    },
                )
                yield _emit(incident_id, "done", done_data)
                complete(incident_id)
                return

            match = await find_duplicate(
                session=session,
                title=incident.title,
                affected_services=[],
                exclude_id=incident_id,
            )
            prior_context: dict[str, str | float] | None = None
            if match:
                try:
                    match_uuid = UUID(match.incident_id)
                    matched = (await session.exec(
                        select(Incident).where(Incident.id == match_uuid)
                    )).one_or_none()
                    if matched and matched.root_cause_hypothesis:
                        prior_context = {
                            "root_cause": matched.root_cause_hypothesis,
                            "suggested_fix": matched.suggested_fix or "",
                            "similarity": match.similarity,
                        }
                except (ValueError, Exception):
                    pass
                yield _emit(
                    incident_id,
                    "dedup",
                    {"match_id": match.incident_id, "similarity": round(match.similarity, 3)},
                )

            yield _emit(incident_id, "stage", {"stage": "classification", "status": "running", "model": "mistral-medium-latest"})
            async with stage_span("classification", model="mistral-medium-latest"):
                cls_result = await classify_incident(
                    mistral, title=incident.title, description=description_with_context
                )
            yield _emit(
                incident_id,
                "classification",
                {
                    "severity": cls_result.severity,
                    "category": cls_result.category,
                    "affected_services": cls_result.affected_services,
                },
            )
            yield _emit(incident_id, "stage", {"stage": "classification", "status": "done"})

            incident.severity = cls_result.severity
            incident.classified_category = cls_result.category
            incident.affected_services = json.dumps(cls_result.affected_services)
            incident.search_paths = json.dumps(cls_result.search_paths)
            session.add(incident)
            await session.commit()
            await session.refresh(incident)

            yield _emit(incident_id, "stage", {"stage": "triage", "status": "running", "model": "claude-sonnet-4-6"})
            try:
                triage_result: TriageResult | None = None
                async with stage_span("triage", model="claude-sonnet-4-6"):
                    async for event in triage_incident(
                        title=incident.title,
                        description=incident.description,
                        search_paths=cls_result.search_paths,
                        affected_services=cls_result.affected_services,
                        severity=cls_result.severity,
                        category=cls_result.category,
                        attachment_summaries=attachment_summaries,
                        prior_context=prior_context,
                    ):
                        if isinstance(event, TriageEvent):
                            yield _emit(
                                incident_id,
                                "agent",
                                {"action": event.action, "tool": event.tool, "file": event.file},
                            )
                        elif isinstance(event, TriageComplete):
                            triage_result = event.result

                if triage_result is None:
                    raise RuntimeError("triage_incident did not yield TriageComplete")
                _persist_triage(incident, triage_result)
                session.add(incident)
                await session.commit()
                await session.refresh(incident)
                yield _emit(incident_id, "triage", _triage_result_to_dict(triage_result))
            except Exception as exc:
                _log.warning("triage_failed", error=str(exc))
                _root_span.add_event("stage_failed", {"stage": "triage", "error": str(exc)})
                try:
                    await session.rollback()
                    incident.status = IncidentStatus.TRIAGE_FAILED
                    session.add(incident)
                    await session.commit()
                    await session.refresh(incident)
                except Exception:
                    _log.warning("triage_failed_persist_error")
                yield _emit(
                    incident_id,
                    "error",
                    {"stage": "triage", "error": str(exc), "recoverable": True},
                )
            yield _emit(incident_id, "stage", {"stage": "triage", "status": "done"})

            if incident.status == IncidentStatus.TRIAGED and not match:
                oncall = get_oncall_engineer()
                linear_issue = None

                yield _emit(incident_id, "stage", {"stage": "ticket", "status": "running"})
                try:
                    async with stage_span("ticket"):
                        linear_issue = await create_issue(
                            deps.http_client,
                            api_key=os.environ.get("LINEAR_API_KEY", ""),
                            team_id=os.environ.get("LINEAR_TEAM_ID", ""),
                            title=f"[{incident.severity}] {incident.title}",
                            description=_build_ticket_body(incident, oncall),
                            severity=incident.severity or "P3",
                        )
                    incident.linear_id = linear_issue.identifier
                    incident.linear_url = linear_issue.url
                    incident.status = IncidentStatus.TICKET_CREATED
                    session.add(incident)
                    await session.commit()
                    await session.refresh(incident)
                    yield _emit(
                        incident_id,
                        "ticket",
                        {"linear_id": linear_issue.identifier, "linear_url": linear_issue.url},
                    )
                except Exception as exc:
                    _log.warning("ticket_creation_failed", error=str(exc))
                    yield _emit(
                        incident_id,
                        "error",
                        {"stage": "ticket", "error": str(exc), "recoverable": True},
                    )
                yield _emit(incident_id, "stage", {"stage": "ticket", "status": "done"})

                yield _emit(incident_id, "stage", {"stage": "notify", "status": "running"})
                async with stage_span("notify"):
                    slack_ok, email_ok = await _notify(
                        deps.http_client,
                        incident=incident,
                        oncall=oncall,
                        ticket_url=linear_issue.url if linear_issue else None,
                        incident_id=incident_id,
                    )
                if slack_ok or email_ok:
                    incident.status = IncidentStatus.NOTIFIED
                    session.add(incident)
                    await session.commit()
                    await session.refresh(incident)
                yield _emit(incident_id, "notify", {"slack": slack_ok, "email": email_ok})
                yield _emit(incident_id, "stage", {"stage": "notify", "status": "done"})

            done_data = _incident_to_dict(incident)
            _root_span.set_attribute(
                SpanAttributes.OUTPUT_VALUE, json.dumps(done_data),
            )
            _root_span.set_attribute(SpanAttributes.OUTPUT_MIME_TYPE, "application/json")
            if incident.status == IncidentStatus.TRIAGE_FAILED:
                _root_span.set_attribute("pipeline.outcome", "partial_failure")
            else:
                _root_span.set_attribute("pipeline.outcome", "success")
            _root_span.set_status(trace.StatusCode.OK)
            yield _emit(incident_id, "done", done_data)

            complete(incident_id)
        except Exception as exc:
            _root_span.set_status(trace.StatusCode.ERROR, str(exc))
            _root_span.record_exception(exc)
            raise
        finally:
            _root_span.end()
            context.detach(_root_token)
            structlog.contextvars.clear_contextvars()


@router.get("/incidents/{incident_id}")
async def get_incident(
    session: SessionDep,
    incident_id: UUID,
) -> IncidentRead:
    result = await session.exec(select(Incident).where(Incident.id == incident_id))
    incident = result.one_or_none()
    if incident is None:
        raise HTTPException(status_code=404, detail={"error": "Incident not found"})
    return IncidentRead.model_validate(incident, from_attributes=True)


@router.get("/stats")
async def get_stats(session: SessionDep) -> dict[str, object]:
    from sqlalchemy import func

    from sqlmodel import col

    total = (await session.exec(select(func.count()).select_from(Incident))).one()

    severity_rows = await session.exec(
        select(Incident.severity, func.count())
        .where(col(Incident.severity).is_not(None))
        .group_by(Incident.severity)
    )
    by_severity = {row[0]: row[1] for row in severity_rows.all()}

    status_rows = await session.exec(
        select(Incident.status, func.count()).group_by(Incident.status)
    )
    by_status = {row[0]: row[1] for row in status_rows.all()}

    avg_row = await session.exec(
        select(func.avg(Incident.triage_duration_ms))
        .where(col(Incident.triage_duration_ms).is_not(None))
    )
    avg_triage = avg_row.one() or 0

    resolved = (await session.exec(
        select(func.count())
        .select_from(Incident)
        .where(col(Incident.resolved_at).is_not(None))
    )).one()

    from app.token_tracker import get_summary as token_summary

    return {
        "total_incidents": total,
        "by_severity": by_severity,
        "by_status": by_status,
        "avg_triage_duration_ms": round(avg_triage),
        "resolved_count": resolved,
        "token_usage": token_summary(),
    }


def _build_ticket_body(incident: Incident, oncall: str) -> str:
    read = IncidentRead.model_validate(incident, from_attributes=True)

    steps = "\n".join(f"- {s}" for s in (read.investigation_steps or []))
    files = "\n".join(f"- `{f}`" for f in (read.relevant_files or []))
    services = ", ".join(read.affected_services or [])

    return (
        f"## Triage Summary\n\n"
        f"**Severity:** {read.severity}\n"
        f"**On-call:** {oncall}\n"
        f"**Affected services:** {services or 'Unknown'}\n\n"
        f"### Root Cause\n{read.root_cause_hypothesis or 'N/A'}\n\n"
        f"### Suggested Fix\n{read.suggested_fix or 'N/A'}\n\n"
        f"### Investigation Steps\n{steps or 'N/A'}\n\n"
        f"### Relevant Files\n{files or 'N/A'}\n\n"
        f"---\n\n"
        f"## Original Report\n\n"
        f"**Title:** {read.title}\n"
        f"**Category:** {read.category}\n\n"
        f"{read.description}"
    )


async def _notify(
    client: httpx.AsyncClient,
    *,
    incident: Incident,
    oncall: str,
    ticket_url: str | None,
    incident_id: str,
) -> tuple[bool, bool]:
    async def _slack() -> bool:
        webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
        if not webhook_url:
            return False
        try:
            await post_incident(
                client,
                webhook_url=webhook_url,
                severity=incident.severity or "P3",
                title=incident.title,
                summary=incident.root_cause_hypothesis or incident.description[:200],
                ticket_url=ticket_url or "",
                oncall_name=oncall,
            )
            return True
        except Exception as exc:
            _log.warning("slack_notification_failed", error=str(exc))
            return False

    async def _email() -> bool:
        resend_key = os.environ.get("RESEND_API_KEY", "")
        from_addr = os.environ.get("RESEND_FROM_EMAIL", "")
        if not (resend_key and from_addr and incident.reporter_email):
            return False
        try:
            import resend

            resend.api_key = resend_key
            t = html_escape(incident.title)
            rca = html_escape(incident.root_cause_hypothesis or "Triage in progress")
            u = html_escape(ticket_url or "#", quote=True)
            await send_incident_email(
                to=incident.reporter_email,
                from_addr=from_addr,
                subject=f"[{incident.severity}] {incident.title}",
                html=f'<h2>{t}</h2><p>{rca}</p><p><a href="{u}">View Ticket</a></p>',
            )
            return True
        except Exception as exc:
            _log.warning("email_notification_failed", error=str(exc))
            return False

    slack_ok, email_ok = await asyncio.gather(_slack(), _email())
    return slack_ok, email_ok


def _incident_to_dict(incident: Incident) -> dict[str, Any]:
    return IncidentRead.model_validate(incident, from_attributes=True).model_dump(mode="json")
