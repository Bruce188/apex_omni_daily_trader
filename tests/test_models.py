"""
Tests for Data Models.

Tests cover:
- Trade creation and validation
- TradeResult
- WeeklyTradeRecord
- StakingInfo calculations
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.models import (
    Trade,
    TradeResult,
    WeeklyTradeRecord,
    StakingInfo,
    OrderSide,
    OrderType,
    TradeStatus,
)


# =============================================================================
# Trade Model Tests
# =============================================================================

class TestTrade:
    """Tests for Trade data model."""

    def test_trade_creation_valid(self):
        """Should create Trade with valid parameters."""
        trade = Trade(
            symbol="BTC-USDT",
            side="buy",
            size=0.001,
            price=95000.0,
            order_type="market",
            leverage=1,
            day_number=1,
        )
        assert trade.symbol == "BTC-USDT"
        assert trade.side == "buy"
        assert trade.size == 0.001
        assert trade.price == 95000.0

    def test_trade_normalizes_side(self):
        """Should normalize side to lowercase."""
        trade = Trade(
            symbol="BTC-USDT",
            side="BUY",
            size=0.001,
            price=95000.0,
        )
        assert trade.side == "buy"

    def test_trade_normalizes_order_type(self):
        """Should normalize order_type to lowercase."""
        trade = Trade(
            symbol="BTC-USDT",
            side="buy",
            size=0.001,
            price=95000.0,
            order_type="MARKET",
        )
        assert trade.order_type == "market"

    def test_trade_invalid_side(self):
        """Should reject invalid side."""
        with pytest.raises(ValueError) as excinfo:
            Trade(
                symbol="BTC-USDT",
                side="LONG",
                size=0.001,
                price=95000.0,
            )
        assert "Invalid side" in str(excinfo.value)

    def test_trade_invalid_order_type(self):
        """Should reject invalid order type."""
        with pytest.raises(ValueError) as excinfo:
            Trade(
                symbol="BTC-USDT",
                side="buy",
                size=0.001,
                price=95000.0,
                order_type="STOP",
            )
        assert "Invalid order_type" in str(excinfo.value)

    def test_trade_invalid_size_zero(self):
        """Should reject zero size."""
        with pytest.raises(ValueError) as excinfo:
            Trade(
                symbol="BTC-USDT",
                side="buy",
                size=0,
                price=95000.0,
            )
        assert "Size must be positive" in str(excinfo.value)

    def test_trade_invalid_size_negative(self):
        """Should reject negative size."""
        with pytest.raises(ValueError) as excinfo:
            Trade(
                symbol="BTC-USDT",
                side="buy",
                size=-0.001,
                price=95000.0,
            )
        assert "Size must be positive" in str(excinfo.value)

    def test_trade_invalid_price_zero(self):
        """Should reject zero price."""
        with pytest.raises(ValueError) as excinfo:
            Trade(
                symbol="BTC-USDT",
                side="buy",
                size=0.001,
                price=0,
            )
        assert "Price must be positive" in str(excinfo.value)

    def test_trade_invalid_price_negative(self):
        """Should reject negative price."""
        with pytest.raises(ValueError) as excinfo:
            Trade(
                symbol="BTC-USDT",
                side="buy",
                size=0.001,
                price=-100,
            )
        assert "Price must be positive" in str(excinfo.value)

    def test_trade_invalid_leverage_low(self):
        """Should reject leverage below 1."""
        with pytest.raises(ValueError) as excinfo:
            Trade(
                symbol="BTC-USDT",
                side="buy",
                size=0.001,
                price=95000.0,
                leverage=0,
            )
        assert "Leverage must be between 1 and 100" in str(excinfo.value)

    def test_trade_invalid_leverage_high(self):
        """Should reject leverage above 100."""
        with pytest.raises(ValueError) as excinfo:
            Trade(
                symbol="BTC-USDT",
                side="buy",
                size=0.001,
                price=95000.0,
                leverage=101,
            )
        assert "Leverage must be between 1 and 100" in str(excinfo.value)

    def test_trade_invalid_day_number_low(self):
        """Should reject day_number below 1."""
        with pytest.raises(ValueError) as excinfo:
            Trade(
                symbol="BTC-USDT",
                side="buy",
                size=0.001,
                price=95000.0,
                day_number=0,
            )
        assert "Day number must be between 1 and 5" in str(excinfo.value)

    def test_trade_invalid_day_number_high(self):
        """Should reject day_number above 5."""
        with pytest.raises(ValueError) as excinfo:
            Trade(
                symbol="BTC-USDT",
                side="buy",
                size=0.001,
                price=95000.0,
                day_number=6,
            )
        assert "Day number must be between 1 and 5" in str(excinfo.value)

    def test_trade_to_dict(self):
        """Should convert to dictionary."""
        trade = Trade(
            symbol="BTC-USDT",
            side="buy",
            size=0.001,
            price=95000.0,
            order_type="market",
            leverage=2,
            day_number=3,
        )
        data = trade.to_dict()

        assert data["symbol"] == "BTC-USDT"
        assert data["side"] == "buy"
        assert data["size"] == 0.001
        assert data["price"] == 95000.0
        assert data["order_type"] == "market"
        assert data["leverage"] == 2
        assert data["day_number"] == 3

    def test_trade_from_dict(self):
        """Should create Trade from dictionary."""
        data = {
            "symbol": "ETH-USDT",
            "side": "sell",
            "size": 0.1,
            "price": 3000.0,
            "order_type": "limit",
            "leverage": 5,
            "day_number": 2,
        }
        trade = Trade.from_dict(data)

        assert trade.symbol == "ETH-USDT"
        assert trade.side == "sell"
        assert trade.size == 0.1
        assert trade.leverage == 5


# =============================================================================
# TradeResult Model Tests
# =============================================================================

class TestTradeResult:
    """Tests for TradeResult data model."""

    @pytest.fixture
    def sample_trade(self):
        return Trade(
            symbol="BTC-USDT",
            side="buy",
            size=0.001,
            price=95000.0,
        )

    def test_trade_result_success(self, sample_trade):
        """Should create successful TradeResult."""
        result = TradeResult(
            trade=sample_trade,
            success=True,
            order_id="ORDER-001",
            executed_price=95000.0,
            executed_size=0.001,
            fees=0.0475,
        )
        assert result.success is True
        assert result.status == TradeStatus.FILLED
        assert result.is_filled is True

    def test_trade_result_failure(self, sample_trade):
        """Should create failed TradeResult."""
        result = TradeResult(
            trade=sample_trade,
            success=False,
            error="Insufficient balance",
        )
        assert result.success is False
        assert result.status == TradeStatus.FAILED
        assert result.is_filled is False

    def test_trade_result_executed_value(self, sample_trade):
        """Should calculate executed value."""
        result = TradeResult(
            trade=sample_trade,
            success=True,
            executed_price=95000.0,
            executed_size=0.001,
        )
        assert result.executed_value == 95.0  # 95000 * 0.001

    def test_trade_result_executed_value_none(self, sample_trade):
        """Should return 0 when executed price/size not set."""
        result = TradeResult(
            trade=sample_trade,
            success=False,
        )
        assert result.executed_value == 0.0

    def test_trade_result_slippage(self, sample_trade):
        """Should calculate slippage percentage."""
        result = TradeResult(
            trade=sample_trade,
            success=True,
            executed_price=95100.0,  # 0.1% higher than expected
            executed_size=0.001,
        )
        # (95100 - 95000) / 95000 * 100 = 0.1052...
        assert abs(result.slippage - 0.1052631579) < 0.0001

    def test_trade_result_slippage_none(self, sample_trade):
        """Should return None when prices not set."""
        result = TradeResult(
            trade=sample_trade,
            success=False,
        )
        assert result.slippage is None

    def test_trade_result_to_dict(self, sample_trade):
        """Should convert to dictionary."""
        result = TradeResult(
            trade=sample_trade,
            success=True,
            order_id="ORDER-001",
            executed_price=95000.0,
            executed_size=0.001,
            fees=0.05,
        )
        data = result.to_dict()

        assert data["success"] is True
        assert data["order_id"] == "ORDER-001"
        assert data["trade"]["symbol"] == "BTC-USDT"
        assert "timestamp" in data

    def test_trade_result_from_dict(self, sample_trade):
        """Should create from dictionary."""
        data = {
            "trade": sample_trade.to_dict(),
            "success": True,
            "order_id": "ORDER-002",
            "executed_price": 94900.0,
            "executed_size": 0.001,
            "fees": 0.04,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "filled",
        }
        result = TradeResult.from_dict(data)

        assert result.success is True
        assert result.order_id == "ORDER-002"
        assert result.status == TradeStatus.FILLED


# =============================================================================
# WeeklyTradeRecord Tests
# =============================================================================

class TestWeeklyTradeRecord:
    """Tests for WeeklyTradeRecord data model."""

    @pytest.fixture
    def week_bounds(self):
        now = datetime.utcnow()
        monday = now - timedelta(days=now.weekday())
        monday = monday.replace(hour=8, minute=0, second=0, microsecond=0)
        return monday, monday + timedelta(days=7)

    @pytest.fixture
    def empty_record(self, week_bounds):
        week_start, week_end = week_bounds
        return WeeklyTradeRecord(
            week_start=week_start,
            week_end=week_end,
        )

    def test_weekly_record_creation(self, week_bounds):
        """Should create WeeklyTradeRecord."""
        week_start, week_end = week_bounds
        record = WeeklyTradeRecord(
            week_start=week_start,
            week_end=week_end,
        )
        assert record.week_start == week_start
        assert record.week_end == week_end
        assert record.trades == []
        assert record.days_traded == set()

    def test_num_days_traded_empty(self, empty_record):
        """Should return 0 for empty record."""
        assert empty_record.num_days_traded == 0

    def test_trading_activity_factor_0_days(self, empty_record):
        """TAF should be 0 with 0 days traded."""
        assert empty_record.trading_activity_factor == 0.0

    def test_trading_activity_factor_calculation(self, empty_record):
        """TAF should be 0.1 per day, max 0.5."""
        empty_record.days_traded = {0}  # Monday
        assert empty_record.trading_activity_factor == 0.1

        empty_record.days_traded = {0, 1, 2}  # Mon, Tue, Wed
        assert abs(empty_record.trading_activity_factor - 0.3) < 0.0001

        empty_record.days_traded = {0, 1, 2, 3, 4}  # Mon-Fri
        assert empty_record.trading_activity_factor == 0.5

        # More than 5 should still cap at 0.5
        empty_record.days_traded = {0, 1, 2, 3, 4, 5, 6}
        assert empty_record.trading_activity_factor == 0.5

    def test_add_trade_success(self, empty_record, sample_trade_result):
        """Should add successful trade and track day."""
        # Set timestamp to Monday
        sample_trade_result.timestamp = sample_trade_result.timestamp.replace(
            year=2024, month=1, day=15  # A Monday
        )
        empty_record.add_trade(sample_trade_result)

        assert len(empty_record.trades) == 1
        assert 0 in empty_record.days_traded  # Monday = 0

    def test_add_trade_failure_no_day_track(self, empty_record, failed_trade_result):
        """Should add failed trade but not track day."""
        empty_record.add_trade(failed_trade_result)

        assert len(empty_record.trades) == 1
        assert len(empty_record.days_traded) == 0

    def test_success_count(self, empty_record, sample_trade_result, failed_trade_result):
        """Should count successful trades."""
        empty_record.trades = [sample_trade_result, sample_trade_result, failed_trade_result]
        assert empty_record.success_count == 2

    def test_failure_count(self, empty_record, sample_trade_result, failed_trade_result):
        """Should count failed trades."""
        empty_record.trades = [sample_trade_result, failed_trade_result, failed_trade_result]
        assert empty_record.failure_count == 2

    def test_total_volume(self, empty_record, sample_trade_result):
        """Should calculate total volume."""
        sample_trade_result.executed_price = 95000.0
        sample_trade_result.executed_size = 0.001
        empty_record.trades = [sample_trade_result, sample_trade_result]
        assert empty_record.total_volume == 190.0  # 95 * 2

    def test_total_fees(self, empty_record, sample_trade_result):
        """Should calculate total fees."""
        sample_trade_result.fees = 0.05
        empty_record.trades = [sample_trade_result, sample_trade_result]
        assert empty_record.total_fees == 0.10

    def test_to_dict(self, empty_record):
        """Should convert to dictionary."""
        empty_record.days_traded = {0, 1}
        data = empty_record.to_dict()

        assert "week_start" in data
        assert "week_end" in data
        assert data["num_days_traded"] == 2
        assert data["trading_activity_factor"] == 0.2

    def test_from_dict(self, week_bounds):
        """Should create from dictionary."""
        week_start, week_end = week_bounds
        data = {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "trades": [],
            "days_traded": [0, 1, 2],
        }
        record = WeeklyTradeRecord.from_dict(data)

        assert record.week_start == week_start
        assert record.days_traded == {0, 1, 2}


# =============================================================================
# StakingInfo Tests
# =============================================================================

class TestStakingInfo:
    """Tests for StakingInfo data model."""

    def test_staking_info_creation(self):
        """Should create StakingInfo."""
        info = StakingInfo(
            staked_amount=1000.0,
            lock_months=6,
        )
        assert info.staked_amount == 1000.0
        assert info.lock_months == 6

    def test_staking_info_negative_amount(self):
        """Should reject negative staked amount."""
        with pytest.raises(ValueError) as excinfo:
            StakingInfo(staked_amount=-100.0)
        assert "negative" in str(excinfo.value)

    def test_staking_info_negative_months(self):
        """Should reject negative lock months."""
        with pytest.raises(ValueError) as excinfo:
            StakingInfo(staked_amount=1000.0, lock_months=-1)
        assert "negative" in str(excinfo.value)

    def test_time_factor_0_months(self):
        """Time factor should be 0 for no lock."""
        info = StakingInfo(staked_amount=1000.0, lock_months=0)
        assert info.time_factor == 0.0

    def test_time_factor_6_months(self):
        """Time factor should be 0.5 for 6-month lock."""
        info = StakingInfo(staked_amount=1000.0, lock_months=6)
        assert info.time_factor == 0.5

    def test_time_factor_12_months(self):
        """Time factor should be 1.0 for 12-month lock."""
        info = StakingInfo(staked_amount=1000.0, lock_months=12)
        assert info.time_factor == 1.0

    def test_time_factor_24_months(self):
        """Time factor should be 2.0 for 24-month lock."""
        info = StakingInfo(staked_amount=1000.0, lock_months=24)
        assert info.time_factor == 2.0

    def test_to_dict(self):
        """Should convert to dictionary."""
        info = StakingInfo(staked_amount=1000.0, lock_months=6)
        data = info.to_dict()

        assert data["staked_amount"] == 1000.0
        assert data["lock_months"] == 6
        assert "start_date" in data

    def test_from_dict(self):
        """Should create from dictionary."""
        data = {
            "staked_amount": 5000.0,
            "lock_months": 12,
            "start_date": datetime.utcnow().isoformat(),
        }
        info = StakingInfo.from_dict(data)

        assert info.staked_amount == 5000.0
        assert info.lock_months == 12


# =============================================================================
# Enum Tests
# =============================================================================

class TestEnums:
    """Tests for enum classes."""

    def test_order_side_values(self):
        """Should have correct OrderSide values."""
        assert OrderSide.BUY.value == "buy"
        assert OrderSide.SELL.value == "sell"

    def test_order_type_values(self):
        """Should have correct OrderType values."""
        assert OrderType.MARKET.value == "market"
        assert OrderType.LIMIT.value == "limit"

    def test_trade_status_values(self):
        """Should have correct TradeStatus values."""
        assert TradeStatus.PENDING.value == "pending"
        assert TradeStatus.FILLED.value == "filled"
        assert TradeStatus.PARTIAL.value == "partial"
        assert TradeStatus.FAILED.value == "failed"
        assert TradeStatus.CANCELLED.value == "cancelled"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
