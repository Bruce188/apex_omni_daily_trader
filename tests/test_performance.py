"""
Tests for Performance Analytics.

Tests cover:
- WeeklyPerformanceSummary dataclass
- CostAnalysis dataclass
- ROIAnalysis dataclass
- PerformanceAnalyzer class
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analytics.performance import (
    WeeklyPerformanceSummary,
    CostAnalysis,
    ROIAnalysis,
    PerformanceAnalyzer,
)
from data.models import Trade, TradeResult, WeeklyTradeRecord, TradeStatus
from data.storage import Storage


# =============================================================================
# WeeklyPerformanceSummary Tests
# =============================================================================

class TestWeeklyPerformanceSummary:
    """Tests for WeeklyPerformanceSummary dataclass."""

    @pytest.fixture
    def week_bounds(self):
        now = datetime.utcnow()
        monday = now - timedelta(days=now.weekday())
        monday = monday.replace(hour=8, minute=0, second=0, microsecond=0)
        return monday, monday + timedelta(days=7)

    def test_creation_defaults(self, week_bounds):
        """Should create with default values."""
        week_start, week_end = week_bounds
        summary = WeeklyPerformanceSummary(
            week_start=week_start,
            week_end=week_end,
        )
        assert summary.days_traded == 0
        assert summary.trading_factor == 0.0
        assert summary.total_factor == 1.0
        assert summary.trades_executed == 0
        assert summary.success_rate == 0.0
        assert summary.max_factor_achieved is False

    def test_creation_with_values(self, week_bounds):
        """Should create with specified values."""
        week_start, week_end = week_bounds
        summary = WeeklyPerformanceSummary(
            week_start=week_start,
            week_end=week_end,
            days_traded=5,
            trading_factor=0.5,
            total_factor=2.0,
            trades_executed=10,
            trades_successful=9,
            trades_failed=1,
            success_rate=90.0,
            total_volume=1000.0,
            total_fees=0.5,
            max_factor_achieved=True,
        )
        assert summary.days_traded == 5
        assert summary.trading_factor == 0.5
        assert summary.max_factor_achieved is True

    def test_to_dict(self, week_bounds):
        """Should convert to dictionary correctly."""
        week_start, week_end = week_bounds
        summary = WeeklyPerformanceSummary(
            week_start=week_start,
            week_end=week_end,
            days_traded=3,
            trading_factor=0.3,
            total_factor=1.8,
            success_rate=85.5,
        )
        data = summary.to_dict()

        assert data["days_traded"] == 3
        assert data["trading_factor"] == 0.3
        assert data["total_factor"] == 1.8
        assert data["success_rate"] == 85.5
        assert "week_start" in data
        assert "week_end" in data

    def test_str_representation(self, week_bounds):
        """Should have readable string representation."""
        week_start, week_end = week_bounds
        summary = WeeklyPerformanceSummary(
            week_start=week_start,
            week_end=week_end,
            days_traded=3,
            trading_factor=0.3,
            total_factor=1.8,
            trades_executed=5,
            trades_successful=4,
            success_rate=80.0,
            total_fees=0.25,
            total_volume=500.0,
        )
        text = str(summary)

        assert "Days Traded: 3/5" in text
        assert "Trading Factor: 0.30" in text
        assert "Total Factor: 1.80x" in text

    def test_str_max_factor_achieved(self, week_bounds):
        """Should show MAX FACTOR when 5 days traded."""
        week_start, week_end = week_bounds
        summary = WeeklyPerformanceSummary(
            week_start=week_start,
            week_end=week_end,
            days_traded=5,
            max_factor_achieved=True,
        )
        text = str(summary)
        assert "MAX FACTOR!" in text


# =============================================================================
# CostAnalysis Tests
# =============================================================================

class TestCostAnalysis:
    """Tests for CostAnalysis dataclass."""

    @pytest.fixture
    def period_bounds(self):
        end = datetime.utcnow()
        start = end - timedelta(days=30)
        return start, end

    def test_creation_defaults(self, period_bounds):
        """Should create with default values."""
        start, end = period_bounds
        analysis = CostAnalysis(
            period_start=start,
            period_end=end,
        )
        assert analysis.total_fees == 0.0
        assert analysis.total_slippage_cost == 0.0
        assert analysis.total_cost == 0.0
        assert analysis.cost_per_trade == 0.0

    def test_creation_with_values(self, period_bounds):
        """Should create with specified values."""
        start, end = period_bounds
        analysis = CostAnalysis(
            period_start=start,
            period_end=end,
            total_fees=0.5,
            total_slippage_cost=0.1,
            total_cost=0.6,
            cost_per_trade=0.12,
            cost_per_day=0.02,
            fee_rate_avg=0.0005,
            trades_count=5,
        )
        assert analysis.total_fees == 0.5
        assert analysis.total_cost == 0.6
        assert analysis.trades_count == 5

    def test_to_dict(self, period_bounds):
        """Should convert to dictionary correctly."""
        start, end = period_bounds
        analysis = CostAnalysis(
            period_start=start,
            period_end=end,
            total_fees=0.5,
            total_cost=0.6,
            trades_count=5,
        )
        data = analysis.to_dict()

        assert data["total_fees"] == 0.5
        assert data["total_cost"] == 0.6
        assert data["trades_count"] == 5
        assert "period_start" in data
        assert "period_end" in data


# =============================================================================
# ROIAnalysis Tests
# =============================================================================

class TestROIAnalysis:
    """Tests for ROIAnalysis dataclass."""

    def test_creation_defaults(self):
        """Should create with default values."""
        roi = ROIAnalysis(period="4 weeks")
        assert roi.period == "4 weeks"
        assert roi.staking_reward_estimate == 0.0
        assert roi.trading_cost == 0.0
        assert roi.net_roi == 0.0
        assert roi.roi_percentage == 0.0

    def test_creation_with_values(self):
        """Should create with specified values."""
        roi = ROIAnalysis(
            period="4 weeks",
            staking_reward_estimate=100.0,
            trading_cost=10.0,
            net_roi=90.0,
            roi_percentage=900.0,
            break_even_stake=500.0,
        )
        assert roi.staking_reward_estimate == 100.0
        assert roi.net_roi == 90.0
        assert roi.roi_percentage == 900.0

    def test_to_dict(self):
        """Should convert to dictionary correctly."""
        roi = ROIAnalysis(
            period="4 weeks",
            staking_reward_estimate=100.0,
            trading_cost=10.0,
            net_roi=90.0,
        )
        data = roi.to_dict()

        assert data["period"] == "4 weeks"
        assert data["staking_reward_estimate"] == 100.0
        assert data["net_roi"] == 90.0


# =============================================================================
# PerformanceAnalyzer Tests
# =============================================================================

class TestPerformanceAnalyzer:
    """Tests for PerformanceAnalyzer class."""

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage instance."""
        storage = Mock(spec=Storage)
        storage.get_weekly_record.return_value = None
        storage.get_all_trades.return_value = []
        storage.get_all_weekly_records.return_value = []
        return storage

    @pytest.fixture
    def analyzer(self, mock_storage):
        """Create analyzer with mock storage."""
        return PerformanceAnalyzer(
            storage=mock_storage,
            staked_amount=1000.0,
            lock_months=6,
        )

    def test_initialization(self, mock_storage):
        """Should initialize with provided values."""
        analyzer = PerformanceAnalyzer(
            storage=mock_storage,
            staked_amount=5000.0,
            lock_months=12,
        )
        assert analyzer.staked_amount == 5000.0
        assert analyzer.lock_months == 12
        assert analyzer.storage == mock_storage

    def test_initialization_with_data_dir(self, temp_data_dir):
        """Should initialize with data directory."""
        analyzer = PerformanceAnalyzer(
            data_dir=temp_data_dir,
            staked_amount=1000.0,
            lock_months=6,
        )
        assert analyzer.storage is not None
        assert analyzer.staked_amount == 1000.0

    def test_get_weekly_summary_empty(self, analyzer, mock_storage):
        """Should return empty summary when no data."""
        mock_storage.get_weekly_record.return_value = None

        summary = analyzer.get_weekly_summary()

        assert summary.days_traded == 0
        assert summary.trading_factor == 0.0
        assert summary.trades_executed == 0

    def test_get_weekly_summary_with_data(self, analyzer, mock_storage):
        """Should calculate summary from weekly record."""
        # Create mock weekly record
        now = datetime.utcnow()
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=8, minute=0, second=0, microsecond=0)

        trade = Trade(
            symbol="BTC-USDT",
            side="buy",
            size=0.001,
            price=95000.0,
        )
        trade_result = TradeResult(
            trade=trade,
            success=True,
            order_id="ORDER-001",
            executed_price=95000.0,
            executed_size=0.001,
            fees=0.0475,
            timestamp=datetime.utcnow(),
            status=TradeStatus.FILLED,
        )

        record = WeeklyTradeRecord(
            week_start=week_start,
            week_end=week_start + timedelta(days=7),
            trades=[trade_result],
            days_traded={0, 1, 2},  # 3 days
        )
        mock_storage.get_weekly_record.return_value = record

        summary = analyzer.get_weekly_summary(week_start)

        assert summary.days_traded == 3
        assert summary.trades_executed == 1
        assert summary.trades_successful == 1
        assert summary.trades_failed == 0
        assert summary.success_rate == 100.0

    def test_get_current_week_summary(self, analyzer, mock_storage):
        """Should get summary for current week."""
        mock_storage.get_weekly_record.return_value = None

        summary = analyzer.get_current_week_summary()

        assert summary is not None
        assert summary.days_traded == 0


