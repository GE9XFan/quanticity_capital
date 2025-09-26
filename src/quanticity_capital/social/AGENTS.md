# Social Distribution Hub

Implement per `docs/specs/social_hub.md`.

## Modules
- `queue.py` – Redis-backed queues (`social:queue:<channel>`) with approval flags and scheduled run times.
- `templating.py` – render Jinja2 templates using analytics/signals/trade context.
- `dispatchers.py` – connectors for Discord, Twitter, Telegram, Reddit with retry/backoff logic.
- `approvals.py` – integrate with watchdog/manual commands for message approval.
- `metrics.py` – push queue depth and failure stats for observability.

## Templates
- Store channel-tier templates under `social/templates/`. Keep Markdown/character limits per platform.
- Document template variables in module docstrings to reduce guesswork.
