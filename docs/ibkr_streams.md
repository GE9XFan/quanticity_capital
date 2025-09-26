# IBKR Stream Tracker

Use this table to capture handshake details and verification status for each IBKR data stream.

| Stream | Status | Redis Key / Pattern | TTL (s) | Cadence Target | Notes |
|--------|--------|---------------------|---------|----------------|-------|
| Level-2 Depth Rotation | done | `raw:ibkr:l2:{symbol}` | 10 | 5s per trio | Module `src/ingestion/ibkr/level2.py`; docs/verification/ibkr_level2_20250927.json; 2025-09-27 – Full rotation verified, ISLAND/NASDAQ overrides active, depth data (10 levels) captured for all groups. |
| Top-of-Book Quotes | done| `raw:ibkr:quotes:{symbol}` | 6 | 3s | Module `src/ingestion/ibkr/quotes.py`; 2025-09-26 – Live verified with TWS, NVDA/AAPL/MSFT captured in Redis. |
| Account Summary | done | `raw:ibkr:account:summary` | 30 | 15s | Module `src/ingestion/ibkr/account.py`; docs/verification/ibkr_account_bundle_20250927.json; 2025-09-27 – Async path working, captures cash/equity/margin data. |
| Positions | done | `raw:ibkr:account:positions` | 30 | 15s | Module `src/ingestion/ibkr/account.py`; docs/verification/ibkr_account_bundle_20250927.json; 2025-09-27 – STK/OPT positions captured correctly. |
| Account PnL | done | `raw:ibkr:account:pnl` | 30 | 15s | Module `src/ingestion/ibkr/account.py`; docs/verification/ibkr_account_bundle_20250927.json; 2025-09-27 – Using pnlEvent/pnlSingleEvent with proper cleanup. |
| Per-Position PnL | done | `raw:ibkr:position:pnl:{symbol}` | 30 | 15s | Module `src/ingestion/ibkr/account.py`; docs/verification/ibkr_account_bundle_20250927.json; 2025-09-27 – Per-symbol PnL working for all positions. |
| Execution Stream | done | `stream:ibkr:executions` | stream | on event | Module `src/ingestion/ibkr/executions.py`; docs/verification/ibkr_executions_20250927.json; 2025-09-27 – Stream captures executions with commission data (maxlen 5000). |

**Status Legend**
- `awaiting-handshake` – Inputs pending.
- `ready-to-build` – Handshake complete; implementation can start.
- `in-progress` – Code under development or under initial validation.
- `awaiting-signoff` – Live validation complete, pending approval.
- `done` – Stream accepted; record date and verification artifact in Notes.

Update this tracker alongside `docs/specs/ingestion_ibkr.md` when handshake details change.
