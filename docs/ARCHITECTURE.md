# ApexOmni Trading Bot - System Architecture

---

## 1. Architecture Overview

### 1.1 System Purpose

A Python trading bot that executes strategic trades on ApexOmni to maximize the staking factor multiplication. The bot is designed for:

- **Safety First:** 1x leverage only, mandatory position closing
- **Docker Deployment:** Production-ready containerized operation
- **24/7 Operation:** Continuous trading mode with configurable intervals
- **Optimization:** Maximize Trading Activity Factor (0.5)

### 1.2 High-Level Architecture

```
                     Docker Container (Production)
                              |
                              v
+--------------------------------------------------------------------+
|                      ApexOmni Trading Bot                           |
+--------------------------------------------------------------------+
|                                                                     |
|  +-------------+  +-------------+  +---------------------------+   |
|  |   Config    |  |   Logger    |  |    Environment (.env)     |   |
|  |   Manager   |  |   System    |  |    API Keys, Settings     |   |
|  +------+------+  +------+------+  +-------------+-------------+   |
|         |                |                       |                  |
|         +----------------+-----------------------+                  |
|                          |                                          |
|  +-----------------------v-----------------------------------+     |
|  |                  Entry Points                              |     |
|  |  +--------------------+  +--------------+  +------------+ |     |
|  |  | run_continuous.py  |  | run_bot.py   |  | dry_run.py | |     |
|  |  | (Docker daemon)    |  | (CLI)        |  | (testing)  | |     |
|  |  +--------------------+  +--------------+  +------------+ |     |
|  +------------------------------+-----------------------------+     |
|                                 |                                   |
|  +------------------------------v-----------------------------+     |
|  |                    Core Engine                             |     |
|  |  +-------------+  +---------------+  +----------------+   |     |
|  |  | API Client  |  |    Trade      |  |    Strategy    |   |     |
|  |  | (ApexOmni)  |<-|   Executor    |<-| (continuous/   |   |     |
|  |  +-------------+  | (mandatory    |  |  daily modes)  |   |     |
|  |                   |  close)       |  +----------------+   |     |
|  |                   +---------------+                       |     |
|  +------------------------------+-----------------------------+     |
|                                 |                                   |
|  +------------------------------v-----------------------------+     |
|  |                  Data & Analytics                          |     |
|  |  +-------------+  +-------------+  +-----------------+    |     |
|  |  |    Data     |  |   Metrics   |  |   Multiplier    |    |     |
|  |  |  Collector  |  |   Tracker   |  |   Calculator    |    |     |
|  |  +-------------+  +-------------+  +-----------------+    |     |
|  +------------------------------------------------------------+     |
|                                                                     |
+--------------------------------------------------------------------+
                              |
                              v
                 +------------------------+
                 |    ApexOmni API        |
                 |  omni.apex.exchange    |
                 +------------------------+
```

---

## 2. Component Design

### 2.1 Entry Points

#### 2.1.1 Trading Daemon (`scripts/run_continuous.py`)

**Primary entry point for Docker deployment.**

**Responsibilities:**
- Run continuous trading loop
- Handle graceful shutdown (SIGTERM/SIGINT)
- Check trade eligibility at intervals
- Maintain last trade timestamp

**Key Classes:**
```python
class TradingDaemon:
    def __init__(self, config: Config, check_interval: int = 300)
    def run(self) -> None  # Main daemon loop
    def _check_and_trade(self) -> None
    def _execute_trade(self, day_number: int) -> None
    def _signal_handler(self, signum, frame) -> None
```

#### 2.1.2 CLI Entry Point (`scripts/run_bot.py`)

**For manual execution and development.**

**Commands:**
- `--status`: Show current trading status
- `--plan`: Show weekly trading plan
- `--live`: Execute live trade
- `--force`: Force trade even if already traded today
- `--verbose`: Enable debug logging

#### 2.1.3 Dry-Run Script (`scripts/dry_run.py`)

