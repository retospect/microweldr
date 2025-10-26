"""CLI entry point for MicroWeldr UI."""

import sys
from pathlib import Path

import click

from ..ui.curses_ui import MicroWeldrUI


@click.command()
@click.argument(
    "svg_file", type=click.Path(exists=True, path_type=Path), required=False
)
@click.option(
    "--config",
    "-c",
    type=click.Path(path_type=Path),
    help="Configuration file path (default: config.toml)",
)
@click.option(
    "--secrets",
    "-s",
    type=click.Path(path_type=Path),
    help="Secrets file path (default: secrets.toml)",
)
def main(svg_file: Path, config: Path, secrets: Path):
    """
    Launch MicroWeldr interactive terminal UI.

    SVG_FILE: Optional SVG file to load on startup
    """
    try:
        ui = MicroWeldrUI(svg_file=svg_file, config_file=config)
        ui.run()
    except KeyboardInterrupt:
        click.echo("\nExiting MicroWeldr UI...")
        sys.exit(0)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
