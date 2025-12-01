"""Analysis engine - orchestrates data fetching, strategy execution, and result storage."""

import logging
from datetime import UTC, datetime

import pandas as pd

from cryptopilot.analysis.registry import create_strategy, get_strategy_class
from cryptopilot.analysis.strategies.base import AnalysisResult
from cryptopilot.database.models import AnalysisResultRecord, Timeframe
from cryptopilot.database.repository import Repository

logger = logging.getLogger(__name__)


class AnalysisError(Exception):
    """Analysis operation errors."""

    pass


class InsufficientDataError(AnalysisError):
    """Raised when not enough data for analysis."""

    pass


class AnalysisEngine:
    """Orchestrates market analysis.

    Responsibilities:
    - Fetch market data from database
    - Run strategies on data
    - Store analysis results
    - Handle failures gracefully
    """

    def __init__(
        self,
        repo: Repository,
    ) -> None:
        self._repo = repo

    async def analyze(
        self,
        symbol: str,
        strategy_name: str,
        timeframe: Timeframe = Timeframe.ONE_DAY,
        provider: str = "coingecko",
        save_result: bool = True,
        **strategy_params: object,
    ) -> AnalysisResult:
        """Run analysis on a symbol.

        Args:
            symbol: Cryptocurrency symbol
            strategy_name: Name of strategy to run
            timeframe: Timeframe for analysis
            provider: Data provider name
            save_result: Whether to save result to database
            **strategy_params: Additional strategy parameters

        Returns:
            AnalysisResult from strategy

        Raises:
            InsufficientDataError: If not enough market data
            AnalysisError: For other analysis failures
        """
        symbol = symbol.upper().strip()

        logger.info(f"Running {strategy_name} analysis on {symbol} ({timeframe.value})")

        # 1. Validate strategy and get requirements
        try:
            strategy_cls = get_strategy_class(strategy_name)
            strategy = create_strategy(strategy_name, **strategy_params)
        except ValueError as e:
            raise AnalysisError(f"Invalid strategy: {e}") from e

        required_periods = strategy.get_required_periods()

        # 2. Fetch market data
        data = await self._fetch_market_data(
            symbol=symbol,
            timeframe=timeframe,
            provider=provider,
            min_candles=required_periods,
        )

        if len(data) < required_periods:
            raise InsufficientDataError(
                f"Need {required_periods} candles for {strategy_name}, "
                f"but only {len(data)} available. "
                f"Run: cryptopilot collect --symbols {symbol} --days {required_periods}"
            )

        # 3. Run strategy analysis
        try:
            result = strategy.analyze(data)
            logger.info(
                f"Analysis complete: {result.action.value} "
                f"(confidence: {result.confidence.value}, "
                f"score: {result.confidence_score})"
            )
        except Exception as e:
            logger.exception(f"Strategy execution failed: {e}")
            raise AnalysisError(f"Strategy execution failed: {e}") from e

        # 4. Save result if requested
        if save_result:
            await self._save_result(
                symbol=symbol,
                strategy_name=strategy_name,
                result=result,
            )

        return result

    async def analyze_portfolio(
        self,
        symbols: list[str],
        strategy_name: str,
        timeframe: Timeframe = Timeframe.ONE_DAY,
        provider: str = "coingecko",
        save_results: bool = True,
        **strategy_params: object,
    ) -> dict[str, AnalysisResult]:
        """Run analysis on multiple symbols.

        Args:
            symbols: List of cryptocurrency symbols
            strategy_name: Strategy to run
            timeframe: Timeframe for analysis
            provider: Data provider
            save_results: Whether to save results
            **strategy_params: Strategy parameters

        Returns:
            Dict of {symbol: AnalysisResult}

        Note:
            Failures on individual symbols are logged but don't stop analysis.
        """
        results: dict[str, AnalysisResult] = {}

        for symbol in symbols:
            try:
                result = await self.analyze(
                    symbol=symbol,
                    strategy_name=strategy_name,
                    timeframe=timeframe,
                    provider=provider,
                    save_result=save_results,
                    **strategy_params,
                )
                results[symbol] = result
            except InsufficientDataError as e:
                logger.warning(f"Skipping {symbol}: {e}")
            except AnalysisError as e:
                logger.error(f"Analysis failed for {symbol}: {e}")

        return results

    async def get_latest_analysis(
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
        return await self._repo.get_latest_result(symbol, strategy)

    async def get_analysis_history(
        self,
        symbol: str | None = None,
        strategy: str | None = None,
        days: int = 30,
        limit: int = 50,
    ) -> list[AnalysisResultRecord]:
        """Get historical analysis results.

        Args:
            symbol: Optional symbol filter
            strategy: Optional strategy filter
            days: Look back this many days
            limit: Maximum results

        Returns:
            List of AnalysisResultRecords
        """
        start_date = datetime.now(UTC).replace(hour=0, minute=0, second=0)
        start_date = start_date.replace(day=start_date.day - days)

        return await self._repo.list_results(
            symbol=symbol,
            strategy=strategy,
            start_date=start_date,
            limit=limit,
        )

    async def _fetch_market_data(
        self,
        symbol: str,
        timeframe: Timeframe,
        provider: str,
        min_candles: int,
    ) -> pd.DataFrame:
        """Fetch market data from database as DataFrame.

        Args:
            symbol: Symbol to fetch
            timeframe: Timeframe
            provider: Provider name
            min_candles: Minimum candles needed

        Returns:
            DataFrame with OHLCV data

        Raises:
            InsufficientDataError: If not enough data available
        """
        # Query database for market data
        query = """
            SELECT timestamp, open, high, low, close, volume
            FROM market_data
            WHERE symbol = ? AND timeframe = ? AND provider = ?
            ORDER BY timestamp ASC
        """

        rows = await self._repo._db.fetch_all(
            query,
            (symbol, timeframe.value, provider),
        )

        if not rows:
            raise InsufficientDataError(
                f"No market data found for {symbol} ({timeframe.value}). "
                f"Run: cryptopilot collect --symbols {symbol}"
            )

        if len(rows) < min_candles:
            raise InsufficientDataError(f"Need {min_candles} candles, only {len(rows)} available")
        data = pd.DataFrame([dict(row) for row in rows])
        # Convert timestamp strings to datetime
        data["timestamp"] = pd.to_datetime(data["timestamp"])

        # Convert price/volume strings to float for indicators
        # (Indicators work with float; final results use Decimal)
        for col in ["open", "high", "low", "close", "volume"]:
            data[col] = data[col].astype(float)

        return data

    async def _save_result(
        self,
        symbol: str,
        strategy_name: str,
        result: AnalysisResult,
    ) -> int:
        """Save analysis result to database.

        Args:
            symbol: Symbol analyzed
            strategy_name: Strategy used
            result: Analysis result

        Returns:
            Row ID of saved record
        """
        record = AnalysisResultRecord(
            symbol=symbol,
            strategy=strategy_name,
            action=result.action,
            confidence=result.confidence,
            confidence_score=result.confidence_score,
            evidence=result.evidence,
            risk_assessment=result.risk_assessment,
            market_context=result.market_context,
            timestamp=datetime.now(UTC),
        )

        row_id = await self._repo.insert_result(record)
        logger.debug(f"Saved analysis result (id={row_id}) for {symbol}")

        return row_id
