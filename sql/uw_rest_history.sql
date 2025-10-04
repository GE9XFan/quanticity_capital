-- Table storing historical snapshots for high-frequency REST endpoints.

CREATE TABLE IF NOT EXISTS uw_rest_history (
    endpoint TEXT NOT NULL,
    symbol TEXT,
    fetched_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_uw_rest_history_unique
    ON uw_rest_history (endpoint, symbol, fetched_at);
