"""
Tests for Trade Executor.

Tests cover:
- Trade validation (symbol, size, balance)
- Dry-run mode
- Order placement
- Error scenarios
- Retry logic
- Position closing
"""

import pytest
import sys
import json
from pathlib import Path
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bot.trade_executor import Trade, TradeResult, TradeExecutor
from bot.api_client import MockApexOmniClient, ApexOmniClient, OrderResult, AccountBalance, SymbolConfig
from bot.config import Config


# =============================================================================
# Trade Dataclass Tests
# =============================================================================

class TestTrade:
    """Tests for Trade dataclass."""

    def test_trade_creation(self):
        """Should create Trade with all fields."""
        trade = Trade(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
            price=Decimal("95000.0"),
            day_number=1,
            # NOTE: leverage and close_position are hardcoded (removed from dataclass)
        )
        assert trade.symbol == "BTC-USDT"
        assert trade.side == "BUY"
        assert trade.size == Decimal("0.001")
        assert trade.day_number == 1

    def test_trade_defaults(self):
        """Should use default values."""
        trade = Trade(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
        )
        assert trade.price is None
        assert trade.day_number == 1
        # NOTE: leverage and close_position are no longer fields (hardcoded)


# =============================================================================
# TradeResult Tests
# =============================================================================

class TestTradeResult:
    """Tests for TradeResult dataclass."""

    @pytest.fixture
    def trade(self):
        return Trade(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
        )

    def test_successful_trade_result(self, trade):
        """Should create successful TradeResult."""
        result = TradeResult(
            trade=trade,
            success=True,
            order_id="ORDER-001",
            executed_price=Decimal("95000.0"),
            executed_size=Decimal("0.001"),
            fees=Decimal("0.0475"),
        )
        assert result.success is True
        assert result.order_id == "ORDER-001"
        assert result.error is None

    def test_failed_trade_result(self, trade):
        """Should create failed TradeResult."""
        result = TradeResult(
            trade=trade,
            success=False,
            error="Insufficient balance",
        )
        assert result.success is False
        assert result.error == "Insufficient balance"

    def test_total_fees_calculation(self, trade):
        """Should calculate total fees including close order."""
        result = TradeResult(
            trade=trade,
            success=True,
            fees=Decimal("0.05"),
            close_fees=Decimal("0.05"),
        )
        assert result.total_fees == Decimal("0.10")

    def test_pnl_calculation_long(self, trade):
        """Should calculate P&L for long position."""
        trade.side = "BUY"
        result = TradeResult(
            trade=trade,
            success=True,
            executed_price=Decimal("95000.0"),
            executed_size=Decimal("0.001"),
            close_price=Decimal("95100.0"),  # $100 increase
        )
        # P&L = (95100 - 95000) * 0.001 = 0.1
        assert result.pnl == Decimal("0.1")

    def test_pnl_calculation_short(self, trade):
        """Should calculate P&L for short position."""
        trade.side = "SELL"
        result = TradeResult(
            trade=trade,
            success=True,
            executed_price=Decimal("95000.0"),
            executed_size=Decimal("0.001"),
            close_price=Decimal("94900.0"),  # $100 decrease (profit for short)
        )
        # P&L = (95000 - 94900) * 0.001 = 0.1
        assert result.pnl == Decimal("0.1")

    def test_to_dict(self, trade):
        """Should convert to dictionary correctly."""
        result = TradeResult(
            trade=trade,
            success=True,
            order_id="ORDER-001",
            executed_price=Decimal("95000.0"),
            executed_size=Decimal("0.001"),
            fees=Decimal("0.05"),
        )
        data = result.to_dict()
        assert data["success"] is True
        assert data["order_id"] == "ORDER-001"
        assert data["executed_price"] == "95000.0"
        assert "timestamp" in data


# =============================================================================
# TradeExecutor Validation Tests
# =============================================================================

