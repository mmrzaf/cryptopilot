"""Async SQLite connection management with connection pooling and proper initialization."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any

import aiosqlite


class DatabaseConnection:
    """Manages async SQLite connections with proper initialization and connection pooling."""

    def __init__(self, db_path: Path, schema_path: Path) -> None:
        self.db_path = db_path
        self.schema_path = schema_path
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database with schema if needed."""
        async with self._lock:
            if self._initialized:
                return

            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("PRAGMA foreign_keys = ON")
                await db.execute("PRAGMA journal_mode = WAL")

                schema_sql = self.schema_path.read_text()
                await db.executescript(schema_sql)
                await db.commit()

            self._initialized = True

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Get a database connection with proper configuration.

        Usage:
            async with db.get_connection() as conn:
                await conn.execute(...)
        """
        if not self._initialized:
            await self.initialize()

        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("PRAGMA foreign_keys = ON")

            conn.row_factory = aiosqlite.Row

            try:
                yield conn
            except Exception:
                await conn.rollback()
                raise

    async def execute(
        self, query: str, parameters: tuple[Any, ...] | dict[str, Any] | None = None
    ) -> aiosqlite.Cursor:
        """Execute a single query."""
        async with self.get_connection() as conn:
            if parameters:
                cursor = await conn.execute(query, parameters)
            else:
                cursor = await conn.execute(query)
            await conn.commit()
            return cursor

    async def execute_many(
        self, query: str, parameters: list[tuple[Any, ...]] | list[dict[str, Any]]
    ) -> None:
        """Execute query with multiple parameter sets (bulk insert)."""
        async with self.get_connection() as conn:
            await conn.executemany(query, parameters)
            await conn.commit()

    async def fetch_one(
        self, query: str, parameters: tuple[Any, ...] | dict[str, Any] | None = None
    ) -> aiosqlite.Row | None:
        """Fetch a single row."""
        async with self.get_connection() as conn:
            if parameters:
                cursor = await conn.execute(query, parameters)
            else:
                cursor = await conn.execute(query)
            return await cursor.fetchone()

    async def fetch_all(
        self, query: str, parameters: tuple[Any, ...] | dict[str, Any] | None = None
    ) -> list[aiosqlite.Row]:
        """Fetch all rows."""
        async with self.get_connection() as conn:
            if parameters:
                cursor = await conn.execute(query, parameters)
            else:
                cursor = await conn.execute(query)
            return await cursor.fetchall()

    async def transaction(self) -> "Transaction":
        """Begin an explicit transaction."""
        return Transaction(self)

    async def get_schema_version(self) -> int:
        """Get current schema version."""
        row = await self.fetch_one("SELECT MAX(version) as version FROM schema_version")
        return row["version"] if row else 0

    async def check_integrity(self) -> bool:
        """Run SQLite integrity check."""
        row = await self.fetch_one("PRAGMA integrity_check")
        return row is not None and row[0] == "ok"


class Transaction:
    """Context manager for explicit transactions."""

    def __init__(self, db: DatabaseConnection) -> None:
        self.db = db
        self._conn: aiosqlite.Connection | None = None

    async def __aenter__(self) -> aiosqlite.Connection:
        if not self.db._initialized:
            await self.db.initialize()

        self._conn = await aiosqlite.connect(self.db.db_path).__aenter__()
        await self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("BEGIN")
        return self._conn

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._conn:
            if exc_type is None:
                await self._conn.commit()
            else:
                await self._conn.rollback()
            await self._conn.__aexit__(exc_type, exc_val, exc_tb)


def decimal_to_str(value: Decimal) -> str:
    """Convert Decimal to string for storage."""
    return str(value)


def str_to_decimal(value: str) -> Decimal:
    """Convert string from database to Decimal."""
    return Decimal(value)


def ensure_decimal(value: int | float | str | Decimal) -> Decimal:
    """Ensure value is Decimal, converting if necessary."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))
