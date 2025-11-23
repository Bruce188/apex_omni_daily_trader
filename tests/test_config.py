"""
Tests for Configuration Management.

Tests cover:
- Loading from .env
- Loading from YAML
- Validation errors
- Default values
- Environment variable overrides
"""

import pytest
import sys
import os
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bot.config import (
    Config,
    APIConfig,
    TradingConfig,
    SafetyConfig,
    ScheduleConfig,
)


# =============================================================================
# APIConfig Tests
# =============================================================================

class TestAPIConfig:
    """Tests for API configuration."""

    def test_default_values(self):
        """Should have correct default values."""
        config = APIConfig()
        assert config.api_key == ""
        assert config.api_secret == ""
        assert config.passphrase == ""
        assert config.testnet is True
        assert config.network == "testnet"

    def test_testnet_endpoint(self):
        """Should return testnet endpoint."""
        config = APIConfig(testnet=True)
        assert "testnet" in config.endpoint

    def test_mainnet_endpoint(self):
        """Should return mainnet endpoint."""
        config = APIConfig(testnet=False, network="mainnet")
        assert "testnet" not in config.endpoint

    def test_network_id_testnet(self):
        """Should return testnet network ID."""
        config = APIConfig(testnet=True)
        assert config.network_id == 5

    def test_network_id_mainnet(self):
        """Should return mainnet network ID."""
        config = APIConfig(testnet=False, network="mainnet")
        assert config.network_id == 1

    def test_validation_missing_api_key(self):
        """Should report missing API key."""
        config = APIConfig(api_secret="secret", passphrase="pass")
        errors = config.validate()
        assert any("APEX_API_KEY" in e for e in errors)

    def test_validation_missing_api_secret(self):
        """Should report missing API secret."""
        config = APIConfig(api_key="key", passphrase="pass")
        errors = config.validate()
        assert any("APEX_API_SECRET" in e for e in errors)

    def test_validation_missing_passphrase(self):
        """Should report missing passphrase."""
        config = APIConfig(api_key="key", api_secret="secret")
        errors = config.validate()
        assert any("APEX_PASSPHRASE" in e for e in errors)

    def test_validation_all_present(self):
        """Should return no errors when all required fields present."""
        config = APIConfig(
            api_key="key",
            api_secret="secret",
            passphrase="pass",
        )
        errors = config.validate()
        assert len(errors) == 0


# =============================================================================
# TradingConfig Tests
# =============================================================================

class TestTradingConfig:
    """Tests for trading configuration."""

    def test_default_values(self):
        """Should have correct default values."""
        config = TradingConfig()
        assert config.symbol == "BTC-USDT"
        assert config.side == "BUY"
        assert config.order_type == "MARKET"
        assert config.size == Decimal("0.001")
        # NOTE: leverage and close_position are hardcoded (not in TradingConfig)

    def test_validation_valid_config(self):
        """Should accept valid trading config."""
        config = TradingConfig(
            symbol="ETH-USDT",
            side="SELL",
            order_type="LIMIT",
            size=Decimal("0.1"),
            # NOTE: leverage is hardcoded to 1
        )
        errors = config.validate()
        assert len(errors) == 0

    def test_validation_symbol_ignored(self):
        """Symbol validation removed - bot always auto-selects cheapest."""
        # NOTE: Symbol field is now deprecated and not validated
        # The bot always auto-selects the cheapest tradeable symbol
        config = TradingConfig(symbol="BTCUSDT")  # No dash - but ignored
        errors = config.validate()
        # No symbol validation errors - field is deprecated
        assert not any("symbol" in e.lower() for e in errors)

    def test_validation_invalid_side(self):
        """Should reject invalid side."""
        config = TradingConfig(side="LONG")
        errors = config.validate()
        assert any("side" in e.lower() for e in errors)

    def test_validation_invalid_order_type(self):
        """Should reject invalid order type."""
        config = TradingConfig(order_type="STOP")
        errors = config.validate()
        assert any("order_type" in e.lower() for e in errors)

    def test_validation_negative_size(self):
        """Should reject negative size."""
        config = TradingConfig(size=Decimal("-0.001"))
        errors = config.validate()
        assert any("size" in e.lower() for e in errors)

    def test_validation_zero_size(self):
        """Should reject zero size."""
        config = TradingConfig(size=Decimal("0"))
        errors = config.validate()
        assert any("size" in e.lower() for e in errors)

    # NOTE: test_validation_invalid_leverage_low and test_validation_invalid_leverage_high removed
    # Leverage is now hardcoded to 1 and not part of TradingConfig


# =============================================================================
# SafetyConfig Tests
# =============================================================================

