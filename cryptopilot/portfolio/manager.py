"""Portfolio management with trade tracking and P&L calculation."""

import logging
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal

from cryptopilot.database.connection import DatabaseConnection
from cryptopilot.database.models import (
    Position,
    PositionWithMarketData,
    TradeRecord,
    TradeSide,
)
from cryptopilot.database.repository import Repository
from cryptopilot.utils.decimal_math import (
    calculate_average_cost_basis,
    calculate_unrealized_pnl,
    round_price,
    round_usd,
)

logger = logging.getLogger(__name__)


class PortfolioError(Exception):
    """Portfolio operation errors."""

    pass


class InsufficientBalanceError(PortfolioError):
    """Raised when trying to sell more than owned."""

    pass


class PortfolioManager:
    """Manage portfolio trades and positions.

    Responsibilities:
    - Record trades with validation
    - Calculate positions from trade history
    - Compute P&L using current market prices
    - FIFO/average cost basis tracking
    """

    def __init__(
        self,
        repository: Repository,
        db: DatabaseConnection,
    ) -> None:
        self._repo = repository
        self._db = db

    async def record_trade(
        self,
        symbol: str,
        side: TradeSide,
        quantity: Decimal,
        price: Decimal,
        fee: Decimal = Decimal("0"),
        timestamp: datetime | None = None,
        account: str = "default",
        notes: str | None = None,
    ) -> TradeRecord:
        """Record a new trade.

        Args:
            symbol: Cryptocurrency symbol
            side: BUY or SELL
            quantity: Amount traded
            price: Price per unit in USD
            fee: Transaction fee in USD
            timestamp: Trade timestamp (defaults to now)
            account: Account identifier
            notes: Optional notes

        Returns:
            Created TradeRecord

        Raises:
            InsufficientBalanceError: If selling more than owned
            PortfolioError: For other validation errors
        """
        symbol = symbol.upper().strip()

        if timestamp is None:
            timestamp = datetime.now(UTC)
        elif timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        # Calculate total cost
        if side == TradeSide.BUY:
            total_cost = round_usd((quantity * price) + fee)
        else:  # SELL
            total_cost = round_usd((quantity * price) - fee)

        # Validate sell doesn't exceed holdings
        if side == TradeSide.SELL:
            position = await self.get_position(symbol, account)
            if position and position.quantity < quantity:
                raise InsufficientBalanceError(
                    f"Cannot sell {quantity} {symbol}. Current position: {position.quantity}"
                )

        trade = TradeRecord(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            fee=fee,
            total_cost=total_cost,
            timestamp=timestamp,
            account=account,
            notes=notes,
        )

        await self._repo.insert_trade(trade)
        logger.info(
            f"Recorded {side.value} trade: {quantity} {symbol} @ ${price} "
            f"(fee: ${fee}, total: ${total_cost})"
        )

        return trade

    async def list_trades(
        self,
        symbol: str | None = None,
        account: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int | None = None,
    ) -> list[TradeRecord]:
        """List trades with optional filters.

        Args:
            symbol: Filter by symbol
            account: Filter by account
            start_date: Filter trades after this date
            end_date: Filter trades before this date
            limit: Maximum trades to return

        Returns:
            List of trades, sorted by timestamp descending
        """
        return await self._repo.list_trades(
            symbol=symbol,
            account=account,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    async def get_position(
        self,
        symbol: str,
        account: str = "default",
    ) -> Position | None:
        """Get current position for a symbol.

        Calculates position from trade history using average cost basis.

        Args:
            symbol: Cryptocurrency symbol
            account: Account identifier

        Returns:
            Position or None if no holdings
        """
        positions = await self.get_all_positions(account=account)
        return positions.get(symbol.upper())

    async def get_all_positions(
        self,
        account: str | None = None,
    ) -> dict[str, Position]:
        """Calculate all current positions from trade history.

        Uses average cost basis method:
        - Buys: Add to position, update average cost
        - Sells: Reduce position, cost basis unchanged

        Args:
            account: Filter by account (None = all accounts)

        Returns:
            Dict of {symbol: Position}
        """
        trades = await self.list_trades(account=account)

        if not trades:
            return {}

        # Group trades by symbol and account
        by_symbol: dict[tuple[str, str], list[TradeRecord]] = defaultdict(list)
        for trade in trades:
            key = (trade.symbol, trade.account)
            by_symbol[key].append(trade)

        positions: dict[str, Position] = {}

        for (symbol, acc), symbol_trades in by_symbol.items():
            # Sort by timestamp
            symbol_trades.sort(key=lambda t: t.timestamp)

            quantity = Decimal("0")
            cost_basis = Decimal("0")
            total_cost = Decimal("0")
            trade_count = 0

            first_trade = symbol_trades[0].timestamp
            last_trade = symbol_trades[-1].timestamp

            for trade in symbol_trades:
                trade_count += 1

                if trade.side == TradeSide.BUY:
                    # Update average cost basis
                    cost_basis = calculate_average_cost_basis(
                        existing_quantity=quantity,
                        existing_cost_basis=cost_basis,
                        new_quantity=trade.quantity,
                        new_price=trade.price,
                    )
                    quantity += trade.quantity
                    total_cost += trade.total_cost

                else:  # SELL
                    quantity -= trade.quantity
                    # Reduce total cost proportionally
                    if quantity > 0:
                        total_cost = quantity * cost_basis
                    else:
                        total_cost = Decimal("0")

            # Only include if we have a position
            if quantity > Decimal("0"):
                positions[symbol] = Position(
                    symbol=symbol,
                    quantity=quantity,
                    cost_basis=round_price(cost_basis),
                    total_cost=round_usd(total_cost),
                    account=acc,
                    first_trade=first_trade,
                    last_trade=last_trade,
                    trade_count=trade_count,
                )

        return positions

    async def get_positions_with_pnl(
        self,
        account: str | None = None,
    ) -> dict[str, PositionWithMarketData]:
        """Get positions enriched with current market prices and P&L.

        Fetches latest market prices from market_data table.

        Args:
            account: Filter by account

        Returns:
            Dict of {symbol: PositionWithMarketData}

        Raises:
            PortfolioError: If market data is missing for a position
        """
        positions = await self.get_all_positions(account=account)

        if not positions:
            return {}

        positions_with_pnl: dict[str, PositionWithMarketData] = {}

        for symbol, position in positions.items():
            # Fetch current price from market_data
            price_data = await self._repo.get_latest_price(symbol)

            if price_data is None:
                logger.warning(
                    f"No market data found for {symbol}. Run 'cryptopilot collect' to fetch prices."
                )
                continue

            current_price, price_updated_at = price_data

            # Calculate P&L
            market_value = position.quantity * current_price
            absolute_pnl, pct_pnl = calculate_unrealized_pnl(
                quantity=position.quantity,
                cost_basis=position.cost_basis,
                current_price=current_price,
            )

            positions_with_pnl[symbol] = PositionWithMarketData(
                **position.model_dump(),
                current_price=current_price,
                market_value=round_usd(market_value),
                unrealized_pnl=absolute_pnl,
                unrealized_pnl_pct=pct_pnl,
                price_updated_at=price_updated_at,
            )

        return positions_with_pnl

    async def get_portfolio_summary(
        self,
        account: str | None = None,
    ) -> dict[str, Decimal]:
        """Get portfolio-level summary statistics.

        Returns:
            Dict with total_value, total_cost, total_pnl, total_pnl_pct
        """
        positions = await self.get_positions_with_pnl(account=account)

        if not positions:
            return {
                "total_value": Decimal("0"),
                "total_cost": Decimal("0"),
                "total_pnl": Decimal("0"),
                "total_pnl_pct": Decimal("0"),
            }

        total_value = sum(p.market_value for p in positions.values())
        total_cost = sum(p.total_cost for p in positions.values())
        total_pnl = sum(p.unrealized_pnl for p in positions.values())

        if total_cost > 0:
            total_pnl_pct = (total_pnl / total_cost) * 100
        else:
            total_pnl_pct = Decimal("0")

        return {
            "total_value": round_usd(total_value),
            "total_cost": round_usd(total_cost),
            "total_pnl": round_usd(total_pnl),
            "total_pnl_pct": round_price(total_pnl_pct),
        }
