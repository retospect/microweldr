"""Configuration setup utilities for MicroWeldr."""

import shutil
from pathlib import Path
from typing import Optional

import click

from ..core.secrets_config import SecretsConfig


@click.group()
def config():
    """Configuration management commands."""
    pass


@config.command()
@click.option(
    "--scope",
    type=click.Choice(["local", "user", "system"]),
    default="local",
    help="Configuration scope (local=current dir, user=~/.config, system=/etc)",
)
@click.option("--force", is_flag=True, help="Overwrite existing configuration file")
def init(scope: str, force: bool):
    """Initialize a new configuration file from template."""
    template_path = (
        Path(__file__).parent.parent.parent / "microweldr_secrets.toml.template"
    )

    if scope == "local":
        config_path = Path.cwd() / "microweldr_secrets.toml"
    elif scope == "user":
        config_dir = Path.home() / ".config" / "microweldr"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "microweldr_secrets.toml"
    elif scope == "system":
        config_dir = Path("/etc/microweldr")
        config_path = config_dir / "microweldr_secrets.toml"

        # Check if we can write to system directory
        if not config_dir.exists():
            try:
                config_dir.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                click.echo(
                    "Error: Permission denied. Run with sudo for system configuration.",
                    err=True,
                )
                return

    if config_path.exists() and not force:
        click.echo(f"Configuration file already exists: {config_path}")
        click.echo("Use --force to overwrite")
        return

    try:
        shutil.copy2(template_path, config_path)
        click.echo(f"Created configuration file: {config_path}")
        click.echo("\nNext steps:")
        click.echo("1. Edit the file to add your printer's IP address and credentials")
        click.echo("2. Test the connection with: microweldr status")

        if scope == "system":
            click.echo(
                "3. Set appropriate file permissions: sudo chmod 600 {config_path}"
            )

    except Exception as e:
        click.echo(f"Error creating configuration file: {e}", err=True)


@config.command()
def show():
    """Show current configuration and sources."""
    try:
        secrets_config = SecretsConfig()
        config_data = secrets_config.to_dict()
        sources = secrets_config.list_sources()

        click.echo("Configuration Sources (in load order):")
        if sources:
            for i, source in enumerate(sources, 1):
                click.echo(f"  {i}. {source}")
        else:
            click.echo("  No configuration files found")

        click.echo("\nMerged Configuration:")
        if config_data:
            # Hide sensitive information
            safe_config = _sanitize_config(config_data)
            import json

            click.echo(json.dumps(safe_config, indent=2))
        else:
            click.echo("  No configuration loaded")

    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)


@config.command()
def validate():
    """Validate configuration and test printer connection."""
    try:
        secrets_config = SecretsConfig()
        prusalink_config = secrets_config.get_prusalink_config()

        click.echo("✓ Configuration loaded successfully")

        # Validate required fields
        required_fields = ["host", "username"]
        for field in required_fields:
            if field in prusalink_config:
                click.echo(f"✓ {field}: {prusalink_config[field]}")
            else:
                click.echo(f"✗ Missing required field: {field}", err=True)
                return

        # Check authentication
        if "password" in prusalink_config:
            click.echo("✓ Authentication: LCD password")
        elif "api_key" in prusalink_config:
            click.echo("✓ Authentication: API key")
        else:
            click.echo(
                "✗ Missing authentication: need either 'password' or 'api_key'",
                err=True,
            )
            return

        # Test connection
        click.echo("\nTesting printer connection...")
        try:
            from ..prusalink.client import PrusaLinkClient

            client = PrusaLinkClient()
            info = client.get_printer_info()
            click.echo(f"✓ Connected to printer: {info.get('name', 'Unknown')}")
            click.echo(f"  Firmware: {info.get('firmware', 'Unknown')}")
            click.echo(f"  State: {info.get('state', 'Unknown')}")
        except Exception as e:
            click.echo(f"✗ Connection failed: {e}", err=True)

    except Exception as e:
        click.echo(f"Error validating configuration: {e}", err=True)


@config.command()
@click.argument("key")
@click.argument("value", required=False)
def get(key: str, value: Optional[str]):
    """Get or set a configuration value."""
    try:
        secrets_config = SecretsConfig()

        if value is None:
            # Get value
            result = secrets_config.get(key)
            if result is not None:
                # Sanitize sensitive values
                if any(
                    sensitive in key.lower()
                    for sensitive in ["password", "api_key", "secret"]
                ):
                    click.echo(f"{key}: [HIDDEN]")
                else:
                    click.echo(f"{key}: {result}")
            else:
                click.echo(f"Key not found: {key}")
        else:
            click.echo("Setting configuration values is not yet implemented.")
            click.echo("Please edit the configuration files directly.")

    except Exception as e:
        click.echo(f"Error: {e}", err=True)


def _sanitize_config(config_data: dict) -> dict:
    """Remove sensitive information from configuration for display."""
    import copy

    safe_config = copy.deepcopy(config_data)

    # List of sensitive keys to hide
    sensitive_keys = ["password", "api_key", "secret", "token"]

    def sanitize_dict(d):
        if isinstance(d, dict):
            for key, value in d.items():
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    d[key] = "[HIDDEN]"
                elif isinstance(value, dict):
                    sanitize_dict(value)

    sanitize_dict(safe_config)
    return safe_config


if __name__ == "__main__":
    config()
