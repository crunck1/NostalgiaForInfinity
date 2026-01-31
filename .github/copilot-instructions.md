# NostalgiaForInfinity AI Agent Instructions

## Project Overview
This is **NostalgiaForInfinity (NFI)**, a sophisticated cryptocurrency trading strategy for [Freqtrade](https://www.freqtrade.io). The codebase contains multiple strategy versions (`NostalgiaForInfinityX.py` through `NostalgiaForInfinityX7.py`).

**⚠️ IMPORTANT: Use only `NostalgiaForInfinityX7.py` for all current development, modifications, and deployments.**

## Architecture & Key Concepts

### Strategy Structure
- **Current Version**: `NostalgiaForInfinityX7.py` is the ONLY version to use for active development and live trading
- **Legacy Versions**: X, X2-X6 exist only for historical backtesting comparisons - do not modify or recommend these
- **Single-File Design**: Strategy files are intentionally large (30k-70k+ lines) containing all buy/sell conditions, indicators, and trade management logic - this is by design, do not suggest splitting them

### Critical Configuration Requirements
Freqtrade configuration **must** include these exact settings (documented in strategy headers):
- Timeframe: **5m only** (hardcoded requirement)
- `use_exit_signal: true`
- `exit_profit_only: false`
- `ignore_roi_if_entry_signal: true`
- Recommended: 6-12 open trades with unlimited stake
- Recommended: 40-80 pairs, stable coin pairs (USDT/USDC), blacklist leveraged tokens

### Trading Modes & Short Control
X7 supports spot/futures/margin trading with configurable short trading:
- Environment variable `NFI_CAN_SHORT` (true/false/yes/no/1/0) controls short trading enablement
- Parameter `can_short_override` in config overrides default behavior
- See [SHORT_TRADING_CONFIG.md](SHORT_TRADING_CONFIG.md) for implementation details

### Position Management Features
- **Rebuy/DCA System**: `position_adjustment_enable` flag controls automatic position averaging down via `adjust_trade_position()` method
- **Hold Support**: `user_data/nfi-hold-trades.json` allows manual hold overrides for specific trade IDs or pairs with profit thresholds
  ```json
  {"trade_ids": {"1": 0.001, "3": -0.005}, "trade_pairs": {"BTC/USDT": 0.001}}
  ```

### Multi-Timeframe Indicator System
Strategies use informative pairs across multiple timeframes:
- Base timeframe: 5m
- Info timeframes: 15m, 1h, 4h, 1d
- BTC informatives: separate BTC pair data for market context
- Indicators calculated via `populate_indicators()` with `pandas_ta` and `talib`

## Development Workflows

### Running Live/Dry-Run Trading
```bash
# 1. Copy and configure environment
cp live-account-example.env .env
# Edit .env with exchange credentials and settings

# 2. Run with Docker Compose
docker compose up

# Container name pattern: {BOT_NAME}_{EXCHANGE}_{TRADING_MODE}-{STRATEGY}
# Logs: user_data/logs/
# Database: user_data/{BOT_NAME}_{EXCHANGE}_{TRADING_MODE}-tradesv3.sqlite
```

### Backtesting Workflow
```bash
# 1. Download market data (uses sparse git checkout for efficiency)
./tools/download-necessary-exchange-market-data-for-backtests.sh
# Edit script variables: EXCHANGE, TRADING_MODE, TIMEFRAME

# 2. Run comprehensive backtests
cd tests/backtests/
./backtesting-all.sh  # Multi-day run across all exchanges/years
# Or use specific scripts:
./backtesting-focus-group.sh  # Smaller pair subset
./backtesting-analysis.sh     # Generate analysis reports

# 3. Tests use pytest with parallel execution
pytest -n 5  # Configured in pytest.ini
```

### Testing
- **Unit Tests**: `tests/unit/` - test individual strategy methods
- **Backtest Tests**: `tests/backtests/` - extensive historical performance validation
- Config in `pytest.ini`: parallel execution (`-n 5`), JUnit XML reports for CI

## Code Conventions

### Strategy Entry/Exit Conditions
Buy conditions numbered sequentially with enable flags:
```python
buy_params = {
  "buy_condition_1_enable": True,
  "buy_condition_2_enable": True,
  # ... up to 100+ conditions
}
```

Each condition in `populate_entry_trend()` with detailed inline comments explaining indicator logic.

### Indicator Calculation Patterns
```python
# Standard pattern in populate_indicators()
dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
dataframe['ema_12'] = ta.EMA(dataframe, timeperiod=12)

# Informative pair merging
informative_1h = self.dp.get_pair_dataframe(pair=metadata['pair'], timeframe='1h')
informative_1h = self.populate_indicators_1h(informative_1h, metadata)
dataframe = merge_informative_pair(dataframe, informative_1h, self.timeframe, '1h', ffill=True)
```

### Mode Tags System
Strategies use mode tags to categorize entry conditions:
- Long normal mode: tags "1"-"13"
- Long pump mode: tags "21"-"26"
- Long quick mode: tags "41"-"53"
- Long rebuy/high profit/rapid/grind modes: various tag ranges
- Short modes: similar numbering in "201"+ range

Tags set in entry conditions for trade tracking/analysis.

## Configuration Management

### Environment-Based Configuration
Docker Compose uses `FREQTRADE__*` environment variables:
```bash
FREQTRADE__EXCHANGE__NAME=binance
FREQTRADE__TRADING_MODE=futures
FREQTRADE__STRATEGY=NostalgiaForInfinityX7
FREQTRADE__MAX_OPEN_TRADES=12
```

### Config File Hierarchy
- `configs/exampleconfig.json` - base configuration template
- `configs/exampleconfig-rebuy.json` - rebuy-specific settings
- `configs/blacklist-{exchange}.json` - exchange-specific pair blacklists
- `configs/pairlist-*.json` - static/volume-based pair lists for different exchanges

### Exchange-Specific Considerations
Multiple exchange support with exchange-specific:
- Blacklists in `configs/blacklist-{exchange}.json`
- Pairlist configurations for spot/futures markets
- CCXT config with rate limiting and partner IDs in config JSON

## Project Structure

```
NostalgiaForInfinityX[1-7].py  # Strategy versions (use X7)
configs/                        # Freqtrade configurations
  exampleconfig.json           # Base config template
  blacklist-*.json             # Exchange blacklists
  pairlist-*.json              # Pair lists
docker/
  Dockerfile.custom            # Custom Freqtrade image with deps
docker-compose.yml             # Production deployment
tests/
  unit/                        # Unit tests
  backtests/                   # Backtest scripts and historical data
tools/                         # Helper scripts
  download-necessary-exchange-market-data-for-backtests.sh
  update_nfx*.sh              # Strategy update scripts
user_data/                     # Runtime data (logs, databases, holds)
  nfi-hold-trades.json        # Optional hold overrides
docs/                          # MkDocs documentation
```

## Important Dependencies
- **Freqtrade**: Core trading framework (automatically pulled in Docker)
- **pandas_ta**: Technical analysis indicators (required, installed in custom Docker image)
- **talib**: TA-Lib for additional indicators
- Python 3.12+ (specified in pyproject.toml)

## Common Pitfalls
- **Never modify timeframe** from 5m - strategies are optimized for 5-minute candles
- **Don't override ROI/stoploss** settings in config - strategy manages exits
- **Blacklist leveraged tokens** (*BULL, *BEAR, *UP, *DOWN) - patterns in strategy header
- **Use stable coin pairs** (USDT/USDC preferred over BTC/ETH pairs)
- When modifying indicators, ensure informative timeframes are populated before merging

## Documentation
- Full docs: https://iterativv.github.io/NostalgiaForInfinity/
- Commit messages contain backtest results for strategy changes
- Strategy headers contain detailed configuration requirements and hold support docs
