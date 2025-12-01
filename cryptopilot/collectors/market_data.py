import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cryptopilot.database.models import MarketDataRecord, Timeframe
from cryptopilot.database.repository import MarketDataRepository
from cryptopilot.providers.base import OHLCV, DataProviderBase
from cryptopilot.utils.retry import RetryConfig, retry_with_backoff

logger = logging.getLogger(__name__)

_TIMEFRAME_DELTAS: dict[Timeframe, timedelta] = {
    Timeframe.ONE_HOUR: timedelta(hours=1),
    Timeframe.FOUR_HOUR: timedelta(hours=4),
    Timeframe.ONE_DAY: timedelta(days=1),
    Timeframe.ONE_WEEK: timedelta(weeks=1),
}


@dataclass
class CollectionResult:
    """Summary of a single symbol/timeframe collection."""

    symbol: str
    timeframe: Timeframe
    candles_fetched: int
    candles_inserted: int
    start: datetime | None = None
    end: datetime | None = None


class MarketDataCollector:
    """High-level market data collector.

    Responsibilities:
        - Figure out what time range to fetch per symbol.
        - Call provider with retry/backoff.
        - Persist data via MarketDataRepository (no SQL here).
    """

    def __init__(
        self,
        repository: MarketDataRepository,
        provider: DataProviderBase,
        provider_name: str,
        base_currency: str,
        batch_size: int = 100,
        retry_config: RetryConfig | None = None,
    ) -> None:
        self._repo = repository
        self._provider = provider
        self._provider_name = provider_name
        self._base_currency = base_currency
        self._batch_size = batch_size
        self._retry_config = retry_config or RetryConfig()

    async def collect(
        self,
        symbols: Sequence[str],
        timeframe: Timeframe,
        lookback_days: int,
        update_all: bool = False,
        dry_run: bool = False,
    ) -> list[CollectionResult]:
        """Collect data for multiple symbols.

        Args:
            symbols: Symbols to collect.
            timeframe: Candle timeframe.
            lookback_days: How many days back to include in the window.
            update_all: If True, ignore lookback window and purely append from the
                last known candle.
            dry_run: If True, fetch from provider but do not write anything to the DB.

        Returns:
            Per-symbol collection summaries.
        """
        now = datetime.now(UTC)
        results: list[CollectionResult] = []

        for raw_symbol in symbols:
            symbol = raw_symbol.upper().strip()
            try:
                result = await self._collect_single(
                    symbol=symbol,
                    timeframe=timeframe,
                    now=now,
                    lookback_days=lookback_days,
                    update_all=update_all,
                    dry_run=dry_run,
                )
                results.append(result)
            except Exception as exc:
                logger.exception("Failed to collect data for %s: %s", symbol, exc)
                # One failure stops entire collection run as per spec.
                raise

        return results

    async def _collect_single(
        self,
        symbol: str,
        timeframe: Timeframe,
        now: datetime,
        lookback_days: int,
        update_all: bool,
        dry_run: bool,
    ) -> CollectionResult:
        logger.info(
            "Collecting %s candles for %s (provider=%s, lookback_days=%d, update_all=%s, dry_run=%s)",
            timeframe.value,
            symbol,
            self._provider_name,
            lookback_days,
            update_all,
            dry_run,
        )

        latest = await self._repo.get_latest_timestamp(
            symbol=symbol,
            timeframe=timeframe,
            provider=self._provider_name,
        )
        tf_delta = _TIMEFRAME_DELTAS[timeframe]

        if latest is None:
            start = now - timedelta(days=lookback_days)
        elif update_all:
            start = latest + tf_delta
        else:
            candidate = now - timedelta(days=lookback_days)
            start = max(candidate, latest + tf_delta)

        if start >= now:
            logger.info("No new data needed for %s (%s)", symbol, timeframe.value)
            return CollectionResult(
                symbol=symbol,
                timeframe=timeframe,
                candles_fetched=0,
                candles_inserted=0,
                start=None,
                end=None,
            )

        candles = await self._fetch_ohlcv(symbol, timeframe, start, now)
        candles_fetched = len(candles)

        if not candles:
            logger.warning("Provider returned no candles for %s %s", symbol, timeframe.value)
            return CollectionResult(
                symbol=symbol,
                timeframe=timeframe,
                candles_fetched=0,
                candles_inserted=0,
                start=None,
                end=None,
            )

        records = self._to_records(symbol, timeframe, candles)

        if dry_run:
            inserted = 0
            logger.info(
                "Dry run: fetched %d candles for %s %s – skipping DB insert",
                candles_fetched,
                symbol,
                timeframe.value,
            )
        else:
            inserted = await self._repo.insert_market_data(records, self._batch_size)
            logger.info(
                "Inserted %d rows for %s %s (fetched %d candles)",
                inserted,
                symbol,
                timeframe.value,
                candles_fetched,
            )

        return CollectionResult(
            symbol=symbol,
            timeframe=timeframe,
            candles_fetched=candles_fetched,
            candles_inserted=inserted,
            start=candles[0].timestamp if candles else None,
            end=candles[-1].timestamp if candles else None,
        )

    async def _fetch_ohlcv(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: datetime,
        end: datetime,
    ) -> list[OHLCV]:
        """Fetch OHLCV from provider with retry/backoff."""
        return await retry_with_backoff(
            self._provider.get_ohlcv,
            symbol,
            timeframe.value,
            start,
            end,
            None,  # limit
            config=self._retry_config,
        )

    def _to_records(
        self,
        symbol: str,
        timeframe: Timeframe,
        candles: list[OHLCV],
    ) -> list[MarketDataRecord]:
        """Convert provider OHLCV into DB records."""
        now = datetime.now(UTC)

        return [
            MarketDataRecord(
                symbol=symbol,
                base_currency=self._base_currency,
                timestamp=candle.timestamp,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                timeframe=timeframe,
                provider=self._provider_name,
                collected_at=now,
            )
            for candle in candles
        ]
