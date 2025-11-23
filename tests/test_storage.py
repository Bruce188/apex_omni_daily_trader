"""
Tests for Data Storage.

Tests cover:
- Save/load operations
- File handling
- Data integrity
- Weekly boundaries
"""

import pytest
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.storage import Storage
from data.models import Trade, TradeResult, WeeklyTradeRecord, StakingInfo, TradeStatus


# =============================================================================
# Storage Initialization Tests
# =============================================================================

class TestStorageInit:
    """Tests for Storage initialization."""

    def test_storage_creates_directory(self, temp_data_dir):
        """Should create data directory if not exists."""
        new_dir = Path(temp_data_dir) / "new_storage"
        storage = Storage(data_dir=str(new_dir))
        assert new_dir.exists()

    def test_storage_default_directory(self):
        """Should use default directory when not specified."""
        storage = Storage()
        # data_dir is resolved (absolute), so compare resolved paths
        assert storage.data_dir == Path(Storage.DEFAULT_DATA_DIR).resolve()


# =============================================================================
# Trade History Tests
# =============================================================================

class TestTradeHistory:
    """Tests for trade history operations."""

    def test_save_trade(self, storage, sample_trade_result):
        """Should save trade to history."""
        result = storage.save_trade(sample_trade_result)
        assert result is True

    def test_get_all_trades_empty(self, storage):
        """Should return empty list when no trades."""
        trades = storage.get_all_trades()
        assert trades == []

    def test_get_all_trades_with_data(self, storage, sample_trade_result):
        """Should return all saved trades."""
        storage.save_trade(sample_trade_result)
        storage.save_trade(sample_trade_result)

        trades = storage.get_all_trades()
        assert len(trades) == 2

    def test_get_recent_trades(self, storage, sample_trade_result):
        """Should return most recent trades first."""
        # Create trades with different timestamps
        for i in range(5):
            trade = Trade(
                symbol="BTC-USDT",
                side="buy",
                size=0.001,
                price=95000.0,
            )
            result = TradeResult(
                trade=trade,
                success=True,
                order_id=f"ORDER-{i:03d}",
                executed_price=95000.0,
                executed_size=0.001,
                timestamp=datetime.utcnow() - timedelta(hours=i),
            )
            storage.save_trade(result)

        recent = storage.get_recent_trades(count=3)
        assert len(recent) == 3
        # Most recent should be first
        assert recent[0].order_id == "ORDER-000"

    def test_get_trades_for_week(self, storage, sample_trade_result):
        """Should filter trades by week."""
        week_start, _ = Storage.get_current_week_boundaries()

        # Trade in current week
        sample_trade_result.timestamp = week_start + timedelta(days=1)
        storage.save_trade(sample_trade_result)

        # Trade from last week (should not be included)
        old_trade = Trade(
            symbol="BTC-USDT",
            side="buy",
            size=0.001,
            price=95000.0,
        )
        old_result = TradeResult(
            trade=old_trade,
            success=True,
            order_id="OLD-001",
            timestamp=week_start - timedelta(days=1),
        )
        storage.save_trade(old_result)

        week_trades = storage.get_trades_for_week(week_start)
        assert len(week_trades) == 1
        assert week_trades[0].order_id == sample_trade_result.order_id

    def test_clear_trades(self, storage, sample_trade_result):
        """Should clear all trade history."""
        storage.save_trade(sample_trade_result)
        assert len(storage.get_all_trades()) == 1

        result = storage.clear_trades()
        assert result is True
        assert len(storage.get_all_trades()) == 0


# =============================================================================
# Weekly Record Tests
# =============================================================================

