#!/usr/bin/env python3
"""
ApexOmni Automatic Daily Trader
Runs continuously and executes 1 trade per day for staking factor bonus.

Staking Factor Rules:
- +0.1 per day traded (only 1 trade counts per day)
- +0.5 maximum per week (5 different days)
- Must repeat weekly to maintain multiplier

This script:
- Checks every hour if a trade is needed
- Executes 1 trade per day (UTC time)
- Tracks trading days to avoid duplicates
- Logs all activity
- Implements circuit breaker for failure protection
"""

import os
import sys
import time
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from textwrap import dedent

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/app/data/trader.log')
    ]
)
logger = logging.getLogger(__name__)

# Configuration from environment
API_KEY = os.getenv('APEX_API_KEY')
API_SECRET = os.getenv('APEX_API_SECRET')
PASSPHRASE = os.getenv('APEX_PASSPHRASE')
ZK_SEEDS = os.getenv('APEX_ZK_SEEDS')
ZK_L2KEY = os.getenv('APEX_ZK_L2KEY')

# Trading hours (UTC) - trade between these hours
TRADE_HOUR_START = int(os.getenv('TRADE_HOUR_START', '8'))  # 8 AM UTC
TRADE_HOUR_END = int(os.getenv('TRADE_HOUR_END', '20'))     # 8 PM UTC

# Check interval in seconds
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '3600'))  # 1 hour default

# Data file for persistence
DATA_FILE = Path('/app/data/trade_history.json')

# Debug mode for detailed error logging
DEBUG = os.getenv('DEBUG', '').lower() == 'true'

# Network mode (testnet/mainnet)
USE_TESTNET = os.getenv('APEX_TESTNET', 'false').lower() == 'true'

# Circuit breaker settings
MAX_CONSECUTIVE_FAILURES = int(os.getenv('MAX_FAILURES', '5'))
CIRCUIT_RESET_MINUTES = int(os.getenv('CIRCUIT_RESET_MINUTES', '30'))


def log_error(message: str, exception: Exception = None) -> None:
    """
    Log error with appropriate detail level based on DEBUG setting.

    In production (DEBUG=false), sanitizes error messages.
    """
    if DEBUG and exception:
        logger.error(f"{message}: {exception}")
    elif exception:
        logger.error(f"{message}. Enable DEBUG=true for details.")
    else:
        logger.error(message)


class CircuitBreaker:
    """Simple circuit breaker for failure protection."""

    def __init__(self, max_failures: int = 5, reset_minutes: int = 30):
        self.max_failures = max_failures
        self.reset_minutes = reset_minutes
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)
        if self.failure_count >= self.max_failures:
            self.state = "OPEN"
            logger.warning(dedent(f"""
                Circuit breaker OPEN after {self.failure_count} consecutive failures.
                Trading halted for {self.reset_minutes} minutes.
            """).strip())

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"

    def can_execute(self) -> tuple:
        if self.state == "CLOSED":
            return True, "Circuit closed"
        if self.state == "OPEN" and self.last_failure_time:
            elapsed = datetime.now(timezone.utc) - self.last_failure_time
            if elapsed >= timedelta(minutes=self.reset_minutes):
                self.state = "HALF_OPEN"
                return True, "Circuit half-open, testing recovery"
            remaining = self.reset_minutes - (elapsed.total_seconds() / 60)
            return False, f"Circuit OPEN, resumes in {remaining:.1f} minutes"
        if self.state == "HALF_OPEN":
            return True, "Circuit half-open"
        return False, f"Unknown state: {self.state}"


# Global circuit breaker instance
circuit_breaker = CircuitBreaker(MAX_CONSECUTIVE_FAILURES, CIRCUIT_RESET_MINUTES)


# Cheapest trades to rotate through
TRADES = [
    {"symbol": "ARB-USDT", "size": "0.1", "price": "0.35"},
    {"symbol": "APT-USDT", "size": "0.01", "price": "4.00"},
    {"symbol": "OP-USDT", "size": "0.1", "price": "0.50"},
    {"symbol": "TIA-USDT", "size": "0.1", "price": "1.00"},
    {"symbol": "1000SHIB-USDT", "size": "10", "price": "0.015"},
]


