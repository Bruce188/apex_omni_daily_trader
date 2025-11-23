"""
Integration Tests for Dry-Run Mode.

These tests verify the complete trading workflow in simulation mode
without making any real API calls.

Tests cover:
- Full workflow simulation
- All 5 days scenario
- Verification that no real API calls are made
"""

import pytest
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from bot.api_client import MockApexOmniClient, create_client, AccountBalance
from bot.trade_executor import Trade, TradeResult, TradeExecutor
from bot.strategy import StakingOptimizationStrategy
from bot.config import Config
from data.collector import DataCollector
from data.storage import Storage


# =============================================================================
# Dry-Run Integration Tests
# =============================================================================

@pytest.mark.integration
@pytest.mark.dry_run
class TestDryRunFullWorkflow:
    """Integration tests for complete dry-run workflow."""

    @pytest.fixture
    def dry_run_setup(self, temp_data_dir):
        """Set up a complete dry-run environment."""
        # Create config
        config = Config()
        config.trading.symbol = "BTC-USDT"
        config.trading.side = "BUY"
        config.trading.size = Decimal("0.001")
        config.trading.order_type = "MARKET"
        config.trading.leverage = 1
        config.trading.close_position = True
        config.safety.dry_run = True
        config.safety.max_position_size = Decimal("1.0")
        config.safety.min_balance = Decimal("10.0")
        config.data_dir = temp_data_dir

        # Create mock client (dry-run mode)
        client = MockApexOmniClient(config.api)

        # Create executor and strategy
        executor = TradeExecutor(client=client, config=config)
        strategy = StakingOptimizationStrategy(config)

        # Create data collector
        storage = Storage(data_dir=temp_data_dir)
        collector = DataCollector(storage=storage)

        return {
            "config": config,
            "client": client,
            "executor": executor,
            "strategy": strategy,
            "collector": collector,
            "storage": storage,
        }

    def test_single_trade_dry_run(self, dry_run_setup):
        """Should execute a single trade in dry-run mode."""
        executor = dry_run_setup["executor"]

        trade = Trade(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
            day_number=1,
            # NOTE: close_position is now hardcoded to True (always closes)
        )

        result = executor.execute_trade(trade)

        # Should succeed
        assert result.success is True

        # Should have mock order ID
        assert result.order_id is not None
        assert "MOCK" in result.order_id

        # Should have executed price and size
        assert result.executed_price is not None
        assert result.executed_size is not None

        # Should have fees calculated
        assert result.fees > Decimal("0")

        # Should have close order (position is ALWAYS closed now - hardcoded)
        assert result.close_order_id is not None

    def test_five_day_trading_simulation(self, dry_run_setup):
        """Should simulate all 5 days of trading."""
        executor = dry_run_setup["executor"]
        strategy = dry_run_setup["strategy"]
        collector = dry_run_setup["collector"]

        # Generate weekly schedule
        trades = strategy.generate_weekly_schedule()
        assert len(trades) == 5

        results = []
        for i, trade_params in enumerate(trades, 1):
            # Create executor-compatible trade
            # NOTE: close_position is now hardcoded (always closes)
            trade = Trade(
                symbol=trade_params.symbol,
                side=trade_params.side,
                order_type=trade_params.order_type,
                size=trade_params.size,
                day_number=i,
            )

            # Execute trade
            result = executor.execute_trade(trade)
            results.append(result)

            # Record in collector (simulating data tracking)
            # Note: We'd need to adapt models for this

        # All 5 trades should succeed
        assert len(results) == 5
        assert all(r.success for r in results)

        # Each should have unique order ID
        order_ids = [r.order_id for r in results]
        assert len(set(order_ids)) == 5

    def test_no_real_api_calls_in_dry_run(self, dry_run_setup):
        """Verify no real API calls are made in dry-run mode."""
        client = dry_run_setup["client"]

        # Mock client should not have _client initialized
        assert client._client is None

        # Execute operations
        assert client.test_connection() is True
        balance = client.get_account_balance()
        price = client.get_current_price("BTC-USDT")
        config = client.get_symbol_config("BTC-USDT")

        # These should all work without real API
        assert balance is not None
        assert price is not None
        assert config is not None

        # _client should still be None (never initialized real SDK)
        assert client._client is None

    def test_mock_client_returns_consistent_data(self, dry_run_setup):
        """Mock client should return consistent, realistic data."""
        client = dry_run_setup["client"]

        # Balance should be reasonable
        balance = client.get_account_balance()
        assert balance.total_equity > 0
        assert balance.available_balance > 0
        assert balance.available_balance <= balance.total_equity

        # Price should be realistic
        price = client.get_current_price("BTC-USDT")
        assert price > Decimal("10000")  # BTC > $10k

        # Symbol config should be valid
        config = client.get_symbol_config("BTC-USDT")
        assert config.min_order_size > 0
        assert config.max_leverage >= 1

    def test_order_id_incrementing(self, dry_run_setup):
        """Order IDs should increment in dry-run mode."""
        client = dry_run_setup["client"]

        results = []
        for _ in range(5):
            result = client.place_order(
                symbol="BTC-USDT",
                side="BUY",
                order_type="MARKET",
                size=Decimal("0.001"),
            )
            results.append(result)

        # Order IDs should be sequential
        ids = [r.order_id for r in results]
        assert ids == ["MOCK-000001", "MOCK-000002", "MOCK-000003", "MOCK-000004", "MOCK-000005"]

    def test_fee_calculation_in_dry_run(self, dry_run_setup):
        """Fees should be calculated realistically in dry-run."""
        client = dry_run_setup["client"]

        result = client.place_order(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.01"),
            price=Decimal("95000.0"),
        )

        # Fee should be 0.05% of trade value
        expected_value = Decimal("0.01") * Decimal("95000.0")
        expected_fee = expected_value * Decimal("0.0005")

        assert result.fee == expected_fee


