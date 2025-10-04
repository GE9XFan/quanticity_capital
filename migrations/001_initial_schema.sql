-- Migration: 001_initial_schema.sql
-- Description: Initial database schema for IB account and portfolio data
-- Created: 2025-10-03
-- IB API Version: 10.37.2
--
-- IMPORTANT: All field names verified against Interactive Brokers API documentation
-- See docs/3.1 Data Storage Strategy.md for complete field mapping reference
--
-- Data Retention: 2-year rolling window (except pnl_daily which is 3 years)

-- ============================================================================
-- CONTRACTS TABLE
-- Stores contract details from IB API Contract object
-- ============================================================================

CREATE TABLE IF NOT EXISTS contracts (
    -- Primary Key: IB Contract ID
    con_id INTEGER PRIMARY KEY,  -- Maps from: contract.conId

    -- Basic Contract Information
    symbol VARCHAR(50) NOT NULL,                -- Maps from: contract.symbol
    sec_type VARCHAR(20) NOT NULL,              -- Maps from: contract.secType (STK, OPT, FUT, etc.)
    exchange VARCHAR(50) NOT NULL,              -- Maps from: contract.exchange
    primary_exchange VARCHAR(50),               -- Maps from: contract.primaryExchange
    currency VARCHAR(10) NOT NULL,              -- Maps from: contract.currency

    -- Derivative-Specific Fields
    last_trade_date VARCHAR(20),                -- Maps from: contract.lastTradeDateOrContractMonth
    strike DECIMAL(24,4),                       -- Maps from: contract.strike (for options)
    "right" VARCHAR(1),                         -- Maps from: contract.right (P or C for options) - quoted because RIGHT is reserved keyword
    trading_class VARCHAR(50),                  -- Maps from: contract.tradingClass
    multiplier VARCHAR(20),                     -- Maps from: contract.multiplier

    -- Additional Contract Details
    local_symbol VARCHAR(50),                   -- Maps from: contract.localSymbol
    combo_legs_descrip TEXT,                    -- Maps from: contract.comboLegsDescrip

    -- Metadata
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Indexes for common queries
    CONSTRAINT contracts_symbol_sectype_exchange_key UNIQUE (symbol, sec_type, exchange, currency)
);

CREATE INDEX idx_contracts_symbol ON contracts(symbol);
CREATE INDEX idx_contracts_sec_type ON contracts(sec_type);
CREATE INDEX idx_contracts_exchange ON contracts(exchange);

COMMENT ON TABLE contracts IS 'Contract details from IB API - normalized reference table';
COMMENT ON COLUMN contracts.con_id IS 'IB Contract ID - Primary identifier from contract.conId';
COMMENT ON COLUMN contracts.sec_type IS 'Security type: STK, OPT, FUT, CASH, BOND, CFD, etc.';
COMMENT ON COLUMN contracts.right IS 'Option right: P (Put) or C (Call)';

-- ============================================================================
-- ACCOUNT SUMMARY TABLE
-- Stores account summary data from reqAccountSummary
-- IB Callback: accountSummary(reqId, account, tag, value, currency)
-- Update Frequency: Every 3 minutes (IB limitation)
-- ============================================================================

