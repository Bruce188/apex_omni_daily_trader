"""
Tests for Performance Metrics.

Tests cover:
- Success rate calculation
- Aggregation
- Real-time metrics
- Health checks
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.metrics import MetricsTracker, RealTimeMetrics, MetricsSummary
from data.models import Trade, TradeResult, TradeStatus


# =============================================================================
# RealTimeMetrics Tests
# =============================================================================

class TestRealTimeMetrics:
    """Tests for RealTimeMetrics class."""

    def test_initial_state(self):
        """Should have correct initial state."""
        metrics = RealTimeMetrics()
        assert metrics.trades_total == 0
        assert metrics.trades_success == 0
        assert metrics.trades_failed == 0
        assert metrics.volume_total == 0.0
        assert metrics.fees_total == 0.0

    def test_update_success(self, sample_trade_result):
        """Should update metrics on successful trade."""
        metrics = RealTimeMetrics()
        metrics.update(sample_trade_result, execution_time_ms=100)

        assert metrics.trades_total == 1
        assert metrics.trades_success == 1
        assert metrics.trades_failed == 0
        assert metrics.volume_total > 0
        assert metrics.fees_total > 0
        assert len(metrics.execution_times_ms) == 1

    def test_update_failure(self, failed_trade_result):
        """Should update metrics on failed trade."""
        metrics = RealTimeMetrics()
        metrics.update(failed_trade_result)

        assert metrics.trades_total == 1
        assert metrics.trades_success == 0
        assert metrics.trades_failed == 1
        assert "Insufficient balance" in metrics.errors

    def test_success_rate_calculation(self, sample_trade_result, failed_trade_result):
        """Should calculate correct success rate."""
        metrics = RealTimeMetrics()

        # 3 successes, 1 failure = 75%
        metrics.update(sample_trade_result)
        metrics.update(sample_trade_result)
        metrics.update(sample_trade_result)
        metrics.update(failed_trade_result)

        assert metrics.success_rate == 75.0

    def test_success_rate_no_trades(self):
        """Should return 0 for no trades."""
        metrics = RealTimeMetrics()
        assert metrics.success_rate == 0.0

    def test_avg_execution_time(self, sample_trade_result):
        """Should calculate average execution time."""
        metrics = RealTimeMetrics()
        metrics.update(sample_trade_result, execution_time_ms=100)
        metrics.update(sample_trade_result, execution_time_ms=200)
        metrics.update(sample_trade_result, execution_time_ms=300)

        assert metrics.avg_execution_time == 200.0

    def test_avg_execution_time_no_data(self):
        """Should return 0 with no execution time data."""
        metrics = RealTimeMetrics()
        assert metrics.avg_execution_time == 0.0

    def test_most_common_error(self, failed_trade_result):
        """Should track most common error."""
        metrics = RealTimeMetrics()

        # Create different error types
        error1 = TradeResult(
            trade=failed_trade_result.trade,
            success=False,
            error="Error A",
        )
        error2 = TradeResult(
            trade=failed_trade_result.trade,
            success=False,
            error="Error B",
        )

        # 2 Error A, 1 Error B
        metrics.update(error1)
        metrics.update(error1)
        metrics.update(error2)

        assert metrics.most_common_error == "Error A"

    def test_to_dict(self, sample_trade_result):
        """Should convert to dictionary."""
        metrics = RealTimeMetrics()
        metrics.update(sample_trade_result, execution_time_ms=150)

        data = metrics.to_dict()

        assert "trades_total" in data
        assert "success_rate" in data
        assert "volume_total" in data
        assert "session_start" in data


# =============================================================================
# MetricsSummary Tests
# =============================================================================

class TestMetricsSummary:
    """Tests for MetricsSummary dataclass."""

    def test_summary_creation(self):
        """Should create summary with fields."""
        summary = MetricsSummary(
            period_start=datetime.utcnow() - timedelta(days=7),
            period_end=datetime.utcnow(),
            total_trades=10,
            successful_trades=8,
            failed_trades=2,
            success_rate=80.0,
        )
        assert summary.total_trades == 10
        assert summary.success_rate == 80.0

    def test_to_dict(self):
        """Should convert to dictionary."""
        summary = MetricsSummary(
            period_start=datetime.utcnow() - timedelta(days=7),
            period_end=datetime.utcnow(),
            total_trades=10,
            successful_trades=8,
            failed_trades=2,
            success_rate=80.0,
        )
        data = summary.to_dict()

        assert data["total_trades"] == 10
        assert data["success_rate"] == 80.0
        assert "period_start" in data
        assert "period_end" in data


# =============================================================================
# MetricsTracker Tests
# =============================================================================

class TestMetricsTracker:
    """Tests for MetricsTracker class."""

    def test_initialization(self, storage):
        """Should initialize with storage."""
        tracker = MetricsTracker(storage=storage)
        assert tracker.storage is storage
        assert tracker.realtime is not None

    def test_update(self, metrics_tracker, sample_trade_result):
        """Should update real-time metrics."""
        metrics_tracker.update(sample_trade_result, execution_time_ms=100)

        assert metrics_tracker.realtime.trades_total == 1
        assert metrics_tracker.realtime.trades_success == 1

    def test_get_summary_session(self, metrics_tracker, sample_trade_result):
        """Should get session summary."""
        metrics_tracker.update(sample_trade_result)
        metrics_tracker.update(sample_trade_result)

        summary = metrics_tracker.get_summary("session")

        assert summary.total_trades == 2
        assert summary.successful_trades == 2

    def test_get_summary_empty(self, metrics_tracker):
        """Should handle empty history."""
        summary = metrics_tracker.get_summary("week")

        assert summary.total_trades == 0
        assert summary.success_rate == 0.0

    def test_get_success_rate(self, metrics_tracker, sample_trade_result, failed_trade_result):
        """Should get success rate for period."""
        # Update realtime (for session summary)
        metrics_tracker.update(sample_trade_result)
        metrics_tracker.update(sample_trade_result)
        metrics_tracker.update(failed_trade_result)

        rate = metrics_tracker.get_success_rate("session")
        # 2 success, 1 failure = 66.67%
        assert abs(rate - 66.67) < 1.0

    def test_get_total_volume(self, metrics_tracker, sample_trade_result):
        """Should get total volume for period."""
        metrics_tracker.update(sample_trade_result)
        metrics_tracker.update(sample_trade_result)

        volume = metrics_tracker.get_total_volume("session")
        assert volume > 0

    def test_get_total_fees(self, metrics_tracker, sample_trade_result):
        """Should get total fees for period."""
        metrics_tracker.update(sample_trade_result)
        metrics_tracker.update(sample_trade_result)

        fees = metrics_tracker.get_total_fees("session")
        assert fees > 0

    def test_get_daily_breakdown(self, metrics_tracker):
        """Should return daily breakdown list."""
        breakdown = metrics_tracker.get_daily_breakdown(days=7)

        assert len(breakdown) == 7
        for day in breakdown:
            assert "date" in day
            assert "trades" in day
            assert "success_rate" in day

    def test_get_error_breakdown(self, metrics_tracker):
        """Should return error breakdown."""
        breakdown = metrics_tracker.get_error_breakdown("week")
        assert isinstance(breakdown, dict)

    def test_check_health_healthy(self, metrics_tracker):
        """Should report healthy status."""
        health = metrics_tracker.check_health()

        assert "status" in health
        assert "alerts" in health
        assert "metrics" in health
        assert "checked_at" in health

    def test_reset_session(self, metrics_tracker, sample_trade_result):
        """Should reset session metrics."""
        metrics_tracker.update(sample_trade_result)
        assert metrics_tracker.realtime.trades_total == 1

        metrics_tracker.reset_session()

        assert metrics_tracker.realtime.trades_total == 0


# =============================================================================
# Health Check Tests
# =============================================================================

class TestHealthCheck:
    """Tests for health check functionality."""

    def test_health_check_returns_status(self, metrics_tracker):
        """Should return health status."""
        health = metrics_tracker.check_health()
        assert health["status"] in ["healthy", "warning", "critical"]

    def test_health_check_alerts_list(self, metrics_tracker):
        """Alerts should be a list."""
        health = metrics_tracker.check_health()
        assert isinstance(health["alerts"], list)


# =============================================================================
# Export Tests
# =============================================================================

class TestMetricsExport:
    """Tests for metrics export functionality."""

    def test_export_metrics(self, metrics_tracker, temp_data_dir, sample_trade_result):
        """Should export metrics to file."""
        metrics_tracker.update(sample_trade_result)

        export_path = Path(temp_data_dir) / "metrics_export.json"
        result = metrics_tracker.export_metrics(str(export_path))

        assert result is True
        assert export_path.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
