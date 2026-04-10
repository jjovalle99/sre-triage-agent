from unittest.mock import AsyncMock, MagicMock, patch

from opentelemetry.sdk.trace import TracerProvider

from app.transcription import transcribe_audio
from tests.conftest import CollectingExporter


async def test_transcribe_audio_creates_otel_span(
    otel_collector: tuple[CollectingExporter, TracerProvider],
) -> None:
    exporter, provider = otel_collector

    mock_response = MagicMock()
    mock_response.text = "checkout page is broken"
    mock_client = AsyncMock()
    mock_client.audio.transcriptions.complete_async = AsyncMock(return_value=mock_response)

    with patch("app.transcription._tracer", provider.get_tracer("test")):
        result = await transcribe_audio(
            mock_client, audio_bytes=b"fake", filename="test.wav"
        )

    assert result == "checkout page is broken"

    provider.force_flush()
    assert len(exporter.spans) == 1
    span = exporter.spans[0]
    assert span.name == "mistral.audio.transcription"
    attrs = dict(span.attributes or {})
    assert attrs["llm.provider"] == "mistralai"
    assert attrs["llm.model"] == "voxtral-mini-latest"
