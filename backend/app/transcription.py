from dataclasses import dataclass

import structlog
from mistralai.client import Mistral
from mistralai.client.models import File
from opentelemetry import trace

_log = structlog.get_logger()
_tracer = trace.get_tracer(__name__)

_MODEL = "voxtral-mini-latest"
TRANSCRIPTION_TAG = "[Audio transcription]"


@dataclass(frozen=True)
class AudioUpload:
    content: bytes
    filename: str


async def transcribe_audio(
    client: Mistral,
    *,
    audio_bytes: bytes,
    filename: str,
) -> str:
    with _tracer.start_as_current_span("mistral.audio.transcription") as span:
        span.set_attribute("llm.provider", "mistralai")
        span.set_attribute("llm.model", _MODEL)
        span.set_attribute("audio.filename", filename)
        try:
            response = await client.audio.transcriptions.complete_async(
                model=_MODEL,
                file=File(file_name=filename, content=audio_bytes),
            )
            return response.text  # type: ignore[no-any-return]
        except Exception as exc:
            _log.warning("voxtral_transcription_failed", filename=filename, error=str(exc))
            span.set_attribute("transcription.error", True)
            return ""
