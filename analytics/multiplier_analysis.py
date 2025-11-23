"""
Staking Multiplier Calculator for ApexOmni Trading Bot.

This module implements the ApeX staking reward formula calculations
to help optimize staking rewards through strategic trading.

Formula Reference:
    Total Staking Factor = 1 + Time Factor + Trading Activity Factor

    Time Factor = Lock-Up Period (Months) / 12
    Trading Activity Factor = 0.1 * Days Traded (max 0.5)

Examples:
    - 6-month lock + 5 days traded: 1 + 0.5 + 0.5 = 2.0x
    - No lock + 5 days traded: 1 + 0 + 0.5 = 1.5x
    - 12-month lock + 0 days traded: 1 + 1.0 + 0 = 2.0x
    - 24-month lock + 5 days traded: 1 + 2.0 + 0.5 = 3.5x (maximum)
"""

import logging
from dataclasses import dataclass
from textwrap import dedent
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


# Constants
BASE_FACTOR = 1.0
MAX_TRADING_FACTOR = 0.5
TRADING_FACTOR_PER_DAY = 0.1
MAX_TRADING_DAYS = 5
MONTHS_IN_YEAR = 12


@dataclass
class MultiplierBreakdown:
    """
    Detailed breakdown of staking multiplier components.

    Attributes:
        base_factor: Base multiplier (always 1.0)
        time_factor: Factor from lock-up period
        trading_factor: Factor from trading activity
        total_factor: Combined total factor
        lock_months: Lock-up period in months
        days_traded: Number of days traded this week
    """
    base_factor: float
    time_factor: float
    trading_factor: float
    total_factor: float
    lock_months: int
    days_traded: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "base_factor": self.base_factor,
            "time_factor": round(self.time_factor, 4),
            "trading_factor": round(self.trading_factor, 2),
            "total_factor": round(self.total_factor, 4),
            "lock_months": self.lock_months,
            "days_traded": self.days_traded,
        }

    def __str__(self) -> str:
        """Human-readable string representation."""
        return (
            f"Staking Factor: {self.total_factor:.2f}x\n"
            f"  Base:    {self.base_factor:.1f}\n"
            f"  Time:    +{self.time_factor:.2f} ({self.lock_months} months lock)\n"
            f"  Trading: +{self.trading_factor:.2f} ({self.days_traded} days traded)"
        )


@dataclass
class RewardProjection:
    """
    Projected weekly staking rewards.

    Attributes:
        staked_amount: Amount of APEX staked
        staking_factor: User's total staking factor
        effective_stake: Weighted stake (amount * factor)
        pool_share_pct: Estimated share of reward pool
        estimated_reward: Estimated weekly reward in APEX
    """
    staked_amount: float
    staking_factor: float
    effective_stake: float
    pool_share_pct: float
    estimated_reward: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "staked_amount": self.staked_amount,
            "staking_factor": round(self.staking_factor, 4),
            "effective_stake": round(self.effective_stake, 2),
            "pool_share_pct": round(self.pool_share_pct, 6),
            "estimated_reward": round(self.estimated_reward, 4),
        }


