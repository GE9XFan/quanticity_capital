# IBKR Ingestion & Connectivity Module

## Purpose
Maintain resilient connectivity to Interactive Brokers TWS/Gateway, rotate market data subscriptions within IBKR constraints, and persist account/market data into Redis with precise TTL guarantees.

## Handshake Checklist
Collect the following inputs from the user before writing code:

| Input | Description | Notes |
|-------|-------------|-------|
| Connection host/port | TWS or Gateway address (`127.0.0.1:7497` paper, `7496` live) | ✅ Paper trading port `7497`; connect to local TWS. |
| Gateway vs. TWS | Whether automation connects to IB Gateway or full TWS UI | ✅ Use TWS (already running and configured). |
| Client ID pool | Reserved range that will not clash with manual sessions | ✅ Adopt default pool `101-120`. |
| Heartbeat cadence | Seconds between connectivity heartbeats | ✅ 5 seconds. |
| Reconnect backoff | Sequence of delays after disconnects | ✅ `[1, 5, 15, 30, 60]`. |
| Pacing window | Maximum subscription bursts before throttling | ✅ Enforce max 3 concurrent level-2 subscriptions. |
| Redis contracts | Confirm key patterns, TTL, and metadata expectations | Defaults listed in `DEFAULT_CONTRACTS` of `src/ingestion/ibkr/handshake.py`. |
| Symbol rotation groups | Universe and grouping for level-2 cycles | ✅ Use `DEFAULT_LEVEL2_GROUPS` (five trios + final pair). |
| Authentication | Location of IBKR credentials and auto-login status | ✅ TWS kept running; rely on existing session for auto-connect (no headless login). |

### Proposed Level-2 Rotation (5s windows, 3 concurrent symbols)

| Group | Symbols |
|-------|---------|
| grp1 | SPY, QQQ, IWM |
| grp2 | NVDA, AAPL, MSFT |
| grp3 | GOOGL, META, ORCL |
| grp4 | AMZN, TSLA, DIS |
| grp5 | V, COST, WMT |
| grp6 | GE, AMD *(2-symbol tail group)* |

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
   - Key: `raw:ibkr:l2:{symbol}` TTL 10s.
   - Payload: top 10 levels bid/ask with size, market maker, timestamp.
   - Rotation groups precomputed (see `config/ibkr.yml`), module manages subscribe/unsubscribe cycle in 5s windows.
   - Use `contract_overrides` to specify exchange/primary exchange for symbols requiring venue-specific depth (e.g., NASDAQ TotalView entitlements for NVDA/AAPL/MSFT).
2. **Top-of-Book Quotes**
   - Key: `raw:ibkr:quotes:{symbol}` TTL 6s.
   - Fields: bid, ask, last, bid/ask size, last size, volume, mark price, timestamp.
   - Implementation: snapshot polling via `src/ingestion/ibkr/quotes.py` using `ib_insync` with `reqMktData(..., snapshot=True)`.
3. **Account Summary**
   - Key: `raw:ibkr:account:summary` TTL 30s.
   - Includes cash, equity with loan, buying power, margin requirements.
   - Implementation target: `src/ingestion/ibkr/account.py` using `ib.accountSummary()` with 15s cadence.
4. **Positions**
   - Key: `raw:ibkr:account:positions` TTL 30s.
   - Per position (symbol, quantity, avg cost, realized PnL). Filter asset classes (default STK/OPT via config).
5. **PnL Streams**
   - Keys: `raw:ibkr:account:pnl` and `raw:ibkr:position:pnl:{symbol}` TTL 30s.
   - Account-level PnL plus per-symbol PnL snapshots (unrealized/realized at 15s cadence).
6. **Execution Feed**
   - Redis Stream `stream:ibkr:executions` (maxlen default 5000) storing full execution + commission details.
   - Snapshot key `raw:ibkr:execution:last` captures most recent execution for fast lookup; heartbeat `state:ibkr:executions` tracks listener health.
   - Payload: include all fields exposed via ib_insync `ExecDetails`, `OrderStatus`, and `CommissionReport` (order/contract identifiers, fill quantities, avg price, liquidity, commission, realized/unrealized PnL).
   - Startup flow: hydrate stream with `reqAllOpenOrdersAsync` + `reqExecutionsAsync`, then rely on live events; orphan commission reports are discarded to prevent empty contract/execution payloads.

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
