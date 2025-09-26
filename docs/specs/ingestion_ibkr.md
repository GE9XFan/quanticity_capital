# IBKR Ingestion & Connectivity Module

## Purpose
Maintain resilient connectivity to Interactive Brokers TWS/Gateway, rotate market data subscriptions within IBKR constraints, and persist account/market data into Redis with precise TTL guarantees.

## Connectivity Requirements
- Host: `127.0.0.1`, Port: `7497` (paper). Live port configurable (default `7496`).
- Client IDs: orchestrator assigns unique IDs per module; primary ingestion client defaults to 101 to avoid clashing with manual master client (1).
- Auto-reconnect with exponential backoff capped at 60s; detect duplicate client ID errors and increment ID modulo reserved range (101-120).
- Monitor TWS API connection status and network latency; log heartbeat every 5s.

## Responsibilities
- Manage subscriptions for:
  - Level-2 market depth (3 symbols per active subscription limit).
  - Top-of-book quotes.
  - Account updates, positions, PnL (account-level & per-position).
  - Order status and execution reports (shared with execution module via callback hooks).
- Rotate level-2 subscriptions in 5s windows per trio to cover symbol universe.
- Normalize data to consistent JSON structures and write to Redis.

## Data Capture Targets
1. **Level-2 Depth**
   - Key: `raw:l2:<symbol>` TTL 10s.
   - Payload: top 10 levels bid/ask with size, market maker, timestamp.
   - Rotation groups precomputed; scheduler requests subscription/unsubscription events.
2. **Top-of-Book Quotes**
   - Key: `raw:quotes:<symbol>` TTL 6s.
   - Fields: bid, ask, last, volume, implied volatility (if provided), timestamp.
3. **Account Summary**
   - Key: `raw:account:summary` TTL 30s.
   - Includes cash, equity with loan, buying power, margin requirements.
4. **Positions**
   - Key: `raw:account:positions` TTL 30s.
   - Per position (symbol, quantity, avg cost, realized PnL).
5. **PnL Streams**
   - Keys: `raw:account:pnl` and `raw:position:pnl:<symbol>` TTL 30s.
6. **Execution Feed**
   - All order executions appended to Redis Stream `stream:executions` with no TTL (archived daily to Postgres).

## Implementation Notes
- Use `ib_insync` for simplified async integration; wrap event loop integration carefully to avoid blocking.
- Subscribe/unsubscribe using `reqMktDepth`/`cancelMktDepth` while respecting pacing violations (maintain 2s delay after cancellations as per IBKR docs).
- Map IBKR error codes to categories; e.g., `100` (pacing violation) triggers scheduler slowdown, `366` (no data) logs warning and retries next rotation.
- Provide CLI `tools/ibkr_diag.py` to inspect connection status and active subscriptions.

## Redis Interaction
- Before writing depth snapshot, include metadata: `"source":"ibkr","ts":"...","sequence":<increment>`.
- Maintain index sets: `index:ibkr:l2_active` and `index:ibkr:quotes`.

## Failure Handling
- On disconnect, trigger orchestrator alert, pause level-2 rotation until reconnected.
- On repeated pacing violations, reduce rotation cadence to 7s and gradually restore.
- Validate payload freshness timestamps; discard stale updates >5s.

## Integration Testing
- Connect to TWS paper gateway, verify level-2 rotation logs for all symbols within 60s.
- Confirm Redis keys TTLs via CLI.
- Manually disable TWS network to validate auto-reconnect and alerting flow.
- Execute sample paper trade to ensure executions appear on `stream:executions`.
