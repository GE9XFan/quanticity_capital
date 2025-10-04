# Pipeline Overview

All long-running components live inside `src.system.runtime`. Each stage is a plain coroutine that loops forever and stores its state in Redis.

| Stage | Module | Redis Writes | Description |
|-------|--------|--------------|-------------|
| Ingestion | `src/ingestion/unusual_whales.py` | `uw:ws:*`, `uw:rest:*` | WebSocket + REST feeds mirrored into snapshot hashes. |
| Ingestion (IB) | `src/ingestion/interactive_brokers.py` | `ib:status` | Placeholder loop until the IB API is wired. |
| Analytics | `src/analytics/core.py` | `analytics:<symbol>` | Derives simple statistics (SMA placeholder). |
| Signals | `src/signals/core.py` | `signals:pending`, `signals:latest:<symbol>` | Pushes momentum crossover intents. |
| Risk | `src/risk/core.py` | `risk:last:<symbol>`, `signals:approved` | Approves signals (replace with real rules). |
| Execution | `src/execution/core.py` | `execution:last:<symbol>`, `execution:fills` | Simulates fills and publishes them downstream. |
| Distribution | `src/distribution/core.py` | `distribution:*`, `distribution:social_queue` | Handles tiered announcement delays. |
| Reports | `src/reports/ai_commentator.py` | `reports:latest` | Summaries using Claude or fallback text. |

All modules expect a `redis.asyncio.Redis` client and the shared `Settings` object. There is no cross-module import spaghetti—everything coordinates through Redis.

## Key Settings
See `src/settings.py` for defaults. Tweak cadence or symbols through environment variables—no code edits required.

## Development Workflow

1. Start `python -m src.system.runtime`.
2. Watch logs or run `python scripts/show_latest.py` for the latest snapshots.
3. Modify a module (e.g., `signals/core.py` with your production logic).
4. Restart the runtime to pick up changes.

That’s it: one runtime, one datastore, clear data flow.
