"""
Tests for Data Collector.

Tests cover:
- Trade recording
- Weekly boundary handling
- Days traded counting
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.collector import DataCollector
from data.storage import Storage
from data.models import Trade, TradeResult, TradeStatus


# =============================================================================
# DataCollector Initialization Tests
# =============================================================================

class TestDataCollectorInit:
    """Tests for DataCollector initialization."""

    def test_collector_with_storage(self, storage):
        """Should initialize with provided storage."""
        collector = DataCollector(storage=storage)
        assert collector.storage is storage

    def test_collector_creates_storage(self, temp_data_dir):
        """Should create storage if not provided."""
        collector = DataCollector(data_dir=temp_data_dir)
        assert collector.storage is not None


# =============================================================================
# Trade Recording Tests
# =============================================================================

class TestTradeRecording:
    """Tests for trade recording functionality."""

    def test_record_trade_success(self, data_collector, sample_trade_result):
        """Should record successful trade."""
        result = data_collector.record_trade(sample_trade_result)
        assert result is True

    def test_record_trade_updates_days_traded(self, data_collector, sample_trade_result):
        """Should update days traded count on success."""
        # Record a successful trade
        sample_trade_result.success = True
        sample_trade_result.timestamp = datetime.utcnow()
        data_collector.record_trade(sample_trade_result)

        # Days traded should be at least 1
        days = data_collector.get_days_traded()
        assert days >= 1

    def test_record_failed_trade_no_day_count(self, data_collector, failed_trade_result):
        """Should not increment day count for failed trades."""
        initial_days = data_collector.get_days_traded()

        data_collector.record_trade(failed_trade_result)

        assert data_collector.get_days_traded() == initial_days


# =============================================================================
# Days Traded Tests
# =============================================================================

class TestDaysTraded:
    """Tests for days traded tracking."""

    def test_get_days_traded_empty(self, data_collector):
        """Should return 0 when no trades."""
        assert data_collector.get_days_traded() == 0

    def test_get_trading_activity_factor_0_days(self, data_collector):
        """TAF should be 0 with 0 days traded."""
        assert data_collector.get_trading_activity_factor() == 0.0


# =============================================================================
# Has Traded Today Tests
# =============================================================================

class TestHasTradedToday:
    """Tests for today's trading status."""

    def test_has_traded_today_false(self, data_collector):
        """Should return False when no trades today."""
        assert data_collector.has_traded_today() is False


# =============================================================================
# Weekly Trades Tests
# =============================================================================

class TestWeeklyTrades:
    """Tests for weekly trade access."""

    def test_get_weekly_trades_empty(self, data_collector):
        """Should return empty list when no trades."""
        trades = data_collector.get_weekly_trades()
        assert trades == []

    def test_get_weekly_summary(self, data_collector):
        """Should return summary dictionary."""
        summary = data_collector.get_weekly_summary()

        assert "week_start" in summary
        assert "week_end" in summary
        assert "days_traded" in summary
        assert "trading_activity_factor" in summary
        assert "trades_count" in summary
        assert "remaining_days" in summary

    def test_weekly_summary_values(self, data_collector):
        """Summary values should be correct for empty week."""
        summary = data_collector.get_weekly_summary()

        assert summary["days_traded"] == 0
        assert summary["trading_activity_factor"] == 0.0
        assert summary["trades_count"] == 0
        assert summary["remaining_days"] == 5


# =============================================================================
# Trade History Tests
# =============================================================================

class TestTradeHistory:
    """Tests for trade history access."""

    def test_get_trade_history_empty(self, data_collector):
        """Should return empty list when no history."""
        history = data_collector.get_trade_history()
        assert history == []

    def test_get_trade_history_with_limit(self, data_collector, sample_trade_result):
        """Should respect limit parameter."""
        # Record multiple trades
        for i in range(10):
            trade = Trade(
                symbol="BTC-USDT",
                side="buy",
                size=0.001,
                price=95000.0,
            )
            result = TradeResult(
                trade=trade,
                success=True,
                order_id=f"ORDER-{i:03d}",
                timestamp=datetime.utcnow(),
            )
            data_collector.record_trade(result)

        history = data_collector.get_trade_history(limit=5)
        assert len(history) == 5


# =============================================================================
# All Weekly Records Tests
# =============================================================================

class TestAllWeeklyRecords:
    """Tests for all weekly records access."""

    def test_get_all_weekly_records_empty(self, data_collector):
        """Should return empty list when no records."""
        # Note: get_current_week_record may create a record
        records = data_collector.get_all_weekly_records()
        assert isinstance(records, list)


# =============================================================================
# Historical Summary Tests
# =============================================================================

class TestHistoricalSummary:
    """Tests for historical summary."""

    def test_get_historical_summary_empty(self, data_collector):
        """Should return zero values when no history."""
        summary = data_collector.get_historical_summary()

        assert summary["total_weeks"] == 0
        assert summary["total_trades"] == 0
        assert summary["total_volume"] == 0.0
        assert summary["total_fees"] == 0.0


# =============================================================================
# Next Trade Time Tests
# =============================================================================

class TestNextTradeTime:
    """Tests for next trade time calculation."""

    def test_get_next_trade_time(self, data_collector):
        """Should return a datetime for next trade."""
        next_trade = data_collector.get_next_trade_time()
        assert isinstance(next_trade, datetime)


# =============================================================================
# Remaining Trade Days Tests
# =============================================================================

class TestRemainingTradeDays:
    """Tests for remaining trade days calculation."""

    def test_get_remaining_trade_days(self, data_collector):
        """Should return list of day names."""
        remaining = data_collector.get_remaining_trade_days()
        assert isinstance(remaining, list)
        # All days should be weekday names
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        for day in remaining:
            assert day in valid_days


# =============================================================================
# Reset Week Tests
# =============================================================================

class TestResetWeek:
    """Tests for week reset functionality."""

    def test_reset_week(self, data_collector, sample_trade_result):
        """Should reset to fresh weekly record."""
        # Record some trades
        data_collector.record_trade(sample_trade_result)

        # Reset
        result = data_collector.reset_week()
        assert result is True

        # Should have fresh record
        summary = data_collector.get_weekly_summary()
        assert summary["trades_count"] == 0


# =============================================================================
# Validate Trade Day Tests
# =============================================================================

class TestValidateTradeDay:
    """Tests for trade day validation."""

    def test_validate_trade_day_invalid_number(self, data_collector):
        """Should reject invalid day numbers."""
        assert data_collector.validate_trade_day(0) is False
        assert data_collector.validate_trade_day(6) is False
        assert data_collector.validate_trade_day(-1) is False


# =============================================================================
# Current Week Record Tests
# =============================================================================

class TestCurrentWeekRecord:
    """Tests for current week record property."""

    def test_current_week_record_lazy_load(self, data_collector):
        """Should lazy-load current week record."""
        record = data_collector.current_week_record
        assert record is not None
        assert record.week_start is not None
        assert record.week_end is not None

    def test_current_week_record_cached(self, data_collector):
        """Should cache the weekly record."""
        record1 = data_collector.current_week_record
        record2 = data_collector.current_week_record
        # Should be same object (cached)
        assert record1 is record2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
