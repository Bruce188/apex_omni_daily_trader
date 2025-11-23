# ApexOmni Daily Trading Bot

A Python trading bot that executes strategic trades on ApexOmni to maximize your staking Trading Activity Factor (+0.5 maximum).

## Features

- **24/7 Continuous Trading**: Configurable intervals for round-the-clock operation
- **Automatic Position Closing**: All positions closed immediately (hardcoded safety)
- **1x Cross Margin**: Conservative leverage for safety (hardcoded)
- **Staking Optimization**: Achieves maximum Trading Activity Factor (0.5) with 5 unique trading days
- **Docker Ready**: Production-ready containerized deployment
- **Dry-Run Mode**: Safe testing without real trades

## Quick Start (Docker - Recommended)

Docker is the recommended deployment method for production use. It provides a stable, reproducible environment with automatic restarts and health checks.

### 1. Clone and Configure

```bash
# Clone the repository
git clone <repository-url>
cd apex_omni_daily_trader

# Copy the environment template
cp .env.example .env

# Edit with your credentials
nano .env  # or your preferred editor
```

Add your API credentials to `.env`:

```bash
APEX_API_KEY=your_api_key_here
APEX_API_SECRET=your_api_secret_here
APEX_PASSPHRASE=your_passphrase_here
APEX_ZK_SEEDS=your_zk_seeds_here
APEX_NETWORK=testnet  # Use 'mainnet' for live trading
DRY_RUN=true          # Set to 'false' for live trading
```

### 2. Start the Bot

```bash
# Build and start in detached mode
docker compose up -d --build

# Check if running
docker compose ps
```

### 3. Monitor

```bash
# View live logs
docker compose logs -f apex-trader

# View recent logs
docker compose logs --tail=100 apex-trader

# Check health status
docker inspect --format='{{.State.Health.Status}}' apex-daily-trader
```

### 4. Stop the Bot

```bash
# Graceful shutdown
docker compose down
```

## Quick Start (Python - Development Only)

Use Python directly for development, testing, or debugging. For production, use Docker.

### 1. Setup Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
nano .env  # Add your credentials
```

### 2. Test Configuration

```bash
# Validate configuration
python scripts/dry_run.py --validate

# Simulate a trade
python scripts/dry_run.py
```

### 3. Run Manually

```bash
# Check current status
python scripts/run_bot.py --status

# Execute a single trade (dry-run)
python scripts/run_bot.py

# Execute a live trade
python scripts/run_bot.py --live

# Force trade even if already traded today
python scripts/run_bot.py --force

# Enable verbose/debug logging
python scripts/run_bot.py --verbose
```

## Configuration

### Environment Variables (.env)

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `APEX_API_KEY` | Yes | Your ApexOmni API key | - |
| `APEX_API_SECRET` | Yes | Your API secret | - |
| `APEX_PASSPHRASE` | Yes | Your API passphrase | - |
| `APEX_ZK_SEEDS` | Yes | ZK seeds for order signing | - |
| `APEX_ZK_L2KEY` | No | ZK L2 key (derived from seeds if empty) | - |
| `APEX_NETWORK` | No | `testnet` or `mainnet` | `testnet` |
| `DRY_RUN` | No | Force dry-run mode | `true` |
| `LOG_LEVEL` | No | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `SCHEDULE_MODE` | No | `daily` or `continuous` | `daily` |
| `TRADE_INTERVAL_HOURS` | No | Hours between trades (continuous mode) | `4` |
| `DEBUG` | No | Enable detailed error messages | `false` |
| `MAX_FAILURES` | No | Circuit breaker failure threshold | `5` |
| `CIRCUIT_RESET_MINUTES` | No | Circuit breaker reset time (minutes) | `30` |

### Trading Configuration (config/trading.yaml)

```yaml
trading:
  # Symbol selection is AUTOMATIC - the bot always picks the cheapest tradeable symbol
  # based on your available balance. No manual symbol configuration needed.
  side: "BUY"                     # BUY or SELL
  type: "MARKET"                  # MARKET or LIMIT

