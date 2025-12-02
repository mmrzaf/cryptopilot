"""Technical analysis indicators using pandas.

All indicators work on OHLCV DataFrames loaded from market_data.
"""

import pandas as pd


def calculate_sma(prices: pd.Series, period: int) -> pd.Series:
    """Calculate Simple Moving Average.

    Args:
        prices: Series of prices (typically 'close')
        period: Number of periods for SMA

    Returns:
        Series with SMA values
    """
    return prices.rolling(window=period, min_periods=period).mean()


def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average.

    Args:
        prices: Series of prices (typically 'close')
        period: Number of periods for EMA

    Returns:
        Series with EMA values
    """
    return prices.ewm(span=period, adjust=False, min_periods=period).mean()


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index.

    Args:
        prices: Series of prices (typically 'close')
        period: RSI period (default: 14)

    Returns:
        Series with RSI values (0-100)
    """
    delta = prices.diff()

    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_bollinger_bands(
    prices: pd.Series,
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate Bollinger Bands.

    Args:
        prices: Series of prices (typically 'close')
        period: SMA period for middle band
        num_std: Number of standard deviations for bands

    Returns:
        Tuple of (upper_band, middle_band, lower_band)
    """
    middle = calculate_sma(prices, period)
    std = prices.rolling(window=period, min_periods=period).std()

    upper = middle + (std * num_std)
    lower = middle - (std * num_std)

    return upper, middle, lower


def calculate_macd(
    prices: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate MACD (Moving Average Convergence Divergence).

    Args:
        prices: Series of prices (typically 'close')
        fast_period: Fast EMA period
        slow_period: Slow EMA period
        signal_period: Signal line EMA period

    Returns:
        Tuple of (macd_line, signal_line, histogram)
    """
    fast_ema = calculate_ema(prices, fast_period)
    slow_ema = calculate_ema(prices, slow_period)

    macd_line = fast_ema - slow_ema
    signal_line = calculate_ema(macd_line, signal_period)
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def calculate_volatility(prices: pd.Series, period: int = 20) -> pd.Series:
    """Calculate rolling volatility (standard deviation of returns).

    Args:
        prices: Series of prices (typically 'close')
        period: Rolling window period

    Returns:
        Series with volatility values
    """
    returns = prices.pct_change()
    return returns.rolling(window=period, min_periods=period).std()


def calculate_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Calculate Average True Range.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ATR period

    Returns:
        Series with ATR values
    """
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=period, min_periods=period).mean()

    return atr


def is_uptrend(prices: pd.Series, short_period: int = 50, long_period: int = 200) -> bool:
    """Check if current trend is upward based on SMA crossover.

    Args:
        prices: Series of prices
        short_period: Short-term SMA period
        long_period: Long-term SMA period

    Returns:
        True if short SMA > long SMA (uptrend)
    """
    short_sma = calculate_sma(prices, short_period)
    long_sma = calculate_sma(prices, long_period)

    if short_sma.isna().all() or long_sma.isna().all():
        return False

    return float(short_sma.iloc[-1]) > float(long_sma.iloc[-1])


def detect_crossover(
    fast: pd.Series,
    slow: pd.Series,
    lookback: int = 5,
) -> str | None:
    """Detect recent crossover between two indicators.

    Args:
        fast: Fast-moving indicator
        slow: Slow-moving indicator
        lookback: How many periods back to check

    Returns:
        'bullish' if fast crossed above slow
        'bearish' if fast crossed below slow
        None if no crossover
    """
    if len(fast) < lookback + 1 or len(slow) < lookback + 1:
        return None

    recent = min(lookback, len(fast) - 1)

    for i in range(1, recent + 1):
        prev_idx = -i - 1
        curr_idx = -i

        prev_fast = float(fast.iloc[prev_idx])
        prev_slow = float(slow.iloc[prev_idx])
        curr_fast = float(fast.iloc[curr_idx])
        curr_slow = float(slow.iloc[curr_idx])

        # Bullish crossover: fast was below, now above
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            return "bullish"

        # Bearish crossover: fast was above, now below
        if prev_fast >= prev_slow and curr_fast < curr_slow:
            return "bearish"

    return None
