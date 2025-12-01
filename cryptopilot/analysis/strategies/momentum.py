"""Momentum strategy using MACD and price momentum.

Core concept: Trend is your friend - ride strong momentum.

Signals:
- BUY: MACD bullish crossover + positive momentum + strong volume
- SELL: MACD bearish crossover + negative momentum + strong volume
- HOLD: Mixed signals or weak momentum

Confidence based on:
- MACD histogram strength
- Price momentum magnitude
- Volume confirmation
- Trend consistency
"""

from decimal import Decimal

import pandas as pd

from cryptopilot.analysis.indicators import (
    calculate_ema,
    calculate_macd,
    calculate_volatility,
    detect_crossover,
)
from cryptopilot.analysis.strategies.base import AnalysisResult, StrategyBase
from cryptopilot.database.models import ActionType


class MomentumStrategy(StrategyBase):
    """MACD-based momentum strategy.

    Args:
        macd_fast: MACD fast EMA period (default: 12)
        macd_slow: MACD slow EMA period (default: 26)
        macd_signal: MACD signal line period (default: 9)
        momentum_period: Price momentum lookback (default: 20)
        crossover_lookback: Periods to check for MACD crossover (default: 5)
    """

    def __init__(
        self,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        momentum_period: int = 20,
        crossover_lookback: int = 5,
    ) -> None:
        super().__init__(name="momentum")
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.momentum_period = momentum_period
        self.crossover_lookback = crossover_lookback

    def get_required_periods(self) -> int:
        """Need enough data for MACD + momentum calculation."""
        return max(self.macd_slow, self.momentum_period) + self.macd_signal + 20

    def analyze(self, data: pd.DataFrame) -> AnalysisResult:
        """Analyze using MACD and price momentum.

        Args:
            data: OHLCV DataFrame

        Returns:
            AnalysisResult with BUY/SELL/HOLD recommendation
        """
        self.validate_data(data)

        # Calculate indicators
        close = data["close"]
        volume = data["volume"]

        macd_line, signal_line, histogram = calculate_macd(
            close, self.macd_fast, self.macd_slow, self.macd_signal
        )
        ema_fast = calculate_ema(close, self.macd_fast)
        ema_slow = calculate_ema(close, self.macd_slow)
        volatility = calculate_volatility(close, period=20)

        # Price momentum (rate of change)
        price_momentum = close.pct_change(self.momentum_period) * 100

        # Current values
        current_price = float(close.iloc[-1])
        current_macd = float(macd_line.iloc[-1])
        current_signal = float(signal_line.iloc[-1])
        current_histogram = float(histogram.iloc[-1])
        current_momentum = (
            float(price_momentum.iloc[-1]) if not pd.isna(price_momentum.iloc[-1]) else 0.0
        )
        current_ema_fast = float(ema_fast.iloc[-1])
        current_ema_slow = float(ema_slow.iloc[-1])
        current_vol = float(volatility.iloc[-1]) if not pd.isna(volatility.iloc[-1]) else 0.0

        # Detect MACD crossover
        crossover = detect_crossover(macd_line, signal_line, self.crossover_lookback)

        # Volume analysis
        avg_volume = float(volume.tail(20).mean())
        recent_volume = float(volume.tail(5).mean())
        volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0

        # Histogram trend (is momentum strengthening?)
        hist_values = histogram.tail(5).values
        histogram_trend = (
            "strengthening"
            if len(hist_values) >= 2 and abs(hist_values[-1]) > abs(hist_values[-2])
            else "weakening"
        )

        # Calculate momentum strength (0-100 scale)
        momentum_strength = min(abs(current_momentum), 50) / 50 * 100

        # Decision logic
        evidence: list[str] = []
        action: ActionType
        confidence_score: Decimal

        # BULLISH MOMENTUM - BUY
        if crossover == "bullish" and current_momentum > 0:
            action = ActionType.BUY
            evidence.append(
                f"MACD bullish crossover: MACD ({current_macd:.4f}) crossed above "
                f"Signal ({current_signal:.4f})"
            )
            evidence.append(
                f"Positive momentum: Price up {current_momentum:.1f}% over {self.momentum_period} periods"
            )
            evidence.append(f"Current price: ${current_price:.2f}")
            evidence.append(
                f"MACD histogram: {current_histogram:.4f} ({'strengthening' if histogram_trend == 'strengthening' else 'weakening'})"
            )

            # Base confidence from strong crossover
            base_confidence = Decimal("0.70")

            # Boost from momentum strength
            momentum_boost = min(Decimal(str(momentum_strength / 100 * 0.15)), Decimal("0.15"))

            # Volume confirmation
            if volume_ratio > 1.3:
                evidence.append(f"Strong volume confirming: {volume_ratio:.1f}x average")
                volume_boost = Decimal("0.1")
            elif volume_ratio > 1.0:
                evidence.append(f"Volume confirming: {volume_ratio:.1f}x average")
                volume_boost = Decimal("0.05")
            else:
                evidence.append(f"Weak volume: {volume_ratio:.1f}x average")
                volume_boost = Decimal("0")

            # Histogram strengthening adds confidence
            if histogram_trend == "strengthening":
                evidence.append("Momentum accelerating")
                hist_boost = Decimal("0.05")
            else:
                hist_boost = Decimal("0")

            confidence_score = min(
                base_confidence + momentum_boost + volume_boost + hist_boost, Decimal("0.95")
            )

        # BEARISH MOMENTUM - SELL
        elif crossover == "bearish" and current_momentum < 0:
            action = ActionType.SELL
            evidence.append(
                f"MACD bearish crossover: MACD ({current_macd:.4f}) crossed below "
                f"Signal ({current_signal:.4f})"
            )
            evidence.append(
                f"Negative momentum: Price down {abs(current_momentum):.1f}% over {self.momentum_period} periods"
            )
            evidence.append(f"Current price: ${current_price:.2f}")
            evidence.append(
                f"MACD histogram: {current_histogram:.4f} ({'strengthening' if histogram_trend == 'strengthening' else 'weakening'})"
            )

            base_confidence = Decimal("0.70")
            momentum_boost = min(Decimal(str(momentum_strength / 100 * 0.15)), Decimal("0.15"))

            if volume_ratio > 1.3:
                evidence.append(f"Strong volume confirming: {volume_ratio:.1f}x average")
                volume_boost = Decimal("0.1")
            elif volume_ratio > 1.0:
                evidence.append(f"Volume confirming: {volume_ratio:.1f}x average")
                volume_boost = Decimal("0.05")
            else:
                evidence.append(f"Weak volume: {volume_ratio:.1f}x average")
                volume_boost = Decimal("0")

            if histogram_trend == "strengthening":
                evidence.append("Downward momentum accelerating")
                hist_boost = Decimal("0.05")
            else:
                hist_boost = Decimal("0")

            confidence_score = min(
                base_confidence + momentum_boost + volume_boost + hist_boost, Decimal("0.95")
            )

        # Crossover without momentum confirmation (lower confidence)
        elif crossover == "bullish":
            action = ActionType.BUY
            evidence.append(f"MACD bullish crossover but weak momentum: {current_momentum:.1f}%")
            evidence.append(f"Current price: ${current_price:.2f}")
            evidence.append("⚠ Momentum not confirming - proceed with caution")
            confidence_score = Decimal("0.50")

        elif crossover == "bearish":
            action = ActionType.SELL
            evidence.append(f"MACD bearish crossover but weak momentum: {current_momentum:.1f}%")
            evidence.append(f"Current price: ${current_price:.2f}")
            evidence.append("⚠ Momentum not confirming - proceed with caution")
            confidence_score = Decimal("0.50")

        # Strong momentum without recent crossover
        elif abs(current_momentum) > 10 and current_macd > current_signal and current_momentum > 0:
            action = ActionType.HOLD
            evidence.append(
                f"Strong upward momentum: {current_momentum:.1f}% over {self.momentum_period} periods"
            )
            evidence.append(f"MACD above signal: {current_macd:.4f} > {current_signal:.4f}")
            evidence.append(f"Current price: ${current_price:.2f}")
            evidence.append("Riding existing momentum - no new entry signal")
            confidence_score = Decimal("0.65")

        elif abs(current_momentum) > 10 and current_macd < current_signal and current_momentum < 0:
            action = ActionType.HOLD
            evidence.append(
                f"Strong downward momentum: {abs(current_momentum):.1f}% over {self.momentum_period} periods"
            )
            evidence.append(f"MACD below signal: {current_macd:.4f} < {current_signal:.4f}")
            evidence.append(f"Current price: ${current_price:.2f}")
            evidence.append("In downtrend - wait for reversal signal")
            confidence_score = Decimal("0.65")

        # HOLD - no clear momentum
        else:
            action = ActionType.HOLD
            evidence.append(
                f"Weak momentum: {current_momentum:.1f}% over {self.momentum_period} periods"
            )
            evidence.append(
                f"MACD: {current_macd:.4f}, Signal: {current_signal:.4f}, "
                f"Histogram: {current_histogram:.4f}"
            )
            evidence.append(f"Current price: ${current_price:.2f}")

            # Check if consolidating
            if abs(current_histogram) < 0.5 and abs(current_momentum) < 5:
                evidence.append("Market consolidating - wait for breakout")
                confidence_score = Decimal("0.55")
            else:
                evidence.append("Mixed signals - no clear direction")
                confidence_score = Decimal("0.45")

        # Risk assessment
        risk_assessment = {
            "macd": Decimal(str(current_macd)),
            "signal": Decimal(str(current_signal)),
            "histogram": Decimal(str(current_histogram)),
            "momentum_pct": Decimal(str(current_momentum)),
            "momentum_strength": Decimal(str(momentum_strength)),
            "volatility": Decimal(str(current_vol)),
            "volume_ratio": Decimal(str(volume_ratio)),
        }

        # Market context
        market_context = {
            "current_price": Decimal(str(current_price)),
            "ema_fast": Decimal(str(current_ema_fast)),
            "ema_slow": Decimal(str(current_ema_slow)),
            "macd_trend": "bullish" if current_macd > current_signal else "bearish",
            "histogram_trend": histogram_trend,
            "momentum_direction": "up"
            if current_momentum > 0
            else "down"
            if current_momentum < 0
            else "flat",
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