schedule:
  mode: "continuous"              # "daily" or "continuous"
  trade_interval_hours: 4
  trade_days: [0, 1, 2, 3, 4, 5, 6]  # All 7 days (24/7 trading)
  trade_time: "09:00"             # For daily mode (UTC)
  continue_after_max_factor: true

safety:
  dry_run: true
  max_position_size: 0.01
  min_balance: 0.01
```

### Hardcoded Safety Settings

The following settings are **hardcoded for safety** and cannot be configured:

| Setting | Value | Reason |
|---------|-------|--------|
| **Leverage** | Always 1x (cross margin) | Prevents liquidation risk |
| **Position Closing** | Always immediate | Eliminates market exposure |

### Schedule Modes

#### Continuous Mode (Recommended for Docker)

Trades at regular intervals 24/7 on configured days:

- Default: Every 4 hours
- Runs continuously in the background
- Ideal for Docker deployment
- Checks trade eligibility at each interval

```yaml
schedule:
  mode: "continuous"
  trade_interval_hours: 4
  trade_days: [0, 1, 2, 3, 4, 5, 6]  # All 7 days (24/7 trading)
  continue_after_max_factor: true
```

#### Daily Mode

Single trade per day at a scheduled time:

- Traditional cron-style scheduling
- One trade at the specified time
- Good for manual execution
- **State persistence**: Bot remembers if it traded today (survives restarts)

```yaml
schedule:
  mode: "daily"
  trade_days: [0, 1, 2, 3, 4, 5, 6]  # All 7 days (24/7 trading)
  trade_time: "09:00"  # UTC
```

**Daily Mode State Tracking:**
- Bot tracks whether it has traded today in `bot_state.json`
- State survives container restarts and system reboots
- Prevents duplicate trades when bot restarts during the same day
- State resets automatically at midnight UTC

## Docker Deployment (Production)

### docker-compose.yml Overview

The Docker setup includes:

- **Automatic restarts**: `restart: unless-stopped`
- **Health checks**: Monitors bot health every 5 minutes
- **Graceful shutdown**: 30-second grace period for clean stops
- **Log rotation**: Prevents disk space issues
- **Data persistence**: Trade history stored in `./data` volume

### Starting Production

```bash
# Set environment for production
echo "DRY_RUN=false" >> .env
echo "APEX_NETWORK=mainnet" >> .env
echo "SCHEDULE_MODE=continuous" >> .env

# Start with build
docker compose up -d --build

# Verify running
docker compose ps
docker compose logs --tail=50 apex-trader
```

### Managing the Container

```bash
# View logs (follow mode)
docker compose logs -f apex-trader

# Check health
docker inspect apex-daily-trader --format='{{json .State.Health}}'

# Restart
docker compose restart apex-trader

# Stop gracefully
docker compose down

# Rebuild after code changes
docker compose up -d --build
```

### Data Persistence

Trade data and bot state are persisted in the `./data` directory:

```
data/
  trades.json           # Trade history
  weekly_records.json   # Weekly staking progress
  bot_state.json        # Daily mode state (has_traded_today)
```

This data survives container restarts and rebuilds.

**State Persistence (Daily Mode):**
The `bot_state.json` file tracks whether the bot has traded today. The state includes:
- `last_trade_date`: Date of last successful trade
- `traded_today`: Boolean flag checked before trading

## How It Works

### Order Flow and SDK Initialization

The bot uses the ApexOmni SDK v3 for all trading operations. Understanding the order flow is critical for troubleshooting:

```
1. SDK Initialization (CRITICAL)
   ├── Call configs_v3() → Sets internal configV3 state
   └── Call get_account_v3() → Sets internal accountV3 state
       └── BOTH required before placing any order

2. Symbol Selection (AUTOMATIC)
   ├── Call determine_best_symbol() to find cheapest tradeable symbol
   ├── Analyze ALL available trading pairs
   ├── Filter: enableOpenPosition=true AND enableTrade=true
   ├── Calculate min order value for each: min_order_size × current_price
   └── Select symbol with lowest minimum order value that fits balance

