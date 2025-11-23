#!/usr/bin/env python3
"""
Continuous trading daemon for 24/7 operation.

This script runs the trading bot in a continuous loop, executing trades
at configured intervals. Designed for Docker deployment.

Usage:
    python scripts/run_continuous.py [--check-interval SECONDS]
"""

import sys
import time
import signal
import argparse
from pathlib import Path
from datetime import datetime
from textwrap import dedent

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bot.config import Config
from bot.api_client import ApexOmniClient, MockApexOmniClient
from bot.trade_executor import TradeExecutor
from bot.strategy import StakingOptimizationStrategy
from bot.utils import setup_logging, get_current_utc_time, get_logger, warn_if_live_mainnet
from data.storage import Storage


class TradingDaemon:
    """
    Continuous trading daemon.

    Runs in a loop, checking if trades should be executed
    based on the configured schedule mode and intervals.
    """

    def __init__(self, config: Config, check_interval: int = 300):
        """
        Initialize the trading daemon.

        Args:
            config: Bot configuration
            check_interval: Seconds between trade checks
        """
        self.config = config
        self.check_interval = check_interval  # Seconds between checks
        self.running = True

        # Setup components
        setup_logging(config.log_level)
        self.logger = get_logger()
        self.storage = Storage(config.data_dir)

        # Load last trade time from storage (survives container restarts)
        state = self.storage.get_state()
        last_trade_str = state.get("last_trade_time")
        if last_trade_str:
            try:
                self.last_trade_time = datetime.fromisoformat(last_trade_str)
                self.logger.info(f"Restored last_trade_time from storage: {self.last_trade_time}")
            except (ValueError, TypeError):
                self.last_trade_time = None
        else:
            self.last_trade_time = None

        # Initialize API client
        if config.safety.dry_run:
            self.logger.info("Running in DRY-RUN mode")
            self.client = MockApexOmniClient(config.api)
        else:
            self.logger.info("Running in LIVE mode")
            self.client = ApexOmniClient(config.api)

        self.executor = TradeExecutor(self.client, config)
        self.strategy = StakingOptimizationStrategy(config)

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False

    def run(self):
        """Main daemon loop."""
        self.logger.info(dedent(f"""
            ========================================
            ApexOmni Trading Daemon Started
            ========================================
            Mode: {self.config.schedule.mode}
            Trade Interval: {self.config.schedule.trade_interval_hours}h
            Check Interval: {self.check_interval}s
            Dry Run: {self.config.safety.dry_run}
            ========================================
        """).strip())

        while self.running:
            try:
                self._check_and_trade()

                # Sleep until next check
                self.logger.debug(f"Sleeping for {self.check_interval} seconds...")

                # Use interruptible sleep
                for _ in range(self.check_interval):
                    if not self.running:
                        break
                    time.sleep(1)

            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                # Error backoff - wait 60 seconds before retrying
                time.sleep(60)

        self.logger.info("Trading daemon stopped.")

    def _check_and_trade(self):
        """Check if we should trade and execute if needed."""
        # Get current stats
        weekly_record = self.storage.get_current_week_record()
        unique_days = len(weekly_record.days_traded) if weekly_record else 0

        # CRITICAL: Check if already traded today (for daily mode)
        already_traded_today = self.storage.has_traded_today()
        if self.config.schedule.mode == "daily" and already_traded_today:
            self.logger.debug("Trade check: SKIP - Already traded today (daily mode)")
            return

        # Check if we should trade
        should_trade, reason = self.strategy.should_trade_now(
            last_trade_time=self.last_trade_time,
            unique_days_this_week=unique_days
        )

        if should_trade:
            self.logger.info(f"Trade check: PROCEED - {reason}")
            self._execute_trade(unique_days)
        else:
            self.logger.debug(f"Trade check: SKIP - {reason}")

    def _execute_trade(self, day_number: int):
        """Execute a single trade."""
        try:
            # Step 1: Determine the best symbol FIRST based on balance
            symbol_result = self.executor.determine_best_symbol()
            if symbol_result is None:
                self.logger.error(
                    "No tradeable symbol found. Check balance - it may be too low to trade."
                )
                return

            symbol_name, min_order_size, symbol_config = symbol_result
            self.logger.info(
                f"Selected symbol: {symbol_name} (min size: {min_order_size})"
            )

            # Step 2: Generate trade with the pre-selected symbol
            trade = self.strategy.get_trade_for_today(
                day_number=day_number + 1,
                symbol_override=symbol_name,
                size_override=min_order_size
            )
            if trade is None:
                self.logger.warning("Strategy returned no trade for today")
                return

            self.logger.info(f"Executing trade: {trade.symbol} {trade.side} {trade.size}")

            # Step 3: Execute the trade (symbol already validated)
            result = self.executor.execute_trade(trade)

            if result.success:
                self.logger.info(dedent(f"""
                    Trade executed successfully!
                    - Order ID: {result.order_id}
                    - Price: {result.executed_price}
                    - Fees: {result.fees}
                """).strip())
                self.last_trade_time = get_current_utc_time()

                # CRITICAL: Persist state to survive container restarts
                self.storage.update_state({
                    "last_trade_time": self.last_trade_time.isoformat()
                })
                self.storage.mark_traded_today()
                self.logger.info("Trade state persisted to storage")
            else:
                self.logger.error(f"Trade failed: {result.error}")

        except Exception as e:
            self.logger.error(f"Error executing trade: {e}", exc_info=True)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="ApexOmni Continuous Trading Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=dedent("""
            Examples:
                # Run with default settings
                python scripts/run_continuous.py

                # Run with custom check interval (10 minutes)
                python scripts/run_continuous.py --check-interval 600

                # Run with custom config file
                python scripts/run_continuous.py --config /path/to/config.yaml
        """)
    )

    parser.add_argument(
        "--check-interval",
        type=int,
        default=300,
        help="Seconds between trade checks (default: 300)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config file"
    )

    args = parser.parse_args()

    # Load configuration
    config = Config.load(args.config)

    # Validate configuration
    errors = config.validate()
    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    # Check for live mainnet and show warning
    setup_logging(config.log_level)
    logger = get_logger()
    if not warn_if_live_mainnet(config, logger):
        sys.exit(0)

    # Run daemon
    daemon = TradingDaemon(config, args.check_interval)
    daemon.run()


if __name__ == "__main__":
    main()