# =============================================================================
# Trade Success Analysis Tests
# =============================================================================

class TestTradeSuccessAnalysis:
    """Tests for trade success analysis."""

    @pytest.fixture
    def analyzer_with_trades(self, temp_data_dir):
        """Create analyzer with mock trades."""
        analyzer = PerformanceAnalyzer(
            data_dir=temp_data_dir,
            staked_amount=1000.0,
            lock_months=6,
        )
        return analyzer

    def test_analyze_trade_success_empty(self, analyzer_with_trades):
        """Should handle empty trade history."""
        analysis = analyzer_with_trades.analyze_trade_success(30)

        assert analysis["total_trades"] == 0
        assert analysis["success_rate"] == 0.0


# =============================================================================
# Cost Analysis Tests
# =============================================================================

class TestCostAnalysisMethod:
    """Tests for cost analysis method."""

    @pytest.fixture
    def analyzer(self, temp_data_dir):
        """Create analyzer with temp storage."""
        return PerformanceAnalyzer(
            data_dir=temp_data_dir,
            staked_amount=1000.0,
            lock_months=6,
        )

    def test_analyze_costs_empty(self, analyzer):
        """Should handle empty trade history."""
        analysis = analyzer.analyze_costs(30)

        assert analysis.total_fees == 0.0
        assert analysis.total_cost == 0.0
        assert analysis.trades_count == 0


