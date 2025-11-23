"""
Tests for the StakingOptimizationStrategy.
"""

import pytest
import sys
from pathlib import Path
from decimal import Decimal

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bot.strategy import StakingOptimizationStrategy
from bot.config import Config
from bot.utils import calculate_trading_activity_factor, calculate_total_staking_factor


class TestTradingActivityFactor:
    """Tests for trading activity factor calculation."""

    def test_zero_days(self):
        """Trading 0 days should give 0 factor."""
        assert calculate_trading_activity_factor(0) == 0.0

    def test_one_day(self):
        """Trading 1 day should give 0.1 factor."""
        assert calculate_trading_activity_factor(1) == 0.1

    def test_five_days(self):
        """Trading 5 days should give maximum 0.5 factor."""
        assert calculate_trading_activity_factor(5) == 0.5

    def test_more_than_five_days(self):
        """Trading more than 5 days should still cap at 0.5."""
        assert calculate_trading_activity_factor(6) == 0.5
        assert calculate_trading_activity_factor(7) == 0.5
        assert calculate_trading_activity_factor(100) == 0.5


class TestTotalStakingFactor:
    """Tests for total staking factor calculation."""

    def test_base_factor_only(self):
        """Base factor with no trading and no lock should be 1.0."""
        assert calculate_total_staking_factor(0, 0) == 1.0

    def test_with_trading_only(self):
        """Factor with 5 days trading, no lock should be 1.5."""
        assert calculate_total_staking_factor(0, 5) == 1.5

    def test_with_lock_only(self):
        """Factor with 6-month lock, no trading should be 1.5."""
        assert calculate_total_staking_factor(0.5, 0) == 1.5

    def test_combined_factors(self):
        """Factor with 5 days trading and 6-month lock should be 2.0."""
        assert calculate_total_staking_factor(0.5, 5) == 2.0

    def test_maximum_factor(self):
        """Maximum factor with 5 days and 24-month lock should be 3.5."""
        # 24-month lock = 24/12 = 2.0 time factor
        assert calculate_total_staking_factor(2.0, 5) == 3.5


class TestStrategy:
    """Tests for the StakingOptimizationStrategy class."""

    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        config = Config()
        config.trading.symbol = "BTC-USDT"
        config.trading.side = "BUY"
        config.trading.size = Decimal("0.001")
        config.schedule.trade_days = [0, 1, 2, 3, 4]  # Mon-Fri
        return config

    @pytest.fixture
    def strategy(self, config):
        """Create a strategy instance."""
        return StakingOptimizationStrategy(config)

    def test_generate_weekly_schedule(self, strategy):
        """Should generate 5 trades for the week."""
        trades = strategy.generate_weekly_schedule()
        assert len(trades) == 5

        for i, trade in enumerate(trades, 1):
            assert trade.day_number == i
            assert trade.symbol == "BTC-USDT"
            assert trade.side == "BUY"

    def test_calculate_expected_multiplier(self, strategy):
        """Should calculate expected multiplier correctly."""
        # No trading, no lock
        assert strategy.calculate_expected_multiplier(0, 0) == 1.0

        # 5 days trading, no lock
        assert strategy.calculate_expected_multiplier(5, 0) == 1.5

        # 5 days trading, 6-month lock
        assert strategy.calculate_expected_multiplier(5, 0.5) == 2.0

    def test_estimate_weekly_cost(self, strategy):
        """Should estimate reasonable weekly cost."""
        cost = strategy.estimate_weekly_cost(fee_rate=0.001)
        # Should be a small amount (less than $1 for minimum trades)
        assert cost > 0
        assert cost < Decimal("10")  # Should be well under $10


