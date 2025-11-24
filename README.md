# CryptoPilot

> Your cryptocurrency market co-pilot for data-driven trading analysis

**Status**: Phase 1 - Foundation Development

## Overview

CryptoPilot is a modular CLI-based platform for cryptocurrency market analysis with personalized portfolio insights and AI-powered reporting. Built with strict typing, async-first architecture, and robust data handling.

## Core Philosophy

**"Collect once, analyze many ways"** - A robust data collection foundation with pluggable data sources and analysis strategies, always explaining the "why" behind every suggestion.

## Features

### Current (Phase 1)
- ✅ Abstracted data provider architecture (CoinGecko first)
- ✅ Async SQLite database with decimal precision
- ✅ Strict Pydantic models with comprehensive validation
- ✅ Configuration hierarchy (CLI > ENV > TOML > Defaults)
- ✅ Exponential backoff retry logic for rate limits
- ✅ USDT-based valuation system

### Planned
- 🔄 Multi-provider support (CoinMarketCap, Binance)
- 🔄 Portfolio management with cost basis tracking
- 🔄 Analysis strategies (trend following, mean reversion, momentum)
- 🔄 LLM-enhanced reporting (Ollama, OpenAI, etc.)
- 🔄 Gap detection and automatic data filling

## Installation

### Prerequisites
- Python 3.11+
- pip

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/cryptopilot.git
cd cryptopilot

# Install dependencies
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"

# Initialize CryptoPilot
cryptopilot init
```

## Quick Start

```bash
# Check system status
cryptopilot status

# View current configuration
cryptopilot config show

# Collect market data
cryptopilot collect --symbols BTC,ETH,SOL --timeframe 1d --days 90

# Update portfolio balances (all values in USDT)
cryptopilot balance update --btc 0.5 --eth 2.0 --usdt 5000

# Record a trade
cryptopilot trade record --buy ETH --quantity 1.0 --price 2800 --fees 10

# Analyze market
cryptopilot analyze --symbol BTC --strategies trend_following

# Generate report
cryptopilot report generate --format console
```

## Project Structure

```
cryptopilot/
├── config/          # Configuration management
├── database/        # Async SQLite + models
├── providers/       # Data provider abstractions
├── collectors/      # Market data collection
├── portfolio/       # Portfolio management
├── analysis/        # Analysis strategies
├── reporting/       # Report generation + LLM
├── utils/           # Common utilities
└── cli/             # CLI commands
```

## Configuration

Configuration follows priority hierarchy:
1. CLI Arguments (highest)
2. Environment Variables
3. TOML Configuration File
4. Default Values (lowest)

### Configuration File

Located at `~/.cryptopilot/config.toml`:

```toml
[api]
default_provider = "coingecko"
api_key = ""  # Optional for most providers

[data]
default_timeframe = "1d"
default_symbols = ["BTC", "ETH", "SOL"]
retention_days = 730

[analysis]
default_strategies = ["trend_following", "mean_reversion"]
confidence_threshold = 0.6
risk_tolerance = "moderate"

[reporting]
llm_provider = "ollama"
llm_model = "gemma2:2b"
output_format = ["console", "json"]

[currency]
base_currency = "USDT"
```

### Environment Variables

```bash
# API Configuration
export CRYPTOPILOT_API__DEFAULT_PROVIDER="coingecko"
export CRYPTOPILOT_API__API_KEY="your-key"

# Analysis Configuration
export CRYPTOPILOT_ANALYSIS__RISK_TOLERANCE="aggressive"

# Debug Mode
export CRYPTOPILOT_DEBUG=true
```

## Architecture Highlights

### Decimal Precision
All monetary values stored as `TEXT` in database to prevent floating-point errors:
```python
# ✅ Correct
price = Decimal("42000.50")

# ❌ Wrong
price = 42000.50  # Float precision issues
```

### Provider Abstraction
Easy to add new data providers:
```python
class NewProvider(DataProviderBase):
    async def get_ohlcv(self, symbol: str, ...) -> list[OHLCV]:
        # Implement provider-specific logic
        # Must return normalized XXX/USDT data
        pass
```

### Async-First
All I/O operations are async for better performance:
```python
async with db.get_connection() as conn:
    await conn.execute(query, params)
```

### Strict Typing
Comprehensive type hints with mypy strict mode:
```python
def calculate_cost_basis(
    trades: list[TradeRecord],
) -> dict[str, Decimal]:
    ...
```

## Development

### Run Tests
```bash
pytest tests/ -v
```

### Type Checking
```bash
mypy cryptopilot/
```

### Code Formatting
```bash
black cryptopilot/
ruff check cryptopilot/
```

## Database Schema

### Core Tables
- `market_data` - OHLCV data with provider tracking
- `trades` - Trade history with cost tracking
- `balance_snapshots` - Portfolio state over time
- `analysis_results` - Strategy recommendations
- `strategy_performance` - Backtest results

All tables use:
- UTC timestamps (ISO 8601)
- Decimal values stored as TEXT
- Comprehensive indexing

## Safety Features

### Financial Integrity
- Strict decimal arithmetic (no floats)
- Transaction validation
- Atomic database operations
- Comprehensive error handling

### Rate Limit Protection
- Exponential backoff
- Provider-specific retry logic
- Graceful degradation

### Data Quality
- Gap detection
- Integrity checks
- Validation at every layer

## Roadmap

### Phase 1: Foundation (Current)
- [x] Database schema and connection
- [x] Configuration system
- [x] Provider abstraction
- [ ] Data collection implementation
- [ ] Basic CLI commands

### Phase 2: Analysis
- [ ] Multiple data providers
- [ ] Analysis strategies
- [ ] Portfolio tracking
- [ ] Cost basis calculation

### Phase 3: Intelligence
- [ ] LLM integration
- [ ] Enhanced reporting
- [ ] Historical comparisons
- [ ] Risk assessment

### Phase 4: Production
- [ ] Comprehensive testing
- [ ] Performance optimization
- [ ] Documentation
- [ ] CI/CD pipeline

## Contributing

This project is in early development. Contributions welcome!

## License

GNU GPL 3 License - See LICENSE file for details

## Disclaimer

⚠️ **IMPORTANT**: CryptoPilot is for informational purposes only. It does NOT provide financial advice. All trading decisions are your responsibility. Cryptocurrency trading carries significant risk.

## Support

- Documentation: [Coming soon]
- Issues: GitHub Issues
- Discussions: GitHub Discussions

