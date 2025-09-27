# Time Series & Intraday Integration

## Purpose
Document the required intraday spot and indicator polling routines that support 0DTE/1DTE hedging, analytics enrichment, and AlphaVantage rate-limit budgeting as defined in `quantum-trading-architecture.md`.

## Responsibilities
- Poll AlphaVantage `TimeSeries.get_intraday` for each configured symbol and interval (default `1min`, `5min`).
- Compute local VWAP fallback when AlphaVantage omits the field, flagging recalculated values via `quality_flags`.
- Stream technical indicators (MACD, Bollinger Bands, VWAP) using `TechIndicators` with reuse of cached intraday prices.
- Publish normalized payloads to `ingestion.marketdata.live` and `ingestion.indicators.alpha` after DTO validation.

## Scheduling & Cadence
| Stream            | Interval | Offset Strategy | Notes |
|-------------------|----------|-----------------|-------|
| Intraday 1-Min    | 60s      | Stagger by 5s per symbol bucket | Required for 0DTE hedging checks |
| Intraday 5-Min    | 300s     | Offset by +30s relative to 1-min | Feeds indicator smoothing |
| MACD              | 60s      | Align with 1-min refresh        | Cache for analytics |
| VWAP              | 60s      | Shared fetch with MACD          | Local fallback uses intraday data |
| Bollinger Bands   | 300s     | Trigger after 5-min intraday run| Keep 20-period window |

## Implementation Notes
- Use the async executor pool defined in `AlphaVantageClient` to parallelize indicator calls without exceeding rate quotas.
- Every indicator fetch must request `datatype=json` explicitly; parse floats using `decimal.Decimal` before converting to Python floats to avoid rounding drift.
- Cache keys follow the pattern documented in `CARD_005`: `indicator:{symbol}:{indicator}` and `intraday:{symbol}:{interval}`.
- Store the latest processed timestamp per symbol in Redis (`ingestion:last_processed:{symbol}`) to resume cleanly after restarts.
- When AlphaVantage returns `None` or `0` for VWAP on thin symbols, recompute using cumulative intraday volume/price and mark `quality_flags` with `VWAP_RECOMPUTED`.

## Live Validation
1. Run `python scripts/stream_alpha_indicators.py --symbol SPY --duration 600 --interval 1min --indicators macd vwap bbands`.
2. Verify output payloads against `technical_indicators:v1.0.0` using `scripts/validate_contract.py`.
3. Monitor Grafana panel `Ingestion › Indicator Freshness` to ensure data age < 90 seconds and cache hit rate > 85%.
4. Capture raw logs to `logs/alpha_vantage_indicators.log` and attach to `docs/evidence/phase1/` for audit.

## Failure Handling
- **HTTP 429:** respect rate limiter waits; prefer rescheduling the poll rather than retrying immediately.
- **Missing data:** raise `IndicatorUnavailable` exception and degrade gracefully by surfacing cached values (if within TTL) or computed fallbacks.
- **Clock skew:** sync system clock via NTP; include timestamp drift metric `data_ingestion.indicators.clock_skew_ms`.

## Dependencies
- `data_ingestion/alphavantage_client.py`
- `data_ingestion/indicator_service.py`
- Redis TimeSeries schema for storing intraday curves (`CARD_003`)

## Evidence
- Store validation artifacts in `docs/evidence/phase1/indicators/` (JSON samples, Grafana screenshots, test logs).
- Update `VALIDATION_CHECKLIST.md` Phase 1 section with links upon completion.
