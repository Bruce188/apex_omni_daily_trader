"""
Trade Data Collection for ApexOmni Trading Bot.

This module handles recording trade executions and maintaining trade history
with proper weekly cycle tracking for staking factor optimization.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from data.models import Trade, TradeResult, WeeklyTradeRecord
from data.storage import Storage

logger = logging.getLogger(__name__)


class DataCollector:
    """
    Collects and manages trade execution data.

    This class is responsible for:
    - Recording trade executions
    - Tracking daily trading activity
    - Managing weekly cycle boundaries
    - Providing trade history access

    The collector integrates with the Storage module for persistence
    and ensures proper tracking of the Trading Activity Factor.

    Attributes:
        storage: Storage instance for data persistence
    """

    def __init__(self, storage: Optional[Storage] = None, data_dir: Optional[str] = None):
        """
        Initialize the data collector.

        Args:
            storage: Optional Storage instance. Creates new one if not provided.
            data_dir: Directory for data storage (only used if storage not provided)
        """
        self.storage = storage or Storage(data_dir)
        self._current_week_record: Optional[WeeklyTradeRecord] = None
        logger.info("DataCollector initialized")

    @property
    def current_week_record(self) -> WeeklyTradeRecord:
        """
        Get or create the current week's trade record.

        Lazy-loads the record from storage and caches it.
        Automatically creates a new record if the week has changed.

        Returns:
            The current week's trade record
        """
        week_start, week_end = Storage.get_current_week_boundaries()

        # Check if we need to refresh the cached record
        if self._current_week_record is None:
            self._current_week_record = self.storage.get_current_week_record()
        elif self._current_week_record.week_start != week_start:
            # New week started, get fresh record
            logger.info("New staking week detected, refreshing record")
            self._current_week_record = self.storage.get_current_week_record()

        return self._current_week_record

    def record_trade(self, trade_result: TradeResult) -> bool:
        """
        Record a trade execution result.

        This method:
        1. Saves the trade to persistent history
        2. Updates the current week's record
        3. Updates the days traded count
        4. Marks today as traded (if successful)

        Args:
            trade_result: The result of the executed trade

        Returns:
            True if recording was successful
        """
        try:
            # Save individual trade
            if not self.storage.save_trade(trade_result):
                logger.error("Failed to save trade to history")
                return False

            # Update weekly record
            self.current_week_record.add_trade(trade_result)

            if not self.storage.save_weekly_record(self.current_week_record):
                logger.error("Failed to update weekly record")
                return False

            # Mark traded today (if successful)
            if trade_result.success:
                self.storage.mark_traded_today()
                logger.info(
                    f"Trade recorded: {trade_result.trade.symbol} "
                    f"Day {trade_result.trade.day_number} - "
                    f"Days traded this week: {self.get_days_traded()}"
                )
            else:
                logger.warning(f"Failed trade recorded: {trade_result.error}")

            return True

        except Exception as e:
            logger.error(f"Error recording trade: {e}")
            return False

    def get_days_traded(self) -> int:
        """
        Get the number of days traded in the current week.

        Returns:
            Count of unique days with successful trades (0-5)
        """
        return self.current_week_record.num_days_traded

    def get_trading_activity_factor(self) -> float:
        """
        Calculate the current Trading Activity Factor.

        Formula: 0.1 * days_traded (max 0.5)

        Returns:
            Current Trading Activity Factor (0.0 to 0.5)
        """
        return self.current_week_record.trading_activity_factor

    def has_traded_today(self) -> bool:
        """
        Check if a successful trade has been executed today.

        Uses 8AM UTC as the day boundary per ApeX staking rules.

        Returns:
            True if already traded today
        """
        return self.storage.has_traded_today()

    def get_weekly_trades(self) -> List[TradeResult]:
        """
        Get all trades for the current week.

        Returns:
            List of trade results for the current staking week
        """
        return self.current_week_record.trades

    def get_weekly_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the current week's trading activity.

        Returns:
            Dictionary containing:
            - week_start: Start of the staking week
            - week_end: End of the staking week
            - days_traded: Number of unique days traded
            - trading_activity_factor: Current TAF (0.0-0.5)
            - trades_count: Total trades executed
            - success_count: Successful trades
            - failure_count: Failed trades
            - total_volume: Total traded volume
            - total_fees: Total fees paid
            - remaining_days: Days needed to reach max factor
        """
        record = self.current_week_record

        return {
            "week_start": record.week_start.isoformat(),
            "week_end": record.week_end.isoformat(),
            "days_traded": record.num_days_traded,
            "trading_activity_factor": record.trading_activity_factor,
            "trades_count": len(record.trades),
            "success_count": record.success_count,
            "failure_count": record.failure_count,
            "total_volume": record.total_volume,
            "total_fees": record.total_fees,
            "remaining_days": max(0, 5 - record.num_days_traded),
            "max_factor_achieved": record.num_days_traded >= 5,
        }

    def get_trade_history(self, limit: int = 100) -> List[TradeResult]:
        """
        Get trade history with optional limit.

        Args:
            limit: Maximum number of trades to return

        Returns:
            List of trade results, most recent first
        """
        return self.storage.get_recent_trades(limit)

    def get_all_weekly_records(self) -> List[WeeklyTradeRecord]:
        """
        Get all historical weekly records.

        Returns:
            List of all weekly trade records
        """
        return self.storage.get_all_weekly_records()

    def get_historical_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all historical trading activity.

        Returns:
            Dictionary containing historical statistics
        """
        records = self.get_all_weekly_records()

        if not records:
            return {
                "total_weeks": 0,
                "total_trades": 0,
                "total_volume": 0.0,
                "total_fees": 0.0,
                "weeks_with_max_factor": 0,
                "average_days_traded": 0.0,
            }

        total_trades = sum(len(r.trades) for r in records)
        total_volume = sum(r.total_volume for r in records)
        total_fees = sum(r.total_fees for r in records)
        weeks_with_max = sum(1 for r in records if r.num_days_traded >= 5)
        avg_days = sum(r.num_days_traded for r in records) / len(records)

        return {
            "total_weeks": len(records),
            "total_trades": total_trades,
            "total_volume": total_volume,
            "total_fees": total_fees,
            "weeks_with_max_factor": weeks_with_max,
            "max_factor_percentage": (weeks_with_max / len(records)) * 100,
            "average_days_traded": avg_days,
            "average_trading_factor": min(0.1 * avg_days, 0.5),
        }

    def get_next_trade_time(self) -> Optional[datetime]:
        """
        Get the next recommended trade time.

        Returns:
            Datetime of next trade, or None if already at max factor
        """
        if self.get_days_traded() >= 5:
            # Already at max factor this week
            week_start, week_end = Storage.get_current_week_boundaries()
            # Return next week's first trade time (Monday 9AM UTC)
            next_trade = week_end.replace(hour=9, minute=0, second=0)
            return next_trade

        if self.has_traded_today():
            # Already traded today, suggest tomorrow
            tomorrow = datetime.utcnow() + timedelta(days=1)
            return tomorrow.replace(hour=9, minute=0, second=0, microsecond=0)

        # Can trade now
        return datetime.utcnow()

    def get_remaining_trade_days(self) -> List[str]:
        """
        Get the remaining days that need trades this week.

        Returns:
            List of day names still needing trades
        """
        traded_days = self.current_week_record.days_traded
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

        # Get current day of week
        current_day = datetime.utcnow().weekday()

        remaining = []
        for day_num in range(5):  # Monday (0) to Friday (4)
            if day_num not in traded_days:
                # Only include if it's today or future
                if day_num >= current_day:
                    remaining.append(day_names[day_num])
                elif current_day == day_num and not self.has_traded_today():
                    remaining.append(day_names[day_num])

        return remaining

    def reset_week(self) -> bool:
        """
        Force reset to a new week (for testing or error recovery).

        Creates a fresh weekly record for the current week.

        Returns:
            True if reset was successful
        """
        try:
            week_start, week_end = Storage.get_current_week_boundaries()
            self._current_week_record = WeeklyTradeRecord(
                week_start=week_start,
                week_end=week_end
            )
            return self.storage.save_weekly_record(self._current_week_record)
        except Exception as e:
            logger.error(f"Failed to reset week: {e}")
            return False

    def validate_trade_day(self, day_number: int) -> bool:
        """
        Validate if a trade can be executed for the given day.

        Checks:
        - Day number is valid (1-5)
        - Day hasn't already been traded
        - It's actually that day of the week

        Args:
            day_number: The day number (1=Monday, 5=Friday)

        Returns:
            True if trade is valid for this day
        """
        if not 1 <= day_number <= 5:
            logger.warning(f"Invalid day number: {day_number}")
            return False

        # Convert day_number (1-5) to weekday (0-4)
        expected_weekday = day_number - 1
        current_weekday = datetime.utcnow().weekday()

        if current_weekday != expected_weekday:
            logger.warning(
                f"Day mismatch: trade is for day {day_number} "
                f"but current weekday is {current_weekday}"
            )
            return False

        if expected_weekday in self.current_week_record.days_traded:
            logger.warning(f"Day {day_number} already traded this week")
            return False

        return True