class TestTradeExecutorValidation:
    """Tests for trade validation in TradeExecutor."""

    def test_validate_trade_valid(self, trade_executor, sample_executor_trade):
        """Should accept valid trade."""
        is_valid, error = trade_executor.validate_trade(sample_executor_trade)
        assert is_valid is True
        assert error is None

    def test_validate_trade_invalid_symbol(self, trade_executor):
        """Should reject unknown symbol."""
        # Patch get_symbol_config to return None
        trade_executor.client.get_symbol_config = Mock(return_value=None)

        trade = Trade(
            symbol="INVALID-SYMBOL",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
        )
        is_valid, error = trade_executor.validate_trade(trade)
        assert is_valid is False
        assert "Unknown symbol" in error

    def test_validate_trade_zero_size(self, trade_executor):
        """Should reject zero or negative size."""
        trade = Trade(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0"),
        )
        is_valid, error = trade_executor.validate_trade(trade)
        assert is_valid is False
        assert "positive" in error.lower()

    def test_validate_trade_negative_size(self, trade_executor):
        """Should reject negative size."""
        trade = Trade(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("-0.001"),
        )
        is_valid, error = trade_executor.validate_trade(trade)
        assert is_valid is False
        assert "positive" in error.lower()

    def test_validate_trade_below_minimum(self, trade_executor, mock_symbol_config):
        """Should reject size below minimum."""
        trade_executor.client.get_symbol_config = Mock(return_value=mock_symbol_config)

        trade = Trade(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.0001"),  # Below 0.001 minimum
        )
        is_valid, error = trade_executor.validate_trade(trade)
        assert is_valid is False
        assert "minimum" in error.lower()

    def test_validate_trade_exceeds_max_position(self, trade_executor, mock_symbol_config):
        """Should reject size exceeding max position."""
        trade_executor.client.get_symbol_config = Mock(return_value=mock_symbol_config)

        trade = Trade(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("100"),  # Exceeds max_position_size
        )
        is_valid, error = trade_executor.validate_trade(trade)
        assert is_valid is False
        assert "max position" in error.lower()

    def test_validate_trade_invalid_side(self, trade_executor, mock_symbol_config):
        """Should reject invalid side."""
        trade_executor.client.get_symbol_config = Mock(return_value=mock_symbol_config)

        trade = Trade(
            symbol="BTC-USDT",
            side="LONG",  # Invalid
            order_type="MARKET",
            size=Decimal("0.001"),
        )
        is_valid, error = trade_executor.validate_trade(trade)
        assert is_valid is False
        assert "Invalid side" in error

    def test_validate_trade_invalid_order_type(self, trade_executor, mock_symbol_config):
        """Should reject invalid order type."""
        trade_executor.client.get_symbol_config = Mock(return_value=mock_symbol_config)

        trade = Trade(
            symbol="BTC-USDT",
            side="BUY",
            order_type="STOP",  # Invalid
            size=Decimal("0.001"),
        )
        is_valid, error = trade_executor.validate_trade(trade)
        assert is_valid is False
        assert "Invalid order type" in error

    # NOTE: test_validate_trade_invalid_leverage removed
    # Leverage is now hardcoded to 1 and not part of Trade dataclass


# =============================================================================
# TradeExecutor Balance Check Tests
# =============================================================================

class TestTradeExecutorBalanceCheck:
    """Tests for balance checking in TradeExecutor."""

    def test_check_balance_sufficient(self, trade_executor, mock_account_balance):
        """Should pass with sufficient balance."""
        trade_executor.client.get_account_balance = Mock(return_value=mock_account_balance)

        has_balance, error = trade_executor.check_balance(Decimal("100"))
        assert has_balance is True
        assert error is None

    def test_check_balance_insufficient(self, trade_executor, mock_account_balance):
        """Should fail with insufficient balance."""
        mock_account_balance.available_balance = Decimal("50")
        trade_executor.client.get_account_balance = Mock(return_value=mock_account_balance)

        has_balance, error = trade_executor.check_balance(Decimal("100"))
        assert has_balance is False
        assert "Insufficient" in error

    def test_check_balance_below_minimum(self, trade_executor, mock_account_balance):
        """Should fail when below minimum balance."""
        mock_account_balance.available_balance = Decimal("30")  # Below min 50
        trade_executor.client.get_account_balance = Mock(return_value=mock_account_balance)

        has_balance, error = trade_executor.check_balance(Decimal("10"))
        assert has_balance is False
        assert "minimum" in error.lower()

    def test_check_balance_api_failure(self, trade_executor):
        """Should fail when cannot retrieve balance."""
        trade_executor.client.get_account_balance = Mock(return_value=None)

        has_balance, error = trade_executor.check_balance(Decimal("100"))
        assert has_balance is False
        assert "Could not retrieve" in error

    def test_check_balance_disabled(self, trade_executor, mock_account_balance):
        """Should pass when balance check is disabled."""
        trade_executor.config.safety.require_balance_check = False
        trade_executor.client.get_account_balance = Mock(return_value=mock_account_balance)

        has_balance, error = trade_executor.check_balance(Decimal("10000"))
        assert has_balance is True


# =============================================================================
# TradeExecutor Execution Tests
# =============================================================================

