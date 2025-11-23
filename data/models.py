"""
Data Models for ApexOmni Trading Bot.

This module defines the core data structures used throughout the trading bot
for representing trades, results, and related entities.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    """Trade side enumeration."""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order type enumeration."""
    MARKET = "market"
    LIMIT = "limit"


class TradeStatus(str, Enum):
    """Trade execution status enumeration."""
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Trade:
    """
    Represents a trade to be executed on ApexOmni.

    This is the input model for trade execution, containing all parameters
    needed to place an order on the exchange.

    Attributes:
        symbol: Trading pair symbol (e.g., "BTC-USDT")
        side: Order side - "buy" or "sell"
        size: Trade size in base currency
        price: Limit price (required even for market orders on zkLink)
        order_type: Order type - "market" or "limit"
        leverage: Position leverage (1-100, default 1 for safety)
        day_number: Day number in the weekly trading cycle (1-5)
    """
    symbol: str
    side: str
    size: float
    price: float
    order_type: str = "market"
    leverage: int = 1
    day_number: int = 1

    def __post_init__(self):
        """Validate trade parameters after initialization."""
        # Normalize side to lowercase
        self.side = self.side.lower()
        self.order_type = self.order_type.lower()

        # Validate side
        if self.side not in [OrderSide.BUY.value, OrderSide.SELL.value]:
            raise ValueError(f"Invalid side: {self.side}. Must be 'buy' or 'sell'.")

        # Validate order type
        if self.order_type not in [OrderType.MARKET.value, OrderType.LIMIT.value]:
            raise ValueError(f"Invalid order_type: {self.order_type}. Must be 'market' or 'limit'.")

        # Validate size
        if self.size <= 0:
            raise ValueError(f"Size must be positive, got: {self.size}")

        # Validate price
        if self.price <= 0:
            raise ValueError(f"Price must be positive, got: {self.price}")

        # Validate leverage
        if not 1 <= self.leverage <= 100:
            raise ValueError(f"Leverage must be between 1 and 100, got: {self.leverage}")

        # Validate day_number
        if not 1 <= self.day_number <= 5:
            raise ValueError(f"Day number must be between 1 and 5, got: {self.day_number}")

    def to_dict(self) -> dict:
        """Convert trade to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "side": self.side,
            "size": self.size,
            "price": self.price,
            "order_type": self.order_type,
            "leverage": self.leverage,
            "day_number": self.day_number,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Trade":
        """Create Trade from dictionary."""
        return cls(
            symbol=data["symbol"],
            side=data["side"],
            size=data["size"],
            price=data["price"],
            order_type=data.get("order_type", "market"),
            leverage=data.get("leverage", 1),
            day_number=data.get("day_number", 1),
        )


@dataclass
class TradeResult:
    """
    Represents the result of an executed trade.

    This is the output model after trade execution, containing the outcome
    and all relevant execution details.

    Attributes:
        trade: The original Trade that was executed
        success: Whether the trade was successfully executed
        order_id: Exchange order ID (None if failed)
        executed_price: Actual fill price (None if failed)
        executed_size: Actual fill size (None if failed)
        fees: Trading fees paid
        timestamp: When the trade was executed
        error: Error message if trade failed (None if success)
        status: Detailed trade status
    """
    trade: Trade
    success: bool
    order_id: Optional[str] = None
    executed_price: Optional[float] = None
    executed_size: Optional[float] = None
    fees: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None
    status: TradeStatus = TradeStatus.PENDING

    def __post_init__(self):
        """Set status based on success flag if not explicitly set."""
        if self.success and self.status == TradeStatus.PENDING:
            self.status = TradeStatus.FILLED
        elif not self.success and self.status == TradeStatus.PENDING:
            self.status = TradeStatus.FAILED

    @property
    def is_filled(self) -> bool:
        """Check if trade was fully filled."""
        return self.status == TradeStatus.FILLED

    @property
    def is_partial(self) -> bool:
        """Check if trade was partially filled."""
        return self.status == TradeStatus.PARTIAL

    @property
    def executed_value(self) -> float:
        """Calculate the total executed value (price * size)."""
        if self.executed_price and self.executed_size:
            return self.executed_price * self.executed_size
        return 0.0

    @property
    def slippage(self) -> Optional[float]:
        """Calculate slippage as percentage difference from expected price."""
        if self.executed_price and self.trade.price:
            return ((self.executed_price - self.trade.price) / self.trade.price) * 100
        return None

    def to_dict(self) -> dict:
        """Convert trade result to dictionary for serialization."""
        return {
            "trade": self.trade.to_dict(),
            "success": self.success,
            "order_id": self.order_id,
            "executed_price": self.executed_price,
            "executed_size": self.executed_size,
            "fees": self.fees,
            "timestamp": self.timestamp.isoformat(),
            "error": self.error,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TradeResult":
        """Create TradeResult from dictionary."""
        return cls(
            trade=Trade.from_dict(data["trade"]),
            success=data["success"],
            order_id=data.get("order_id"),
            executed_price=data.get("executed_price"),
            executed_size=data.get("executed_size"),
            fees=data.get("fees", 0.0),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            error=data.get("error"),
            status=TradeStatus(data.get("status", "pending")),
        )


@dataclass
class WeeklyTradeRecord:
    """
    Aggregated weekly trading record for staking factor calculation.

    Tracks all trades within a weekly staking period (Monday 8AM UTC to Monday 8AM UTC).

    Attributes:
        week_start: Start of the weekly period (Monday 8AM UTC)
        week_end: End of the weekly period (next Monday 8AM UTC)
        trades: List of trade results for the week
        days_traded: Set of unique days traded (0-6, Monday=0)
    """
    week_start: datetime
    week_end: datetime
    trades: list = field(default_factory=list)
    days_traded: set = field(default_factory=set)

    @property
    def num_days_traded(self) -> int:
        """Get the number of unique days traded this week."""
        return len(self.days_traded)

    @property
    def trading_activity_factor(self) -> float:
        """
        Calculate the Trading Activity Factor for this week.

        Formula: 0.1 * days_traded (max 0.5)
        """
        return min(0.1 * self.num_days_traded, 0.5)

    @property
    def total_volume(self) -> float:
        """Calculate total traded volume for the week."""
        return sum(
            t.executed_value for t in self.trades
            if t.success and t.executed_value
        )

    @property
    def total_fees(self) -> float:
        """Calculate total fees paid for the week."""
        return sum(t.fees for t in self.trades if t.success)

    @property
    def success_count(self) -> int:
        """Count successful trades."""
        return sum(1 for t in self.trades if t.success)

    @property
    def failure_count(self) -> int:
        """Count failed trades."""
        return sum(1 for t in self.trades if not t.success)

    def add_trade(self, trade_result: TradeResult) -> None:
        """
        Add a trade result to the weekly record.

        Args:
            trade_result: The trade result to add
        """
        self.trades.append(trade_result)
        if trade_result.success:
            # Track the day of week (0=Monday, 6=Sunday)
            day_of_week = trade_result.timestamp.weekday()
            self.days_traded.add(day_of_week)

    def to_dict(self) -> dict:
        """Convert weekly record to dictionary for serialization."""
        return {
            "week_start": self.week_start.isoformat(),
            "week_end": self.week_end.isoformat(),
            "trades": [t.to_dict() for t in self.trades],
            "days_traded": list(self.days_traded),
            "num_days_traded": self.num_days_traded,
            "trading_activity_factor": self.trading_activity_factor,
            "total_volume": self.total_volume,
            "total_fees": self.total_fees,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WeeklyTradeRecord":
        """Create WeeklyTradeRecord from dictionary."""
        record = cls(
            week_start=datetime.fromisoformat(data["week_start"]),
            week_end=datetime.fromisoformat(data["week_end"]),
            trades=[TradeResult.from_dict(t) for t in data.get("trades", [])],
            days_traded=set(data.get("days_traded", [])),
        )
        return record


@dataclass
class StakingInfo:
    """
    User's staking information for multiplier calculations.

    Attributes:
        staked_amount: Amount of APEX staked
        lock_months: Lock-up period in months (0 for no lock)
        start_date: When staking began
    """
    staked_amount: float
    lock_months: int = 0
    start_date: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        """Validate staking parameters."""
        if self.staked_amount < 0:
            raise ValueError(f"Staked amount cannot be negative: {self.staked_amount}")
        if self.lock_months < 0:
            raise ValueError(f"Lock months cannot be negative: {self.lock_months}")

    @property
    def time_factor(self) -> float:
        """
        Calculate the Time Factor based on lock-up period.

        Formula: Lock-Up Period (Months) / 12
        """
        return self.lock_months / 12

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "staked_amount": self.staked_amount,
            "lock_months": self.lock_months,
            "start_date": self.start_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StakingInfo":
        """Create StakingInfo from dictionary."""
        return cls(
            staked_amount=data["staked_amount"],
            lock_months=data.get("lock_months", 0),
            start_date=datetime.fromisoformat(data.get("start_date", datetime.utcnow().isoformat())),
        )
