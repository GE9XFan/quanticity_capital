# Execution & Risk Management Module

## Purpose
Translate approved signals into IBKR orders, manage live positions with trailing stops and profit targets, and enforce portfolio-level risk guardrails.

## Responsibilities
- Subscribe to `signal:approved` entries, translate into IBKR order objects (single-leg options only initially).
- Submit orders through IBKR API, handle acknowledgements, and update Redis/Postgres with execution status.
- Apply risk controls: position sizing validation, max exposure per symbol, session loss caps, Kelly/Achilles guardrails.
- Manage live trades: update stops/targets, trail profits, close positions on rule triggers or manual override.
- Record detailed trade lifecycle for auditing and reporting.

## Order Workflow
1. Receive approved signal payload.
2. Validate prerequisites (account availability, position limits, data freshness).
3. Build IBKR order: specify contract, action, quantity, order type (limit/market), transmit flag.
4. Submit order via dedicated IBKR client ID (e.g., 201) to avoid clashing with market data client.
5. Listen for order status updates and execution details; update `exec:order:<trade_id>`.
6. Store fills in Postgres `trading.fills`; update `trading.trades` summary.
7. Initiate monitoring loop for trailing stops, take-profit adjustments, time-based exits.

## Risk Controls
- **Sizing Validation:** ensure requested contracts match Kelly/Achilles output ± tolerance.
- **Exposure Limits:** config-driven per symbol and global notional caps.
- **Session Loss Limit:** abort further signals if cumulative realized loss exceeds threshold; set `system:state:trading_halt` key.
- **Stop Management:** supports fixed price, percentage, volatility-adjusted stops; trails ratchet only upward for long positions.
- **Timeouts:** positions auto-closed if no target/stop triggered by specified time (e.g., market close minus buffer).

## Redis & Postgres Usage
- Redis keys: `exec:order:<trade_id>` (TTL 2h), `signal:active:<trade_id>`, `trade:state:<trade_id>`.
- Postgres tables: `trading.trades`, `trading.fills`, `trading.stop_adjustments`, `trading.execution_events`.
- Append events to Redis Stream `stream:trades` (no TTL) for dashboard streaming.

## Error Handling
- Handle IBKR error codes: re-submit on `100` (pacing) after delay, cancel on hard rejects (e.g., `201` order rejected).
- On partial fills, adjust outstanding quantity or close remainder per strategy guidelines.
- If connection lost, mark orders as `pending_recovery` and re-request open orders upon reconnect.

## Manual Controls
- Provide CLI commands for manual cancel, modify stops, flatten positions.
- Reflect manual actions in Postgres with user metadata.

## Observability
- Heartbeat `system:heartbeat:execution_engine` every 5s.
- Metrics: fill latency, slippage vs. mid, success rate, stop adjustments.
- Detailed logging to `logs/execution.log` with order/contract identifiers.

## Integration Testing
- Use paper account to execute sample trades; verify Redis/Postgres entries created.
- Simulate trailing stop adjustments by manipulating market data and confirm updates propagate.
- Force IBKR disconnect to ensure recovery logic fetches open orders and resumes monitoring.
