from dataclasses import dataclass

import httpx
import stamina

_ENDPOINT = "https://api.linear.app/graphql"

_CREATE_ISSUE = """
mutation IssueCreate($input: IssueCreateInput!) {
  issueCreate(input: $input) {
    success
    issue { id identifier url }
  }
}
"""

_PRIORITY_MAP = {"P0": 1, "P1": 2, "P2": 3, "P3": 4}


@dataclass(frozen=True)
class LinearIssue:
    id: str
    identifier: str
    url: str


@stamina.retry(on=httpx.HTTPStatusError, attempts=3, wait_initial=0.1, wait_max=2.0)
async def create_issue(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    team_id: str,
    title: str,
    description: str,
    severity: str,
) -> LinearIssue:
    variables = {
        "input": {
            "teamId": team_id,
            "title": title,
            "description": description,
            "priority": _PRIORITY_MAP.get(severity, 0),
        }
    }
    resp = await client.post(
        _ENDPOINT,
        headers={"Authorization": api_key, "Content-Type": "application/json"},
        json={"query": _CREATE_ISSUE, "variables": variables},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    if errors := data.get("errors"):
        raise RuntimeError(f"Linear API error: {errors[0]['message']}")

    issue = data["data"]["issueCreate"]["issue"]
    return LinearIssue(id=issue["id"], identifier=issue["identifier"], url=issue["url"])