class MultiplierCalculator:
    """
    Calculator for ApeX staking multiplier and reward projections.

    This class provides methods to:
    - Calculate individual factor components
    - Compute total staking factor
    - Project weekly rewards
    - Compare different staking scenarios

    Usage:
        calc = MultiplierCalculator(staked_amount=1000, lock_months=6)
        factor = calc.calculate_total_factor(days_traded=5)
        print(f"Your staking factor: {factor:.2f}x")
    """

    def __init__(
        self,
        staked_amount: float = 0,
        lock_months: int = 0
    ):
        """
        Initialize the multiplier calculator.

        Args:
            staked_amount: Amount of APEX staked
            lock_months: Lock-up period in months (0 for flexible staking)
        """
        self.staked_amount = staked_amount
        self.lock_months = lock_months

        # Validate inputs
        if staked_amount < 0:
            raise ValueError("Staked amount cannot be negative")
        if lock_months < 0:
            raise ValueError("Lock months cannot be negative")

        logger.debug(
            f"MultiplierCalculator initialized: "
            f"{staked_amount} APEX, {lock_months} months lock"
        )

    @staticmethod
    def calculate_time_factor(lock_months: int) -> float:
        """
        Calculate the Time Factor based on lock-up period.

        Formula: Time Factor = Lock-Up Period (Months) / 12

        Args:
            lock_months: Number of months tokens are locked

        Returns:
            Time Factor value

        Examples:
            - 3 months: 0.25
            - 6 months: 0.50
            - 12 months: 1.00
            - 24 months: 2.00
        """
        if lock_months < 0:
            raise ValueError("Lock months cannot be negative")

        return lock_months / MONTHS_IN_YEAR

    @staticmethod
    def calculate_trading_factor(days_traded: int) -> float:
        """
        Calculate the Trading Activity Factor.

        Formula: Trading Activity Factor = 0.1 * Days Traded (max 0.5)

        Args:
            days_traded: Number of unique days traded in the week (0-5)

        Returns:
            Trading Activity Factor value (0.0 to 0.5)

        Examples:
            - 1 day: 0.1
            - 3 days: 0.3
            - 5 days: 0.5 (maximum)
            - 7 days: 0.5 (capped)
        """
        if days_traded < 0:
            raise ValueError("Days traded cannot be negative")

        factor = TRADING_FACTOR_PER_DAY * days_traded
        return min(factor, MAX_TRADING_FACTOR)

    def calculate_total_factor(
        self,
        days_traded: int = 0,
        lock_months: Optional[int] = None
    ) -> float:
        """
        Calculate the total staking factor.

        Formula: Total Factor = 1 + Time Factor + Trading Activity Factor

        Args:
            days_traded: Number of unique days traded (0-5)
            lock_months: Override lock months (uses instance value if None)

        Returns:
            Total staking factor multiplier

        Examples:
            - 6-month lock, 5 days traded: 2.0x
            - No lock, 5 days traded: 1.5x
            - 24-month lock, 5 days traded: 3.5x
        """
        months = lock_months if lock_months is not None else self.lock_months

        time_factor = self.calculate_time_factor(months)
        trading_factor = self.calculate_trading_factor(days_traded)

        total = BASE_FACTOR + time_factor + trading_factor

        logger.debug(
            f"Total factor: {total:.2f} "
            f"(base: {BASE_FACTOR}, time: {time_factor:.2f}, trading: {trading_factor:.2f})"
        )

        return total

    def get_factor_breakdown(
        self,
        days_traded: int = 0,
        lock_months: Optional[int] = None
    ) -> MultiplierBreakdown:
        """
        Get detailed breakdown of all factor components.

        Args:
            days_traded: Number of unique days traded
            lock_months: Override lock months

        Returns:
            MultiplierBreakdown with all components
        """
        months = lock_months if lock_months is not None else self.lock_months

        time_factor = self.calculate_time_factor(months)
        trading_factor = self.calculate_trading_factor(days_traded)
        total_factor = BASE_FACTOR + time_factor + trading_factor

        return MultiplierBreakdown(
            base_factor=BASE_FACTOR,
            time_factor=time_factor,
            trading_factor=trading_factor,
            total_factor=total_factor,
            lock_months=months,
            days_traded=days_traded,
        )

    def calculate_effective_stake(
        self,
        days_traded: int = 0,
        staked_amount: Optional[float] = None
    ) -> float:
        """
        Calculate the effective (weighted) stake.

        Formula: Effective Stake = Staked Amount * Total Factor

        Args:
            days_traded: Number of days traded
            staked_amount: Override staked amount

        Returns:
            Effective stake value
        """
        amount = staked_amount if staked_amount is not None else self.staked_amount
        factor = self.calculate_total_factor(days_traded)

        return amount * factor

    def project_weekly_reward(
        self,
        pool_size: float,
        total_pool_factor: float,
        days_traded: int = 5,
        staked_amount: Optional[float] = None
    ) -> RewardProjection:
        """
        Project weekly staking reward based on pool parameters.

        Formula:
            User's Share = (User's Effective Stake) / Total Pool Factor
            Weekly Reward = User's Share * Weekly Reward Pool

        Args:
            pool_size: Total weekly reward pool in APEX
            total_pool_factor: Sum of all stakers' effective stakes
            days_traded: Number of days traded (default 5 for max factor)
            staked_amount: Override staked amount

        Returns:
            RewardProjection with estimated rewards
        """
        amount = staked_amount if staked_amount is not None else self.staked_amount
        factor = self.calculate_total_factor(days_traded)
        effective_stake = amount * factor

        if total_pool_factor <= 0:
            raise ValueError("Total pool factor must be positive")

        share_pct = (effective_stake / total_pool_factor) * 100
        reward = (effective_stake / total_pool_factor) * pool_size

        return RewardProjection(
            staked_amount=amount,
            staking_factor=factor,
            effective_stake=effective_stake,
            pool_share_pct=share_pct,
            estimated_reward=reward,
        )

    def compare_scenarios(
        self,
        scenarios: List[Dict[str, int]]
    ) -> List[MultiplierBreakdown]:
        """
        Compare multiple staking scenarios.

        Args:
            scenarios: List of dicts with 'lock_months' and 'days_traded'

        Returns:
            List of MultiplierBreakdown for each scenario

        Example:
            scenarios = [
                {"lock_months": 0, "days_traded": 0},
                {"lock_months": 6, "days_traded": 5},
                {"lock_months": 12, "days_traded": 5},
            ]
            results = calc.compare_scenarios(scenarios)
        """
        return [
            self.get_factor_breakdown(
                days_traded=s.get("days_traded", 0),
                lock_months=s.get("lock_months", self.lock_months)
            )
            for s in scenarios
        ]

    def days_to_max_trading_factor(self, current_days: int) -> int:
        """
        Calculate remaining days needed to reach max trading factor.

        Args:
            current_days: Number of days already traded

        Returns:
            Number of additional days needed (0 if already at max)
        """
        return max(0, MAX_TRADING_DAYS - current_days)

    def get_trading_factor_progress(self, days_traded: int) -> Dict[str, Any]:
        """
        Get progress toward maximum trading factor.

        Args:
            days_traded: Number of days traded

        Returns:
            Progress information dictionary
        """
        current = self.calculate_trading_factor(days_traded)
        remaining = self.days_to_max_trading_factor(days_traded)

        return {
            "days_traded": days_traded,
            "max_days": MAX_TRADING_DAYS,
            "remaining_days": remaining,
            "current_factor": current,
            "max_factor": MAX_TRADING_FACTOR,
            "progress_pct": (days_traded / MAX_TRADING_DAYS) * 100,
            "at_max": remaining == 0,
        }

    def optimal_lock_period(
        self,
        target_factor: float,
        days_traded: int = 5
    ) -> Optional[int]:
        """
        Calculate optimal lock period to achieve target factor.

        Args:
            target_factor: Desired total staking factor
            days_traded: Expected days traded (default 5)

        Returns:
            Required lock months, or None if impossible
        """
        trading_factor = self.calculate_trading_factor(days_traded)
        required_time_factor = target_factor - BASE_FACTOR - trading_factor

        if required_time_factor < 0:
            return 0  # No lock needed

        lock_months = int(required_time_factor * MONTHS_IN_YEAR)
        return lock_months

    def to_dict(self) -> Dict[str, Any]:
        """Convert calculator state to dictionary."""
        return {
            "staked_amount": self.staked_amount,
            "lock_months": self.lock_months,
            "time_factor": self.calculate_time_factor(self.lock_months),
            "max_trading_factor": MAX_TRADING_FACTOR,
            "base_factor": BASE_FACTOR,
        }


