#!/usr/bin/env python3
"""
ApexOmni Trading Bot - Main Entry Point

Executes today's trade for staking factor optimization.

Usage:
    python scripts/run_bot.py                    # Default (dry-run)
    python scripts/run_bot.py --live             # Live trading
    python scripts/run_bot.py --dry-run          # Explicit dry-run
    python scripts/run_bot.py --config config.yaml   # Custom config
    python scripts/run_bot.py --status           # Show status only
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bot.config import Config
from bot.api_client import create_client
from bot.trade_executor import TradeExecutor
from bot.strategy import StakingOptimizationStrategy
from bot.utils import setup_logging, get_logger, warn_if_live_mainnet


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="ApexOmni Trading Bot - Staking Factor Optimization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_bot.py                  # Dry-run mode (default)
  python scripts/run_bot.py --live           # Execute real trades
  python scripts/run_bot.py --status         # Show current status
  python scripts/run_bot.py --plan           # Show weekly plan
  python scripts/run_bot.py --force          # Trade even if already traded today
        """
    )

    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to configuration file"
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help="Execute real trades (disable dry-run)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate trades without executing (default)"
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current status and exit"
    )

    parser.add_argument(
        "--plan",
        action="store_true",
        help="Show weekly plan and exit"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Execute trade even if already traded today"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    return parser.parse_args()


def show_status(config: Config, executor: TradeExecutor, strategy: StakingOptimizationStrategy):
    """Display current status."""
    logger = get_logger()

    days_traded = executor.get_week_trades_count()
    status = strategy.get_status(days_traded)

    logger.info("")
    logger.info("=" * 60)
    logger.info("APEXOMNI STAKING BOT STATUS")
    logger.info("=" * 60)
    logger.info("")
    logger.info(f"Week Period: {status.week_start.strftime('%Y-%m-%d %H:%M')} to {status.week_end.strftime('%Y-%m-%d %H:%M')} UTC")
    logger.info(f"Current Day: {status.current_day} of 7")
    logger.info("")
    logger.info(f"Days Traded This Week: {status.days_traded} / 5")
    logger.info(f"Remaining Trade Days: {status.days_remaining}")
    logger.info("")
    logger.info(f"Current Trading Activity Factor: {status.trading_activity_factor:.1f}")
    logger.info(f"Expected Final Factor: {status.expected_final_factor:.1f}")
    logger.info("")
    logger.info(f"Is Trade Day: {'Yes' if status.is_trade_day else 'No'}")
    logger.info(f"Should Trade Today: {'Yes' if status.should_trade_today else 'No'}")
    logger.info(f"Already Traded Today: {'Yes' if executor.has_traded_today() else 'No'}")
    logger.info("")

    if status.next_trade_day and not status.should_trade_today:
        logger.info(f"Next Trade: {status.next_trade_day.strftime('%Y-%m-%d %H:%M')} UTC")

    logger.info("=" * 60)


def main():
    """Main entry point."""
    args = parse_args()

    # Load configuration
    config = Config.load(args.config)

    # Setup logging
    log_level = "DEBUG" if args.verbose else config.log_level
    setup_logging(level=log_level, log_file=config.log_file)
    logger = get_logger()

    logger.info("=" * 60)
    logger.info("ApexOmni Trading Bot Starting")
    logger.info("=" * 60)

    # Handle dry-run/live mode
    if args.live:
        config.safety.dry_run = False
        logger.warning("LIVE TRADING MODE - Real trades will be executed!")
    elif args.dry_run or not args.live:
        config.safety.dry_run = True
        logger.info("DRY-RUN MODE - No real trades will be executed")

    # Validate configuration
    errors = config.validate()
    if errors:
        for error in errors:
            logger.error(f"Config error: {error}")

        # Only fail on critical errors if doing live trading
        if not config.safety.dry_run:
            logger.error("Cannot proceed with live trading due to configuration errors")
            return 1

        logger.warning("Proceeding with dry-run despite configuration errors")

    # Print configuration summary
    config.print_summary()

    # Check for live mainnet and show warning
    if not warn_if_live_mainnet(config, logger):
        return 0

    # Create components
    client = create_client(config.api, dry_run=config.safety.dry_run)
    executor = TradeExecutor(client, config)
    strategy = StakingOptimizationStrategy(config)

    # Test connection (if not dry-run)
    if not config.safety.dry_run:
        logger.info("Testing API connection...")
        if not client.test_connection():
            logger.error("API connection test failed")
            return 1
        logger.info("API connection successful")

    # Handle --status flag
    if args.status:
        show_status(config, executor, strategy)
        return 0

    # Handle --plan flag
    if args.plan:
        days_traded = executor.get_week_trades_count()
        strategy.print_weekly_plan(days_traded)
        return 0

    # Check if already traded today
    if executor.has_traded_today() and not args.force:
        logger.info("Already traded today. Use --force to trade again.")
        show_status(config, executor, strategy)
        return 0

    # Get strategy status
    days_traded = executor.get_week_trades_count()
    status = strategy.get_status(days_traded)

    # Check if we should trade
    if not status.should_trade_today and not args.force:
        logger.info("No trade scheduled for today.")
        show_status(config, executor, strategy)
        return 0

    # Check if max trades reached
    if days_traded >= 5:
        logger.info("Maximum trades (5) already reached this week.")
        show_status(config, executor, strategy)
        return 0

    # Step 1: Determine the best symbol FIRST based on balance
    symbol_result = executor.determine_best_symbol()
    if symbol_result is None:
        logger.error(
            "No tradeable symbol found. Check balance - it may be too low to trade."
        )
        return 1

    symbol_name, min_order_size, symbol_config = symbol_result
    logger.info(f"Selected symbol: {symbol_name} (min size: {min_order_size})")

    # Step 2: Generate trade with the pre-selected symbol
    trade = strategy.get_trade_for_today(
        day_number=days_traded + 1,
        symbol_override=symbol_name,
        size_override=min_order_size
    )
    if trade is None:
        logger.warning("Could not generate trade for today")
        return 1

    # Step 3: Execute trade
    logger.info("")
    logger.info("Executing trade...")
    result = executor.execute_trade(trade)

    # Report result
    if result.success:
        logger.info("")
        logger.info("Trade completed successfully!")
        logger.info(f"Order ID: {result.order_id}")
        logger.info(f"Total Fees: {result.total_fees}")
        logger.info("")

        # Show updated status
        days_traded = executor.get_week_trades_count()
        status = strategy.get_status(days_traded)
        logger.info(f"Trading Activity Factor: {status.trading_activity_factor:.1f}")
        logger.info(f"Trades this week: {days_traded}/5")

        return 0
    else:
        logger.error("")
        logger.error("Trade failed!")
        logger.error(f"Error: {result.error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