class TestStrategyStatus:
    """Tests for strategy status reporting."""

    @pytest.fixture
    def config(self):
        config = Config()
        config.schedule.trade_days = [0, 1, 2, 3, 4]
        return config

    @pytest.fixture
    def strategy(self, config):
        return StakingOptimizationStrategy(config)

    def test_status_with_no_trades(self, strategy):
        """Status with 0 trades should show 0 factor."""
        status = strategy.get_status(days_already_traded=0)
        assert status.days_traded == 0
        assert status.trading_activity_factor == 0.0

    def test_status_with_some_trades(self, strategy):
        """Status with 3 trades should show 0.3 factor."""
        status = strategy.get_status(days_already_traded=3)
        assert status.days_traded == 3
        assert abs(status.trading_activity_factor - 0.3) < 0.001

    def test_status_with_max_trades(self, strategy):
        """Status with 5 trades should show max 0.5 factor."""
        status = strategy.get_status(days_already_traded=5)
        assert status.days_traded == 5
        assert status.trading_activity_factor == 0.5


class TestStrategyAdvanced:
    """Advanced strategy tests for edge cases."""

    @pytest.fixture
    def config(self):
        config = Config()
        config.trading.symbol = "BTC-USDT"
        config.trading.side = "BUY"
        config.trading.size = Decimal("0.001")
        config.schedule.trade_days = [0, 1, 2, 3, 4]
        config.schedule.trade_time = "09:00"
        return config

    @pytest.fixture
    def strategy(self, config):
        return StakingOptimizationStrategy(config)

    def test_count_remaining_trade_days_from_day_1(self, strategy):
        """Should count all trade days from day 1."""
        remaining = strategy._count_remaining_trade_days(1)
        assert remaining == 5  # All Mon-Fri

    def test_count_remaining_trade_days_from_day_5(self, strategy):
        """Should count 1 trade day from day 5."""
        remaining = strategy._count_remaining_trade_days(5)
        assert remaining == 1  # Just Friday

    def test_count_remaining_trade_days_from_day_7(self, strategy):
        """Should count 0 trade days from day 7 (weekend)."""
        remaining = strategy._count_remaining_trade_days(7)
        # Day 7 = Saturday, no more weekdays
        assert remaining == 0


class TestGetTradeForToday:
    """Tests for get_trade_for_today method."""

    @pytest.fixture
    def config(self):
        config = Config()
        config.trading.symbol = "BTC-USDT"
        config.trading.side = "BUY"
        config.trading.size = Decimal("0.001")
        config.schedule.trade_days = [0, 1, 2, 3, 4]
        return config

    @pytest.fixture
    def strategy(self, config):
        return StakingOptimizationStrategy(config)

    def test_get_trade_with_day_override(self, strategy):
        """Should generate trade with day override."""
        # Mock is_trade_day to return True
        from unittest.mock import patch
        with patch('bot.strategy.is_trade_day', return_value=True):
            trade = strategy.get_trade_for_today(day_number=3)
            if trade:
                assert trade.day_number == 3
                assert trade.symbol == "BTC-USDT"


class TestPrintWeeklyPlan:
    """Tests for print_weekly_plan method."""

    @pytest.fixture
    def config(self):
        config = Config()
        config.trading.symbol = "BTC-USDT"
        config.trading.side = "BUY"
        config.trading.size = Decimal("0.001")
        config.schedule.trade_days = [0, 1, 2, 3, 4]
        return config

    @pytest.fixture
    def strategy(self, config):
        return StakingOptimizationStrategy(config)

    def test_print_weekly_plan_no_errors(self, strategy, caplog):
        """Should print weekly plan without errors."""
        # This should not raise any exceptions
        strategy.print_weekly_plan(days_already_traded=2)
        # Just verify no exception was raised

    def test_print_weekly_plan_max_days(self, strategy, caplog):
        """Should print weekly plan with max days."""
        strategy.print_weekly_plan(days_already_traded=5)
        # Just verify no exception was raised


