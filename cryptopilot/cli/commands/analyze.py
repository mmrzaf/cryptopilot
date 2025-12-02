"""Analysis CLI commands."""

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from cryptopilot.analysis.engine import AnalysisEngine, InsufficientDataError
from cryptopilot.analysis.registry import get_strategy_info, list_strategies
from cryptopilot.config.settings import get_settings
from cryptopilot.database.connection import DatabaseConnection
from cryptopilot.database.models import ActionType, Timeframe
from cryptopilot.database.repository import Repository

console = Console()
app = typer.Typer(help="Market analysis commands")


def _parse_timeframe(raw: str | None, default_tf: str) -> Timeframe:
    """Parse timeframe string to Timeframe enum."""
    value = (raw or default_tf).strip()
    try:
        return Timeframe(value)
    except ValueError as exc:
        allowed = ", ".join(tf.value for tf in Timeframe)
        raise typer.BadParameter(f"Invalid timeframe '{value}'. Allowed: {allowed}") from exc


@app.command(name="run")
def analyze_symbol(
    symbol: str = typer.Argument(..., help="Symbol to analyze (e.g., BTC, ETH)"),
    strategy: str = typer.Option(
        "trend_following",
        "--strategy",
        "-s",
        help="Strategy to use",
    ),
    timeframe: str = typer.Option(
        None,
        "--timeframe",
        "-t",
        help="Timeframe (1h, 4h, 1d, 1w)",
    ),
    no_save: bool = typer.Option(
        False,
        "--no-save",
        help="Don't save result to database",
    ),
) -> None:
    """Run analysis on a symbol."""

    async def _analyze() -> None:
        settings = get_settings()
        db = DatabaseConnection(
            db_path=settings.database.path,
            schema_path=settings.database.schema_path,
        )
        await db.initialize()

        repo = Repository(db)
        engine = AnalysisEngine(repo)

        tf = _parse_timeframe(timeframe, settings.data.default_timeframe)

        console.print(f"\n[bold cyan]Analyzing {symbol.upper()}[/bold cyan]")
        console.print(f"Strategy: [magenta]{strategy}[/magenta]")
        console.print(f"Timeframe: [magenta]{tf.value}[/magenta]\n")

        try:
            result = await engine.analyze(
                symbol=symbol,
                strategy_name=strategy,
                timeframe=tf,
                provider=settings.api.default_provider,
                save_result=not no_save,
            )

            # Display result
            action_color = {
                ActionType.BUY: "green",
                ActionType.SELL: "red",
                ActionType.HOLD: "yellow",
            }[result.action]

            console.print(
                f"[bold {action_color}]{result.action.value}[/bold {action_color}] "
                f"(Confidence: {result.confidence.value}, "
                f"Score: {result.confidence_score:.2f})\n"
            )

            # Evidence
            console.print("[bold]Evidence:[/bold]")
            for i, ev in enumerate(result.evidence, 1):
                console.print(f"  {i}. {ev}")

            # Risk assessment
            if result.risk_assessment:
                console.print("\n[bold]Risk Assessment:[/bold]")
                for key, value in result.risk_assessment.items():
                    console.print(f"  • {key}: {value}")

            # Market context
            if result.market_context:
                console.print("\n[bold]Market Context:[/bold]")
                for key, value in result.market_context.items():
                    if isinstance(value, (int, float)):
                        console.print(f"  • {key}: {value:.2f}")
                    else:
                        console.print(f"  • {key}: {value}")

            if not no_save:
                console.print("\n[dim]✓ Result saved to database[/dim]")

        except InsufficientDataError as e:
            console.print(f"[red]Insufficient data: {e}[/red]")
            raise typer.Exit(1)
        except Exception as e:
            console.print(f"[red]Analysis failed: {e}[/red]")
            raise typer.Exit(1)

    asyncio.run(_analyze())


