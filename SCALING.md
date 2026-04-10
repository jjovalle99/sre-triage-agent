# SCALING.md

## Cost Model

### Per-model pricing

Rates used in `token_tracker.py`, sourced from provider pricing pages:

| Model | Input ($/M tokens) | Output ($/M tokens) | Role |
|-------|-------------------|---------------------|------|
| `claude-sonnet-4-6` | $3.00 | $15.00 | Codebase triage |
| `mistral-medium-latest` | $0.40 | $2.00 | Classification |
| `mistral-small-latest` | $0.15 | $0.60 | Image analysis |
| `voxtral-mini-latest` | $0.04 | $0.04 | Audio transcription |
| `mistral-moderation-2603` | $0.00 | $0.00 | Guardrails (free) |

### Measured cost per incident

From test runs (5 incidents via `/api/stats`):

```json
"token_usage": {
  "by_model": {
    "claude-sonnet-4-6": {
      "prompt_tokens": 5027,
      "completion_tokens": 777,
      "estimated_cost_usd": 0.026736
    }
  },
  "estimated_cost_usd": 0.026736
}
```

Average cost per triaged incident: **~$0.007** (Claude triage only — Mistral classification and moderation are negligible/free). Token volumes are lower than initially estimated because classification-driven search scoping keeps Claude tool calls focused.

Claude dominates cost at ~98% of total. This validates the multi-model approach: using Claude for classification would cost ~7.5x more for that step with no quality benefit.

### Cost comparison: multi-model vs single-model

Using measured per-incident cost (~$0.007) vs hypothetical Claude-only (same token volumes at Claude rates):

| Approach | Moderation | Classification | Image | Triage | Total |
|----------|-----------|---------------|-------|--------|-------|
| Multi-model (measured) | Free | < $0.001 | < $0.001 | ~$0.007 | ~$0.007 |
| Claude-only (projected) | $0.001 | $0.005 | $0.008 | ~$0.007 | ~$0.021 |

The non-triage steps are **14x cheaper** with specialized models ($0.001 vs $0.014). The bigger win is using each model for what it's best at: a dedicated moderation classifier beats repurposing a chat model for safety screening.

## Latency Model

### Measured per-stage latency

From structured logs (`stage_complete` events across 5 test incidents):

| Stage | Measured (avg) | Notes |
|-------|---------------|-------|
| Moderation | ~420ms | Mistral Moderation API, single call |
| Classification | ~1.5s | Mistral Medium, JSON mode + inline guardrails |
| Codebase triage | ~123s | Claude Agent SDK, multiple Grep/Read tool calls |
| Ticket creation | ~500ms | Linear GraphQL mutation |
| Notifications | ~2.4s | Slack + email via `asyncio.gather` |
| **Total (text-only)** | **~127s** | |

The triage step dominates latency at ~96% of total time. Each Claude tool call (Grep, Read) is a round trip to the API. The `max_turns=15` budget prevents runaway searches. Classification-driven search scoping narrows the search space before Claude runs its first tool call.

**Sample `stage_complete` log (real output):**

```json
{"stage": "classification", "duration_ms": 869, "model": "mistral-medium-latest",
 "event": "stage_complete", "incident_id": "3ea1991c-...",
 "trace_id": "8019498f0517a3d9eb608a92b0a8038f", "span_id": "a944fe88cf385977",
 "level": "info", "timestamp": "2026-04-09T23:33:48.036250Z"}
```

## Current Architecture Constraints

| Constraint | Current | Limit |
|-----------|---------|-------|
| Concurrent triages | `asyncio.Semaphore(3)` | 3 simultaneous sessions |
| Database | SQLite (WAL mode) | Single writer, adequate for demo |
| Token tracker | In-memory dict | Resets on restart |
| SSE buffer | 50 events/incident | In-memory, per-process |
| Rate limiting | `slowapi` 10 req/min | Per-IP, in-memory |

These constraints are appropriate for a demo/single-instance deployment. The system handles the hackathon evaluation workload without issues.

## Scaling Strategy

### 10x volume (~30 incidents/hour)

| Change | Why |
|--------|-----|
| SQLite → PostgreSQL | Concurrent writes from multiple workers |
| Add task queue (Celery or Dramatiq) | Decouple HTTP request from triage processing |
| Redis for SSE buffer | Shared state across workers |
| Redis for rate limiting | `slowapi` with Redis backend instead of in-memory |
| Increase semaphore to ~10 | More concurrent triages per worker |

Estimated monthly cost at 30 incidents/hour (21,600/month): 21,600 x $0.007 = ~$150/month in LLM costs. Infrastructure costs (Postgres, Redis, 2-3 workers) add ~$100-200/month.

### 100x volume (~300 incidents/hour)

| Change | Why |
|--------|-----|
| Horizontal scaling (3-5 workers) | Distribute triage load |
| Batch classification | Group similar incidents for efficiency |
| Cache eshop-map.md in Redis | Avoid repeated file reads |
| Dedicated model endpoints | Reserved capacity for latency SLAs |
| Incident priority queue | P0/P1 triaged before P2/P3 |

At this scale (216,000 incidents/month), LLM cost: 216,000 x $0.007 = ~$1,500/month. The hybrid model architecture keeps non-triage costs negligible — using Claude for classification and moderation would add ~$3,000/month with no quality improvement on those mechanical steps.

### What does NOT need to change

- The pipeline structure (moderation → classify → triage → ticket → notify) works at any scale
- Claude Agent SDK's async generator model is already non-blocking
- `stamina` retry logic handles transient API failures at any volume
- SSE streaming works per-connection with no shared state bottleneck
- Docker Compose structure maps directly to Kubernetes Deployment/Service definitions

## Tech Choice Justifications

| Choice | Alternatives considered | Why this one |
|--------|------------------------|-------------|
| Claude Sonnet for triage | GPT-4o | Native tool use (Read/Glob/Grep) via Agent SDK. No custom tool wrappers needed. Structured output via JSON schema |
| Mistral Medium for classification | Claude Haiku 4.5, GPT-4o-mini | $0.40/M input vs $1.00 (Haiku 4.5) vs $0.15 (4o-mini). JSON mode is reliable. Inline guardrails at zero extra cost |
| Mistral Moderation for guardrails | OpenAI Moderation, custom classifier | 11 harm categories including jailbreaking. Free. Dedicated classifier, not a chat model repurposed |
| Voxtral Mini for STT | Whisper, Deepgram | $0.04/M tokens (~$0.002/min). Native Mistral SDK integration (same client). Supports 6 audio formats |
| SQLite over Postgres | Postgres, DynamoDB | Zero infrastructure for demo. WAL mode handles concurrent reads. Single writer is fine for 3 concurrent triages |
| `stamina` over `tenacity` | tenacity, custom retry | Simpler API, sensible defaults (exponential backoff, jitter). 3 retries is the right number for external APIs |
| `structlog` over stdlib logging | stdlib logging, loguru | Bound context pattern (`contextvars`) for per-incident fields. OTel trace_id injection via custom processor. JSON output is Phoenix-compatible |
| Arize Phoenix over Jaeger | Jaeger, Langfuse, LangSmith | Single Docker container, no external deps. OpenInference auto-instrumentors for Claude Agent SDK + Mistral. Free, self-hosted |
| Raw httpx over Linear SDK | linear-api (PyPI) | Third-party `linear-api` is v0.2.0, sync-only. One GraphQL mutation doesn't justify a dependency |
| Raw httpx over slack-sdk | slack-sdk | Incoming webhooks are a plain HTTPS POST with JSON. The full SDK is 50MB+ for a single POST call |