class TestSafetyConfig:
    """Tests for safety configuration."""

    def test_default_values(self):
        """Should have correct default values."""
        config = SafetyConfig()
        assert config.dry_run is True
        assert config.max_position_size == Decimal("0.01")
        assert config.max_daily_trades == 5
        assert config.min_balance == Decimal("50.0")
        assert config.require_balance_check is True
        assert config.max_retries == 3
        assert config.retry_delay == 1.0

    def test_validation_valid_config(self):
        """Should accept valid safety config."""
        config = SafetyConfig(
            max_position_size=Decimal("1.0"),
            min_balance=Decimal("100.0"),
            max_retries=5,
        )
        errors = config.validate()
        assert len(errors) == 0

    def test_validation_negative_max_position(self):
        """Should reject negative max position size."""
        config = SafetyConfig(max_position_size=Decimal("-1.0"))
        errors = config.validate()
        assert any("max_position_size" in e for e in errors)

    def test_validation_negative_min_balance(self):
        """Should reject negative min balance."""
        config = SafetyConfig(min_balance=Decimal("-50.0"))
        errors = config.validate()
        assert any("min_balance" in e for e in errors)

    def test_validation_negative_retries(self):
        """Should reject negative max retries."""
        config = SafetyConfig(max_retries=-1)
        errors = config.validate()
        assert any("max_retries" in e for e in errors)


# =============================================================================
# ScheduleConfig Tests
# =============================================================================

class TestScheduleConfig:
    """Tests for schedule configuration."""

    def test_default_values(self):
        """Should have correct default values."""
        config = ScheduleConfig()
        assert config.mode == "daily"
        assert config.trade_interval_hours == 4
        assert config.trade_days == [0, 1, 2, 3, 4, 5, 6]  # All 7 days (24/7)
        assert config.trade_time == "09:00"
        assert config.timezone == "UTC"
        assert config.continue_after_max_factor is True

    def test_validation_valid_config(self):
        """Should accept valid schedule config."""
        config = ScheduleConfig(
            mode="continuous",
            trade_interval_hours=6,
            trade_days=[0, 2, 4],  # Mon, Wed, Fri
            trade_time="14:30",
            continue_after_max_factor=False,
        )
        errors = config.validate()
        assert len(errors) == 0

    def test_validation_invalid_day(self):
        """Should reject invalid day number."""
        config = ScheduleConfig(trade_days=[0, 1, 7])  # 7 is invalid
        errors = config.validate()
        assert any("trade day" in e.lower() for e in errors)

    def test_validation_allows_more_than_5_days(self):
        """Should allow more than 5 trading days (staking factor maxes at 5 but trading continues)."""
        config = ScheduleConfig(mode="daily", trade_days=[0, 1, 2, 3, 4, 5])  # 6 days
        errors = config.validate()
        # No errors expected - more than 5 days is valid
        # Staking factor maxes at 5 unique days but user may want to trade more
        assert len(errors) == 0

    def test_validation_invalid_mode(self):
        """Should reject invalid schedule mode."""
        config = ScheduleConfig(mode="invalid")
        errors = config.validate()
        assert any("mode" in e.lower() for e in errors)

    def test_validation_invalid_interval(self):
        """Should reject invalid trade interval."""
        config = ScheduleConfig(trade_interval_hours=0)
        errors = config.validate()
        assert any("trade_interval_hours" in e for e in errors)

        config = ScheduleConfig(trade_interval_hours=25)
        errors = config.validate()
        assert any("trade_interval_hours" in e for e in errors)

    def test_post_init_converts_tuple_to_list(self):
        """Should convert tuple trade_days to list."""
        config = ScheduleConfig(trade_days=(0, 1, 2))
        assert isinstance(config.trade_days, list)
        assert config.trade_days == [0, 1, 2]


# =============================================================================
# Config Integration Tests
# =============================================================================

class TestConfig:
    """Tests for main Config class."""

    def test_default_config(self):
        """Should create config with all defaults."""
        config = Config()
        assert isinstance(config.api, APIConfig)
        assert isinstance(config.trading, TradingConfig)
        assert isinstance(config.safety, SafetyConfig)
        assert isinstance(config.schedule, ScheduleConfig)

    def test_is_valid_all_valid(self):
        """Should return True when all configs valid."""
        config = Config(
            api=APIConfig(api_key="key", api_secret="secret", passphrase="pass"),
            trading=TradingConfig(),
            safety=SafetyConfig(),
            schedule=ScheduleConfig(),
        )
        assert config.is_valid() is True

    def test_is_valid_with_errors(self):
        """Should return False when configs have errors."""
        config = Config(
            api=APIConfig(),  # Missing credentials
            trading=TradingConfig(),
            safety=SafetyConfig(),
            schedule=ScheduleConfig(),
        )
        assert config.is_valid() is False

    def test_validate_aggregates_errors(self):
        """Should aggregate errors from all sub-configs."""
        config = Config(
            api=APIConfig(),  # Missing credentials (3 errors)
            trading=TradingConfig(side="INVALID"),  # 1 error
            safety=SafetyConfig(),
            schedule=ScheduleConfig(),
        )
        errors = config.validate()
        assert len(errors) >= 4


# =============================================================================
# YAML Loading Tests
# =============================================================================

