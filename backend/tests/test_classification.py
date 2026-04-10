import json
from unittest.mock import AsyncMock, MagicMock

from app.classification import ClassificationResult, classify_incident

_VALID_PAYLOAD = {
    "severity": "P1",
    "category": "payment",
    "affected_services": ["PaymentProcessor"],
    "search_paths": ["src/PaymentProcessor/"],
    "urgency_reasoning": "Payment completely broken",
    "requires_deep_analysis": True,
}


def _mock_client(payload: dict) -> MagicMock:
    client = MagicMock()
    client.chat.complete_async = AsyncMock(
        return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(payload)))]
        )
    )
    return client


async def test_classify_incident_returns_structured_result():
    client = _mock_client(_VALID_PAYLOAD)

    result = await classify_incident(client, title="Payment down", description="504 on checkout")

    assert isinstance(result, ClassificationResult)
    assert result.severity == "P1"
    assert result.category == "payment"
    assert result.affected_services == ["PaymentProcessor"]
    assert result.search_paths == ["src/PaymentProcessor/"]
    assert result.requires_deep_analysis is True
    assert result.guardrails_blocked is False


async def test_classify_incident_passes_guardrails_param():
    client = _mock_client(_VALID_PAYLOAD)

    await classify_incident(client, title="t", description="d")

    call_kwargs = client.chat.complete_async.call_args.kwargs
    assert "guardrails" in call_kwargs
    assert len(call_kwargs["guardrails"]) == 1


async def test_classify_incident_handles_403_guardrails_block():
    import httpx
    from mistralai.client.errors import SDKError

    client = MagicMock()
    raw_resp = httpx.Response(status_code=403, text="Blocked by guardrails")
    client.chat.complete_async = AsyncMock(
        side_effect=SDKError("Blocked", raw_response=raw_resp)
    )

    result = await classify_incident(client, title="inject", description="bad")

    assert result.guardrails_blocked is True
    assert result.severity == "P2"


async def test_classify_incident_uses_boundary_markers():
    client = _mock_client(_VALID_PAYLOAD)

    await classify_incident(client, title="my title", description="my desc")

    call_kwargs = client.chat.complete_async.call_args.kwargs
    prompt_content = call_kwargs["messages"][0]["content"]
    assert "[USER_INPUT_START]" in prompt_content
    assert "[USER_INPUT_END]" in prompt_content
    assert "my title" in prompt_content
    assert "my desc" in prompt_content
