from __future__ import annotations

import asyncio
from pathlib import Path

from rich.console import Console

from cryptopilot import __version__
from cryptopilot.config.settings import get_settings
from cryptopilot.database.connection import DatabaseConnection

console = Console()


def version() -> None:
    """Show version information."""
    console.print(f"[bold cyan]CryptoPilot[/bold cyan] v{__version__}")
    console.print("Your cryptocurrency market co-pilot")


def init() -> None:
    """Initialize CryptoPilot (config dir, DB, config.toml)."""
    settings = get_settings()

    console.print("[bold cyan]Initializing CryptoPilot...[/bold cyan]")

    config_dir = Path.home() / ".cryptopilot"
    config_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"Created config directory: {config_dir}")

    async def init_db() -> None:
        db = DatabaseConnection(
            db_path=settings.database.path,
            schema_path=settings.database.schema_path,
        )
        await db.initialize()
        schema_version = await db.get_schema_version()
        console.print(f"Initialized database (schema v{schema_version}): {settings.database.path}")

    asyncio.run(init_db())

    config_path = config_dir / "config.toml"
    if not config_path.exists():
        settings.save_to_toml(config_path)
        console.print(f"Created config file: {config_path}")
    else:
        console.print(f"Config file already exists: {config_path}")
    console.print("\n[bold green]✓ Initialization complete![/bold green]")
    console.print("\nNext steps:")
    console.print("1. Edit config file: [cyan]~/.cryptopilot/config.toml[/cyan]")
    console.print("2. Collect data: [cyan]cryptopilot collect --symbols BTC,ETH[/cyan]")
    console.print(
        "3. Record a trade: [cyan]"
        "cryptopilot portfolio trade BTC BUY 0.05 65000 "
        "--fee 5 --account main --notes 'Bought the dip, allegedly'"
        "[/cyan]"
    )


def status() -> None:
    """Show system status and configuration."""
    settings = get_settings()

    console.print("[bold cyan]CryptoPilot Status[/bold cyan]\n")

    async def check_db() -> None:
        db = DatabaseConnection(
            db_path=settings.database.path,
            schema_path=settings.database.schema_path,
        )

        if settings.database.path.exists():
            await db.initialize()
            version = await db.get_schema_version()
            integrity = await db.check_integrity()

            console.print("Database: [green]✓ Ready[/green]")
            # console.print(f"  Path: {settings.database.path}")
            console.print(f"  Schema version: {version}")
            console.print(f"  Integrity: {'✓ OK' if integrity else '✗ FAILED'}")
        else:
            console.print("Database: [yellow]⚠ Not initialized[/yellow]")
            console.print("  Run: [cyan]cryptopilot init[/cyan]")

    asyncio.run(check_db())

    console.print("\nConfiguration:")
    console.print(f"  Default provider: {settings.api.default_provider}")
    console.print(f"  Base currency: {settings.currency.base_currency}")
    console.print(f"  Default symbols: {', '.join(settings.data.default_symbols)}")
    console.print(f"  Debug mode: {'ON' if settings.debug else 'OFF'}")
