# IBKR Ingestion

Implements connectivity to TWS/Gateway per `docs/specs/ingestion_ibkr.md`.

## Key Duties
- Manage `ib_insync` connection lifecycle (client IDs 101+, auto-reconnect with capped backoff).
- Rotate level-2 subscriptions in scheduler-driven windows, respecting pacing limits.
- Normalize and publish Redis keys:
  - `raw:l2:<symbol>` (TTL 10s)
  - `raw:quotes:<symbol>` (TTL 6s)
  - `raw:account:*` snapshots (TTL 30s)
  - Streams `stream:executions`
- Surface diagnostics via CLI (`tools/ibkr_diag.py`).

## File Stubs
- `client.py` – gateway connection + reconnect logic.
- `subscriptions.py` – rotation scheduling.
- `handlers.py` – event callbacks → Redis writes.