@app.command(name="portfolio")
def analyze_portfolio(
    symbols: str = typer.Option(
        None,
        "--symbols",
        "-s",
        help="Comma-separated symbols (defaults to config)",
    ),
    strategy: str = typer.Option(
        "trend_following",
        "--strategy",
        help="Strategy to use",
    ),
    timeframe: str = typer.Option(
        None,
        "--timeframe",
        "-t",
        help="Timeframe",
    ),
) -> None:
    """Run analysis on multiple symbols."""

    async def _analyze_all() -> None:
        settings = get_settings()
        db = DatabaseConnection(
            db_path=settings.database.path,
            schema_path=settings.database.schema_path,
        )
        await db.initialize()

        repo = Repository(db)
        engine = AnalysisEngine(repo)

        symbol_list = (
            [s.strip().upper() for s in symbols.split(",")]
            if symbols
            else [s.upper() for s in settings.data.default_symbols]
        )

        tf = _parse_timeframe(timeframe, settings.data.default_timeframe)

        console.print("\n[bold cyan]Portfolio Analysis[/bold cyan]")
        console.print(f"Symbols: [magenta]{', '.join(symbol_list)}[/magenta]")
        console.print(f"Strategy: [magenta]{strategy}[/magenta]")
        console.print(f"Timeframe: [magenta]{tf.value}[/magenta]\n")

        results = await engine.analyze_portfolio(
            symbols=symbol_list,
            strategy_name=strategy,
            timeframe=tf,
            provider=settings.api.default_provider,
            save_results=True,
        )

        if not results:
            console.print("[yellow]No analysis results available[/yellow]")
            return

        # Display as table
        table = Table(title="Analysis Results")
        table.add_column("Symbol", style="cyan")
        table.add_column("Action", style="bold")
        table.add_column("Confidence", style="magenta")
        table.add_column("Score", justify="right")
        table.add_column("Key Evidence")

        for sym, result in results.items():
            action_color = {
                ActionType.BUY: "green",
                ActionType.SELL: "red",
                ActionType.HOLD: "yellow",
            }[result.action]

            evidence_summary = result.evidence[0] if result.evidence else "—"
            if len(evidence_summary) > 60:
                evidence_summary = evidence_summary[:57] + "..."

            table.add_row(
                sym,
                f"[{action_color}]{result.action.value}[/{action_color}]",
                result.confidence.value,
                f"{result.confidence_score:.2f}",
                evidence_summary,
            )

        console.print(table)
        console.print("\n[dim]✓ Results saved to database[/dim]")

    asyncio.run(_analyze_all())


@app.command(name="history")
def show_history(
    symbol: str = typer.Option(None, "--symbol", "-s", help="Filter by symbol"),
    strategy: str = typer.Option(None, "--strategy", help="Filter by strategy"),
    days: int = typer.Option(30, "--days", "-d", help="Look back N days"),
    limit: int = typer.Option(20, "--limit", "-l", help="Max results to show"),
) -> None:
    """Show analysis history."""

    async def _history() -> None:
        settings = get_settings()
        db = DatabaseConnection(
            db_path=settings.database.path,
            schema_path=settings.database.schema_path,
        )
        await db.initialize()

        repo = Repository(db)
        engine = AnalysisEngine(repo)

        results = await engine.get_analysis_history(
            symbol=symbol,
            strategy=strategy,
            days=days,
            limit=limit,
        )

        if not results:
            console.print("[yellow]No analysis history found[/yellow]")
            return

        table = Table(title=f"Analysis History ({len(results)} results)")
        table.add_column("Date", style="cyan")
        table.add_column("Symbol", style="magenta")
        table.add_column("Strategy")
        table.add_column("Action", style="bold")
        table.add_column("Confidence")
        table.add_column("Score", justify="right")

        for res in results:
            action_color = {
                ActionType.BUY: "green",
                ActionType.SELL: "red",
                ActionType.HOLD: "yellow",
            }[res.action]

            table.add_row(
                res.timestamp.strftime("%Y-%m-%d %H:%M"),
                res.symbol,
                res.strategy,
                f"[{action_color}]{res.action.value}[/{action_color}]",
                res.confidence.value,
                f"{res.confidence_score:.2f}",
            )

        console.print(table)

    asyncio.run(_history())


