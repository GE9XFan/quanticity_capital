# Phase Validation Checklist

Use this checklist before promoting any phase or layer to the next milestone. Evidence links should point to dashboards, tests, or documents stored in this repo.

## Universal Checks
- [ ] Contracts versioned and linked in `contracts/` (owner: Michael Merrick)
- [ ] Build Cards completed with verification results attached (see mapping below)
- [ ] Runbooks updated in relevant `runbooks/` directory
- [ ] Observability dashboards reviewed with on-call team
- [ ] Backups and retention policies tested
- [ ] Security/credential rotation reviewed
- [ ] Risks and open questions logged with owners

## Phase 1 – Data Foundation
- [ ] AlphaVantage & IBKR ingestion guides in `phase-1-data/layer-1-ingestion/` finalized
- [ ] Redis TimeSeries storage patterns validated against retention requirements (CARD_003, CARD_007)
- [ ] Schema registry (`schemas/`) populated and referenced by analytics consumers
- [ ] Rate limiting and retry strategies tested against sandbox environments

## Phase 2 – Analytics & Signals
- [ ] Greeks engine benchmarks recorded and meet SLA
- [ ] Regime classifier integration validated with historical replay (`regime_state` contract, CARD TBD)
- [ ] Backtest engine signed off with reproducible notebooks/tests
- [ ] Signal validator gating logic documented with failure cases

## Phase 3 – Execution & Risk
- [ ] OMS handles reject scenarios with documented failover runbook
- [ ] Position manager reconciliation tested after cold restart
- [ ] Risk alerts wired to monitoring stack and escalations exercised
- [ ] Compliance logging verified (orders, fills, overrides)

## Phase 4 – AI, Reporting, Social
- [ ] AI overseer prompt templates peer-reviewed
- [ ] Reporting templates validated across sample datasets
- [ ] Social broadcast throttles tested per platform policies
- [ ] Audit trail storage confirmed for AI decisions and distributions

## Phase 5 – Observability & Dashboard
- [ ] React dashboard deployed to staging with data freshness monitors
- [ ] Alert enrichment appended with runbook links and on-call owner
- [ ] Appendices cross-checked against live system configs
- [ ] Quarterly review calendar accepted by review board

## Contract & Build Card Mapping
- **Layer 1 – Data Ingestion**
  - Contracts: `option_chain`, `market_data`, `technical_indicators`, `alphavantage_rate_limit`
  - Build Cards: `CARD_001`, `CARD_002`, `CARD_004`, `CARD_005`, `CARD_006`
- **Layer 2 – Storage**
  - Contracts: `redis_timeseries_schema`
  - Build Cards: `CARD_003`, `CARD_007`, `CARD_008`, `CARD_009`
- **Layer 3 – Analytics**
  - Contracts: `greeks`, `liquidity_stress`, `regime_state`, `vpin_series`
  - Build Cards: TBD (to be created before phase start)
- **Layer 5 – Execution & Risk**
  - Contracts: `order_state`, `execution_fill`, `risk_limit`, `position_snapshot`
  - Build Cards: TBD
- **Layer 7 – AI Overseer & Reporting**
  - Contracts: `ai_verdict`, `narrative_block`, `report_artifact`, `dashboard_asset`, `social_alert`
  - Build Cards: TBD
