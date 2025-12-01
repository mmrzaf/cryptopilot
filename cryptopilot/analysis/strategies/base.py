"""Base class for all analysis strategies.

All strategies must implement the analyze() method and return
consistent AnalysisResult objects.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from cryptopilot.database.models import ActionType, ConfidenceLevel


@dataclass
class AnalysisResult:
    """Standardized output from all strategies.

    This ensures all strategies return consistent, comparable results.
    """

    action: ActionType
    confidence: ConfidenceLevel
    confidence_score: Decimal  # 0.0 - 1.0
    evidence: list[str]  # Human-readable reasons for the recommendation
    risk_assessment: dict[str, Decimal | str] | None = None
    market_context: dict[str, Decimal | str] | None = None

    def __post_init__(self) -> None:
        """Validate confidence score."""
        if not (Decimal("0") <= self.confidence_score <= Decimal("1")):
            raise ValueError(f"Confidence score must be 0-1, got {self.confidence_score}")


class StrategyBase(ABC):
    """Abstract base class for all trading strategies.

    Each strategy analyzes market data and produces actionable signals
    with evidence and confidence levels.
    """

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def get_required_periods(self) -> int:
        """Return minimum number of candles needed for analysis.

        Returns:
            Minimum candles required (e.g., 200 for 200-day SMA)
        """
        pass

    @abstractmethod
    def analyze(self, data: pd.DataFrame) -> AnalysisResult:
        """Analyze market data and produce a trading signal.

        Args:
            data: DataFrame with OHLCV data (columns: timestamp, open, high, low, close, volume)
                  Must be sorted by timestamp ascending
                  Must have at least get_required_periods() rows

        Returns:
            AnalysisResult with action, confidence, and supporting evidence

        Raises:
            ValueError: If data is insufficient or invalid
        """
        pass

    def validate_data(self, data: pd.DataFrame) -> None:
        """Validate input DataFrame has required structure.

        Args:
            data: DataFrame to validate

        Raises:
            ValueError: If data is invalid
        """
        required_cols = {"timestamp", "open", "high", "low", "close", "volume"}
        missing = required_cols - set(data.columns)

        if missing:
            raise ValueError(f"DataFrame missing required columns: {missing}")

        min_periods = self.get_required_periods()
        if len(data) < min_periods:
            raise ValueError(f"{self.name} requires {min_periods} candles, got {len(data)}")

        # Check for NaN in critical columns
        critical_cols = ["close"]
        for col in critical_cols:
            if data[col].isna().any():
                raise ValueError(f"Column '{col}' contains NaN values. Run data integrity checks.")

    def calculate_confidence_level(self, score: Decimal) -> ConfidenceLevel:
        """Map confidence score to confidence level.

        Args:
            score: Decimal between 0 and 1

        Returns:
            HIGH (>0.7), MEDIUM (0.4-0.7), or LOW (<0.4)
        """
        if score >= Decimal("0.7"):
            return ConfidenceLevel.HIGH
        elif score >= Decimal("0.4"):
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
