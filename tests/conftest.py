"""
Pytest Configuration and Fixtures for ApexOmni Trading Bot Tests.

This module provides shared fixtures and configuration for all test modules.
"""

import pytest
import sys
import os
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import project modules
from bot.config import Config, APIConfig, TradingConfig, SafetyConfig, ScheduleConfig
from bot.api_client import (
    ApexOmniClient,
    MockApexOmniClient,
    AccountBalance,
    SymbolConfig,
    OrderResult,
)
from bot.trade_executor import Trade as ExecutorTrade, TradeResult as ExecutorTradeResult, TradeExecutor
from bot.strategy import StakingOptimizationStrategy
from data.models import Trade, TradeResult, WeeklyTradeRecord, StakingInfo, TradeStatus
from data.storage import Storage
from data.collector import DataCollector
from data.metrics import MetricsTracker


# =============================================================================
# Configuration Fixtures
# =============================================================================

@pytest.fixture
def api_config():
    """Create a test API configuration."""
    return APIConfig(
        api_key="test_api_key_12345678",
        api_secret="test_api_secret_1234567890abcdef",
        passphrase="test_passphrase",
        zk_seeds="test_zk_seeds",
        zk_l2key="test_zk_l2key",
        testnet=True,
        network="testnet",
    )


@pytest.fixture
def trading_config():
    """Create a test trading configuration."""
    return TradingConfig(
        symbol="BTC-USDT",  # DEPRECATED - bot always auto-selects cheapest
        side="BUY",
        order_type="MARKET",
        size=Decimal("0.001"),
        # REMOVED: leverage - hardcoded to 1
        # REMOVED: close_position - hardcoded to True
        # REMOVED: auto_select_symbol - bot ALWAYS auto-selects
        min_trade_value_usdt=Decimal("0.01"),
    )


@pytest.fixture
def safety_config():
    """Create a test safety configuration."""
    return SafetyConfig(
        dry_run=True,
        max_position_size=Decimal("0.01"),
        max_daily_trades=5,
        min_balance=Decimal("50.0"),
        require_balance_check=True,
        max_retries=3,
        retry_delay=0.1,  # Faster for tests
    )


@pytest.fixture
def schedule_config():
    """Create a test schedule configuration."""
    return ScheduleConfig(
        mode="daily",  # NEW
        trade_interval_hours=4,  # NEW
        trade_days=[0, 1, 2, 3, 4],  # Monday to Friday
        trade_time="09:00",
        timezone="UTC",
        continue_after_max_factor=True,  # NEW
    )


@pytest.fixture
def config(api_config, trading_config, safety_config, schedule_config):
    """Create a complete test configuration."""
    return Config(
        api=api_config,
        trading=trading_config,
        safety=safety_config,
        schedule=schedule_config,
        log_level="DEBUG",
        log_file=None,
        data_dir="test_data",
    )


# =============================================================================
# API Client Fixtures
# =============================================================================

@pytest.fixture
def mock_account_balance():
    """Create a mock account balance."""
    return AccountBalance(
        total_equity=Decimal("1000.0"),
        available_balance=Decimal("950.0"),
        margin_balance=Decimal("1000.0"),
        unrealized_pnl=Decimal("0.0"),
    )


@pytest.fixture
def mock_symbol_config():
    """Create a mock symbol configuration."""
    return SymbolConfig(
        symbol="BTC-USDT",
        base_currency="BTC",
        quote_currency="USDT",
        min_order_size=Decimal("0.001"),
        tick_size=Decimal("0.1"),
        step_size=Decimal("0.001"),
        max_leverage=100,
    )


@pytest.fixture
def mock_order_result():
    """Create a mock successful order result."""
    return OrderResult(
        success=True,
        order_id="TEST-ORDER-001",
        client_order_id="client-TEST-001",
        symbol="BTC-USDT",
        side="BUY",
        order_type="MARKET",
        size=Decimal("0.001"),
        price=Decimal("95000.0"),
        filled_size=Decimal("0.001"),
        filled_price=Decimal("95000.0"),
        status="FILLED",
        fee=Decimal("0.0475"),  # 0.05% of 95
        timestamp=1700000000000,
    )