def load_history():
    """Load trade history from file"""
    if DATA_FILE.exists():
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {
        "traded_dates": [],
        "trades": [],
        "current_week": None,
        "weekly_days_traded": 0
    }


def save_history(history):
    """Save trade history to file"""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, 'w') as f:
        json.dump(history, f, indent=2)


def get_week_number(dt):
    """Get ISO week number"""
    return dt.isocalendar()[1]


def get_utc_now():
    """Get current UTC time"""
    return datetime.now(timezone.utc)


def should_trade_now():
    """Check if we should execute a trade now"""
    now = get_utc_now()
    today = now.strftime("%Y-%m-%d")
    current_hour = now.hour
    current_week = get_week_number(now)

    history = load_history()

    # Reset weekly counter if new week
    if history.get("current_week") != current_week:
        logger.info(f"New week {current_week} - resetting weekly counter")
        history["current_week"] = current_week
        history["weekly_days_traded"] = 0
        save_history(history)

    # Check if already traded today
    if today in history.get("traded_dates", []):
        logger.debug(f"Already traded today ({today})")
        return False, "Already traded today"

    # Check weekly limit (5 days max)
    if history.get("weekly_days_traded", 0) >= 5:
        logger.debug(f"Weekly limit reached (5/5 days)")
        return False, "Weekly limit reached"

    # Check if within trading hours
    if not (TRADE_HOUR_START <= current_hour < TRADE_HOUR_END):
        logger.debug(f"Outside trading hours ({current_hour}h, need {TRADE_HOUR_START}-{TRADE_HOUR_END})")
        return False, "Outside trading hours"

    return True, "Ready to trade"


def execute_trade():
    """Execute one trade with circuit breaker protection."""
    # Check circuit breaker first
    can_trade, reason = circuit_breaker.can_execute()
    if not can_trade:
        logger.warning(f"Trade blocked by circuit breaker: {reason}")
        return False, reason

    now = get_utc_now()
    today = now.strftime("%Y-%m-%d")
    weekday = now.weekday()

    # Select trade based on weekday (rotates through the list)
    trade = TRADES[weekday % len(TRADES)]

    # Generate unique client order ID for deduplication
    client_order_id = f"auto_{today}_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    logger.info(f"Executing trade: {trade['symbol']} BUY {trade['size']}")

    try:
        from apexomni.http_private_sign import HttpPrivateSign

        # Support testnet/mainnet based on config
        if USE_TESTNET:
            from apexomni.constants import APEX_OMNI_HTTP_TEST, NETWORKID_TEST
            endpoint = APEX_OMNI_HTTP_TEST
            network_id = NETWORKID_TEST
            logger.info("Using TESTNET")
        else:
            from apexomni.constants import APEX_OMNI_HTTP_MAIN, NETWORKID_MAIN
            endpoint = APEX_OMNI_HTTP_MAIN
            network_id = NETWORKID_MAIN
            logger.info("Using MAINNET")

        client = HttpPrivateSign(
            endpoint,
            network_id=network_id,
            zk_seeds=ZK_SEEDS,
            zk_l2Key=ZK_L2KEY,
            api_key_credentials={
                'key': API_KEY,
                'secret': API_SECRET,
                'passphrase': PASSPHRASE
            }
        )

        client.configs_v3()
        client.get_account_v3()

        result = client.create_order_v3(
            symbol=trade['symbol'],
            side="BUY",
            type="MARKET",
            size=trade['size'],
            price=trade['price'],
            clientId=client_order_id
        )

        if result.get('code'):
            error_msg = result.get('msg', 'Unknown error')
            log_error(f"Trade failed: {error_msg}")
            circuit_breaker.record_failure()
            return False, error_msg if DEBUG else "Trade failed"

        order_id = result.get('data', {}).get('orderId', 'N/A')
        logger.info(f"Trade successful! Order ID: {order_id}")

        # Record success with circuit breaker
        circuit_breaker.record_success()

        # Update history
        history = load_history()
        history["traded_dates"].append(today)
        history["trades"].append({
            "date": today,
            "symbol": trade['symbol'],
            "size": trade['size'],
            "order_id": order_id,
            "client_order_id": client_order_id,
            "timestamp": now.isoformat()
        })
        history["weekly_days_traded"] = history.get("weekly_days_traded", 0) + 1
        save_history(history)

        bonus = history["weekly_days_traded"] * 0.1
        logger.info(f"Weekly progress: {history['weekly_days_traded']}/5 days (+{bonus:.1f} bonus)")

        return True, order_id

    except Exception as e:
        log_error("Trade error", e)
        circuit_breaker.record_failure()
        return False, str(e) if DEBUG else "Trade execution error"