class TestWeeklyRecords:
    """Tests for weekly record operations."""

    def test_save_weekly_record(self, storage, sample_weekly_record):
        """Should save weekly record."""
        result = storage.save_weekly_record(sample_weekly_record)
        assert result is True

    def test_get_weekly_record(self, storage, sample_weekly_record):
        """Should retrieve saved weekly record."""
        storage.save_weekly_record(sample_weekly_record)

        retrieved = storage.get_weekly_record(sample_weekly_record.week_start)
        assert retrieved is not None
        assert retrieved.week_start == sample_weekly_record.week_start

    def test_get_weekly_record_not_found(self, storage):
        """Should return None for non-existent week."""
        old_week = datetime.utcnow() - timedelta(weeks=52)
        result = storage.get_weekly_record(old_week)
        assert result is None

    def test_get_current_week_record_new(self, storage):
        """Should create new record for current week."""
        record = storage.get_current_week_record()

        assert record is not None
        assert record.trades == []
        assert record.days_traded == set()

    def test_get_current_week_record_existing(self, storage, sample_weekly_record):
        """Should return existing record for current week."""
        sample_weekly_record.days_traded = {0, 1}
        storage.save_weekly_record(sample_weekly_record)

        record = storage.get_current_week_record()
        assert record.days_traded == {0, 1}

    def test_update_weekly_record(self, storage, sample_weekly_record):
        """Should update existing weekly record."""
        storage.save_weekly_record(sample_weekly_record)

        # Update the record
        sample_weekly_record.days_traded = {0, 1, 2}
        storage.save_weekly_record(sample_weekly_record)

        # Should have same record, not duplicate
        all_records = storage.get_all_weekly_records()
        assert len(all_records) == 1
        assert all_records[0].days_traded == {0, 1, 2}

    def test_get_all_weekly_records(self, storage):
        """Should return all weekly records."""
        week_start, week_end = Storage.get_current_week_boundaries()

        # Create records for multiple weeks
        for i in range(3):
            record = WeeklyTradeRecord(
                week_start=week_start - timedelta(weeks=i),
                week_end=week_end - timedelta(weeks=i),
            )
            storage.save_weekly_record(record)

        records = storage.get_all_weekly_records()
        assert len(records) == 3


# =============================================================================
# Staking Info Tests
# =============================================================================

class TestStakingInfo:
    """Tests for staking info operations."""

    def test_save_staking_info(self, storage, sample_staking_info):
        """Should save staking info."""
        result = storage.save_staking_info(sample_staking_info)
        assert result is True

    def test_get_staking_info(self, storage, sample_staking_info):
        """Should retrieve saved staking info."""
        storage.save_staking_info(sample_staking_info)

        info = storage.get_staking_info()
        assert info is not None
        assert info.staked_amount == sample_staking_info.staked_amount
        assert info.lock_months == sample_staking_info.lock_months

    def test_get_staking_info_not_found(self, storage):
        """Should return None when no staking info."""
        info = storage.get_staking_info()
        assert info is None


# =============================================================================
# Bot State Tests
# =============================================================================

class TestBotState:
    """Tests for bot state operations."""

    def test_save_state(self, storage):
        """Should save bot state."""
        state = {"key": "value", "count": 42}
        result = storage.save_state(state)
        assert result is True

    def test_get_state(self, storage):
        """Should retrieve saved state."""
        state = {"key": "value", "count": 42}
        storage.save_state(state)

        retrieved = storage.get_state()
        assert retrieved["key"] == "value"
        assert retrieved["count"] == 42

    def test_get_state_empty(self, storage):
        """Should return empty dict when no state."""
        state = storage.get_state()
        assert state == {}

    def test_update_state(self, storage):
        """Should update specific state fields."""
        storage.save_state({"a": 1, "b": 2})
        storage.update_state({"b": 3, "c": 4})

        state = storage.get_state()
        assert state["a"] == 1
        assert state["b"] == 3
        assert state["c"] == 4


# =============================================================================
# Week Boundaries Tests
# =============================================================================

class TestWeekBoundaries:
    """Tests for week boundary calculations."""

    def test_get_current_week_boundaries(self):
        """Should return correct week boundaries."""
        week_start, week_end = Storage.get_current_week_boundaries()

        # Week start should be Monday at 8 AM UTC
        assert week_start.weekday() == 0  # Monday
        assert week_start.hour == 8
        assert week_start.minute == 0

        # Week end should be 7 days after start
        assert (week_end - week_start).days == 7

    def test_get_current_trading_day(self):
        """Should return trading day 1-5 or 0 for weekend."""
        day = Storage.get_current_trading_day()
        assert 0 <= day <= 5


