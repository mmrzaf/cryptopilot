import asyncio
import logging
from collections.abc import Sequence

import typer
from rich.console import Console

from cryptopilot.cli.formatters import print_collection_header, print_collection_summary
from cryptopilot.collectors.gap_filler import GapFiller
from cryptopilot.collectors.market_data import MarketDataCollector
from cryptopilot.config.settings import get_settings
from cryptopilot.database.connection import DatabaseConnection
from cryptopilot.database.models import Timeframe
from cryptopilot.database.repository import Repository
from cryptopilot.providers.registry import create_provider
from cryptopilot.utils.retry import RetryConfig

console = Console()
logger = logging.getLogger(__name__)

def _parse_symbols(arg: str | None, default_symbols: Sequence[str]) -> list[str]:
    if arg is None:
        return [s.upper() for s in default_symbols]

    parts = [p.strip().upper() for p in arg.split(",") if p.strip()]
    if not parts:
        raise typer.BadParameter("At least one symbol must be provided")
    return parts


def _parse_timeframe(raw: str | None, default_tf: str) -> Timeframe:
    value = (raw or default_tf).strip()
    try:
        return Timeframe(value)
    except ValueError as exc:
        allowed = ", ".join(tf.value for tf in Timeframe)
        raise typer.BadParameter(f"Invalid timeframe '{value}'. Allowed: {allowed}") from exc


async def _run_collect(
    symbols: list[str],
    timeframe: Timeframe,
    days: int,
    update_all: bool,
    provider_name: str,
    dry_run: bool,
) -> None:
    settings = get_settings()

    db = DatabaseConnection(
        db_path=settings.database.path,
        schema_path=settings.database.schema_path,
    )
    await db.initialize()

    repo = Repository(db)

    provider = create_provider(
        provider_name,
        api_key=settings.api.api_key,
        request_timeout=settings.api.request_timeout,
    )
    provider_info = provider.get_info()

    retry_cfg = RetryConfig(
        max_retries=settings.api.max_retries,
        exponential_base=settings.api.retry_backoff,
    )

    collector = MarketDataCollector(
        repository=repo,
        provider=provider,
        provider_name=provider_name,
        base_currency=settings.currency.base_currency,
        batch_size=settings.data.batch_size,
        retry_config=retry_cfg,
    )

    print_collection_header(
        console,
        provider_name=provider_info.name,
        base_url=provider_info.base_url,
        timeframe=timeframe.value,
        base_currency=settings.currency.base_currency,
        symbols=symbols,
        days=days,
        dry_run=dry_run,
    )

    results = await collector.collect(
        symbols=symbols,
        timeframe=timeframe,
        lookback_days=days,
        update_all=update_all,
        dry_run=dry_run,
    )

    print_collection_summary(console, results)

    if dry_run or not results:
        if dry_run:
            console.print("[yellow]DRY RUN:[/yellow] no data was written to the database.")
        return

    if settings.data.gap_fill_check:
        gap_filler = GapFiller(
            repository=repo,
            provider=provider,
            provider_name=provider_name,
            base_currency=settings.currency.base_currency,
            batch_size=settings.data.batch_size,
            retry_config=retry_cfg,
        )

        console.print(
            "[dim]Running data integrity check for recent window (gap detection)...[/dim]"
        )
        total_issues = 0

        for symbol in symbols:
            try:
                check = await gap_filler.detect_gaps_recent(
                    symbol=symbol,
                    timeframe=timeframe,
                    lookback_days=days,
                )
            except Exception as exc:
                logger.exception("Gap check failed for %s: %s", symbol, exc)
                console.print(f"[red]Gap check failed for {symbol}: {exc}[/red]")
                continue

            issues = check.issues_found
            total_issues += issues

            if issues == 0:
                logger.info("Integrity check: no gaps detected for %s %s", symbol, timeframe.value)
            else:
                logger.warning(
                    "Integrity check: %d missing candles across %d gaps for %s %s",
                    issues,
                    len(check.gaps),
                    symbol,
                    timeframe.value,
                )
                console.print(
                    f"[yellow]Integrity: {symbol} {timeframe.value} has "
                    f"{issues} missing candles across {len(check.gaps)} gaps.[/yellow]"
                )

        if total_issues == 0:
            console.print(
                "[green]Data integrity check passed – no gaps detected in the checked window.[/green]"
            )
        else:
            console.print(
                f"[yellow]Data integrity check found {total_issues} missing candles in total.[/yellow]"
            )


def collect_command(
    symbols: str = typer.Option(
        None,
        "--symbols",
        "-s",
        help="Comma-separated list of symbols, e.g. BTC,ETH,SOL. "
        "Defaults to config.data.default_symbols.",
    ),
    timeframe: str = typer.Option(
        None,
        "--timeframe",
        "-t",
        help="Timeframe: 1h, 4h, 1d, 1w. Defaults to config.data.default_timeframe.",
    ),
    days: int = typer.Option(
        None,
        "--days",
        "-d",
        min=1,
        help="Number of days to look back. Defaults to config.data.retention_days.",
    ),
    provider: str = typer.Option(
        None,
        "--provider",
        "-p",
        help="Data provider name. Defaults to config.api.default_provider.",
    ),
    update_all: bool = typer.Option(
        False,
        "--update-all",
        help="Incrementally update from last stored candle to now, "
        "instead of strictly enforcing the --days window.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Fetch data and show what would change, but do not write to the database.",
    ),
) -> None:
    """Collect market data from configured provider into the local database."""
    settings = get_settings()

    symbol_list = _parse_symbols(symbols, settings.data.default_symbols)
    tf = _parse_timeframe(timeframe, settings.data.default_timeframe)
    lookback_days = days if days is not None else settings.data.retention_days
    provider_name = (provider or settings.api.default_provider).lower()

    try:
        asyncio.run(
            _run_collect(
                symbols=symbol_list,
                timeframe=tf,
                days=lookback_days,
                update_all=update_all,
                provider_name=provider_name,
                dry_run=dry_run,
            )
        )
    except Exception as exc:
        logger.exception("Collect command failed: %s", exc)
        raise typer.Exit(code=1) from exc
