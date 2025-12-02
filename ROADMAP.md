# CryptoPilot Roadmap

## 0.0.x – Foundation and stabilization

### 0.0.0 – Project scaffolding

**Scope**

- Repository structure and packaging
- CI skeleton and basic tooling

**Deliverables**

- Python project layout with `cryptopilot` package
- `pyproject.toml` / setup configuration
- Basic logging and error-handling conventions
- Placeholder CLI entry point (`cryptopilot`)

---

### 0.0.1 – Persistence and configuration

**Scope**

- Local database and configuration system

**Deliverables**

- SQLite schema (initial tables for `market_data`, `trades`, `analysis_results`, `system_events`)
- Database connection and migration utilities
- Configuration loader:
  - Config file (`config.toml`) under `~/.cryptopilot/`
  - Environment-variable overrides
- `cryptopilot init` and `cryptopilot status` commands

---

### 0.0.2 – Provider abstraction

**Scope**

- Standardized access to external market data

**Deliverables**

- `DataProviderBase` interface (OHLCV, symbol validation, supported timeframes, health check)
- Provider models (`OHLCV`, `ProviderInfo`, errors)
- Initial provider implementation (CoinGecko):
  - OHLCV fetch
  - Current price
  - Supported symbol listing
- Common retry and rate-limit handling

---

### 0.0.3 – Data collection pipeline

**Scope**

- End-to-end pipeline to fetch and store OHLCV data

**Deliverables**

- Collection service using providers and database:
  - Windowed backfill for historical data
  - Continuous append for new candles
- Gap detection and basic gap-filling logic
- `cryptopilot collect` command:
  - Symbols, timeframe, and history window selection
  - Dry-run mode (no writes)

---

### 0.0.4 – MetricSeries and technical factor engine

**Scope**

- Internal representation of time series and technical factors

**Deliverables**

- MetricSeries model for price/volume-based data:
  - Namespace, metric name, symbol, timeframe, (optional) venue
- Mapping between stored OHLCV and MetricSeries
- Technical factor library:
  - Moving averages (SMA/EMA)
  - Momentum, RSI, MACD
  - Volatility, ATR, basic trend helpers
- Factor computation service that:
  - Accepts MetricSeries inputs
  - Computes factors once per run for reuse by strategies

---

### 0.0.5 – Strategy framework and analysis CLI

**Scope**

- Strategy execution on top of technical factors

**Deliverables**

- Strategy specification:
  - Name, category (technical)
  - Supported goals (entry/exit/hold)
  - Supported horizons (short-term/swing/position)
  - Required factors and metrics
- Standardized strategy signal model:
  - Action (buy/sell/hold/no-action)
  - Confidence score and label
  - Validity window and optional price levels
  - Evidence and risk annotations
- Initial strategies:
  - Trend-following
  - Mean-reversion
  - Momentum
- Analysis engine:
  - Loads OHLCV from DB
  - Computes required factors
  - Executes selected strategies
- CLI:
  - `cryptopilot analyze run`
  - `cryptopilot analyze portfolio`
  - `cryptopilot analyze history`
  - `cryptopilot analyze strategies`
  - `cryptopilot analyze compare`

---

### 0.0.6 – Portfolio engine

**Scope**

- Core portfolio accounting on top of trade history

**Deliverables**

- Portfolio manager:
  - Trade recording with validation
  - Position construction using average cost basis
  - Unrealized P&L per position
- Portfolio-level metrics:
  - Total cost
  - Total value
  - Total P&L and P&L %
- CLI:
  - `cryptopilot portfolio trade`
  - `cryptopilot portfolio list`
  - `cryptopilot portfolio positions`
  - `cryptopilot portfolio pnl`

---

### 0.0.7 – Technical decision engine and profile v1

**Scope**

- First decision engine based only on technical strategies and portfolio context

**Deliverables**

- Minimal user profile:
  - Risk level: conservative / moderate / aggressive
- Decision engine v0:
  - Input: symbol, goal (entry/exit/hold), horizon, user profile
  - Input signals: bundle of technical strategies
  - Output: decision object:
    - Action (buy/sell/hold/no-action)
    - Confidence score and classification
    - Validity window
    - Evidence summary and risk notes
- Structured outputs:
  - Console view
  - JSON format for programmatic use
- CLI:
  - `cryptopilot decide` for single-symbol decisions

---

### 0.0.8 – Test and validation release

**Scope**

- Stabilization, test coverage, and basic reliability checks for everything in 0.0.0–0.0.7

**Deliverables**

- Test suite:
  - Unit tests for providers, DB access, indicators, strategies, portfolio logic
  - Integration tests for:
    - Data collection flows
    - Decision engine end-to-end
    - Portfolio summaries
  - CLI smoke tests for main commands
