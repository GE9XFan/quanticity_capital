# Alpha Vantage Endpoint Tracker

Use this table to capture the state of every Alpha Vantage endpoint. Update it before any development work begins and after each verification cycle.

| Endpoint | Status | Parameters Received | TTL (s) | Verification Artifact | Notes |
|----------|--------|---------------------|---------|------------------------|-------|
| REALTIME_OPTIONS (SPY, QQQ, IWM, NVDA, AAPL, MSFT, GOOGL, META, ORCL, AMZN, TSLA, DIS, V, COST, WMT, GE, AMD) | ready-to-build | function=REALTIME_OPTIONS; symbols=Techascope equities + ETFs; require_greeks=true; cadence=10s | 30 | — | Sample: docs/samples/alpha_vantage/realtime_options/TSLA.json ; TTL confirmed at 30s |
| VWAP (SPY, QQQ, IWM, NVDA, AAPL, MSFT, GOOGL, META, ORCL, AMZN, TSLA, DIS, V, COST, WMT, GE, AMD) | ready-to-build | function=VWAP; interval=1min; cadence=30s | 300 | — | Sample: docs/samples/alpha_vantage/vwap/IBM.json ; TTL confirmed at 5 minutes |
| MACD (SPY, QQQ, IWM, NVDA, AAPL, MSFT, GOOGL, META, ORCL, AMZN, TSLA, DIS, V, COST, WMT, GE, AMD) | ready-to-build | function=MACD; interval=1min; series_type=close; fastperiod=12; slowperiod=26; signalperiod=9; cadence=30s | 300 | — | Sample: docs/samples/alpha_vantage/macd/USDEUR.json |
| BBANDS (SPY, QQQ, IWM, NVDA, AAPL, MSFT, GOOGL, META, ORCL, AMZN, TSLA, DIS, V, COST, WMT, GE, AMD) | ready-to-build | function=BBANDS; interval=1min; time_period=20; series_type=close; nbdevup=2; nbdevdn=2; matype=0; cadence=30s | 300 | — | Sample: docs/samples/alpha_vantage/bbands/IBM.json |

**Status Legend**
- `awaiting-params` – Endpoint identified but inputs not yet provided by the user.
- `ready-to-build` – All parameters + sample JSON supplied; implementation can start.
- `in-progress` – Code under development or awaiting initial validation.
- `awaiting-signoff` – Implementation complete, verification artifact produced, waiting for user approval.
- `done` – Endpoint accepted; note date of sign-off in the Notes column.

Record verification captures under `docs/verification/` using the pattern `<endpoint>_<YYYYMMDD>.json`.