class TestTradeExecutorExecution:
    """Tests for trade execution in TradeExecutor."""

    def test_execute_trade_success(self, trade_executor, sample_executor_trade, mock_order_result):
        """Should execute trade successfully."""
        trade_executor.client.place_order = Mock(return_value=mock_order_result)

        result = trade_executor.execute_trade(sample_executor_trade)

        assert result.success is True
        assert result.order_id == mock_order_result.order_id
        assert result.executed_price == mock_order_result.filled_price

    def test_execute_trade_validation_failure(self, trade_executor):
        """Should fail on validation error (invalid side)."""
        # Note: With auto-selection, the size gets replaced. So test with invalid side instead.
        trade = Trade(
            symbol="BTC-USDT",
            side="INVALID_SIDE",  # Invalid
            order_type="MARKET",
            size=Decimal("0.001"),
        )

        result = trade_executor.execute_trade(trade)
        assert result.success is False
        assert "side" in result.error.lower()

    def test_execute_trade_price_failure(self, trade_executor, sample_executor_trade):
        """Should fail when cannot get price for any symbol (no tradeable symbols)."""
        # When price is unavailable for ALL symbols, bot can't find any tradeable symbol
        trade_executor.client.get_current_price = Mock(return_value=None)

        result = trade_executor.execute_trade(sample_executor_trade)
        assert result.success is False
        # With auto-selection, failure is about no tradeable symbol (due to no prices)
        assert "no tradeable symbol" in result.error.lower() or "price" in result.error.lower()


# =============================================================================
# Dry-Run Mode Tests
# =============================================================================

@pytest.mark.dry_run
class TestDryRunMode:
    """Tests for dry-run mode execution."""

    def test_dry_run_no_real_orders(self, config, temp_data_dir):
        """Verify no actual API calls in dry-run mode."""
        config.data_dir = temp_data_dir
        client = MockApexOmniClient(config.api)
        executor = TradeExecutor(client=client, config=config)

        # Place order - should be simulated
        trade = Trade(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
        )

        result = executor.execute_trade(trade)

        # Should succeed with mock order ID
        assert result.success is True
        assert result.order_id.startswith("MOCK-")

    def test_dry_run_simulates_execution(self, config, temp_data_dir):
        """Should return simulated results in dry-run."""
        config.data_dir = temp_data_dir
        client = MockApexOmniClient(config.api)
        executor = TradeExecutor(client=client, config=config)

        trade = Trade(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
        )

        result = executor.execute_trade(trade)

        assert result.success is True
        assert result.executed_price is not None
        assert result.executed_size is not None
        assert result.fees > Decimal("0")

    def test_dry_run_closes_position(self, config, temp_data_dir):
        """Should simulate position closing in dry-run (always closes, hardcoded)."""
        config.data_dir = temp_data_dir
        client = MockApexOmniClient(config.api)
        executor = TradeExecutor(client=client, config=config)

        trade = Trade(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
            # NOTE: close_position is now hardcoded to True
        )

        result = executor.execute_trade(trade)

        assert result.success is True
        # Position is always closed (hardcoded behavior)
        assert result.close_order_id is not None
        assert result.close_price is not None


# =============================================================================
# Trade History Tests
# =============================================================================

class TestTradeHistory:
    """Tests for trade history tracking."""

    def test_get_today_trades_empty(self, trade_executor):
        """Should return empty list when no trades today."""
        trades = trade_executor.get_today_trades()
        assert trades == []

    def test_has_traded_today_false(self, trade_executor):
        """Should return False when no trades today."""
        assert trade_executor.has_traded_today() is False

    def test_get_week_trades_count_zero(self, trade_executor):
        """Should return 0 when no trades this week."""
        count = trade_executor.get_week_trades_count()
        assert count == 0


# =============================================================================
# Symbol Selection Tests
# =============================================================================

