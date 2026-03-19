"""
Bot State Persistence for ApexOmni Trading Bot.

Provides simple JSON-based state tracking for the continuous trading daemon.
Tracks whether the bot has traded today and weekly boundaries.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.resolve()


class Storage:
    """
    Simple file-based bot state storage.

    Used by run_continuous.py to track daily trade status
    and weekly staking boundaries.
    """

    DEFAULT_DATA_DIR = "data"
    STATE_FILE = "bot_state.json"

    ALLOWED_PATH_PREFIXES = [
        str(PROJECT_ROOT),
        "/app/data",
        "/tmp",
    ]

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir:
            self.data_dir = Path(data_dir).resolve()
            self._validate_data_dir()
        else:
            self.data_dir = Path(self.DEFAULT_DATA_DIR).resolve()

        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _validate_data_dir(self) -> None:
        data_dir_str = str(self.data_dir)
        is_allowed = any(
            data_dir_str.startswith(prefix)
            for prefix in self.ALLOWED_PATH_PREFIXES
        )
        if not is_allowed:
            raise ValueError(
                f"Data directory path not allowed: {self.data_dir}. "
                f"Allowed prefixes: {self.ALLOWED_PATH_PREFIXES}"
            )

    def _get_file_path(self, filename: str) -> Path:
        return self.data_dir / filename

    def _read_json(self, filename: str) -> Optional[Dict[str, Any]]:
        file_path = self._get_file_path(filename)
        if not file_path.exists():
            return None
        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Failed to read {filename}: {e}")
            return None

    def _write_json(self, filename: str, data: Dict[str, Any]) -> bool:
        file_path = self._get_file_path(filename)
        try:
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except Exception as e:
            logger.error(f"Failed to write {filename}: {e}")
            return False

    def get_state(self) -> Dict[str, Any]:
        return self._read_json(self.STATE_FILE) or {}

    def save_state(self, state: Dict[str, Any]) -> bool:
        state["last_updated"] = datetime.now(timezone.utc).isoformat()
        return self._write_json(self.STATE_FILE, state)

    def update_state(self, updates: Dict[str, Any]) -> bool:
        state = self.get_state()
        state.update(updates)
        return self.save_state(state)

    def has_traded_today(self) -> bool:
        state = self.get_state()
        last_trade_date = state.get("last_trade_date")
        if not last_trade_date:
            return False
        last_trade = datetime.fromisoformat(last_trade_date)
        today_start = self._get_day_boundary(datetime.now(timezone.utc))
        if last_trade.tzinfo is None:
            last_trade = last_trade.replace(tzinfo=timezone.utc)
        return last_trade >= today_start

    def mark_traded_today(self) -> bool:
        return self.update_state({
            "last_trade_date": datetime.now(timezone.utc).isoformat()
        })

    @staticmethod
    def get_current_week_boundaries() -> tuple:
        now = datetime.now(timezone.utc)
        days_since_monday = now.weekday()
        monday = now - timedelta(days=days_since_monday)
        week_start = monday.replace(hour=8, minute=0, second=0, microsecond=0)
        if now < week_start:
            week_start -= timedelta(days=7)
        week_end = week_start + timedelta(days=7)
        return week_start, week_end

    @staticmethod
    def _get_day_boundary(dt: datetime) -> datetime:
        boundary = dt.replace(hour=8, minute=0, second=0, microsecond=0)
        if dt.hour < 8:
            boundary -= timedelta(days=1)
        return boundary
