"""
Tests for Multiplier Analysis (CRITICAL!).

These tests verify the staking multiplier calculations which are
essential for the bot's core functionality.

Formula Reference:
    Total Staking Factor = 1 + Time Factor + Trading Activity Factor
    Time Factor = Lock-Up Period (Months) / 12
    Trading Activity Factor = 0.1 * Days Traded (max 0.5)
"""

import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analytics.multiplier_analysis import (
    MultiplierCalculator,
    MultiplierBreakdown,
    RewardProjection,
    quick_calculate,
    BASE_FACTOR,
    MAX_TRADING_FACTOR,
    TRADING_FACTOR_PER_DAY,
    MAX_TRADING_DAYS,
    MONTHS_IN_YEAR,
)


# =============================================================================
# Time Factor Tests (CRITICAL)
# =============================================================================

class TestTimeFactor:
    """Tests for Time Factor calculation."""

    def test_time_factor_0_months(self):
        """0 months lock = 0 time factor."""
        assert MultiplierCalculator.calculate_time_factor(0) == 0.0

    def test_time_factor_3_months(self):
        """3 months lock = 0.25 time factor."""
        assert MultiplierCalculator.calculate_time_factor(3) == 0.25

    def test_time_factor_6_months(self):
        """6 months lock = 0.5 time factor (CRITICAL TEST)."""
        assert MultiplierCalculator.calculate_time_factor(6) == 0.5

    def test_time_factor_12_months(self):
        """12 months lock = 1.0 time factor."""
        assert MultiplierCalculator.calculate_time_factor(12) == 1.0

    def test_time_factor_24_months(self):
        """24 months lock = 2.0 time factor (maximum)."""
        assert MultiplierCalculator.calculate_time_factor(24) == 2.0

    def test_time_factor_negative(self):
        """Should reject negative months."""
        with pytest.raises(ValueError):
            MultiplierCalculator.calculate_time_factor(-1)


# =============================================================================
# Trading Activity Factor Tests (CRITICAL)
# =============================================================================

class TestTradingFactor:
    """Tests for Trading Activity Factor calculation."""

    def test_trading_factor_0_days(self):
        """0 days traded = 0 trading factor."""
        assert MultiplierCalculator.calculate_trading_factor(0) == 0.0

    def test_trading_factor_1_day(self):
        """1 day traded = 0.1 trading factor."""
        assert MultiplierCalculator.calculate_trading_factor(1) == 0.1

    def test_trading_factor_2_days(self):
        """2 days traded = 0.2 trading factor."""
        assert MultiplierCalculator.calculate_trading_factor(2) == 0.2

    def test_trading_factor_3_days(self):
        """3 days traded = 0.3 trading factor."""
        assert abs(MultiplierCalculator.calculate_trading_factor(3) - 0.3) < 0.0001

    def test_trading_factor_4_days(self):
        """4 days traded = 0.4 trading factor."""
        assert MultiplierCalculator.calculate_trading_factor(4) == 0.4

    def test_trading_factor_5_days(self):
        """5 days traded = 0.5 trading factor (CRITICAL TEST - MAXIMUM)."""
        assert MultiplierCalculator.calculate_trading_factor(5) == 0.5

    def test_trading_factor_capped_at_5_days(self):
        """More than 5 days should still cap at 0.5."""
        assert MultiplierCalculator.calculate_trading_factor(6) == 0.5
        assert MultiplierCalculator.calculate_trading_factor(7) == 0.5
        assert MultiplierCalculator.calculate_trading_factor(100) == 0.5

    def test_trading_factor_negative(self):
        """Should reject negative days."""
        with pytest.raises(ValueError):
            MultiplierCalculator.calculate_trading_factor(-1)


# =============================================================================
# Total Staking Factor Tests (CRITICAL)
# =============================================================================

class TestTotalFactor:
    """Tests for Total Staking Factor calculation."""

    def test_base_factor_only(self):
        """Base factor with no trading and no lock should be 1.0."""
        calc = MultiplierCalculator(staked_amount=1000, lock_months=0)
        assert calc.calculate_total_factor(days_traded=0) == 1.0

    def test_total_factor_5_days_no_lock(self):
        """5 days trading, no lock = 1.5 (CRITICAL TEST)."""
        calc = MultiplierCalculator(staked_amount=1000, lock_months=0)
        result = calc.calculate_total_factor(days_traded=5)
        # 1 + 0 + 0.5 = 1.5
        assert result == 1.5

    def test_total_factor_6_month_lock_no_trading(self):
        """6-month lock, no trading = 1.5."""
        calc = MultiplierCalculator(staked_amount=1000, lock_months=6)
        result = calc.calculate_total_factor(days_traded=0)
        # 1 + 0.5 + 0 = 1.5
        assert result == 1.5

    def test_total_factor_6_month_lock_5_days(self):
        """6-month lock + 5 days trading = 2.0 (CRITICAL TEST)."""
        calc = MultiplierCalculator(staked_amount=1000, lock_months=6)
        result = calc.calculate_total_factor(days_traded=5)
        # 1 + 0.5 + 0.5 = 2.0
        assert result == 2.0

    def test_total_factor_12_month_lock_5_days(self):
        """12-month lock + 5 days trading = 2.5."""
        calc = MultiplierCalculator(staked_amount=1000, lock_months=12)
        result = calc.calculate_total_factor(days_traded=5)
        # 1 + 1.0 + 0.5 = 2.5
        assert result == 2.5

    def test_total_factor_24_month_lock_5_days(self):
        """24-month lock + 5 days trading = 3.5 (CRITICAL - MAXIMUM)."""
        calc = MultiplierCalculator(staked_amount=1000, lock_months=24)
        result = calc.calculate_total_factor(days_traded=5)
        # 1 + 2.0 + 0.5 = 3.5
        assert result == 3.5


