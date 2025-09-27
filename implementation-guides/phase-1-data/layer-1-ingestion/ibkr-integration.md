# IBKR Integration

## Purpose
Implement and maintain the Interactive Brokers real-time data ingestion stack (quotes, tick-by-tick, depth, historical backfill) per Layer 1 architecture requirements.

## Prerequisites
- IBKR TWS or Gateway running with market data entitlements for target symbols.
- `ib_async` library installed with Python 3.11 compatibility.
- Network connectivity to TWS/Gateway host/port (default 127.0.0.1:7497 for TWS, 127.0.0.1:4001 for Gateway).
- Redis or Kafka infrastructure for publishing normalized events.

## Connection Strategy
1. Implement `IBKRClient` wrapper using `IB.connectAsync` with automatic reconnection and heartbeat supervision.
2. Persist client IDs in Redis to avoid collisions across subsystems.
3. Map environment configuration in `config/trading_params.yaml::ibkr` (host, port, client_ids, data_type).
4. Handle delayed vs live market data toggles via `reqMarketDataType` during startup.

## Streaming Subscriptions
| Data Type | API Call | Consumer |
|-----------|----------|----------|
| L1 Quotes | `reqMktData` | Greeks engine, hedging checks |
| Tick-by-Tick | `reqTickByTickData` | VPIN calculator, microstructure analytics |
| Depth of Market | `reqMarketDepth` | Liquidity monitor |
| Option Chains | `reqSecDefOptParams` + `reqContractDetails` | Contract validation |
| Historical Bars | `reqHistoricalData` | Gap backfill, VWAP sanity |

## DTO Normalization
- Map IBKR ticks to `UnderlyingQuote`, `OrderBookSnapshot`, and `TickEvent` DTOs.
- Ensure timestamp alignment with exchange-provided times for cross-feed reconciliation.
- Publish normalized events to `ingestion.quotes.ibkr` and contract metadata to `ingestion.refdata.ibkr`.

## Resilience & Monitoring
- Metrics: `data_ingestion.ibkr.disconnects`, `data_ingestion.ibkr.reconnects`, `data_ingestion.ibkr.latency_ms`.
- Alert when disconnect duration exceeds `disconnect_grace_seconds`.
- Mirror raw data into append-only Kafka/Redis Streams for audit purposes.

## Testing Checklist
- [ ] Run `pytest tests/layer1/test_ibkr_wrapper.py`
- [ ] Execute `python scripts/stream_ibkr.py --symbol SPY --duration 120`
- [ ] Validate contract metadata via `scripts/validate_contract.py option_chain:v1.0.0` using IBKR derived samples
- [ ] Confirm depth snapshots feed into `analytics/liquidity_monitor.py` integration test

## Troubleshooting
- Error 10167 (market data permission): verify entitlements and log to runbook.
- Pacing violations: adjust submission cadence or throttle subscription count.
- Timestamp drift: compare TWS timestamp with system clock and enable NTP sync.
