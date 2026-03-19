"""
Tests for Bot State Storage.

Tests the slimmed-down Storage class that handles
bot state persistence for the continuous trading daemon.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.storage import Storage


class TestStorageInit:

    def test_storage_creates_directory(self, temp_data_dir):
        new_dir = Path(temp_data_dir) / "new_storage"
        storage = Storage(data_dir=str(new_dir))
        assert new_dir.exists()

    def test_storage_default_directory(self):
        storage = Storage()
        assert storage.data_dir == Path(Storage.DEFAULT_DATA_DIR).resolve()

    def test_storage_rejects_disallowed_path(self):
        with pytest.raises(ValueError, match="not allowed"):
            Storage(data_dir="/etc/evil")


class TestBotState:

    def test_save_state(self, storage):
        state = {"key": "value", "count": 42}
        result = storage.save_state(state)
        assert result is True

    def test_get_state(self, storage):
        state = {"key": "value", "count": 42}
        storage.save_state(state)
        retrieved = storage.get_state()
        assert retrieved["key"] == "value"
        assert retrieved["count"] == 42

    def test_get_state_empty(self, storage):
        state = storage.get_state()
        assert state == {}

    def test_update_state(self, storage):
        storage.save_state({"a": 1, "b": 2})
        storage.update_state({"b": 3, "c": 4})
        state = storage.get_state()
        assert state["a"] == 1
        assert state["b"] == 3
        assert state["c"] == 4


class TestHasTradedToday:

    def test_has_traded_today_false(self, storage):
        assert storage.has_traded_today() is False

    def test_has_traded_today_true(self, storage):
        storage.mark_traded_today()
        assert storage.has_traded_today() is True

    def test_mark_traded_today(self, storage):
        result = storage.mark_traded_today()
        assert result is True
        state = storage.get_state()
        assert "last_trade_date" in state


class TestWeekBoundaries:

    def test_get_current_week_boundaries(self):
        week_start, week_end = Storage.get_current_week_boundaries()
        assert week_start.weekday() == 0  # Monday
        assert week_start.hour == 8
        assert week_start.minute == 0
        assert (week_end - week_start).days == 7

    def test_day_boundary_after_8am(self):
        dt = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        boundary = Storage._get_day_boundary(dt)
        assert boundary.hour == 8
        assert boundary.day == 15

    def test_day_boundary_before_8am(self):
        dt = datetime(2024, 1, 15, 6, 0, 0, tzinfo=timezone.utc)
        boundary = Storage._get_day_boundary(dt)
        assert boundary.hour == 8
        assert boundary.day == 14


class TestJsonReadWrite:

    def test_read_nonexistent_file(self, storage):
        result = storage._read_json("nonexistent.json")
        assert result is None

    def test_write_and_read(self, storage):
        data = {"test": "data", "number": 42}
        storage._write_json("test.json", data)
        result = storage._read_json("test.json")
        assert result == data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