# =============================================================================
# MultiplierCalculator Class Tests
# =============================================================================

class TestMultiplierCalculator:
    """Tests for MultiplierCalculator class."""

    def test_initialization_valid(self):
        """Should initialize with valid parameters."""
        calc = MultiplierCalculator(staked_amount=1000, lock_months=6)
        assert calc.staked_amount == 1000
        assert calc.lock_months == 6

    def test_initialization_negative_amount(self):
        """Should reject negative staked amount."""
        with pytest.raises(ValueError):
            MultiplierCalculator(staked_amount=-1000, lock_months=0)

    def test_initialization_negative_months(self):
        """Should reject negative lock months."""
        with pytest.raises(ValueError):
            MultiplierCalculator(staked_amount=1000, lock_months=-1)

    def test_factor_breakdown(self):
        """Should provide detailed factor breakdown."""
        calc = MultiplierCalculator(staked_amount=1000, lock_months=6)
        breakdown = calc.get_factor_breakdown(days_traded=3)

        assert breakdown.base_factor == 1.0
        assert breakdown.time_factor == 0.5
        assert abs(breakdown.trading_factor - 0.3) < 0.0001
        assert abs(breakdown.total_factor - 1.8) < 0.0001
        assert breakdown.lock_months == 6
        assert breakdown.days_traded == 3

    def test_calculate_effective_stake(self):
        """Should calculate effective (weighted) stake."""
        calc = MultiplierCalculator(staked_amount=1000, lock_months=6)
        # With 5 days trading: factor = 2.0
        effective = calc.calculate_effective_stake(days_traded=5)
        assert effective == 2000.0  # 1000 * 2.0

    def test_days_to_max_trading_factor(self):
        """Should calculate remaining days to max factor."""
        calc = MultiplierCalculator()

        assert calc.days_to_max_trading_factor(0) == 5
        assert calc.days_to_max_trading_factor(3) == 2
        assert calc.days_to_max_trading_factor(5) == 0
        assert calc.days_to_max_trading_factor(6) == 0

    def test_trading_factor_progress(self):
        """Should provide trading factor progress info."""
        calc = MultiplierCalculator()
        progress = calc.get_trading_factor_progress(days_traded=3)

        assert progress["days_traded"] == 3
        assert progress["max_days"] == 5
        assert progress["remaining_days"] == 2
        assert abs(progress["current_factor"] - 0.3) < 0.0001
        assert progress["max_factor"] == 0.5
        assert progress["progress_pct"] == 60.0
        assert progress["at_max"] is False

    def test_trading_factor_progress_at_max(self):
        """Should show at_max when 5 days reached."""
        calc = MultiplierCalculator()
        progress = calc.get_trading_factor_progress(days_traded=5)

        assert progress["at_max"] is True
        assert progress["remaining_days"] == 0

    def test_optimal_lock_period(self):
        """Should calculate optimal lock period for target factor."""
        calc = MultiplierCalculator()

        # Want factor of 2.0 with 5 days trading
        # 2.0 = 1 + time + 0.5 => time = 0.5 => 6 months
        months = calc.optimal_lock_period(target_factor=2.0, days_traded=5)
        assert months == 6

        # Want factor of 1.5 with 5 days trading
        # 1.5 = 1 + time + 0.5 => time = 0 => 0 months
        months = calc.optimal_lock_period(target_factor=1.5, days_traded=5)
        assert months == 0

    def test_compare_scenarios(self):
        """Should compare multiple scenarios."""
        calc = MultiplierCalculator(staked_amount=1000, lock_months=0)

        scenarios = [
            {"lock_months": 0, "days_traded": 0},
            {"lock_months": 6, "days_traded": 5},
            {"lock_months": 24, "days_traded": 5},
        ]
        results = calc.compare_scenarios(scenarios)

        assert len(results) == 3
        assert results[0].total_factor == 1.0   # Base only
        assert results[1].total_factor == 2.0   # 6 months + 5 days
        assert results[2].total_factor == 3.5   # 24 months + 5 days (max)