**For testing and validation.**

**Commands:**
- Default: Simulate today's trade
- `--all`: Simulate full week
- `--validate`: Validate configuration only

### 2.2 Core Components

#### 2.2.1 API Client (`bot/api_client.py`)

**Responsibilities:**
- Authenticate with ApexOmni API
- Handle HTTP requests/responses
- Manage rate limiting
- Error handling and retries

**Key Classes:**
```python
class ApexOmniClient:
    def __init__(self, config: APIConfig)
    def test_connection(self) -> bool
    def get_account_balance(self) -> AccountBalance
    def get_current_price(self, symbol: str) -> Decimal
    def place_order(self, symbol: str, side: str, order_type: str, size: Decimal) -> OrderResult
    def get_positions(self) -> list[Position]

class MockApexOmniClient:
    """Mock client for dry-run mode and testing."""
```

**Dependencies:**
- `apexomni` SDK (official)
- `requests` for HTTP
- `python-dotenv` for env vars

#### 2.2.2 Trade Executor (`bot/trade_executor.py`)

**Responsibilities:**
- **Automatic symbol selection** via `determine_best_symbol()`
- Execute trades based on strategy
- Validate trade parameters
- **Mandatory position closing** (hardcoded)
- **1x leverage only** (hardcoded)
- Log trade results

**Key Classes:**
```python
class TradeExecutor:
    def __init__(self, client: ApexOmniClient, config: Config)
    def determine_best_symbol(self) -> Optional[tuple[str, Decimal, SymbolConfig]]
    def execute_trade(self, trade: Trade) -> TradeResult
    def validate_trade(self, trade: Trade) -> bool
    def check_balance(self, required: float) -> bool
    def _close_position(self, trade: Trade) -> None  # Always called
```

**Key Method - determine_best_symbol():**
- Analyzes ALL available trading pairs
- Calculates minimum order value for each symbol
- Selects the cheapest tradeable symbol that fits the available balance
- Returns `(symbol_name, min_order_size, symbol_config)` or `None`

**Hardcoded Safety:**
- Leverage is always 1x (cross margin)
- Position is always closed immediately after opening

#### 2.2.3 Circuit Breaker (`bot/circuit_breaker.py`)

**Responsibilities:**
- Halt trading after consecutive failures
- Prevent runaway losses during API outages
- Auto-recover after timeout period

**Key Classes:**
```python
@dataclass
class CircuitBreaker:
    max_failures: int = 5
    reset_timeout_minutes: int = 30

    def can_execute(self) -> Tuple[bool, str]
    def record_success(self) -> None
    def record_failure(self) -> None
    def reset(self) -> None
    def get_status(self) -> dict
```

**States:**
- `CLOSED`: Normal operation, trades allowed
- `OPEN`: Too many failures, trades blocked
- `HALF_OPEN`: Testing if system recovered

**Flow:**
```
Trade Attempt
    |
    v
Circuit Breaker Check
    |
    +-> CLOSED -> Execute Trade -> Success -> Reset counter
    |                    |
    |                    +-> Failure -> Increment counter
    |                                        |
    |                                        +-> If >= max_failures -> OPEN
    |
    +-> OPEN -> Check timeout elapsed?
    |               |
    |               +-> No -> Block trade
    |               +-> Yes -> HALF_OPEN -> Allow test trade
    |
    +-> HALF_OPEN -> Execute Trade
                         |
                         +-> Success -> CLOSED
                         +-> Failure -> OPEN
```

**Configuration:**
- `MAX_FAILURES` env var (default: 5)
- `CIRCUIT_RESET_MINUTES` env var (default: 30)

#### 2.2.4 Strategy (`bot/strategy.py`)

**Responsibilities:**
- Support both `continuous` and `daily` modes
- Optimize for Trading Activity Factor
- Schedule trades across days
- Determine trade eligibility
- Accept symbol/size overrides from pre-selection

