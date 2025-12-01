"""Trend following strategy using SMA crossover.

Classic dual moving average crossover:
- BUY signal: Fast SMA crosses above Slow SMA (golden cross)
- SELL signal: Fast SMA crosses below Slow SMA (death cross)
- HOLD: No recent crossover or trend unclear

Confidence is based on:
- Strength of separation between SMAs
- Volume confirmation
- Recent trend consistency
"""

from decimal import Decimal

import pandas as pd

from cryptopilot.analysis.indicators import (
    calculate_sma,
    calculate_volatility,
    detect_crossover,
)
from cryptopilot.analysis.strategies.base import AnalysisResult, StrategyBase
from cryptopilot.database.models import ActionType


class TrendFollowingStrategy(StrategyBase):
    """Dual SMA crossover strategy.

    Args:
        fast_period: Fast SMA period (default: 50)
        slow_period: Slow SMA period (default: 200)
        crossover_lookback: Periods to check for crossover (default: 5)
    """

    def __init__(
        self,
        fast_period: int = 50,
        slow_period: int = 200,
        crossover_lookback: int = 5,
    ) -> None:
        super().__init__(name="trend_following")
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.crossover_lookback = crossover_lookback

    def get_required_periods(self) -> int:
        """Need enough data for slow SMA plus crossover lookback."""
        return self.slow_period + self.crossover_lookback

    def analyze(self, data: pd.DataFrame) -> AnalysisResult:
        """Analyze trend using SMA crossover.

        Args:
            data: OHLCV DataFrame

        Returns:
            AnalysisResult with BUY/SELL/HOLD recommendation
        """
        self.validate_data(data)

        # Calculate indicators
        close = data["close"]
        volume = data["volume"]

        fast_sma = calculate_sma(close, self.fast_period)
        slow_sma = calculate_sma(close, self.slow_period)
        volatility = calculate_volatility(close, period=20)

        # Current values
        current_price = float(close.iloc[-1])
        current_fast = float(fast_sma.iloc[-1])
        current_slow = float(slow_sma.iloc[-1])
        current_vol = float(volatility.iloc[-1]) if not pd.isna(volatility.iloc[-1]) else 0.0

        # Detect crossover
        crossover = detect_crossover(fast_sma, slow_sma, self.crossover_lookback)

        # Calculate separation percentage
        separation_pct = abs((current_fast - current_slow) / current_slow * 100)

        # Volume analysis (compare recent to average)
        avg_volume = float(volume.tail(20).mean())
        recent_volume = float(volume.tail(5).mean())
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0

        # Decision logic
        evidence: list[str] = []
        action: ActionType
        confidence_score: Decimal

        if crossover == "bullish":
            action = ActionType.BUY
            evidence.append(
                f"Golden cross: Fast SMA ({self.fast_period}) crossed above "
                f"Slow SMA ({self.slow_period})"
            )
            evidence.append(f"Current price: ${current_price:.2f}")
            evidence.append(f"Fast SMA: ${current_fast:.2f}, Slow SMA: ${current_slow:.2f}")

            # Higher confidence if volume confirms
            if volume_ratio > 1.2:
                evidence.append(f"Volume confirming: {volume_ratio:.1f}x average")
                base_confidence = Decimal("0.75")
            else:
                evidence.append(f"Volume neutral: {volume_ratio:.1f}x average")
                base_confidence = Decimal("0.65")

            # Adjust for separation strength
            sep_boost = min(Decimal(str(separation_pct / 100)), Decimal("0.15"))
            confidence_score = min(base_confidence + sep_boost, Decimal("0.95"))

        elif crossover == "bearish":
            action = ActionType.SELL
            evidence.append(
                f"Death cross: Fast SMA ({self.fast_period}) crossed below "
                f"Slow SMA ({self.slow_period})"
            )
            evidence.append(f"Current price: ${current_price:.2f}")
            evidence.append(f"Fast SMA: ${current_fast:.2f}, Slow SMA: ${current_slow:.2f}")

            if volume_ratio > 1.2:
                evidence.append(f"Volume confirming: {volume_ratio:.1f}x average")
                base_confidence = Decimal("0.75")
            else:
                evidence.append(f"Volume neutral: {volume_ratio:.1f}x average")
                base_confidence = Decimal("0.65")

            sep_boost = min(Decimal(str(separation_pct / 100)), Decimal("0.15"))
            confidence_score = min(base_confidence + sep_boost, Decimal("0.95"))

        else:
            # No recent crossover - check current position
            if current_fast > current_slow:
                # In uptrend but no recent signal
                action = ActionType.HOLD
                evidence.append(
                    f"Uptrend: Fast SMA (${current_fast:.2f}) above Slow SMA (${current_slow:.2f})"
                )
                evidence.append(f"Separation: {separation_pct:.1f}%")
                evidence.append("No recent crossover - holding pattern")

                # Higher confidence for stronger trends
                if separation_pct > 5:
                    confidence_score = Decimal("0.70")
                    evidence.append("Strong uptrend continuation")
                else:
                    confidence_score = Decimal("0.50")
                    evidence.append("Weak uptrend - monitor closely")

            else:
                # In downtrend but no recent signal
                action = ActionType.HOLD
                evidence.append(
                    f"Downtrend: Fast SMA (${current_fast:.2f}) below "
                    f"Slow SMA (${current_slow:.2f})"
                )
                evidence.append(f"Separation: {separation_pct:.1f}%")
                evidence.append("No recent crossover - holding pattern")

                if separation_pct > 5:
                    confidence_score = Decimal("0.70")
                    evidence.append("Strong downtrend continuation")
                else:
                    confidence_score = Decimal("0.50")
                    evidence.append("Weak downtrend - monitor closely")

        # Risk assessment
        risk_assessment = {
            "volatility": Decimal(str(current_vol)),
            "separation_pct": Decimal(str(separation_pct)),
            "volume_ratio": Decimal(str(volume_ratio)),
        }

        # Market context
        market_context = {
            "current_price": Decimal(str(current_price)),
            "fast_sma": Decimal(str(current_fast)),
            "slow_sma": Decimal(str(current_slow)),
            "trend": "up" if current_fast > current_slow else "down",
        }

        confidence_level = self.calculate_confidence_level(confidence_score)

        return AnalysisResult(
            action=action,
            confidence=confidence_level,
            confidence_score=confidence_score,
            evidence=evidence,
            risk_assessment=risk_assessment,
            market_context=market_context,
        )
