from collections.abc import Sequence

from rich.console import Console
from rich.table import Table

from cryptopilot.collectors.market_data import CollectionResult


def print_collection_header(
    console: Console,
    *,
    provider_name: str,
    base_url: str,
    timeframe: str,
    base_currency: str,
    symbols: Sequence[str],
    days: int,
    dry_run: bool,
) -> None:
    symbols_str = ", ".join(symbols)
    console.print(
        "[bold cyan]CryptoPilot – Market Data Collection[/bold cyan]\n",
    )
    console.print(f"Provider: [green]{provider_name}[/green] ([blue]{base_url}[/blue])")
    console.print(f"Symbols : [magenta]{symbols_str}[/magenta]")
    console.print(
        f"Window  : Last [magenta]{days}[/magenta] days @ timeframe [magenta]{timeframe}[/magenta]"
    )
    console.print(f"Base    : [magenta]{base_currency}[/magenta]")
    console.print(f"Dry run : {'[yellow]YES[/yellow]' if dry_run else 'NO'}")
    console.print("")


def print_collection_summary(
    console: Console,
    results: Sequence[CollectionResult],
) -> None:
    if not results:
        console.print("[yellow]No new data to collect – everything is up to date.[/yellow]")
        return

    table = Table(title="Collection Summary")
    table.add_column("Symbol", style="cyan", justify="left")
    table.add_column("Timeframe", style="magenta", justify="center")
    table.add_column("Fetched", style="green", justify="right")
    table.add_column("Inserted", style="green", justify="right")

    total_fetched = 0
    total_inserted = 0

    for res in results:
        table.add_row(
            res.symbol,
            res.timeframe.value,
            str(res.candles_fetched),
            str(res.candles_inserted),
        )
        total_fetched += res.candles_fetched
        total_inserted += res.candles_inserted

    console.print("")
    console.print(table)
    console.print(
        f"\n[bold]Total candles fetched:[/bold] {total_fetched}  •  "
        f"[bold]inserted:[/bold] {total_inserted}"
    )
    console.print("")
