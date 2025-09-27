# Alpha Vantage Endpoint Inventory

Reference table for every Alpha Vantage feed we support. All rows below are live in Phase 2, with
sample payloads stored under `docs/samples/alpha_vantage/` for verification and regression tests.

| Endpoint | Scope / Symbols | Parameters | Sample Payload |
|----------|-----------------|------------|----------------|
| REALTIME_OPTIONS | SPY, QQQ, IWM, NVDA, AAPL, MSFT, GOOGL, META, ORCL, AMZN, TSLA, DIS, V, COST, WMT, GE, AMD | `function=REALTIME_OPTIONS`, `symbols=<list above>`, `require_greeks=true` | `docs/samples/alpha_vantage/realtime_options/TSLA.json` |
| VWAP | Same symbol list as realtime options | `function=VWAP`, `interval=1min`, `series_type=close` | `docs/samples/alpha_vantage/vwap/IBM.json` |
| MACD | Same symbol list as realtime options | `function=MACD`, `interval=1min`, `series_type=close`, `fastperiod=12`, `slowperiod=26`, `signalperiod=9` | `docs/samples/alpha_vantage/macd/USDEUR.json` |
| BBANDS | Same symbol list as realtime options | `function=BBANDS`, `interval=1min`, `time_period=20`, `series_type=close`, `nbdevup=2`, `nbdevdn=2`, `matype=0` | `docs/samples/alpha_vantage/bbands/IBM.json` |
| TIME_SERIES_INTRADAY | Same symbol list as realtime options | `function=TIME_SERIES_INTRADAY`, `interval=1min`, `outputsize=full`, `extended_hours=true` | `docs/samples/alpha_vantage/time_series_intraday/IBM.json` |
| TOP_GAINERS_LOSERS | Aggregate market feed | `function=TOP_GAINERS_LOSERS`, `market=<US\|TORONTO\|LONDON>` | `docs/samples/alpha_vantage/top_gainers_losers/US.json` |
| NEWS_SENTIMENT | Techascope equities (excludes SPY/QQQ/IWM) | `function=NEWS_SENTIMENT`, `limit=50`, `sort=LATEST`, `tickers=<symbol>` | `docs/samples/alpha_vantage/news_sentiment/sample.json` |
| REAL_GDP | Macro | `function=REAL_GDP`, `interval=<quarterly\|annual>` | `docs/samples/alpha_vantage/macro/real_gdp_quarterly.json` |
| CPI | Macro | `function=CPI`, `interval=<monthly\|semiannual>` | `docs/samples/alpha_vantage/macro/cpi_monthly.json` |
| INFLATION | Macro | `function=INFLATION` | `docs/samples/alpha_vantage/macro/inflation.json` |
| TREASURY_YIELD | Macro | `function=TREASURY_YIELD`, `interval=<daily\|weekly\|monthly>`, `maturity=<2year\|10year\|30year>` | `docs/samples/alpha_vantage/macro/treasury_yield_weekly_10year.json` |
| FEDERAL_FUNDS_RATE | Macro | `function=FEDERAL_FUNDS_RATE`, `interval=<daily\|weekly\|monthly>` | `docs/samples/alpha_vantage/macro/federal_funds_rate_weekly.json` |
| EARNINGS_CALENDAR | Fundamentals (aggregate) | `function=EARNINGS_CALENDAR`, `horizon=3month`, `response_format=csv` | `docs/samples/alpha_vantage/fundamentals/earnings_calendar.json` |
| EARNINGS_ESTIMATES | Techascope equity universe | `function=EARNINGS_ESTIMATES` | `docs/samples/alpha_vantage/fundamentals/earnings_estimates_NVDA.json` |
| INCOME_STATEMENT | Techascope equity universe | `function=INCOME_STATEMENT` | `docs/samples/alpha_vantage/fundamentals/income_statement_NVDA.json` |
| BALANCE_SHEET | Techascope equity universe | `function=BALANCE_SHEET` | `docs/samples/alpha_vantage/fundamentals/balance_sheet_NVDA.json` |
| CASH_FLOW | Techascope equity universe | `function=CASH_FLOW` | `docs/samples/alpha_vantage/fundamentals/cash_flow_NVDA.json` |
| SHARES_OUTSTANDING | Techascope equity universe | `function=SHARES_OUTSTANDING` | `docs/samples/alpha_vantage/fundamentals/shares_outstanding_NVDA.json` |
| EARNINGS_CALL_TRANSCRIPT | On-demand per symbol/quarter | `function=EARNINGS_CALL_TRANSCRIPT`, `symbol=<symbol>`, `quarter=<YYYYQ#>` | `docs/samples/alpha_vantage/fundamentals/earnings_call_transcript_NVDA_2024Q3.json` |

## Usage Notes
- Keep this table focused on request construction. Storage cadence, TTLs, and verification artifacts
  now live in `docs/data_sources.md` once defined.
- When adding a new endpoint, drop its sample payload under `docs/samples/alpha_vantage/<endpoint>/`
  and append a row here immediately.
