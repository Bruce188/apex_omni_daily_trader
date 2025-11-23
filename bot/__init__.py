"""
ApexOmni Trading Bot - Core Package

A simple trading bot that executes 5 strategic trades on ApexOmni
to maximize the staking factor multiplication.
"""

from bot.config import Config, TradingConfig, SafetyConfig
from bot.api_client import ApexOmniClient
from bot.trade_executor import TradeExecutor, Trade, TradeResult
from bot.strategy import StakingOptimizationStrategy

__version__ = "1.0.0"
__all__ = [
    "Config",
    "TradingConfig",
    "SafetyConfig",
    "ApexOmniClient",
    "TradeExecutor",
    "Trade",
    "TradeResult",
    "StakingOptimizationStrategy",
]
