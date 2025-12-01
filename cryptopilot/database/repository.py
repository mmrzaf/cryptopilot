from collections.abc import Sequence
from datetime import UTC, datetime

from cryptopilot.database.connection import DatabaseConnection, decimal_to_str
from cryptopilot.database.models import MarketDataRecord, Timeframe


def _to_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class MarketDataRepository:
    """Data-access layer for market_data table.

    All SQL related to market data lives here.
    """

    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    async def get_latest_timestamp(
        self,
        symbol: str,
        timeframe: Timeframe,
        provider: str,
    ) -> datetime | None:
        """Return latest candle timestamp for symbol/timeframe/provider, or None."""
        query = """
            SELECT timestamp
            FROM market_data
            WHERE symbol = ? AND timeframe = ? AND provider = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """

        row = await self._db.fetch_one(
            query,
            (symbol.upper(), timeframe.value, provider),
        )
        if row is None:
            return None

        ts = row["timestamp"]
        if isinstance(ts, str):
            dt = datetime.fromisoformat(ts)
            return _to_utc(dt)
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=UTC)

        raise TypeError(f"Unsupported timestamp type from DB: {type(ts)!r}")

    async def insert_market_data(
        self,
        records: Sequence[MarketDataRecord],
        batch_size: int | None = None,
    ) -> int:
        """Bulk insert market data records.

        Uses INSERT OR IGNORE to avoid blowing up on duplicates while still
        keeping inserts idempotent.

        Returns:
            Number of rows reported inserted by SQLite.

        """
        if not records:
            return 0

        query = """
            INSERT OR IGNORE INTO market_data (
                symbol,
                base_currency,
                timestamp,
                open,
                high,
                low,
                close,
                volume,
                timeframe,
                provider,
                collected_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        params: list[tuple[object, ...]] = []
        for rec in records:
            params.append(
                (
                    rec.symbol.upper(),
                    rec.base_currency,
                    _to_utc(rec.timestamp).isoformat(),
                    decimal_to_str(rec.open),
                    decimal_to_str(rec.high),
                    decimal_to_str(rec.low),
                    decimal_to_str(rec.close),
                    decimal_to_str(rec.volume),
                    rec.timeframe.value,
                    rec.provider,
                    _to_utc(rec.collected_at).isoformat(),
                )
            )

        if batch_size is None or batch_size <= 0:
            batch_size = len(params)

        total_inserted = 0

        for i in range(0, len(params), batch_size):
            chunk = params[i : i + batch_size]

            tx = await self._db.transaction()
            async with tx as conn:
                cursor = await conn.executemany(query, chunk)

            # For INSERT OR IGNORE, rowcount is "rows actually inserted".
            if cursor.rowcount is not None:
                total_inserted += cursor.rowcount

        return total_inserted

    async def list_timestamps(
        self,
        symbol: str,
        timeframe: Timeframe,
        provider: str,
        start: datetime,
        end: datetime,
    ) -> list[datetime]:
        """Return all candle timestamps for symbol/timeframe/provider in [start, end].

        Timestamps are returned as timezone-aware UTC datetimes sorted ascending.
        """
        query = """
            SELECT timestamp
            FROM market_data
            WHERE symbol = ? AND timeframe = ? AND provider = ?
              AND timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
        """

        start_utc = _to_utc(start).isoformat()
        end_utc = _to_utc(end).isoformat()

        rows = await self._db.fetch_all(
            query,
            (symbol.upper(), timeframe.value, provider, start_utc, end_utc),
        )

        timestamps: list[datetime] = []
        for row in rows:
            ts = row["timestamp"]
            if isinstance(ts, str):
                dt = datetime.fromisoformat(ts)
                timestamps.append(_to_utc(dt))
            elif isinstance(ts, (int, float)):
                timestamps.append(datetime.fromtimestamp(ts, tz=UTC))
            else:
                raise TypeError(f"Unsupported timestamp type from DB: {type(ts)!r}")
        return timestamps
