"""
Utility functions for the ApexOmni Trading Bot.

Provides logging setup, date/time helpers, and validation utilities.
"""

import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from textwrap import dedent
from typing import Optional, TYPE_CHECKING
from decimal import Decimal, InvalidOperation

if TYPE_CHECKING:
    from bot.config import Config


# Constants for staking timing
WEEKLY_RESET_HOUR = 8  # 8 AM UTC
WEEKLY_RESET_DAY = 0   # Monday


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Configure logging for the trading bot.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to write logs to
        format_string: Optional custom format string

    Returns:
        Configured logger instance
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Create logger
    logger = logging.getLogger("apex_bot")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    console_formatter = logging.Formatter(format_string)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        file_formatter = logging.Formatter(format_string)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger() -> logging.Logger:
    """Get the trading bot logger instance."""
    return logging.getLogger("apex_bot")


def get_current_utc_time() -> datetime:
    """Get current UTC time with timezone info."""
    return datetime.now(timezone.utc)


def get_weekly_round_start() -> datetime:
    """
    Get the start of the current weekly staking round.

    Weekly rounds start Monday at 8AM UTC.

    Returns:
        datetime: Start of current weekly round
    """
    now = get_current_utc_time()

    # Calculate days since Monday
    days_since_monday = now.weekday()

    # Get Monday at 8AM UTC this week
    monday_8am = now.replace(hour=WEEKLY_RESET_HOUR, minute=0, second=0, microsecond=0)
    monday_8am = monday_8am - timedelta(days=days_since_monday)

    # If we're before Monday 8AM, go back to previous week
    if now < monday_8am:
        monday_8am = monday_8am - timedelta(weeks=1)

    return monday_8am


def get_weekly_round_end() -> datetime:
    """
    Get the end of the current weekly staking round.

    Returns:
        datetime: End of current weekly round (next Monday 8AM UTC)
    """
    return get_weekly_round_start() + timedelta(weeks=1)


def get_current_staking_day() -> int:
    """
    Get the current day number within the staking week (1-7).

    Day 1 = Monday after 8AM UTC
    Day 7 = Sunday after 8AM UTC

    Returns:
        int: Day number (1-7)
    """
    now = get_current_utc_time()
    round_start = get_weekly_round_start()

    # Calculate full days since round start
    delta = now - round_start
    day_number = delta.days + 1

    return min(max(day_number, 1), 7)


def get_staking_day_start(day_number: int) -> datetime:
    """
    Get the start time of a specific staking day.

    Args:
        day_number: Day number (1-7)

    Returns:
        datetime: Start of that staking day
    """
    round_start = get_weekly_round_start()
    return round_start + timedelta(days=day_number - 1)


def is_trade_day(days_to_trade: list[int] = None) -> bool:
    """
    Check if today is a configured trading day.

    Args:
        days_to_trade: List of weekday numbers (0=Monday, 6=Sunday)
                      Default fallback is [0, 1, 2, 3, 4] (Mon-Fri) if not specified.
                      Note: The bot's YAML config defaults to all 7 days.

    Returns:
        bool: True if today is a trading day
    """
    if days_to_trade is None:
        days_to_trade = [0, 1, 2, 3, 4]  # Fallback default (config default is all 7 days)

    now = get_current_utc_time()
    return now.weekday() in days_to_trade


def parse_decimal(value: str | float | int | Decimal, default: Decimal = Decimal("0")) -> Decimal:
    """
    Parse a value to Decimal, handling various input types.

    Args:
        value: Value to parse
        default: Default value if parsing fails or value is empty

    Returns:
        Decimal representation

    Raises:
        ValueError: If value cannot be parsed and no default provided
    """
    try:
        if isinstance(value, Decimal):
            return value
        # Handle empty strings and None
        if value is None or (isinstance(value, str) and value.strip() == ''):
            return default
        return Decimal(str(value))
    except InvalidOperation as e:
        raise ValueError(f"Cannot parse '{value}' as Decimal: {e}")


