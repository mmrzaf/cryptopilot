import json
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

from cryptopilot.database.connection import DatabaseConnection, decimal_to_str, str_to_decimal
from cryptopilot.database.models import (
    ActionType,
    AnalysisResultRecord,
    ConfidenceLevel,
    MarketDataRecord,
    Timeframe,
    TradeRecord,
    TradeSide,
)


def _to_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


class Repository:
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

    async def insert_trade(self, trade: TradeRecord) -> int:
        """Insert a trade record.

        Returns:
            Row ID of inserted trade
        """
        query = """
            INSERT INTO trades (
                trade_id, symbol, side, quantity, price, fee,
                total_cost, timestamp, account, notes, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        cursor = await self._db.execute(
            query,
            (
                str(trade.trade_id),
                trade.symbol.upper(),
                trade.side.value,
                decimal_to_str(trade.quantity),
                decimal_to_str(trade.price),
                decimal_to_str(trade.fee),
                decimal_to_str(trade.total_cost),
                _to_utc(trade.timestamp).isoformat(),
                trade.account,
                trade.notes,
                _to_utc(trade.created_at).isoformat(),
            ),
        )

        return cursor.lastrowid or 0

    async def list_trades(
        self,
        symbol: str | None = None,
        account: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int | None = None,
    ) -> list[TradeRecord]:
        """Query trades with filters."""
        conditions = []
        params: list[str] = []

        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol.upper())

        if account:
            conditions.append("account = ?")
            params.append(account)

        if start_date:
            conditions.append("timestamp >= ?")
            params.append(_to_utc(start_date).isoformat())

        if end_date:
            conditions.append("timestamp <= ?")
            params.append(_to_utc(end_date).isoformat())

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        limit_clause = f"LIMIT {limit}" if limit else ""

        query = f"""
            SELECT * FROM trades
            {where_clause}
            ORDER BY timestamp DESC
            {limit_clause}
        """

        rows = await self._db.fetch_all(query, tuple(params) if params else None)

        trades: list[TradeRecord] = []
        for row in rows:
            trades.append(
                TradeRecord(
                    id=row["id"],
                    trade_id=row["trade_id"],
                    symbol=row["symbol"],
                    side=TradeSide(row["side"]),
                    quantity=str_to_decimal(row["quantity"]),
                    price=str_to_decimal(row["price"]),
                    fee=str_to_decimal(row["fee"]),
                    total_cost=str_to_decimal(row["total_cost"]),
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    account=row["account"],
                    notes=row["notes"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            )

        return trades

    async def get_latest_price(
        self,
        symbol: str,
    ) -> tuple[Decimal, datetime] | None:
        """Get most recent price from market_data.

        Returns:
            (price, timestamp) or None if no data
        """
        query = """
            SELECT close, timestamp
            FROM market_data
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """

        row = await self._db.fetch_one(query, (symbol.upper(),))

        if row is None:
            return None

        price = str_to_decimal(row["close"])
        timestamp = datetime.fromisoformat(row["timestamp"])

        return price, _to_utc(timestamp)

    async def insert_result(self, result: AnalysisResultRecord) -> int:
        """Insert analysis result.

        Args:
            result: AnalysisResultRecord to insert

        Returns:
            Row ID of inserted record
        """
        query = """
            INSERT INTO analysis_results (
                analysis_id, symbol, strategy, action, confidence,
                confidence_score, evidence, risk_assessment,
                timestamp, market_context
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        # Serialize complex fields to JSON
        evidence_json = json.dumps(result.evidence)
        risk_json = (
            json.dumps(result.risk_assessment, default=str) if result.risk_assessment else None
        )
        context_json = (
            json.dumps(result.market_context, default=str) if result.market_context else None
        )

        cursor = await self._db.execute(
            query,
            (
                str(result.analysis_id),
                result.symbol.upper(),
                result.strategy,
                result.action.value,
                result.confidence.value,
                decimal_to_str(result.confidence_score),
                evidence_json,
                risk_json,
                _to_utc(result.timestamp).isoformat(),
                context_json,
            ),
        )

        return cursor.lastrowid or 0

    async def get_latest_result(
        self,
        symbol: str,
        strategy: str | None = None,
    ) -> AnalysisResultRecord | None:
        """Get most recent analysis result for a symbol.

        Args:
            symbol: Cryptocurrency symbol
            strategy: Optional strategy filter

        Returns:
            Latest AnalysisResultRecord or None
        """
        if strategy:
            query = """
                SELECT * FROM analysis_results
                WHERE symbol = ? AND strategy = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """
            params = (symbol.upper(), strategy)
        else:
            query = """
                SELECT * FROM analysis_results
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """
            params = (symbol.upper(),)

        row = await self._db.fetch_one(query, params)

        if row is None:
            return None

        return self._row_to_record(row)

    async def list_results(
        self,
        symbol: str | None = None,
        strategy: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int | None = None,
    ) -> list[AnalysisResultRecord]:
        """Query analysis results with filters.

        Args:
            symbol: Filter by symbol
            strategy: Filter by strategy
            start_date: Filter results after this date
            end_date: Filter results before this date
            limit: Maximum results to return

        Returns:
            List of AnalysisResultRecords sorted by timestamp desc
        """
        conditions = []
        params: list[str] = []

        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol.upper())

        if strategy:
            conditions.append("strategy = ?")
            params.append(strategy)

        if start_date:
            conditions.append("timestamp >= ?")
            params.append(_to_utc(start_date).isoformat())

        if end_date:
            conditions.append("timestamp <= ?")
            params.append(_to_utc(end_date).isoformat())

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        limit_clause = f"LIMIT {limit}" if limit else ""

        query = f"""
            SELECT * FROM analysis_results
            {where_clause}
            ORDER BY timestamp DESC
            {limit_clause}
        """

        rows = await self._db.fetch_all(query, tuple(params) if params else None)

        return [self._row_to_record(row) for row in rows]

    async def get_results_by_action(
        self,
        action: ActionType,
        start_date: datetime | None = None,
        limit: int = 50,
    ) -> list[AnalysisResultRecord]:
        """Get results filtered by action type.

        Args:
            action: BUY, SELL, or HOLD
            start_date: Optional start date filter
            limit: Maximum results

        Returns:
            List of results with matching action
        """
        if start_date:
            query = """
                SELECT * FROM analysis_results
                WHERE action = ? AND timestamp >= ?
                ORDER BY timestamp DESC
                LIMIT ?
            """
            params = (action.value, _to_utc(start_date).isoformat(), limit)
        else:
            query = """
                SELECT * FROM analysis_results
                WHERE action = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """
            params = (action.value, limit)

        rows = await self._db.fetch_all(query, params)
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: object) -> AnalysisResultRecord:
        """Convert database row to AnalysisResultRecord.

        Args:
            row: Database row from aiosqlite

        Returns:
            AnalysisResultRecord
        """
        # Parse JSON fields
        evidence = json.loads(row["evidence"]) if row["evidence"] else []

        risk_assessment = None
        if row["risk_assessment"]:
            risk_data = json.loads(row["risk_assessment"])
            # Convert string decimals back to Decimal
            risk_assessment = {
                k: Decimal(v)
                if isinstance(v, str) and v.replace(".", "").replace("-", "").isdigit()
                else v
                for k, v in risk_data.items()
            }

        market_context = None
        if row["market_context"]:
            ctx_data = json.loads(row["market_context"])
            market_context = {
                k: Decimal(v)
                if isinstance(v, str) and v.replace(".", "").replace("-", "").isdigit()
                else v
                for k, v in ctx_data.items()
            }

        return AnalysisResultRecord(
            id=row["id"],
            analysis_id=row["analysis_id"],
            symbol=row["symbol"],
            strategy=row["strategy"],
            action=ActionType(row["action"]),
            confidence=ConfidenceLevel(row["confidence"]),
            confidence_score=str_to_decimal(row["confidence_score"]),
            evidence=evidence,
            risk_assessment=risk_assessment,
            timestamp=datetime.fromisoformat(row["timestamp"]),
            market_context=market_context,
        )
