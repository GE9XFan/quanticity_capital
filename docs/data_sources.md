# Data Sources & Storage Contracts

This guide captures every external data feed, the exact API calls we make, and the Redis/Postgres
contracts that store their outputs. Flesh out each subsection with the sanctioned specs and sample
payloads before implementation resumes.

### Environment Prefixes
- All Redis keys are written with environment prefix (`dev:`, `staging:`, `prod:`). Example key
  references omit the prefix for clarity.
- Payload schema versions are appended when breaking changes occur (e.g., `raw:ibkr:bars:{symbol}:1min:v1`).
- `.env` controls target environment and secrets; vendor payloads contain no PII once stored in Redis.

## Naming Convention (Proposal)
- Prefix by lifecycle: `raw:` for direct API captures, `derived:` for analytics outputs, `state:` for
  heartbeats/metadata, `stream:` for Redis Streams, `config:` for cached configuration, `index:` for
  lookup sets.
- Key template: `scope:source:entity[:context]` where `context` is optional (symbol, account code,
  strategy).
- Metadata envelope stored with every JSON payload:
  ```json
  {
    "source": "alpha_vantage",
    "entity": "realtime_options",
    "context": "SPY",
    "requested_at": "2025-09-27T14:32:11Z",
    "ttl_applied": 24,
    "request_params": {...},
    "data": { /* vendor payload */ }
  }
  ```
- Default write mode is overwrite; Streams (`stream:*`) append by design.

## Alpha Vantage

-### General Notes
- Base documentation: <https://www.alphavantage.co/documentation/>.
- All requests include `apikey=<ALPHAVANTAGE_API_KEY>` from environment.
- Retry policy: honor `Information` / `Note` throttling messages; shared ingestion runner handles
  exponential backoff `[1s, 3s, 7s]` and surfaces failures without writing stale payloads.
- Redis payload envelope must follow the metadata schema defined at the top of this document.
- Cadence and TTL values are intentionally left `tbd` until we finalize scheduling; populate columns
  once rate plans are confirmed.
- Symbol coverage:
  - Options/technical indicators operate on the full Techascope universe (equities + ETFs: SPY, QQQ, IWM included).
  - News & sentiment excludes ETFs (no responses for SPY/QQQ/IWM).
  - Macro endpoints are global and symbol agnostic.
  - Fundamentals cover equities only (exclude SPY/QQQ/IWM unless Alpha Vantage adds support); retain
    raw JSON in Redis with long TTLs rather than Postgres mirroring for now.
- Intraday analytics favour IBKR 1-minute bars (`raw:ibkr:bars:{symbol}:1min`) with Alpha Vantage
  series kept purely as fallback redundancy.