**Key Classes:**
```python
class StakingOptimizationStrategy:
    def __init__(self, config: Config)
    def should_trade_now(self, last_trade_time: datetime, unique_days_this_week: int) -> tuple[bool, str]
    def get_trade_for_today(self, day_number: int = None,
                            symbol_override: str = None,
                            size_override: Decimal = None) -> Trade
    def calculate_expected_multiplier(self, days_traded: int) -> float
```

**get_trade_for_today() Parameters:**
- Accepts `symbol_override` and `size_override` parameters
- Used with `determine_best_symbol()` for symbol selection
- Trade is generated with pre-selected symbol

**Schedule Modes:**

**Daily Mode:**
```
Day 1: Trade at 09:00 UTC (Monday)   -> +0.1 Trading Activity Factor
Day 2: Trade at 09:00 UTC (Tuesday)  -> +0.1 Trading Activity Factor
Day 3: Trade at 09:00 UTC (Wednesday)-> +0.1 Trading Activity Factor
Day 4: Trade at 09:00 UTC (Thursday) -> +0.1 Trading Activity Factor
Day 5: Trade at 09:00 UTC (Friday)   -> +0.1 Trading Activity Factor
                                     --------------------------------
Total Trading Activity Factor: 0.5 (Maximum!)
```

**Continuous Mode:**
```
Every 4 hours (default): Check if should trade
- Is it a configured trade day?
- Has enough time passed since last trade?
- Has max factor been reached? (configurable to continue)
```

#### 2.2.5 Config Manager (`bot/config.py`)

**Responsibilities:**
- Load configuration from files/env
- Validate configuration
- Provide defaults

**Configuration Dataclasses:**
```python
@dataclass
class APIConfig:
    api_key: str
    api_secret: str
    passphrase: str
    zk_seeds: str
    zk_l2key: str
    testnet: bool
    network: str

@dataclass
class TradingConfig:
    # NOTE: symbol is auto-selected (cheapest tradeable)
    side: str = "BUY"
    order_type: str = "MARKET"
    # NOTE: leverage and close_position removed (hardcoded)

@dataclass
class SafetyConfig:
    dry_run: bool = True
    max_position_size: Decimal = Decimal("0.01")
    max_daily_trades: int = 10
    min_balance: Decimal = Decimal("50.0")
    require_balance_check: bool = True

@dataclass
class ScheduleConfig:
    mode: str = "daily"  # "daily" or "continuous"
    trade_interval_hours: int = 4
    trade_days: list[int] = [0, 1, 2, 3, 4, 5, 6]  # All 7 days (24/7)
    trade_time: str = "09:00"
    timezone: str = "UTC"
    continue_after_max_factor: bool = True
```

### 2.3 Data Components

#### 2.3.1 Data Collector (`data/collector.py`)

**Responsibilities:**
- Collect trade execution data
- Store trade history
- Track daily trading activity

**Key Classes:**
```python
class DataCollector:
    def __init__(self, storage: Storage)
    def record_trade(self, trade_result: TradeResult)
    def get_weekly_trades(self) -> list[TradeResult]
    def get_days_traded(self) -> int
```

#### 2.3.2 Metrics Tracker (`data/metrics.py`)

**Responsibilities:**
- Track performance metrics
- Calculate success rates
- Monitor trading volume

**Key Classes:**
```python
class MetricsTracker:
    def __init__(self)
    def update(self, trade_result: TradeResult)
    def get_summary(self) -> MetricsSummary
```

#### 2.3.3 Storage (`data/storage.py`)

**Responsibilities:**
- Persist trade history to JSON
- Manage weekly records
- Thread-safe file operations

**Key Classes:**
```python
class Storage:
    def __init__(self, data_dir: str = "data")
    def save_trade(self, trade_result: TradeResult)
    def get_current_weekly_record(self) -> WeeklyTradeRecord
    def get_trade_history(self, limit: int = 100) -> list[TradeResult]
```

