# Alpha Vantage Endpoint Tracker

Use this table to capture the state of every Alpha Vantage endpoint. Update it before any development work begins and after each verification cycle.

| Endpoint | Status | Parameters Received | TTL (s) | Verification Artifact | Notes |
|----------|--------|---------------------|---------|------------------------|-------|
| REALTIME_OPTIONS (SPY, QQQ, IWM, NVDA, AAPL, MSFT, GOOGL, META, ORCL, AMZN, TSLA, DIS, V, COST, WMT, GE, AMD) | done | function=REALTIME_OPTIONS; symbols=Techascope equities + ETFs; require_greeks=true; cadence=10s | 30 | docs/verification/realtime_options_20250926.json | Sample: docs/samples/alpha_vantage/realtime_options/TSLA.json ; TTL confirmed at 30s ; 2025-09-26 – 17 symbols verified, TTL/heartbeat normal |
| VWAP (SPY, QQQ, IWM, NVDA, AAPL, MSFT, GOOGL, META, ORCL, AMZN, TSLA, DIS, V, COST, WMT, GE, AMD) | done | function=VWAP; interval=1min; cadence=30s | 300 | docs/verification/vwap_20250926.json | Sample: docs/samples/alpha_vantage/vwap/IBM.json ; TTL confirmed at 5 minutes ; 2025-09-26 – 17 symbols verified, TTL/heartbeat normal |
| MACD (SPY, QQQ, IWM, NVDA, AAPL, MSFT, GOOGL, META, ORCL, AMZN, TSLA, DIS, V, COST, WMT, GE, AMD) | done | function=MACD; interval=1min; series_type=close; fastperiod=12; slowperiod=26; signalperiod=9; cadence=30s | 300 | docs/verification/macd_20250926.json | Sample: docs/samples/alpha_vantage/macd/USDEUR.json ; 2025-09-26 – 17 symbols verified, TTL/heartbeat normal |
| BBANDS (SPY, QQQ, IWM, NVDA, AAPL, MSFT, GOOGL, META, ORCL, AMZN, TSLA, DIS, V, COST, WMT, GE, AMD) | done | function=BBANDS; interval=1min; time_period=20; series_type=close; nbdevup=2; nbdevdn=2; matype=0; cadence=30s | 300 | docs/verification/bbands_20250926.json | Sample: docs/samples/alpha_vantage/bbands/IBM.json ; 2025-09-26 – 17 symbols verified, TTL/heartbeat normal |

**Status Legend**
- `awaiting-params` – Endpoint identified but inputs not yet provided by the user.
- `ready-to-build` – All parameters + sample JSON supplied; implementation can start.
- `in-progress` – Code under development or awaiting initial validation.
- `awaiting-signoff` – Implementation complete, verification artifact produced, waiting for user approval.
- `done` – Endpoint accepted; note date of sign-off in the Notes column.

Record verification captures under `docs/verification/` using the pattern `<endpoint>_<YYYYMMDD>.json`.
