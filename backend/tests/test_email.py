from unittest.mock import AsyncMock, patch

import pytest

from app.email import send_incident_email, send_resolution_email


@pytest.mark.asyncio
async def test_send_incident_email_calls_resend() -> None:
    with patch("app.email.resend.Emails.send_async", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"id": "email-abc"}
        await send_incident_email(
            to="reporter@example.com",
            from_addr="incidents@example.com",
            subject="[P0] Payments down",
            html="<h1>Incident</h1><p>Details</p>",
        )

    mock_send.assert_awaited_once()
    params = mock_send.call_args.args[0]
    assert params["to"] == ["reporter@example.com"]
    assert params["from"] == "incidents@example.com"
    assert params["subject"] == "[P0] Payments down"
    assert "<h1>Incident</h1>" in params["html"]


@pytest.mark.asyncio
async def test_send_resolution_email_calls_resend() -> None:
    with patch("app.email.resend.Emails.send_async", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"id": "email-res"}
        await send_resolution_email(
            to="reporter@example.com",
            from_addr="incidents@example.com",
            title="Payments down",
            resolver="Alice",
            ttr_minutes=42,
            ticket_url="https://linear.app/issue/ENG-42",
        )

    mock_send.assert_awaited_once()
    params = mock_send.call_args.args[0]
    assert params["to"] == ["reporter@example.com"]
    assert "resolved" in params["subject"].lower()
    assert "Alice" in params["html"]
    assert "42" in params["html"]


@pytest.mark.asyncio
async def test_send_incident_email_propagates_error() -> None:
    with patch("app.email.resend.Emails.send_async", new_callable=AsyncMock) as mock_send:
        mock_send.side_effect = Exception("API rate limit")
        with pytest.raises(Exception, match="API rate limit"):
            await send_incident_email(
                to="reporter@example.com",
                from_addr="incidents@example.com",
                subject="test",
                html="<p>test</p>",
            )