3. Trade Generation
   └── Generate trade with auto-selected symbol and size

4. Order Placement
   ├── Validate trade parameters
   ├── Check balance against margin requirements
   ├── Place BUY/SELL order via create_order_v3()
   └── Immediately place opposite order to close position

5. Position Management
   └── All positions closed immediately (hardcoded safety)
```

**Critical SDK Requirement**: The ApexOmni SDK v3 requires calling BOTH `configs_v3()` AND `get_account_v3()` BEFORE placing any orders. Without this initialization, the SDK lacks internal state needed for zkLink signature generation, causing orders to fail with cryptic errors like "insufficient margin" even when balance is sufficient.

### Symbol Selection Logic

The bot automatically selects the cheapest tradeable symbol based on your available balance:

1. `determine_best_symbol()` analyzes ALL available trading pairs
2. Filters to only tradeable symbols (`enableOpenPosition=true` AND `enableTrade=true`)
3. Calculates minimum order value for each: `min_order_size x current_price`
4. Selects the symbol with the lowest minimum order value that fits your balance
5. Trade is generated with the auto-selected symbol

**Symbol Tradability:**
- Each symbol has `enableOpenPosition` and `enableTrade` flags
- Only symbols with both flags `true` are considered
- The bot always picks the cheapest option to minimize trading costs

**Example successful trade:**
- Symbol: LINEA-USDT (auto-selected as cheapest tradeable)
- Min Order: 1.0 LINEA @ $0.0093 = $0.0093 trade value
- Balance: $2.01 (sufficient)

## Trading Strategy

### Goal

Maximize the **Trading Activity Factor** (up to 0.5) by trading on 5 different days within each weekly staking period.

### How It Works

| Days Traded | Trading Activity Factor | Staking Boost |
|-------------|-------------------------|---------------|
| 0 | 0.0 | +0% |
| 1 | 0.1 | +10% |
| 2 | 0.2 | +20% |
| 3 | 0.3 | +30% |
| 4 | 0.4 | +40% |
| 5 | 0.5 | +50% (maximum) |

### Weekly Staking Period

- **Reset**: Every Monday at 8:00 AM UTC
- **Day boundary**: 8:00 AM UTC each day
- **Recommended trade time**: 9:00 AM UTC (after boundary)

### Trade Characteristics

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Size | Minimum order size | Minimize cost and risk |
| Pair | Auto-selected | Cheapest tradeable symbol |
| Type | MARKET | Guaranteed fills |
| Leverage | 1x (hardcoded) | Safety |
| Position | Always closed (hardcoded) | No exposure |

### Cost-Benefit Analysis

Weekly trading costs are minimal to zero. Real trades have shown $0.00 fees when using minimum order sizes on certain trading pairs. For stakers with meaningful APEX holdings, the 50% reward boost comes at virtually no cost.

### Successful Trade Example

Here's what a successful trade looks like in the logs:

```
Determining best symbol (balance: $2.0065 USDT)
Analyzing all tradeable symbols...
Found 113 tradeable symbols
Symbol Analysis (balance: $2.01):
  - LINEA-USDT: min 1 x $0.0093 = $0.0093 (CHEAPEST - SELECTED)
  - MOCA-USDT: min 1 x $0.0156 = $0.0156 (TRADEABLE)
  - BTC-USDT: min 0.001 x $95000.00 = $95.0000 (INSUFFICIENT BALANCE)
  ...
Auto-selected cheapest symbol: LINEA-USDT (min size: 1)
Generated trade for today:
  Symbol: LINEA-USDT
  Side: BUY
  Size: 1
