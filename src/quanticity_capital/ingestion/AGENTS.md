# Ingestion Module

Responsible for fetching external market data and normalizing it into Redis `raw:*` namespaces. Refer to `docs/specs/ingestion_alpha_vantage.md` and `docs/specs/ingestion_ibkr.md`.

## Subpackages
- `alpha_vantage/` – HTTP client, capability map enforcement, retries/backoff, redis writes.
- `ibkr/` – TWS connectivity, subscription rotation, event callbacks.

## Patterns
- Single orchestrator task per endpoint category; concurrency managed via scheduler semaphores.
- All outputs include metadata (`symbol`, `as_of`, `source`) and respect TTL scheme.
- Heartbeats + error counters written to `state:ingestion:*` keys.

## TODO Placeholders
- `alpha_vantage/client.py` – wraps aiohttp with rate awareness.
- `alpha_vantage/tasks.py` – job handlers triggered by scheduler events.
- `ibkr/client.py` – `ib_insync` integration.
- `ibkr/subscriptions.py` – rotation logic.
