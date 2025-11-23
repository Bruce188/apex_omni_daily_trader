"""
Trade Execution Engine for the ApexOmni Trading Bot.

Handles trade execution, validation, balance checks, and logging.
"""

import os
import time
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from dataclasses import dataclass, field
from textwrap import dedent
from typing import Optional
from pathlib import Path

from bot.api_client import ApexOmniClient, OrderResult, SymbolConfig
from bot.circuit_breaker import CircuitBreaker
from bot.config import Config
from bot.utils import (
    get_logger,
    get_current_utc_time,
    parse_decimal,
    format_price,
    format_size,
    calculate_trading_activity_factor,
)


# Safety constants - DO NOT CHANGE
HARDCODED_LEVERAGE = 1
MARGIN_MODE = "CROSS"


@dataclass
class Trade:
    """
    Represents a planned trade.

    Note: Positions are ALWAYS closed immediately after opening.
    This is hardcoded for safety - no configuration option.
    Leverage is ALWAYS 1x (hardcoded for safety).
    """
    symbol: str
    side: str
    order_type: str
    size: Decimal
    price: Optional[Decimal] = None
    day_number: int = 1
    # REMOVED: leverage - now always 1 (hardcoded via HARDCODED_LEVERAGE)
    # REMOVED: close_position - now always True (hardcoded)


@dataclass
class TradeResult:
    """Result of a trade execution."""
    trade: Trade
    success: bool
    order_id: Optional[str] = None
    executed_price: Optional[Decimal] = None
    executed_size: Optional[Decimal] = None
    fees: Decimal = Decimal("0")
    timestamp: datetime = field(default_factory=lambda: get_current_utc_time())
    error: Optional[str] = None

    # Close order details (if position was closed)
    close_order_id: Optional[str] = None
    close_price: Optional[Decimal] = None
    close_fees: Decimal = Decimal("0")

    @property
    def total_fees(self) -> Decimal:
        """Get total fees including close order."""
        return self.fees + self.close_fees

    @property
    def pnl(self) -> Decimal:
        """Calculate rough P&L (not including fees)."""
        if not self.success or not self.executed_price or not self.close_price:
            return Decimal("0")

        if self.trade.side.upper() == "BUY":
            return (self.close_price - self.executed_price) * (self.executed_size or self.trade.size)
        else:
            return (self.executed_price - self.close_price) * (self.executed_size or self.trade.size)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "trade": {
                "symbol": self.trade.symbol,
                "side": self.trade.side,
                "order_type": self.trade.order_type,
                "size": str(self.trade.size),
                "price": str(self.trade.price) if self.trade.price else None,
                "day_number": self.trade.day_number,
            },
            "success": self.success,
            "order_id": self.order_id,
            "executed_price": str(self.executed_price) if self.executed_price else None,
            "executed_size": str(self.executed_size) if self.executed_size else None,
            "fees": str(self.fees),
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
            "close_order_id": self.close_order_id,
            "close_price": str(self.close_price) if self.close_price else None,
            "close_fees": str(self.close_fees),
            "total_fees": str(self.total_fees),
            "pnl": str(self.pnl),
        }