def quick_calculate(
    staked_amount: float,
    lock_months: int,
    days_traded: int
) -> Dict[str, Any]:
    """
    Quick calculation function for command-line usage.

    Args:
        staked_amount: Amount of APEX staked
        lock_months: Lock-up period in months
        days_traded: Number of days traded this week

    Returns:
        Dictionary with calculation results
    """
    calc = MultiplierCalculator(staked_amount, lock_months)
    breakdown = calc.get_factor_breakdown(days_traded)
    effective_stake = calc.calculate_effective_stake(days_traded)

    return {
        "input": {
            "staked_amount": staked_amount,
            "lock_months": lock_months,
            "days_traded": days_traded,
        },
        "factors": breakdown.to_dict(),
        "effective_stake": effective_stake,
        "summary": str(breakdown),
    }


def print_factor_table() -> None:
    """Print a reference table of staking factors."""
    lock_periods = [0, 3, 6, 12, 24]
    calc = MultiplierCalculator()

    # Build table rows
    rows = []
    for months in lock_periods:
        factors = [
            calc.calculate_total_factor(days, months)
            for days in range(6)
        ]
        factor_str = " | ".join(f"{f:.2f}x" for f in factors)
        period_name = f"{months:2d} months" if months > 0 else "No lock  "
        rows.append(f"{period_name}  |  {factor_str}")

    table_rows = "\n".join(rows)
    print(dedent(f"""

        === ApeX Staking Factor Reference Table ===

        Lock Period | 0 days | 1 day | 2 days | 3 days | 4 days | 5 days
        ----------------------------------------------------------------------
        {table_rows}

        Max achievable factor: 3.5x (24-month lock + 5 days trading)
    """).strip())
