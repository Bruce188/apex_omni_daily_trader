"""
5-Trade Staking Optimization Strategy.

Generates optimal trades to maximize the Trading Activity Factor
on ApexOmni's staking system.

Supports:
- Daily mode: One trade per day at scheduled time
- Continuous mode: Trades at regular intervals 24/7
"""

from datetime import datetime, timedelta
from decimal import Decimal
from dataclasses import dataclass
from textwrap import dedent
from typing import Optional, Tuple

from bot.config import Config
from bot.trade_executor import Trade
from bot.utils import (
    get_logger,
    get_current_utc_time,
    get_weekly_round_start,
    get_weekly_round_end,
    get_current_staking_day,
    is_trade_day,
    calculate_trading_activity_factor,
    calculate_total_staking_factor,
)


@dataclass
class StrategyStatus:
    """Current status of the staking optimization strategy."""
    week_start: datetime
    week_end: datetime
    current_day: int
    days_traded: int
    days_remaining: int
    trading_activity_factor: float
    expected_final_factor: float
    is_trade_day: bool
    should_trade_today: bool
    next_trade_day: Optional[datetime]


class StakingOptimizationStrategy:
    """
    Generate 5 trades to maximize Trading Activity Factor.

    Strategy:
    - Execute 1 trade per day on configured trade days (default: all 7 days)
    - Use minimum trade size to reduce risk
    - Each trade adds +0.1 to Trading Activity Factor
    - After 5 unique days: Factor = 0.5 (maximum)
    """

    # Maximum days that count toward trading factor
    MAX_TRADE_DAYS = 5

    # Factor increment per day traded
    FACTOR_PER_DAY = 0.1

    # Maximum trading activity factor
    MAX_FACTOR = 0.5

    def __init__(self, config: Config):
        """
        Initialize the strategy.

        Args:
            config: Bot configuration
        """
        self.config = config
        self.logger = get_logger()

    def get_status(self, days_already_traded: int = 0) -> StrategyStatus:
        """
        Get current strategy status.

        Args:
            days_already_traded: Number of days already traded this week

        Returns:
            StrategyStatus with current state
        """
        now = get_current_utc_time()
        week_start = get_weekly_round_start()
        week_end = get_weekly_round_end()
        current_day = get_current_staking_day()

        # Calculate remaining trade days
        days_remaining = self._count_remaining_trade_days(current_day)
        trades_needed = self.MAX_TRADE_DAYS - days_already_traded

        # Current factor
        current_factor = calculate_trading_activity_factor(days_already_traded)

        # Expected final factor (if we complete all remaining trades)
        final_trades = min(
            days_already_traded + min(days_remaining, trades_needed),
            self.MAX_TRADE_DAYS
        )
        expected_factor = calculate_trading_activity_factor(final_trades)

        # Check if today is a trade day
        today_is_trade_day = is_trade_day(self.config.schedule.trade_days)

        # Should we trade today?
        should_trade = (
            today_is_trade_day and
            days_already_traded < self.MAX_TRADE_DAYS and
            current_day <= 7
        )

        # Find next trade day
        next_trade = self._get_next_trade_day() if not should_trade else None

        return StrategyStatus(
            week_start=week_start,
            week_end=week_end,
            current_day=current_day,
            days_traded=days_already_traded,
            days_remaining=days_remaining,
            trading_activity_factor=current_factor,
            expected_final_factor=expected_factor,
            is_trade_day=today_is_trade_day,
            should_trade_today=should_trade,
            next_trade_day=next_trade
        )

    def get_trade_for_today(
        self,
        day_number: int = None,
        symbol_override: Optional[str] = None,
        size_override: Optional[Decimal] = None
    ) -> Optional[Trade]:
        """
        Generate trade parameters for today.

        Args:
            day_number: Override day number (for testing)
            symbol_override: Override symbol (from pre-selection based on balance)
            size_override: Override size (typically min_order_size for selected symbol)

        Returns:
            Trade to execute, or None if shouldn't trade today
        """
        if day_number is None:
            day_number = get_current_staking_day()

        # Check if this is a trade day
        if not is_trade_day(self.config.schedule.trade_days):
            self.logger.info("Today is not a configured trade day")
            return None

        # Use override values if provided (from pre-selection)
        symbol = symbol_override if symbol_override else self.config.trading.symbol
        size = size_override if size_override else self.config.trading.size

        # Generate trade (leverage and close_position are hardcoded)
        trade = Trade(
            symbol=symbol,
            side=self.config.trading.side,
            order_type=self.config.trading.order_type,
            size=size,
            day_number=day_number,
            # REMOVED: leverage - hardcoded to 1
            # REMOVED: close_position - hardcoded to True
        )

        self.logger.info("Generated trade for today:")
        self.logger.info(f"  Symbol: {trade.symbol}")
        self.logger.info(f"  Side: {trade.side}")
        self.logger.info(f"  Size: {trade.size}")
        self.logger.info(f"  Type: {trade.order_type}")

        return trade

    def generate_weekly_schedule(self) -> list[Trade]:
        """
        Generate all 5 trades for the week.

        Returns:
            List of Trade objects for the week
        """
        trades = []

        for day in range(1, 6):  # Days 1-5 (Mon-Fri)
            trade = Trade(
                symbol=self.config.trading.symbol,
                side=self.config.trading.side,
                order_type=self.config.trading.order_type,
                size=self.config.trading.size,
                day_number=day,
                # REMOVED: leverage - hardcoded to 1
                # REMOVED: close_position - hardcoded to True
            )
            trades.append(trade)

        return trades

    def should_trade_now(
        self,
        last_trade_time: Optional[datetime] = None,
        unique_days_this_week: int = 0
    ) -> Tuple[bool, str]:
        """
        Determine if the bot should execute a trade now.

        Args:
            last_trade_time: Timestamp of last successful trade
            unique_days_this_week: Number of unique days traded this week

        Returns:
            Tuple of (should_trade: bool, reason: str)
        """
        if self.config.schedule.mode == "continuous":
            return self._check_continuous_mode(last_trade_time, unique_days_this_week)
        else:
            return self._check_daily_mode(unique_days_this_week)

    def _check_continuous_mode(
        self,
        last_trade_time: Optional[datetime],
        unique_days_this_week: int
    ) -> Tuple[bool, str]:
        """Check if should trade in continuous mode."""
        now = get_current_utc_time()

        # Check if today is a configured trade day
        if now.weekday() not in self.config.schedule.trade_days:
            return False, f"Day {now.weekday()} not in configured trade_days"

        # Check if we've hit max factor and should stop
        if unique_days_this_week >= self.MAX_TRADE_DAYS:
            if not self.config.schedule.continue_after_max_factor:
                return False, dedent(f"""
                    Max Trading Activity Factor achieved ({unique_days_this_week} days).
                    Waiting for next weekly reset.
                """).strip()

        # Check interval since last trade
        if last_trade_time:
            hours_since_last = (now - last_trade_time).total_seconds() / 3600
            required_interval = self.config.schedule.trade_interval_hours

            if hours_since_last < required_interval:
                remaining = required_interval - hours_since_last
                return False, f"Only {hours_since_last:.1f}h since last trade. Need {remaining:.1f}h more."

        return True, "Ready to trade (continuous mode)"

    def _check_daily_mode(self, unique_days_this_week: int) -> Tuple[bool, str]:
        """Check if should trade in daily mode."""
        now = get_current_utc_time()

        # Check if today is a configured trade day
        if now.weekday() not in self.config.schedule.trade_days:
            return False, f"Day {now.weekday()} not in configured trade_days"

        # Check if we've hit max factor
        if unique_days_this_week >= self.MAX_TRADE_DAYS:
            if not self.config.schedule.continue_after_max_factor:
                return False, "Max Trading Activity Factor achieved"

        # Check if it's the right time
        trade_hour, trade_minute = map(int, self.config.schedule.trade_time.split(":"))
        if now.hour < trade_hour or (now.hour == trade_hour and now.minute < trade_minute):
            return False, f"Before scheduled trade time ({self.config.schedule.trade_time})"

        return True, "Ready to trade (daily mode)"

    def get_status_summary(self, unique_days_this_week: int) -> str:
        """Get a human-readable status summary."""
        factor = min(unique_days_this_week * Decimal("0.1"), Decimal("0.5"))

        return dedent(f"""
            === Staking Optimization Status ===
            Mode: {self.config.schedule.mode}
            Days traded this week: {unique_days_this_week}/{self.MAX_TRADE_DAYS}
            Trading Activity Factor: {factor}
            Continue after max: {self.config.schedule.continue_after_max_factor}
            Trade interval: {self.config.schedule.trade_interval_hours}h
        """).strip()

    def calculate_expected_multiplier(
        self,
        days_traded: int,
        time_factor: float = 0.0
    ) -> float:
        """
        Calculate expected total staking factor.

        Args:
            days_traded: Number of days traded this week
            time_factor: Time Factor from locked staking

        Returns:
            Total staking factor
        """
        return calculate_total_staking_factor(time_factor, days_traded)

    def print_weekly_plan(self, days_already_traded: int = 0) -> None:
        """Print the weekly trading plan."""
        status = self.get_status(days_already_traded)

        self.logger.info("=" * 60)
        self.logger.info("WEEKLY STAKING OPTIMIZATION PLAN")
        self.logger.info("=" * 60)

        self.logger.info(f"Week: {status.week_start.strftime('%Y-%m-%d')} to {status.week_end.strftime('%Y-%m-%d')}")
        self.logger.info(f"Current Day: {status.current_day}")
        self.logger.info("")

        # Progress bar
        progress = "=" * status.days_traded + "-" * (5 - status.days_traded)
        self.logger.info(f"Progress: [{progress}] {status.days_traded}/5 days")
        self.logger.info("")

        # Current status
        self.logger.info("Current Trading Activity Factor: {:.1f}".format(status.trading_activity_factor))
        self.logger.info("Expected Final Factor: {:.1f}".format(status.expected_final_factor))
        self.logger.info("")

        # Today's action
        if status.should_trade_today:
            self.logger.info("ACTION: Execute trade today!")
        elif status.is_trade_day:
            if status.days_traded >= 5:
                self.logger.info("ACTION: Maximum trades reached for this week")
            else:
                self.logger.info("ACTION: Already traded today")
        else:
            self.logger.info(f"ACTION: No trade today (not a trade day)")
            if status.next_trade_day:
                self.logger.info(f"Next trade: {status.next_trade_day.strftime('%Y-%m-%d %H:%M UTC')}")

        self.logger.info("")

        # Impact table
        self.logger.info("Impact Analysis:")
        self.logger.info("-" * 40)
        self.logger.info(f"{'Days Traded':<15} {'Activity Factor':<15} {'Total Factor*':<15}")
        self.logger.info("-" * 40)

        for days in range(6):
            factor = calculate_trading_activity_factor(days)
            total = calculate_total_staking_factor(0.0, days)
            marker = " <-- current" if days == status.days_traded else ""
            self.logger.info(f"{days:<15} {factor:<15.1f} {total:<15.1f}{marker}")

        self.logger.info("-" * 40)
        self.logger.info("* Total Factor assumes Time Factor = 0 (no locked staking)")
        self.logger.info("=" * 60)

    def estimate_weekly_cost(self, fee_rate: float = 0.001) -> Decimal:
        """
        Estimate weekly trading cost.

        Args:
            fee_rate: Fee rate per trade (default 0.1%)

        Returns:
            Estimated total weekly cost
        """
        # Get current price estimate (use mock if not connected)
        trade_value = self.config.trading.size * Decimal("95000")  # Assume ~$95k BTC

        # Cost per trade (open + close)
        cost_per_trade = trade_value * Decimal(str(fee_rate)) * 2

        # Total for 5 trades
        return cost_per_trade * 5

    def _count_remaining_trade_days(self, current_day: int) -> int:
        """Count remaining trade days this week."""
        remaining = 0
        for day in range(current_day, 8):  # Days up to 7
            day_of_week = (day - 1) % 7  # Convert to 0-6
            if day_of_week in self.config.schedule.trade_days:
                remaining += 1
        return remaining

    def _get_next_trade_day(self) -> Optional[datetime]:
        """Get the next scheduled trade day."""
        now = get_current_utc_time()
        week_end = get_weekly_round_end()

        # Check remaining days this week
        for days_ahead in range(1, 8):
            next_day = now + timedelta(days=days_ahead)

            if next_day >= week_end:
                return None

            if next_day.weekday() in self.config.schedule.trade_days:
                # Parse trade time
                hours, minutes = map(int, self.config.schedule.trade_time.split(":"))
                return next_day.replace(hour=hours, minute=minutes, second=0, microsecond=0)

        return None


def create_trade_from_config(config: Config, day_number: int = 1) -> Trade:
    """
    Factory function to create a trade from configuration.

    Args:
        config: Bot configuration
        day_number: Day number in the staking week

    Returns:
        Trade object

    Note: leverage (1x) and close_position (True) are hardcoded for safety.
    """
    return Trade(
        symbol=config.trading.symbol,
        side=config.trading.side,
        order_type=config.trading.order_type,
        size=config.trading.size,
        day_number=day_number,
        # REMOVED: leverage - hardcoded to 1
        # REMOVED: close_position - hardcoded to True
    )