class TradeExecutor:
    """
    Executes trades on ApexOmni with validation and safety checks.
    """

    def __init__(self, client: ApexOmniClient, config: Config):
        """
        Initialize the trade executor.

        Args:
            client: ApexOmni API client
            config: Bot configuration
        """
        self.client = client
        self.config = config
        self.logger = get_logger()
        self._trade_log_file = Path(config.data_dir) / "trades.json"

        # Circuit breaker for consecutive failure protection
        self.circuit_breaker = CircuitBreaker(
            max_failures=5,
            reset_timeout_minutes=30,
        )

    def _should_include_error_details(self) -> bool:
        """
        Determine if error details should be included in logs.

        In production (mainnet, not debug), sanitizes error messages.
        In development (testnet or DEBUG=true), includes full details.
        """
        return self.config.api.testnet or os.getenv("DEBUG", "").lower() == "true"

    def _log_error(
        self,
        message: str,
        exception: Optional[Exception] = None,
        include_details: Optional[bool] = None
    ) -> None:
        """
        Log error with appropriate detail level.

        Args:
            message: Base error message
            exception: Optional exception to log details from
            include_details: Override for including details (None = auto-detect)
        """
        if include_details is None:
            include_details = self._should_include_error_details()

        if include_details and exception:
            self.logger.error(f"{message}: {exception}")
        elif exception:
            self.logger.error(f"{message}. Enable DEBUG=true for details.")
        else:
            self.logger.error(message)

    def _generate_client_order_id(self, trade: Trade, attempt: int = 1) -> str:
        """
        Generate unique client_order_id for order deduplication.

        Format: {symbol}-{timestamp_ms}-{uuid_short}-{attempt}

        Args:
            trade: Trade being executed
            attempt: Retry attempt number

        Returns:
            Unique client order ID
        """
        timestamp_ms = int(time.time() * 1000)
        uuid_short = uuid.uuid4().hex[:8]
        return f"{trade.symbol}-{timestamp_ms}-{uuid_short}-{attempt}"

    def _check_existing_order(self, client_order_id: str) -> Optional[OrderResult]:
        """
        Check if an order with this client_order_id already exists.

        Used to detect if an order succeeded but was reported as failed.

        Args:
            client_order_id: The client order ID to search for

        Returns:
            OrderResult if found, None otherwise
        """
        try:
            orders = self.client.get_open_orders()
            for order in orders:
                if order.get('clientOrderId') == client_order_id:
                    self.logger.info(f"Found existing order with client_order_id: {client_order_id}")
                    return OrderResult(
                        success=True,
                        order_id=order.get('id', ''),
                        client_order_id=client_order_id,
                        symbol=order.get('symbol', ''),
                        side=order.get('side', ''),
                        order_type=order.get('type', ''),
                        size=parse_decimal(order.get('size', '0')),
                        price=parse_decimal(order.get('price', '0')),
                        filled_size=parse_decimal(order.get('filledSize', '0')),
                        filled_price=parse_decimal(order.get('avgFillPrice', '0')),
                        status=order.get('status', 'UNKNOWN'),
                    )
            return None
        except Exception:
            # If we can't check, assume order doesn't exist
            return None

    def get_min_trade_value_usdt(self, symbol_config: SymbolConfig) -> Optional[Decimal]:
        """
        Get minimum trade value in USDT for a symbol.

        Args:
            symbol_config: Symbol configuration

        Returns:
            Minimum trade value in USDT, or None if price unavailable
        """
        current_price = self.client.get_current_price(symbol_config.symbol)
        if current_price is None:
            return None
        return symbol_config.min_order_size * current_price

    def determine_best_symbol(self) -> Optional[tuple[str, Decimal, SymbolConfig]]:
        """
        Determine the best (cheapest) symbol to trade BEFORE generating a trade.

        This method ALWAYS selects the cheapest tradeable symbol based on
        available balance. There is no "preferred" symbol concept - the bot
        always optimizes for lowest minimum order value.

        This should be called first to know what symbol to use when
        generating the trade, ensuring the correct symbol is used
        from the start.

        Returns:
            Tuple of (symbol_name, min_order_size, symbol_config) if found,
            None if no tradeable symbol available
        """
        # Get current balance
        balance = self.client.get_account_balance()
        if balance is None:
            self.logger.error("Could not retrieve account balance for symbol selection")
            return None

        available_balance = balance.available_balance
        self.logger.info(f"Determining best symbol (balance: ${available_balance:.4f} USDT)")

        # ALWAYS find the cheapest tradeable symbol - no preferred symbol logic
        result = self.find_best_tradeable_symbol(available_balance=available_balance)

        if result is None:
            return None

        symbol_config, min_order_value, current_price = result
        return (symbol_config.symbol, symbol_config.min_order_size, symbol_config)

    def find_best_tradeable_symbol(
        self,
        available_balance: Decimal,
    ) -> Optional[tuple[SymbolConfig, Decimal, Decimal]]:
        """
        Find the cheapest tradeable symbol based on available balance.

        Selection criteria:
        1. min_order_value <= available_balance
        2. Select symbol with LOWEST min order value (always cheapest)

        Args:
            available_balance: Available balance in USDT

        Returns:
            Tuple of (SymbolConfig, min_order_value_usdt, current_price) if found,
            None if no tradeable symbol
        """
        self.logger.info("Finding cheapest tradeable symbol...")

        # Get all available symbols
        all_symbols = self.client.get_all_symbols()
        if not all_symbols:
            self.logger.error("No symbols available from exchange")
            return None

        # Calculate min order value for each symbol
        tradeable_symbols: list[tuple[SymbolConfig, Decimal, Decimal]] = []
        symbol_analysis: list[str] = []

        for symbol_config in all_symbols:
            current_price = self.client.get_current_price(symbol_config.symbol)
            if current_price is None:
                symbol_analysis.append(
                    f"  - {symbol_config.symbol}: PRICE UNAVAILABLE"
                )
                continue

            min_order_value = symbol_config.min_order_size * current_price

            # Check if tradeable with current balance
            if min_order_value <= available_balance:
                tradeable_symbols.append((symbol_config, min_order_value, current_price))
                symbol_analysis.append(
                    f"  - {symbol_config.symbol}: min {symbol_config.min_order_size} "
                    f"x ${current_price:.4f} = ${min_order_value:.4f} (TRADEABLE)"
                )
            else:
                symbol_analysis.append(
                    f"  - {symbol_config.symbol}: min {symbol_config.min_order_size} "
                    f"x ${current_price:.4f} = ${min_order_value:.4f} (INSUFFICIENT BALANCE)"
                )

        # Log symbol analysis
        self.logger.info(dedent(f"""
            Symbol Analysis (balance: ${available_balance:.2f}):
        """).strip() + "\n" + "\n".join(symbol_analysis))

        if not tradeable_symbols:
            self.logger.warning(
                f"No tradeable symbols found with balance ${available_balance:.2f}. "
                f"Account needs more funds to trade."
            )
            return None

        # Sort by min order value (ascending) and pick cheapest - ALWAYS
        tradeable_symbols.sort(key=lambda x: x[1])
        best = tradeable_symbols[0]

        # Check if balance is dangerously close to min order value (< 10% buffer)
        margin_buffer_ratio = (available_balance - best[1]) / best[1]
        if margin_buffer_ratio < Decimal("0.1"):
            self.logger.warning(dedent(f"""
                WARNING: Available balance is VERY CLOSE to minimum order value!
                - Available: ${available_balance:.4f} USDT
                - Min Order Value: ${best[1]:.4f} USDT
                - Buffer: {margin_buffer_ratio * 100:.1f}%
                Exchange may still reject orders due to fees and slippage.
                Consider adding more funds (recommended: ${best[1] * Decimal("1.5"):.2f}+ USDT).
            """).strip())

        self.logger.info(dedent(f"""
            Selected cheapest symbol: {best[0].symbol}
            - Min Order Value: ${best[1]:.4f} USDT
            - Current Price: ${best[2]:.4f}
            - Available Balance: ${available_balance:.2f} USDT
        """).strip())

        return best

    def select_symbol_for_trade(self, trade: Trade) -> Optional[tuple[Trade, SymbolConfig]]:
        """
        Select the cheapest tradeable symbol for the trade.

        This method ALWAYS selects the cheapest tradeable symbol based on
        available balance. There is no "preferred" symbol concept.

        Args:
            trade: Original trade (symbol will be replaced with cheapest available)

        Returns:
            Tuple of (updated Trade, SymbolConfig) or None if no tradeable symbol
        """
        # Get current balance
        balance = self.client.get_account_balance()
        if balance is None:
            self.logger.error("Could not retrieve account balance for symbol selection")
            return None

        available_balance = balance.available_balance
        self.logger.info(f"Available balance: ${available_balance:.4f} USDT")

        # ALWAYS find the cheapest tradeable symbol
        result = self.find_best_tradeable_symbol(available_balance=available_balance)

        if result is None:
            return None

        symbol_config, min_order_value, current_price = result

        # Create new trade with selected symbol
        # Use minimum order size as the trade size (smallest possible trade)
        new_size = symbol_config.min_order_size

        new_trade = Trade(
            symbol=symbol_config.symbol,
            side=trade.side,
            order_type=trade.order_type,
            size=new_size,
            price=current_price,
            day_number=trade.day_number,
        )

        if trade.symbol != symbol_config.symbol:
            self.logger.info(dedent(f"""
                Trade symbol selected (cheapest available):
                - Original request: {trade.symbol} (size: {trade.size})
                - Selected: {new_trade.symbol} (size: {new_trade.size})
                - Trade Value: ${new_size * current_price:.4f} USDT
            """).strip())

        return (new_trade, symbol_config)

    def validate_trade(self, trade: Trade) -> tuple[bool, Optional[str]]:
        """
        Validate trade parameters before execution.

        Args:
            trade: Trade to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate symbol
        symbol_config = self.client.get_symbol_config(trade.symbol)
        if symbol_config is None:
            return False, f"Unknown symbol: {trade.symbol}"

        # Validate size
        if trade.size <= 0:
            return False, f"Trade size must be positive: {trade.size}"

        if trade.size < symbol_config.min_order_size:
            return False, (
                f"Trade size {trade.size} is below minimum "
                f"{symbol_config.min_order_size} for {trade.symbol}"
            )

        # Validate against max position size (in USDT value)
        # This allows trading low-value tokens where unit size > max_position_size
        current_price = self.client.get_current_price(trade.symbol)
        if current_price is not None:
            trade_value_usdt = trade.size * current_price
            max_value_usdt = self.config.safety.max_position_size * Decimal("100000")  # Max ~$1000 in USDT
            # Only apply max_position_size if it's configured for high-value assets
            # For low-value tokens, we rely on balance checks instead
            if current_price >= Decimal("100"):  # Only enforce for assets >= $100/unit
                if trade.size > self.config.safety.max_position_size:
                    return False, (
                        f"Trade size {trade.size} exceeds max position size "
                        f"{self.config.safety.max_position_size}"
                    )

        # Validate side
        if trade.side.upper() not in ("BUY", "SELL"):
            return False, f"Invalid side: {trade.side}"

        # Validate order type
        if trade.order_type.upper() not in ("MARKET", "LIMIT"):
            return False, f"Invalid order type: {trade.order_type}"

        # Note: Leverage validation removed - now hardcoded to 1

        return True, None

    def check_balance(self, required_margin: Decimal) -> tuple[bool, Optional[str]]:
        """
        Check if account has sufficient balance.

        Args:
            required_margin: Required margin for the trade

        Returns:
            Tuple of (has_balance, error_message)
        """
        if not self.config.safety.require_balance_check:
            return True, None

        balance = self.client.get_account_balance()
        if balance is None:
            return False, "Could not retrieve account balance"

        if balance.available_balance < self.config.safety.min_balance:
            return False, (
                f"Available balance {balance.available_balance} is below "
                f"minimum required {self.config.safety.min_balance}"
            )

        if balance.available_balance < required_margin:
            return False, (
                f"Insufficient balance. Available: {balance.available_balance}, "
                f"Required margin: {required_margin}"
            )

        return True, None

    def execute_trade(self, trade: Trade) -> TradeResult:
        """
        Execute a trade with validation and error handling.

        The bot ALWAYS selects the cheapest tradeable symbol automatically.
        There is no "preferred" symbol concept.

        Args:
            trade: Trade to execute

        Returns:
            TradeResult with execution details
        """
        # Step 0: Check circuit breaker
        can_execute, reason = self.circuit_breaker.can_execute()
        if not can_execute:
            self.logger.warning(f"Trade blocked by circuit breaker: {reason}")
            return TradeResult(
                trade=trade,
                success=False,
                error=f"Circuit breaker: {reason}",
            )

        self.logger.info("=" * 50)
        self.logger.info("Executing trade for today")
        self.logger.info(f"Requested Symbol: {trade.symbol}")
        self.logger.info(f"Side: {trade.side}")
        self.logger.info(f"Requested Size: {trade.size}")
        self.logger.info("=" * 50)

        # Step 0.5: ALWAYS select cheapest tradeable symbol
        selection_result = self.select_symbol_for_trade(trade)
        if selection_result is None:
            error = "No tradeable symbol found. Insufficient balance for any symbol."
            self.logger.error(error)
            return TradeResult(trade=trade, success=False, error=error)

        # Use selected trade (cheapest available symbol)
        original_symbol = trade.symbol
        trade, symbol_config = selection_result

        self.logger.info(f"Selected Symbol: {trade.symbol} (cheapest available)")
        self.logger.info(f"Trade Size: {trade.size}")

        # Step 1: Validate trade
        is_valid, error = self.validate_trade(trade)
        if not is_valid:
            self.logger.error(f"Trade validation failed: {error}")
            return TradeResult(trade=trade, success=False, error=error)

        # Step 2: Get current price
        current_price = self.client.get_current_price(trade.symbol)
        if current_price is None:
            error = f"Could not get current price for {trade.symbol}"
            self.logger.error(error)
            return TradeResult(trade=trade, success=False, error=error)

        self.logger.info(f"Current price: {format_price(current_price)}")

        # Step 3: Check balance (leverage is always 1)
        trade_value = trade.size * current_price / HARDCODED_LEVERAGE
        self.logger.info(f"Trade value: ${trade_value:.4f}")
        is_sufficient, error = self.check_balance(trade_value)
        if not is_sufficient:
            self.logger.error(f"Balance check failed: {error}")
            return TradeResult(trade=trade, success=False, error=error)

        # Step 4: Place opening order
        result = self._place_order_with_retry(
            trade=trade,
            price=current_price
        )

        if not result.success:
            # Record failure with circuit breaker
            self.circuit_breaker.record_failure()
            self._save_trade_result(TradeResult(
                trade=trade,
                success=False,
                error=result.error
            ))
            return TradeResult(trade=trade, success=False, error=result.error)

        self.logger.info(f"Opening order placed: {result.order_id}")
        self.logger.info(f"Filled at: {format_price(result.filled_price)}")

        trade_result = TradeResult(
            trade=trade,
            success=True,
            order_id=result.order_id,
            executed_price=result.filled_price,
            executed_size=result.filled_size,
            fees=result.fee,
        )

        # Step 5: MANDATORY - Always close position immediately
        self.logger.info("Closing position immediately (mandatory for safety)...")
        time.sleep(0.5)  # Small delay between orders

        close_result = self._close_position_with_retry(trade, result)
        if close_result.success:
            trade_result.close_order_id = close_result.order_id
            trade_result.close_price = close_result.filled_price
            trade_result.close_fees = close_result.fee
            self.logger.info(f"Position closed at: {format_price(close_result.filled_price)}")
        else:
            self.logger.critical(dedent(f"""
                CRITICAL: Failed to close position!
                - Symbol: {trade.symbol}
                - Order ID: {result.order_id}
                - Error: {close_result.error}
                Manual intervention may be required.
            """).strip())

        # Step 6: Log and save result
        self._log_trade_result(trade_result)
        self._save_trade_result(trade_result)

        # Record success with circuit breaker
        self.circuit_breaker.record_success()

        return trade_result

    def _place_order_with_retry(
        self,
        trade: Trade,
        price: Decimal
    ) -> OrderResult:
        """
        Place order with retry logic and deduplication.

        Uses client_order_id to prevent duplicate orders on retries.

        Args:
            trade: Trade to execute
            price: Current price

        Returns:
            OrderResult
        """
        max_retries = self.config.safety.max_retries
        retry_delay = self.config.safety.retry_delay
        result = None

        for attempt in range(1, max_retries + 1):
            # Generate unique client_order_id for this attempt
            client_order_id = self._generate_client_order_id(trade, attempt)

            self.logger.debug(dedent(f"""
                Trade attempt {attempt}/{max_retries}
                Client Order ID: {client_order_id}
            """).strip())

            try:
                result = self.client.place_order(
                    symbol=trade.symbol,
                    side=trade.side,
                    order_type=trade.order_type,
                    size=trade.size,
                    price=price,
                    client_order_id=client_order_id,
                )

                if result.success:
                    return result

                self.logger.warning(
                    f"Order attempt {attempt}/{max_retries} failed: {result.error}"
                )

                # Check if order actually succeeded but was reported as failed
                existing_order = self._check_existing_order(client_order_id)
                if existing_order:
                    self.logger.warning(dedent(f"""
                        Order appears to have succeeded despite error response.
                        Found existing order: {existing_order.order_id}
                    """).strip())
                    return existing_order

            except Exception as e:
                self._log_error(f"Order attempt {attempt}/{max_retries} exception", e)
                result = OrderResult(success=False, error=str(e))

            # Wait before retry (exponential backoff)
            if attempt < max_retries:
                wait_time = retry_delay * (2 ** (attempt - 1))
                self.logger.info(f"Retrying in {wait_time:.1f} seconds...")
                time.sleep(wait_time)

        return result

    def _close_position_with_retry(
        self,
        trade: Trade,
        open_result: OrderResult,
        max_retries: int = 5
    ) -> OrderResult:
        """
        Close position with aggressive retry - MUST succeed.

        Uses exponential backoff with max 30 second delay.

        Args:
            trade: Original trade
            open_result: Result of opening order
            max_retries: Maximum number of retry attempts

        Returns:
            OrderResult for close order
        """
        last_result = None

        for attempt in range(1, max_retries + 1):
            result = self._close_position(trade, open_result)
            if result.success:
                self.logger.info(f"Position closed successfully on attempt {attempt}")
                return result

            last_result = result
            wait_time = min(30, 2 ** attempt)  # 2, 4, 8, 16, 30 seconds

            self.logger.warning(dedent(f"""
                Close attempt {attempt}/{max_retries} failed.
                Error: {result.error}
                Retrying in {wait_time} seconds...
            """).strip())

            time.sleep(wait_time)

        return last_result  # Return last failed result

    def _close_position(self, trade: Trade, open_result: OrderResult) -> OrderResult:
        """
        Close an open position.

        Args:
            trade: Original trade
            open_result: Result of opening order

        Returns:
            OrderResult for close order
        """
        # Opposite side for closing
        close_side = "SELL" if trade.side.upper() == "BUY" else "BUY"

        # Get current price for close
        current_price = self.client.get_current_price(trade.symbol)
        if current_price is None:
            current_price = open_result.filled_price

        return self._place_order_with_retry(
            trade=Trade(
                symbol=trade.symbol,
                side=close_side,
                order_type="MARKET",
                size=open_result.filled_size or trade.size,
            ),
            price=current_price
        )

    def _log_trade_result(self, result: TradeResult) -> None:
        """Log trade result summary."""
        if result.success:
            self.logger.info("-" * 50)
            self.logger.info("TRADE SUCCESSFUL")
            self.logger.info(f"  Order ID: {result.order_id}")
            self.logger.info(f"  Symbol: {result.trade.symbol}")
            self.logger.info(f"  Side: {result.trade.side}")
            self.logger.info(f"  Size: {format_size(result.executed_size or result.trade.size)}")
            self.logger.info(f"  Price: {format_price(result.executed_price or Decimal(0))}")
            self.logger.info(f"  Fees: {format_price(result.total_fees)}")

            if result.close_order_id:
                self.logger.info(f"  Close Order ID: {result.close_order_id}")
                self.logger.info(f"  Close Price: {format_price(result.close_price or Decimal(0))}")
                self.logger.info(f"  P&L: {format_price(result.pnl)}")

            # Calculate trading activity factor impact
            self.logger.info("-" * 50)
            self.logger.info("Today's trading complete!")
            factor = calculate_trading_activity_factor(result.trade.day_number)
            self.logger.info(f"Trading Activity Factor: {factor:.1f}")
            self.logger.info("-" * 50)
        else:
            self.logger.error("-" * 50)
            self.logger.error("TRADE FAILED")
            self.logger.error(f"  Error: {result.error}")
            self.logger.error("-" * 50)

    def _save_trade_result(self, result: TradeResult) -> None:
        """Save trade result to file."""
        try:
            # Ensure data directory exists
            self._trade_log_file.parent.mkdir(parents=True, exist_ok=True)

            # Load existing trades
            trades = []
            if self._trade_log_file.exists():
                with open(self._trade_log_file, "r") as f:
                    trades = json.load(f)

            # Add new trade
            trades.append(result.to_dict())

            # Save back
            with open(self._trade_log_file, "w") as f:
                json.dump(trades, f, indent=2)

            self.logger.debug(f"Trade saved to {self._trade_log_file}")

        except Exception as e:
            self.logger.warning(f"Failed to save trade result: {e}")

    def get_today_trades(self) -> list[dict]:
        """Get trades executed today."""
        today = get_current_utc_time().date()

        try:
            if not self._trade_log_file.exists():
                return []

            with open(self._trade_log_file, "r") as f:
                trades = json.load(f)

            today_trades = []
            for trade in trades:
                trade_time = datetime.fromisoformat(trade["timestamp"].replace("Z", "+00:00"))
                if trade_time.date() == today:
                    today_trades.append(trade)

            return today_trades

        except Exception as e:
            self.logger.warning(f"Failed to load trades: {e}")
            return []

    def has_traded_today(self) -> bool:
        """Check if a successful trade was already executed today."""
        today_trades = self.get_today_trades()
        return any(trade["success"] for trade in today_trades)

    def get_week_trades_count(self) -> int:
        """Get count of successful trades this week."""
        from bot.utils import get_weekly_round_start

        round_start = get_weekly_round_start()

        try:
            if not self._trade_log_file.exists():
                return 0

            with open(self._trade_log_file, "r") as f:
                trades = json.load(f)

            count = 0
            for trade in trades:
                if not trade["success"]:
                    continue
                trade_time = datetime.fromisoformat(trade["timestamp"].replace("Z", "+00:00"))
                if trade_time >= round_start:
                    count += 1

            return count

        except Exception as e:
            self.logger.warning(f"Failed to count week trades: {e}")
            return 0