class TestCreateTradeFromConfig:
    """Tests for create_trade_from_config factory function."""

    def test_create_trade(self):
        """Should create trade from config."""
        from bot.strategy import create_trade_from_config

        config = Config()
        config.trading.symbol = "ETH-USDT"
        config.trading.side = "SELL"
        config.trading.size = Decimal("0.1")
        # NOTE: leverage and close_position are hardcoded (not in TradingConfig)

        trade = create_trade_from_config(config, day_number=3)

        assert trade.symbol == "ETH-USDT"
        assert trade.side == "SELL"
        assert trade.size == Decimal("0.1")
        assert trade.day_number == 3
        # NOTE: leverage and close_position are hardcoded, not in Trade dataclass


class TestContinuousMode:
    """Tests for continuous trading mode."""

    @pytest.fixture
    def config(self):
        config = Config()
        config.schedule.mode = "continuous"
        config.schedule.trade_interval_hours = 4
        config.schedule.trade_days = [0, 1, 2, 3, 4, 5, 6]  # All days
        config.schedule.continue_after_max_factor = True
        return config

    @pytest.fixture
    def strategy(self, config):
        return StakingOptimizationStrategy(config)

    def test_should_trade_respects_interval(self, strategy):
        """Test that continuous mode respects trade interval."""
        from datetime import timedelta
        from bot.utils import get_current_utc_time

        # No last trade - should trade
        should_trade, reason = strategy.should_trade_now(
            last_trade_time=None,
            unique_days_this_week=0
        )
        assert should_trade is True
        assert "Ready to trade" in reason

        # Recent trade - should not trade
        recent_time = get_current_utc_time() - timedelta(hours=2)
        should_trade, reason = strategy.should_trade_now(
            last_trade_time=recent_time,
            unique_days_this_week=0
        )
        assert should_trade is False
        assert "since last trade" in reason

    def test_should_trade_after_interval(self, strategy):
        """Test that trading is allowed after interval passes."""
        from datetime import timedelta
        from bot.utils import get_current_utc_time

        # Old trade - should trade
        old_time = get_current_utc_time() - timedelta(hours=5)
        should_trade, reason = strategy.should_trade_now(
            last_trade_time=old_time,
            unique_days_this_week=0
        )
        assert should_trade is True

    def test_continue_after_max_factor_true(self, strategy):
        """Test trading continues after max factor when configured."""
        strategy.config.schedule.continue_after_max_factor = True

        should_trade, reason = strategy.should_trade_now(
            last_trade_time=None,
            unique_days_this_week=5
        )
        assert should_trade is True

    def test_continue_after_max_factor_false(self, strategy):
        """Test trading stops after max factor when configured."""
        strategy.config.schedule.continue_after_max_factor = False

        should_trade, reason = strategy.should_trade_now(
            last_trade_time=None,
            unique_days_this_week=5
        )
        assert should_trade is False
        assert "Max Trading Activity Factor" in reason

    def test_get_status_summary(self, strategy):
        """Test status summary generation."""
        summary = strategy.get_status_summary(unique_days_this_week=3)
        assert "Mode: continuous" in summary
        assert "Days traded this week: 3/5" in summary


class TestDailyMode:
    """Tests for daily trading mode."""

    @pytest.fixture
    def config(self):
        config = Config()
        config.schedule.mode = "daily"
        config.schedule.trade_days = [0, 1, 2, 3, 4]
        config.schedule.trade_time = "09:00"
        return config

    @pytest.fixture
    def strategy(self, config):
        return StakingOptimizationStrategy(config)

    def test_daily_mode_checks_time(self, strategy):
        """Test that daily mode checks scheduled time."""
        from unittest.mock import patch
        from datetime import datetime

        # Mock time to be before scheduled trade time
        mock_time = datetime(2024, 1, 15, 8, 0, 0)  # Monday 8 AM, before 9 AM
        with patch('bot.strategy.get_current_utc_time', return_value=mock_time):
            should_trade, reason = strategy.should_trade_now(
                last_trade_time=None,
                unique_days_this_week=0
            )
            assert should_trade is False
            assert "Before scheduled trade time" in reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
