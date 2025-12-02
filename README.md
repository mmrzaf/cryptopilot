# CryptoPilot

> Turn messy crypto market data into clear, explainable trading calls

**Status:** Early alpha – `0.0.5` (foundation in progress)  
**Scope right now:** Technical-only, OHLCV-based engine + portfolio tracking. Whale data, exchange flows, decision engine, and backtesting are planned but not implemented yet.

---

## What CryptoPilot is

CryptoPilot is a CLI-first platform that:

- Collects and stores crypto market data in a **local, queryable database**.
- Runs **pluggable analysis strategies** (trend-following, mean-reversion, momentum) on that data.
- Tracks your trades and positions with proper **Decimal-safe accounting**.
- Prepares the ground for a full **decision engine** that will combine:
  - Technicals
  - Whale / on-chain flows
  - Exchange flow / microstructure
  - Portfolio context and risk profile

Right now, it’s a solid **technical analysis + portfolio toolkit** with a lot of infrastructure already in place for the bigger vision.

For the long-term vision and design, see [`ROADMAP.md`](./ROADMAP.md).

---

## Features (0.0.5)

### Implemented today

**Data platform**

- Async SQLite database with schema for:
  - `market_data` (OHLCV candles)
  - `trades` and `balance_snapshots`
  - `analysis_results` and `strategy_performance`
  - `data_quality_log` and `system_events`
- All monetary values stored as `TEXT` (stringified `Decimal`) – no float money.
- Integrity checks and schema versioning.

**Provider + collection**

- Provider abstraction (`DataProviderBase`) with a registry.
- CoinGecko provider implementation.
- Market data collector:
  - Figures out collection windows per symbol/timeframe.
  - Handles retries/backoff for provider errors.
  - Bulk inserts OHLCV candles into the DB.
- Gap detection + optional gap filling for missing candles.

**Analysis engine (technical-only)**

- Indicator library:
  - SMA, EMA, RSI, Bollinger Bands, MACD, volatility, ATR, trend helpers, crossovers.
- Strategy framework:
  - Base strategy class with standardized `AnalysisResult` (action, confidence, evidence, risk/context).
  - Built-in strategies:
    - `trend_following`
    - `mean_reversion`
    - `momentum`
- Analysis engine:
  - Loads OHLCV data from DB into pandas.
  - Validates data length vs strategy requirements.
  - Runs a chosen strategy and stores results.

**Portfolio engine**

- Trade recording with validation (including “don’t sell more than you own” safeguard).
- Position construction from trade history (average cost basis).
- Unrealized P&L calculation using latest stored market prices.
- Portfolio summary:
  - Total value, cost, P&L, and P&L %.

**CLI**

Top-level entry point: `cryptopilot`

Subcommands:

- `cryptopilot init`
  - Create `~/.cryptopilot` directory.
  - Initialize SQLite DB with schema.
  - Generate default `config.toml` if missing.
- `cryptopilot status`
  - Check DB initialization and integrity.
  - Show key config values.
- `cryptopilot collect`
  - Collect OHLCV for one or more symbols from the configured provider.
  - Supports:
    - `--symbols` / `--timeframe` / `--days`
    - `--update-all` (append from last candle)
    - `--dry-run` (do everything except writing to DB)
- `cryptopilot analyze run`
  - Run a single strategy on one symbol.
  - Prints action (BUY/SELL/HOLD), confidence, score, evidence, risk/context.
- `cryptopilot analyze portfolio`
  - Run a strategy across multiple symbols and show them in a table.
- `cryptopilot analyze history`
  - Show recent analysis results from the DB.
- `cryptopilot analyze strategies`
  - List all registered strategies and their required periods.
- `cryptopilot analyze compare`
  - Run all strategies on a single symbol and compare their outputs.
- `cryptopilot portfolio trade`
  - Record BUY/SELL trades with quantity, price, fee, account, notes.
- `cryptopilot portfolio list`
  - Show recent trades.
- `cryptopilot portfolio positions`
  - Show current positions (quantity, average cost, total cost, trade count).
- `cryptopilot portfolio pnl`
  - Show positions with current price, market value, and unrealized P&L + a portfolio summary.

---

## Not implemented yet (but designed)

These are part of the blueprint and roadmap, but you shouldn’t expect them to work today:

- Whale / on-chain metric series and factors.
- Exchange flow (venue-level) metric series and factors.
- Explicit **MetricSeries** abstraction for all data types (not just OHLCV).
- Full **decision & risk engine** that combines multiple strategy signals, user profile, and portfolio into a single decision plan per symbol.
- Rich user profiles (risk level, attention profile, allocation rules, preferences).
- Backtesting and strategy performance analytics.
- Report generator + LLM-based narrative reports.
- Dedicated `decide` and `report` CLI commands.
- API / UI layer on top of the same core.

See `ROADMAP.md` for how these arrive over 0.1.x–0.5.x and 1.0.0.

---

## Installation

### Requirements

- Python 3.11+
- `pip`
- SQLite (standard Python build is enough)

### Install from source