#### 2.3.4 Multiplier Calculator (`analytics/multiplier_analysis.py`)

**Responsibilities:**
- Calculate current staking factor
- Project future multiplier
- Optimize trade scheduling

**Key Classes:**
```python
class MultiplierCalculator:
    def __init__(self, staked_amount: float, lock_period_months: int)
    def calculate_time_factor(self) -> float
    def calculate_trading_factor(self, days_traded: int) -> float
    def calculate_total_factor(self) -> float
    def project_weekly_reward(self, pool_size: float) -> float
```

---

## 3. Data Flow

### 3.1 Trade Execution Flow

```
+------------+    +------------+    +-----------+    +------------+    +------------+
|  Trading   |    |  Strategy  |    |  Circuit  |    |  Executor  |    |  ApexOmni  |
|   Daemon   |--->|            |--->|  Breaker  |--->|            |--->|    API     |
+------------+    +------------+    +-----+-----+    +-----+------+    +-----+------+
                                         |                |                  |
                                         | Block if OPEN  | Close Position   |
                                         v                |<-----------------+
                                    +---------+          |
                                    | CLOSED? |          v
                                    |  OPEN?  |   +------------+    +------------+
                                    |HALF_OPEN|   | Collector  |--->|  Metrics   |
                                    +---------+   |            |    |  Tracker   |
                                                  +------------+    +------------+
```

**Circuit Breaker Integration:**
1. Before any trade, check `circuit_breaker.can_execute()`
2. If OPEN, block trade and return early
3. On trade success, call `circuit_breaker.record_success()`
4. On trade failure, call `circuit_breaker.record_failure()`

### 3.2 Continuous Mode Flow

```
1. Daemon Starts
   |-> Load Configuration
   |-> Initialize Components
   |-> Setup Signal Handlers

2. Main Loop (every check_interval seconds)
   |-> Get weekly record from storage
   |-> Calculate unique days traded
   |-> Call strategy.should_trade_now()
   |   |-> Check if trade day
   |   |-> Check time since last trade
   |   |-> Check if max factor reached
   |-> If should trade:
       |-> Call determine_best_symbol() to auto-select cheapest symbol
       |-> Generate trade with auto-selected symbol
       |-> Validate trade parameters
       |-> Execute opening order
       |-> Execute closing order (mandatory)
       |-> Record result
       |-> Update last_trade_time

3. On SIGTERM/SIGINT
   |-> Set running = False
   |-> Complete current operation
   |-> Exit gracefully
```

### 3.3 Daily Mode Flow

```
1. Load Configuration
   |-> Read .env, config/*.yaml

2. Initialize Components
   |-> Create Client, Executor, Strategy

3. Check Pre-conditions
   |-> Verify API connection
   |-> Check account balance
   |-> Validate today is trade day
   |-> Check not already traded today (via bot_state.json)

4. Execute Today's Trade
   |-> Call determine_best_symbol() to auto-select cheapest symbol
   |-> Generate trade with auto-selected symbol
   |-> Validate trade parameters
   |-> Execute (or dry-run)
   |-> Close position (mandatory)
   |-> Record result
   |-> Mark traded today (save to bot_state.json)

5. Update Analytics
   |-> Update metrics
   |-> Calculate new multiplier
   |-> Log summary

6. Cleanup
   |-> Save state, close connections
```

**State Persistence (Daily Mode):**
- Bot tracks whether it traded today in `bot_state.json`
- State survives container restarts
- Prevents duplicate trades when bot restarts during same day

---

## 4. Security Architecture

### 4.1 API Key Management