# =============================================================================
# Has Traded Today Tests
# =============================================================================

class TestHasTradedToday:
    """Tests for today's trading status."""

    def test_has_traded_today_false(self, storage):
        """Should return False when no trades today."""
        assert storage.has_traded_today() is False

    def test_has_traded_today_true(self, storage):
        """Should return True after marking traded."""
        storage.mark_traded_today()
        assert storage.has_traded_today() is True

    def test_mark_traded_today(self, storage):
        """Should mark that a trade was executed today."""
        result = storage.mark_traded_today()
        assert result is True

        state = storage.get_state()
        assert "last_trade_date" in state


# =============================================================================
# Days Traded This Week Tests
# =============================================================================

class TestDaysTradedThisWeek:
    """Tests for days traded count."""

    def test_days_traded_empty(self, storage):
        """Should return 0 when no trades this week."""
        count = storage.get_days_traded_this_week()
        assert count == 0

    def test_days_traded_with_record(self, storage, sample_weekly_record):
        """Should return count from weekly record."""
        sample_weekly_record.days_traded = {0, 1, 2}
        storage.save_weekly_record(sample_weekly_record)

        count = storage.get_days_traded_this_week()
        assert count == 3


# =============================================================================
# Export Data Tests
# =============================================================================

class TestExportData:
    """Tests for data export functionality."""

    def test_export_data(self, storage, sample_trade_result, sample_weekly_record, sample_staking_info, temp_data_dir):
        """Should export all data to JSON file."""
        # Save some data
        storage.save_trade(sample_trade_result)
        storage.save_weekly_record(sample_weekly_record)
        storage.save_staking_info(sample_staking_info)
        storage.save_state({"test": "state"})

        export_path = Path(temp_data_dir) / "export.json"
        result = storage.export_data(str(export_path))

        assert result is True
        assert export_path.exists()

        # Verify exported data
        with open(export_path) as f:
            data = json.load(f)

        assert "export_timestamp" in data
        assert "trades" in data
        assert "weekly_records" in data
        assert "staking_info" in data
        assert "state" in data


# =============================================================================
# File Locking Tests
# =============================================================================

class TestFileLocking:
    """Tests for file locking behavior."""

    def test_read_json_nonexistent_file(self, storage):
        """Should return None for nonexistent file."""
        result = storage._read_json("nonexistent.json")
        assert result is None

    def test_write_and_read_json(self, storage):
        """Should write and read JSON correctly."""
        data = {"test": "data", "number": 42}
        storage._write_json("test.json", data)

        result = storage._read_json("test.json")
        assert result == data


# =============================================================================
# Data Integrity Tests
# =============================================================================

class TestDataIntegrity:
    """Tests for data integrity."""

    def test_trade_roundtrip(self, storage, sample_trade_result):
        """Trade data should survive save/load cycle."""
        original_order_id = sample_trade_result.order_id
        original_price = sample_trade_result.executed_price

        storage.save_trade(sample_trade_result)
        trades = storage.get_all_trades()

        assert len(trades) == 1
        assert trades[0].order_id == original_order_id
        assert trades[0].executed_price == original_price

    def test_weekly_record_roundtrip(self, storage, sample_weekly_record):
        """Weekly record data should survive save/load cycle."""
        sample_weekly_record.days_traded = {0, 2, 4}

        storage.save_weekly_record(sample_weekly_record)
        records = storage.get_all_weekly_records()

        assert len(records) == 1
        assert records[0].days_traded == {0, 2, 4}

    def test_staking_info_roundtrip(self, storage, sample_staking_info):
        """Staking info should survive save/load cycle."""
        original_amount = sample_staking_info.staked_amount
        original_months = sample_staking_info.lock_months

        storage.save_staking_info(sample_staking_info)
        info = storage.get_staking_info()

        assert info.staked_amount == original_amount
        assert info.lock_months == original_months


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
