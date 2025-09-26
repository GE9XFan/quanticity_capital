# Config Directory Guide

## Purpose
Centralized YAML configuration consumed by `src/quanticity_capital.config.loader`. Values here feed runtime toggles, cadences, symbol universes, and alert thresholds—never hard-code equivalents in code.

## Files
- `runtime.yml` – enables/disables modules, concurrency settings, global toggles (e.g., watchdog mode, autopilot flag).
- `schedule.yml` – scheduler job definitions, cadences, jitter, token buckets (align with `docs/specs/scheduler*.md`).
- `symbols.yml` – symbol groups and capability maps (Alpha Vantage scope reset, IBKR rotation groups).
- `analytics.yml` – metric parameters, weighting for risk scores, thresholds used by analytics engine.
- `watchdog.yml` – prompt templates, confidence thresholds, rate limits for OpenAI watchdog.
- `observability.yml` – heartbeat expectations, alert routing (Telegram/email), log rotation overrides.

## Usage Notes
- Load with Pydantic models (`src/quanticity_capital/config/models.py`). Keep schemas synced with spec changes.
- Store secrets in `.env`; reference via `${ENV_VAR}` syntax if templating is needed.
- When changing cadences or symbols, update `docs/specs` if the contract changes and run targeted integration smoke tests.