```
+-------------------------------------+
|           .env File                 |
|  (NEVER committed to git)           |
+-------------------------------------+
|  APEX_API_KEY=xxx                   |
|  APEX_API_SECRET=xxx                |
|  APEX_PASSPHRASE=xxx                |
|  APEX_ZK_SEEDS=xxx                  |
+-------------------------------------+
            |
            v
+-------------------------------------+
|      Environment Variables          |
|   (Loaded by python-dotenv)         |
+-------------------------------------+
            |
            v
+-------------------------------------+
|        API Client                   |
|   (Keys never logged/exposed)       |
+-------------------------------------+
```

### 4.2 Safety Mechanisms

1. **Dry-Run Mode:** Default enabled, simulates trades
2. **Balance Checks:** Verify funds before trading
3. **Position Limits:** Max position size enforced
4. **Mandatory Closing:** Positions always closed (hardcoded)
5. **1x Leverage Only:** Prevents liquidation (hardcoded)
6. **Graceful Shutdown:** Docker handles SIGTERM properly
7. **Rate Limiting:** Respect API limits with retry backoff
8. **Circuit Breaker:** Halts trading after 5 consecutive failures
9. **Mainnet Warning:** 5-second countdown before live mainnet trading
10. **Error Sanitization:** Detailed errors only in DEBUG mode
11. **Order Deduplication:** `client_order_id` prevents duplicate orders

---

## 5. Directory Structure

```
apex_omni_daily_trader/
|-- .env.example              # Template for environment variables
|-- .gitignore                # Excludes .env, __pycache__, etc.
|-- requirements.txt          # Python dependencies
|-- setup.py                  # Package setup
|-- README.md                 # Quick start guide
|-- docker-compose.yml        # Docker orchestration
|
|-- docker/
|   `-- Dockerfile            # Container build instructions
|
|-- bot/                      # Core trading bot
|   |-- __init__.py
|   |-- api_client.py         # ApexOmni API client
|   |-- trade_executor.py     # Trade execution (mandatory close)
|   |-- circuit_breaker.py    # Circuit breaker protection
|   |-- strategy.py           # Continuous/daily mode strategy
|   |-- config.py             # Configuration management
|   `-- utils.py              # Helper utilities
|
|-- data/                     # Data management
|   |-- __init__.py
|   |-- collector.py          # Trade data collection
|   |-- metrics.py            # Performance metrics
|   |-- storage.py            # Data persistence (JSON)
|   |-- models.py             # Data models (Trade, TradeResult)
|   |-- trades.json           # Trade history (runtime)
|   |-- weekly_records.json   # Weekly staking progress (runtime)
|   `-- bot_state.json        # Daily mode state persistence (runtime)
|
|-- analytics/                # Analytics & calculations
|   |-- __init__.py
|   |-- multiplier_analysis.py # Staking multiplier calculations
|   `-- performance.py        # Performance analytics
|
|-- config/                   # Configuration files
|   `-- trading.yaml          # Trading parameters
|
|-- scripts/                  # Entry points
|   |-- run_continuous.py     # 24/7 daemon (Docker default)
|   |-- run_bot.py            # CLI entry point
|   |-- dry_run.py            # Simulation mode
|   |-- derive_zk_seeds.py    # ZK key derivation
|   `-- calculate_multiplier.py # Multiplier calculator
|
|-- tests/                    # Test suite
|   |-- __init__.py
|   |-- conftest.py           # Pytest fixtures
|   |-- test_api_client.py
|   |-- test_strategy.py
|   |-- test_trade_executor.py
|   |-- test_config.py
|   `-- ...
|
`-- docs/                     # Documentation
    |-- ARCHITECTURE.md       # This document
    |-- API.md                # API documentation
    |-- SETUP.md              # Installation guide
    |-- STRATEGY.md           # Trading strategy
    |-- STAKING_OPTIMIZATION.md
    `-- TROUBLESHOOTING.md
