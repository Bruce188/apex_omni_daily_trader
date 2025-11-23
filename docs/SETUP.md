# ApexOmni Trading Bot - Setup Guide

This guide provides detailed instructions for installing and configuring the ApexOmni Daily Trading Bot.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Docker Setup (Recommended)](#docker-setup-recommended)
3. [Python Setup (Development)](#python-setup-development)
4. [Configuration](#configuration)
5. [Verification](#verification)

---

## Prerequisites

### For Docker Setup (Recommended)

| Requirement | Minimum | Installation |
|-------------|---------|--------------|
| Docker | 20.10+ | https://docs.docker.com/get-docker/ |
| Docker Compose | 2.0+ | Included with Docker Desktop |

**Verify Docker Installation:**

```bash
docker --version
docker compose version
```

### For Python Setup (Development)

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.8+ | 3.10+ |
| pip | Latest | Latest |
| Memory | 100 MB | 256 MB |

**Verify Python Installation:**

```bash
python --version  # Should be 3.8+
pip --version
```

### Required Accounts

1. **ApexOmni Account**
   - Register at https://omni.apex.exchange
   - Complete KYC verification if required
   - Fund account with USDT for trading

2. **Ethereum Wallet** (for initial setup)
   - Required for account registration
   - Used to derive zkKeys

---

## Docker Setup (Recommended)

Docker is the recommended method for production deployment. It provides:

- Consistent environment across systems
- Automatic restarts on failure
- Health monitoring
- Log rotation
- Easy updates

### Step 1: Clone the Repository

```bash
# Navigate to your preferred directory
cd ~

# Clone the repository
git clone <repository-url> apex_omni_daily_trader
cd apex_omni_daily_trader
```

### Step 2: Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Set restrictive permissions (security)
chmod 600 .env

# Edit with your credentials
nano .env  # or your preferred editor
```

Add your API credentials:

```bash
# API Credentials
APEX_API_KEY=your_api_key_here
APEX_API_SECRET=your_api_secret_here
APEX_PASSPHRASE=your_passphrase_here

# ZK Keys (required for trading)
APEX_ZK_SEEDS=your_zk_seeds_here
APEX_ZK_L2KEY=  # Can be left empty

# Network (start with testnet!)
APEX_NETWORK=testnet

# Safety (start with dry-run!)
DRY_RUN=true

# Schedule (continuous is recommended for Docker)
SCHEDULE_MODE=continuous
TRADE_INTERVAL_HOURS=4
```

### Step 3: Build and Start

```bash
# Build the Docker image
docker compose build

# Start the bot in detached mode
docker compose up -d

# Verify it's running
docker compose ps
```

Expected output:
```
NAME                 SERVICE       STATUS       PORTS
apex-daily-trader    apex-trader   Up (healthy)
```

### Step 4: Monitor the Bot

```bash
# View live logs
docker compose logs -f apex-trader

# View recent logs
docker compose logs --tail=100 apex-trader

# Check health status
docker inspect apex-daily-trader --format='{{.State.Health.Status}}'
```

### Step 5: Stop/Restart

```bash
# Stop gracefully
docker compose down

# Restart
docker compose restart apex-trader

# Rebuild and restart (after code changes)
docker compose up -d --build
```

### Docker Troubleshooting

**Container won't start:**
```bash
# Check logs for errors
docker compose logs apex-trader

# Verify configuration
docker compose config

# Check environment variables
docker compose exec apex-trader env | grep APEX
```

**Health check failing:**
```bash
# View health check output
docker inspect apex-daily-trader --format='{{range .State.Health.Log}}{{.Output}}{{end}}'
```

**Permission issues:**
```bash
# Ensure data directory is writable
sudo chown -R $(id -u):$(id -g) data/
```

---

## Python Setup (Development)

Use Python directly for development, testing, or debugging. For production, use Docker.

### Step 1: Clone the Repository

```bash
cd ~
git clone <repository-url> apex_omni_daily_trader
cd apex_omni_daily_trader
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate

# On Windows (Command Prompt):
venv\Scripts\activate.bat

# On Windows (PowerShell):
venv\Scripts\Activate.ps1
```

You should see `(venv)` in your terminal prompt when activated.

### Step 3: Install Dependencies

```bash
# Upgrade pip first
pip install --upgrade pip

# Install required packages
pip install -r requirements.txt
```

### Step 4: Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Set restrictive permissions (security)
chmod 600 .env

# Edit with your credentials
nano .env
```

### Step 5: Verify Installation

```bash
# Check if SDK is installed
python -c "import apexomni; print('SDK installed successfully')"

# Run validation
python scripts/dry_run.py --validate
```

---

## Configuration

### API Key Generation

#### Step 1: Access Key Management

1. Log in to ApexOmni
   - **Mainnet**: https://omni.apex.exchange
   - **Testnet**: https://testnet.omni.apex.exchange

2. Navigate to **Key Management**
   - Click on your profile/settings
   - Select "API Key Management" or "Key Management"

#### Step 2: Create API Key

1. Click **Create API Key** or **New Key**

2. Set permissions:
   - **Trading**: Enable (required)
   - **Read**: Enable (required)
   - **Withdrawal**: Disable (not needed)

3. Set a **Passphrase**
   - Choose a strong, memorable passphrase
   - **Important**: Store this securely - it cannot be recovered

4. Complete verification (2FA if enabled)

5. **Save your credentials immediately**:
   - API Key
   - Secret Key
   - Passphrase (you set this)

#### Step 3: Get ZK Seeds

The ZK Seeds are required for signing orders on the zkLink layer.

1. In Key Management, find your API key
2. Click **Omni Key** or **ZK Key** button
3. Copy the **Seeds** value
4. Optionally copy the **L2 Key** (can be left empty)

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `APEX_API_KEY` | Yes | Your ApexOmni API key | - |
| `APEX_API_SECRET` | Yes | Your API secret | - |
| `APEX_PASSPHRASE` | Yes | Your API passphrase | - |
| `APEX_ZK_SEEDS` | Yes | ZK seeds for order signing | - |
| `APEX_ZK_L2KEY` | No | ZK L2 key | Derived from seeds |
| `APEX_NETWORK` | No | `testnet` or `mainnet` | `testnet` |
| `DRY_RUN` | No | Force dry-run mode | `true` |
| `LOG_LEVEL` | No | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |
| `SCHEDULE_MODE` | No | `daily` or `continuous` | `daily` |
| `TRADE_INTERVAL_HOURS` | No | Hours between trades (continuous mode) | `4` |

### Trading Configuration (config/trading.yaml)

```yaml
# Trading Parameters
trading:
  # SYMBOL SELECTION IS AUTOMATIC
  # The bot analyzes ALL available trading pairs, calculates the minimum
  # order value for each, and selects the cheapest tradeable symbol.
  # No manual symbol configuration is needed.
  side: "BUY"           # Order side (BUY or SELL)
  type: "MARKET"        # Order type (MARKET recommended)

# NOTE: The following are HARDCODED and cannot be changed:
# - Leverage: Always 1x (cross margin)
# - Position Closing: Always immediate

# Schedule Configuration
schedule:
  mode: "continuous"    # "daily" or "continuous"
  trade_interval_hours: 4
  trade_days:
    - 0  # Monday
    - 1  # Tuesday
    - 2  # Wednesday
    - 3  # Thursday
    - 4  # Friday
    - 5  # Saturday
    - 6  # Sunday
  trade_time: "09:00"   # For daily mode (UTC)
  continue_after_max_factor: true

# Safety Configuration
safety:
  dry_run: true         # ALWAYS start with true!
  max_position_size: 0.01
  min_balance: 50
  require_balance_check: true
```

### Configuration Priority

Configuration is loaded with the following precedence (highest to lowest):

1. Environment variables (`.env`)
2. YAML config file (`config/trading.yaml`)
3. Default values

---

## Security Configuration

### Error Message Detail Level

By default, error messages are sanitized in production (mainnet). To see full error details:

```bash
# In .env or docker-compose.yml
DEBUG=true
```

### Circuit Breaker Settings

```bash
# Maximum consecutive failures before halting (default: 5)
MAX_FAILURES=5

# Minutes to wait before attempting recovery (default: 30)
CIRCUIT_RESET_MINUTES=30
```

### Mainnet Warning

When running live on mainnet, you will see a 5-second warning countdown. Press Ctrl+C to abort if needed. This safety feature only appears when:
- `DRY_RUN=false` AND
- `APEX_NETWORK=mainnet`

---

## Verification

### Step 1: Validate Configuration

**Docker:**
```bash
docker compose exec apex-trader python scripts/dry_run.py --validate
```

**Python:**
```bash
python scripts/dry_run.py --validate
```

Expected output:
```
Configuration is valid!
...configuration summary...
```

### Step 2: Test on Testnet

**Always test on testnet before mainnet!**

1. Ensure your `.env` has:
   ```bash
   APEX_NETWORK=testnet
   DRY_RUN=true
   ```

2. Get testnet funds:
   - Visit https://testnet.omni.apex.exchange
   - Use faucet or testnet deposit

3. Run dry-run simulation:
   ```bash
   # Docker
   docker compose exec apex-trader python scripts/dry_run.py

   # Python
   python scripts/dry_run.py
   ```

### Step 3: Execute Test Trade (Testnet)

**Docker:**
```bash
# Change DRY_RUN to false in .env, then:
docker compose restart apex-trader
docker compose logs -f apex-trader
```

**Python:**
```bash
python scripts/run_bot.py --live --verbose
```

Verify:
- Connection successful
- Trade executed
- Position closed (always happens automatically)

### Step 4: Check Status

**Docker:**
```bash
docker compose exec apex-trader python scripts/run_bot.py --status
```

**Python:**
```bash
python scripts/run_bot.py --status
```

This shows:
- Current week period
- Days traded
- Trading Activity Factor
- Next scheduled trade

### Step 5: Enable Mainnet (When Ready)

Once testnet is verified:

1. Generate **new** API keys for mainnet (don't reuse testnet keys)

2. Update `.env`:
   ```bash
   APEX_NETWORK=mainnet
   APEX_API_KEY=your_mainnet_key
   APEX_API_SECRET=your_mainnet_secret
   APEX_PASSPHRASE=your_mainnet_passphrase
   APEX_ZK_SEEDS=your_mainnet_seeds
   ```

3. Test with dry-run first:
   ```bash
   # Docker
   docker compose restart apex-trader
   docker compose logs --tail=20 apex-trader

   # Python
   python scripts/dry_run.py
   ```

4. Enable live trading:
   ```bash
   # Update .env
   DRY_RUN=false

   # Docker
   docker compose restart apex-trader

   # Python
   python scripts/run_bot.py --live
   ```

---

## Quick Start Checklist

### Docker

- [ ] Docker and Docker Compose installed
- [ ] Repository cloned
- [ ] `.env` file created with credentials
- [ ] API key has trading permission
- [ ] ZK seeds obtained and configured
- [ ] `docker compose up -d --build` successful
- [ ] Health check passing
- [ ] Testnet dry-run working
- [ ] Testnet live trade successful
- [ ] Mainnet enabled (when ready)

### Python (Development)

- [ ] Python 3.8+ installed
- [ ] Virtual environment created and activated
- [ ] Dependencies installed
- [ ] `.env` file created with credentials
- [ ] Configuration validated
- [ ] Testnet dry-run working
- [ ] Testnet live trade successful

---

## Next Steps

1. **Read the Strategy Guide**: [STRATEGY.md](STRATEGY.md)
2. **Understand the Staking System**: [STAKING_OPTIMIZATION.md](STAKING_OPTIMIZATION.md)
3. **Review Troubleshooting**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