==================================================
Executing trade for today
Symbol: LINEA-USDT
Side: BUY
Size: 1
==================================================
Current price: $0.0093
Trade value: $0.0093
Placing MARKET BUY order: 1 LINEA-USDT @ 0.0093
Order placed successfully: 780050192285040971
Opening order placed: 780050192285040971
Filled at: $0.0093
Closing position immediately (mandatory for safety)...
Placing MARKET SELL order: 1.0 LINEA-USDT @ 0.0093
Order placed successfully: 780050196705837387
Position closed at: $0.0093
--------------------------------------------------
TRADE SUCCESSFUL
  Order ID: 780050192285040971
  Symbol: LINEA-USDT
  Side: BUY
  Size: 1.0
  Price: $0.0093
  Fees: $0.0000
  Close Order ID: 780050196705837387
  Close Price: $0.0093
  P&L: $0.0000
--------------------------------------------------
Today's trading complete!
Trading Activity Factor: 0.1
--------------------------------------------------
```

## Monitoring and Logs

### Docker Logs

```bash
# Live log streaming
docker compose logs -f apex-trader

# Last 100 lines
docker compose logs --tail=100 apex-trader

# Search logs
docker compose logs apex-trader 2>&1 | grep -i error
```

### Bot Status (Python)

```bash
# Current status
python scripts/run_bot.py --status

# Weekly plan
python scripts/run_bot.py --plan
```

### Log Levels

Set `LOG_LEVEL` in `.env`:

- `DEBUG`: Detailed debugging information
- `INFO`: Normal operation logs (default)
- `WARNING`: Potential issues
- `ERROR`: Errors only

## Troubleshooting

### "Insufficient Margin" Error (CRITICAL)

This is the most common error and often has a non-obvious cause:

**Symptoms:**
```
API Error: insufficient margin
API Error: Margin insufficient for new order
```

**Root Causes:**

1. **SDK Not Initialized** (Most Common)
   - The ApexOmni SDK requires `configs_v3()` AND `get_account_v3()` to be called before any order
   - Without this, the SDK lacks internal state for zkLink signature generation
   - The bot handles this automatically via `_ensure_sdk_initialized()`

2. **Symbol Not Tradeable**
   - Many symbols have `enableOpenPosition=false` or `enableTrade=false`
   - The bot filters these out automatically with `get_all_symbols(tradeable_only=True)`

3. **Actual Insufficient Balance**
   - Ensure balance meets the minimum order value
   - The bot automatically selects the cheapest tradeable symbol for your balance

**Solutions:**
```bash
# Enable debug mode to see full error details
DEBUG=true python scripts/run_bot.py --live

# Check available tradeable symbols
python -c "
from bot.api_client import create_client
from bot.config import Config
config = Config.load()
client = create_client(config.api, dry_run=False)
client.test_connection()
symbols = client.get_all_symbols(tradeable_only=True)
for s in sorted(symbols, key=lambda x: float(x.min_order_size)):
    price = client.get_current_price(s.symbol)
    if price:
        value = float(s.min_order_size) * float(price)
        print(f'{s.symbol}: min_size={s.min_order_size}, price={price:.6f}, value=\${value:.4f}')
"
```

### Container Won't Start

```bash
# Check logs for errors
docker compose logs apex-trader

# Verify configuration
docker compose config

# Check .env file exists and has values
cat .env | grep APEX
```

### Health Check Failures

```bash
# Check health status
docker inspect apex-daily-trader --format='{{json .State.Health}}'

