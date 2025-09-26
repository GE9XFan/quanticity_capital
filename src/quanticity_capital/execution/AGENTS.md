# Execution & Risk Management

Follow `docs/specs/execution_engine.md`.

## Modules
- `router.py` – translate approved signals into IBKR order objects, submit via shared client.
- `risk.py` – enforce position limits, session loss caps, Kelly/Achilles tolerances.
- `lifecycle.py` – monitor open orders, manage trailing stops/targets, publish updates.
- `persistence.py` – write trades/fills to Postgres (`trading.*` tables) and mirror Redis state.

## Integration Points
- Consumes `signal:approved:*` keys and pushes updates to `exec:order:*`, `signal:active:*`, `stream:trades`.
- Shares IBKR connection infra with ingestion module—coordinate via `core` factories.
- Expose manual override hooks via `cli` commands (cancel, adjust stops).
