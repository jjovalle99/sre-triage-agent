# Frontend

Next.js 16 + React 19 incident submission UI. Dark theme, real-time SSE pipeline view.

For full architecture and setup, see the root [README.md](../README.md) and [QUICKGUIDE.md](../QUICKGUIDE.md).

## Local Development

```bash
bun install
bun dev
```

Runs at [localhost:3000](http://localhost:3000). Requires the backend at `:8000`.

## Components

| Component | File | Purpose |
|-----------|------|---------|
| IncidentForm | `incident-form.tsx` | 5-field form + email + evidence attachment |
| PipelineView | `pipeline-view.tsx` | Real-time SSE stage progress with collapsible triage report |
| SeverityBadge | `severity-badge.tsx` | Animated P0-P3 badge (gray pulse → colored) |
| DictationButton | `dictation-button.tsx` | Audio recording via MediaRecorder API |
| AttachEvidenceZone | `attach-evidence-zone.tsx` | Drag-and-drop file upload (image, log, audio) |
| StatsDrawer | `stats-drawer.tsx` | Token usage, cost, incident distribution |
| DeduplicationAlert | `deduplication-alert.tsx` | Similar incident warning with link |
| ManualResolveButton | `manual-resolve-button.tsx` | Resolution fallback when webhook is unavailable |

## SSE Hook

`use-incident-stream.ts` manages the connection to `POST /api/incidents`. Parses stage, triage, ticket, and error events. Supports cancellation via AbortController.

## Testing

```bash
bun test
```

## Linting

```bash
bun run lint
```

Biome handles both formatting and linting.

## Stack

- Next.js 16, React 19, Bun
- shadcn/ui, Tailwind CSS v4
- Geist font family
- Biome (lint + format)
- Testing Library + jsdom
