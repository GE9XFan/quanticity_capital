# Interactive Brokers (IB) Ingestion Plan

We will start IB integration only after the Unusual Whales REST + WebSocket feeds are solid. This document describes the feeds we care about, where their data will live, and what needs to be in place before coding begins.

## 1. Feeds

| Feed | Source | Cadence | Primary Use |
|------|--------|---------|-------------|
| Level 1 top-of-book quotes | TWS API (reqMktData) | Streaming | price snapshots, analytics, signal confirmation |
| Level 2 depth (DOM) | TWS API (reqMktDepth) | Streaming | future market microstructure analytics |
| 5-second bars | TWS API (reqRealTimeBars) | 5s cadence | complement UW price feed, backup for OHLC generation |
| Account + portfolio | TWS API (reqAccountUpdates / reqPositions) | On change + periodic | risk checks, execution sizing |

## 2. Storage Targets

| Data | Redis | Postgres | Notes |
|------|-------|----------|-------|
| L1 quotes | `ib:l1:<symbol>` hash (latest bid/ask/last) + stream `ib:l1:<symbol>:stream` (short window) | Optional later | same pattern as UW price snapshots |
| L2 depth | `ib:l2:<symbol>` hash for latest aggregated view | Optional (JSON per update) | start simple; detailed history can wait |
| Real-time bars | append to `ib:bars:<symbol>` Redis stream (`maxlen` ~ 300) | Postgres table `ib_real_time_bars` | reuse UW history approach |
| Account/portfolio | `ib:account` hash + `ib:positions:<symbol>` hash | Postgres `ib_positions` snapshot once per run | Enables risk engine to query quickly |

## 3. Runtime Outline

1. Reuse settings model: IB host/port/client ID already present in `.env.example`.
2. Launch a dedicated asyncio loop (similar to WebSocket service) that hosts the IB API client.
3. For each subscription: update Redis hash for latest state and push to stream if we want short-term history.
4. Postgres writes mirror the UW history pattern: append rows for bars and periodic account snapshots.

## 4. Dependencies & Setup

- Ensure TWS/IB Gateway is running with API access enabled.
- Verify network connectivity from this machine to the TWS host/port.
- Store credentials (client ID, host, port) in `.env`.
- Consider a simple watchdog that restarts the IB connection if it drops.

## 5. Validation Checklist (when we implement)

- Redis: `redis-cli HGETALL ib:l1:SPY`, `redis-cli XREVRANGE ib:bars:SPY + - COUNT 5`.
- Postgres: `SELECT * FROM ib_real_time_bars ORDER BY fetched_at DESC LIMIT 5;`.
- Account: spot-check position values against TWS dashboard.

This plan mirrors the patterns already proven with Unusual Whales—once UW streams are live on Monday, we can follow this guide to add IB support without surprises.
