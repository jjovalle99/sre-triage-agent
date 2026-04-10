from html import escape as html_escape
from urllib.parse import urlparse

import resend
import stamina


@stamina.retry(on=Exception, attempts=3, wait_initial=0.1, wait_max=2.0)
async def send_incident_email(
    *,
    to: str,
    from_addr: str,
    subject: str,
    html: str,
) -> None:
    params: resend.Emails.SendParams = {
        "from": from_addr,
        "to": [to],
        "subject": subject,
        "html": html,
    }
    await resend.Emails.send_async(params)


def _safe_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https", ""):
        return "#"
    return html_escape(url, quote=True)


async def send_resolution_email(
    *,
    to: str,
    from_addr: str,
    title: str,
    resolver: str,
    ttr_minutes: int,
    ticket_url: str,
) -> None:
    t = html_escape(title)
    r = html_escape(resolver)
    u = _safe_url(ticket_url)
    html = (
        f"<h2>Incident Resolved: {t}</h2>"
        f"<p>Resolved by <strong>{r}</strong> in {ttr_minutes} minutes.</p>"
        f'<p><a href="{u}">View Ticket</a></p>'
    )
    await send_incident_email(
        to=to,
        from_addr=from_addr,
        subject=f"Resolved: {title}",
        html=html,
    )