@pytest.fixture
def failed_order_result():
    """Create a mock failed order result."""
    return OrderResult(
        success=False,
        error="Insufficient balance",
    )


@pytest.fixture
def mock_api_client(api_config, mock_account_balance, mock_symbol_config, mock_order_result):
    """Create a mock ApexOmni API client."""
    return MockApexOmniClient(api_config)


@pytest.fixture
def patched_api_client(api_config, mock_account_balance, mock_symbol_config, mock_order_result):
    """Create a patched real API client that doesn't make actual requests."""
    client = ApexOmniClient(api_config)

    # Patch all methods that would make API calls
    client.test_connection = Mock(return_value=True)
    client.get_account_balance = Mock(return_value=mock_account_balance)
    client.get_symbol_config = Mock(return_value=mock_symbol_config)
    client.get_current_price = Mock(return_value=Decimal("95000.0"))
    client.place_order = Mock(return_value=mock_order_result)
    client.cancel_order = Mock(return_value=True)
    client.get_open_orders = Mock(return_value=[])
    client.get_positions = Mock(return_value=[])
    client.get_trade_fills = Mock(return_value=[])

    return client


# =============================================================================
# Trade Fixtures
# =============================================================================

@pytest.fixture
def sample_trade():
    """Create a sample trade (data.models.Trade)."""
    return Trade(
        symbol="BTC-USDT",
        side="buy",
        size=0.001,
        price=95000.0,
        order_type="market",
        leverage=1,
        day_number=1,
    )


@pytest.fixture
def sample_executor_trade():
    """Create a sample trade (bot.trade_executor.Trade)."""
    return ExecutorTrade(
        symbol="BTC-USDT",
        side="BUY",
        order_type="MARKET",
        size=Decimal("0.001"),
        price=Decimal("95000.0"),
        day_number=1,
        # REMOVED: leverage - hardcoded to 1
        # REMOVED: close_position - hardcoded to True
    )


@pytest.fixture
def sample_trade_result(sample_trade):
    """Create a sample trade result."""
    return TradeResult(
        trade=sample_trade,
        success=True,
        order_id="TEST-ORDER-001",
        executed_price=95000.0,
        executed_size=0.001,
        fees=0.0475,
        timestamp=datetime.utcnow(),
        status=TradeStatus.FILLED,
    )


@pytest.fixture
def failed_trade_result(sample_trade):
    """Create a failed trade result."""
    return TradeResult(
        trade=sample_trade,
        success=False,
        error="Insufficient balance",
        status=TradeStatus.FAILED,
    )


@pytest.fixture
def sample_weekly_trades():
    """Create a list of sample trades for a week."""
    trades = []
    base_time = datetime.utcnow().replace(hour=10, minute=0, second=0, microsecond=0)

    for day in range(5):  # Monday to Friday
        trade = Trade(
            symbol="BTC-USDT",
            side="buy",
            size=0.001,
            price=95000.0 + (day * 100),
            order_type="market",
            day_number=day + 1,
        )
        result = TradeResult(
            trade=trade,
            success=True,
            order_id=f"ORDER-{day + 1:03d}",
            executed_price=95000.0 + (day * 100),
            executed_size=0.001,
            fees=0.0475,
            timestamp=base_time - timedelta(days=4 - day),
            status=TradeStatus.FILLED,
        )
        trades.append(result)

    return trades


# =============================================================================
# Storage and Data Fixtures
# =============================================================================