# View health check output
docker inspect apex-daily-trader --format='{{range .State.Health.Log}}{{.Output}}{{end}}'
```

### Authentication Errors

1. Verify API credentials in `.env`
2. Ensure ZK seeds are correct
3. Check network setting matches your API key (testnet vs mainnet)
4. Sync system time: `sudo ntpdate pool.ntp.org`

### No Trades Executing

1. Check if `DRY_RUN=true` (trades simulated, not real)
2. Verify today is a configured trade day
3. Check account balance meets minimum requirement
4. Review logs for specific errors

### Common Docker Issues

| Issue | Solution |
|-------|----------|
| "Permission denied" | Run with `sudo` or add user to docker group |
| "Port already in use" | Bot doesn't use ports, check other containers |
| "No space left" | Run `docker system prune` to clean up |
| Container keeps restarting | Check logs, likely config error |

For comprehensive troubleshooting, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Project Structure

```
apex_omni_daily_trader/
|-- bot/                      # Core trading bot
|   |-- api_client.py         # ApexOmni SDK wrapper
|   |-- config.py             # Configuration management
|   |-- strategy.py           # Trading strategy logic
|   |-- trade_executor.py     # Trade execution (mandatory closing, symbol-first)
|   |-- circuit_breaker.py    # Circuit breaker protection
|   `-- utils.py              # Helper utilities
|-- data/                     # Data management (runtime files)
|   |-- collector.py          # Trade data collection
|   |-- metrics.py            # Performance metrics
|   |-- models.py             # Data models
|   |-- storage.py            # Data persistence
|   |-- trades.json           # Trade history (runtime)
|   |-- weekly_records.json   # Weekly staking progress (runtime)
|   `-- bot_state.json        # Daily mode state (runtime)
|-- analytics/                # Analytics
|   |-- multiplier_analysis.py
|   `-- performance.py
|-- scripts/                  # Entry points
|   |-- run_bot.py            # CLI entry point
|   |-- run_continuous.py     # Daemon for Docker
|   |-- dry_run.py            # Simulation mode
|   |-- derive_zk_seeds.py    # ZK key derivation utility
|   `-- calculate_multiplier.py
|-- config/
|   `-- trading.yaml          # Trading parameters
|-- docker/
|   `-- Dockerfile
|-- tests/                    # Test suite
|-- docs/                     # Documentation
|-- docker-compose.yml
|-- .env.example
`-- README.md
```

## Documentation

- [Setup Guide](docs/SETUP.md) - Detailed installation instructions
- [API Documentation](docs/API.md) - ApexOmni API integration details
- [Trading Strategy](docs/STRATEGY.md) - Strategy explanation
- [Staking Optimization](docs/STAKING_OPTIMIZATION.md) - Multiplier formulas
- [Architecture](docs/ARCHITECTURE.md) - System design
- [Troubleshooting](docs/TROUBLESHOOTING.md) - Common issues and solutions

## Safety Considerations

### Security Best Practices

- API keys are stored in `.env` (never committed to git)
- `.gitignore` excludes sensitive files
- No credentials are logged
- All API communication uses HTTPS

### Trading Safety

- **Leverage is always 1x** - prevents liquidation risk
- **Positions always close immediately** - no market exposure
- **Dry-run mode enabled by default** - test before live trading
- Balance checks before trading
- Position limits enforced

### Circuit Breaker Protection

The bot includes automatic circuit breaker protection:
- Blocks trading after 5 consecutive failures
- Auto-resets after 30 minutes
- Prevents runaway losses during API outages
- Configurable via environment variables:
  - `MAX_FAILURES` (default: 5)
  - `CIRCUIT_RESET_MINUTES` (default: 30)

### Mainnet Safety Warning

When running in live mode on mainnet, the bot displays a warning with 5-second countdown:
- Press Ctrl+C to abort
- Prevents accidental live trading
- Only shown when `DRY_RUN=false` AND `APEX_NETWORK=mainnet`

### Risk Warnings

- Trading cryptocurrencies involves risk
- Past performance does not guarantee future results
- Only trade with funds you can afford to lose
- Minor slippage may occur between buy and sell orders

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Run tests: `pytest`
4. Commit your changes (`git commit -m 'Add your feature'`)
5. Push to the branch (`git push origin feature/your-feature`)
6. Open a Pull Request

## License

MIT License - see LICENSE file for details.

## Disclaimer

This software is provided for educational and informational purposes only. It is not financial advice. Trading cryptocurrencies carries significant risk, and you should consult with a qualified financial advisor before making any investment decisions. The authors are not responsible for any losses incurred through the use of this software.

## Support

- **Issues**: Report bugs via GitHub Issues
- **Documentation**: See the `docs/` folder for detailed guides
- **ApexOmni**: https://omni.apex.exchange
- **Testnet**: https://testnet.omni.apex.exchange