CREATE TABLE IF NOT EXISTS account_summary (
    id BIGSERIAL PRIMARY KEY,

    -- IB API Fields (exact mapping)
    account VARCHAR(50) NOT NULL,               -- Maps from: account (accountSummary callback)
    tag VARCHAR(100) NOT NULL,                  -- Maps from: tag (e.g., "NetLiquidation", "BuyingPower")
    value DECIMAL(24,4),                        -- Maps from: value (converted from string)
    currency VARCHAR(10),                       -- Maps from: currency

    -- Timestamp
    timestamp TIMESTAMPTZ NOT NULL,             -- When this value was captured

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes optimized for common queries
CREATE INDEX idx_account_summary_account_time ON account_summary(account, timestamp DESC);
CREATE INDEX idx_account_summary_tag ON account_summary(tag);
CREATE INDEX idx_account_summary_account_tag_time ON account_summary(account, tag, timestamp DESC);

COMMENT ON TABLE account_summary IS 'Account summary data from reqAccountSummary - updates every 3 minutes';
COMMENT ON COLUMN account_summary.tag IS 'Summary tag name from AccountSummaryTags (NetLiquidation, BuyingPower, etc.)';
COMMENT ON COLUMN account_summary.value IS 'Numeric value - stored as DECIMAL(24,4) for precision';

-- ============================================================================
-- ACCOUNT VALUES TABLE
-- Stores account values from reqAccountUpdates → updateAccountValue callback
-- IB Callback: updateAccountValue(key, val, currency, accountName)
-- Update Frequency: Every 3 minutes or on position change
-- ============================================================================

CREATE TABLE IF NOT EXISTS account_values (
    id BIGSERIAL PRIMARY KEY,

    -- IB API Fields (exact mapping)
    account VARCHAR(50) NOT NULL,               -- Maps from: accountName (updateAccountValue callback)
    key VARCHAR(100) NOT NULL,                  -- Maps from: key (e.g., "NetLiquidation", "BuyingPower")
    value VARCHAR(255),                         -- Maps from: val (kept as string - can be numeric or text)
    currency VARCHAR(10),                       -- Maps from: currency

    -- Timestamp
    timestamp TIMESTAMPTZ NOT NULL,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for efficient queries
CREATE INDEX idx_account_values_account_key_time ON account_values(account, key, timestamp DESC);
CREATE INDEX idx_account_values_time ON account_values(timestamp DESC);

COMMENT ON TABLE account_values IS 'Account values from reqAccountUpdates - more detailed than summary';
COMMENT ON COLUMN account_values.key IS 'Account value key - see Account Value Keys documentation';
COMMENT ON COLUMN account_values.value IS 'Stored as VARCHAR - can be numeric, boolean, or text';

-- ============================================================================
-- POSITIONS TABLE
-- Stores position data from multiple sources:
-- 1. reqAccountUpdates → updatePortfolio callback
-- 2. reqPositions → position callback
-- IB Callbacks:
--   updatePortfolio(contract, position, marketPrice, marketValue, averageCost,
--                   unrealizedPNL, realizedPNL, accountName)
--   position(account, contract, position, avgCost)
-- ============================================================================

CREATE TABLE IF NOT EXISTS positions (
    id BIGSERIAL PRIMARY KEY,

    -- Account & Contract
    account VARCHAR(50) NOT NULL,               -- Maps from: accountName (updatePortfolio) or account (position)
    contract_id INTEGER NOT NULL,               -- Maps from: contract.conId

    -- Position Details
    position DECIMAL(28,8) NOT NULL,            -- Maps from: position (Decimal) - supports fractional shares
    avg_cost DECIMAL(24,4),                     -- Maps from: averageCost (updatePortfolio) or avgCost (position)

    -- Market Data (from updatePortfolio only)
    market_price DECIMAL(24,4),                 -- Maps from: marketPrice
    market_value DECIMAL(24,4),                 -- Maps from: marketValue

    -- PnL (from updatePortfolio only)
    unrealized_pnl DECIMAL(24,4),               -- Maps from: unrealizedPNL
    realized_pnl DECIMAL(24,4),                 -- Maps from: realizedPNL

    -- Denormalized contract info for quick access (duplicated from contracts table)
    symbol VARCHAR(50),                         -- Maps from: contract.symbol
    sec_type VARCHAR(20),                       -- Maps from: contract.secType
    exchange VARCHAR(50),                       -- Maps from: contract.exchange

    -- Timestamp
    timestamp TIMESTAMPTZ NOT NULL,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Foreign Key
    CONSTRAINT fk_positions_contract FOREIGN KEY (contract_id) REFERENCES contracts(con_id)
);

-- Indexes for common query patterns
CREATE INDEX idx_positions_account_contract_time ON positions(account, contract_id, timestamp DESC);
CREATE INDEX idx_positions_time ON positions(timestamp DESC);
CREATE INDEX idx_positions_contract ON positions(contract_id);
CREATE INDEX idx_positions_symbol ON positions(symbol);

COMMENT ON TABLE positions IS 'Position snapshots from updatePortfolio and position callbacks';
COMMENT ON COLUMN positions.position IS 'DECIMAL(28,8) to support fractional shares';
COMMENT ON COLUMN positions.avg_cost IS 'Average cost per share/contract - maps from averageCost or avgCost';
COMMENT ON COLUMN positions.unrealized_pnl IS 'Daily unrealized P&L - only from updatePortfolio';
COMMENT ON COLUMN positions.realized_pnl IS 'Daily realized P&L - only from updatePortfolio';

-- ============================================================================
-- PNL DAILY TABLE
-- Stores daily account-level P&L from reqPnL
-- IB Callback: pnl(reqId, dailyPnL, unrealizedPnL, realizedPnL)
-- Update Frequency: ~1 second (real-time)
-- Storage Strategy: Snapshot every 5 minutes + EOD summary
-- ============================================================================

CREATE TABLE IF NOT EXISTS pnl_daily (
    id BIGSERIAL PRIMARY KEY,

    -- Account & Date
    account VARCHAR(50) NOT NULL,               -- Single account (not from IB - derived from config)
    date DATE NOT NULL,                         -- Trading day

    -- PnL Values
    daily_pnl DECIMAL(24,4),                    -- Maps from: dailyPnL
    unrealized_pnl DECIMAL(24,4),               -- Maps from: unrealizedPnL (total since inception)
    realized_pnl DECIMAL(24,4),                 -- Maps from: realizedPnL (total since inception)

    -- Timestamp (for intraday snapshots)
    timestamp TIMESTAMPTZ NOT NULL,

    -- Metadata
    is_eod_snapshot BOOLEAN DEFAULT FALSE,      -- True for end-of-day final values
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_pnl_daily_account_date ON pnl_daily(account, date DESC);
CREATE INDEX idx_pnl_daily_time ON pnl_daily(timestamp DESC);
-- Ensure one EOD snapshot per day using partial unique index
CREATE UNIQUE INDEX idx_pnl_daily_unique_eod ON pnl_daily(account, date) WHERE is_eod_snapshot = TRUE;

COMMENT ON TABLE pnl_daily IS 'Account-level daily P&L from reqPnL - real-time updates';
COMMENT ON COLUMN pnl_daily.daily_pnl IS 'Daily P&L - resets based on TWS settings';
COMMENT ON COLUMN pnl_daily.unrealized_pnl IS 'Total unrealized P&L since inception';
COMMENT ON COLUMN pnl_daily.realized_pnl IS 'Total realized P&L since inception';
COMMENT ON COLUMN pnl_daily.is_eod_snapshot IS 'True for end-of-day summary records';

-- ============================================================================
-- PNL POSITIONS TABLE
-- Stores position-level P&L from reqPnLSingle
-- IB Callback: pnlSingle(reqId, pos, dailyPnL, unrealizedPnL, realizedPnL, value)
-- Update Frequency: ~1 second (real-time)
-- Storage Strategy: Snapshot every 5 minutes
-- ============================================================================

CREATE TABLE IF NOT EXISTS pnl_positions (
    id BIGSERIAL PRIMARY KEY,

    -- Account & Contract
    account VARCHAR(50) NOT NULL,               -- Single account (not from IB - derived)
    contract_id INTEGER NOT NULL,               -- From reqPnLSingle request parameter

    -- Position & PnL
    position DECIMAL(28,8),                     -- Maps from: pos (NOT position!)
    daily_pnl DECIMAL(24,4),                    -- Maps from: dailyPnL
    unrealized_pnl DECIMAL(24,4),               -- Maps from: unrealizedPnL (since inception)
    realized_pnl DECIMAL(24,4),                 -- Maps from: realizedPnL (since inception)
    value DECIMAL(24,4),                        -- Maps from: value (current market value)

    -- Timestamp
    timestamp TIMESTAMPTZ NOT NULL,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Foreign Key
    CONSTRAINT fk_pnl_positions_contract FOREIGN KEY (contract_id) REFERENCES contracts(con_id)
);

-- Indexes
CREATE INDEX idx_pnl_positions_account_contract_time ON pnl_positions(account, contract_id, timestamp DESC);
CREATE INDEX idx_pnl_positions_time ON pnl_positions(timestamp DESC);
CREATE INDEX idx_pnl_positions_contract ON pnl_positions(contract_id);

COMMENT ON TABLE pnl_positions IS 'Position-level P&L from reqPnLSingle - real-time updates';
COMMENT ON COLUMN pnl_positions.position IS 'Current position size - maps from pos (not position!)';
COMMENT ON COLUMN pnl_positions.daily_pnl IS 'Daily P&L for this position';
COMMENT ON COLUMN pnl_positions.value IS 'Current market value of position';

-- ============================================================================
-- DATA RETENTION FUNCTION
-- Automatically removes data older than 2 years (3 years for pnl_daily)
-- ============================================================================

CREATE OR REPLACE FUNCTION cleanup_old_data()
RETURNS void AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Clean up account_summary (2 years)
    DELETE FROM account_summary WHERE timestamp < NOW() - INTERVAL '2 years';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE 'Deleted % rows from account_summary', deleted_count;

    -- Clean up account_values (2 years)
    DELETE FROM account_values WHERE timestamp < NOW() - INTERVAL '2 years';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE 'Deleted % rows from account_values', deleted_count;

    -- Clean up positions (2 years)
    DELETE FROM positions WHERE timestamp < NOW() - INTERVAL '2 years';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE 'Deleted % rows from positions', deleted_count;

    -- Clean up pnl_positions (2 years)
    DELETE FROM pnl_positions WHERE timestamp < NOW() - INTERVAL '2 years';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE 'Deleted % rows from pnl_positions', deleted_count;

    -- Clean up pnl_daily (3 years - keep longer for annual reports)
    DELETE FROM pnl_daily WHERE date < NOW() - INTERVAL '3 years';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE 'Deleted % rows from pnl_daily', deleted_count;

    -- Clean up unused contracts (contracts not referenced in positions for 2 years)
    DELETE FROM contracts
    WHERE con_id NOT IN (
        SELECT DISTINCT contract_id FROM positions
        WHERE timestamp >= NOW() - INTERVAL '2 years'
    )
    AND last_updated < NOW() - INTERVAL '2 years';
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RAISE NOTICE 'Deleted % rows from contracts', deleted_count;

END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_data IS 'Removes data older than retention period - run daily at 00:00 UTC';

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to update contract last_updated timestamp
CREATE OR REPLACE FUNCTION update_contract_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_updated = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update contract timestamp
CREATE TRIGGER trigger_update_contract_timestamp
BEFORE UPDATE ON contracts
FOR EACH ROW
EXECUTE FUNCTION update_contract_timestamp();

-- ============================================================================
-- VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Latest account summary view (most recent value for each tag)
CREATE OR REPLACE VIEW v_latest_account_summary AS
SELECT DISTINCT ON (account, tag)
    account,
    tag,
    value,
    currency,
    timestamp
FROM account_summary
ORDER BY account, tag, timestamp DESC;

COMMENT ON VIEW v_latest_account_summary IS 'Most recent account summary value for each tag';

-- Current positions view (most recent position for each contract)
CREATE OR REPLACE VIEW v_current_positions AS
SELECT DISTINCT ON (account, contract_id)
    p.account,
    p.contract_id,
    c.symbol,
    c.sec_type,
    c.exchange,
    c.currency,
    p.position,
    p.avg_cost,
    p.market_price,
    p.market_value,
    p.unrealized_pnl,
    p.realized_pnl,
    p.timestamp
FROM positions p
JOIN contracts c ON p.contract_id = c.con_id
WHERE p.position != 0  -- Only show non-zero positions
ORDER BY account, contract_id, timestamp DESC;

COMMENT ON VIEW v_current_positions IS 'Most recent non-zero positions';

-- Latest EOD PnL
CREATE OR REPLACE VIEW v_latest_eod_pnl AS
SELECT
    account,
    date,
    daily_pnl,
    unrealized_pnl,
    realized_pnl,
    timestamp
FROM pnl_daily
WHERE is_eod_snapshot = TRUE
ORDER BY date DESC;

COMMENT ON VIEW v_latest_eod_pnl IS 'End-of-day P&L snapshots';

-- ============================================================================
-- SAMPLE QUERIES FOR DOCUMENTATION
-- ============================================================================

-- Get current account summary
-- SELECT * FROM v_latest_account_summary WHERE account = 'U123456';

-- Get current positions
-- SELECT * FROM v_current_positions WHERE account = 'U123456';

-- Get daily PnL history for last 30 days
-- SELECT * FROM pnl_daily
-- WHERE account = 'U123456'
-- AND is_eod_snapshot = TRUE
-- AND date >= CURRENT_DATE - INTERVAL '30 days'
-- ORDER BY date DESC;

-- Get position history for specific contract
-- SELECT * FROM positions
-- WHERE contract_id = 8314
-- AND timestamp >= NOW() - INTERVAL '7 days'
-- ORDER BY timestamp DESC;

-- ============================================================================
-- GRANT PERMISSIONS (Adjust based on your security model)
-- ============================================================================

-- Grant to application user (replace 'app_user' with your actual username)
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_user;
-- GRANT EXECUTE ON FUNCTION cleanup_old_data() TO app_user;

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================

-- Verify tables were created
DO $$
BEGIN
    RAISE NOTICE 'Migration 001_initial_schema.sql completed successfully';
    RAISE NOTICE 'Tables created:';
    RAISE NOTICE '  - contracts';
    RAISE NOTICE '  - account_summary';
    RAISE NOTICE '  - account_values';
    RAISE NOTICE '  - positions';
    RAISE NOTICE '  - pnl_daily';
    RAISE NOTICE '  - pnl_positions';
    RAISE NOTICE 'Views created:';
    RAISE NOTICE '  - v_latest_account_summary';
    RAISE NOTICE '  - v_current_positions';
    RAISE NOTICE '  - v_latest_eod_pnl';
END $$;