# =============================================================================
# Trend Analysis Tests
# =============================================================================

class TestTrendAnalysis:
    """Tests for trend analysis."""

    @pytest.fixture
    def mock_storage(self):
        """Create mock storage."""
        storage = Mock(spec=Storage)
        storage.get_all_weekly_records.return_value = []
        storage.get_weekly_record.return_value = None
        return storage

    @pytest.fixture
    def analyzer(self, mock_storage):
        """Create analyzer with mock storage."""
        return PerformanceAnalyzer(
            storage=mock_storage,
            staked_amount=1000.0,
            lock_months=6,
        )

    def test_get_trend_analysis_empty(self, analyzer, mock_storage):
        """Should handle no weekly records."""
        mock_storage.get_all_weekly_records.return_value = []

        trends = analyzer.get_trend_analysis(8)

        assert trends["weeks_analyzed"] == 0


# =============================================================================
# Report Generation Tests
# =============================================================================

class TestReportGeneration:
    """Tests for report generation."""

    @pytest.fixture
    def mock_storage(self):
        """Create mock storage."""
        storage = Mock(spec=Storage)
        storage.get_weekly_record.return_value = None
        storage.get_all_trades.return_value = []
        storage.get_all_weekly_records.return_value = []
        return storage

    @pytest.fixture
    def analyzer(self, mock_storage):
        """Create analyzer with mock storage."""
        return PerformanceAnalyzer(
            storage=mock_storage,
            staked_amount=1000.0,
            lock_months=6,
        )

    def test_generate_report(self, analyzer):
        """Should generate comprehensive report."""
        report = analyzer.generate_report()

        assert "generated_at" in report
        assert "current_week" in report
        assert "success_analysis" in report
        assert "cost_analysis" in report
        assert "trends" in report
        assert "staking_config" in report

    def test_generate_report_staking_config(self, analyzer):
        """Report should include staking configuration."""
        report = analyzer.generate_report()

        assert report["staking_config"]["staked_amount"] == 1000.0
        assert report["staking_config"]["lock_months"] == 6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
