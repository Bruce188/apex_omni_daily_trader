# Troubleshooting Guide

This document covers common issues and solutions when using the ApexOmni Daily Trading Bot.

## Table of Contents

1. [Critical SDK Issues](#critical-sdk-issues) **START HERE**
2. [Docker Issues](#docker-issues)
3. [Installation Issues](#installation-issues)
4. [Configuration Errors](#configuration-errors)
5. [API Connection Problems](#api-connection-problems)
6. [Authentication Failures](#authentication-failures)
7. [Trading Errors](#trading-errors)
8. [Circuit Breaker Issues](#circuit-breaker-issues)
9. [Error Messages](#error-messages)
10. [Scheduling Issues](#scheduling-issues)
11. [Dry-Run Mode Issues](#dry-run-mode-issues)
12. [Logging and Debugging](#logging-and-debugging)

---

## Critical SDK Issues

**READ THIS SECTION FIRST** - These are the most common causes of order failures that appear as "insufficient margin" errors even when you have sufficient balance.

### SDK Initialization Failure (MOST COMMON)

**Symptom:**
```
API Error: insufficient margin
API Error: Margin insufficient for new order
```

Even when your account balance is clearly sufficient for the trade.

**Root Cause:**
The ApexOmni SDK v3 requires calling BOTH `configs_v3()` AND `get_account_v3()` BEFORE placing any orders. Without this initialization:
- The SDK lacks internal state (`configV3` and `accountV3`) needed for zkLink signature generation
- Orders fail with cryptic "insufficient margin" errors
- The actual margin calculation never happens because signing fails first

**Technical Details:**
```python
# The SDK internally requires these to be set:
# self.configV3 - Set by configs_v3()
# self.accountV3 - Set by get_account_v3()

# When create_order_v3() is called without these:
# 1. zkLink signature generation fails
# 2. API receives malformed request
# 3. Returns generic "insufficient margin" error
```

**Solution:**
The bot automatically handles this via `_ensure_sdk_initialized()` in `bot/api_client.py`:
```python
def _ensure_sdk_initialized(self) -> bool:
    """
    Ensure the SDK client has configV3 and accountV3 set.
    MUST be called before any order placement.
    """
    if self._sdk_initialized:
        return True

    # Call configs_v3() to set configV3
    configs = client.configs_v3()

    # Call get_account_v3() to set accountV3
    account = client.get_account_v3()

    self._sdk_initialized = True
    return True
```

**Verification:**
```bash
# Test if SDK initializes correctly
DEBUG=true python -c "
from bot.api_client import create_client
from bot.config import Config
config = Config.load()
client = create_client(config.api, dry_run=False)
if client.test_connection():
    print('SDK initialized successfully')
    balance = client.get_account_balance()
    print(f'Balance: {balance.available_balance} USDT')
"
```

### Symbol Not Tradeable

**Symptom:**
```
API Error: insufficient margin
API Error: Symbol not available for trading
```

Or orders fail even for symbols that appear in the symbol list.

**Root Cause:**
Many symbols on ApexOmni have trading disabled via flags:
- `enableOpenPosition: false` - Cannot open new positions
- `enableTrade: false` - Trading disabled entirely

**Technical Details:**
```python
# Example symbol configuration from API:
{
    "symbol": "SOME-USDT",
    "enableOpenPosition": false,  # <-- Cannot open positions!
    "enableTrade": true,
    "minOrderSize": "1",
    ...
}
```

**Solution:**
The bot filters symbols automatically:
```python
def get_all_symbols(self, tradeable_only: bool = True) -> list[SymbolConfig]:
    """
    Args:
        tradeable_only: If True, only return symbols where
                       enableOpenPosition=True AND enableTrade=True
    """
    for contract in perpetuals:
        enable_open = contract.get('enableOpenPosition', True)
        enable_trade = contract.get('enableTrade', True)

        if tradeable_only and (not enable_open or not enable_trade):
            skipped_disabled += 1
            continue
```

**Verification:**
```bash
# List all tradeable symbols
python -c "
from bot.api_client import create_client
from bot.config import Config
config = Config.load()
client = create_client(config.api, dry_run=False)
client.test_connection()

all_symbols = client.get_all_symbols(tradeable_only=False)
tradeable = client.get_all_symbols(tradeable_only=True)

print(f'Total symbols: {len(all_symbols)}')
print(f'Tradeable symbols: {len(tradeable)}')
print(f'Disabled symbols: {len(all_symbols) - len(tradeable)}')

print('\nTradeable symbols:')
for s in tradeable:
    print(f'  - {s.symbol}')
"
```

### Response Parsing Errors

**Symptom:**
```
TypeError: 'NoneType' object is not subscriptable
KeyError: 'data'
```

**Root Cause:**
The SDK API responses have varying formats:
- Some return `{'data': {...}}`
- Some return `{'data': [...]}`
- Some return lists directly `[...]`
- Error responses have `{'code': 3, 'message': '...'}`

**Solution:**
The bot handles all response formats:
```python
# Handle various API response formats
if response is None:
    return []

# If response is already a list, return it directly
if isinstance(response, list):
    return response

# If response is a dict with 'data' key
if isinstance(response, dict):
    data = response.get('data')
    if isinstance(data, list):
        return data
```

### clientOrderId Not Supported

**Symptom:**
```
TypeError: create_order_v3() got an unexpected keyword argument 'clientOrderId'
```

**Root Cause:**
The SDK's `create_order_v3()` method does not support the `clientOrderId` parameter, even though the API documentation mentions it.

**Solution:**
The bot no longer passes `clientOrderId` to the SDK:
```python
# Note: clientOrderId is NOT supported by SDK v3's create_order_v3()
order_params = {
    "symbol": symbol,
    "side": side.upper(),
    "type": order_type.upper(),
    "size": str(size),
    "price": str(price),
    "timestampSeconds": int(time.time()),
}

# Log client_order_id for our tracking but don't pass to SDK
if client_order_id:
    self.logger.debug(f"Internal order tracking ID: {client_order_id}")
```

### Empty String Parsing

**Symptom:**
```
decimal.InvalidOperation: [<class 'decimal.ConversionSyntax'>]
```

**Root Cause:**
Some API responses return empty strings `""` instead of `"0"` for numeric fields.

**Solution:**
The `parse_decimal()` utility handles empty strings:
```python
def parse_decimal(value: Any) -> Decimal:
    """Parse a value to Decimal, handling empty strings."""
    if value is None or value == "":
        return Decimal("0")
    return Decimal(str(value))
```

---

## Docker Issues

### Container Won't Start

**Symptom:** Container exits immediately or keeps restarting

**Diagnosis:**
```bash
# Check container status
docker compose ps

# View logs
docker compose logs apex-trader

# Check configuration
docker compose config
```

**Common Causes:**

1. **Missing .env file:**
   ```bash
   cp .env.example .env
   nano .env  # Add your credentials
   ```

2. **Invalid credentials:**
   - Check API key format in .env
   - Ensure no extra spaces or quotes

3. **Configuration syntax error:**
   ```bash
   # Validate config
   docker compose exec apex-trader python scripts/dry_run.py --validate
   ```

### Health Check Failing

**Symptom:**
```
NAME                 STATUS
apex-daily-trader    Up (unhealthy)
```

**Diagnosis:**
```bash
# View health check output
docker inspect apex-daily-trader --format='{{range .State.Health.Log}}{{.Output}}{{end}}'

# Check detailed health status
docker inspect apex-daily-trader --format='{{json .State.Health}}' | jq
```

**Common Causes:**

1. **Config load failure:**
   - Missing required environment variables
   - Invalid YAML syntax in config/trading.yaml

2. **Python import error:**
   - Rebuild the container: `docker compose up -d --build`

### Container Logs Issues

**View logs:**
```bash
# Live streaming
docker compose logs -f apex-trader

# Last 100 lines
docker compose logs --tail=100 apex-trader

# Search for errors
docker compose logs apex-trader 2>&1 | grep -i error

# Since a specific time
docker compose logs --since="1h" apex-trader
```

**Log rotation:**
The docker-compose.yml includes log rotation. If logs are too large:
```bash
# Prune old logs
docker system prune --volumes
```

### Data Persistence Issues

**Symptom:** Trade history lost after container restart

**Cause:** Volume not properly mounted

**Solution:**
```bash
# Check volumes
docker compose config | grep -A5 volumes

# Ensure data directory exists
mkdir -p data

# Verify permissions
ls -la data/

# Fix permissions if needed
sudo chown -R $(id -u):$(id -g) data/
```

### Graceful Shutdown

**Proper shutdown:**
```bash
# Graceful (waits up to 30 seconds)
docker compose down

# Force stop (immediate)
docker compose kill
```

**Verify clean shutdown:**
```bash
docker compose logs --tail=20 apex-trader
# Should show: "Trading daemon stopped."
```

### Rebuilding After Code Changes

```bash
# Rebuild and restart
docker compose up -d --build

# Force rebuild without cache
docker compose build --no-cache
docker compose up -d
```

### Permission Denied

**Symptom:**
```
PermissionError: [Errno 13] Permission denied: '/app/data/trades.json'
```

**Solution:**
```bash
# Fix data directory permissions
sudo chown -R $(id -u):$(id -g) data/
chmod 755 data/
```

### Network Issues in Container

**Symptom:** Container can't reach ApexOmni API

**Diagnosis:**
```bash
# Enter container shell
docker compose exec apex-trader /bin/sh

# Test connectivity
ping -c 3 omni.apex.exchange

# Test HTTPS
wget -q -O- https://omni.apex.exchange/api/v3/time
```

**Solution:**
- Check Docker network settings
- Verify firewall allows outbound HTTPS
- Try restarting Docker daemon

---

## Installation Issues

### Python Version Error

**Symptom:**
```
SyntaxError: invalid syntax
```
or
```
ModuleNotFoundError: No module named 'dataclasses'
```

**Cause:** Python version too old (requires 3.8+)

**Solution:**
```bash
# Check Python version
python --version

# If below 3.8, install newer Python
# Ubuntu/Debian:
sudo apt install python3.10

# Use specific version
python3.10 -m venv venv
```

### SDK Installation Failed

**Symptom:**
```
ERROR: Could not find a version that satisfies the requirement apexomni
```

**Cause:** PyPI package name or network issue

**Solution:**
```bash
# Upgrade pip first
pip install --upgrade pip

# Try installing directly
pip install apexomni

# If still failing, try from source
pip install git+https://github.com/ApeX-Protocol/apexpro-openapi.git
```

### Virtual Environment Issues

**Symptom:**
```
-bash: venv/bin/activate: No such file or directory
```

**Cause:** Virtual environment not created or corrupted

**Solution:**
```bash
# Remove old venv
rm -rf venv

# Create new venv
python -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

### Permission Denied

**Symptom:**
```
PermissionError: [Errno 13] Permission denied
```

**Cause:** File permissions issue

**Solution:**
```bash
# Fix script permissions
chmod +x scripts/*.py

# Fix .env permissions (security)
chmod 600 .env
```

---

## Configuration Errors

### Missing .env File

**Symptom:**
```
FileNotFoundError: [Errno 2] No such file or directory: '.env'
```
or
```
Config error: APEX_API_KEY not set
```

**Cause:** .env file not created

**Solution:**
```bash
# Copy example file
cp .env.example .env

# Edit with your credentials
nano .env
```

### Invalid Credentials Format

**Symptom:**
```
Config error: Invalid API key format
```

**Cause:** Credentials copied with extra spaces or quotes

**Solution:**
Ensure .env has clean values:
```bash
# Wrong
APEX_API_KEY="abc123"
APEX_API_KEY= abc123

# Correct
APEX_API_KEY=abc123
```

### YAML Configuration Error

**Symptom:**
```
yaml.scanner.ScannerError: while scanning a simple key
```

**Cause:** Invalid YAML syntax in config file

**Solution:**
Check `config/trading.yaml`:
```yaml
# Wrong - missing space after colon
trading:side: "BUY"

# Wrong - inconsistent indentation
trading:
  side: "BUY"
   type: "MARKET"

# Correct
trading:
  side: "BUY"
  type: "MARKET"
```

### Missing Required Fields

**Symptom:**
```
Config error: Missing required field
```

**Cause:** Configuration file incomplete

**Solution:**
Ensure all required fields are present:
```yaml
trading:
  # Symbol selection is AUTOMATIC - the bot picks the cheapest tradeable symbol
  side: "BUY"
  type: "MARKET"
  # NOTE: leverage and close_position are hardcoded (not configurable)

schedule:
  mode: "continuous"  # or "daily"
  trade_interval_hours: 4
  trade_days: [0, 1, 2, 3, 4, 5, 6]  # All 7 days (24/7 trading)
  trade_time: "09:00"  # For daily mode

safety:
  dry_run: true
  max_position_size: 0.01
  min_balance: 50
```

---

## API Connection Problems

### Connection Refused

**Symptom:**
```
ConnectionError: HTTPSConnectionPool... Connection refused
```

**Cause:** Network issue or ApexOmni API down

**Solution:**
1. Check internet connection:
   ```bash
   ping omni.apex.exchange
   ```

2. Check if API is accessible:
   ```bash
   curl https://omni.apex.exchange/api/v3/time
   ```

3. Check firewall settings
4. Try again later if API is down

### Timeout Error

**Symptom:**
```
ReadTimeout: HTTPSConnectionPool... Read timed out
```

**Cause:** Slow network or API response

**Solution:**
```bash
# Run with verbose logging
python scripts/run_bot.py --verbose

# If persistent, check network
traceroute omni.apex.exchange
```

### SSL Certificate Error

**Symptom:**
```
SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Cause:** SSL certificate issue or outdated Python

**Solution:**
```bash
# Update certificates
pip install --upgrade certifi

# If on macOS
/Applications/Python\ 3.x/Install\ Certificates.command
```

### DNS Resolution Failed

**Symptom:**
```
socket.gaierror: [Errno -2] Name or service not known
```

**Cause:** DNS issue

**Solution:**
1. Check DNS:
   ```bash
   nslookup omni.apex.exchange
   ```

2. Try using IP directly (not recommended long-term)
3. Change DNS servers to 8.8.8.8 or 1.1.1.1

---

## Authentication Failures

### Invalid API Key

**Symptom:**
```
API Error: Invalid API key
```
or HTTP 401 response

**Cause:** Wrong API key or key not activated

**Solution:**
1. Verify API key in .env matches exactly
2. Regenerate API key on ApexOmni
3. Ensure no extra spaces in .env

### Invalid Signature

**Symptom:**
```
API Error: Invalid signature
```

**Cause:** Wrong secret or timestamp issue

**Solution:**
1. Check secret key is correct
2. Verify system time is accurate:
   ```bash
   date -u
   # Should match UTC time

   # Sync time (Linux)
   sudo ntpdate pool.ntp.org
   ```

3. Regenerate credentials if problem persists

### Invalid Passphrase

**Symptom:**
```
API Error: Invalid passphrase
```

**Cause:** Wrong passphrase

**Solution:**
1. Passphrase is case-sensitive
2. If forgotten, delete API key and create new one

### ZK Keys Error

**Symptom:**
```
API Error: Invalid zkKeys signature
```
or
```
Error: zk_seeds required for order signing
```

**Cause:** Missing or invalid ZK seeds

**Solution:**
1. Get ZK seeds from ApexOmni Key Management
2. Click "Omni Key" or "ZK Key" button
3. Copy seeds to .env:
   ```bash
   APEX_ZK_SEEDS=your_seeds_here
   ```

### Rate Limited

**Symptom:**
```
HTTP 403: Rate limit exceeded
```

**Cause:** Too many API requests

**Solution:**
1. Wait a few minutes
2. The bot has built-in retry with backoff
3. Don't run multiple bot instances

---

## Trading Errors

### Insufficient Balance / Margin

**Symptom:**
```
API Error: Insufficient balance
API Error: insufficient margin
Balance check failed: Insufficient balance
```

**Important:** "Insufficient margin" errors can have TWO different causes:
1. **SDK Not Initialized** - See [Critical SDK Issues](#critical-sdk-issues) above
2. **Actual Insufficient Balance** - Covered here

**Understanding Margin Requirements:**

The bot checks that your balance meets the minimum order value for the symbol:
- Each symbol has a minimum order size (e.g., 1 LINEA, 0.001 BTC)
- The minimum order value = min_order_size x current_price

**Example:**
- Trade value: $0.0093 (1.0 LINEA @ $0.0093)
- Balance: $2.01
- Result: Trade will succeed (balance > min order value)

**Solutions:**

1. **Check your actual balance:**
   ```bash
   python -c "
   from bot.api_client import create_client
   from bot.config import Config
   config = Config.load()
   client = create_client(config.api, dry_run=False)
   client.test_connection()
   balance = client.get_account_balance()
   print(f'Available: \${balance.available_balance}')
   print(f'Total Equity: \${balance.total_equity}')
   print(f'Margin Balance: \${balance.margin_balance}')
   "
   ```

2. **Check minimum tradeable amount:**
   ```bash
   python -c "
   from bot.api_client import create_client
   from bot.config import Config
   config = Config.load()
   client = create_client(config.api, dry_run=False)
   client.test_connection()

   symbols = client.get_all_symbols(tradeable_only=True)
   cheapest = None
   cheapest_value = float('inf')

   for s in symbols:
       price = client.get_current_price(s.symbol)
       if price:
           value = float(s.min_order_size) * float(price)
           if value < cheapest_value:
               cheapest_value = value
               cheapest = (s.symbol, s.min_order_size, price, value)

   if cheapest:
       print(f'Cheapest symbol: {cheapest[0]}')
       print(f'Min order: {cheapest[1]} @ \${cheapest[2]:.6f} = \${cheapest[3]:.4f}')
   "
   ```

3. **Deposit more USDT** if balance is insufficient

4. **Ensure margin is available** (not locked in open positions)

### Invalid Symbol

**Symptom:**
```
API Error: Invalid symbol
```

**Cause:** Trading pair doesn't exist or wrong format

**Solution:**
1. The bot automatically selects the cheapest tradeable symbol
2. If you see this error, it may indicate an API issue or symbol list change
3. Check the logs for which symbol was auto-selected
4. Verify the symbol exists on ApexOmni (correct format: `BTC-USDT` not `BTCUSDT`)

### Order Size Too Small

**Symptom:**
```
API Error: Order size below minimum
```

**Cause:** Trade size below minimum

**Solution:**
1. Check minimum order size:
   ```bash
   python -c "from bot.api_client import *; print('Check API for min sizes')"
   ```

2. Increase size in config:
   ```yaml
   trading:
     size: 0.001  # Must be >= minimum
   ```

### Price Parameter Required

**Symptom:**
```
API Error: Price required for order
```

**Cause:** Market orders on ApexOmni still require price

**Solution:**
This is handled automatically by the bot. If seeing this error:
1. Check API client code is up to date
2. The bot should fetch current price automatically

### Order Rejected

**Symptom:**
```
API Error: Order rejected
```

**Cause:** Various validation failures

**Solution:**
1. Enable verbose logging:
   ```bash
   python scripts/run_bot.py --live --verbose
   ```

2. Check the specific error message
3. Verify all order parameters are valid

---

## Circuit Breaker Issues

### Trading Halted - Circuit Breaker Open

**Symptom:**
- Trades are blocked
- Logs show "Circuit breaker OPEN"

**Cause:**
5 or more consecutive trade failures triggered the circuit breaker.

**Solutions:**
1. Wait 30 minutes for automatic reset
2. Check API connectivity
3. Verify account balance and permissions
4. Check ApexOmni service status
5. Review logs for root cause of failures

**Check Circuit Breaker Status:**
```bash
# Docker
docker compose logs --tail=50 apex-trader | grep -i "circuit"

# Python
python -c "from bot.circuit_breaker import CircuitBreaker; cb = CircuitBreaker(); print(cb.get_status())"
```

### Manual Circuit Breaker Reset

If you need to force a reset (Docker):
```bash
docker compose restart apex-trader
```

The circuit breaker resets on container restart.

### Adjusting Circuit Breaker Thresholds

If you need different thresholds, update your `.env`:
```bash
# Increase failure tolerance
MAX_FAILURES=10

# Decrease recovery wait time
CIRCUIT_RESET_MINUTES=15
```

---

## Error Messages

### "Enable DEBUG=true for details"

**Symptom:**
Error messages show generic text with suggestion to enable DEBUG mode.

**Cause:**
Error messages are sanitized in production mode to prevent information leakage.

**Solution:**
Add `DEBUG=true` to your environment to see full error details:

```bash
# Docker
docker compose down
# Add DEBUG=true to .env file, then:
docker compose up -d

# Manual
DEBUG=true python scripts/run_bot.py --live
```

### Generic Error Messages in Logs

**Symptom:**
Log entries show sanitized errors like "Trade execution failed. Check configuration."

**Cause:**
Production mode sanitizes error messages for security.

**Solution:**
Temporarily enable debug mode for troubleshooting:
```bash
# In .env
DEBUG=true
LOG_LEVEL=DEBUG
```

Remember to disable DEBUG mode after troubleshooting on mainnet.

---

## Scheduling Issues

### Cron Not Running

**Symptom:** Bot doesn't execute at scheduled time

**Cause:** Cron misconfigured

**Solution:**
1. Check cron is running:
   ```bash
   systemctl status cron
   ```

2. Verify cron entry:
   ```bash
   crontab -l
   ```

3. Check cron logs:
   ```bash
   grep CRON /var/log/syslog
   ```

4. Use absolute paths in cron:
   ```
   0 9 * * 1-5 /usr/bin/python3 /full/path/to/scripts/run_bot.py --live
   ```

### Wrong Timezone

**Symptom:** Trades execute at wrong time

**Cause:** System timezone not UTC

**Solution:**
1. Check system timezone:
   ```bash
   date
   timedatectl
   ```

2. Adjust cron time for your timezone
3. Or set timezone in cron:
   ```
   TZ=UTC
   0 9 * * 1-5 python scripts/run_bot.py --live
   ```

### Already Traded Today

**Symptom:**
```
Already traded today. Use --force to trade again.
```

**Cause:** Bot already executed today's trade

**Understanding State Persistence (Daily Mode):**

The bot tracks whether it has traded today in `bot_state.json`. This state:
- Survives container restarts and system reboots
- Prevents duplicate trades when bot restarts during the same day
- Resets automatically at midnight UTC

**State file location:**
```
data/bot_state.json
```

**State file contents:**
```json
{
  "last_trade_date": "2025-11-22",
  "traded_today": true
}
```

**Solutions:**

1. **This is normal** - prevents duplicate trades
2. **Use `--force` only if you need to retry** (e.g., after a failed trade):
   ```bash
   python scripts/run_bot.py --live --force
   ```
3. **Manually reset state** (if needed):
   ```bash
   # Delete state file to force fresh start
   rm data/bot_state.json
   ```
4. **Docker - check state file**:
   ```bash
   docker compose exec apex-trader cat /app/data/bot_state.json
   ```

### Not a Trade Day

**Symptom:**
```
No trade scheduled for today.
```

**Cause:** Today not in configured trade days

**Solution:**
1. Check configured days:
   ```yaml
   schedule:
     trade_days: [0, 1, 2, 3, 4, 5, 6]  # All 7 days (24/7 trading)
   ```

2. Day mapping: 0=Monday, 6=Sunday

---

## Dry-Run Mode Issues

### Unexpected Dry-Run

**Symptom:** Bot says "DRY-RUN" when you want live trading

**Cause:** Dry-run enabled by default or in config

**Solution:**
1. Explicitly enable live mode:
   ```bash
   python scripts/run_bot.py --live
   ```

2. Check config file:
   ```yaml
   safety:
     dry_run: false  # Must be false for live
   ```

3. Check .env:
   ```bash
   # Remove or set to false
   DRY_RUN=false
   ```

### Mock Client Being Used

**Symptom:** Logs show "[DRY-RUN]" prefix

**Cause:** MockApexOmniClient being used instead of real client

**Solution:**
This is expected behavior in dry-run mode. For live trading:
```bash
python scripts/run_bot.py --live
```

---

## Logging and Debugging

### Enable Verbose Logging

**Docker:**
```bash
# Set in .env
LOG_LEVEL=DEBUG

# Restart container
docker compose restart apex-trader

# View logs
docker compose logs -f apex-trader
```

**Python:**
```bash
# Command line
python scripts/run_bot.py --verbose

# Or in .env
LOG_LEVEL=DEBUG
```

### Check Log Files

**Docker:**
```bash
# View live logs
docker compose logs -f apex-trader

# Last 100 lines
docker compose logs --tail=100 apex-trader

# Search for errors
docker compose logs apex-trader 2>&1 | grep -i error

# Since a specific time
docker compose logs --since="1h" apex-trader
```

**Python:**
```bash
# View recent logs
tail -f logs/bot.log

# Search for errors
grep ERROR logs/bot.log

# Search for specific date
grep "2025-11-21" logs/bot.log
```

### Debug API Responses

Add to your script:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Common Log Messages

| Message | Meaning |
|---------|---------|
| "API connection test successful" | Connection OK |
| "DRY-RUN MODE" | Not executing real trades |
| "LIVE TRADING MODE" | Real trades will execute |
| "Already traded today" | Duplicate prevention |
| "Trade completed successfully" | Order filled |

---

## Error Code Reference

### HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Continue |
| 400 | Bad request | Check parameters |
| 401 | Unauthorized | Check credentials |
| 403 | Forbidden/Rate limited | Wait and retry |
| 404 | Not found | Check endpoint |
| 500 | Server error | Retry later |

### Common API Error Codes

| Error | Meaning | Solution |
|-------|---------|----------|
| INVALID_API_KEY | Bad API key | Regenerate key |
| INVALID_SIGNATURE | Signature failed | Check secret, sync time |
| INSUFFICIENT_BALANCE | Low balance | Deposit funds |
| INVALID_SYMBOL | Unknown pair | Use correct format |
| ORDER_SIZE_TOO_SMALL | Below minimum | Increase size |
| RATE_LIMITED | Too many requests | Wait and retry |

---

## Getting Help

### Self-Diagnosis Steps

**Docker:**
1. Check container status:
   ```bash
   docker compose ps
   docker inspect apex-daily-trader --format='{{json .State.Health}}'
   ```

2. Check logs for errors:
   ```bash
   docker compose logs --tail=100 apex-trader | grep -i error
   ```

3. Validate configuration:
   ```bash
   docker compose exec apex-trader python scripts/dry_run.py --validate
   ```

4. Check bot status:
   ```bash
   docker compose exec apex-trader python scripts/run_bot.py --status
   ```

**Python:**
1. Check configuration:
   ```bash
   python scripts/dry_run.py --validate
   ```

2. Run dry-run test:
   ```bash
   python scripts/dry_run.py --verbose
   ```

3. Check status:
   ```bash
   python scripts/run_bot.py --status
   ```

4. Review logs for errors

### Information to Gather

Before asking for help, collect:
1. Python version: `python --version`
2. SDK version: `pip show apexomni`
3. Error message (full traceback)
4. Config (without credentials!)
5. Log output

### Resources

- **ApexOmni Docs**: https://api-docs.pro.apex.exchange/
- **SDK Issues**: https://github.com/ApeX-Protocol/apexpro-openapi/issues
- **Project Docs**: See `docs/` folder

---

## Quick Fixes Checklist

### Pre-Flight Checklist (Before First Trade)

**Critical SDK Requirements:**
- [ ] SDK can initialize: `configs_v3()` returns data
- [ ] SDK can get account: `get_account_v3()` returns data
- [ ] Test connection passes: `client.test_connection()` returns True

**Symbol Verification:**
- [ ] Bot successfully identifies tradeable symbols
- [ ] At least one symbol has `enableOpenPosition: true` AND `enableTrade: true`
- [ ] Balance is sufficient for at least one symbol's minimum order value

**Margin Verification:**
- [ ] Balance >= minimum order value for your symbol
- [ ] No margin locked in open positions

### Docker Checklist

- [ ] Docker and Docker Compose installed
- [ ] `.env` file exists with credentials
- [ ] API key has trading permission
- [ ] ZK seeds obtained and configured
- [ ] `docker compose up -d --build` successful
- [ ] Container healthy: `docker compose ps`
- [ ] No errors in logs: `docker compose logs apex-trader`
- [ ] Sufficient USDT balance for minimum order value
- [ ] Using correct network (testnet vs mainnet)
- [ ] `DRY_RUN` set appropriately

### Python Checklist

- [ ] Python 3.8+ installed
- [ ] Virtual environment activated
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file exists with credentials
- [ ] API key has trading permission
- [ ] ZK seeds obtained and configured
- [ ] System time is accurate (`date -u` matches UTC)
- [ ] Network can reach ApexOmni (`ping omni.apex.exchange`)
- [ ] Sufficient USDT balance for minimum order value
- [ ] Configuration validated (`python scripts/dry_run.py --validate`)
- [ ] Using correct network (testnet vs mainnet)

### Debugging Checklist (When Orders Fail)

- [ ] Enable debug mode: `DEBUG=true`
- [ ] Check full error message in logs
- [ ] Verify SDK initialization: test_connection() succeeds
- [ ] Check symbol is tradeable (not disabled)
- [ ] Verify actual balance vs required margin
- [ ] Check for open positions consuming margin
- [ ] Ensure symbol format is correct (e.g., "BTC-USDT" not "BTCUSDT")
