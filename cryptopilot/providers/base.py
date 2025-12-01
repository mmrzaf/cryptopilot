"""Abstract base class for cryptocurrency data providers.

All providers must normalize data to XXX/USD pairs.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OHLCV(BaseModel):
    """Standardized OHLCV data structure.

    All prices in USD.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    timestamp: datetime
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)


class ProviderInfo(BaseModel):
    """Provider information and capabilities."""

    name: str
    requires_api_key: bool
    rate_limit_per_minute: int
    supported_timeframes: list[str]
    max_candles_per_request: int
    base_url: str


class ProviderError(Exception):
    """Base exception for provider errors."""

    pass


class RateLimitError(ProviderError):
    """Raised when rate limit is hit."""

    def __init__(self, retry_after: int | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s")


class InvalidSymbolError(ProviderError):
    """Raised when symbol is not supported."""

    pass


class DataProviderBase(ABC):
    """Abstract base class for all data providers.

    All implementations must:
    1. Return data normalized to XXX/USD pairs
    2. Handle rate limiting with RateLimitError
    3. Provide consistent error handling
    4. Return UTC timestamps
    """

    def __init__(self, api_key: str | None = None, **kwargs: Any) -> None:
        self.api_key = api_key
        self._session_data: dict[str, Any] = kwargs

    @abstractmethod
    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int | None = None,
    ) -> list[OHLCV]:
        """Fetch OHLCV data for a symbol.

        Args:
            symbol: Cryptocurrency symbol (e.g., 'BTC', 'ETH')
            timeframe: Timeframe ('1h', '4h', '1d', '1w')
            start_time: Start datetime (UTC)
            end_time: End datetime (UTC)
            limit: Maximum number of candles to fetch

        Returns:
            List of OHLCV data sorted by timestamp (oldest first)

        Raises:
            RateLimitError: When rate limit is exceeded
            InvalidSymbolError: When symbol is not supported
            ProviderError: For other provider-specific errors

        """
        pass

    @abstractmethod
    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current price in USD.

        Args:
            symbol: Cryptocurrency symbol

        Returns:
            Current price in USD

        """
        pass

    @abstractmethod
    async def validate_symbol(self, symbol: str) -> bool:
        """Check if symbol is supported by this provider.

        Args:
            symbol: Cryptocurrency symbol

        Returns:
            True if symbol is supported

        """
        pass

    @abstractmethod
    async def get_supported_symbols(self) -> list[str]:
        """Get list of all supported symbols.

        Returns:
            List of supported cryptocurrency symbols

        """
        pass

    @abstractmethod
    def get_info(self) -> ProviderInfo:
        """Get provider information and capabilities.

        Returns:
            Provider information

        """
        pass

    async def health_check(self) -> bool:
        """Check if provider is accessible and API key is valid.

        Returns:
            True if provider is healthy

        """
        try:
            # Try to fetch a common symbol
            await self.get_current_price("BTC")
            return True
        except Exception:
            return False

    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol to uppercase and remove /USD suffix if present.

        Args:
            symbol: Symbol to normalize

        Returns:
            Normalized symbol

        """
        symbol = symbol.upper().strip()
        for suffix in ("/USD", "/USDT"):
            if symbol.endswith(suffix):
                symbol = symbol[: -len(suffix)]
                break
        return symbol

    def _validate_timeframe(self, timeframe: str) -> None:
        """Validate timeframe is supported.

        Args:
            timeframe: Timeframe to validate

        Raises:
            ValueError: If timeframe is not supported

        """
        info = self.get_info()
        if timeframe not in info.supported_timeframes:
            raise ValueError(
                f"Timeframe '{timeframe}' not supported by {info.name}. "
                f"Supported: {info.supported_timeframes}"
            )
