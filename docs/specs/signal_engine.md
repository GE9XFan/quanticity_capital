# Signal Engine

## Purpose
Evaluate analytics outputs to generate trade signals for defined strategies (0DTE, 1DTE, 14DTE, MOC imbalance) with risk-aware sizing toggled between Kelly and Achilles methods.

## Responsibilities
- Pull latest analytics bundles from Redis, validate freshness, and compute strategy-specific entry/exit conditions.
- Determine position sizing using selected risk model per strategy; produce recommended contract counts or notional.
- Create signal objects stored in Redis (`signal:pending:<symbol>:<strategy>`) with full context (analytics snapshot, sizing rationale, risk limits).
- De-duplicate and throttle signals to prevent churn; track active signals and their statuses.
- Notify OpenAI watchdog for review/commentary and execution module for approval workflow.

## Strategy Templates
1. **0DTE Options (SPY/QQQ/IWM)**
   - Entry triggers: volatility regime `calm/elevated`, dealer gamma flips, VPIN spikes, liquidity thresholds.
   - Trade types: directional and gamma scalping.
2. **1DTE Options (SPY/QQQ/IWM)**
   - Similar metrics with reduced sensitivity; include overnight risk adjustments.
3. **14DTE Techascope Equities**
   - Focus on dealer skew, IV smile curvature, macro overlays, correlations.
4. **MOC Imbalance Strategy**
   - Triggered when MOC imbalance exceeds notional threshold and aligns with macro/futures signals.

## Signal Structure
```json
{
  "signal_id": "20250924-SPY-0dte-001",
  "symbol": "SPY",
  "strategy": "0dte",
  "action": "BUY_CALL_SPREAD",
  "entry": {"type": "MARKET", "limit": null},
  "size": {"contracts": 5, "sizing_model": "kelly", "details": {...}},
  "analytics_ref": "derived:analytics:SPY",
  "risk": {"max_loss": 1500, "take_profit": 2300, "trail": {"type": "percentage", "value": 0.3}},
  "meta": {"generated_at": "...", "confidence": 0.72}
}
```

## Risk Models
- **Kelly Fraction:** uses expected edge from dealer edge attribution and estimated hit rate; configurable risk caps.
- **Achilles (conservative):** predetermined fraction based on volatility regime and liquidity stress.
- Toggle stored in Postgres `reference.strategy_config` and cached in Redis `config:strategy:<name>`.

## Workflow
1. Scheduler triggers evaluation every 10s (strategy-specific cadence adjustable).
2. For each symbol/strategy, compute signal state → compare to last emitted state.
3. If new signal, write to `signal:pending` with TTL 30m and push event to `stream:signals`.
4. Await watchdog approval or manual override; once approved, execution engine picks up from `signal:approved`.
5. Update `signal:active` upon order submission; archive on closure to Postgres.

## Dependencies
- Redis for analytics data and signal storage.
- Postgres for configuration and archiving.
- Watchdog + execution modules for downstream actions.

## Error Handling
- If analytics stale, skip symbol and record reason in log.
- If sizing model returns invalid value, fallback to minimum contract size and flag risk.
- Detect repeated rejections and dampen signal frequency (cooldown).

## Observability
- Emit evaluation metrics to `metrics:signals` (signals generated, approved, rejected).
- Heartbeat key `system:heartbeat:signal_engine` (10s).

## Integration Testing
- Run with live analytics feed to confirm signal creation and TTL behavior.
- Simulate Kelly vs. Achilles toggles and verify size outputs change accordingly.
- Verify deduplication by triggering same conditions twice within cooldown window.
