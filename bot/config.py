"""
Configuration management for the ApexOmni Trading Bot.

Loads configuration from environment variables and YAML files,
validates settings, and provides sensible defaults.
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from decimal import Decimal

import yaml
from dotenv import load_dotenv

from bot.utils import get_logger, parse_decimal, validate_symbol


# Load .env file from project root
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)


@dataclass
class APIConfig:
    """API configuration for ApexOmni."""

    api_key: str = ""
    api_secret: str = ""
    passphrase: str = ""
    zk_seeds: str = ""
    zk_l2key: str = ""

    # Network settings
    testnet: bool = True
    network: str = "testnet"

    @property
    def endpoint(self) -> str:
        """Get the API endpoint URL."""
        if self.testnet or self.network == "testnet":
            return "https://testnet.omni.apex.exchange"
        return "https://omni.apex.exchange"

    @property
    def network_id(self) -> int:
        """Get the network ID."""
        if self.testnet or self.network == "testnet":
            return 5  # Testnet network ID
        return 1  # Mainnet network ID

    def validate(self) -> list[str]:
        """Validate API configuration. Returns list of errors."""
        errors = []

        if not self.api_key:
            errors.append("APEX_API_KEY is required")
        if not self.api_secret:
            errors.append("APEX_API_SECRET is required")
        if not self.passphrase:
            errors.append("APEX_PASSPHRASE is required")

        # zkKeys are required for trading (but not for read-only operations)
        # We'll warn but not fail here since dry-run doesn't need them

        return errors


@dataclass
class TradingConfig:
    """
    Trading configuration.

    Note: leverage and close_position are NOT configurable.
    They are hardcoded to 1x and True respectively for safety.

    Symbol Selection: The bot ALWAYS auto-selects the cheapest tradeable symbol
    based on available balance. There is no "preferred" symbol concept.
    """

    # DEPRECATED: symbol field kept for backward compatibility but NOT used for preference
    # The bot always selects the cheapest tradeable symbol automatically
    symbol: str = "BTC-USDT"  # Ignored - bot auto-selects cheapest symbol
    side: str = "BUY"
    order_type: str = "MARKET"
    size: Decimal = Decimal("0.001")
    # REMOVED: leverage - hardcoded to 1 for safety
    # REMOVED: close_position - hardcoded to True for safety

    # REMOVED: auto_select_symbol - bot ALWAYS auto-selects (no option to disable)
    min_trade_value_usdt: Decimal = Decimal("0.01")  # Minimum trade value target in USDT


    def validate(self) -> list[str]:
        """Validate trading configuration. Returns list of errors."""
        errors = []

        # NOTE: symbol validation removed - bot auto-selects cheapest tradeable symbol

        if self.side.upper() not in ("BUY", "SELL"):
            errors.append(f"Invalid side: {self.side}. Must be BUY or SELL")

        if self.order_type.upper() not in ("MARKET", "LIMIT"):
            errors.append(f"Invalid order_type: {self.order_type}. Must be MARKET or LIMIT")

        if self.size <= 0:
            errors.append(f"Size must be positive: {self.size}")

        if self.min_trade_value_usdt <= 0:
            errors.append(f"min_trade_value_usdt must be positive: {self.min_trade_value_usdt}")


        # REMOVED: leverage validation (hardcoded to 1)

        return errors


@dataclass
class SafetyConfig:
    """Safety and risk management configuration."""

    dry_run: bool = True
    max_position_size: Decimal = Decimal("0.01")
    max_daily_trades: int = 5
    min_balance: Decimal = Decimal("50.0")
    require_balance_check: bool = True
    max_retries: int = 3
    retry_delay: float = 1.0

    def validate(self) -> list[str]:
        """Validate safety configuration. Returns list of errors."""
        errors = []

        if self.max_position_size <= 0:
            errors.append(f"max_position_size must be positive: {self.max_position_size}")

        if self.min_balance < 0:
            errors.append(f"min_balance cannot be negative: {self.min_balance}")

        if self.max_retries < 0:
            errors.append(f"max_retries cannot be negative: {self.max_retries}")

        return errors


@dataclass
class ScheduleConfig:
    """
    Trade scheduling configuration.

    Supports two modes:
    - "daily": One trade per day at scheduled time (legacy behavior)
    - "continuous": Trades at regular intervals 24/7
    """

    mode: str = "daily"  # "daily" or "continuous"
    trade_interval_hours: int = 4  # For continuous mode
    trade_days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])  # All 7 days (24/7)
    trade_time: str = "09:00"  # For daily mode (UTC)
    timezone: str = "UTC"
    continue_after_max_factor: bool = True  # Keep trading after 5 unique days?

    def __post_init__(self):
        """Ensure trade_days is a list (may come as tuple from YAML)."""
        if isinstance(self.trade_days, tuple):
            self.trade_days = list(self.trade_days)

    def validate(self) -> list[str]:
        """Validate schedule configuration. Returns list of errors."""
        errors = []

        if self.mode not in ("daily", "continuous"):
            errors.append(f"Invalid schedule mode: {self.mode}. Must be 'daily' or 'continuous'")

        if self.trade_interval_hours < 1 or self.trade_interval_hours > 24:
            errors.append(f"trade_interval_hours must be 1-24, got: {self.trade_interval_hours}")

        if not self.trade_days:
            errors.append("trade_days cannot be empty")

        for day in self.trade_days:
            if not 0 <= day <= 6:
                errors.append(f"Invalid trade day: {day}. Must be 0-6 (Mon-Sun)")

        # Note: >5 trade days is allowed - staking factor maxes at 5 unique days
        # but user may want to trade every day for volume or other reasons

        return errors


@dataclass
class Config:
    """Main configuration container."""

    api: APIConfig = field(default_factory=APIConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)

    log_level: str = "INFO"
    log_file: Optional[str] = None
    data_dir: str = "data"

    @classmethod
    def load(cls, config_file: Optional[str] = None) -> "Config":
        """
        Load configuration from environment and optional YAML file.

        Args:
            config_file: Path to YAML config file (optional)

        Returns:
            Config instance
        """
        logger = get_logger()
        config = cls()

        # Load from YAML file if provided
        if config_file and Path(config_file).exists():
            logger.info(f"Loading configuration from {config_file}")
            config._load_yaml(config_file)
        else:
            # Try default config location
            default_config = PROJECT_ROOT / "config" / "trading.yaml"
            if default_config.exists():
                logger.info(f"Loading configuration from {default_config}")
                config._load_yaml(str(default_config))

        # Override with environment variables (highest priority)
        config._load_env()

        return config

    def _load_yaml(self, config_file: str) -> None:
        """Load configuration from YAML file."""
        with open(config_file, "r") as f:
            data = yaml.safe_load(f) or {}

        # API config (most comes from env, but some from yaml)
        if "api" in data:
            api_data = data["api"]
            if "endpoint" in api_data:
                self.api.network = api_data["endpoint"]
                self.api.testnet = api_data["endpoint"] == "testnet"

        # Trading config
        if "trading" in data:
            trading_data = data["trading"]
            # NOTE: symbol field is ignored - bot always auto-selects cheapest tradeable symbol
            if "symbol" in trading_data:
                self.trading.symbol = trading_data["symbol"]  # Kept for backward compat, but ignored
            if "side" in trading_data:
                self.trading.side = trading_data["side"]
            if "type" in trading_data:
                self.trading.order_type = trading_data["type"]
            if "size" in trading_data:
                self.trading.size = parse_decimal(trading_data["size"])
            # REMOVED: leverage - hardcoded to 1 for safety
            # REMOVED: close_position - hardcoded to True for safety
            # REMOVED: auto_select_symbol - bot ALWAYS auto-selects cheapest symbol
            if "min_trade_value_usdt" in trading_data:
                self.trading.min_trade_value_usdt = parse_decimal(trading_data["min_trade_value_usdt"])

        # Safety config
        if "safety" in data:
            safety_data = data["safety"]
            if "dry_run" in safety_data:
                self.safety.dry_run = safety_data["dry_run"]
            if "max_position_size" in safety_data:
                self.safety.max_position_size = parse_decimal(safety_data["max_position_size"])
            if "max_daily_trades" in safety_data:
                self.safety.max_daily_trades = int(safety_data["max_daily_trades"])
            if "min_balance" in safety_data:
                self.safety.min_balance = parse_decimal(safety_data["min_balance"])
            if "require_balance_check" in safety_data:
                self.safety.require_balance_check = safety_data["require_balance_check"]

        # Schedule config
        if "schedule" in data:
            schedule_data = data["schedule"]
            if "mode" in schedule_data:
                self.schedule.mode = schedule_data["mode"]
            if "trade_interval_hours" in schedule_data:
                self.schedule.trade_interval_hours = int(schedule_data["trade_interval_hours"])
            if "trade_days" in schedule_data:
                self.schedule.trade_days = list(schedule_data["trade_days"])
            if "trade_time" in schedule_data:
                self.schedule.trade_time = schedule_data["trade_time"]
            if "timezone" in schedule_data:
                self.schedule.timezone = schedule_data["timezone"]
            if "continue_after_max_factor" in schedule_data:
                self.schedule.continue_after_max_factor = schedule_data["continue_after_max_factor"]

        # Logging
        if "log_level" in data:
            self.log_level = data["log_level"]
        if "log_file" in data:
            self.log_file = data["log_file"]
        if "data_dir" in data:
            self.data_dir = data["data_dir"]

    def _load_env(self) -> None:
        """Load configuration from environment variables."""
        # API credentials (always from env for security)
        self.api.api_key = os.getenv("APEX_API_KEY", "")
        self.api.api_secret = os.getenv("APEX_API_SECRET", "")
        self.api.passphrase = os.getenv("APEX_PASSPHRASE", "")
        self.api.zk_seeds = os.getenv("APEX_ZK_SEEDS", "")
        self.api.zk_l2key = os.getenv("APEX_ZK_L2KEY", "")

        # Network override
        network = os.getenv("APEX_NETWORK", "")
        if network:
            self.api.network = network
            self.api.testnet = network.lower() == "testnet"

        # Testnet override
        testnet_env = os.getenv("APEX_TESTNET", "")
        if testnet_env.lower() in ("true", "1", "yes"):
            self.api.testnet = True
            self.api.network = "testnet"
        elif testnet_env.lower() in ("false", "0", "no"):
            self.api.testnet = False
            self.api.network = "mainnet"

        # Safety override (can force dry_run from env)
        dry_run_env = os.getenv("DRY_RUN", "")
        if dry_run_env.lower() in ("true", "1", "yes"):
            self.safety.dry_run = True
        elif dry_run_env.lower() in ("false", "0", "no"):
            self.safety.dry_run = False

        # Logging override
        log_level = os.getenv("LOG_LEVEL", "")
        if log_level:
            self.log_level = log_level

    def validate(self) -> list[str]:
        """
        Validate all configuration.

        Returns:
            List of validation error messages
        """
        errors = []

        errors.extend(self.api.validate())
        errors.extend(self.trading.validate())
        errors.extend(self.safety.validate())
        errors.extend(self.schedule.validate())

        return errors

    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return len(self.validate()) == 0

    def print_summary(self) -> None:
        """Print configuration summary (safe for logging)."""
        logger = get_logger()

        from bot.utils import mask_api_key

        logger.info("=" * 50)
        logger.info("Configuration Summary")
        logger.info("=" * 50)

        # API (masked)
        logger.info(f"API Key: {mask_api_key(self.api.api_key)}")
        logger.info(f"Network: {self.api.network}")
        logger.info(f"Endpoint: {self.api.endpoint}")

        # Trading
        logger.info("Symbol Selection: AUTO (always selects cheapest tradeable)")
        logger.info(f"Side: {self.trading.side}")
        logger.info(f"Order Type: {self.trading.order_type}")
        logger.info(f"Size: {self.trading.size}")
        logger.info("Leverage: 1x (hardcoded)")
        logger.info("Close Position: Always (hardcoded)")
        logger.info(f"Min Trade Value: {self.trading.min_trade_value_usdt} USDT")

        # Safety
        logger.info(f"Dry Run: {self.safety.dry_run}")
        logger.info(f"Max Position Size: {self.safety.max_position_size}")
        logger.info(f"Min Balance: {self.safety.min_balance}")

        # Schedule
        days_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
        trade_days_str = ", ".join(days_map.get(d, str(d)) for d in self.schedule.trade_days)
        logger.info(f"Schedule Mode: {self.schedule.mode}")
        logger.info(f"Trade Days: {trade_days_str}")
        if self.schedule.mode == "continuous":
            logger.info(f"Trade Interval: {self.schedule.trade_interval_hours}h")
            logger.info(f"Continue After Max Factor: {self.schedule.continue_after_max_factor}")
        else:
            logger.info(f"Trade Time: {self.schedule.trade_time} {self.schedule.timezone}")

        logger.info("=" * 50)