- Validation:
  - Sample workflows over real historical data for a small set of symbols/timeframes
  - Basic performance checks on typical usage (few symbols, standard timeframes)
- Tooling:
  - CI configuration to run tests and linters
  - Clear error messages for common failure modes (missing data, config issues)

0.0.8 acts as the stability baseline for subsequent feature releases.

---

## 0.1 – Whales: long-term smart money layer

**Scope**

- Add whale / on-chain metrics as a first-class signal for swing and position horizons.

**Deliverables**

- Whale MetricSeries:
  - Net exchange inflow/outflow
  - Accumulation vs distribution indices
  - Whale activity ratios
- Whale factor library:
  - Accumulation/distribution regimes
  - Flow-based risk flags (e.g. heavy inflow to exchanges)
- Whale-only strategies:
  - Swing/position-focused accumulation and distribution strategies
- Mixed technical + whale strategies:
  - Trend/whale alignment and conflict handling
- Decision engine updates:
  - Technical and whale views combined
  - Confidence adjustment based on whale confirmation or contradiction
- Reporting:
  - Whale viewpoint included in decision outputs and reports

---

## 0.2 – Exchange flow: short-term microstructure layer

**Scope**

- Introduce exchange-level flow signals for short-term and intraday decisions.

**Deliverables**

- Exchange flow MetricSeries:
  - Spot volume per exchange
  - Taker buy/sell volumes and ratios
  - Optional derivatives-related metrics where available
- Flow factors:
  - Volume surges vs baseline
  - Taker dominance regimes
  - Simple spot vs derivatives imbalance
- Flow-focused strategies:
  - Confirmation/fakeout detection for short-term moves
  - Breakout and exhaustion detection
- Mixed technical + flow strategies:
  - Up/downgrading technical breakouts based on flow
- Decision engine:
  - Explicit separation of long-term (whales + higher timeframe) vs short-term (flow + lower timeframe) views

---

## 0.3 – Portfolio-aware decision making

**Scope**

- Make all decisions portfolio-aware, with explicit sizing and rebalancing logic.

**Deliverables**

- Portfolio engine v2:
  - Exposure per asset and per category
  - Portfolio-level concentration metrics
- User profile v2:
  - Max per-asset allocation
  - Category-level constraints (e.g. memecoins, majors)
  - Preferred horizons and style
- Portfolio-aware decision engine:
  - Uses portfolio snapshot and constraints in all decisions
  - Produces sizing recommendations (add/trim/exit amounts)
  - Explicit rebalance goal support
- Portfolio reports:
  - Portfolio review with per-symbol recommendations and exposure analysis

---

## 0.4 – Backtesting and evaluation

**Scope**

- Evaluate strategies and decision logic on historical data.

**Deliverables**

- Backtest framework:
  - Reuse data platform, factors, strategies, and decision engine
  - Single-strategy and portfolio-level backtests
- Performance metrics:
  - Hit rate, payoff distributions, drawdown, volatility
  - Regime breakdown (trending vs ranging, high-vol vs low-vol)
- Decision logic benchmarking:
  - Comparison against simple baselines (buy-and-hold, MA crossover)
- Internal analytics tools:
  - Identification of weak/redundant strategies
  - Support for tuning strategy weights and thresholds

---

## 0.5 – Risk, profiles, and reporting

**Scope**

- Harden risk management, refine profiles, and standardize reporting.

**Deliverables**

- Risk engine v1:
  - Maximum per-trade risk
  - Asset and category allocation limits
  - Integration of risk checks into final decisions
- User profiles v3:
  - Attention/time model
  - Preferences for horizon and noise level
- Report templates:
  - Quick symbol decision report
  - Daily overview for watchlists
  - Weekly portfolio review
- LLM-assisted narrative (optional):
  - Natural-language summaries built from structured reports
  - Strict risk and responsibility messaging
- CLI polish:
  - Clear command set (`config`, `collect`, `portfolio`, `decide`, `report`)
  - Improved error handling and diagnostics

---

## 1.0 – Production release

**Scope**

- Deliver a stable, explainable, portfolio-aware decision engine integrating technicals, whales, and exchange flows.

**Expected characteristics**

- Data platform:
  - MetricSeries support for OHLCV, whale metrics, and exchange flow
  - Reliable ingestion, validation, and gap handling
- Intelligence core:
  - Documented factor library
  - Curated set of technical, whale, flow, and mixed strategies
  - Decision engine that consistently applies user profile and risk constraints
- Portfolio and user layer:
  - Portfolio-aware decisions as the default
  - Support for entries, exits, holds, and rebalancing
- Reporting:
  - Standardized report types
  - Clear explanation of signals, decisions, conflicts, and risk flags
- Quality:
  - Backtesting-informed tuning of strategies and weights
  - Solid automated test coverage
  - Documentation of capabilities and limitations


