"""
Performance Metrics Tracking for ApexOmni Trading Bot.

This module provides metrics collection, calculation, and reporting
for monitoring trading bot performance.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from statistics import mean

from data.models import TradeResult
from data.storage import Storage

logger = logging.getLogger(__name__)


@dataclass
class MetricsSummary:
    """
    Summary of performance metrics.

    Contains aggregated metrics for a specific time period.

    Attributes:
        period_start: Start of the metrics period
        period_end: End of the metrics period
        total_trades: Total number of trades
        successful_trades: Number of successful trades
        failed_trades: Number of failed trades
        success_rate: Percentage of successful trades
        total_volume: Total traded volume
        total_fees: Total fees paid
        avg_execution_time_ms: Average trade execution time
        avg_slippage_pct: Average slippage percentage
        days_traded: Number of unique trading days
    """
    period_start: datetime
    period_end: datetime
    total_trades: int = 0
    successful_trades: int = 0
    failed_trades: int = 0
    success_rate: float = 0.0
    total_volume: float = 0.0
    total_fees: float = 0.0
    avg_execution_time_ms: float = 0.0
    avg_slippage_pct: float = 0.0
    days_traded: int = 0
    largest_trade: float = 0.0
    smallest_trade: float = 0.0
    most_common_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_trades": self.total_trades,
            "successful_trades": self.successful_trades,
            "failed_trades": self.failed_trades,
            "success_rate": round(self.success_rate, 2),
            "total_volume": round(self.total_volume, 4),
            "total_fees": round(self.total_fees, 6),
            "avg_execution_time_ms": round(self.avg_execution_time_ms, 2),
            "avg_slippage_pct": round(self.avg_slippage_pct, 4),
            "days_traded": self.days_traded,
            "largest_trade": round(self.largest_trade, 4),
            "smallest_trade": round(self.smallest_trade, 4),
            "most_common_error": self.most_common_error,
        }


@dataclass
class RealTimeMetrics:
    """
    Real-time metrics that are updated incrementally.

    These metrics are maintained in memory and can be persisted periodically.
    """
    # Counters
    trades_total: int = 0
    trades_success: int = 0
    trades_failed: int = 0

    # Running totals
    volume_total: float = 0.0
    fees_total: float = 0.0

    # Timing
    execution_times_ms: List[float] = field(default_factory=list)
    last_trade_time: Optional[datetime] = None

    # Slippage tracking
    slippages: List[float] = field(default_factory=list)

    # Error tracking
    errors: Dict[str, int] = field(default_factory=dict)

    # Session info
    session_start: datetime = field(default_factory=datetime.utcnow)

    def update(self, trade_result: TradeResult, execution_time_ms: float = 0) -> None:
        """
        Update metrics with a new trade result.

        Args:
            trade_result: The trade result to record
            execution_time_ms: Execution time in milliseconds
        """
        self.trades_total += 1
        self.last_trade_time = datetime.utcnow()

        if trade_result.success:
            self.trades_success += 1
            self.volume_total += trade_result.executed_value
            self.fees_total += trade_result.fees

            if execution_time_ms > 0:
                self.execution_times_ms.append(execution_time_ms)

            if trade_result.slippage is not None:
                self.slippages.append(trade_result.slippage)
        else:
            self.trades_failed += 1
            error = trade_result.error or "unknown"
            self.errors[error] = self.errors.get(error, 0) + 1

    @property
    def success_rate(self) -> float:
        """Calculate current success rate."""
        if self.trades_total == 0:
            return 0.0
        return (self.trades_success / self.trades_total) * 100

    @property
    def avg_execution_time(self) -> float:
        """Calculate average execution time."""
        if not self.execution_times_ms:
            return 0.0
        return mean(self.execution_times_ms)

    @property
    def avg_slippage(self) -> float:
        """Calculate average slippage."""
        if not self.slippages:
            return 0.0
        return mean(self.slippages)

    @property
    def most_common_error(self) -> Optional[str]:
        """Get the most common error."""
        if not self.errors:
            return None
        return max(self.errors, key=self.errors.get)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trades_total": self.trades_total,
            "trades_success": self.trades_success,
            "trades_failed": self.trades_failed,
            "success_rate": round(self.success_rate, 2),
            "volume_total": round(self.volume_total, 4),
            "fees_total": round(self.fees_total, 6),
            "avg_execution_time_ms": round(self.avg_execution_time, 2),
            "avg_slippage_pct": round(self.avg_slippage, 4),
            "most_common_error": self.most_common_error,
            "error_counts": self.errors,
            "session_start": self.session_start.isoformat(),
            "last_trade_time": self.last_trade_time.isoformat() if self.last_trade_time else None,
        }


class MetricsTracker:
    """
    Tracks and calculates performance metrics for the trading bot.

    Provides both real-time metrics (updated incrementally) and historical
    metrics (calculated from stored data).

    Attributes:
        storage: Storage instance for accessing trade history
        realtime: Real-time metrics for current session
    """

    def __init__(self, storage: Optional[Storage] = None, data_dir: Optional[str] = None):
        """
        Initialize the metrics tracker.

        Args:
            storage: Optional Storage instance. Creates new one if not provided.
            data_dir: Directory for data storage (only used if storage not provided)
        """
        self.storage = storage or Storage(data_dir)
        self.realtime = RealTimeMetrics()
        logger.info("MetricsTracker initialized")

    def update(self, trade_result: TradeResult, execution_time_ms: float = 0) -> None:
        """
        Update metrics with a new trade result.

        Args:
            trade_result: The trade result to record
            execution_time_ms: Execution time in milliseconds
        """
        self.realtime.update(trade_result, execution_time_ms)

        logger.debug(
            f"Metrics updated: "
            f"Success rate: {self.realtime.success_rate:.1f}% "
            f"({self.realtime.trades_success}/{self.realtime.trades_total})"
        )

    def get_summary(self, period: str = "session") -> MetricsSummary:
        """
        Get metrics summary for a specified period.

        Args:
            period: One of "session", "day", "week", "month", "all"

        Returns:
            MetricsSummary for the requested period
        """
        now = datetime.utcnow()

        if period == "session":
            return self._get_session_summary()
        elif period == "day":
            start = now - timedelta(days=1)
        elif period == "week":
            start = now - timedelta(weeks=1)
        elif period == "month":
            start = now - timedelta(days=30)
        else:  # "all"
            start = datetime.min

        return self._calculate_summary(start, now)

    def _get_session_summary(self) -> MetricsSummary:
        """Get summary for current session (real-time metrics)."""
        rt = self.realtime

        return MetricsSummary(
            period_start=rt.session_start,
            period_end=datetime.utcnow(),
            total_trades=rt.trades_total,
            successful_trades=rt.trades_success,
            failed_trades=rt.trades_failed,
            success_rate=rt.success_rate,
            total_volume=rt.volume_total,
            total_fees=rt.fees_total,
            avg_execution_time_ms=rt.avg_execution_time,
            avg_slippage_pct=rt.avg_slippage,
            most_common_error=rt.most_common_error,
        )

    def _calculate_summary(self, start: datetime, end: datetime) -> MetricsSummary:
        """
        Calculate metrics summary from stored trade history.

        Args:
            start: Start of the period
            end: End of the period

        Returns:
            Calculated MetricsSummary
        """
        # Get all trades and filter by date
        all_trades = self.storage.get_all_trades()
        trades = [t for t in all_trades if start <= t.timestamp <= end]

        if not trades:
            return MetricsSummary(period_start=start, period_end=end)

        # Calculate metrics
        successful = [t for t in trades if t.success]
        failed = [t for t in trades if not t.success]

        # Volumes and fees
        volumes = [t.executed_value for t in successful if t.executed_value]
        total_volume = sum(volumes) if volumes else 0.0
        total_fees = sum(t.fees for t in successful)

        # Slippage
        slippages = [t.slippage for t in successful if t.slippage is not None]
        avg_slippage = mean(slippages) if slippages else 0.0

        # Days traded
        unique_days = set(t.timestamp.date() for t in successful)

        # Error tracking
        errors: Dict[str, int] = {}
        for t in failed:
            error = t.error or "unknown"
            errors[error] = errors.get(error, 0) + 1
        most_common = max(errors, key=errors.get) if errors else None

        return MetricsSummary(
            period_start=start,
            period_end=end,
            total_trades=len(trades),
            successful_trades=len(successful),
            failed_trades=len(failed),
            success_rate=(len(successful) / len(trades)) * 100 if trades else 0.0,
            total_volume=total_volume,
            total_fees=total_fees,
            avg_slippage_pct=avg_slippage,
            days_traded=len(unique_days),
            largest_trade=max(volumes) if volumes else 0.0,
            smallest_trade=min(volumes) if volumes else 0.0,
            most_common_error=most_common,
        )

    def get_success_rate(self, period: str = "week") -> float:
        """
        Get the success rate for a specified period.

        Args:
            period: Time period for calculation

        Returns:
            Success rate as percentage (0-100)
        """
        summary = self.get_summary(period)
        return summary.success_rate

    def get_total_volume(self, period: str = "week") -> float:
        """
        Get total traded volume for a specified period.

        Args:
            period: Time period for calculation

        Returns:
            Total volume traded
        """
        summary = self.get_summary(period)
        return summary.total_volume

    def get_total_fees(self, period: str = "week") -> float:
        """
        Get total fees paid for a specified period.

        Args:
            period: Time period for calculation

        Returns:
            Total fees paid
        """
        summary = self.get_summary(period)
        return summary.total_fees

    def get_daily_breakdown(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get daily metrics breakdown for the past N days.

        Args:
            days: Number of days to include

        Returns:
            List of daily metrics dictionaries
        """
        now = datetime.utcnow()
        daily_metrics = []

        for i in range(days):
            day_end = now - timedelta(days=i)
            day_start = day_end - timedelta(days=1)
            day_start = day_start.replace(hour=8, minute=0, second=0, microsecond=0)
            day_end = day_end.replace(hour=8, minute=0, second=0, microsecond=0)

            summary = self._calculate_summary(day_start, day_end)
            daily_metrics.append({
                "date": day_start.date().isoformat(),
                "trades": summary.total_trades,
                "success_rate": summary.success_rate,
                "volume": summary.total_volume,
                "fees": summary.total_fees,
            })

        return daily_metrics

    def get_error_breakdown(self, period: str = "week") -> Dict[str, int]:
        """
        Get breakdown of errors by type.

        Args:
            period: Time period for calculation

        Returns:
            Dictionary of error types and their counts
        """
        now = datetime.utcnow()

        if period == "day":
            start = now - timedelta(days=1)
        elif period == "week":
            start = now - timedelta(weeks=1)
        elif period == "month":
            start = now - timedelta(days=30)
        else:
            start = datetime.min

        all_trades = self.storage.get_all_trades()
        failed = [t for t in all_trades if not t.success and start <= t.timestamp <= now]

        errors: Dict[str, int] = {}
        for t in failed:
            error = t.error or "unknown"
            errors[error] = errors.get(error, 0) + 1

        return errors

    def check_health(self) -> Dict[str, Any]:
        """
        Check the health of trading operations.

        Returns:
            Health check results with warnings/alerts
        """
        week_summary = self.get_summary("week")
        alerts = []
        status = "healthy"

        # Check success rate
        if week_summary.success_rate < 90:
            alerts.append({
                "level": "warning",
                "message": f"Low success rate: {week_summary.success_rate:.1f}%"
            })
            status = "warning"

        if week_summary.success_rate < 80:
            alerts.append({
                "level": "critical",
                "message": f"Critical success rate: {week_summary.success_rate:.1f}%"
            })
            status = "critical"

        # Check consecutive failures
        recent_trades = self.storage.get_recent_trades(5)
        consecutive_failures = 0
        for t in recent_trades:
            if not t.success:
                consecutive_failures += 1
            else:
                break

        if consecutive_failures >= 3:
            alerts.append({
                "level": "critical",
                "message": f"{consecutive_failures} consecutive failures"
            })
            status = "critical"

        # Check days traded
        if week_summary.days_traded < 5 and datetime.utcnow().weekday() >= 4:
            alerts.append({
                "level": "warning",
                "message": f"Only {week_summary.days_traded} days traded, may miss max factor"
            })

        return {
            "status": status,
            "alerts": alerts,
            "metrics": week_summary.to_dict(),
            "checked_at": datetime.utcnow().isoformat(),
        }

    def reset_session(self) -> None:
        """Reset real-time session metrics."""
        self.realtime = RealTimeMetrics()
        logger.info("Session metrics reset")

    def export_metrics(self, filepath: str) -> bool:
        """
        Export metrics to a JSON file.

        Args:
            filepath: Path to export file

        Returns:
            True if export was successful
        """
        import json

        try:
            metrics_data = {
                "exported_at": datetime.utcnow().isoformat(),
                "session": self._get_session_summary().to_dict(),
                "day": self.get_summary("day").to_dict(),
                "week": self.get_summary("week").to_dict(),
                "month": self.get_summary("month").to_dict(),
                "all_time": self.get_summary("all").to_dict(),
                "daily_breakdown": self.get_daily_breakdown(30),
                "errors": self.get_error_breakdown("all"),
                "health": self.check_health(),
            }

            with open(filepath, "w") as f:
                json.dump(metrics_data, f, indent=2)

            logger.info(f"Metrics exported to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
            return False