### Options & Technical Indicators
| Endpoint | Alpha Vantage doc | Required params | Sample payload | Redis key | Storage mode | Notes |
|----------|-------------------|-----------------|----------------|-----------|--------------|-------|
| REALTIME_OPTIONS | [Option Chain](https://www.alphavantage.co/documentation/#realtime-options) | `function=REALTIME_OPTIONS`, `symbol=<ticker>`, `require_greeks=true` | `docs/samples/alpha_vantage/realtime_options/TSLA.json` | `raw:alpha_vantage:realtime_options:{symbol}` | Overwrite | Applies to entire Techascope universe (SPY/QQQ/IWM included). Provides bid/ask/last plus Greeks; capture contract list as-is with snapshot timestamp. |
| TIME_SERIES_INTRADAY | [Intraday](https://www.alphavantage.co/documentation/#intraday) | `function=TIME_SERIES_INTRADAY`, `symbol`, `interval=1min`, `outputsize=full`, `extended_hours=true` | `docs/samples/alpha_vantage/time_series_intraday/IBM.json` | `raw:alpha_vantage:time_series_intraday:{symbol}` | Overwrite (full payload) | Fallback only—IBKR bars are the primary intraday source. Persist full AV response for redundancy. |
| VWAP | [VWAP](https://www.alphavantage.co/documentation/#vwap) | `function=VWAP`, `symbol`, `interval=1min`, `series_type=close` | `docs/samples/alpha_vantage/vwap/IBM.json` | `raw:alpha_vantage:vwap:{symbol}` | Overwrite | Techascope universe incl. ETFs. Store technical series map keyed by timestamp. |
| MACD | [MACD](https://www.alphavantage.co/documentation/#macd) | `function=MACD`, `symbol`, `interval=1min`, `series_type=close`, `fastperiod=12`, `slowperiod=26`, `signalperiod=9` | `docs/samples/alpha_vantage/macd/USDEUR.json` | `raw:alpha_vantage:macd:{symbol}` | Overwrite | Techascope universe incl. ETFs. Keep `MACD`, `MACD_Signal`, `MACD_Hist` per timestamp. |
| BBANDS | [BBANDS](https://www.alphavantage.co/documentation/#bbands) | `function=BBANDS`, `symbol`, `interval=1min`, `time_period=20`, `series_type=close`, `nbdevup=2`, `nbdevdn=2`, `matype=0` | `docs/samples/alpha_vantage/bbands/IBM.json` | `raw:alpha_vantage:bbands:{symbol}` | Overwrite | Techascope universe incl. ETFs. Store upper/lower/middle bands keyed by timestamp. |

### News & Market Movers
| Endpoint | Alpha Vantage doc | Required params | Sample payload | Redis key | Storage mode | Notes |
|----------|-------------------|-----------------|----------------|-----------|--------------|-------|
| TOP_GAINERS_LOSERS | [Top Gainers & Losers](https://www.alphavantage.co/documentation/#gainer-loser) | `function=TOP_GAINERS_LOSERS` | `docs/samples/alpha_vantage/top_gainers_losers/sample.json` | `raw:alpha_vantage:top_gainers_losers` | Overwrite | Aggregate response with sections `top_gainers`, `top_losers`, `most_actively_traded`; no symbol parameter. |
| NEWS_SENTIMENT | [News & Sentiment](https://www.alphavantage.co/documentation/#news-sentiment) | `function=NEWS_SENTIMENT`, `tickers=<symbol>`, `limit=50`, `sort=LATEST` | `docs/samples/alpha_vantage/news_sentiment/sample.json` | `raw:alpha_vantage:news_sentiment:{symbol}` | Overwrite | Equities only (Alpha Vantage returns no data for SPY/QQQ/IWM). Payload includes `items`, `feed`, sentiment/relevance scores. Maintain array order for downstream analytics. |

### Macro Series
| Endpoint | Alpha Vantage doc | Required params | Sample payload | Redis key | Storage mode | Notes |
|----------|-------------------|-----------------|----------------|-----------|--------------|-------|
| REAL_GDP | [Real GDP](https://www.alphavantage.co/documentation/#real-gdp) | `function=REAL_GDP`, `interval=quarterly` | `docs/samples/alpha_vantage/macro/real_gdp.json` | `raw:alpha_vantage:macro:real_gdp` | Overwrite | Store entire `data` array; include unit info. |
| CPI | [Consumer Price Index](https://www.alphavantage.co/documentation/#cpi) | `function=CPI`, `interval=monthly` | `docs/samples/alpha_vantage/macro/cpi.json` | `raw:alpha_vantage:macro:cpi` | Overwrite | Preserve `unit` for analytics normalization. |
| INFLATION | [Inflation](https://www.alphavantage.co/documentation/#inflation) | `function=INFLATION` | `docs/samples/alpha_vantage/macro/inflation.json` | `raw:alpha_vantage:macro:inflation` | Overwrite | Similar structure to CPI. |
| TREASURY_YIELD | [Treasury Yield](https://www.alphavantage.co/documentation/#treasury-yield) | `function=TREASURY_YIELD`, `interval=weekly`, `maturity=10year` | `docs/samples/alpha_vantage/macro/treasury_yield_10year.json` | `raw:alpha_vantage:macro:treasury_yield:10year` | Overwrite | Capture `maturity` in key context. |
| FEDERAL_FUNDS_RATE | [Federal Funds Rate](https://www.alphavantage.co/documentation/#interest-rate) | `function=FEDERAL_FUNDS_RATE`, `interval=monthly` | `docs/samples/alpha_vantage/macro/federal_funds_rate.json` | `raw:alpha_vantage:macro:federal_funds_rate` | Overwrite | Data array with monthly rate. |

### Fundamentals
| Endpoint | Alpha Vantage doc | Required params | Sample payload | Redis key | Storage mode | Notes |
|----------|-------------------|-----------------|----------------|-----------|--------------|-------|
| EARNINGS_CALENDAR | [Earnings Calendar](https://www.alphavantage.co/documentation/#earnings-calendar) | `function=EARNINGS_CALENDAR`, `horizon=3month`, `response_format=csv` | `docs/samples/alpha_vantage/fundamentals/earnings_calendar.json` | `raw:alpha_vantage:fundamentals:earnings_calendar` | Overwrite | CSV response converted to JSON list (`earningsCalendar`). |
| EARNINGS_ESTIMATES | [Earnings Estimates](https://www.alphavantage.co/documentation/#earnings-estimates) | `function=EARNINGS_ESTIMATES`, `symbol` | `docs/samples/alpha_vantage/fundamentals/earnings_estimates_NVDA.json` | `raw:alpha_vantage:fundamentals:earnings_estimates:{symbol}` | Overwrite | Equity symbols only (exclude SPY/QQQ/IWM). Persist `estimates` array. |
| INCOME_STATEMENT | [Income Statement](https://www.alphavantage.co/documentation/#income-statement) | `function=INCOME_STATEMENT`, `symbol` | `docs/samples/alpha_vantage/fundamentals/income_statement_NVDA.json` | `raw:alpha_vantage:fundamentals:income_statement:{symbol}` | Overwrite | Equity symbols only. Keep both `annualReports` and `quarterlyReports`. |
| BALANCE_SHEET | [Balance Sheet](https://www.alphavantage.co/documentation/#balance-sheet) | `function=BALANCE_SHEET`, `symbol` | `docs/samples/alpha_vantage/fundamentals/balance_sheet_NVDA.json` | `raw:alpha_vantage:fundamentals:balance_sheet:{symbol}` | Overwrite | Equity symbols only. Same storage pattern as income statement. |
| CASH_FLOW | [Cash Flow](https://www.alphavantage.co/documentation/#cash-flow) | `function=CASH_FLOW`, `symbol` | `docs/samples/alpha_vantage/fundamentals/cash_flow_NVDA.json` | `raw:alpha_vantage:fundamentals:cash_flow:{symbol}` | Overwrite | Equity symbols only. Persist both annual and quarterly arrays. |
| SHARES_OUTSTANDING | [Shares Outstanding](https://www.alphavantage.co/documentation/#shares-outstanding) | `function=SHARES_OUTSTANDING`, `symbol` | `docs/samples/alpha_vantage/fundamentals/shares_outstanding_NVDA.json` | `raw:alpha_vantage:fundamentals:shares_outstanding:{symbol}` | Overwrite | Equity symbols only. Payload includes `status` and `data` arrays (annual, quarterly). |
| EARNINGS_CALL_TRANSCRIPT | [Earnings Call Transcript](https://www.alphavantage.co/documentation/#transcript) | `function=EARNINGS_CALL_TRANSCRIPT`, `symbol`, `quarter=<YYYYQ#>` | `docs/samples/alpha_vantage/fundamentals/earnings_call_transcript_NVDA_2024Q3.json` | `raw:alpha_vantage:fundamentals:earnings_call_transcript:{symbol}:{quarter}` | Overwrite | Equity symbols only. Large text transcripts; consider compression or trimmed storage if size becomes an issue. |

### Recommended Cadence & TTL
| Endpoint | Suggested cadence | TTL target | Rationale |
|----------|-------------------|-----------|-----------|
| REALTIME_OPTIONS | 10s per symbol (sequential loop over 17 symbols) | 60s | TTL ≈ 6× cadence leaves headroom for retries while analytics read fresh Greeks. |
| IBKR Quotes | Streaming (expect update ≤3s) | 9s | Provides 3× buffer for high-frequency analytics; refreshes extend TTL automatically. |
| IBKR Level-2 Depth | Rotation window 5s per group (max 3 concurrent) | 10s | TTL exceeds rotation window so liquidity metrics see fresh book. |
| IBKR Account Summary | 15s | 60s | Ensures exposure/risk calcs have margin over polling cadence. |
| IBKR Account PnL | 15s | 60s | Matches account summary buffer; supports dealer edge reconciliation. |
| IBKR Position PnL | 15s | 60s | Separate per-symbol PnL snapshots share the same buffer. |
| IBKR Positions | 15s | 60s | Allows two missed polls before analytics halt exposure calc. |
| IBKR Executions Stream | Streaming (append) | n/a (stream) | Redis Stream retains rolling history (maxlen configurable) for VPIN & attribution. |
| TIME_SERIES_INTRADAY (fallback) | 30s per symbol | 180s | Provides ~6 refresh cycles before expiry when IBKR unavailable. |
| VWAP | 60s per symbol | 300s | Indicator updates every minute; 5-minute TTL keeps history available for calculations. |
| MACD | 60s per symbol | 300s | Matches VWAP cadence/TTL to synchronize technical metrics. |
| BBANDS | 60s per symbol | 300s | Same cadence as other technical indicators to simplify scheduling. |
| TOP_GAINERS_LOSERS | 120s global | 600s | Market movers shift slowly; 5-minute TTL keeps snapshot alive for dashboards. |
| NEWS_SENTIMENT | 600s per equity symbol | 1800s | News feed throttled at 10-minute cadence; 30-minute TTL allows multiple downstream consumers to process updates. |
| REAL_GDP / CPI / INFLATION / TREASURY_YIELD / FEDERAL_FUNDS_RATE | 6h | 24h | Macro data updates infrequently; daily TTL suffices while keeping cache warm. |
| EARNINGS_CALENDAR | 24h (fetch pre-market) | 48h | Daily refresh captures new listings; extra day TTL covers outages. |
| EARNINGS_ESTIMATES | Weekly (Monday 06:00 ET) | 14d | Weekly cadence with two-week TTL ensures data persists between runs. |
| INCOME_STATEMENT / BALANCE_SHEET / CASH_FLOW | Weekly (Monday 06:00 ET) | 14d | Fundamentals shift quarterly; weekly check with two-week TTL balances freshness vs. churn. |
| SHARES_OUTSTANDING | Weekly (Monday 06:00 ET) | 14d | Weekly refresh catches corporate actions; TTL keeps prior value for audits. |
| EARNINGS_CALL_TRANSCRIPT | On demand | 90d | Transcripts requested ad-hoc; retain three months for review without hitting API repeatedly. |
| IBKR Bars (1min) | 30s (keepUpToDate) | 900s | Primary intraday series; TTL ensures ≥15 minutes of history for analytics retry windows. |
| IBKR Tick Stream | Streaming (subscription) | 60s | Prune old ticks while keeping recent flow for VPIN and realized vol calculations. |

### Open Items
- Validate the proposed cadences/TTLs during scheduler implementation and adjust for observed rate-limit behaviour.
- Monitor Redis memory usage with full intraday payload retention; introduce pruning if required.
- Revisit fundamentals persistence if/when long-term analytics need Postgres history. 

## Interactive Brokers (IBKR)

### Connection Prerequisites
- TWS/Gateway host: `127.0.0.1`, default ports `7497` (paper) / `7496` (live).
- Reserve client ID range `101-120` for automation; keep `1` free for manual session.
- Enable API access inside TWS (`Configure → API → Settings`) with trusted IPs if required.
- `ib_insync` entry point: instantiate `IB()` and call `await ib.connect(host, port, clientId)` using
  asyncio event loop shared with orchestrator.

### Feed Reference
| Feed | ib-insync call | Primary objects | Redis contract |
|------|----------------|-----------------|----------------|
| Account summary | `IB.accountSummary(account='All', tags='All')` | `AccountValue` | `raw:ibkr:account:summary` (overwrite) |
| Account positions | `IB.positions()` | `Position` (`Contract`, qty, avgCost) | `raw:ibkr:account:positions` (overwrite) |
| Account PnL | `IB.reqPnL(account, modelCode)` | `PnL` | `raw:ibkr:account:pnl` (overwrite) |
| Position PnL | `IB.reqPnLSingle(account, modelCode, conId)` | `PnLSingle` | `raw:ibkr:position:pnl:{symbol}` (overwrite) |
| Executions & commissions | `IB.reqExecutions()`, execution callbacks | `Execution`, `CommissionReport` | `stream:ibkr:executions` (append) + `raw:ibkr:execution:last` |
| Market depth (Level 2) | `IB.reqMktDepth(contract, numRows)` | `MarketDepthData` | `raw:ibkr:l2:{symbol}` (overwrite) |
| Top-of-book quotes | `IB.reqMktData(contract, snapshot=True)` or streaming `Ticker` | `Ticker` (`bid`, `ask`, greeks, volume) | `raw:ibkr:quotes:{symbol}` (overwrite) |
| Intraday bars (primary) | `IB.reqHistoricalData(contract, endDateTime='', durationStr, '1 min', whatToShow='TRADES', useRTH)` | `BarData` (`open`, `high`, `low`, `close`, `volume`) | `raw:ibkr:bars:{symbol}:1min` (overwrite rolling window) |
| Tick stream | `IB.reqTickByTickData(contract, 'Trade')` or `IB.reqMktData` tick snapshots | `TickData`, `TickByTickAllLast` | `raw:ibkr:ticks:{symbol}` (append with pruning) |
| Historical data (optional) | `IB.reqHistoricalData()` | `BarData` | `raw:ibkr:historical:{symbol}:{range}` (append/overwrite per job) |

### Payload Details (from ib-insync docs)

#### Account Summary (`AccountValue`)
- Fields: `tag`, `value`, `currency`, `account`.
- Common tags to persist: `TotalCashValue`, `NetLiquidation`, `BuyingPower`, `UnrealizedPnL`,
  `RealizedPnL`, `EquityWithLoanValue`, `InitMarginReq`, `MaintMarginReq`, `GrossPositionValue`.
- Collect raw list for transparency; store as array of objects and optionally pivot into
  `<tag>:<value>` map when deriving analytics.

#### Positions (`Position`)
- Fields: `account`, `contract` (contains `conId`, `symbol`, `secType`, `exchange`, `currency`,
  option strikes/expiry for OPT), `position` (float), `avgCost` (USD), `marketPrice`, `marketValue`,
  `unrealizedPNL`, `realizedPNL`.
- Use `IB.qualifyContracts()` to guarantee fully specified contracts before persisting.
- Store one entry per contract; include `contract.localSymbol` and `contract.primaryExchange` for
  downstream disambiguation.

#### Account PnL (`PnL`)
- Subscription fields: `dailyPnL`, `unrealizedPnL`, `realizedPnL`, `value` (net liquidation),
  `account`, `modelCode`.
- Update frequency ~1s when market data active. Persist latest snapshot with metadata including
  IBKR `reqId` for diagnostics.

#### Position PnL (`PnLSingle`)
- Fields: `dailyPnL`, `unrealizedPnL`, `realizedPnL`, `value`, `account`, `modelCode`, `contractId`.
- Map `contractId` back to symbol/expiry via cached contract lookup before writing to Redis.
- Consider namespacing Redis keys by `conId` for uniqueness, with symbol alias in payload.

#### Executions
- `Execution` fields: `execId`, `orderId`, `clientId`, `permId`, `time`, `acctNumber`, `exchange`,
  `side`, `shares`, `price`, `avgPrice`, `cumQty`, `evRule`, `evMultiplier`, `orderRef`.
- `CommissionReport` fields: `commission`, `currency`, `yield_`, `yieldRedemptionDate`.
- Persist combined record with associated `Contract` (localSymbol, secType, strike, right,
  multiplier) and the original signal/trade reference if available.
- Append to Redis Stream (`stream:ibkr:executions`, maxlen configurable) and update
  `raw:ibkr:execution:last` snapshot for quick lookup.

#### Market Depth (`MarketDepthData` / `MktDepthRow`)
- Update payload includes: `position` (level index), `marketMaker`, `operation` (0 insert, 1 update,
  2 delete), `side` (0 bid, 1 ask), `price`, `size`.
- Request depth via `reqMktDepth(contract, numRows=10, isSmartDepth=False)`. Handle pacing rules:
  max 3 concurrent L2 subscriptions without depth licenses; orchestrator must rotate symbols in
  5-second windows and specify the correct exchange per symbol (no SMART default). Throttle
  subscribe/unsubscribe cycles (`cancelMktDepth`) with ≥2s spacing.
- Redis payload should bundle the full book snapshot (top 10 levels per side) with timestamp and
  sequence number for replay.

#### Quotes (`Ticker`)
- Snapshot fields of interest: `bid`, `bidSize`, `ask`, `askSize`, `last`, `lastSize`, `close`,
  `volume`, `high`, `low`, `open`, `timestamp`, `halted`, `marketPrice`, `modelGreeks`
  (`delta`, `gamma`, `vega`, `theta`, `impliedVol`, `pvDividend`).
- For streaming quotes (non-snapshot) subscribe once per symbol; reuse same ticker object in memory
  and persist to Redis on each update with TTL slightly above expected cadence (to be confirmed).

#### Tick Stream (`TickData` / `TickByTickAllLast`)
- Requested via `IB.reqTickByTickData(contract, 'AllLast')` (preferred) or `IB.reqMktData` with
  tick-by-tick option enabled.
- Fields include `time`, `price`, `size`, `attribs`, and optionally `pastLimit`, `unreported`.
- For aggressor side, compare with quotes (tick rule) or read `attribs.lastLiquidity` when provided.
- Redis storage `raw:ibkr:ticks:{symbol}` should append entries with capped list/stream (e.g., store
  last 500 ticks) and include metadata `classification` (buy/sell/unknown).
- Used for VPIN buckets, high-frequency realized volatility, and execution diagnostics.
- Ensure scheduler throttles tick subscriptions to avoid exceeding IBKR market data limits.

#### Intraday Bars (`BarData` 1 Minute)
- Primary intraday source for analytics.
- Request via `IB.reqHistoricalData(contract, endDateTime='', durationStr='1 D', barSizeSetting='1 min', whatToShow='TRADES', useRTH=False, keepUpToDate=True)`.
- Payload fields: `date`, `open`, `high`, `low`, `close`, `volume`, `barCount`, `average`.
- Redis storage: `raw:ibkr:bars:{symbol}:1min` retaining rolling window (target ≥600 bars) with TTL 900s.
- Scheduler should refresh every 30s and maintain keep-alive subscription for continuous updates.
- Tag payload with metadata (`source`, `requested_at`, `durationStr`, `keepUpToDate=true`).
- Alpha Vantage intraday feed remains a fallback; note source in analytics bundle when fallback used.

#### Historical Bars (if enabled)
- `reqHistoricalData(contract, endDateTime, durationStr, barSizeSetting, whatToShow, useRTH)` yields
  `BarDataList` containing `BarData` elements (`date`, `open`, `high`, `low`, `close`, `volume`,
  `barCount`, `average`). Decide whether to store as append-only series or latest window snapshot.

### Operational Notes
- Heartbeat keys: `state:ibkr:quotes`, `state:ibkr:l2`, `state:ibkr:account`,
  `state:ibkr:executions`, etc., set to last success timestamp with status flag (`ok`, `error`).
- Reconnect policy: exponential backoff `[1, 5, 15, 30, 60]` seconds as per ib-insync reconnection
  guidance; log pacing violations (error code 100) and slow rotation when triggered.
- Utilize ib-insync utilities for contract helpers (`Stock`, `Option`, `Future`, `Index`), order
  factories (`MarketOrder`, `LimitOrder`, `BracketOrder`), and option calculations (`IB.calcOptionPrice`,
  `IB.calcOptionImpliedVolatility`) when building analytics or execution flows.

## Additional Feeds (Placeholder)
Add new sections following the same template when other vendors are introduced (e.g., Alpha Vantage
macro batches, futures data, social sentiment).

## Postgres Contracts
Until tables are implemented, use this area to plan schema names, column types, and relationships
for each feed archived from Redis.

| Table | Source | Purpose | Primary Keys | Notes |
|-------|--------|---------|--------------|-------|
| `analytics.metric_snapshots` | derived analytics | Historical storage | `(symbol, generated_at)` | To design |
| `trading.trades` | execution module | Trade lifecycle | `trade_id` | To design |

Populate with concrete definitions once migrations are drafted.
