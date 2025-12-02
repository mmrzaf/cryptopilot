"""Portfolio management CLI commands."""

import asyncio
from decimal import Decimal

import typer
from rich.console import Console
from rich.table import Table

from cryptopilot.config.settings import get_settings
from cryptopilot.database.connection import DatabaseConnection
from cryptopilot.database.models import TradeSide
from cryptopilot.database.repository import Repository
from cryptopilot.portfolio.manager import InsufficientBalanceError, PortfolioManager

console = Console()
app = typer.Typer(help="Portfolio management commands")


@app.command(name="trade")
def record_trade(
    symbol: str = typer.Argument(..., help="Symbol (e.g., BTC, ETH)"),
    side: str = typer.Argument(..., help="BUY or SELL"),
    quantity: str = typer.Argument(..., help="Quantity"),
    price: str = typer.Argument(..., help="Price per unit in USD"),
    fee: str = typer.Option("0", "--fee", "-f", help="Transaction fee in USD"),
    notes: str = typer.Option(None, "--notes", "-n", help="Optional notes"),
    account: str = typer.Option("default", "--account", "-a", help="Account identifier"),
) -> None:
    """Record a trade (buy or sell)."""

    async def _record() -> None:
        settings = get_settings()
        db = DatabaseConnection(
            db_path=settings.database.path,
            schema_path=settings.database.schema_path,
        )
        await db.initialize()

        repo = Repository(db)
        manager = PortfolioManager(repo, db)

        try:
            trade_side = TradeSide(side.upper())
        except ValueError:
            console.print(f"[red]Invalid side '{side}'. Must be BUY or SELL.[/red]")
            raise typer.Exit(1)

        try:
            qty = Decimal(quantity)
            px = Decimal(price)
            fee_amt = Decimal(fee)
        except Exception as e:
            console.print(f"[red]Invalid numeric value: {e}[/red]")
            raise typer.Exit(1)

        try:
            trade = await manager.record_trade(
                symbol=symbol,
                side=trade_side,
                quantity=qty,
                price=px,
                fee=fee_amt,
                account=account,
                notes=notes,
            )

            console.print("\n[green]✓ Trade recorded successfully![/green]")
            console.print(f"Trade ID: {trade.trade_id}")
            console.print(f"{trade.side.value} {trade.quantity} {trade.symbol} @ ${trade.price}")
            console.print(f"Total cost: ${trade.total_cost}")

        except InsufficientBalanceError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)

    asyncio.run(_record())


@app.command(name="list")
def list_trades(
    symbol: str = typer.Option(None, "--symbol", "-s", help="Filter by symbol"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max trades to show"),
) -> None:
    """List recent trades."""

    async def _list() -> None:
        settings = get_settings()
        db = DatabaseConnection(
            db_path=settings.database.path,
            schema_path=settings.database.schema_path,
        )
        await db.initialize()

        repo = Repository(db)
        manager = PortfolioManager(repo, db)

        trades = await manager.list_trades(symbol=symbol, limit=limit)

        if not trades:
            console.print("[yellow]No trades found.[/yellow]")
            return

        table = Table(title=f"Trade History ({len(trades)} trades)")
        table.add_column("Date", style="cyan")
        table.add_column("Symbol", style="magenta")
        table.add_column("Side", style="green")
        table.add_column("Quantity", justify="right")
        table.add_column("Price", justify="right")
        table.add_column("Fee", justify="right")
        table.add_column("Total", justify="right")

        for trade in trades:
            side_color = "green" if trade.side == TradeSide.BUY else "red"
            table.add_row(
                trade.timestamp.strftime("%Y-%m-%d %H:%M"),
                trade.symbol,
                f"[{side_color}]{trade.side.value}[/{side_color}]",
                str(trade.quantity),
                f"${trade.price:,.2f}",
                f"${trade.fee:,.2f}",
                f"${trade.total_cost:,.2f}",
            )

        console.print(table)

    asyncio.run(_list())


@app.command(name="positions")
def show_positions() -> None:
    """Show current portfolio positions."""

    async def _positions() -> None:
        settings = get_settings()
        db = DatabaseConnection(
            db_path=settings.database.path,
            schema_path=settings.database.schema_path,
        )
        await db.initialize()

        repo = Repository(db)
        manager = PortfolioManager(repo, db)

        positions = await manager.get_all_positions()

        if not positions:
            console.print("[yellow]No open positions.[/yellow]")
            return

        table = Table(title="Current Positions")
        table.add_column("Symbol", style="cyan")
        table.add_column("Quantity", justify="right")
        table.add_column("Avg Cost", justify="right")
        table.add_column("Total Cost", justify="right")
        table.add_column("Trades", justify="right")

        for symbol, pos in positions.items():
            table.add_row(
                symbol,
                f"{pos.quantity:,.8f}",
                f"${pos.cost_basis:,.2f}",
                f"${pos.total_cost:,.2f}",
                str(pos.trade_count),
            )

        console.print(table)

    asyncio.run(_positions())


@app.command(name="pnl")
def show_pnl() -> None:
    """Show portfolio with unrealized P&L."""

    async def _pnl() -> None:
        settings = get_settings()
        db = DatabaseConnection(
            db_path=settings.database.path,
            schema_path=settings.database.schema_path,
        )
        await db.initialize()

        repo = Repository(db)
        manager = PortfolioManager(repo, db)

        positions = await manager.get_positions_with_pnl()

        if not positions:
            console.print("[yellow]No positions with market data.[/yellow]")
            console.print("Run: [cyan]cryptopilot collect[/cyan] to fetch prices.")
            return

        table = Table(title="Portfolio P&L")
        table.add_column("Symbol", style="cyan")
        table.add_column("Quantity", justify="right")
        table.add_column("Cost Basis", justify="right")
        table.add_column("Current Price", justify="right")
        table.add_column("Market Value", justify="right")
        table.add_column("P&L ($)", justify="right")
        table.add_column("P&L (%)", justify="right")

        for symbol, pos in positions.items():
            pnl_color = "green" if pos.unrealized_pnl >= 0 else "red"

            table.add_row(
                symbol,
                f"{pos.quantity:,.8f}",
                f"${pos.cost_basis:,.2f}",
                f"${pos.current_price:,.2f}",
                f"${pos.market_value:,.2f}",
                f"[{pnl_color}]${pos.unrealized_pnl:+,.2f}[/{pnl_color}]",
                f"[{pnl_color}]{pos.unrealized_pnl_pct:+.2f}%[/{pnl_color}]",
            )

        console.print(table)

        # Summary
        summary = await manager.get_portfolio_summary()
        console.print("\n[bold]Portfolio Summary[/bold]")
        console.print(f"Total Value: ${summary['total_value']:,.2f}")
        console.print(f"Total Cost:  ${summary['total_cost']:,.2f}")

        pnl_color = "green" if summary["total_pnl"] >= 0 else "red"
        console.print(
            f"Total P&L:   [{pnl_color}]${summary['total_pnl']:+,.2f} "
            f"({summary['total_pnl_pct']:+.2f}%)[/{pnl_color}]"
        )

    asyncio.run(_pnl())