# =============================================================================
# MultiplierBreakdown Tests
# =============================================================================

class TestMultiplierBreakdown:
    """Tests for MultiplierBreakdown dataclass."""

    def test_to_dict(self):
        """Should convert to dictionary."""
        breakdown = MultiplierBreakdown(
            base_factor=1.0,
            time_factor=0.5,
            trading_factor=0.3,
            total_factor=1.8,
            lock_months=6,
            days_traded=3,
        )
        data = breakdown.to_dict()

        assert data["base_factor"] == 1.0
        assert data["time_factor"] == 0.5
        assert data["trading_factor"] == 0.3
        assert data["total_factor"] == 1.8

    def test_str_representation(self):
        """Should have readable string representation."""
        breakdown = MultiplierBreakdown(
            base_factor=1.0,
            time_factor=0.5,
            trading_factor=0.5,
            total_factor=2.0,
            lock_months=6,
            days_traded=5,
        )
        text = str(breakdown)

        assert "2.00x" in text
        assert "6 months" in text
        assert "5 days" in text


# =============================================================================
# RewardProjection Tests
# =============================================================================

class TestRewardProjection:
    """Tests for RewardProjection dataclass."""

    def test_project_weekly_reward(self):
        """Should project weekly rewards correctly."""
        calc = MultiplierCalculator(staked_amount=10000, lock_months=6)

        projection = calc.project_weekly_reward(
            pool_size=100000,      # 100k APEX weekly pool
            total_pool_factor=1000000,  # Total weighted stake in pool
            days_traded=5,
        )

        # Factor = 2.0, effective stake = 20000
        assert projection.staking_factor == 2.0
        assert projection.effective_stake == 20000.0

        # Share = 20000 / 1000000 = 2%
        assert abs(projection.pool_share_pct - 2.0) < 0.01

        # Reward = 2% * 100000 = 2000
        assert abs(projection.estimated_reward - 2000.0) < 0.01

    def test_projection_to_dict(self):
        """Should convert projection to dictionary."""
        projection = RewardProjection(
            staked_amount=10000,
            staking_factor=2.0,
            effective_stake=20000,
            pool_share_pct=2.0,
            estimated_reward=2000.0,
        )
        data = projection.to_dict()

        assert data["staked_amount"] == 10000
        assert data["staking_factor"] == 2.0
        assert data["effective_stake"] == 20000


# =============================================================================
# Quick Calculate Function Tests
# =============================================================================

class TestQuickCalculate:
    """Tests for quick_calculate helper function."""

    def test_quick_calculate(self):
        """Should return complete calculation results."""
        result = quick_calculate(
            staked_amount=1000,
            lock_months=6,
            days_traded=5,
        )

        assert result["input"]["staked_amount"] == 1000
        assert result["input"]["lock_months"] == 6
        assert result["input"]["days_traded"] == 5
        assert result["factors"]["total_factor"] == 2.0
        assert result["effective_stake"] == 2000.0


# =============================================================================
# Constants Tests
# =============================================================================

class TestConstants:
    """Tests for module constants."""

    def test_base_factor(self):
        """Base factor should be 1.0."""
        assert BASE_FACTOR == 1.0

    def test_max_trading_factor(self):
        """Max trading factor should be 0.5."""
        assert MAX_TRADING_FACTOR == 0.5

    def test_trading_factor_per_day(self):
        """Trading factor per day should be 0.1."""
        assert TRADING_FACTOR_PER_DAY == 0.1

    def test_max_trading_days(self):
        """Max trading days should be 5."""
        assert MAX_TRADING_DAYS == 5

    def test_months_in_year(self):
        """Months in year should be 12."""
        assert MONTHS_IN_YEAR == 12


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Edge case tests for multiplier calculations."""

    def test_zero_staked_amount(self):
        """Should handle zero staked amount."""
        calc = MultiplierCalculator(staked_amount=0, lock_months=6)
        effective = calc.calculate_effective_stake(days_traded=5)
        assert effective == 0.0

    def test_very_large_lock_period(self):
        """Should handle very large lock periods."""
        result = MultiplierCalculator.calculate_time_factor(120)  # 10 years
        assert result == 10.0

    def test_float_precision(self):
        """Should maintain precision in calculations."""
        calc = MultiplierCalculator(staked_amount=999.99, lock_months=6)
        factor = calc.calculate_total_factor(days_traded=5)
        effective = calc.calculate_effective_stake(days_traded=5)

        assert factor == 2.0
        assert abs(effective - 1999.98) < 0.01

    def test_project_reward_zero_pool(self):
        """Should handle zero total pool factor gracefully."""
        calc = MultiplierCalculator(staked_amount=1000, lock_months=6)

        with pytest.raises(ValueError):
            calc.project_weekly_reward(
                pool_size=100000,
                total_pool_factor=0,  # Invalid
                days_traded=5,
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
