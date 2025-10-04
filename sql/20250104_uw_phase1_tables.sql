-- Phase 1 Week 1: foundational tables for Unusual Whales ingestion.

CREATE TABLE IF NOT EXISTS uw_flow_alerts (
    alert_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    rule_name TEXT,
    direction TEXT,
    sweep BOOLEAN,
    premium NUMERIC(18, 2),
    aggregated_premium NUMERIC(18, 2),
    trade_ids TEXT[],
    raw_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_uw_flow_alerts_ticker_timestamp
    ON uw_flow_alerts (ticker, event_timestamp DESC);

CREATE TABLE IF NOT EXISTS uw_price_ticks (
    ticker TEXT NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    last_price NUMERIC(18, 6) NOT NULL,
    bid NUMERIC(18, 6),
    ask NUMERIC(18, 6),
    raw_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ticker, event_timestamp)
);

CREATE INDEX IF NOT EXISTS idx_uw_price_ticks_ticker
    ON uw_price_ticks (ticker, event_timestamp DESC);

CREATE TABLE IF NOT EXISTS uw_option_trades (
    trade_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    option_symbol TEXT NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    price NUMERIC(18, 6),
    size BIGINT,
    premium NUMERIC(18, 2),
    side TEXT,
    exchange TEXT,
    raw_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_uw_option_trades_ticker_ts
    ON uw_option_trades (ticker, event_timestamp DESC);

CREATE TABLE IF NOT EXISTS uw_gex_snapshot (
    ticker TEXT NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    gamma_exposure NUMERIC(18, 4),
    delta_exposure NUMERIC(18, 4),
    vanna NUMERIC(18, 4),
    charm NUMERIC(18, 4),
    raw_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ticker, event_timestamp)
);

CREATE TABLE IF NOT EXISTS uw_gex_strike (
    ticker TEXT NOT NULL,
    strike NUMERIC(18, 4) NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    gamma_exposure NUMERIC(18, 4),
    open_interest NUMERIC(18, 4),
    raw_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ticker, strike, event_timestamp)
);

CREATE TABLE IF NOT EXISTS uw_gex_strike_expiry (
    ticker TEXT NOT NULL,
    expiry DATE NOT NULL,
    strike NUMERIC(18, 4) NOT NULL,
    event_timestamp TIMESTAMPTZ NOT NULL,
    gamma_exposure NUMERIC(18, 4),
    raw_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ticker, expiry, strike, event_timestamp)
);

CREATE TABLE IF NOT EXISTS uw_news (
    headline_id TEXT PRIMARY KEY,
    headline TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    source TEXT,
    tickers TEXT[],
    is_trump_ts BOOLEAN,
    raw_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS uw_rest_payloads (
    endpoint TEXT NOT NULL,
    scope TEXT,
    payload_hash TEXT NOT NULL,
    payload JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (endpoint, scope, payload_hash)
);

CREATE INDEX IF NOT EXISTS idx_uw_rest_payloads_fetched_at
    ON uw_rest_payloads (fetched_at DESC);
