from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import stamina

from app.email import send_incident_email
from app.linear import LinearIssue, create_issue
from app.slack import post_incident


def _make_status_error(status_code: int) -> httpx.HTTPStatusError:
    response = httpx.Response(status_code, request=httpx.Request("POST", "https://test"))
    return httpx.HTTPStatusError(
        f"{status_code} error", request=response.request, response=response
    )


def _success_response() -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {
        "data": {
            "issueCreate": {
                "success": True,
                "issue": {"id": "abc", "identifier": "ENG-1", "url": "https://linear.app/ENG-1"},
            }
        }
    }
    return resp


def _ok_response() -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    return resp


@pytest.mark.asyncio
async def test_create_issue_retries_on_transient_http_error() -> None:
    with stamina.set_testing(False):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            side_effect=[_make_status_error(502), _success_response()]
        )

        result = await create_issue(
            mock_client,
            api_key="key",
            team_id="team",
            title="test",
            description="test",
            severity="P2",
        )

        assert isinstance(result, LinearIssue)
        assert mock_client.post.await_count == 2


@pytest.mark.asyncio
async def test_post_incident_retries_on_transient_http_error() -> None:
    with stamina.set_testing(False):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            side_effect=[_make_status_error(503), _ok_response()]
        )

        await post_incident(
            mock_client,
            webhook_url="https://hooks.slack.com/test",
            severity="P1",
            title="test",
            summary="test",
            ticket_url="https://linear.app/ENG-1",
            oncall_name="Alice",
        )

        assert mock_client.post.await_count == 2


@pytest.mark.asyncio
async def test_send_email_retries_on_transient_error() -> None:
    with stamina.set_testing(False):
        call_count = 0

        async def _flaky_send(params):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Connection reset")
            return {"id": "email-ok"}

        with patch("app.email.resend.Emails.send_async", side_effect=_flaky_send):
            await send_incident_email(
                to="test@example.com",
                from_addr="incidents@example.com",
                subject="test",
                html="<p>test</p>",
            )

        assert call_count == 2
