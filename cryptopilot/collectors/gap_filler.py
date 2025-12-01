import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from cryptopilot.database.models import MarketDataRecord, Timeframe
from cryptopilot.database.repository import MarketDataRepository
from cryptopilot.providers.base import OHLCV, DataProviderBase
from cryptopilot.utils.retry import RetryConfig, retry_with_backoff

logger = logging.getLogger(__name__)

_TIMEFRAME_DELTAS: Final[dict[Timeframe, timedelta]] = {
    Timeframe.ONE_HOUR: timedelta(hours=1),
    Timeframe.FOUR_HOUR: timedelta(hours=4),
    Timeframe.ONE_DAY: timedelta(days=1),
    Timeframe.ONE_WEEK: timedelta(weeks=1),
}


@dataclass
class Gap:
    """Represents a contiguous gap in candle timestamps."""

    start: datetime
    end: datetime
    missing_candles: int


@dataclass
class GapCheckResult:
    """Result of a gap / integrity check for a symbol/timeframe."""

    symbol: str
    timeframe: Timeframe
    checked_from: datetime
    checked_to: datetime
    gaps: list[Gap]

    @property
    def issues_found(self) -> int:
        return sum(g.missing_candles for g in self.gaps)


class GapFiller:
    """Detect and optionally fill gaps in market_data.

    This is intentionally conservative and looks at a recent lookback window.
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

    async def detect_gaps_recent(
        self,
        symbol: str,
        timeframe: Timeframe,
        lookback_days: int,
    ) -> GapCheckResult:
        """Detect gaps for the last N days of data.

        Does not modify the database; purely inspects timestamps.
        """
        now = datetime.now(UTC)
        start = now - timedelta(days=lookback_days)

        timestamps = await self._repo.list_timestamps(
            symbol=symbol,
            timeframe=timeframe,
            provider=self._provider_name,
            start=start,
            end=now,
        )

        gaps: list[Gap] = []

        if len(timestamps) < 2:
            logger.info(
                "Gap check: not enough data for %s %s (found %d candles)",
                symbol,
                timeframe.value,
                len(timestamps),
            )
            return GapCheckResult(
                symbol=symbol,
                timeframe=timeframe,
                checked_from=start,
                checked_to=now,
                gaps=gaps,
            )

        tf_delta = _TIMEFRAME_DELTAS[timeframe]

        prev = timestamps[0]
        for ts in timestamps[1:]:
            delta = ts - prev
            # simple heuristic: if difference is more than one interval (+1s slack), treat as gap
            if delta > tf_delta + timedelta(seconds=1):
                missing = int(delta // tf_delta) - 1
                if missing > 0:
                    gap_start = prev + tf_delta
                    gap_end = ts - tf_delta
                    gaps.append(
                        Gap(
                            start=gap_start,
                            end=gap_end,
                            missing_candles=missing,
                        )
                    )
            prev = ts

        if gaps:
            logger.warning(
                "Gap check: detected %d gaps (%d missing candles) for %s %s",
                len(gaps),
                sum(g.missing_candles for g in gaps),
                symbol,
                timeframe.value,
            )
        else:
            logger.info("Gap check: no gaps detected for %s %s", symbol, timeframe.value)

        return GapCheckResult(
            symbol=symbol,
            timeframe=timeframe,
            checked_from=start,
            checked_to=now,
            gaps=gaps,
        )

    async def fill_gaps_recent(
        self,
        symbol: str,
        timeframe: Timeframe,
        lookback_days: int,
        dry_run: bool = False,
    ) -> tuple[GapCheckResult, int]:
        """Attempt to fill gaps in the last N days.

        Returns:
            (gap_check_result, candles_inserted)
        """
        result = await self.detect_gaps_recent(symbol, timeframe, lookback_days)

        if not result.gaps or dry_run:
            if dry_run and result.gaps:
                logger.info(
                    "Gap fill dry run for %s %s – would attempt to fill %d gaps",
                    symbol,
                    timeframe.value,
                    len(result.gaps),
                )
            return result, 0

        tf_delta = _TIMEFRAME_DELTAS[timeframe]
        total_inserted = 0

        for gap in result.gaps:
            # extend window slightly to ensure we capture full missing range
            fetch_start = gap.start - tf_delta
            fetch_end = gap.end + tf_delta

            logger.info(
                "Gap fill: %s %s – fetching missing window %s → %s (%d missing candles)",
                symbol,
                timeframe.value,
                fetch_start.isoformat(),
                fetch_end.isoformat(),
                gap.missing_candles,
            )

            candles = await self._fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                start=fetch_start,
                end=fetch_end,
            )
            if not candles:
                logger.warning(
                    "Gap fill: provider returned no candles for %s %s in window %s → %s",
                    symbol,
                    timeframe.value,
                    fetch_start.isoformat(),
                    fetch_end.isoformat(),
                )
                continue

            records = self._to_records(symbol, timeframe, candles)
            inserted = await self._repo.insert_market_data(records, self._batch_size)
            total_inserted += inserted

            logger.info(
                "Gap fill: inserted %d rows for %s %s while filling gap",
                inserted,
                symbol,
                timeframe.value,
            )

        return result, total_inserted

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
            None,
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