```

---

## 6. Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Language | Python | 3.8+ |
| SDK | apexomni | Latest |
| HTTP | requests | 2.28+ |
| Config | python-dotenv, PyYAML | Latest |
| Testing | pytest | 7.0+ |
| Storage | JSON | - |
| Container | Docker | 20.10+ |
| Orchestration | Docker Compose | 2.0+ |

---

## 7. Interface Contracts

### 7.1 Trade Model

```python
@dataclass
class Trade:
    symbol: str          # e.g., "BTC-USDT"
    side: str            # "BUY" or "SELL"
    size: Decimal        # Trade size
    price: Decimal       # Limit price (for zkLink)
    order_type: str      # "MARKET" or "LIMIT"
    day_number: int      # 1-5 (trade day in week)
    # NOTE: leverage removed (hardcoded to 1)

@dataclass
class TradeResult:
    trade: Trade
    success: bool
    order_id: str | None
    executed_price: Decimal | None
    executed_size: Decimal | None
    fees: Decimal
    timestamp: datetime
    error: str | None
```

### 7.2 Configuration Interface

```python
@dataclass
class TradingConfig:
    # NOTE: symbol is auto-selected (cheapest tradeable)
    default_side: str = "BUY"
    order_type: str = "MARKET"
    # leverage: removed (hardcoded to 1)
    # close_position: removed (hardcoded to True)

@dataclass
class SafetyConfig:
    max_position_size: Decimal = Decimal("0.01")
    max_daily_trades: int = 10
    dry_run: bool = True
    require_balance_check: bool = True
    min_balance: Decimal = Decimal("50.0")

@dataclass
class ScheduleConfig:
    mode: str = "daily"  # "daily" or "continuous"
    trade_interval_hours: int = 4
    trade_days: list[int] = [0, 1, 2, 3, 4, 5, 6]  # All 7 days (24/7)
    trade_time: str = "09:00"  # UTC
    timezone: str = "UTC"
    continue_after_max_factor: bool = True
```

---

## 8. Error Handling

### 8.1 Error Categories

| Category | Examples | Handling |
|----------|----------|----------|
| Network | Timeout, DNS failure | Retry with backoff |
| Auth | Invalid API key | Log error, alert user |
| Rate Limit | 403/429 responses | Wait and retry |
| Validation | Invalid params | Reject trade, log |
| Insufficient Funds | Balance too low | Skip trade, alert |
| API Error | Server error | Retry, then fail |

### 8.2 Retry Strategy

```python
RETRY_CONFIG = {
    "max_retries": 3,
    "base_delay": 1.0,  # seconds
    "max_delay": 30.0,
    "exponential_base": 2
}
```

---

## 9. Docker Deployment

### 9.1 Execution Modes

1. **Docker (Recommended):** Run `docker compose up -d`
2. **Manual Daemon:** Run `python scripts/run_continuous.py`
3. **Single Trade:** Run `python scripts/run_bot.py --live`
4. **Dry-Run:** Run `python scripts/dry_run.py`

### 9.2 Docker Configuration

```yaml
# docker-compose.yml
services:
  apex-trader:
    build:
      context: .
      dockerfile: docker/Dockerfile
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "from bot.config import Config; Config.load()"]
      interval: 5m
      timeout: 10s
    volumes:
      - ./data:/app/data      # Persist trade data
      - ./config:/app/config:ro
    stop_grace_period: 30s    # Graceful shutdown
```

### 9.3 Environment Support

| Environment | Base URL | Notes |
|-------------|----------|-------|
| Testnet | testnet.omni.apex.exchange | For development |
| Mainnet | omni.apex.exchange | Production |

### 9.4 Monitoring

- Docker container logs: `docker compose logs -f apex-trader`
- Health checks: `docker inspect apex-daily-trader --format='{{json .State.Health}}'`
- Trade history files in `./data` volume
- Metrics tracking via MetricsTracker

---

## 10. Future Enhancements (Out of Scope)

- Web dashboard for monitoring
- Multi-account support
- Advanced trading strategies
- Real-time WebSocket integration
- Historical backtesting
- Mobile notifications
- Database storage (PostgreSQL)

---

**Architecture Status:** APPROVED
