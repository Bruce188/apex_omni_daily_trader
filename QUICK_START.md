# ApexOmni Staking Factor Maximizer - Quick Start

## Current Status

| Item | Status |
|------|--------|
| API Key | Configured |
| API Secret | Configured |
| Passphrase | Configured |
| ZK Seeds | **NOT SET** (required for trading) |
| Spot Balance | Check via ApexOmni web interface |
| Contract Balance | Check via ApexOmni web interface |

## Required Actions

### Step 1: Get ZK Seeds (REQUIRED)

The ZK Seeds are cryptographic keys needed to sign trades. Get them from the ApexOmni web interface:

1. Go to **https://omni.apex.exchange**
2. Connect your wallet (`<YOUR_WALLET_ADDRESS>`)
3. Navigate to **Settings** > **API Management**
4. Either:
   - View your existing API key to see the seeds, OR
   - Create a new API key and save the ZK Seeds shown
5. Add to `.env` file:
   ```
   APEX_ZK_SEEDS=0x1234567890abcdef...  (your seeds here)
   ```

### Step 2: Transfer Funds (REQUIRED)

Your funds may be in the **Spot wallet** but perpetual trading requires funds in the **Contract wallet**.

1. Go to **https://omni.apex.exchange**
2. Click **Assets** > **Transfer**
3. Settings:
   - From: **Spot**
   - To: **Contract (Perpetual)**
   - Amount: **2 USDT** (enough for 5 trades + margin)
4. Confirm transfer

### Step 3: Execute Trades

Once ZK Seeds are set and funds transferred:

```bash
# Test first (no real trades)
python3 scripts/dry_run.py

# Execute real trades
python3 scripts/run_bot.py --live
```

## Trade Plan

The bot automatically selects the cheapest tradeable symbol based on your balance:

1. **Symbol Analysis**: `determine_best_symbol()` analyzes ALL available trading pairs
2. **Cost Calculation**: Calculates minimum order value for each symbol
3. **Automatic Selection**: Picks the symbol with the lowest minimum order value
4. **Trade Execution**: Generates and executes trade with the auto-selected symbol

**Example with $2 balance:**
- Bot analyzes all 100+ symbols
- LINEA-USDT identified as cheapest: min 1 @ $0.0093 = $0.0093 trade value
- Trade succeeds with $2 balance (balance > min order value)

## Staking Factor Impact

Trading Activity Factor = 0.1 × Days Traded (max 0.5)

| Days Traded | Bonus |
|-------------|-------|
| 1 day | +0.1 |
| 2 days | +0.2 |
| 3 days | +0.3 |
| 4 days | +0.4 |
| 5 days | +0.5 (MAX) |

**Run this script daily for 5 consecutive days to maximize your staking multiplier!**

## Troubleshooting

### "ZK_SEEDS not set"
Get your ZK Seeds from the ApexOmni web interface (see Step 1)

### "Insufficient Contract Balance"
Transfer USDT from Spot to Contract wallet (see Step 2)

### "Signature verification failed"
Your ZK Seeds may be incorrect. Get new ones from the web interface.

## Files

- `scripts/run_bot.py` - Main trade execution script
- `scripts/dry_run.py` - Dry-run simulation script
- `scripts/derive_zk_seeds.py` - ZK seeds derivation utility
- `scripts/calculate_multiplier.py` - Staking multiplier calculator
- `.env` - API credentials configuration
- `bot/` - Trading bot modules
- `tests/` - Test suite
- `docs/` - Documentation
