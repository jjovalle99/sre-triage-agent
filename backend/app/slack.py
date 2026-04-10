import httpx
import stamina

_SEVERITY_COLOR = {"P0": "#EF4444", "P1": "#F97316", "P2": "#FACC15", "P3": "#60A5FA"}


@stamina.retry(on=httpx.HTTPStatusError, attempts=3, wait_initial=0.1, wait_max=2.0)
async def post_incident(
    client: httpx.AsyncClient,
    *,
    webhook_url: str,
    severity: str,
    title: str,
    summary: str,
    ticket_url: str,
    oncall_name: str,
) -> None:
    payload = {
        "text": f"[{severity}] {title}",
        "attachments": [
            {
                "color": _SEVERITY_COLOR.get(severity, "#888888"),
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*[{severity}] {title}*\n{summary}",
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"On-call: *{oncall_name}* | <{ticket_url}|View Ticket>",
                        },
                    },
                ],
            }
        ],
    }
    resp = await client.post(webhook_url, json=payload, timeout=10)
    resp.raise_for_status()


@stamina.retry(on=httpx.HTTPStatusError, attempts=3, wait_initial=0.1, wait_max=2.0)
async def post_resolution(
    client: httpx.AsyncClient,
    *,
    webhook_url: str,
    title: str,
    resolver: str,
    ttr_minutes: int,
    ticket_url: str,
) -> None:
    payload = {
        "text": f"Resolved: {title}",
        "attachments": [
            {
                "color": "#22C55E",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f":white_check_mark: *Resolved: {title}*\n"
                                f"Resolved by *{resolver}* in {ttr_minutes} minutes"
                            ),
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"<{ticket_url}|View Ticket>",
                        },
                    },
                ],
            }
        ],
    }
    resp = await client.post(webhook_url, json=payload, timeout=10)
    resp.raise_for_status()
