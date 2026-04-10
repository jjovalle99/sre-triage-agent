# Backend

FastAPI backend for the SRE triage agent. Runs the multi-model AI pipeline and integrates with Linear, Slack, and Resend.

For full architecture and setup, see the root [README.md](../README.md) and [QUICKGUIDE.md](../QUICKGUIDE.md).

## Local Development

```bash
uv sync
uv run uvicorn app.main:app --reload
```

Runs at [localhost:8000](http://localhost:8000). Requires `.env` with API keys (see [QUICKGUIDE.md](../QUICKGUIDE.md)).

## Modules

| Module | Purpose |
|--------|---------|
| `triage.py` | Claude Agent SDK codebase analysis (Read/Glob/Grep on eShop) |
| `classification.py` | Mistral Medium severity + service routing (JSON mode, temp=0.1) |
| `moderation.py` | Mistral Moderation prompt injection + PII screening |
| `transcription.py` | Voxtral Mini audio-to-text |
| `webhook.py` | HMAC-SHA256 Linear webhook verification + resolution parsing |
| `linear.py` | Linear GraphQL ticket creation (raw httpx) |
| `slack.py` | Slack Block Kit notifications (raw httpx) |
| `email.py` | Resend email (SDK async) |
| `dedup.py` | Incident deduplication (SequenceMatcher + Jaccard, 30-min window) |
| `observability.py` | OTel span context manager + structured logging |
| `token_tracker.py` | Per-model token count and cost tracking |
| `validation.py` | Magic bytes file validation, input sanitization |
| `models.py` | SQLModel + Pydantic schemas |
| `prompts.py` | Prompt construction with boundary markers |

## API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check (`{"status":"ok"}`) |
| `/api/incidents` | POST | Submit incident, returns SSE stream |
| `/api/incidents/:id` | GET | Get incident by ID |
| `/api/incidents/:id/stream` | GET | Reconnect to SSE stream (replays buffered events) |
| `/api/incidents/:id/resolve` | POST | Manual resolution fallback |
| `/api/webhooks/linear` | POST | Linear webhook receiver (HMAC verified) |
| `/api/stats` | GET | Incident counts + token usage stats |

## Testing

```bash
uv run pytest
```

140 tests across 38 files covering routes, integrations, triage, observability, and security.

## Linting

```bash
uv run ruff check
uv run ty check
```

## eShop Codebase

The [dotnet/eShop](https://github.com/dotnet/eShop) repo is downloaded as a tarball at Docker build time (not tracked in git). The build script also generates `eshop-map.md`, a service map injected into the triage prompt to scope Claude's search.

## Stack

- Python 3.12, FastAPI, uvicorn
- Claude Agent SDK, Mistral SDK
- SQLModel + aiosqlite (SQLite with WAL mode)
- structlog, OpenTelemetry, Arize Phoenix
- stamina (retry), slowapi (rate limiting)