```bash
# Clone the repo
git clone https://github.com/mmrzaf/cryptopilot.git
cd cryptopilot

# Install in editable mode
pip install -e .

# With dev extras (tests, linters, type-checking)
pip install -e ".[dev]"
````

---

## Quick start

### 1. Initialize CryptoPilot

```bash
cryptopilot init
```

This will:

* Create `~/.cryptopilot/`
* Create `~/.cryptopilot/config.toml`
* Create and initialize `~/.cryptopilot/cryptopilot.db`

### 2. Check system status

```bash
cryptopilot status
```

You should see:

* Database: ✓ Ready
* Schema version and integrity
* Default provider, base currency, default symbols, debug mode

### 3. Collect some data

Example: 90 days of daily BTC/ETH candles from the default provider:

```bash
cryptopilot collect \
  --symbols BTC,ETH \
  --timeframe 1d \
  --days 90
```

Dry-run example (see what *would* be fetched, but don’t write to DB):

```bash
cryptopilot collect \
  --symbols BTC,ETH \
  --timeframe 1d \
  --days 90 \
  --dry-run
```

### 4. Run analysis

Single-symbol, single-strategy:

```bash
cryptopilot analyze run BTC \
  --strategy trend_following \
  --timeframe 1d
```

Portfolio-level analysis:

```bash
cryptopilot analyze portfolio \
  --symbols BTC,ETH,SOL \
  --strategy momentum \
  --timeframe 1d
```

Check strategy catalog:

```bash
cryptopilot analyze strategies
```

### 5. Track your portfolio

Record a trade:

```bash
cryptopilot portfolio trade BTC BUY 0.05 65000 \
  --fee 5 \
  --account main \
  --notes "Bought the dip, allegedly"
```

List recent trades:

```bash
cryptopilot portfolio list --limit 20
```

See current positions:

```bash
cryptopilot portfolio positions
```

See unrealized P&L (requires `market_data` for those symbols):

```bash
cryptopilot portfolio pnl
```

If P&L shows missing prices, run `cryptopilot collect` for those symbols/timeframes first.

---

## Configuration

CryptoPilot uses layered configuration:

1. **Environment variables** (`CRYPTOPILOT_*`)
2. **TOML file** (`~/.cryptopilot/config.toml`)
3. **Defaults in code**

### Config file

`cryptopilot init` will create a TOML config. A minimal example:

```toml
[api]
default_provider = "coingecko"
api_key = ""

[data]
default_timeframe = "1d"
default_symbols = ["BTC", "ETH", "SOL"]
retention_days = 730
gap_fill_check = true
batch_size = 100

[analysis]
default_strategies = ["trend_following", "mean_reversion"]
confidence_threshold = 0.6
risk_tolerance = "moderate"

[reporting]
llm_provider = "ollama"
llm_model = "gemma2:2b"
output_format = ["console", "json"]
include_personal_context = true
llm_api_base = "http://localhost:11434"
llm_api_key = ""

[currency]
base_currency = "USD"

debug = false
log_level = "INFO"
```

You can edit this file directly. At 0.0.5 there is no `cryptopilot config` CLI yet; it’s planned as part of the UX/reporting polish work.

### Environment overrides

Examples:

```bash
# Change default provider
export CRYPTOPILOT_API__DEFAULT_PROVIDER="coingecko"

# Set API key (for providers that need it)
export CRYPTOPILOT_API__API_KEY="your-key"

# Change risk tolerance
export CRYPTOPILOT_ANALYSIS__RISK_TOLERANCE="aggressive"

# Enable debug logging
export CRYPTOPILOT_DEBUG=true
```

---

## Architecture (short version)

Conceptually, CryptoPilot is moving toward:

* **Data platform**

  * Providers (market, whale, exchange flow, later derivatives/macro).
  * Time-series / MetricSeries storage with validation + gap handling.
* **Factor engine**

  * Derived metrics on top of series (technicals, whale factors, flow factors).
* **Strategy engine**

  * Strategies that request factors + metrics and emit standardized signals.
* **Decision & risk engine**

  * Aggregates strategy signals + user profile + portfolio into a decision plan.
* **Portfolio + profile services**

  * Trades, positions, P&L, allocations, constraints.
* **Reporting / LLM**

  * Turns structured decisions into human-readable reports.
* **CLI / API**

  * Commands like `collect`, `portfolio`, `analyze`, `decide`, `report`.

At 0.0.5, the **data platform**, **technical factor layer (indicators)**, **strategy engine**, and **portfolio engine** are real. The MetricSeries generalization, whales/flows, decision engine, and rich reporting are tracked in `ROADMAP.md`.

---

## Development

Run tests:

```bash
pytest -v
```

Type-check:

```bash
mypy cryptopilot/
```

Lint + format:

```bash
ruff check cryptopilot/
black cryptopilot/
```

---

## Disclaimer

CryptoPilot is **not** financial advice.

* No guarantees.
* No performance promises.
* You are responsible for your own trades and risk.

Treat it as a tool for structuring information and decisions, not an oracle.

---

## License

CryptoPilot is licensed under the **GNU GPL 3.0 or later**.
See the [`LICENSE`](./LICENSE) file for details.

