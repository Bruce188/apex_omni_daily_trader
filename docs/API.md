# ApexOmni API Integration Documentation

This document describes how the trading bot integrates with the ApexOmni API, including authentication, key endpoints, and error handling.

## Table of Contents

1. [API Overview](#api-overview)
2. [Authentication](#authentication)
3. [Key Endpoints](#key-endpoints)
4. [SDK Usage](#sdk-usage)
5. [Error Handling](#error-handling)
6. [Rate Limits](#rate-limits)

---

## API Overview

ApexOmni provides a REST and WebSocket API for programmatic trading on their decentralized exchange (DEX). The platform is built on zkLink technology and supports perpetual contracts trading.

### Base URLs

| Environment | REST API | Purpose |
|-------------|----------|---------|
| **Mainnet** | `https://omni.apex.exchange/api` | Production trading |
| **Testnet** | `https://testnet.omni.apex.exchange/api` | Development/testing |

### API Documentation

- **Official Docs**: https://api-docs.pro.apex.exchange/
- **Python SDK**: https://github.com/ApeX-Protocol/apexpro-openapi
- **PyPI Package**: https://pypi.org/project/apexomni/

---

## Authentication

ApexOmni uses a multi-layer authentication system combining API keys and zkLink cryptographic signatures.

### Credential Types

#### 1. API Key Credentials

Generated from the ApexOmni web portal at Key Management:

| Credential | Description | Source |
|------------|-------------|--------|
| `APIKey` | Unique identifier | System-generated |
| `SecretKey` | Signing key | System-generated |
| `Passphrase` | User password | User-defined |

#### 2. ZK Keys (for Order Signing)

Required for placing orders and withdrawals:

| Key | Description | Source |
|-----|-------------|--------|
| `seeds` | ZK seed phrase | From "Omni Key" button |
| `l2Key` | L2 signing key | Derived from seeds |

### Authentication Flow

```
1. Load credentials from environment
2. Initialize SDK client with credentials
3. For each API request:
   - Create timestamp
   - Sign: message = timestamp + method + path + body
   - Add headers: signature, api_key, passphrase, timestamp
4. For orders: Include zkKeys signature
```

### Request Headers

```
APEX-SIGNATURE: <signature>
APEX-API-KEY: <api_key>
APEX-PASSPHRASE: <passphrase>
APEX-TIMESTAMP: <timestamp_in_ms>
```

### Signature Generation

**GET Requests:**
```
message = timeStamp + method + path
```

**POST Requests:**
```
message = timeStamp + method + path + requestBody
```

The signature is an HMAC-SHA256 hash of the message using the secret key.

---

## Key Endpoints

### Endpoints Used by This Bot

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/v3/symbols` | GET | Trading pair configs | No |
| `/v3/ticker` | GET | Current prices | No |
| `/v3/account` | GET | Account info | Yes |
| `/v3/account-balance` | GET | Balance check | Yes |
| `/v3/order` | POST | Place order | Yes + zkKeys |
| `/v3/open-orders` | GET | List orders | Yes |
| `/v3/fills` | GET | Trade history | Yes |

### Public Endpoints (No Auth)

#### Get Server Time
```
GET /v3/time
```
Response:
```json
{
  "data": {
    "time": 1700000000000
  }
}
```

#### Get Trading Pairs
```
GET /v3/symbols
```
Response includes all perpetual contract configurations.

**Important: Symbol Tradability Flags**

Each symbol has flags indicating whether it can be traded:

```json
{
  "symbol": "BTC-USDT",
  "enableOpenPosition": true,   // Can open new positions
  "enableTrade": true,          // Trading is enabled
  "minOrderSize": "0.001",
  "tickSize": "0.1",
  ...
}
```

**Trading Requirements:**
- `enableOpenPosition: true` - Required to open new positions
- `enableTrade: true` - Required for any trading activity

Many symbols have one or both flags set to `false`. Always check these before attempting to trade a symbol.

#### Get Ticker
```
GET /v3/ticker?symbol=BTC-USDT
```
Response:
```json
{
  "data": [{
    "symbol": "BTC-USDT",
    "lastPrice": "95000.0",
    "highPrice24h": "96000.0",
    "lowPrice24h": "94000.0",
    "volume24h": "1000000"
  }]
}
```

### Private Endpoints (Auth Required)

#### Get Account
```
GET /v3/account
```
Response:
```json
{
  "data": {
    "totalEquityValue": "1000.00",
    "availableBalance": "950.00",
    "marginBalance": "1000.00",
    "unrealizedPnl": "0",
    "openPositions": []
  }
}
```

#### Place Order
```
POST /v3/order
```
Request Body:
```json
{
  "symbol": "BTC-USDT",
  "side": "BUY",
  "type": "MARKET",
  "size": "0.001",
  "price": "95000",
  "timestampSeconds": 1700000000
}
```

Response:
```json
{
  "data": {
    "id": "123456789",
    "clientOrderId": "client-123",
    "symbol": "BTC-USDT",
    "side": "BUY",
    "type": "MARKET",
    "size": "0.001",
    "price": "95000",
    "status": "FILLED",
    "filledSize": "0.001",
    "avgFillPrice": "95010",
    "fee": "0.0475",
    "createdTime": 1700000000000
  }
}
```

### Order Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `symbol` | string | Yes | Trading pair (e.g., "BTC-USDT") |
| `side` | string | Yes | "BUY" or "SELL" |
| `type` | string | Yes | "MARKET" or "LIMIT" |
| `size` | string | Yes | Order quantity |
| `price` | string | Yes | Price (required even for MARKET orders) |
| `timestampSeconds` | number | Yes | Current Unix timestamp |
| `clientOrderId` | string | No | Custom order ID |
| `reduceOnly` | boolean | No | Reduce-only flag |

**Important**: ApexOmni requires a `price` parameter even for market orders due to zkLink signature requirements.

### Bot Trading Behavior

The bot enforces the following behavior for all trades (hardcoded, not configurable):

| Behavior | Value | Reason |
|----------|-------|--------|
| Leverage | Always 1x (cross margin) | Prevents liquidation risk |
| Position Closing | Always immediate | Eliminates market exposure |

Every trade consists of an open order followed immediately by a close order, resulting in zero net position.

---

## SDK Usage

### Installation

```bash
pip install apexomni
```

### SDK Classes

| Class | Purpose |
|-------|---------|
| `HttpPublic` | Public endpoints (no auth) |
| `HttpPrivate_v3` | Private endpoints (read-only) |
| `HttpPrivateSign` | Private endpoints with zkKeys |
| `WebSocket` | Real-time data streams |

### Constants

```python
from apexomni.constants import (
    APEX_OMNI_HTTP_MAIN,      # Mainnet REST API
    APEX_OMNI_HTTP_TEST,      # Testnet REST API
    APEX_OMNI_WS_MAIN,        # Mainnet WebSocket
    APEX_OMNI_WS_TEST,        # Testnet WebSocket
    NETWORKID_MAIN,           # Mainnet network ID
    NETWORKID_TEST,           # Testnet network ID
)
```

### Client Initialization

**For Trading (with zkKeys):**
```python
from apexomni.http_private_sign import HttpPrivateSign
from apexomni.constants import APEX_OMNI_HTTP_MAIN, NETWORKID_MAIN

client = HttpPrivateSign(
    APEX_OMNI_HTTP_MAIN,
    network_id=NETWORKID_MAIN,
    zk_seeds=seeds,
    zk_l2Key=l2Key,  # Can be empty string
    api_key_credentials={
        'key': api_key,
        'secret': api_secret,
        'passphrase': passphrase
    }
)
```

**For Read-Only:**
```python
from apexomni.http_private_v3 import HttpPrivate_v3
from apexomni.constants import APEX_OMNI_HTTP_TEST, NETWORKID_TEST

client = HttpPrivate_v3(
    APEX_OMNI_HTTP_TEST,
    network_id=NETWORKID_TEST,
    api_key_credentials={
        'key': api_key,
        'secret': api_secret,
        'passphrase': passphrase
    }
)
```

### Key SDK Methods

```python
# Get exchange configuration
configs = client.configs_v3()

# Get account information
account = client.get_account_v3()

# Get account balance
balance = client.get_account_balance_v3()

# Place an order
order = client.create_order_v3(
    symbol="BTC-USDT",
    side="BUY",
    type="MARKET",
    size="0.001",
    price="95000",
    timestampSeconds=int(time.time())
)

# Cancel an order
result = client.delete_order_v3(id="order_id")

# Get open orders
orders = client.open_orders_v3()

# Get trade history
fills = client.fills_v3(limit=100)

# Get current price (public)
from apexomni.http_public import HttpPublic
public = HttpPublic(APEX_OMNI_HTTP_MAIN)
ticker = public.ticker_v3(symbol="BTC-USDT")
```

### CRITICAL: SDK Initialization Requirements

**The ApexOmni SDK v3 requires specific initialization before placing orders.**

You MUST call BOTH `configs_v3()` AND `get_account_v3()` BEFORE any order placement:

```python
# CORRECT - Initialize before trading
client = HttpPrivateSign(...)

# Step 1: Initialize configs (sets internal configV3)
configs = client.configs_v3()

# Step 2: Initialize account (sets internal accountV3)
account = client.get_account_v3()

# Step 3: NOW you can place orders
order = client.create_order_v3(...)  # Will succeed
```

```python
# WRONG - Will fail with "insufficient margin" error
client = HttpPrivateSign(...)

# Skipping initialization...
order = client.create_order_v3(...)  # FAILS!
```

**Why this matters:**
- The SDK stores `configV3` and `accountV3` internally
- These are required for zkLink signature generation
- Without them, the API receives malformed requests
- Error message is misleading: "insufficient margin"

**Bot implementation:**
The bot handles this via `_ensure_sdk_initialized()` in `bot/api_client.py`, which is automatically called before any order placement.

### SDK Method Limitations

**clientOrderId Not Supported:**
Despite API documentation, the SDK's `create_order_v3()` does NOT support `clientOrderId`:

```python
# This will FAIL:
order = client.create_order_v3(
    symbol="BTC-USDT",
    clientOrderId="my-custom-id",  # NOT SUPPORTED!
    ...
)

# This is correct:
order = client.create_order_v3(
    symbol="BTC-USDT",
    side="BUY",
    type="MARKET",
    size="0.001",
    price="95000",
    timestampSeconds=int(time.time())
)
```

**Response Format Variations:**
API responses have inconsistent formats:

```python
# Some endpoints return dict with 'data'
response = {'data': {'id': '123', ...}}

# Some return list directly
response = [{'id': '123'}, {'id': '456'}]

# Error responses have 'code' and 'message'
response = {'code': 3, 'message': 'Error description'}
```

Always check response type before accessing fields.

### Bot Integration Example

The bot's `ApexOmniClient` class wraps the SDK:

```python
from bot.api_client import create_client, ApexOmniClient
from bot.config import Config

# Load configuration
config = Config.load()

# Create client (real or mock based on dry_run setting)
client = create_client(config.api, dry_run=config.safety.dry_run)

# Test connection
if client.test_connection():
    print("Connected successfully")

# Get balance
balance = client.get_account_balance()
print(f"Available: {balance.available_balance}")

# Get current price
price = client.get_current_price("BTC-USDT")
print(f"BTC price: {price}")

# Place order
result = client.place_order(
    symbol="BTC-USDT",
    side="BUY",
    order_type="MARKET",
    size=Decimal("0.001")
)

if result.success:
    print(f"Order filled: {result.order_id}")
else:
    print(f"Order failed: {result.error}")
```

### TradeExecutor Methods

The `TradeExecutor` class provides high-level trading operations:

#### determine_best_symbol()

**Purpose:** Automatically select the cheapest tradeable symbol based on available balance.

```python
from bot.trade_executor import TradeExecutor

executor = TradeExecutor(client, config)

# Get cheapest tradeable symbol based on balance
result = executor.determine_best_symbol()

if result:
    symbol_name, min_order_size, symbol_config = result
    print(f"Cheapest symbol: {symbol_name} (min size: {min_order_size})")
else:
    print("No tradeable symbol available for current balance")
```

**Returns:**
- Tuple of `(symbol_name, min_order_size, symbol_config)` if found
- `None` if no tradeable symbol available

**Behavior:**
1. Analyzes ALL available trading pairs
2. Filters to only tradeable symbols (`enableOpenPosition=true` AND `enableTrade=true`)
3. Calculates minimum order value for each: `min_order_size x current_price`
4. Selects the symbol with the lowest minimum order value that fits the balance
5. Returns None if no symbol is tradeable with current balance

This method should be called before generating a trade, to ensure the correct symbol is used.

#### Strategy Integration with symbol_override

The `get_trade_for_today()` method accepts override parameters:

```python
from bot.strategy import StakingOptimizationStrategy

strategy = StakingOptimizationStrategy(config)

# Auto-select the cheapest tradeable symbol
result = executor.determine_best_symbol()
if result:
    symbol_name, min_order_size, symbol_config = result

    # Generate trade with auto-selected symbol
    trade = strategy.get_trade_for_today(
        symbol_override=symbol_name,
        size_override=min_order_size
    )
```

**Parameters:**
- `symbol_override`: Override with auto-selected symbol
- `size_override`: Override with `min_order_size` for the selected symbol

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Bot Action |
|------|---------|------------|
| 200 | Success | Process response |
| 400 | Bad request | Log error, check params |
| 401 | Unauthorized | Check credentials |
| 403 | Forbidden/Rate limited | Backoff and retry |
| 404 | Not found | Check endpoint |
| 500 | Server error | Retry with backoff |

### Error Response Format

```json
{
  "code": "ERROR_CODE",
  "message": "Human readable error message",
  "data": null
}
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| Invalid signature | Wrong signing | Check timestamp, credentials |
| Insufficient balance | Low funds | Check account balance |
| Invalid symbol | Unknown pair | Verify symbol format |
| Rate limited | Too many requests | Implement backoff |
| Invalid price | Price out of range | Check tick size |
| Invalid size | Size too small | Check min order size |

### Bot Error Handling

The bot implements retry logic with exponential backoff:

```python
RETRY_CONFIG = {
    "max_retries": 3,
    "base_delay": 1.0,  # seconds
    "max_delay": 30.0,
    "exponential_base": 2
}
```

Example retry flow:
1. First attempt fails (rate limit)
2. Wait 1 second, retry
3. Second attempt fails
4. Wait 2 seconds, retry
5. Third attempt fails
6. Wait 4 seconds, retry
7. Give up, log error

---

## Rate Limits

### REST API Limits

| Category | Limit Type | Notes |
|----------|------------|-------|
| Public APIs | IP-based | Varies by endpoint |
| Private APIs | UID-based | Higher limits |
| Order creation | UID-based | Highest limits |

### Best Practices

1. **Cache Static Data**
   - Symbol configs don't change frequently
   - Cache for the session duration

2. **Use Exponential Backoff**
   - On 403/429 responses
   - Don't hammer the API

3. **Batch Operations**
   - Minimize API calls where possible
   - Get account info once per trade cycle

4. **WebSocket for Real-Time**
   - Use REST for trading
   - Consider WebSocket for monitoring (future enhancement)

### Bot Rate Limit Compliance

The bot minimizes API calls:
- Gets configs once at startup
- Caches symbol configurations
- One order per trade cycle (open + close)
- Status checks use cached data when possible

---

## WebSocket API (Reference)

While the current bot uses REST API, WebSocket is available for real-time data:

### Connection

```python
from apexomni.websocket_api import WebSocket
from apexomni.constants import APEX_OMNI_WS_MAIN

ws_client = WebSocket(
    endpoint=APEX_OMNI_WS_MAIN,
    api_key_credentials={
        'key': key,
        'secret': secret,
        'passphrase': passphrase
    }
)
```

### Streams

| Stream | Method | Description |
|--------|--------|-------------|
| Depth | `depth_stream()` | Order book |
| Ticker | `ticker_stream()` | Price updates |
| Trade | `trade_stream()` | Recent trades |
| Klines | `klines_stream()` | Candlesticks |
| Account | `account_info_stream_v3()` | Account updates |

### Heartbeat

Send `ping` every 15 seconds to maintain connection. Server responds with `pong`.

---

## Security Notes

1. **Never expose credentials**
   - Use environment variables
   - Never log API keys or secrets
   - Exclude `.env` from git

2. **Use HTTPS only**
   - All API calls use HTTPS
   - Verify SSL certificates

3. **Testnet first**
   - Always test on testnet
   - Use separate credentials for mainnet

4. **Minimal permissions**
   - Only enable necessary API permissions
   - Disable withdrawal if not needed

5. **Monitor activity**
   - Check trade history regularly
   - Set up alerts for unexpected activity

---

## Additional Resources

- **Official API Documentation**: https://api-docs.pro.apex.exchange/
- **Python SDK Repository**: https://github.com/ApeX-Protocol/apexpro-openapi
- **SDK Demo Scripts**: `tests/demo_*.py` in the SDK repository
- **ApexOmni Platform**: https://omni.apex.exchange
- **Testnet**: https://testnet.omni.apex.exchange
