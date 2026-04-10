from unittest.mock import AsyncMock, MagicMock

from app.transcription import transcribe_audio


async def test_transcribe_audio_returns_text():
    mock_client = MagicMock()
    mock_client.audio.transcriptions.complete_async = AsyncMock(
        return_value=MagicMock(text="checkout page is crashing when I add items")
    )

    result = await transcribe_audio(
        mock_client, audio_bytes=b"RIFF\x00\x00\x00\x00", filename="recording.wav"
    )

    assert result == "checkout page is crashing when I add items"
    call_kwargs = mock_client.audio.transcriptions.complete_async.call_args.kwargs
    assert call_kwargs["model"] == "voxtral-mini-latest"


async def test_transcribe_audio_returns_empty_on_api_error():
    mock_client = MagicMock()
    mock_client.audio.transcriptions.complete_async = AsyncMock(
        side_effect=Exception("API timeout")
    )

    result = await transcribe_audio(
        mock_client, audio_bytes=b"RIFF\x00\x00\x00\x00", filename="recording.wav"
    )

    assert result == ""
