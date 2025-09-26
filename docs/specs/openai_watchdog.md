# OpenAI Watchdog

## Purpose
Review analytics and signals for consistency, generate human-readable commentary, and assist with social content while respecting manual approval workflows unless autopilot is explicitly enabled.

## Responsibilities
- Subscribe to `stream:analytics` and `stream:signals` for new events.
- Evaluate payloads using OpenAI models (default GPT-5 placeholder) to cross-check calculations, flag anomalies, and suggest actions.
- Produce commentary drafts for social channels with tier-specific variations.
- Manage approval workflow: manual (default) requires explicit confirmation via Telegram bot; autopilot (optional) auto-approves when confidence exceeds threshold.
- Log all interactions to Postgres (`audit.watchdog_reviews`).

## Workflow
1. Signal created → watchdog receives event.
2. Compose prompt including analytics snapshot, signal rationale, risk metrics, recent macro context.
3. Send to OpenAI API with configured model and temperature.
4. Parse response into structured output:
   - `analysis`: summary of alignment/mismatch.
   - `risk_flags`: list of concerns.
   - `narrative`: commentary for social use.
   - `confidence`: numeric score.
5. Store output in Redis `watchdog:review:<signal_id>` (TTL 1h) and Postgres.
6. Notify approval channel (Telegram/Discord DM) with summary and accept/reject options.
7. On approval, push to `signal:approved` / `social:queue` as appropriate.

## Modes & Controls
- Config key `watchdog.mode` (`manual`, `autopilot`). Manual is default at startup.
- Confidence thresholds configurable per strategy.
- Rate limiting: enforce max prompts per minute; fallback to manual-only if limit reached or API unavailable.
- Provide override commands: force approve, force reject, request re-review.

## Configuration
- `config/watchdog.yml`: prompt templates, confidence thresholds, autopilot enable flag, token budgets.
- Environment variables: `OPENAI_API_KEY`, optional organization/project IDs.

## Error Handling
- On API failure, log and mark review state `error`; signal remains pending for manual intervention.
- If response malformed, store raw text and trigger alert.
- Maintain retry queue with exponential backoff, max 3 attempts.

## Observability
- Heartbeat `system:heartbeat:watchdog` 15s.
- Metrics: prompts sent, approvals, rejections, autopilot usage.
- Logs to `logs/watchdog.log` with prompt/response IDs (no sensitive data).

## Integration Testing
- Use test prompts against live model or `gpt-4o-mini` for cost-effective validation.
- Verify manual approval flow by sending Telegram command and confirming state transition.
- Confirm autopilot disabled by default and requires explicit config.
