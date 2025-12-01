"""Tests for portfolio management."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from cryptopilot.database.models import TradeSide
from cryptopilot.portfolio.manager import InsufficientBalanceError
from cryptopilot.utils.decimal_math import calculate_average_cost_basis


@pytest.mark.asyncio
async def test_record_buy_trade(portfolio_manager):
    """Test recording a buy trade."""
    trade = await portfolio_manager.record_trade(
        symbol="BTC",
        side=TradeSide.BUY,
        quantity=Decimal("0.5"),
        price=Decimal("50000"),
        fee=Decimal("10"),
    )

    assert trade.symbol == "BTC"
    assert trade.quantity == Decimal("0.5")
    assert trade.total_cost == Decimal("25010.00")  # 0.5 * 50000 + 10


@pytest.mark.asyncio
async def test_record_sell_trade_insufficient_balance(portfolio_manager):
    """Test selling more than owned raises error."""
    with pytest.raises(InsufficientBalanceError):
        await portfolio_manager.record_trade(
            symbol="ETH",
            side=TradeSide.SELL,
            quantity=Decimal("10"),  # Don't own any
            price=Decimal("3000"),
        )


@pytest.mark.asyncio
async def test_position_calculation_single_buy(portfolio_manager):
    """Test position after single buy."""
    await portfolio_manager.record_trade(
        symbol="BTC",
        side=TradeSide.BUY,
        quantity=Decimal("1.0"),
        price=Decimal("40000"),
        fee=Decimal("20"),
    )

    position = await portfolio_manager.get_position("BTC")

    assert position is not None
    assert position.quantity == Decimal("1.0")
    assert position.cost_basis == Decimal("40000.00")
    assert position.total_cost == Decimal("40020.00")


@pytest.mark.asyncio
async def test_position_calculation_multiple_buys(portfolio_manager):
    """Test average cost basis with multiple buys."""
    # Buy 1: 1 BTC @ $40,000
    await portfolio_manager.record_trade(
        symbol="BTC",
        side=TradeSide.BUY,
        quantity=Decimal("1.0"),
        price=Decimal("40000"),
        timestamp=datetime.now(UTC) - timedelta(days=2),
    )

    # Buy 2: 1 BTC @ $50,000
    await portfolio_manager.record_trade(
        symbol="BTC",
        side=TradeSide.BUY,
        quantity=Decimal("1.0"),
        price=Decimal("50000"),
        timestamp=datetime.now(UTC) - timedelta(days=1),
    )

    position = await portfolio_manager.get_position("BTC")

    assert position.quantity == Decimal("2.0")
    # Average: (40000 + 50000) / 2 = 45000
    assert position.cost_basis == Decimal("45000.00")


@pytest.mark.asyncio
async def test_position_after_sell(portfolio_manager):
    """Test position reduces after sell."""
    # Buy 2 BTC
    await portfolio_manager.record_trade(
        symbol="BTC",
        side=TradeSide.BUY,
        quantity=Decimal("2.0"),
        price=Decimal("40000"),
        timestamp=datetime.now(UTC) - timedelta(days=1),
    )

    # Sell 0.5 BTC
    await portfolio_manager.record_trade(
        symbol="BTC",
        side=TradeSide.SELL,
        quantity=Decimal("0.5"),
        price=Decimal("45000"),
    )

    position = await portfolio_manager.get_position("BTC")

    assert position.quantity == Decimal("1.5")
    assert position.cost_basis == Decimal("40000.00")  # Unchanged


@pytest.mark.asyncio
async def test_pnl_calculation(portfolio_manager, mock_market_data):
    """Test P&L calculation with mock market prices."""
    # Buy 1 ETH @ $2,000
    await portfolio_manager.record_trade(
        symbol="ETH",
        side=TradeSide.BUY,
        quantity=Decimal("1.0"),
        price=Decimal("2000"),
    )

    # Mock current price @ $2,500
    await mock_market_data("ETH", Decimal("2500"))

    positions = await portfolio_manager.get_positions_with_pnl()
    eth_position = positions["ETH"]

    assert eth_position.current_price == Decimal("2500.00")
    assert eth_position.market_value == Decimal("2500.00")
    assert eth_position.unrealized_pnl == Decimal("500.00")
    assert eth_position.unrealized_pnl_pct == Decimal("25.00")


def test_average_cost_basis_calculation():
    """Test cost basis math utility."""
    # First buy: 1 @ $40,000
    basis = calculate_average_cost_basis(
        existing_quantity=Decimal("0"),
        existing_cost_basis=Decimal("0"),
        new_quantity=Decimal("1"),
        new_price=Decimal("40000"),
    )
    assert basis == Decimal("40000.00")

    # Second buy: 1 @ $50,000
    basis = calculate_average_cost_basis(
        existing_quantity=Decimal("1"),
        existing_cost_basis=Decimal("40000"),
        new_quantity=Decimal("1"),
        new_price=Decimal("50000"),
    )
    assert basis == Decimal("45000.00")