@app.command(name="strategies")
def list_available_strategies() -> None:
    """List available analysis strategies."""
    strategies = list_strategies()
    info = get_strategy_info()

    console.print("\n[bold cyan]Available Strategies[/bold cyan]\n")

    for strat_name in strategies:
        strat_info = info[strat_name]
        console.print(f"[bold magenta]{strat_name}[/bold magenta]")
        console.print(f"  Class: {strat_info['class']}")
        console.print(f"  Required periods: {strat_info['required_periods']}")

        desc = strat_info["description"].split("\n")[0]  # First line
        if desc:
            console.print(f"  {desc}")
        console.print()


@app.command(name="compare")
def compare_strategies(
    symbol: str = typer.Argument(..., help="Symbol to analyze"),
    timeframe: str = typer.Option(
        None,
        "--timeframe",
        "-t",
        help="Timeframe",
    ),
) -> None:
    """Compare all strategies on a single symbol."""

    async def _compare() -> None:
        settings = get_settings()
        db = DatabaseConnection(
            db_path=settings.database.path,
            schema_path=settings.database.schema_path,
        )
        await db.initialize()

        repo = Repository(db)
        engine = AnalysisEngine(repo)

        tf = _parse_timeframe(timeframe, settings.data.default_timeframe)
        strategies = list_strategies()

        console.print(f"\n[bold cyan]Strategy Comparison: {symbol.upper()}[/bold cyan]")
        console.print(f"Timeframe: [magenta]{tf.value}[/magenta]\n")

        results = {}
        for strategy in strategies:
            try:
                result = await engine.analyze(
                    symbol=symbol,
                    strategy_name=strategy,
                    timeframe=tf,
                    provider=settings.api.default_provider,
                    save_result=False,  # Don't save comparison results
                )
                results[strategy] = result
            except Exception as e:
                console.print(f"[red]✗ {strategy} failed: {e}[/red]")

        if not results:
            console.print("[yellow]No results available[/yellow]")
            return

        # Display comparison table
        table = Table(title="Strategy Comparison")
        table.add_column("Strategy", style="cyan")
        table.add_column("Action", style="bold")
        table.add_column("Confidence", style="magenta")
        table.add_column("Score", justify="right")
        table.add_column("Top Evidence")

        for strategy, result in results.items():
            action_color = {
                ActionType.BUY: "green",
                ActionType.SELL: "red",
                ActionType.HOLD: "yellow",
            }[result.action]

            top_evidence = result.evidence[0] if result.evidence else "—"
            if len(top_evidence) > 50:
                top_evidence = top_evidence[:47] + "..."

            table.add_row(
                strategy,
                f"[{action_color}]{result.action.value}[/{action_color}]",
                result.confidence.value,
                f"{result.confidence_score:.2f}",
                top_evidence,
            )

        console.print(table)

        # Consensus check
        actions = [r.action for r in results.values()]
        if len(set(actions)) == 1:
            consensus_action = actions[0]
            action_color = {
                ActionType.BUY: "green",
                ActionType.SELL: "red",
                ActionType.HOLD: "yellow",
            }[consensus_action]
            console.print(
                f"\n[bold {action_color}]✓ Consensus: All strategies agree on {consensus_action.value}[/bold {action_color}]"
            )
        else:
            console.print("\n[yellow]⚠ No consensus: Strategies disagree[/yellow]")
            buy_count = sum(1 for a in actions if a == ActionType.BUY)
            sell_count = sum(1 for a in actions if a == ActionType.SELL)
            hold_count = sum(1 for a in actions if a == ActionType.HOLD)
            console.print(f"  BUY: {buy_count}, SELL: {sell_count}, HOLD: {hold_count}")

    asyncio.run(_compare())
