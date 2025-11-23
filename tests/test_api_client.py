"""
Tests for ApexOmni API Client.

Tests cover:
- Client initialization
- Mock client functionality
- Authentication handling
- Error scenarios
- Rate limiting behavior
- Testnet and mainnet configurations
"""

import pytest
import sys
from pathlib import Path
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bot.api_client import (
    ApexOmniClient,
    MockApexOmniClient,
    AccountBalance,
    SymbolConfig,
    OrderResult,
    create_client,
)
from bot.config import APIConfig


# =============================================================================
# AccountBalance Tests
# =============================================================================

class TestAccountBalance:
    """Tests for AccountBalance dataclass."""

    def test_account_balance_creation(self):
        """Should create AccountBalance with all fields."""
        balance = AccountBalance(
            total_equity=Decimal("1000.0"),
            available_balance=Decimal("950.0"),
            margin_balance=Decimal("1000.0"),
            unrealized_pnl=Decimal("0.0"),
        )
        assert balance.total_equity == Decimal("1000.0")
        assert balance.available_balance == Decimal("950.0")
        assert balance.margin_balance == Decimal("1000.0")
        assert balance.unrealized_pnl == Decimal("0.0")


# =============================================================================
# SymbolConfig Tests
# =============================================================================

class TestSymbolConfig:
    """Tests for SymbolConfig dataclass."""

    def test_symbol_config_creation(self):
        """Should create SymbolConfig with all fields."""
        config = SymbolConfig(
            symbol="BTC-USDT",
            base_currency="BTC",
            quote_currency="USDT",
            min_order_size=Decimal("0.001"),
            tick_size=Decimal("0.1"),
            step_size=Decimal("0.001"),
            max_leverage=100,
        )
        assert config.symbol == "BTC-USDT"
        assert config.base_currency == "BTC"
        assert config.min_order_size == Decimal("0.001")
        assert config.max_leverage == 100


# =============================================================================
# OrderResult Tests
# =============================================================================

class TestOrderResult:
    """Tests for OrderResult dataclass."""

    def test_successful_order_result(self):
        """Should create successful OrderResult."""
        result = OrderResult(
            success=True,
            order_id="ORDER-001",
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
            price=Decimal("95000.0"),
            filled_size=Decimal("0.001"),
            filled_price=Decimal("95000.0"),
            status="FILLED",
            fee=Decimal("0.0475"),
        )
        assert result.success is True
        assert result.order_id == "ORDER-001"
        assert result.error is None

    def test_failed_order_result(self):
        """Should create failed OrderResult with error."""
        result = OrderResult(
            success=False,
            error="Insufficient balance",
        )
        assert result.success is False
        assert result.error == "Insufficient balance"
        assert result.order_id is None


# =============================================================================
# ApexOmniClient Tests
# =============================================================================

class TestApexOmniClient:
    """Tests for ApexOmniClient class."""

    def test_client_initialization(self, api_config):
        """Should initialize client with config."""
        client = ApexOmniClient(api_config)
        assert client.config == api_config
        assert client._client is None
        assert client._initialized is False

    def test_client_testnet_config(self, api_config):
        """Should use testnet configuration."""
        api_config.testnet = True
        api_config.network = "testnet"
        client = ApexOmniClient(api_config)
        assert client.config.testnet is True
        assert client.config.endpoint == "https://testnet.omni.apex.exchange"

    def test_client_mainnet_config(self, api_config):
        """Should use mainnet configuration."""
        api_config.testnet = False
        api_config.network = "mainnet"
        client = ApexOmniClient(api_config)
        assert client.config.testnet is False
        assert client.config.endpoint == "https://omni.apex.exchange"

    def test_place_order_validates_side(self, api_config):
        """Should reject invalid order side."""
        # Use a real client with SDK initialization mocked to test validation
        client = ApexOmniClient(api_config)
        # Mock _get_client and _ensure_sdk_initialized so we can test validation
        client._get_client = Mock(return_value=MagicMock())
        client._ensure_sdk_initialized = Mock(return_value=True)
        result = client.place_order(
            symbol="BTC-USDT",
            side="INVALID",
            order_type="MARKET",
            size=Decimal("0.001"),
            price=Decimal("95000.0"),
        )
        assert result.success is False
        assert "Invalid side" in result.error

    def test_place_order_validates_order_type(self, api_config):
        """Should reject invalid order type."""
        # Use a real client with SDK initialization mocked to test validation
        client = ApexOmniClient(api_config)
        # Mock _get_client and _ensure_sdk_initialized so we can test validation
        client._get_client = Mock(return_value=MagicMock())
        client._ensure_sdk_initialized = Mock(return_value=True)
        result = client.place_order(
            symbol="BTC-USDT",
            side="BUY",
            order_type="STOP",
            size=Decimal("0.001"),
            price=Decimal("95000.0"),
        )
        assert result.success is False
        assert "Invalid order type" in result.error


# =============================================================================
# MockApexOmniClient Tests
# =============================================================================