class TestYAMLLoading:
    """Tests for loading config from YAML files."""

    def test_load_from_yaml(self, temp_yaml_config):
        """Should load config from YAML file."""
        config = Config()
        config._load_yaml(temp_yaml_config)

        # NOTE: symbol is now DEPRECATED - bot always auto-selects cheapest
        # Symbol from YAML is loaded but ignored at runtime
        assert config.trading.side == "SELL"
        assert config.trading.order_type == "LIMIT"
        assert config.trading.size == Decimal("0.01")
        # NOTE: leverage and close_position are hardcoded (not loaded from YAML)

    def test_yaml_safety_config(self, temp_yaml_config):
        """Should load safety config from YAML."""
        config = Config()
        config._load_yaml(temp_yaml_config)

        assert config.safety.dry_run is True
        assert config.safety.max_position_size == Decimal("0.1")
        assert config.safety.max_daily_trades == 3
        assert config.safety.min_balance == Decimal("100.0")

    def test_yaml_schedule_config(self, temp_yaml_config):
        """Should load schedule config from YAML."""
        config = Config()
        config._load_yaml(temp_yaml_config)

        assert config.schedule.mode == "daily"
        assert config.schedule.trade_interval_hours == 4
        assert config.schedule.trade_time == "10:00"
        assert config.schedule.timezone == "UTC"
        assert config.schedule.continue_after_max_factor is True


# =============================================================================
# Environment Variable Tests
# =============================================================================

class TestEnvLoading:
    """Tests for loading config from environment variables."""

    def test_load_api_credentials_from_env(self):
        """Should load API credentials from environment."""
        with patch.dict(os.environ, {
            "APEX_API_KEY": "env_key",
            "APEX_API_SECRET": "env_secret",
            "APEX_PASSPHRASE": "env_pass",
            "APEX_ZK_SEEDS": "env_seeds",
            "APEX_ZK_L2KEY": "env_l2key",
        }):
            config = Config()
            config._load_env()

            assert config.api.api_key == "env_key"
            assert config.api.api_secret == "env_secret"
            assert config.api.passphrase == "env_pass"
            assert config.api.zk_seeds == "env_seeds"
            assert config.api.zk_l2key == "env_l2key"

    def test_env_testnet_override_true(self):
        """Should set testnet=True from env."""
        with patch.dict(os.environ, {"APEX_TESTNET": "true"}, clear=False):
            config = Config()
            config._load_env()
            assert config.api.testnet is True

    def test_env_testnet_override_false(self):
        """Should set testnet=False from env."""
        with patch.dict(os.environ, {"APEX_TESTNET": "false"}, clear=False):
            config = Config()
            config._load_env()
            assert config.api.testnet is False

    def test_env_dry_run_override(self):
        """Should override dry_run from env."""
        with patch.dict(os.environ, {"DRY_RUN": "false"}, clear=False):
            config = Config()
            config._load_env()
            assert config.safety.dry_run is False

    def test_env_log_level_override(self):
        """Should override log_level from env."""
        with patch.dict(os.environ, {"LOG_LEVEL": "WARNING"}, clear=False):
            config = Config()
            config._load_env()
            assert config.log_level == "WARNING"

    def test_env_network_override(self):
        """Should override network from env."""
        with patch.dict(os.environ, {"APEX_NETWORK": "mainnet"}, clear=False):
            config = Config()
            config._load_env()
            assert config.api.network == "mainnet"
            assert config.api.testnet is False


# =============================================================================
# Config.load() Tests
# =============================================================================

class TestConfigLoad:
    """Tests for Config.load() class method."""

    def test_load_without_file(self):
        """Should load config without config file."""
        with patch.dict(os.environ, {
            "APEX_API_KEY": "test_key",
            "APEX_API_SECRET": "test_secret",
            "APEX_PASSPHRASE": "test_pass",
        }, clear=False):
            config = Config.load(config_file=None)
            assert config.api.api_key == "test_key"

    def test_load_with_yaml_file(self, temp_yaml_config):
        """Should load config from YAML file and env."""
        with patch.dict(os.environ, {
            "APEX_API_KEY": "env_key",
            "APEX_API_SECRET": "env_secret",
            "APEX_PASSPHRASE": "env_pass",
        }, clear=False):
            config = Config.load(config_file=temp_yaml_config)

            # YAML values (symbol is deprecated but other trading values load)
            # NOTE: symbol is now DEPRECATED - bot always auto-selects cheapest
            assert config.trading.side == "SELL"  # From YAML

            # Env values (highest priority)
            assert config.api.api_key == "env_key"

    def test_env_overrides_yaml(self, temp_yaml_config):
        """Environment variables should override YAML values."""
        with patch.dict(os.environ, {
            "APEX_API_KEY": "env_key",
            "APEX_API_SECRET": "env_secret",
            "APEX_PASSPHRASE": "env_pass",
            "DRY_RUN": "false",
        }, clear=False):
            config = Config.load(config_file=temp_yaml_config)

            # YAML says dry_run: true, but env says false
            assert config.safety.dry_run is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
