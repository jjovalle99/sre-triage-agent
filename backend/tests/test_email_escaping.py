from unittest.mock import AsyncMock, patch

import pytest

from app.email import _safe_url, send_resolution_email


@pytest.mark.asyncio
async def test_resolution_email_escapes_html_in_title() -> None:
    with patch("app.email.resend.Emails.send_async", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"id": "email-ok"}
        await send_resolution_email(
            to="test@example.com",
            from_addr="incidents@example.com",
            title='<script>alert("xss")</script>',
            resolver="Alice",
            ttr_minutes=10,
            ticket_url="https://linear.app/ENG-1",
        )

    params = mock_send.call_args.args[0]
    assert "<script>" not in params["html"]


def test_safe_url_blocks_javascript_scheme() -> None:
    assert _safe_url("javascript:alert(1)") == "#"


def test_safe_url_allows_https() -> None:
    assert _safe_url("https://linear.app/ENG-1") == "https://linear.app/ENG-1"