def check_and_trade():
    """Main check and trade function"""
    should_trade, reason = should_trade_now()

    if should_trade:
        logger.info("Trade conditions met - executing trade")
        success, result = execute_trade()
        if success:
            logger.info(f"Daily trade completed successfully")
        else:
            logger.error(f"Daily trade failed: {result}")
    else:
        logger.debug(f"No trade needed: {reason}")


def validate_config():
    """Validate required configuration"""
    required = {
        'APEX_API_KEY': API_KEY,
        'APEX_API_SECRET': API_SECRET,
        'APEX_PASSPHRASE': PASSPHRASE,
        'APEX_ZK_SEEDS': ZK_SEEDS,
        'APEX_ZK_L2KEY': ZK_L2KEY
    }

    missing = [k for k, v in required.items() if not v]
    if missing:
        logger.error(f"Missing required environment variables: {missing}")
        return False

    logger.info("Configuration validated successfully")
    return True


def get_status():
    """Get current status"""
    now = get_utc_now()
    history = load_history()
    current_week = get_week_number(now)

    # Reset if new week
    if history.get("current_week") != current_week:
        weekly_days = 0
    else:
        weekly_days = history.get("weekly_days_traded", 0)

    return {
        "current_time_utc": now.isoformat(),
        "today": now.strftime("%Y-%m-%d"),
        "week_number": current_week,
        "weekly_days_traded": weekly_days,
        "weekly_bonus": f"+{weekly_days * 0.1:.1f}",
        "traded_today": now.strftime("%Y-%m-%d") in history.get("traded_dates", []),
        "total_trades": len(history.get("trades", []))
    }


def warn_if_live_mainnet() -> bool:
    """
    Display warning if running on mainnet.

    Returns:
        True if user confirms (or auto-confirms after timeout),
        False if user aborts.
    """
    if USE_TESTNET:
        return True

    warning = dedent("""
        ================================================================
                              WARNING
        ================================================================

          You are about to run the Docker trader on MAINNET!

          - Real funds will be used for trading
          - Actual orders will be placed on ApexOmni
          - Losses are possible and irreversible

          Set APEX_TESTNET=true for testnet mode.
          Press Ctrl+C within 5 seconds to abort...

        ================================================================
    """).strip()

    logger.warning(warning)
    print(warning)

    try:
        for i in range(5, 0, -1):
            print(f"  Starting in {i} seconds...", end="\r")
            time.sleep(1)
        print("  Starting now!          ")
        return True
    except KeyboardInterrupt:
        print("\n  Aborted by user.")
        logger.info("Mainnet trading aborted by user")
        return False


def main():
    """Main loop"""
    logger.info("=" * 60)
    logger.info("ApexOmni Automatic Daily Trader Starting")
    logger.info("=" * 60)

    if not validate_config():
        sys.exit(1)

    # Show mainnet warning
    if not warn_if_live_mainnet():
        sys.exit(0)

    network_mode = "TESTNET" if USE_TESTNET else "MAINNET"
    logger.info(f"Network: {network_mode}")
    logger.info(f"Trading hours: {TRADE_HOUR_START}:00 - {TRADE_HOUR_END}:00 UTC")
    logger.info(f"Check interval: {CHECK_INTERVAL} seconds")

    # Show initial status
    status = get_status()
    logger.info(f"Current status: Week {status['week_number']}, "
                f"{status['weekly_days_traded']}/5 days traded ({status['weekly_bonus']})")

    # Initial check
    check_and_trade()

    # Main loop
    logger.info(f"Entering main loop (checking every {CHECK_INTERVAL}s)")
    while True:
        time.sleep(CHECK_INTERVAL)
        try:
            check_and_trade()
        except Exception as e:
            log_error("Error in main loop", e)


if __name__ == "__main__":
    main()
