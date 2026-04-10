import pytest

from app.slack import post_incident, post_resolution
from tests.conftest import mock_httpx_client


@pytest.mark.asyncio
async def test_post_incident_sends_formatted_message() -> None:
    mock_client, _ = mock_httpx_client({})

    await post_incident(
        mock_client,
        webhook_url="https://hooks.slack.com/test",
        severity="P0",
        title="Payments down",
        summary="PaymentProcessor throwing timeout exceptions",
        ticket_url="https://linear.app/team/issue/ENG-42",
        oncall_name="Alice",
    )

    mock_client.post.assert_awaited_once()
    call_kwargs = mock_client.post.call_args
    assert call_kwargs.args[0] == "https://hooks.slack.com/test"

    payload = call_kwargs.kwargs["json"]
    assert "P0" in payload["text"]
    assert "Payments down" in payload["text"]
    assert payload["attachments"][0]["color"] == "#EF4444"

    blocks = payload["attachments"][0]["blocks"]
    block_text = blocks[0]["text"]["text"]
    assert "Payments down" in block_text
    assert "PaymentProcessor" in block_text


@pytest.mark.asyncio
async def test_post_incident_includes_oncall_and_ticket_link() -> None:
    mock_client, _ = mock_httpx_client({})

    await post_incident(
        mock_client,
        webhook_url="https://hooks.slack.com/test",
        severity="P2",
        title="Minor UI issue",
        summary="Button misaligned",
        ticket_url="https://linear.app/issue/ENG-99",
        oncall_name="Bob",
    )

    payload = mock_client.post.call_args.kwargs["json"]
    blocks = payload["attachments"][0]["blocks"]
    all_text = " ".join(b["text"]["text"] for b in blocks if "text" in b)
    assert "Bob" in all_text
    assert "ENG-99" in all_text


@pytest.mark.asyncio
async def test_post_resolution_sends_formatted_message() -> None:
    mock_client, _ = mock_httpx_client({})

    await post_resolution(
        mock_client,
        webhook_url="https://hooks.slack.com/test",
        title="Payments down",
        resolver="Alice",
        ttr_minutes=42,
        ticket_url="https://linear.app/issue/ENG-42",
    )

    mock_client.post.assert_awaited_once()
    payload = mock_client.post.call_args.kwargs["json"]
    assert "resolved" in payload["text"].lower()
    blocks = payload["attachments"][0]["blocks"]
    all_text = " ".join(b["text"]["text"] for b in blocks if "text" in b)
    assert "Alice" in all_text
    assert "42" in all_text
