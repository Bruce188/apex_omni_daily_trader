"""
Performance Analytics for ApexOmni Trading Bot.

This module provides comprehensive performance analysis including:
- Weekly performance summaries
- Trade success analysis
- Cost analysis (fees and slippage)
- ROI calculations
- Trend analysis
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from statistics import mean, stdev

from data.models import TradeResult, WeeklyTradeRecord
from data.storage import Storage
from analytics.multiplier_analysis import MultiplierCalculator

logger = logging.getLogger(__name__)


@dataclass
class WeeklyPerformanceSummary:
    """
    Comprehensive weekly performance summary.

    Attributes:
        week_start: Start of the week (Monday 8AM UTC)
        week_end: End of the week
        days_traded: Number of unique days traded
        trading_factor: Trading Activity Factor achieved
        total_factor: Total staking factor (with time factor)
        trades_executed: Total trades attempted
        trades_successful: Successful trades
        trades_failed: Failed trades
        success_rate: Percentage of successful trades
        total_volume: Total traded volume
        total_fees: Total fees paid
        net_cost: Net cost of trading (fees + losses)
        avg_slippage_pct: Average slippage percentage
        effective_stake_multiplier: Improvement from trading activity
    """
    week_start: datetime
    week_end: datetime
    days_traded: int = 0
    trading_factor: float = 0.0
    total_factor: float = 1.0
    trades_executed: int = 0
    trades_successful: int = 0
    trades_failed: int = 0
    success_rate: float = 0.0
    total_volume: float = 0.0
    total_fees: float = 0.0
    net_cost: float = 0.0
    avg_slippage_pct: float = 0.0
    effective_stake_multiplier: float = 1.0
    max_factor_achieved: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "week_start": self.week_start.isoformat(),
            "week_end": self.week_end.isoformat(),
            "days_traded": self.days_traded,
            "trading_factor": round(self.trading_factor, 2),
            "total_factor": round(self.total_factor, 4),
            "trades_executed": self.trades_executed,
            "trades_successful": self.trades_successful,
            "trades_failed": self.trades_failed,
            "success_rate": round(self.success_rate, 2),
            "total_volume": round(self.total_volume, 4),
            "total_fees": round(self.total_fees, 6),
            "net_cost": round(self.net_cost, 6),
            "avg_slippage_pct": round(self.avg_slippage_pct, 4),
            "effective_stake_multiplier": round(self.effective_stake_multiplier, 4),
            "max_factor_achieved": self.max_factor_achieved,
        }

    def __str__(self) -> str:
        """Human-readable summary."""
        status = "MAX FACTOR!" if self.max_factor_achieved else f"{5 - self.days_traded} days remaining"
        return (
            f"Week of {self.week_start.strftime('%Y-%m-%d')}\n"
            f"  Days Traded: {self.days_traded}/5 ({status})\n"
            f"  Trading Factor: {self.trading_factor:.2f}\n"
            f"  Total Factor: {self.total_factor:.2f}x\n"
            f"  Trades: {self.trades_successful}/{self.trades_executed} successful ({self.success_rate:.1f}%)\n"
            f"  Total Fees: ${self.total_fees:.4f}\n"
            f"  Volume: ${self.total_volume:.2f}"
        )


@dataclass
class CostAnalysis:
    """
    Detailed cost analysis for trading operations.

    Attributes:
        period_start: Start of analysis period
        period_end: End of analysis period
        total_fees: Total trading fees paid
        total_slippage_cost: Estimated cost from slippage
        total_cost: Combined cost (fees + slippage)
        cost_per_trade: Average cost per trade
        cost_per_day: Average daily cost
        fee_rate_avg: Average fee rate
    """
    period_start: datetime
    period_end: datetime
    total_fees: float = 0.0
    total_slippage_cost: float = 0.0
    total_cost: float = 0.0
    cost_per_trade: float = 0.0
    cost_per_day: float = 0.0
    fee_rate_avg: float = 0.0
    trades_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_fees": round(self.total_fees, 6),
            "total_slippage_cost": round(self.total_slippage_cost, 6),
            "total_cost": round(self.total_cost, 6),
            "cost_per_trade": round(self.cost_per_trade, 6),
            "cost_per_day": round(self.cost_per_day, 6),
            "fee_rate_avg": round(self.fee_rate_avg, 4),
            "trades_count": self.trades_count,
        }


@dataclass
class ROIAnalysis:
    """
    Return on Investment analysis.

    Compares staking rewards gained vs trading costs incurred.

    Attributes:
        period: Analysis period description
        staking_reward_estimate: Estimated additional rewards from trading
        trading_cost: Total cost of trading activity
        net_roi: Net return (rewards - costs)
        roi_percentage: ROI as percentage
    """
    period: str
    staking_reward_estimate: float = 0.0
    trading_cost: float = 0.0
    net_roi: float = 0.0
    roi_percentage: float = 0.0
    break_even_stake: float = 0.0  # Minimum stake for positive ROI

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "period": self.period,
            "staking_reward_estimate": round(self.staking_reward_estimate, 4),
            "trading_cost": round(self.trading_cost, 6),
            "net_roi": round(self.net_roi, 4),
            "roi_percentage": round(self.roi_percentage, 2),
            "break_even_stake": round(self.break_even_stake, 2),
        }


class PerformanceAnalyzer:
    """
    Comprehensive performance analysis for the trading bot.

    Provides analytics including:
    - Weekly performance summaries
    - Trade success analysis
    - Cost analysis
    - ROI calculations
    - Trend analysis

    Attributes:
        storage: Storage instance for accessing data
        multiplier_calc: MultiplierCalculator for factor calculations
    """

    def __init__(
        self,
        storage: Optional[Storage] = None,
        data_dir: Optional[str] = None,
        staked_amount: float = 0,
        lock_months: int = 0
    ):
        """
        Initialize the performance analyzer.

        Args:
            storage: Optional Storage instance
            data_dir: Directory for data storage
            staked_amount: Amount staked (for ROI calculations)
            lock_months: Lock-up period in months
        """
        self.storage = storage or Storage(data_dir)
        self.multiplier_calc = MultiplierCalculator(staked_amount, lock_months)
        self.staked_amount = staked_amount
        self.lock_months = lock_months

        logger.info("PerformanceAnalyzer initialized")

    def get_weekly_summary(
        self,
        week_start: Optional[datetime] = None
    ) -> WeeklyPerformanceSummary:
        """
        Get comprehensive summary for a specific week.

        Args:
            week_start: Start of week to analyze. Defaults to current week.

        Returns:
            WeeklyPerformanceSummary with all metrics
        """
        if week_start is None:
            week_start, week_end = Storage.get_current_week_boundaries()
        else:
            week_end = week_start + timedelta(days=7)

        # Get weekly record
        record = self.storage.get_weekly_record(week_start)

        if record is None:
            return WeeklyPerformanceSummary(
                week_start=week_start,
                week_end=week_end,
            )

        # Calculate metrics
        trades = record.trades
        successful = [t for t in trades if t.success]
        failed = [t for t in trades if not t.success]

        total_volume = sum(t.executed_value for t in successful if t.executed_value)
        total_fees = sum(t.fees for t in successful)

        # Calculate slippage costs
        slippages = [t.slippage for t in successful if t.slippage is not None]
        avg_slippage = mean(slippages) if slippages else 0.0

        # Calculate factors
        trading_factor = record.trading_activity_factor
        time_factor = self.multiplier_calc.calculate_time_factor(self.lock_months)
        total_factor = 1.0 + time_factor + trading_factor

        # Effective stake multiplier (improvement from trading)
        base_factor = 1.0 + time_factor
        effective_multiplier = total_factor / base_factor if base_factor > 0 else 1.0

        success_rate = (len(successful) / len(trades) * 100) if trades else 0.0

        return WeeklyPerformanceSummary(
            week_start=week_start,
            week_end=week_end,
            days_traded=record.num_days_traded,
            trading_factor=trading_factor,
            total_factor=total_factor,
            trades_executed=len(trades),
            trades_successful=len(successful),
            trades_failed=len(failed),
            success_rate=success_rate,
            total_volume=total_volume,
            total_fees=total_fees,
            net_cost=total_fees,  # Add slippage cost if needed
            avg_slippage_pct=avg_slippage,
            effective_stake_multiplier=effective_multiplier,
            max_factor_achieved=record.num_days_traded >= 5,
        )

    def get_current_week_summary(self) -> WeeklyPerformanceSummary:
        """
        Get summary for the current staking week.

        Returns:
            WeeklyPerformanceSummary for current week
        """
        week_start, _ = Storage.get_current_week_boundaries()
        return self.get_weekly_summary(week_start)

    def analyze_trade_success(
        self,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze trade success patterns.

        Args:
            period_days: Number of days to analyze

        Returns:
            Analysis dictionary with success patterns
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=period_days)

        all_trades = self.storage.get_all_trades()
        trades = [t for t in all_trades if start_date <= t.timestamp <= end_date]

        if not trades:
            return {
                "period_days": period_days,
                "total_trades": 0,
                "success_rate": 0.0,
                "patterns": {},
            }

        successful = [t for t in trades if t.success]
        failed = [t for t in trades if not t.success]

        # Analyze by day of week
        day_analysis = {}
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for day in range(7):
            day_trades = [t for t in trades if t.timestamp.weekday() == day]
            day_success = [t for t in day_trades if t.success]

            if day_trades:
                day_analysis[day_names[day]] = {
                    "total": len(day_trades),
                    "success": len(day_success),
                    "rate": (len(day_success) / len(day_trades)) * 100,
                }

        # Analyze by hour
        hour_analysis = {}
        for hour in range(24):
            hour_trades = [t for t in trades if t.timestamp.hour == hour]
            hour_success = [t for t in hour_trades if t.success]

            if hour_trades:
                hour_analysis[hour] = {
                    "total": len(hour_trades),
                    "success": len(hour_success),
                    "rate": (len(hour_success) / len(hour_trades)) * 100,
                }

        # Error analysis
        error_counts: Dict[str, int] = {}
        for t in failed:
            error = t.error or "unknown"
            error_counts[error] = error_counts.get(error, 0) + 1

        return {
            "period_days": period_days,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_trades": len(trades),
            "successful_trades": len(successful),
            "failed_trades": len(failed),
            "success_rate": (len(successful) / len(trades)) * 100,
            "by_day_of_week": day_analysis,
            "by_hour": hour_analysis,
            "error_breakdown": error_counts,
            "most_common_error": max(error_counts, key=error_counts.get) if error_counts else None,
        }

    def analyze_costs(
        self,
        period_days: int = 30
    ) -> CostAnalysis:
        """
        Analyze trading costs.

        Args:
            period_days: Number of days to analyze

        Returns:
            CostAnalysis with detailed breakdown
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=period_days)

        all_trades = self.storage.get_all_trades()
        trades = [t for t in all_trades if start_date <= t.timestamp <= end_date and t.success]

        if not trades:
            return CostAnalysis(
                period_start=start_date,
                period_end=end_date,
            )

        total_fees = sum(t.fees for t in trades)
        total_volume = sum(t.executed_value for t in trades if t.executed_value)

        # Estimate slippage cost
        slippage_costs = []
        for t in trades:
            if t.slippage is not None and t.executed_value:
                # Negative slippage = cost, positive = benefit
                cost = (t.slippage / 100) * t.executed_value
                if cost > 0:  # Only count negative slippage as cost
                    slippage_costs.append(cost)

        total_slippage_cost = sum(slippage_costs)
        total_cost = total_fees + total_slippage_cost

        # Average fee rate
        fee_rate = (total_fees / total_volume * 100) if total_volume > 0 else 0.0

        return CostAnalysis(
            period_start=start_date,
            period_end=end_date,
            total_fees=total_fees,
            total_slippage_cost=total_slippage_cost,
            total_cost=total_cost,
            cost_per_trade=total_cost / len(trades) if trades else 0.0,
            cost_per_day=total_cost / period_days,
            fee_rate_avg=fee_rate,
            trades_count=len(trades),
        )

    def calculate_roi(
        self,
        weekly_reward_pool: float,
        total_pool_factor: float,
        period_weeks: int = 4
    ) -> ROIAnalysis:
        """
        Calculate return on investment from trading activity.

        Compares the additional staking rewards gained from trading
        against the costs of trading.

        Args:
            weekly_reward_pool: Weekly APEX reward pool
            total_pool_factor: Sum of all stakers' effective stakes
            period_weeks: Number of weeks to analyze

        Returns:
            ROIAnalysis with ROI calculations
        """
        # Get cost analysis for the period
        cost_analysis = self.analyze_costs(period_days=period_weeks * 7)
        total_cost = cost_analysis.total_cost

        # Calculate reward difference
        # Without trading activity factor (just time factor)
        base_factor = 1.0 + self.multiplier_calc.calculate_time_factor(self.lock_months)
        base_effective_stake = self.staked_amount * base_factor
        base_share = base_effective_stake / total_pool_factor if total_pool_factor > 0 else 0
        base_weekly_reward = base_share * weekly_reward_pool

        # With max trading activity factor
        max_factor = base_factor + 0.5  # +0.5 for 5 days trading
        max_effective_stake = self.staked_amount * max_factor
        max_share = max_effective_stake / total_pool_factor if total_pool_factor > 0 else 0
        max_weekly_reward = max_share * weekly_reward_pool

        # Additional reward from trading
        additional_reward_per_week = max_weekly_reward - base_weekly_reward
        total_additional_reward = additional_reward_per_week * period_weeks

        # Net ROI
        net_roi = total_additional_reward - total_cost
        roi_pct = (net_roi / total_cost * 100) if total_cost > 0 else float('inf')

        # Break-even stake calculation
        # At what stake does the additional reward cover costs?
        if additional_reward_per_week > 0:
            reward_per_apex = additional_reward_per_week / self.staked_amount if self.staked_amount > 0 else 0
            break_even = total_cost / (reward_per_apex * period_weeks) if reward_per_apex > 0 else float('inf')
        else:
            break_even = float('inf')

        return ROIAnalysis(
            period=f"{period_weeks} weeks",
            staking_reward_estimate=total_additional_reward,
            trading_cost=total_cost,
            net_roi=net_roi,
            roi_percentage=roi_pct,
            break_even_stake=break_even,
        )

    def get_trend_analysis(
        self,
        weeks: int = 8
    ) -> Dict[str, Any]:
        """
        Analyze performance trends over multiple weeks.

        Args:
            weeks: Number of weeks to analyze

        Returns:
            Trend analysis dictionary
        """
        weekly_records = self.storage.get_all_weekly_records()

        # Sort by week start date, most recent first
        weekly_records.sort(key=lambda r: r.week_start, reverse=True)
        weekly_records = weekly_records[:weeks]

        if not weekly_records:
            return {
                "weeks_analyzed": 0,
                "trends": {},
            }

        # Calculate weekly metrics
        weekly_metrics = []
        for record in weekly_records:
            summary = self.get_weekly_summary(record.week_start)
            weekly_metrics.append({
                "week_start": record.week_start.isoformat(),
                "days_traded": record.num_days_traded,
                "success_rate": summary.success_rate,
                "total_fees": summary.total_fees,
                "total_volume": summary.total_volume,
                "max_factor": record.num_days_traded >= 5,
            })

        # Calculate trends
        days_traded = [m["days_traded"] for m in weekly_metrics]
        success_rates = [m["success_rate"] for m in weekly_metrics if m["success_rate"] > 0]
        fees = [m["total_fees"] for m in weekly_metrics]

        avg_days = mean(days_traded) if days_traded else 0
        avg_success = mean(success_rates) if success_rates else 0
        avg_fees = mean(fees) if fees else 0

        # Count max factor weeks
        max_factor_weeks = sum(1 for m in weekly_metrics if m["max_factor"])

        return {
            "weeks_analyzed": len(weekly_metrics),
            "weekly_data": weekly_metrics,
            "averages": {
                "days_traded": round(avg_days, 2),
                "success_rate": round(avg_success, 2),
                "weekly_fees": round(avg_fees, 6),
            },
            "max_factor_achievement": {
                "weeks_achieved": max_factor_weeks,
                "achievement_rate": (max_factor_weeks / len(weekly_metrics) * 100) if weekly_metrics else 0,
            },
            "consistency": {
                "days_traded_stddev": round(stdev(days_traded), 2) if len(days_traded) > 1 else 0,
            },
        }

    def generate_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive performance report.

        Returns:
            Complete report dictionary
        """
        current_week = self.get_current_week_summary()
        success_analysis = self.analyze_trade_success(30)
        cost_analysis = self.analyze_costs(30)
        trends = self.get_trend_analysis(8)

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "current_week": current_week.to_dict(),
            "success_analysis": success_analysis,
            "cost_analysis": cost_analysis.to_dict(),
            "trends": trends,
            "staking_config": {
                "staked_amount": self.staked_amount,
                "lock_months": self.lock_months,
            },
        }

    def export_report(self, filepath: str) -> bool:
        """
        Export performance report to JSON file.

        Args:
            filepath: Path to export file

        Returns:
            True if export successful
        """
        import json

        try:
            report = self.generate_report()

            with open(filepath, "w") as f:
                json.dump(report, f, indent=2)

            logger.info(f"Report exported to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Failed to export report: {e}")
            return False
