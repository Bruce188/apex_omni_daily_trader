"""
Data Persistence for ApexOmni Trading Bot.

This module provides file-based storage for trade history and weekly records.
Uses JSON format for human-readable data persistence.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from textwrap import dedent
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# filelock is required for concurrent access safety
from filelock import FileLock

from data.models import Trade, TradeResult, WeeklyTradeRecord, StakingInfo

logger = logging.getLogger(__name__)

# Get project root for path validation
PROJECT_ROOT = Path(__file__).parent.parent.resolve()


class Storage:
    """
    File-based storage for trading bot data.

    Provides persistent storage for:
    - Trade history
    - Weekly records
    - Staking information
    - Bot state

    All data is stored in JSON format for easy inspection and debugging.

    Attributes:
        data_dir: Directory where data files are stored
    """

    DEFAULT_DATA_DIR = "data_store"
    TRADES_FILE = "trades.json"
    WEEKLY_FILE = "weekly_records.json"
    STAKING_FILE = "staking_info.json"
    STATE_FILE = "bot_state.json"

    # Allowed path prefixes for data directory (security)
    ALLOWED_PATH_PREFIXES = [
        str(PROJECT_ROOT),  # Project root
        "/app/data",        # Docker container path
        "/tmp",             # Temp directory for tests
    ]

    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize storage with specified data directory.

        Args:
            data_dir: Directory to store data files. Creates if not exists.
                     Defaults to 'data_store' in current directory.

        Raises:
            ValueError: If data_dir is outside allowed paths (security)
        """
        if data_dir:
            self.data_dir = Path(data_dir).resolve()
            self._validate_data_dir()
        else:
            self.data_dir = Path(self.DEFAULT_DATA_DIR).resolve()

        self._ensure_data_dir()
        self._verify_file_locking()

    def _validate_data_dir(self) -> None:
        """
        Validate data directory is safe (within project or common paths).

        Prevents path traversal attacks by ensuring data_dir is within
        allowed prefixes.

        Raises:
            ValueError: If data directory is outside allowed paths
        """
        data_dir_str = str(self.data_dir)

        is_allowed = any(
            data_dir_str.startswith(prefix)
            for prefix in self.ALLOWED_PATH_PREFIXES
        )

        if not is_allowed:
            raise ValueError(dedent(f"""
                Data directory path not allowed: {self.data_dir}
                Must be within project root or /app/data (Docker).
                Allowed prefixes: {self.ALLOWED_PATH_PREFIXES}
            """).strip())

    def _verify_file_locking(self) -> None:
        """
        Verify file locking is functional.

        Logs a warning if file locking doesn't work as expected.
        """
        test_lock_path = self.data_dir / ".lock_test"
        try:
            with FileLock(str(test_lock_path), timeout=1):
                pass
            # Clean up test lock file
            if test_lock_path.exists():
                test_lock_path.unlink()
            lock_file = Path(str(test_lock_path) + ".lock")
            if lock_file.exists():
                lock_file.unlink()
        except Exception as e:
            logger.warning(dedent(f"""
                File locking may not work correctly: {e}
                Concurrent access could cause data corruption.
            """).strip())

    def _ensure_data_dir(self) -> None:
        """Create data directory if it doesn't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Data directory: {self.data_dir.absolute()}")

    def _get_file_path(self, filename: str) -> Path:
        """Get full path for a data file."""
        return self.data_dir / filename

    def _get_lock_path(self, filename: str) -> Path:
        """Get path for file lock."""
        return self.data_dir / f"{filename}.lock"

    @contextmanager
    def _get_lock(self, filename: str):
        """
        Get a file lock context manager.

        Uses filelock to ensure safe concurrent access.
        """
        lock_path = self._get_lock_path(filename)
        lock = FileLock(lock_path)
        with lock:
            yield

    def _read_json(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Read JSON file with file locking.

        Args:
            filename: Name of the file to read

        Returns:
            Parsed JSON data or None if file doesn't exist
        """
        file_path = self._get_file_path(filename)

        if not file_path.exists():
            return None

        try:
            with self._get_lock(filename):
                with open(file_path, "r") as f:
                    return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {filename}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to read {filename}: {e}")
            return None

    def _write_json(self, filename: str, data: Dict[str, Any]) -> bool:
        """
        Write JSON file with file locking.

        Args:
            filename: Name of the file to write
            data: Data to serialize and write

        Returns:
            True if write was successful, False otherwise
        """
        file_path = self._get_file_path(filename)

        try:
            with self._get_lock(filename):
                with open(file_path, "w") as f:
                    json.dump(data, f, indent=2, default=str)
            return True
        except Exception as e:
            logger.error(f"Failed to write {filename}: {e}")
            return False

    # =========================================================================
    # Trade History Methods
    # =========================================================================

    def save_trade(self, trade_result: TradeResult) -> bool:
        """
        Save a single trade result to history.

        Args:
            trade_result: The trade result to save

        Returns:
            True if save was successful
        """
        trades_data = self._read_json(self.TRADES_FILE) or {"trades": []}
        trades_data["trades"].append(trade_result.to_dict())
        trades_data["last_updated"] = datetime.utcnow().isoformat()

        success = self._write_json(self.TRADES_FILE, trades_data)
        if success:
            logger.info(f"Saved trade: {trade_result.order_id}")
        return success

    def get_all_trades(self) -> List[TradeResult]:
        """
        Get all trade results from history.

        Returns:
            List of all trade results
        """
        trades_data = self._read_json(self.TRADES_FILE)
        if not trades_data:
            return []

        return [
            TradeResult.from_dict(t)
            for t in trades_data.get("trades", [])
        ]

    def get_trades_for_week(self, week_start: datetime) -> List[TradeResult]:
        """
        Get trades for a specific week.

        Args:
            week_start: Start of the week (Monday 8AM UTC)

        Returns:
            List of trade results for that week
        """
        week_end = week_start + timedelta(days=7)
        all_trades = self.get_all_trades()

        return [
            t for t in all_trades
            if week_start <= t.timestamp < week_end
        ]

    def get_recent_trades(self, count: int = 10) -> List[TradeResult]:
        """
        Get the most recent trades.

        Args:
            count: Number of recent trades to return

        Returns:
            List of most recent trade results
        """
        all_trades = self.get_all_trades()
        return sorted(all_trades, key=lambda t: t.timestamp, reverse=True)[:count]

    def clear_trades(self) -> bool:
        """
        Clear all trade history.

        Returns:
            True if successful
        """
        return self._write_json(self.TRADES_FILE, {
            "trades": [],
            "cleared_at": datetime.utcnow().isoformat()
        })

    # =========================================================================
    # Weekly Record Methods
    # =========================================================================

    def save_weekly_record(self, record: WeeklyTradeRecord) -> bool:
        """
        Save a weekly trade record.

        Args:
            record: The weekly record to save

        Returns:
            True if save was successful
        """
        weekly_data = self._read_json(self.WEEKLY_FILE) or {"records": []}

        # Find and update existing record for this week, or add new
        week_key = record.week_start.isoformat()
        existing_idx = None

        for idx, r in enumerate(weekly_data.get("records", [])):
            if r.get("week_start") == week_key:
                existing_idx = idx
                break

        if existing_idx is not None:
            weekly_data["records"][existing_idx] = record.to_dict()
        else:
            weekly_data["records"].append(record.to_dict())

        weekly_data["last_updated"] = datetime.utcnow().isoformat()

        success = self._write_json(self.WEEKLY_FILE, weekly_data)
        if success:
            logger.info(f"Saved weekly record for week starting {week_key}")
        return success

    def get_weekly_record(self, week_start: datetime) -> Optional[WeeklyTradeRecord]:
        """
        Get the weekly record for a specific week.

        Args:
            week_start: Start of the week

        Returns:
            Weekly record or None if not found
        """
        weekly_data = self._read_json(self.WEEKLY_FILE)
        if not weekly_data:
            return None

        week_key = week_start.isoformat()
        for r in weekly_data.get("records", []):
            if r.get("week_start") == week_key:
                return WeeklyTradeRecord.from_dict(r)

        return None

    def get_current_week_record(self) -> WeeklyTradeRecord:
        """
        Get or create the current week's record.

        Returns:
            Weekly record for the current staking week
        """
        week_start, week_end = self.get_current_week_boundaries()

        record = self.get_weekly_record(week_start)
        if record is None:
            record = WeeklyTradeRecord(
                week_start=week_start,
                week_end=week_end
            )

        return record

    def get_all_weekly_records(self) -> List[WeeklyTradeRecord]:
        """
        Get all weekly records.

        Returns:
            List of all weekly records
        """
        weekly_data = self._read_json(self.WEEKLY_FILE)
        if not weekly_data:
            return []

        return [
            WeeklyTradeRecord.from_dict(r)
            for r in weekly_data.get("records", [])
        ]

    # =========================================================================
    # Staking Info Methods
    # =========================================================================

    def save_staking_info(self, info: StakingInfo) -> bool:
        """
        Save staking information.

        Args:
            info: The staking info to save

        Returns:
            True if save was successful
        """
        staking_data = info.to_dict()
        staking_data["last_updated"] = datetime.utcnow().isoformat()

        success = self._write_json(self.STAKING_FILE, staking_data)
        if success:
            logger.info(f"Saved staking info: {info.staked_amount} APEX, {info.lock_months} months lock")
        return success

    def get_staking_info(self) -> Optional[StakingInfo]:
        """
        Get saved staking information.

        Returns:
            Staking info or None if not set
        """
        staking_data = self._read_json(self.STAKING_FILE)
        if not staking_data:
            return None

        return StakingInfo.from_dict(staking_data)

    # =========================================================================
    # Bot State Methods
    # =========================================================================

    def save_state(self, state: Dict[str, Any]) -> bool:
        """
        Save bot state.

        Args:
            state: State dictionary to save

        Returns:
            True if save was successful
        """
        state["last_updated"] = datetime.utcnow().isoformat()
        return self._write_json(self.STATE_FILE, state)

    def get_state(self) -> Dict[str, Any]:
        """
        Get saved bot state.

        Returns:
            State dictionary or empty dict if not found
        """
        return self._read_json(self.STATE_FILE) or {}

    def update_state(self, updates: Dict[str, Any]) -> bool:
        """
        Update specific fields in bot state.

        Args:
            updates: Dictionary of fields to update

        Returns:
            True if update was successful
        """
        state = self.get_state()
        state.update(updates)
        return self.save_state(state)

    # =========================================================================
    # Utility Methods
    # =========================================================================

    @staticmethod
    def get_current_week_boundaries() -> tuple:
        """
        Get the current staking week boundaries.

        The staking week runs from Monday 8AM UTC to next Monday 8AM UTC.

        Returns:
            Tuple of (week_start, week_end) datetimes
        """
        now = datetime.utcnow()

        # Find the most recent Monday at 8AM UTC
        days_since_monday = now.weekday()  # Monday = 0
        monday = now - timedelta(days=days_since_monday)
        week_start = monday.replace(hour=8, minute=0, second=0, microsecond=0)

        # If we're before Monday 8AM, go back another week
        if now < week_start:
            week_start -= timedelta(days=7)

        week_end = week_start + timedelta(days=7)

        return week_start, week_end

    @staticmethod
    def get_current_trading_day() -> int:
        """
        Get the current trading day number (1-5).

        Returns:
            Day number (1=Monday, 5=Friday, 0 if weekend)
        """
        now = datetime.utcnow()
        weekday = now.weekday()  # 0=Monday, 6=Sunday

        if weekday <= 4:  # Monday to Friday
            return weekday + 1
        return 0  # Weekend

    def has_traded_today(self) -> bool:
        """
        Check if a trade has been executed today.

        Uses the 8AM UTC day boundary for determining "today".

        Returns:
            True if already traded today
        """
        state = self.get_state()
        last_trade_date = state.get("last_trade_date")

        if not last_trade_date:
            return False

        last_trade = datetime.fromisoformat(last_trade_date)
        today_start = self._get_day_boundary(datetime.utcnow())

        return last_trade >= today_start

    @staticmethod
    def _get_day_boundary(dt: datetime) -> datetime:
        """
        Get the 8AM UTC boundary for a given datetime.

        Args:
            dt: DateTime to get boundary for

        Returns:
            The 8AM UTC of the current "trading day"
        """
        boundary = dt.replace(hour=8, minute=0, second=0, microsecond=0)

        # If before 8AM, the trading day started yesterday at 8AM
        if dt.hour < 8:
            boundary -= timedelta(days=1)

        return boundary

    def mark_traded_today(self) -> bool:
        """
        Mark that a trade was executed today.

        Returns:
            True if state update was successful
        """
        return self.update_state({
            "last_trade_date": datetime.utcnow().isoformat()
        })

    def get_days_traded_this_week(self) -> int:
        """
        Get the count of days traded in the current week.

        Returns:
            Number of unique days with successful trades (0-5)
        """
        record = self.get_current_week_record()
        return record.num_days_traded

    def export_data(self, export_path: str) -> bool:
        """
        Export all data to a single JSON file.

        Args:
            export_path: Path to export file

        Returns:
            True if export was successful
        """
        try:
            export_data = {
                "export_timestamp": datetime.utcnow().isoformat(),
                "trades": self._read_json(self.TRADES_FILE),
                "weekly_records": self._read_json(self.WEEKLY_FILE),
                "staking_info": self._read_json(self.STAKING_FILE),
                "state": self._read_json(self.STATE_FILE),
            }

            with open(export_path, "w") as f:
                json.dump(export_data, f, indent=2, default=str)

            logger.info(f"Exported data to {export_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export data: {e}")
            return False
