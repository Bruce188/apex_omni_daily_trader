# Trading Strategy Documentation

This document explains the staking optimization strategy used by the ApexOmni Daily Trading Bot.

## Table of Contents

1. [Strategy Overview](#strategy-overview)
2. [Why 5 Trades](#why-5-trades)
3. [Schedule Modes](#schedule-modes)
4. [Trade Execution](#trade-execution)
5. [Risk Management](#risk-management)
6. [Expected Outcomes](#expected-outcomes)

---

## Strategy Overview

### Goal

The bot's primary goal is to maximize the **Trading Activity Factor** component of ApexOmni's staking reward formula by trading on 5 unique days per week.

### Key Concept

ApexOmni rewards stakers who actively trade on the platform. The Trading Activity Factor provides a multiplier bonus of up to 0.5 (50% boost) on your staking rewards, achieved by trading on 5 different days within each weekly staking period.

### Strategy Summary

```
Execute trades on 5 unique days = 0.5 Trading Activity Factor

This adds 0.5 to your base staking multiplier (1.0), resulting in
a minimum 1.5x multiplier on your staking rewards.
```

### Safety Design

The bot enforces two critical safety measures that are **hardcoded and cannot be changed**:

| Setting | Value | Reason |
|---------|-------|--------|
| **Leverage** | Always 1x | Prevents liquidation risk |
| **Position Closing** | Always immediate | Eliminates market exposure |

---

## Why 5 Trades

### The Trading Activity Factor Formula

```
Trading Activity Factor = 0.1 x (Unique Days Traded in Week)
Maximum = 0.5 (capped at 5 days)
```

### Accumulation Rules

1. **One trade per day counts** - Trading multiple times in one day does NOT increase your factor
2. **Five days maximum** - Trading more than 5 days provides no additional benefit
3. **Any trade qualifies** - Even the smallest trade counts toward your daily activity
4. **Non-consecutive days OK** - Days don't need to be consecutive

### Factor Values

| Days Traded | Factor | Benefit |
|-------------|--------|---------|
| 0 | 0.0 | No bonus |
| 1 | 0.1 | +10% |
| 2 | 0.2 | +20% |
| 3 | 0.3 | +30% |
| 4 | 0.4 | +40% |
| 5 | 0.5 | +50% (maximum) |
| 6+ | 0.5 | No additional benefit |

Trading more than 5 days wastes trading fees without increasing rewards.

### Cost-Benefit Analysis

```
Weekly Cost (5 trades):
- Trade size: ~$95 (0.001 BTC)
- Round-trip fee: ~0.1% (open + close)
- Cost per trade: ~$0.10
- Weekly cost: ~$0.50

Weekly Benefit:
- 50% boost to staking rewards
- If staking 10,000 APEX earning 100 APEX/week:
  - Without trading: 100 APEX
  - With 5 trades: 150 APEX (+50 APEX)
  - Net gain: 50 APEX - $0.50 = substantial profit
```

---

## Schedule Modes

The bot supports two scheduling modes to accommodate different deployment scenarios.

### Continuous Mode (Recommended for Docker)

**Best for:** Production Docker deployment, 24/7 operation

**How it works:**
- Runs continuously in a daemon loop
- Checks trade eligibility at regular intervals (default: 5 minutes)
- Executes trades when conditions are met
- Respects configured trade days
- Can continue trading after max factor is reached

**Configuration:**

```yaml
schedule:
  mode: "continuous"
  trade_interval_hours: 4  # Hours between trades
  trade_days: [0, 1, 2, 3, 4, 5, 6]  # All 7 days (24/7 trading)
  continue_after_max_factor: true
```

**Behavior:**
- Every 5 minutes (configurable), the daemon checks:
  1. Is today a configured trade day?
  2. Has enough time passed since the last trade?
  3. Has max factor been reached? (and should we continue?)
- If all conditions are met, executes a trade

### Daily Mode

**Best for:** Manual execution, cron scheduling, development

**How it works:**
- Executes a single trade at the scheduled time
- Exits after trade completion
- Good for external schedulers (cron, systemd timers)
- **State persistence**: Tracks whether traded today in `bot_state.json`

**Configuration:**

```yaml
schedule:
  mode: "daily"
  trade_days: [0, 1, 2, 3, 4, 5, 6]  # All 7 days (24/7 trading)
  trade_time: "09:00"  # UTC
```

**State Persistence:**
- `has_traded_today()` check is performed before trading
- State is persisted to `bot_state.json` (survives container restarts)
- `mark_traded_today()` is called after successful trade
- State resets automatically at midnight UTC

**Cron Example:**
```bash
# Run at 9:00 AM UTC Monday-Friday
0 9 * * 1-5 cd /path/to/bot && ./venv/bin/python scripts/run_bot.py --live
```

### Choosing a Mode

| Scenario | Recommended Mode |
|----------|-----------------|
| Docker production deployment | Continuous |
| Cloud/VPS with Docker | Continuous |
| Manual execution | Daily |
| Cron scheduling | Daily |
| Development/testing | Daily |

---

## Trade Execution

### Trade Characteristics

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Size** | Minimum order size for selected symbol | Minimize cost and risk |
| **Pair** | Auto-selected | Cheapest tradeable symbol based on balance |
| **Type** | MARKET | Guaranteed fill |
| **Leverage** | 1x (hardcoded) | Safety - prevents liquidation |
| **Close** | Immediate (hardcoded) | Safety - no market exposure |

**Note:** The bot automatically analyzes ALL available trading pairs, calculates the minimum order value for each, and selects the cheapest tradeable symbol.

### Execution Flow

```
1. Check trade eligibility
   |-> Is it a trade day?
   |-> Has enough time passed since last trade?
   |-> Is max factor reached? (optional continue)
   |-> Has already traded today? (daily mode - checks bot_state.json)

2. Symbol Selection (automatic)
   |-> Call determine_best_symbol()
   |-> Analyze ALL available trading pairs
   |-> Calculate minimum order value for each symbol
   |-> Select cheapest tradeable symbol that fits balance
   |-> Returns: symbol_name, min_order_size

3. Generate trade with auto-selected symbol
   |-> Symbol: Auto-selected (e.g., LINEA-USDT - cheapest)
   |-> Side: BUY (configurable)
   |-> Size: min_order_size for selected symbol
   |-> Type: MARKET

4. Validate preconditions
   |-> Check account balance
   |-> Verify API connection
   |-> Confirm within position limits

5. Execute opening trade
   |-> Place market order
   |-> Wait for fill

6. Execute closing trade (mandatory)
   |-> Place opposite market order
   |-> Wait for fill

7. Record result
   |-> Log to trade history
   |-> Update day counter
   |-> Mark traded today (save to bot_state.json)
```

### What Counts as a Trade?

**Qualifies:**
- Order is **filled** (executed)
- Position opened or closed
- Both maker and taker orders

**Does NOT Qualify:**
- Placing an order that isn't filled
- Canceling an order
- Modifying an existing order
- Failed orders

### Order Types

**Market Order (Default)**

```python
order = client.create_order_v3(
    symbol="BTC-USDT",
    side="BUY",
    type="MARKET",
    size="0.001",
    price="95000",  # Required for zkLink
    timestampSeconds=int(time.time())
)
```

Pros:
- Guaranteed fill
- Immediate execution
- Always counts as a trade

Cons:
- Slight slippage possible
- No price control

---

## Risk Management

### Hardcoded Safety Measures

These cannot be changed or configured:

1. **1x Leverage Only**
   - All trades use 1x cross margin
   - Prevents liquidation risk
   - No leverage amplification

2. **Mandatory Position Closing**
   - Every open position is immediately closed
   - Net position is always zero
   - No overnight exposure

### Position Risk

**Handled by mandatory closing:**

```
1. BUY 0.001 BTC @ market
2. SELL 0.001 BTC @ market (immediate)
3. Net position: 0
```

### Slippage Risk

**Mitigation:**
- Use high-liquidity pairs (BTC-USDT)
- Execute during stable market conditions
- Minimum position size limits losses

**Maximum Expected Slippage:**
- Typical: 0.01-0.05%
- Worst case: 0.1-0.2%
- On $95 position: $0.01-0.20

### Trading Fee Risk

**Fee Structure:**
- Maker fee: 0.02%
- Taker fee: 0.05%
- Round trip: ~0.1%

**Weekly Costs:**
- 5 trades x $0.10 = $0.50/week
- Monthly: ~$2.00

### Balance Risk

**Mitigation:**

```yaml
safety:
  require_balance_check: true
  min_balance: 50  # USD
```

The bot will not trade if balance falls below minimum.

### Technical Risk

**Problem:** API failures, network issues.

**Mitigation:**
- Retry logic with exponential backoff
- Graceful shutdown handling (Docker SIGTERM)
- Comprehensive logging

```python
RETRY_CONFIG = {
    "max_retries": 3,
    "base_delay": 1.0,
    "max_delay": 30.0
}
```

---

## Safety Mechanisms

### Circuit Breaker

The bot automatically stops trading after 5 consecutive failures to prevent:
- Runaway losses during API outages
- Excessive retry attempts
- Rate limit exhaustion

The circuit breaker resets after 30 minutes of inactivity.

**States:**
- `CLOSED`: Normal operation, trades allowed
- `OPEN`: Too many failures, trades blocked
- `HALF_OPEN`: Testing if system recovered

**Configuration:**
```bash
MAX_FAILURES=5              # Failures before halt
CIRCUIT_RESET_MINUTES=30    # Recovery wait time
```

### Order Deduplication

Each order includes a unique `client_order_id` to prevent duplicate orders:
- Format: `{symbol}-{timestamp_ms}-{uuid}-{attempt}`
- Checked before retries to detect orders that succeeded but reported failure
- Prevents position accumulation from partial fills during retries

### Mainnet Warning

When running live on mainnet:
- 5-second countdown warning is displayed
- Press Ctrl+C to abort
- Only shown when `DRY_RUN=false` AND `APEX_NETWORK=mainnet`

---

## Expected Outcomes

### Trading Activity Factor Progression

```
Week Starts (Monday 8AM UTC)
|-- Day 1 Trade: Factor = 0.1
|-- Day 2 Trade: Factor = 0.2
|-- Day 3 Trade: Factor = 0.3
|-- Day 4 Trade: Factor = 0.4
|-- Day 5 Trade: Factor = 0.5 (MAXIMUM)

Week Ends (Next Monday 8AM UTC)
|-- Factor resets to 0.0
|-- Start again
```

### Staking Reward Impact

**Formula:**
```
Total Staking Factor = 1 + Time Factor + Trading Activity Factor
Your Reward = (Your Factor / Total Pool Factor) x Weekly Pool
```

**Example Scenario:**

Without trading (Factor = 1.0):
- Staked: 10,000 APEX
- Base rewards: 100 APEX/week

With 5 trades (Factor = 1.5):
- Same stake
- Boosted rewards: 150 APEX/week
- **Net gain: +50 APEX/week**

With locked staking + trading (Factor = 2.5):
- Time Factor: 1.0 (12-month lock)
- Trading Factor: 0.5
- Boosted rewards: 250 APEX/week
- **Net gain: +150 APEX/week**

### Cost vs. Benefit Analysis

| Scenario | Weekly Cost | Weekly Gain | Net Benefit |
|----------|-------------|-------------|-------------|
| 10K APEX staked | $0.50 | ~50 APEX | Highly positive |
| 5K APEX staked | $0.50 | ~25 APEX | Positive |
| 1K APEX staked | $0.50 | ~5 APEX | Breakeven-ish |

The more APEX you have staked, the more valuable the trading strategy becomes.

### Monthly Summary

```
Monthly Trades: ~20 (5 per week x 4 weeks)
Monthly Cost: ~$2.00
Monthly Benefit: 50% reward boost every week

For a 10,000 APEX stake:
- Without bot: 400 APEX/month
- With bot: 600 APEX/month
- Net gain: 200 APEX - $2 = significant profit
```

---

## Strategy Verification

### Monitor Your Factor

1. Visit https://omni.apex.exchange/staking
2. Check your "Trading Activity Factor"
3. Verify it increases daily (0.1 per day)
4. Confirm it reaches 0.5 by the 5th trade

### Bot Status Check (Docker)

```bash
docker compose exec apex-trader python scripts/run_bot.py --status

# Example output:
# Days Traded This Week: 3 / 5
# Trading Activity Factor: 0.3
# Schedule Mode: continuous
```

### Bot Status Check (Python)

```bash
python scripts/run_bot.py --status
python scripts/run_bot.py --plan
```

---

## Summary

The trading strategy is a simple, low-cost way to maximize your staking rewards on ApexOmni:

1. **Trade 5 unique days per week** - Achieves maximum 0.5 factor
2. **Minimum trade size** - Keeps costs low (~$0.50/week)
3. **Positions always close** - No market exposure (hardcoded)
4. **1x leverage only** - Prevents liquidation (hardcoded)
5. **High-liquidity pair** - Minimizes slippage
6. **Docker deployment** - Automated 24/7 operation

The strategy is most effective for users with meaningful APEX stakes, where the 50% reward boost significantly outweighs the trading costs.
