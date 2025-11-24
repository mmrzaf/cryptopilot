import asyncio
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler

from cryptopilot.config.settings import get_settings

console = Console()

app = typer.Typer(
    name="cryptopilot",
    help="CryptoPilot - Your cryptocurrency market co-pilot",
    add_completion=False,
)


def setup_logging(debug: bool = False) -> None:
    """Setup logging with Rich handler."""
    level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@app.callback()
def main_callback(
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
) -> None:
    """CryptoPilot - Cryptocurrency Trading Analysis Platform"""
    setup_logging(debug)
    
    settings = get_settings()
    settings.debug = debug


@app.command()
def version() -> None:
    """Show version information."""
    console.print("[bold cyan]CryptoPilot[/bold cyan] v0.1.0")
    console.print("Your cryptocurrency market co-pilot")


@app.command()
def init() -> None:
    """
    Initialize CryptoPilot with interactive configuration.
    Creates config directory, database, and config.toml file.
    """
    from database.connection import DatabaseConnection
    
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
    console.print("1. Edit config: [cyan]cryptopilot config show[/cyan]")
    console.print("2. Collect data: [cyan]cryptopilot collect --symbols BTC,ETH[/cyan]")
    console.print("3. Update portfolio: [cyan]cryptopilot balance update --btc 0.1[/cyan]")


@app.command()
def status() -> None:
    """Show system status and configuration."""
    from database.connection import DatabaseConnection
    
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
            
            console.print(f"Database: [green]✓ Ready[/green]")
            console.print(f"  Path: {settings.database.path}")
            console.print(f"  Schema version: {version}")
            console.print(f"  Integrity: {'✓ OK' if integrity else '✗ FAILED'}")
        else:
            console.print(f"Database: [yellow]⚠ Not initialized[/yellow]")
            console.print(f"  Run: [cyan]cryptopilot init[/cyan]")
    
    asyncio.run(check_db())
    
    console.print(f"\nConfiguration:")
    console.print(f"  Default provider: {settings.api.default_provider}")
    console.print(f"  Base currency: {settings.currency.base_currency}")
    console.print(f"  Default symbols: {', '.join(settings.data.default_symbols)}")
    console.print(f"  Debug mode: {'ON' if settings.debug else 'OFF'}")


@app.command()
def collect() -> None:
    """Collect market data from providers."""
    console.print("[yellow]Collect command not yet implemented[/yellow]")
    console.print("This will be implemented in cli/commands/collect.py")


@app.command()
def analyze() -> None:
    """Analyze market data and portfolio."""
    console.print("[yellow]Analyze command not yet implemented[/yellow]")
    console.print("This will be implemented in cli/commands/analyze.py")


@app.command()
def balance() -> None:
    """Manage portfolio balances."""
    console.print("[yellow]Balance command not yet implemented[/yellow]")
    console.print("This will be implemented in cli/commands/portfolio.py")


if __name__ == "__main__":
    app()
