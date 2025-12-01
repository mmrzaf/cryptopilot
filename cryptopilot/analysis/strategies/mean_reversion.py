"""Mean reversion strategy using RSI and Bollinger Bands.

Core concept: Markets tend to revert to their mean after extreme moves.

Signals:
- BUY: Price oversold (RSI < 30) and near lower Bollinger Band
- SELL: Price overbought (RSI > 70) and near upper Bollinger Band
- HOLD: Price in normal range

Confidence based on:
- RSI extremity (further from 50 = higher confidence)
- Bollinger Band position (closer to band = higher confidence)
- Volume confirmation
- Recent volatility
"""

from decimal import Decimal

import pandas as pd

from cryptopilot.analysis.indicators import (
    calculate_bollinger_bands,
    calculate_rsi,
    calculate_volatility,
)
from cryptopilot.analysis.strategies.base import AnalysisResult, StrategyBase
from cryptopilot.database.models import ActionType


class MeanReversionStrategy(StrategyBase):
    """RSI + Bollinger Bands mean reversion strategy.

    Args:
        rsi_period: RSI calculation period (default: 14)
        rsi_oversold: RSI oversold threshold (default: 30)
        rsi_overbought: RSI overbought threshold (default: 70)
        bb_period: Bollinger Bands period (default: 20)
        bb_std: Bollinger Bands standard deviations (default: 2.0)
    """

    def __init__(
        self,
        rsi_period: int = 14,
        rsi_oversold: int = 30,
        rsi_overbought: int = 70,
        bb_period: int = 20,
        bb_std: float = 2.0,
    ) -> None:
        super().__init__(name="mean_reversion")
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.bb_period = bb_period
        self.bb_std = bb_std

    def get_required_periods(self) -> int:
        """Need enough data for RSI and Bollinger Bands."""
        return max(self.rsi_period, self.bb_period) + 20

    def analyze(self, data: pd.DataFrame) -> AnalysisResult:
        """Analyze using RSI and Bollinger Bands.

        Args:
            data: OHLCV DataFrame

        Returns:
            AnalysisResult with BUY/SELL/HOLD recommendation
        """
        self.validate_data(data)

        # Calculate indicators
        close = data["close"]
        volume = data["volume"]

        rsi = calculate_rsi(close, self.rsi_period)
        upper_bb, middle_bb, lower_bb = calculate_bollinger_bands(
            close, self.bb_period, self.bb_std
        )
        volatility = calculate_volatility(close, period=20)

        # Current values
        current_price = float(close.iloc[-1])
        current_rsi = float(rsi.iloc[-1])
        current_upper_bb = float(upper_bb.iloc[-1])
        current_middle_bb = float(middle_bb.iloc[-1])
        current_lower_bb = float(lower_bb.iloc[-1])
        current_vol = float(volatility.iloc[-1]) if not pd.isna(volatility.iloc[-1]) else 0.0

        # Calculate position within Bollinger Bands (0 = lower, 1 = upper)
        bb_range = current_upper_bb - current_lower_bb
        if bb_range > 0:
            bb_position = (current_price - current_lower_bb) / bb_range
        else:
            bb_position = 0.5

        # Volume analysis
        avg_volume = float(volume.tail(20).mean())
        recent_volume = float(volume.tail(5).mean())
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0

        # Calculate band width (volatility indicator)
        band_width_pct = (bb_range / current_middle_bb) * 100 if current_middle_bb > 0 else 0

        # Decision logic
        evidence: list[str] = []
        action: ActionType
        confidence_score: Decimal

        # OVERSOLD - BUY signal
        if current_rsi < self.rsi_oversold and bb_position < 0.2:
            action = ActionType.BUY
            evidence.append(f"Oversold: RSI at {current_rsi:.1f} (threshold: {self.rsi_oversold})")
            evidence.append(
                f"Price near lower Bollinger Band: ${current_price:.2f} "
                f"(band: ${current_lower_bb:.2f})"
            )
            evidence.append(f"Band position: {bb_position * 100:.1f}% of range")

            # Calculate confidence
            # More oversold = higher confidence
            rsi_extremity = (self.rsi_oversold - current_rsi) / self.rsi_oversold
            rsi_boost = min(Decimal(str(rsi_extremity * 0.3)), Decimal("0.3"))

            # Closer to band = higher confidence
            bb_boost = Decimal(str((0.2 - bb_position) * 0.2))

            base_confidence = Decimal("0.65")

            # Volume confirmation adds confidence
            if volume_ratio > 1.3:
                evidence.append(f"High volume confirming: {volume_ratio:.1f}x average")
                volume_boost = Decimal("0.1")
            else:
                evidence.append(f"Volume: {volume_ratio:.1f}x average")
                volume_boost = Decimal("0")

            confidence_score = min(
                base_confidence + rsi_boost + bb_boost + volume_boost, Decimal("0.95")
            )

            # Risk warning if volatility is high
            if band_width_pct > 10:
                evidence.append(f"⚠ High volatility: Band width {band_width_pct:.1f}%")

        # OVERBOUGHT - SELL signal
        elif current_rsi > self.rsi_overbought and bb_position > 0.8:
            action = ActionType.SELL
            evidence.append(
                f"Overbought: RSI at {current_rsi:.1f} (threshold: {self.rsi_overbought})"
            )
            evidence.append(
                f"Price near upper Bollinger Band: ${current_price:.2f} "
                f"(band: ${current_upper_bb:.2f})"
            )
            evidence.append(f"Band position: {bb_position * 100:.1f}% of range")

            # Calculate confidence
            rsi_extremity = (current_rsi - self.rsi_overbought) / (100 - self.rsi_overbought)
            rsi_boost = min(Decimal(str(rsi_extremity * 0.3)), Decimal("0.3"))

            bb_boost = Decimal(str((bb_position - 0.8) * 0.2))

            base_confidence = Decimal("0.65")

            if volume_ratio > 1.3:
                evidence.append(f"High volume confirming: {volume_ratio:.1f}x average")
                volume_boost = Decimal("0.1")
            else:
                evidence.append(f"Volume: {volume_ratio:.1f}x average")
                volume_boost = Decimal("0")

            confidence_score = min(
                base_confidence + rsi_boost + bb_boost + volume_boost, Decimal("0.95")
            )

            if band_width_pct > 10:
                evidence.append(f"⚠ High volatility: Band width {band_width_pct:.1f}%")

        # Potential reversal zones (lower confidence)
        elif current_rsi < 40 and bb_position < 0.3:
            action = ActionType.BUY
            evidence.append(
                f"Weak oversold signal: RSI {current_rsi:.1f}, BB position {bb_position * 100:.1f}%"
            )
            evidence.append(f"Current price: ${current_price:.2f}")
            evidence.append(f"Middle band (mean): ${current_middle_bb:.2f}")
            evidence.append("Price below mean - potential reversal zone")

            confidence_score = Decimal("0.45")

        elif current_rsi > 60 and bb_position > 0.7:
            action = ActionType.SELL
            evidence.append(
                f"Weak overbought signal: RSI {current_rsi:.1f}, "
                f"BB position {bb_position * 100:.1f}%"
            )
            evidence.append(f"Current price: ${current_price:.2f}")
            evidence.append(f"Middle band (mean): ${current_middle_bb:.2f}")
            evidence.append("Price above mean - potential reversal zone")

            confidence_score = Decimal("0.45")

        # HOLD - normal range
        else:
            action = ActionType.HOLD
            evidence.append(
                f"RSI in normal range: {current_rsi:.1f} "
                f"({self.rsi_oversold}-{self.rsi_overbought})"
            )
            evidence.append(f"Price within Bollinger Bands: ${current_price:.2f}")
            evidence.append(
                f"Band position: {bb_position * 100:.1f}% "
                f"(lower: ${current_lower_bb:.2f}, upper: ${current_upper_bb:.2f})"
            )
            evidence.append("No clear mean reversion signal")

            # Distance from mean affects confidence
            distance_from_mean = abs(bb_position - 0.5)
            if distance_from_mean < 0.15:
                evidence.append("Price very close to mean - stable")
                confidence_score = Decimal("0.60")
            else:
                evidence.append("Monitor for breakout or reversal")
                confidence_score = Decimal("0.50")

        # Risk assessment
        risk_assessment = {
            "rsi": Decimal(str(current_rsi)),
            "bb_position": Decimal(str(bb_position)),
            "volatility": Decimal(str(current_vol)),
            "band_width_pct": Decimal(str(band_width_pct)),
            "volume_ratio": Decimal(str(volume_ratio)),
        }

        # Market context
        market_context = {
            "current_price": Decimal(str(current_price)),
            "upper_bb": Decimal(str(current_upper_bb)),
            "middle_bb": Decimal(str(current_middle_bb)),
            "lower_bb": Decimal(str(current_lower_bb)),
            "rsi": Decimal(str(current_rsi)),
            "mean_reversion_zone": "oversold"
            if current_rsi < 40
            else "overbought"
            if current_rsi > 60
            else "neutral",
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