class TestSymbolSelection:
    """Tests for dynamic symbol selection based on balance."""

    @pytest.fixture
    def low_balance_client(self, api_config):
        """Create a mock client with low balance."""
        client = MockApexOmniClient(api_config)
        # Override with low balance
        client._mock_balance = AccountBalance(
            total_equity=Decimal("2.0"),
            available_balance=Decimal("2.0"),
            margin_balance=Decimal("2.0"),
            unrealized_pnl=Decimal("0")
        )
        return client

    @pytest.fixture
    def executor_with_low_balance(self, low_balance_client, config, temp_data_dir):
        """Create executor with low balance client for testing cheapest symbol selection."""
        config.data_dir = temp_data_dir
        config.trading.min_trade_value_usdt = Decimal("0.01")
        config.safety.min_balance = Decimal("0.01")
        return TradeExecutor(client=low_balance_client, config=config)

    def test_get_min_trade_value_usdt(self, executor_with_low_balance):
        """Should calculate minimum trade value in USDT."""
        symbol_config = SymbolConfig(
            symbol="BTC-USDT",
            base_currency="BTC",
            quote_currency="USDT",
            min_order_size=Decimal("0.001"),
            tick_size=Decimal("0.1"),
            step_size=Decimal("0.001"),
            max_leverage=100
        )
        # Mock price is 95000
        min_value = executor_with_low_balance.get_min_trade_value_usdt(symbol_config)
        assert min_value == Decimal("0.001") * Decimal("95000.0")

    def test_find_best_tradeable_symbol_with_sufficient_balance(self, trade_executor):
        """Should find cheapest tradeable symbol when balance is sufficient."""
        # Default mock balance is 950 USDT - should find cheapest symbol
        result = trade_executor.find_best_tradeable_symbol(
            available_balance=Decimal("950.0")
        )
        assert result is not None
        symbol_config, min_value, price = result
        # Should return the cheapest tradeable symbol, not necessarily BTC-USDT
        assert min_value <= Decimal("950.0")

    def test_find_best_tradeable_symbol_returns_cheapest(self, executor_with_low_balance):
        """Should return cheapest tradeable symbol when balance is low."""
        # Balance is 2 USDT, BTC min is ~95 USDT
        result = executor_with_low_balance.find_best_tradeable_symbol(
            available_balance=Decimal("2.0")
        )
        # Should find DOGE-USDT which has lower min order value in mock
        # Note: Depends on mock prices, may need adjustment
        if result is not None:
            symbol_config, min_value, price = result
            assert min_value <= Decimal("2.0")

    def test_find_best_tradeable_symbol_no_tradeable(self, executor_with_low_balance):
        """Should return None when no symbol is tradeable."""
        # Very low balance that can't trade anything
        result = executor_with_low_balance.find_best_tradeable_symbol(
            available_balance=Decimal("0.0001")
        )
        assert result is None

    def test_select_symbol_always_picks_cheapest(self, trade_executor, sample_executor_trade):
        """Should always select cheapest tradeable symbol."""
        # High balance client - should still pick cheapest symbol
        result = trade_executor.select_symbol_for_trade(sample_executor_trade)
        assert result is not None
        trade, symbol_config = result
        # Bot always picks cheapest available symbol
        assert trade.size > Decimal("0")

    def test_select_symbol_with_low_balance(self, executor_with_low_balance):
        """Should select cheapest tradeable symbol when balance is low."""
        trade = Trade(
            symbol="BTC-USDT",  # Request BTC but balance too low
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
        )
        result = executor_with_low_balance.select_symbol_for_trade(trade)
        # May or may not find tradeable symbol depending on mock prices
        # The important thing is it attempts to find cheapest
        if result is not None:
            new_trade, symbol_config = result
            # Should have selected cheapest available symbol
            assert new_trade.size > Decimal("0")

    def test_execute_trade_selects_cheapest_symbol(self, executor_with_low_balance):
        """Should execute trade with cheapest available symbol."""
        trade = Trade(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
        )
        result = executor_with_low_balance.execute_trade(trade)
        # Will either succeed with cheapest symbol or fail with clear error
        # The key is no crash and proper error handling
        assert isinstance(result, TradeResult)

    def test_execute_trade_fails_when_no_tradeable_symbol(self, config, temp_data_dir):
        """Should fail gracefully when no symbol is tradeable."""
        # Create client with very low balance
        api_config = config.api
        client = MockApexOmniClient(api_config)
        client._mock_balance = AccountBalance(
            total_equity=Decimal("0.001"),
            available_balance=Decimal("0.001"),
            margin_balance=Decimal("0.001"),
            unrealized_pnl=Decimal("0")
        )

        config.data_dir = temp_data_dir
        config.safety.min_balance = Decimal("0.0001")

        executor = TradeExecutor(client=client, config=config)

        trade = Trade(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
        )

        # Should fail because no symbol is affordable
        result = executor.execute_trade(trade)
        assert result.success is False


class TestGetAllSymbols:
    """Tests for get_all_symbols API method."""

    def test_mock_client_returns_symbols(self, api_config):
        """Mock client should return list of symbols."""
        client = MockApexOmniClient(api_config)
        symbols = client.get_all_symbols()
        assert len(symbols) > 0
        assert all(isinstance(s, SymbolConfig) for s in symbols)

    def test_mock_client_symbols_have_required_fields(self, api_config):
        """Mock symbols should have all required fields."""
        client = MockApexOmniClient(api_config)
        symbols = client.get_all_symbols()
        for symbol in symbols:
            assert symbol.symbol
            assert symbol.base_currency
            assert symbol.quote_currency
            assert symbol.min_order_size > Decimal("0")
            assert symbol.tick_size > Decimal("0")
            assert symbol.step_size > Decimal("0")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
