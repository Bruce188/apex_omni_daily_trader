"""
Analytics module for ApexOmni Trading Bot.

This module provides staking multiplier calculations and performance analytics
for optimizing staking rewards through strategic trading.
"""

from analytics.multiplier_analysis import MultiplierCalculator
from analytics.performance import PerformanceAnalyzer, WeeklyPerformanceSummary

__all__ = [
    "MultiplierCalculator",
    "PerformanceAnalyzer",
    "WeeklyPerformanceSummary",
]
