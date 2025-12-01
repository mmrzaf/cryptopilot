import logging

import typer
from rich.console import Console
from rich.logging import RichHandler

from cryptopilot.cli.commands.collect import collect_command
from cryptopilot.cli.commands.portfolio import app as portfolio_app
from cryptopilot.cli.commands.system import init as init_command
from cryptopilot.cli.commands.system import status as status_command
from cryptopilot.cli.commands.system import version as version_command

console = Console()

app = typer.Typer(
    name="cryptopilot",
    help="CryptoPilot – your cryptocurrency market co-pilot",
    no_args_is_help=True,
)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the CLI."""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=console,
                rich_tracebacks=True,
                show_time=True,
                show_path=False,
            ),
        ],
    )


@app.callback()
def main(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging output.",
    ),
) -> None:
    """
    Global CLI options.

    This runs before any subcommand and sets up logging.
    """
    setup_logging(verbose)


app.command(name="version")(version_command)
app.command(name="init")(init_command)
app.command(name="status")(status_command)
app.command(name="collect")(collect_command)
app.add_typer(portfolio_app, name="portfolio")

__all__ = ["app"]
