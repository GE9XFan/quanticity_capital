# Social Distribution Hub

## Purpose
Coordinate the creation, approval, and dispatch of trading alerts, recaps, and market analysis across Discord, Twitter, Telegram, and Reddit, respecting tiered content rules and manual oversight.

## Responsibilities
- Maintain message templates per channel/tier and render content using analytics/signals/trade data.
- Manage sending cadence: event-driven alerts plus scheduled blasts (pre-market, midday, close, end-of-day).
- Queue messages in Redis (`social:queue:<channel>`) awaiting approval or scheduled time.
- Handle API interactions with each platform, including retries and rate-limit compliance.
- Log dispatched content to Postgres for auditing.

## Content Structure
- Base payload: `{ "message_id": "...", "channel": "discord", "tier": "premium", "body": {...}, "attachments": [...], "status": "pending" }`.
- Tier rules:
  - **Free:** high-level overnight move, major signals.
  - **Basic:** adds key analytics metrics, simplified commentary.
  - **Premium:** full narrative, dealer metrics, futures context, intraday updates.
- Formatting guidelines: Markdown for Discord/Reddit, short text for Twitter, HTML-safe for Telegram.

## Scheduling
- Event-driven triggers for new trades (entry/exit), significant analytics shifts, risk alerts.
- Scheduled jobs configured in scheduler (`social.blast.<channel>.<tier>`). Default cadences:
  - Discord premium: pre-market (08:15 ET), midday (12:30 ET), close (16:15 ET), end-of-day recap (20:00 ET).
  - Discord basic: pre-market + close.
  - Discord free: daily close recap.
  - Twitter: entries/exits + daily summary.
  - Telegram: pending approvals + premium recaps.
  - Reddit: end-of-day detailed post.

## Integrations
- **Discord:** Webhooks per tier channel; embed structures for metrics tables.
- **Twitter (X):** v2 API with OAuth2 app; maintain queue to respect posting limits (max 5 tweets/4h recommended).
- **Telegram:** Bot API sending to private approval chat + broadcast channels.
- **Reddit:** OAuth via PRAW; post to configured subreddit with flair tags.

## Approval Workflow
- Messages flagged `requires_approval` until watchdog/manual approval granted.
- Telegram command `/approve <message_id>` (or UI button) updates Redis -> dispatch.
- Auto-approval allowed for low-risk updates (e.g., overnight summary) when configured.

## Error Handling
- Retry transient failures (HTTP 5xx, timeouts) up to 3 times with backoff.
- On rate-limit, push message back to queue with delayed schedule.
- Alert on repeated failures via orchestrator notifications.

## Observability
- Heartbeat `system:heartbeat:social_hub` 30s.
- Metrics: messages queued, sent, failed, approvals pending.
- Logs: `logs/social.log` with message IDs and responses (sanitized).

## Integration Testing
- Use staging channels or sandbox accounts to validate formatting.
- Confirm queue -> approval -> dispatch flow using live APIs with low-frequency tests.
- Verify scheduled blasts trigger at correct times (simulate with accelerated scheduler settings).
