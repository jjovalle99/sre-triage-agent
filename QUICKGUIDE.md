# Quick Start Guide

Everything runs via Docker Compose. No local Python or Node.js required.

## Prerequisites

- Docker Desktop (or Docker Engine + Compose v2)
- API keys for the services listed below (all have free tiers)

## Step 1: Clone

```bash
git clone <repository-url>
cd hackathon
```

## Step 2: Create environment file

```bash
cp .env.example .env
```

## Step 3: Get API keys

Open `.env` in your editor. Fill in each variable using the instructions below.

### Required

| Variable | Where to get it |
|----------|----------------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) → API Keys → Create Key |
| `MISTRAL_API_KEY` | [console.mistral.ai](https://console.mistral.ai) → API Keys → Create Key |
| `LINEAR_API_KEY` | [linear.app](https://linear.app) → Settings (gear icon) → API → Personal API keys → Create key |
| `LINEAR_TEAM_ID` | See [Finding your Linear Team ID](#finding-your-linear-team-id) below |
| `SLACK_WEBHOOK_URL` | See [Setting up Slack webhook](#setting-up-slack-webhook) below |
| `RESEND_API_KEY` | [resend.com](https://resend.com) → Dashboard → API Keys → Create API Key |
| `RESEND_FROM_EMAIL` | Use `onboarding@resend.dev` for testing (works without domain verification) |

### Optional

| Variable | Default | Notes |
|----------|---------|-------|
| `ON_CALL_ENGINEER` | `On-Call Engineer` | Name shown in tickets and notifications |
| `LINEAR_WEBHOOK_SECRET` | _(empty)_ | Only needed for automatic resolution detection. See [Step 7](#step-7-optional-resolution-webhook) |

### Finding your Linear Team ID

After creating your Linear API key, run this command (replace `YOUR_LINEAR_API_KEY` with your actual key):

```bash
curl -s \
  -H "Authorization: YOUR_LINEAR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ teams { nodes { id name } } }"}' \
  https://api.linear.app/graphql
```

The response contains your team's UUID. Copy the `id` value (looks like `a1b2c3d4-e5f6-...`).

> [!IMPORTANT]
> Linear API keys go directly in the `Authorization` header with no `Bearer` prefix. This is correct.

### Setting up Slack webhook

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App** → **From scratch**
3. Name it anything (e.g., "SRE Triage"), select your workspace
4. In the left sidebar, click **Incoming Webhooks**
5. Toggle **Activate Incoming Webhooks** to On
6. Click **Add New Webhook to Workspace** at the bottom
7. Select the channel where incident notifications should go
8. Copy the webhook URL (starts with `https://hooks.slack.com/services/...`)

## Step 4: Start the application

```bash
docker compose up --build
```

First build takes 3-5 minutes (downloads eShop codebase, installs dependencies, builds frontend). Subsequent starts use cached layers and are faster.

> [!NOTE]
> The `cloudflared` service prints a tunnel URL to its logs. You only need this for resolution webhooks ([Step 7](#step-7-optional-resolution-webhook)). Ignore it for now.

## Step 5: Verify

Open each URL and confirm it loads:

| URL | Expected |
|-----|----------|
| [localhost:3000](http://localhost:3000) | Incident form with dark theme |
| [localhost:8000/health](http://localhost:8000/health) | `{"status":"ok"}` |
| [localhost:6006](http://localhost:6006) | Arize Phoenix trace viewer |

All three must load before submitting an incident. Services start in order (Phoenix → backend → frontend), so if `:3000` loads, everything is healthy.

## Step 6: Submit a test incident

1. Open [localhost:3000](http://localhost:3000)
2. Fill in the form:
   - **Title**: `Payment processing timeout on checkout`
   - **Description**: `Users report the checkout page hangs for 30+ seconds when processing credit card payments. The PaymentProcessor service seems to be timing out. Error logs show connection pool exhaustion.`
   - **Category**: Payment
   - **Severity**: High
   - **Email**: your email address
3. Click **Submit**
4. Watch the pipeline stages execute in real time:
   - Moderation check (screens for prompt injection)
   - Severity classification (expects P1 or P2)
   - Codebase triage (agent searches eShop's PaymentProcessor)
   - Linear ticket creation
   - Slack and email notifications

The full pipeline takes 15-25 seconds. When complete, you see the triage result with root cause hypothesis, affected files, investigation steps, and a link to the Linear ticket.

5. Check your Slack channel for the incident notification
6. Check your email for the incident report
7. Open [localhost:6006](http://localhost:6006) to see the full distributed trace

## Step 7 (Optional): Resolution webhook

To close the loop (ticket resolved → reporter notified automatically):

1. Find the tunnel URL in cloudflared logs:
   ```bash
   docker compose logs cloudflared | grep "trycloudflare.com"
   ```
   Copy the URL (e.g., `https://random-words.trycloudflare.com`)

2. In Linear: Settings → API → Webhooks → Create webhook
   - **URL**: `<tunnel-url>/api/webhooks/linear`
   - **Resource types**: Issues

3. Copy the **Signing secret** from the webhook settings

4. Add it to `.env`:
   ```
   LINEAR_WEBHOOK_SECRET=the-signing-secret-you-copied
   ```

5. Restart the backend to pick up the new secret:
   ```bash
   docker compose restart backend
   ```

6. Mark a Linear ticket as "Done". The reporter receives a resolution email and the Slack channel gets a resolution message with time-to-resolve.

> [!TIP]
> If you skip webhook setup, use the **Mark Resolved** button in the UI instead. It triggers the same notification flow.

## Troubleshooting

**Build fails**
- Confirm Docker Desktop is running with at least 4GB RAM
- Confirm `.env` has no empty required keys (every line in the Required table above must have a value)

**Backend won't start**
- Run `docker compose logs backend` and check for errors
- Most common cause: invalid or expired API keys

**Phoenix slow to load**
- Phoenix takes 15-20 seconds to initialize. Wait for the healthcheck to pass before opening `:6006`

**Notifications not arriving**
- Slack: confirm `SLACK_WEBHOOK_URL` starts with `https://hooks.slack.com/services/`
- Email: confirm `RESEND_FROM_EMAIL` is `onboarding@resend.dev` or a verified Resend domain
- Check backend logs: `docker compose logs backend | grep -i "error\|fail"`

**Tunnel URL changed after restart**
- Quick tunnels generate a random URL each time. Reconfigure the Linear webhook URL after restarting cloudflared
