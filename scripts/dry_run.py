#!/usr/bin/env python3
"""
ApexOmni Trading Bot - Dry Run Script

Simulate trades without executing real orders.
Useful for testing configuration and strategy logic.

Usage:
    python scripts/dry_run.py                   # Simulate today's trade
    python scripts/dry_run.py --all             # Simulate full week
    python scripts/dry_run.py --validate        # Validate config only
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bot.config import Config
from bot.api_client import MockApexOmniClient
from bot.trade_executor import TradeExecutor
from bot.strategy import StakingOptimizationStrategy
from bot.utils import setup_logging, get_logger, calculate_trading_activity_factor


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="ApexOmni Trading Bot - Dry Run Simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to configuration file"
    )

    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Simulate full week of trades"
    )

    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate configuration and exit"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    return parser.parse_args()


def validate_config(config: Config) -> bool:
    """Validate configuration and report issues."""
    logger = get_logger()

    logger.info("")
    logger.info("=" * 60)
    logger.info("CONFIGURATION VALIDATION")
    logger.info("=" * 60)

    errors = config.validate()

    if not errors:
        logger.info("Configuration is valid!")
        logger.info("")
        config.print_summary()
        return True

    logger.error(f"Found {len(errors)} configuration error(s):")
    for i, error in enumerate(errors, 1):
        logger.error(f"  {i}. {error}")

    logger.info("")
    logger.info("Current configuration:")
    config.print_summary()

    return False


def simulate_today(config: Config, executor: TradeExecutor, strategy: StakingOptimizationStrategy):
    """Simulate today's trade."""
    logger = get_logger()

    logger.info("")
    logger.info("=" * 60)
    logger.info("SIMULATING TODAY'S TRADE")
    logger.info("=" * 60)

    # Get current status
    days_traded = 0  # Assume no trades yet for simulation
    status = strategy.get_status(days_traded)

    logger.info(f"Current Day: {status.current_day}")
    logger.info(f"Is Trade Day: {'Yes' if status.is_trade_day else 'No'}")
    logger.info("")

    if not status.is_trade_day:
        logger.info("Today is not a scheduled trade day.")
        logger.info("In production, the bot would skip trading.")
        return

    # Step 1: Determine best symbol FIRST based on balance
    symbol_result = executor.determine_best_symbol()
    if symbol_result is None:
        logger.error(
            "No tradeable symbol found. Check balance - it may be too low to trade."
        )
        return

    symbol_name, min_order_size, symbol_config = symbol_result
    logger.info(f"Selected symbol: {symbol_name} (min size: {min_order_size})")

    # Step 2: Generate trade with the pre-selected symbol
    trade = strategy.get_trade_for_today(
        symbol_override=symbol_name,
        size_override=min_order_size
    )
    if trade is None:
        logger.warning("Could not generate trade for today")
        return

    logger.info("")
    logger.info("Trade Details:")
    logger.info(f"  Symbol: {trade.symbol}")
    logger.info(f"  Side: {trade.side}")
    logger.info(f"  Size: {trade.size}")
    logger.info(f"  Type: {trade.order_type}")
    logger.info("  Close Position: Always (hardcoded)")
    logger.info("  Leverage: 1x (hardcoded)")
    logger.info("")

    # Simulate execution
    logger.info("Simulating trade execution...")
    result = executor.execute_trade(trade)

    logger.info("")
    if result.success:
        logger.info("SIMULATION RESULT: Trade would succeed")
        logger.info(f"  Mock Order ID: {result.order_id}")
        logger.info(f"  Mock Price: {result.executed_price}")
        logger.info(f"  Mock Fees: {result.total_fees}")
    else:
        logger.error(f"SIMULATION RESULT: Trade would fail - {result.error}")


def simulate_full_week(config: Config, executor: TradeExecutor, strategy: StakingOptimizationStrategy):
    """Simulate a full week of trades."""
    logger = get_logger()

    logger.info("")
    logger.info("=" * 60)
    logger.info("SIMULATING FULL WEEK OF TRADES")
    logger.info("=" * 60)

    # Generate weekly schedule
    trades = strategy.generate_weekly_schedule()

    logger.info(f"Scheduled {len(trades)} trades for the week")
    logger.info("")

    total_fees = 0
    successful_trades = 0

    for trade in trades:
        logger.info(f"--- Day {trade.day_number} ---")
        result = executor.execute_trade(trade)

        if result.success:
            successful_trades += 1
            total_fees += float(result.total_fees)

        logger.info("")

    # Summary
    logger.info("=" * 60)
    logger.info("WEEKLY SIMULATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total Trades: {len(trades)}")
    logger.info(f"Successful: {successful_trades}")
    logger.info(f"Failed: {len(trades) - successful_trades}")
    logger.info(f"Total Estimated Fees: ${total_fees:.4f}")
    logger.info("")

    # Factor calculation
    factor = calculate_trading_activity_factor(successful_trades)
    logger.info(f"Trading Activity Factor: {factor:.1f}")
    logger.info(f"Total Staking Factor (base): {1.0 + factor:.1f}")
    logger.info("")
    logger.info("Impact: Your staking rewards would be multiplied by {:.1f}x".format(1.0 + factor))
    logger.info("=" * 60)


def main():
    """Main entry point."""
    args = parse_args()

    # Load configuration
    config = Config.load(args.config)

    # Always force dry-run mode
    config.safety.dry_run = True

    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(level=log_level)
    logger = get_logger()

    logger.info("=" * 60)
    logger.info("ApexOmni Trading Bot - DRY RUN MODE")
    logger.info("=" * 60)
    logger.info("No real trades will be executed.")
    logger.info("")

    # Handle --validate flag
    if args.validate:
        is_valid = validate_config(config)
        return 0 if is_valid else 1

    # Validate anyway
    errors = config.validate()
    if errors:
        logger.warning(f"Configuration has {len(errors)} issues:")
        for error in errors:
            logger.warning(f"  - {error}")
        logger.warning("Continuing with simulation anyway...")
        logger.info("")

    # Create mock components
    client = MockApexOmniClient(config.api)
    executor = TradeExecutor(client, config)
    strategy = StakingOptimizationStrategy(config)

    # Print config summary
    config.print_summary()

    if args.all:
        simulate_full_week(config, executor, strategy)
    else:
        simulate_today(config, executor, strategy)

    # Show weekly plan
    logger.info("")
    strategy.print_weekly_plan(0)

    return 0


if __name__ == "__main__":
    sys.exit(main())