class TestMockApexOmniClient:
    """Tests for MockApexOmniClient (dry-run mode)."""

    def test_mock_client_test_connection(self, api_config):
        """Mock client should always return True for connection test."""
        client = MockApexOmniClient(api_config)
        assert client.test_connection() is True

    def test_mock_client_get_account_balance(self, api_config):
        """Mock client should return predefined balance."""
        client = MockApexOmniClient(api_config)
        balance = client.get_account_balance()
        assert balance is not None
        assert balance.total_equity == Decimal("1000.0")
        assert balance.available_balance == Decimal("950.0")

    def test_mock_client_get_current_price(self, api_config):
        """Mock client should return predefined price."""
        client = MockApexOmniClient(api_config)
        price = client.get_current_price("BTC-USDT")
        assert price == Decimal("95000.0")

    def test_mock_client_place_order_success(self, api_config):
        """Mock client should simulate successful order."""
        client = MockApexOmniClient(api_config)
        result = client.place_order(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
        )
        assert result.success is True
        assert result.order_id.startswith("MOCK-")
        assert result.symbol == "BTC-USDT"
        assert result.side == "BUY"
        assert result.filled_size == Decimal("0.001")
        assert result.status == "FILLED"

    def test_mock_client_order_counter_increments(self, api_config):
        """Mock client should increment order counter."""
        client = MockApexOmniClient(api_config)

        result1 = client.place_order(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
        )
        result2 = client.place_order(
            symbol="BTC-USDT",
            side="SELL",
            order_type="MARKET",
            size=Decimal("0.001"),
        )

        assert result1.order_id == "MOCK-000001"
        assert result2.order_id == "MOCK-000002"

    def test_mock_client_get_symbol_config(self, api_config):
        """Mock client should return symbol config for any symbol."""
        client = MockApexOmniClient(api_config)

        config = client.get_symbol_config("BTC-USDT")
        assert config is not None
        assert config.symbol == "BTC-USDT"
        assert config.base_currency == "BTC"
        assert config.quote_currency == "USDT"
        assert config.min_order_size == Decimal("0.001")

        config2 = client.get_symbol_config("ETH-USDT")
        assert config2.symbol == "ETH-USDT"
        assert config2.base_currency == "ETH"

    def test_mock_client_get_open_orders_empty(self, api_config):
        """Mock client should return empty open orders."""
        client = MockApexOmniClient(api_config)
        orders = client.get_open_orders()
        assert orders == []

    def test_mock_client_get_positions_empty(self, api_config):
        """Mock client should return empty positions."""
        client = MockApexOmniClient(api_config)
        positions = client.get_positions()
        assert positions == []

    def test_mock_client_calculates_fee(self, api_config):
        """Mock client should calculate realistic fee."""
        client = MockApexOmniClient(api_config)
        result = client.place_order(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
            price=Decimal("95000.0"),
        )
        # Fee is 0.05% of trade value (0.001 * 95000 * 0.0005)
        expected_fee = Decimal("0.001") * Decimal("95000.0") * Decimal("0.0005")
        assert result.fee == expected_fee


# =============================================================================
# Factory Function Tests
# =============================================================================

class TestCreateClient:
    """Tests for create_client factory function."""

    def test_create_dry_run_client(self, api_config):
        """Should create MockApexOmniClient for dry_run=True."""
        client = create_client(api_config, dry_run=True)
        assert isinstance(client, MockApexOmniClient)

    def test_create_real_client(self, api_config):
        """Should create ApexOmniClient for dry_run=False."""
        client = create_client(api_config, dry_run=False)
        assert isinstance(client, ApexOmniClient)
        assert not isinstance(client, MockApexOmniClient)


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for API client error handling."""

    def test_mock_client_handles_no_price(self, api_config):
        """Mock client should use default price if none provided."""
        client = MockApexOmniClient(api_config)
        result = client.place_order(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
            # No price provided
        )
        assert result.success is True
        assert result.price == Decimal("95000.0")  # Default mock price

    def test_order_result_with_client_order_id(self, api_config):
        """Should preserve client order ID."""
        client = MockApexOmniClient(api_config)
        result = client.place_order(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
            client_order_id="my-custom-id",
        )
        assert result.client_order_id == "my-custom-id"


# =============================================================================
# Network Configuration Tests
# =============================================================================

class TestNetworkConfiguration:
    """Tests for network (testnet/mainnet) configuration."""

    def test_api_config_testnet_endpoint(self):
        """Should return testnet endpoint."""
        config = APIConfig(
            api_key="test",
            api_secret="test",
            passphrase="test",
            testnet=True,
            network="testnet",
        )
        assert config.endpoint == "https://testnet.omni.apex.exchange"
        assert config.network_id == 5

    def test_api_config_mainnet_endpoint(self):
        """Should return mainnet endpoint."""
        config = APIConfig(
            api_key="test",
            api_secret="test",
            passphrase="test",
            testnet=False,
            network="mainnet",
        )
        assert config.endpoint == "https://omni.apex.exchange"
        assert config.network_id == 1

    def test_api_config_validation_missing_key(self):
        """Should report missing API key."""
        config = APIConfig(
            api_key="",
            api_secret="secret",
            passphrase="pass",
        )
        errors = config.validate()
        assert any("APEX_API_KEY" in e for e in errors)

    def test_api_config_validation_missing_secret(self):
        """Should report missing API secret."""
        config = APIConfig(
            api_key="key",
            api_secret="",
            passphrase="pass",
        )
        errors = config.validate()
        assert any("APEX_API_SECRET" in e for e in errors)

    def test_api_config_validation_missing_passphrase(self):
        """Should report missing passphrase."""
        config = APIConfig(
            api_key="key",
            api_secret="secret",
            passphrase="",
        )
        errors = config.validate()
        assert any("APEX_PASSPHRASE" in e for e in errors)

    def test_api_config_validation_valid(self):
        """Should return no errors for valid config."""
        config = APIConfig(
            api_key="test_key",
            api_secret="test_secret",
            passphrase="test_pass",
        )
        errors = config.validate()
        assert len(errors) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
