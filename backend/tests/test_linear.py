import pytest

from app.linear import LinearIssue, create_issue
from tests.conftest import mock_httpx_client


@pytest.mark.asyncio
async def test_create_issue_returns_issue() -> None:
    mock_client, _ = mock_httpx_client({
        "data": {
            "issueCreate": {
                "success": True,
                "issue": {
                    "id": "abc-123",
                    "identifier": "ENG-42",
                    "url": "https://linear.app/team/issue/ENG-42",
                },
            }
        }
    })

    result = await create_issue(
        mock_client,
        api_key="lin_api_test",
        team_id="team-uuid",
        title="P0: payments down",
        description="## Summary\nPayments failing",
        severity="P0",
    )

    assert isinstance(result, LinearIssue)
    assert result.id == "abc-123"
    assert result.identifier == "ENG-42"
    assert result.url == "https://linear.app/team/issue/ENG-42"

    body = mock_client.post.call_args.kwargs["json"]
    assert body["variables"]["input"]["priority"] == 1
    assert body["variables"]["input"]["teamId"] == "team-uuid"


@pytest.mark.asyncio
async def test_create_issue_raises_on_graphql_error() -> None:
    mock_client, _ = mock_httpx_client({
        "errors": [{"message": "Team not found"}]
    })

    with pytest.raises(RuntimeError, match="Team not found"):
        await create_issue(
            mock_client,
            api_key="lin_api_test",
            team_id="team-uuid",
            title="test",
            description="test",
            severity="P2",
        )
