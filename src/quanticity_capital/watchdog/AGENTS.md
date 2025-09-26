# OpenAI Watchdog

Implements the oversight workflow in `docs/specs/openai_watchdog.md`.

## Structure
- `service.py` – orchestrates stream consumption, prompt assembly, response parsing.
- `prompts.py` – loads templates from `config/watchdog.yml` and Jinja2 files.
- `approvals.py` – interfaces with Telegram/Discord for manual approvals.
- `storage.py` – writes reviews to Redis (`watchdog:review:*`) and Postgres (`audit.watchdog_reviews`).
- `throttler.py` – enforces prompt rate limits, fallback to manual mode on failures.

## Guidelines
- Default to manual approval; autopilot toggles require explicit config updates.
- Log prompts/responses with minimal sensitive data; store raw responses when parsing fails.
- Provide programmatic API for social hub to fetch approved narratives.