def format_price(price: Decimal | float, decimals: int = 2) -> str:
    """Format a price for display."""
    return f"{float(price):,.{decimals}f}"


def format_size(size: Decimal | float, decimals: int = 6) -> str:
    """Format a trade size for display."""
    return f"{float(size):.{decimals}f}"


def mask_api_key(api_key: str) -> str:
    """
    Mask an API key for safe logging.

    Shows first 4 and last 4 characters only.

    Args:
        api_key: The API key to mask

    Returns:
        Masked string like "abc1****xyz9"
    """
    if not api_key or len(api_key) < 8:
        return "***"
    return f"{api_key[:4]}****{api_key[-4:]}"


def validate_symbol(symbol: str) -> bool:
    """
    Validate a trading symbol format.

    Expected format: "BASE-QUOTE" (e.g., "BTC-USDT")

    Args:
        symbol: Trading symbol to validate

    Returns:
        bool: True if valid format
    """
    if not symbol or not isinstance(symbol, str):
        return False

    parts = symbol.split("-")
    if len(parts) != 2:
        return False

    base, quote = parts
    return len(base) > 0 and len(quote) > 0


def validate_side(side: str) -> bool:
    """
    Validate a trade side.

    Args:
        side: Trade side ("BUY" or "SELL")

    Returns:
        bool: True if valid
    """
    return side.upper() in ("BUY", "SELL")


def validate_order_type(order_type: str) -> bool:
    """
    Validate an order type.

    Args:
        order_type: Order type ("MARKET" or "LIMIT")

    Returns:
        bool: True if valid
    """
    return order_type.upper() in ("MARKET", "LIMIT")


def calculate_trading_activity_factor(days_traded: int) -> float:
    """
    Calculate the Trading Activity Factor based on days traded.

    Formula: Trading Activity Factor = 0.1 * days_traded (max 0.5)

    Args:
        days_traded: Number of days traded this week (0-5)

    Returns:
        float: Trading Activity Factor (0.0 to 0.5)
    """
    return min(0.1 * min(days_traded, 5), 0.5)


def calculate_total_staking_factor(
    time_factor: float = 0.0,
    days_traded: int = 0
) -> float:
    """
    Calculate the Total Staking Factor.

    Formula: Total Factor = 1 + Time Factor + Trading Activity Factor

    Args:
        time_factor: Time Factor from locked staking (0.0 to 2.0)
        days_traded: Number of days traded this week (0-5)

    Returns:
        float: Total Staking Factor
    """
    base_factor = 1.0
    trading_factor = calculate_trading_activity_factor(days_traded)
    return base_factor + time_factor + trading_factor


def warn_if_live_mainnet(config: "Config", logger: logging.Logger) -> bool:
    """
    Display warning if running in live mode on mainnet.

    Shows a countdown warning and allows user to abort within 5 seconds.

    Args:
        config: Bot configuration
        logger: Logger instance

    Returns:
        True if user confirms (or auto-confirms after timeout),
        False if user aborts with Ctrl+C.
    """
    # Dry run mode - no warning needed
    if config.safety.dry_run:
        return True

    # Testnet - no warning needed
    if config.api.testnet:
        return True

    # Live mode on mainnet - show warning
    warning = dedent("""
        ================================================================
                              WARNING
        ================================================================

          You are about to run in LIVE mode on MAINNET!

          - Real funds will be used for trading
          - Actual orders will be placed on ApexOmni
          - Losses are possible and irreversible

          Press Ctrl+C within 5 seconds to abort...

        ================================================================
    """).strip()

    logger.warning(warning)
    print(warning)

    try:
        for i in range(5, 0, -1):
            print(f"  Starting in {i} seconds...", end="\r")
            time.sleep(1)
        print("  Starting now!          ")
        return True
    except KeyboardInterrupt:
        print("\n  Aborted by user.")
        logger.info("Live mainnet trading aborted by user")
        return False
