from unittest.mock import AsyncMock, MagicMock, patch

from opentelemetry.sdk.trace import TracerProvider

from app.moderation import ModerationResult, moderate_text
from tests.conftest import CollectingExporter


async def test_moderate_text_creates_otel_span(
    otel_collector: tuple[CollectingExporter, TracerProvider],
) -> None:
    exporter, provider = otel_collector

    mock_response = MagicMock()
    mock_response.results = [
        MagicMock(category_scores={"jailbreaking": 0.1, "pii": 0.0})
    ]
    mock_client = AsyncMock()
    mock_client.classifiers.moderate_chat_async = AsyncMock(return_value=mock_response)

    with patch("app.moderation._tracer", provider.get_tracer("test")):
        result = await moderate_text(mock_client, title="test", description="desc")

    assert isinstance(result, ModerationResult)
    assert result.passed is True

    provider.force_flush()
    assert len(exporter.spans) == 1
    span = exporter.spans[0]
    assert span.name == "mistral.moderation"
    attrs = dict(span.attributes or {})
    assert attrs["llm.provider"] == "mistralai"
    assert attrs["llm.model"] == "mistral-moderation-2603"
