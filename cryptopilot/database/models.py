"""Pydantic models for database records with strict typing and validation.

All monetary values use Decimal for precision.
"""

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ActionType(str, Enum):
    """Trading action types."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class ConfidenceLevel(str, Enum):
    """Confidence level for analysis."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TradeSide(str, Enum):
    """Trade side."""

    BUY = "BUY"
    SELL = "SELL"


class Timeframe(str, Enum):
    """Supported timeframes."""

    ONE_HOUR = "1h"
    FOUR_HOUR = "4h"
    ONE_DAY = "1d"
    ONE_WEEK = "1w"


class OutcomeType(str, Enum):
    """Strategy performance outcome."""

    WIN = "WIN"
    LOSS = "LOSS"
    NEUTRAL = "NEUTRAL"
    PENDING = "PENDING"


class SeverityLevel(str, Enum):
    """Event severity levels."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class MarketDataRecord(BaseModel):
    """Market data record."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: int | None = None
    symbol: str = Field(min_length=1, max_length=10)
    base_currency: str = Field(default="USD")
    timestamp: datetime
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)
    timeframe: Timeframe
    provider: str
    collected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        return v.upper()

    @field_validator("high")
    @classmethod
    def validate_high(cls, v: Decimal, info: Any) -> Decimal:
        if "low" in info.data and v < info.data["low"]:
            raise ValueError("High must be >= Low")
        return v


class TradeRecord(BaseModel):
    """Trade record."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: int | None = None
    trade_id: UUID = Field(default_factory=uuid4)
    symbol: str = Field(min_length=1, max_length=10)
    side: TradeSide
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(gt=0)
    fee: Decimal = Field(ge=0, default=Decimal("0"))
    total_cost: Decimal = Field(gt=0)
    timestamp: datetime
    account: str = Field(default="default", min_length=1, max_length=50)  # NEW
    notes: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        return v.upper()

    @field_validator("total_cost")
    @classmethod
    def validate_total_cost(cls, v: Decimal, info: Any) -> Decimal:
        """Validate total_cost matches quantity * price + fee."""
        if "quantity" in info.data and "price" in info.data and "fee" in info.data:
            expected = info.data["quantity"] * info.data["price"] + info.data["fee"]
            if abs(v - expected) > Decimal("0.01"):  # Allow small rounding
                raise ValueError(f"Total cost {v} does not match calculation {expected}")
        return v

class Position(BaseModel):
    """Derived position from trade history."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    symbol: str
    quantity: Decimal = Field(ge=0)
    cost_basis: Decimal = Field(gt=0)  # Average cost per unit
    total_cost: Decimal = Field(ge=0)  # Total amount invested
    account: str = Field(default="default")
    first_trade: datetime
    last_trade: datetime
    trade_count: int = Field(gt=0)


class PositionWithMarketData(Position):
    """Position enriched with current market price and P&L."""
    current_price: Decimal = Field(gt=0)
    market_value: Decimal = Field(ge=0)
    unrealized_pnl: Decimal
    unrealized_pnl_pct: Decimal
    price_updated_at: datetime

class BalanceSnapshotRecord(BaseModel):
    """Balance snapshot record."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: int | None = None
    snapshot_id: UUID = Field(default_factory=uuid4)
    symbol: str = Field(min_length=1, max_length=10)
    quantity: Decimal = Field(ge=0)
    cost_basis: Decimal | None = Field(default=None, gt=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    notes: str | None = None

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        return v.upper()


class AnalysisResultRecord(BaseModel):
    """Analysis result record."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: int | None = None
    analysis_id: UUID = Field(default_factory=uuid4)
    symbol: str = Field(min_length=1, max_length=10)
    strategy: str
    action: ActionType
    confidence: ConfidenceLevel
    confidence_score: Decimal = Field(ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)
    risk_assessment: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    market_context: dict[str, Any] | None = None

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v: str) -> str:
        return v.upper()


class StrategyPerformanceRecord(BaseModel):
    """Strategy performance tracking record."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: int | None = None
    strategy: str
    symbol: str
    analysis_id: UUID
    recommendation_timestamp: datetime
    evaluation_timestamp: datetime | None = None
    outcome: OutcomeType = OutcomeType.PENDING
    actual_return: Decimal | None = None
    notes: str | None = None


class DataQualityLogRecord(BaseModel):
    """Data quality log record."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: int | None = None
    check_type: str
    symbol: str | None = None
    timeframe: Timeframe | None = None
    issues_found: int = 0
    details: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SystemEventRecord(BaseModel):
    """System event log record."""

    id: int | None = None
    event_type: str
    severity: SeverityLevel
    message: str
    details: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
