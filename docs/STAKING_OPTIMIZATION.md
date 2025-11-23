# Staking Optimization Guide

This document provides a complete guide to ApexOmni's staking system and how to maximize your staking rewards using the Trading Activity Factor.

## Table of Contents

1. [Staking System Overview](#staking-system-overview)
2. [Reward Formula](#reward-formula)
3. [Trading Activity Factor](#trading-activity-factor)
4. [Time Factor](#time-factor)
5. [Calculation Examples](#calculation-examples)
6. [Optimization Strategies](#optimization-strategies)
7. [Weekly Schedule](#weekly-schedule)

---

## Staking System Overview

### What is Staking?

ApexOmni's staking program allows users to earn passive income by staking $APEX and $esAPEX tokens. The platform distributes a portion of trading fee revenue to stakers in the form of APEX tokens.

### Key Features

| Feature | Description |
|---------|-------------|
| **Reward Token** | APEX (bought back from platform fees) |
| **Distribution** | Weekly (every Monday 8AM UTC) |
| **Claimable** | Thursday 8AM UTC |
| **Stakeable Tokens** | $APEX and $esAPEX |

### Staking Program Evolution

| Version | Date | Key Changes |
|---------|------|-------------|
| Staking 1.0 | Jan 2023 | Initial USDC rewards |
| Staking 2.0 | - | T2E Score integration |
| Staking 3.0 | Mar 2024 | Locked staking, Time Factor |
| Staking 4.0 | Feb 2025 | Migration to Omni, APEX rewards |

---

## Reward Formula

### Total Staking Factor

The core formula that determines your share of the weekly reward pool:

```
Total Staking Factor = 1 + Time Factor + Trading Activity Factor
```

Where:
- **Base Factor**: 1.0 (everyone starts here)
- **Time Factor**: 0.0 to 2.0+ (based on lock-up period)
- **Trading Activity Factor**: 0.0 to 0.5 (based on trading days)

### Reward Calculation

```
Your Weekly Reward = (Your Weighted Stake / Total Pool Weighted Stake) x Weekly Pool

Where:
Your Weighted Stake = Staked Amount x Total Staking Factor
```

### Factor Ranges

| Component | Minimum | Maximum |
|-----------|---------|---------|
| Base Factor | 1.0 | 1.0 |
| Time Factor | 0.0 | 2.0+ |
| Trading Activity Factor | 0.0 | 0.5 |
| **Total** | 1.0 | 3.5+ |

---

## Trading Activity Factor

### Formula

```
Trading Activity Factor = 0.1 x (Days Traded in Week)
Maximum = 0.5 (capped at 5 days)
```

### Factor Values

| Days Traded | Factor Value | Multiplier Boost |
|-------------|--------------|------------------|
| 0 | 0.0 | +0% |
| 1 | 0.1 | +10% |
| 2 | 0.2 | +20% |
| 3 | 0.3 | +30% |
| 4 | 0.4 | +40% |
| 5 | 0.5 | +50% |

### Rules

1. **One trade per day counts**
   - Additional trades on the same day don't add more
   - Trade once = full credit for that day

2. **Any trade size qualifies**
   - Even minimum-size orders count
   - No volume threshold required

3. **Any trading pair works**
   - BTC-USDT, ETH-USDT, etc.
   - All perpetual contracts qualify

4. **Order must fill**
   - Unfilled limit orders don't count
   - Canceled orders don't count

5. **Weekly reset**
   - Factor resets to 0 every Monday 8AM UTC
   - Must trade again each week

### Day Boundaries

A "trading day" in ApexOmni's system:

```
Day Boundary: 8:00 AM UTC

Monday Day:    Mon 8:00 AM UTC → Tue 8:00 AM UTC
Tuesday Day:   Tue 8:00 AM UTC → Wed 8:00 AM UTC
Wednesday Day: Wed 8:00 AM UTC → Thu 8:00 AM UTC
Thursday Day:  Thu 8:00 AM UTC → Fri 8:00 AM UTC
Friday Day:    Fri 8:00 AM UTC → Sat 8:00 AM UTC
Saturday Day:  Sat 8:00 AM UTC → Sun 8:00 AM UTC
Sunday Day:    Sun 8:00 AM UTC → Mon 8:00 AM UTC
```

**Important:** A trade at 7:59 AM UTC Tuesday counts for Monday!

---

## Time Factor

### Formula

For locked staking:

```
Time Factor = Lock-Up Period (Months) / 12 Months
```

### Factor Values

| Lock-Up Period | Time Factor | Total with Trading |
|----------------|-------------|-------------------|
| No lock | 0.0 | 1.5 max |
| 3 months | 0.25 | 1.75 max |
| 6 months | 0.50 | 2.0 max |
| 12 months | 1.00 | 2.5 max |
| 18 months | 1.50 | 3.0 max |
| 24 months | 2.00 | 3.5 max |

### Rules

1. **Lock-up required**
   - Must lock tokens for a specific period
   - Cannot withdraw during lock period

2. **Factor active during lock**
   - Only applies while tokens are locked
   - Resets to 0 when lock expires

3. **Re-lock to maintain**
   - Must re-lock tokens to keep Time Factor
   - Can extend lock for higher factor

### Comparison: Time Factor vs Trading Factor

| Factor | Max Value | Effort | Risk |
|--------|-----------|--------|------|
| Time Factor | 2.0 | Lock tokens | Illiquidity |
| Trading Factor | 0.5 | Trade 5 days | Minimal fees |

**Key Insight:** Trading Factor is easier to achieve and doesn't require locking capital.

---

## Calculation Examples

### Example 1: No Optimization

**Scenario:**
- Staked: 10,000 APEX
- Lock-up: None
- Days traded: 0

**Calculation:**
```
Time Factor = 0
Trading Activity Factor = 0
Total Staking Factor = 1 + 0 + 0 = 1.0

Weighted Stake = 10,000 x 1.0 = 10,000 effective APEX
```

### Example 2: Trading Only

**Scenario:**
- Staked: 10,000 APEX
- Lock-up: None
- Days traded: 5

**Calculation:**
```
Time Factor = 0
Trading Activity Factor = 5 x 0.1 = 0.5
Total Staking Factor = 1 + 0 + 0.5 = 1.5

Weighted Stake = 10,000 x 1.5 = 15,000 effective APEX
Result: 50% more rewards than baseline!
```

### Example 3: Locked Staking Only

**Scenario:**
- Staked: 10,000 APEX
- Lock-up: 6 months
- Days traded: 0

**Calculation:**
```
Time Factor = 6/12 = 0.5
Trading Activity Factor = 0
Total Staking Factor = 1 + 0.5 + 0 = 1.5

Weighted Stake = 10,000 x 1.5 = 15,000 effective APEX
Result: Same as trading 5 days, but capital is locked
```

### Example 4: Full Optimization

**Scenario:**
- Staked: 10,000 APEX
- Lock-up: 12 months
- Days traded: 5

**Calculation:**
```
Time Factor = 12/12 = 1.0
Trading Activity Factor = 5 x 0.1 = 0.5
Total Staking Factor = 1 + 1.0 + 0.5 = 2.5

Weighted Stake = 10,000 x 2.5 = 25,000 effective APEX
Result: 150% more rewards than baseline!
```

### Example 5: Maximum Optimization

**Scenario:**
- Staked: 10,000 APEX
- Lock-up: 24 months
- Days traded: 5

**Calculation:**
```
Time Factor = 24/12 = 2.0
Trading Activity Factor = 5 x 0.1 = 0.5
Total Staking Factor = 1 + 2.0 + 0.5 = 3.5

Weighted Stake = 10,000 x 3.5 = 35,000 effective APEX
Result: 250% more rewards than baseline!
```

### Comparison Summary

| Scenario | Factor | Weighted Stake | vs Baseline |
|----------|--------|----------------|-------------|
| No optimization | 1.0 | 10,000 | - |
| 5 days trading | 1.5 | 15,000 | +50% |
| 6-month lock | 1.5 | 15,000 | +50% |
| 12-month lock + trading | 2.5 | 25,000 | +150% |
| 24-month lock + trading | 3.5 | 35,000 | +250% |

---

## Optimization Strategies

### Strategy 1: Trading Only (Recommended for Most)

**Best for:** Users who want flexibility, don't want to lock tokens

**Implementation:**
- Trade 5 days per week using the bot
- Keep tokens unlocked (can sell anytime)
- Achieve 1.5x multiplier

**Cost:** Minimal to zero (real trades have shown $0.00 fees)

**Benefit:** 50% reward boost with zero lockup

### Strategy 2: Balanced Approach

**Best for:** Users willing to commit some capital

**Implementation:**
- Lock tokens for 6 months
- Trade 5 days per week
- Achieve 2.0x multiplier

**Cost:** ~$0.50/week + capital locked 6 months

**Benefit:** 100% reward boost

### Strategy 3: Maximum Rewards

**Best for:** Long-term believers in APEX

**Implementation:**
- Lock tokens for 24 months
- Trade 5 days per week
- Achieve 3.5x multiplier

**Cost:** ~$0.50/week + capital locked 24 months

**Benefit:** 250% reward boost

### Strategy Comparison

| Strategy | Multiplier | Weekly Cost | Capital Lock |
|----------|------------|-------------|--------------|
| Trading only | 1.5x | $0.50 | None |
| 6-month + trading | 2.0x | $0.50 | 6 months |
| 12-month + trading | 2.5x | $0.50 | 12 months |
| 24-month + trading | 3.5x | $0.50 | 24 months |

### ROI Analysis

Assuming 10,000 APEX staked, 100 APEX base weekly reward:

| Strategy | Weekly Reward | Monthly Reward | Annual Reward |
|----------|---------------|----------------|---------------|
| Baseline | 100 APEX | 400 APEX | 4,800 APEX |
| Trading only | 150 APEX | 600 APEX | 7,200 APEX |
| 6-month lock + trading | 200 APEX | 800 APEX | 9,600 APEX |
| 12-month lock + trading | 250 APEX | 1,000 APEX | 12,000 APEX |
| 24-month lock + trading | 350 APEX | 1,400 APEX | 16,800 APEX |

---

## Weekly Schedule

### Optimal Weekly Routine

```
Monday 8:00 AM UTC - Week Resets
├─ Trading Activity Factor → 0.0
├─ New staking week begins
└─ Rewards from previous week calculated

Monday 9:00 AM UTC - Trade 1
├─ Execute first trade
└─ Factor → 0.1

Tuesday 9:00 AM UTC - Trade 2
├─ Execute second trade
└─ Factor → 0.2

Wednesday 9:00 AM UTC - Trade 3
├─ Execute third trade
└─ Factor → 0.3

Thursday 8:00 AM UTC - Rewards Claimable
├─ Previous week's rewards available
└─ Claim your APEX rewards

Thursday 9:00 AM UTC - Trade 4
├─ Execute fourth trade
└─ Factor → 0.4

Friday 9:00 AM UTC - Trade 5
├─ Execute fifth trade
└─ Factor → 0.5 (MAXIMUM!)

Weekend - No action required
├─ Factor maintained at 0.5
└─ Additional trades provide no benefit

Next Monday 8:00 AM UTC - Cycle repeats
```

### Key Timestamps

| Event | Time (UTC) | Day |
|-------|------------|-----|
| Week reset | 8:00 AM | Monday |
| Daily boundary | 8:00 AM | Daily |
| Rewards calculated | 8:00 AM | Monday |
| Rewards claimable | 8:00 AM | Thursday |

### Bot Automation

The bot handles this schedule automatically.

**Continuous Mode (Docker - Recommended):**

```yaml
schedule:
  mode: "continuous"
  trade_interval_hours: 4  # Trade every 4 hours
  trade_days: [0, 1, 2, 3, 4, 5, 6]  # All 7 days (24/7 trading)
  continue_after_max_factor: true
```

**Daily Mode:**

```yaml
schedule:
  mode: "daily"
  trade_days: [0, 1, 2, 3, 4, 5, 6]  # All 7 days (24/7 trading)
  trade_time: "09:00"  # 9 AM UTC
```

For production, use Docker with continuous mode for 24/7 automated operation.

---

## Verification

### Check Your Factor

1. Visit https://omni.apex.exchange/staking
2. View your "Trading Activity Factor"
3. Verify it shows the expected value

### Monitor Progress

**Docker:**

```bash
docker compose exec apex-trader python scripts/run_bot.py --status
docker compose logs --tail=50 apex-trader
```

**Python:**

```bash
python scripts/run_bot.py --status
```

Output shows:
- Current factor
- Days traded
- Days remaining
- Schedule mode

### Verify Rewards

1. Wait until Thursday 8:00 AM UTC
2. Check staking dashboard for claimable rewards
3. Compare with expected multiplier

---

## Troubleshooting

### Factor Not Increasing

**Possible causes:**
1. Trade didn't fill (check order status)
2. Traded before 8:00 AM UTC (counted for previous day)
3. Same-day duplicate trade (only first counts)

**Solution:** Check trade history on ApexOmni

### Lower Rewards Than Expected

**Possible causes:**
1. Other stakers have higher factors
2. Pool size changed
3. Factor wasn't at maximum when calculated

**Note:** Your share depends on *relative* factor compared to all stakers

### Factor Reset Unexpectedly

**Cause:** Weekly reset on Monday 8:00 AM UTC

**Solution:** This is normal - factor resets every week

---

## Summary

### Quick Reference

```
Maximum Trading Activity Factor: 0.5
Achieved by: Trading 5 different days per week
Cost: Minimal to zero ($0.00 fees observed on minimum trades)
Benefit: 50% boost to staking rewards

Total Staking Factor = 1 + Time Factor + Trading Factor
Maximum possible: 3.5 (24-month lock + 5 days trading)
```

### Key Takeaways

1. **Trade 5 days/week** for maximum 0.5 Trading Activity Factor
2. **Any trade size works** - use minimum to reduce costs
3. **One trade per day** - extras don't help
4. **9 AM UTC recommended** - safely after day boundary
5. **Weekly reset** - start fresh every Monday
6. **Combine with locked staking** for maximum multiplier

### Calculator Command

Use the built-in calculator:

**Docker:**

```bash
docker compose exec apex-trader python scripts/calculate_multiplier.py --staked 10000 --lock-months 12 --days-traded 5
```

**Python:**

```bash
python scripts/calculate_multiplier.py --staked 10000 --lock-months 12 --days-traded 5
```

Output:
```
Staked Amount: 10,000 APEX
Lock Period: 12 months
Days Traded: 5

Time Factor: 1.0
Trading Activity Factor: 0.5
Total Staking Factor: 2.5

Your weighted stake: 25,000 effective APEX
Reward boost: +150% compared to baseline
```

### Continuous Mode and Max Factor

With continuous mode enabled, the bot can continue trading even after reaching the maximum factor (5 days). This is controlled by:

```yaml
schedule:
  continue_after_max_factor: true  # Keep trading for volume
```

Even though additional trades don't increase your factor, some users prefer to continue for:
- Trading volume bonuses
- Market making activity
- Consistency in daily routine

Set to `false` to pause trading after 5 unique days until the next weekly reset.