@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for tests."""
    temp_dir = tempfile.mkdtemp(prefix="apex_test_")
    yield temp_dir
    # Cleanup after test
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def storage(temp_data_dir):
    """Create a storage instance with temp directory."""
    return Storage(data_dir=temp_data_dir)


@pytest.fixture
def data_collector(storage):
    """Create a data collector instance."""
    return DataCollector(storage=storage)


@pytest.fixture
def metrics_tracker(storage):
    """Create a metrics tracker instance."""
    return MetricsTracker(storage=storage)


@pytest.fixture
def sample_weekly_record():
    """Create a sample weekly trade record."""
    now = datetime.utcnow()
    # Get Monday of current week
    monday = now - timedelta(days=now.weekday())
    monday = monday.replace(hour=8, minute=0, second=0, microsecond=0)

    return WeeklyTradeRecord(
        week_start=monday,
        week_end=monday + timedelta(days=7),
        trades=[],
        days_traded=set(),
    )


@pytest.fixture
def sample_staking_info():
    """Create sample staking info."""
    return StakingInfo(
        staked_amount=1000.0,
        lock_months=6,
        start_date=datetime.utcnow() - timedelta(days=30),
    )


# =============================================================================
# Trade Executor Fixtures
# =============================================================================

@pytest.fixture
def trade_executor(mock_api_client, config, temp_data_dir):
    """Create a trade executor with mock client."""
    config.data_dir = temp_data_dir
    return TradeExecutor(client=mock_api_client, config=config)


# =============================================================================
# Strategy Fixtures
# =============================================================================

@pytest.fixture
def strategy(config):
    """Create a staking optimization strategy."""
    return StakingOptimizationStrategy(config)


# =============================================================================
# Environment and Config File Fixtures
# =============================================================================

@pytest.fixture
def temp_env_file(temp_data_dir):
    """Create a temporary .env file."""
    env_path = Path(temp_data_dir) / ".env"
    env_content = """
APEX_API_KEY=test_key_from_env
APEX_API_SECRET=test_secret_from_env
APEX_PASSPHRASE=test_passphrase_from_env
APEX_ZK_SEEDS=test_seeds_from_env
APEX_ZK_L2KEY=test_l2key_from_env
APEX_TESTNET=true
DRY_RUN=true
LOG_LEVEL=DEBUG
"""
    env_path.write_text(env_content.strip())
    return str(env_path)


@pytest.fixture
def temp_yaml_config(temp_data_dir):
    """Create a temporary YAML config file."""
    yaml_path = Path(temp_data_dir) / "config.yaml"
    yaml_content = """
api:
  endpoint: testnet

trading:
  # symbol is DEPRECATED - bot always auto-selects cheapest tradeable symbol
  # symbol: ETH-USDT  # Ignored
  side: SELL
  type: LIMIT
  size: 0.01
  # NOTE: leverage and close_position are no longer configurable
  # They are hardcoded to 1 and True respectively for safety
  # NOTE: auto_select_symbol REMOVED - bot ALWAYS auto-selects
  min_trade_value_usdt: 0.01

safety:
  dry_run: true
  max_position_size: 0.1
  max_daily_trades: 3
  min_balance: 100.0
  require_balance_check: true

schedule:
  mode: daily
  trade_interval_hours: 4
  trade_days: [0, 1, 2, 3, 4, 5, 6]
  trade_time: "10:00"
  timezone: UTC
  continue_after_max_factor: true

log_level: INFO
data_dir: custom_data
"""
    yaml_path.write_text(yaml_content.strip())
    return str(yaml_path)


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def mock_datetime():
    """Mock datetime for consistent time-based tests."""
    # Monday at 10 AM UTC
    fixed_time = datetime(2024, 1, 15, 10, 0, 0)
    return fixed_time


@pytest.fixture
def freeze_time(mock_datetime):
    """Context manager to freeze time for tests."""
    with patch('bot.utils.get_current_utc_time') as mock:
        mock.return_value = mock_datetime
        yield mock_datetime


# =============================================================================
# Markers Configuration
# =============================================================================

def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, isolated)")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "dry_run: Dry-run simulation tests")
    config.addinivalue_line("markers", "slow: Slow tests")
