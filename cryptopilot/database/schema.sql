-- CryptoPilot Database Schema
-- All monetary values stored as TEXT (DECIMAL representation) to prevent floating-point errors
-- All timestamps in UTC ISO 8601 format

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
    description TEXT NOT NULL
);

-- Market data table
CREATE TABLE IF NOT EXISTS market_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,              -- e.g., 'BTC', 'ETH'
    base_currency TEXT NOT NULL DEFAULT 'USDT',
    timestamp TEXT NOT NULL,           -- ISO 8601 UTC
    open TEXT NOT NULL,                -- DECIMAL as TEXT
    high TEXT NOT NULL,                -- DECIMAL as TEXT
    low TEXT NOT NULL,                 -- DECIMAL as TEXT
    close TEXT NOT NULL,               -- DECIMAL as TEXT
    volume TEXT NOT NULL,              -- DECIMAL as TEXT
    timeframe TEXT NOT NULL,           -- '1h', '4h', '1d', '1w'
    provider TEXT NOT NULL,            -- Data source
    collected_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
    UNIQUE(symbol, timestamp, timeframe, provider)
);

CREATE INDEX IF NOT EXISTS idx_market_data_lookup
    ON market_data(symbol, timeframe, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_market_data_symbol
    ON market_data(symbol);

-- Trades table
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id TEXT UNIQUE NOT NULL,     -- UUID
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK(side IN ('BUY', 'SELL')),
    quantity TEXT NOT NULL,            -- DECIMAL as TEXT
    price TEXT NOT NULL,               -- DECIMAL as TEXT (in USDT)
    fee TEXT NOT NULL DEFAULT '0',     -- DECIMAL as TEXT (in USDT)
    total_cost TEXT NOT NULL,          -- DECIMAL as TEXT (in USDT)
    timestamp TEXT NOT NULL,           -- ISO 8601 UTC
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol
    ON trades(symbol, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_trades_timestamp
    ON trades(timestamp DESC);

-- Balance snapshots table
CREATE TABLE IF NOT EXISTS balance_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id TEXT UNIQUE NOT NULL,  -- UUID
    symbol TEXT NOT NULL,
    quantity TEXT NOT NULL,            -- DECIMAL as TEXT
    cost_basis TEXT,                   -- DECIMAL as TEXT (in USDT, nullable for USDT itself)
    timestamp TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_balance_snapshots_symbol
    ON balance_snapshots(symbol, timestamp DESC);

-- Analysis results table
CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id TEXT UNIQUE NOT NULL,  -- UUID
    symbol TEXT NOT NULL,
    strategy TEXT NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('BUY', 'SELL', 'HOLD')),
    confidence TEXT NOT NULL CHECK(confidence IN ('HIGH', 'MEDIUM', 'LOW')),
    confidence_score TEXT NOT NULL,    -- DECIMAL as TEXT (0.0 to 1.0)
    evidence TEXT NOT NULL,            -- JSON array of supporting indicators
    risk_assessment TEXT,              -- JSON object
    timestamp TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
    market_context TEXT                -- JSON object for broader market conditions
);

CREATE INDEX IF NOT EXISTS idx_analysis_results_symbol
    ON analysis_results(symbol, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_results_strategy
    ON analysis_results(strategy, timestamp DESC);

-- Strategy performance tracking
CREATE TABLE IF NOT EXISTS strategy_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy TEXT NOT NULL,
    symbol TEXT NOT NULL,
    analysis_id TEXT NOT NULL,         -- Reference to analysis_results
    recommendation_timestamp TEXT NOT NULL,
    evaluation_timestamp TEXT,         -- When we evaluate the recommendation
    outcome TEXT CHECK(outcome IN ('WIN', 'LOSS', 'NEUTRAL', 'PENDING')),
    actual_return TEXT,                -- DECIMAL as TEXT (percentage)
    notes TEXT,
    FOREIGN KEY (analysis_id) REFERENCES analysis_results(analysis_id)
);

CREATE INDEX IF NOT EXISTS idx_strategy_performance
    ON strategy_performance(strategy, symbol);

-- Data quality tracking
CREATE TABLE IF NOT EXISTS data_quality_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_type TEXT NOT NULL,          -- 'gap_detection', 'integrity_check', etc.
    symbol TEXT,
    timeframe TEXT,
    issues_found INTEGER NOT NULL DEFAULT 0,
    details TEXT,                      -- JSON with specifics
    timestamp TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
);

-- System events log
CREATE TABLE IF NOT EXISTS system_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,          -- 'collection', 'analysis', 'error', etc.
    severity TEXT NOT NULL CHECK(severity IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    message TEXT NOT NULL,
    details TEXT,                      -- JSON with additional context
    timestamp TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
);

CREATE INDEX IF NOT EXISTS idx_system_events_timestamp
    ON system_events(timestamp DESC);

-- Insert initial schema version
INSERT OR IGNORE INTO schema_version (version, description)
VALUES (1, 'Initial schema with USDT-based decimal storage');
