#!/usr/bin/env python3
"""
Staking Multiplier Calculator

Calculate and visualize the staking factor based on different scenarios.

Usage:
    python scripts/calculate_multiplier.py
    python scripts/calculate_multiplier.py --days 3 --lock-months 6
"""

import argparse
import sys
from pathlib import Path
from textwrap import dedent

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bot.utils import (
    calculate_trading_activity_factor,
    calculate_total_staking_factor,
)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Calculate ApexOmni Staking Multiplier",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--days", "-d",
        type=int,
        default=5,
        help="Number of days traded (0-5, default: 5)"
    )

    parser.add_argument(
        "--lock-months", "-l",
        type=int,
        default=0,
        help="Lock-up period in months (0-24, default: 0)"
    )

    parser.add_argument(
        "--staked-amount", "-s",
        type=float,
        default=10000,
        help="Amount staked in APEX (default: 10000)"
    )

    parser.add_argument(
        "--compare",
        action="store_true",
        help="Show comparison table"
    )

    return parser.parse_args()


def calculate_time_factor(lock_months: int) -> float:
    """Calculate Time Factor from lock-up period."""
    return lock_months / 12


def print_calculation(days_traded: int, lock_months: int, staked_amount: float):
    """Print detailed calculation breakdown."""
    time_factor = calculate_time_factor(lock_months)
    trading_factor = calculate_trading_activity_factor(days_traded)
    total_factor = calculate_total_staking_factor(time_factor, days_traded)
    effective_stake = staked_amount * total_factor
    baseline_factor = 1.0  # No trading, no lock
    improvement = ((total_factor / baseline_factor) - 1) * 100

    print(dedent(f"""

        ============================================================
        STAKING FACTOR CALCULATION
        ============================================================

        Input:
          Days Traded:    {days_traded} days
          Lock-up Period: {lock_months} months
          Staked Amount:  {staked_amount:,.0f} APEX

        Calculation:
          Base Factor:              1.0
          Time Factor:            + {time_factor:.2f}  ({lock_months}/12 months)
          Trading Activity Factor: + {trading_factor:.2f}  ({days_traded} * 0.1)
          ----------------------------------------
          Total Staking Factor:    = {total_factor:.2f}

        Effective Stake:
          {staked_amount:,.0f} APEX * {total_factor:.2f} = {effective_stake:,.0f} effective APEX

        Impact:
          Your staking rewards are multiplied by {total_factor:.2f}x
          vs. no optimization: +{improvement:.0f}% more rewards
        ============================================================
    """).strip())


def print_comparison_table():
    """Print comparison table for different scenarios."""
    # Build table rows
    header = f"{'Days Traded':<15} {'No Lock':<12} {'3-Month':<12} {'6-Month':<12} {'12-Month':<12} {'24-Month':<12}"
    rows = []
    for days in range(6):
        row = f"{days:<15}"
        for lock_months in [0, 3, 6, 12, 24]:
            time_factor = calculate_time_factor(lock_months)
            total = calculate_total_staking_factor(time_factor, days)
            row += f" {total:.2f}       "
        rows.append(row)

    table_rows = "\n".join(rows)
    print(dedent(f"""

        ================================================================================
        STAKING FACTOR COMPARISON TABLE
        ================================================================================

        {header}
        --------------------------------------------------------------------------------
        {table_rows}
        --------------------------------------------------------------------------------

        Formula: Total Factor = 1 + (Lock Months / 12) + (Days Traded * 0.1)

        Key Observations:
          - Trading 5 days adds +0.5 to your factor (50% more rewards)
          - 6-month lock adds +0.5 to your factor (50% more rewards)
          - Combined: 5 days + 6-month lock = 2.0x (100% more rewards)
          - Maximum possible: 5 days + 24-month lock = 3.5x (250% more rewards)

        ================================================================================
    """).strip())


def print_optimal_strategy():
    """Print the optimal strategy summary."""
    print(dedent("""

        ============================================================
        OPTIMAL STAKING STRATEGY
        ============================================================

        To maximize your staking rewards:

        1. TRADING ACTIVITY (contributes up to +0.5)
           - Trade once per day
           - Trade on 5 different days per week
           - Any trade size counts (use minimum)
           - Result: +50% more rewards

        2. LOCKED STAKING (contributes up to +2.0)
           - Lock your APEX tokens
           - Longer lock = higher multiplier
           - 24-month lock = +200% more rewards

        3. BOT AUTOMATION
           - Run this bot daily (24/7 trading enabled by default)
           - Automatically maintain 0.5 trading factor
           - Estimated weekly cost: < $0.50
           - Set and forget!

        ============================================================
    """).strip())


def main():
    """Main entry point."""
    args = parse_args()

    # Validate inputs
    if not 0 <= args.days <= 5:
        print("Error: days must be between 0 and 5")
        return 1

    if not 0 <= args.lock_months <= 24:
        print("Error: lock-months must be between 0 and 24")
        return 1

    if args.staked_amount <= 0:
        print("Error: staked-amount must be positive")
        return 1

    if args.compare:
        print_comparison_table()
    else:
        print_calculation(args.days, args.lock_months, args.staked_amount)

    print_optimal_strategy()

    return 0


if __name__ == "__main__":
    sys.exit(main())