# =============================================================================
# Dry-Run Trade Execution Tests
# =============================================================================

@pytest.mark.integration
@pytest.mark.dry_run
class TestDryRunTradeExecution:
    """Tests for trade execution in dry-run mode."""

    def test_execute_buy_trade(self, config, temp_data_dir):
        """Should execute BUY trade in dry-run."""
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
        assert result.trade.side == "BUY"

    def test_execute_sell_trade(self, config, temp_data_dir):
        """Should execute SELL trade in dry-run."""
        config.data_dir = temp_data_dir
        config.trading.side = "SELL"
        client = MockApexOmniClient(config.api)
        executor = TradeExecutor(client=client, config=config)

        trade = Trade(
            symbol="BTC-USDT",
            side="SELL",
            order_type="MARKET",
            size=Decimal("0.001"),
        )

        result = executor.execute_trade(trade)

        assert result.success is True
        assert result.trade.side == "SELL"

    def test_execute_with_close_position(self, config, temp_data_dir):
        """Should execute trade and close position in dry-run.

        NOTE: Position closing is now MANDATORY (hardcoded for safety).
        """
        config.data_dir = temp_data_dir
        client = MockApexOmniClient(config.api)
        executor = TradeExecutor(client=client, config=config)

        trade = Trade(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
            # NOTE: close_position is now hardcoded to True (always closes)
        )

        result = executor.execute_trade(trade)

        assert result.success is True
        # Position is ALWAYS closed now (hardcoded behavior)
        assert result.close_order_id is not None
        assert result.close_price is not None
        assert result.close_fees > 0

    def test_execute_always_closes_position(self, config, temp_data_dir):
        """Verify position is ALWAYS closed (hardcoded safety behavior).

        NOTE: The old 'close_position=False' behavior has been removed.
        Positions are now ALWAYS closed immediately for safety.
        """
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
        # Position is ALWAYS closed - this is now mandatory
        assert result.close_order_id is not None


# =============================================================================
# Dry-Run Validation Tests
# =============================================================================

@pytest.mark.integration
@pytest.mark.dry_run
class TestDryRunValidation:
    """Tests for validation in dry-run mode."""

    def test_validation_still_applies(self, config, temp_data_dir):
        """Validation should still work in dry-run mode (invalid side)."""
        config.data_dir = temp_data_dir
        client = MockApexOmniClient(config.api)
        executor = TradeExecutor(client=client, config=config)

        # NOTE: With auto-selection, size is replaced by symbol's min order size.
        # So we test validation with invalid side instead
        trade = Trade(
            symbol="BTC-USDT",
            side="INVALID_SIDE",  # Invalid side
            order_type="MARKET",
            size=Decimal("0.001"),
        )

        result = executor.execute_trade(trade)

        # Should fail validation even in dry-run
        assert result.success is False
        assert result.error is not None
        assert "side" in result.error.lower()

    def test_no_tradeable_symbol_fails_in_dry_run(self, config, temp_data_dir):
        """Should fail in dry-run when no tradeable symbol is available."""
        config.data_dir = temp_data_dir
        config.safety.min_balance = Decimal("0.0001")  # Low threshold
        client = MockApexOmniClient(config.api)
        # Set very low balance so no symbol is tradeable
        client._mock_balance = AccountBalance(
            total_equity=Decimal("0.0001"),
            available_balance=Decimal("0.0001"),
            margin_balance=Decimal("0.0001"),
            unrealized_pnl=Decimal("0")
        )
        executor = TradeExecutor(client=client, config=config)

        trade = Trade(
            symbol="BTC-USDT",
            side="BUY",
            order_type="MARKET",
            size=Decimal("0.001"),
        )

        result = executor.execute_trade(trade)

        # Should fail because no symbol is affordable
        assert result.success is False
        assert "no tradeable symbol" in result.error.lower()


# =============================================================================
# Factory Function Tests
# =============================================================================

@pytest.mark.integration
@pytest.mark.dry_run
class TestCreateClientFactory:
    """Tests for create_client factory function."""

    def test_create_client_dry_run_true(self, api_config):
        """Should create MockApexOmniClient when dry_run=True."""
        client = create_client(api_config, dry_run=True)

        assert isinstance(client, MockApexOmniClient)
        assert client.test_connection() is True

    def test_create_client_dry_run_false(self, api_config):
        """Should create real ApexOmniClient when dry_run=False."""
        from bot.api_client import ApexOmniClient

        client = create_client(api_config, dry_run=False)

        assert isinstance(client, ApexOmniClient)
        assert not isinstance(client, MockApexOmniClient)


# =============================================================================
# Strategy Integration in Dry-Run
# =============================================================================

@pytest.mark.integration
@pytest.mark.dry_run
class TestStrategyDryRunIntegration:
    """Tests for strategy integration with dry-run mode."""

    def test_strategy_generates_valid_trades(self, config):
        """Strategy should generate valid trades for dry-run execution."""
        strategy = StakingOptimizationStrategy(config)
        trades = strategy.generate_weekly_schedule()

        assert len(trades) == 5

        for i, trade in enumerate(trades, 1):
            assert trade.symbol == config.trading.symbol
            assert trade.side == config.trading.side
            assert trade.order_type == config.trading.order_type
            assert trade.size == config.trading.size
            assert trade.day_number == i

    def test_strategy_status_with_dry_run(self, config):
        """Strategy status should work in dry-run mode."""
        strategy = StakingOptimizationStrategy(config)

        status = strategy.get_status(days_already_traded=2)

        assert status.days_traded == 2
        assert status.trading_activity_factor == 0.2
        assert status.days_remaining >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
