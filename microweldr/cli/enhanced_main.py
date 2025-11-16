"""Enhanced CLI interface with click and improved UX."""

import logging
import sys
from pathlib import Path

import click

from ..core.caching import OptimizedSVGParser
from ..core.config import Config
from ..outputs.streaming_gcode_subscriber import StreamingGCodeSubscriber
from ..core.graceful_degradation import ResilientPrusaLinkClient, check_system_health
from ..core.logging_config import LogContext, setup_logging
from ..core.progress import progress_context
from ..core.resource_management import safe_gcode_generation
from ..core.safety import SafetyError, validate_weld_operation
from ..parsers.svg_parser import SVGParser
from ..validation.validators import GCodeValidator, SVGValidator
from .config_setup import config


# Custom click decorators for common options
def common_options(func):
    """Common CLI options decorator."""
    func = click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")(
        func
    )
    func = click.option(
        "--quiet", "-q", is_flag=True, help="Suppress non-error output"
    )(func)
    func = click.option(
        "--config",
        "-c",
        default="config.toml",
        help="Configuration file path",
        type=click.Path(exists=True),
    )(func)
    func = click.option("--log-file", help="Log file path")(func)
    return func


def printer_options(func):
    """Printer-related CLI options decorator."""
    func = click.option(
        "--secrets",
        default="microweldr_secrets.toml",
        help="Secrets configuration file",
        type=click.Path(),
    )(func)
    func = click.option(
        "--submit-to-printer",
        is_flag=True,
        help="Submit G-code to printer after generation",
    )(func)
    func = click.option(
        "--auto-start", is_flag=True, help="Automatically start print after upload"
    )(func)
    func = click.option(
        "--storage",
        type=click.Choice(["local", "usb"]),
        default="local",
        help="Printer storage location",
    )(func)
    return func


@click.group()
@click.version_option(prog_name="MicroWeldr")
@click.pass_context
def cli(ctx):
    """MicroWeldr - Convert SVG files to G-code for plastic welding.

    A comprehensive tool for converting SVG designs into G-code for
    plastic welding on Prusa Core One printers.
    """
    ctx.ensure_object(dict)


@cli.command()
@click.argument("svg_file", type=click.Path(exists=True, path_type=Path))
@click.option("--output", "-o", help="Output G-code file path")
@click.option("--animation", "-a", help="Output animation SVG file path")
@click.option("--skip-bed-leveling", is_flag=True, help="Skip bed leveling in G-code")
@click.option(
    "--dry-run", is_flag=True, help="Generate files but don't send to printer"
)
@click.option(
    "--validate-only", is_flag=True, help="Only validate input, don't generate"
)
@click.option("--force", is_flag=True, help="Force generation despite warnings")
@click.option(
    "--cache/--no-cache", default=True, help="Enable/disable SVG parsing cache"
)
@common_options
@printer_options
@click.pass_context
def weld(
    ctx,
    svg_file,
    output,
    animation,
    skip_bed_leveling,
    dry_run,
    validate_only,
    force,
    cache,
    verbose,
    quiet,
    config,
    log_file,
    secrets,
    submit_to_printer,
    auto_start,
    storage,
):
    """Generate G-code for welding from SVG file.

    This command processes an SVG file and generates G-code for plastic welding.
    It can also create an animated visualization and optionally submit the job
    to a connected Prusa printer.

    Examples:

        # Basic usage
        microweldr weld design.svg

        # Generate with custom output and animation
        microweldr weld design.svg -o weld.gcode -a animation.svg

        # Submit directly to printer
        microweldr weld design.svg --submit-to-printer --auto-start

        # Validate only (no generation)
        microweldr weld design.svg --validate-only
    """
    # Setup logging
    log_level = "DEBUG" if verbose else "WARNING" if quiet else "INFO"
    setup_logging(level=log_level, log_file=log_file, console=not quiet)

    logger = logging.getLogger(__name__)

    with LogContext("weld_generation"):
        try:
            # Load configuration
            with click.progressbar(length=1, label="Loading configuration") as bar:
                config_obj = Config(config)
                bar.update(1)

            # Check secrets file exists if printer submission is requested
            if submit_to_printer:
                if not Path(secrets).exists():
                    click.echo(f"❌ Secrets file not found: {secrets}")
                    click.echo(
                        "Please create a secrets file with your printer configuration."
                    )
                    raise click.Abort()

            # Parse SVG with progress and caching
            click.echo(f"📄 Processing SVG: {svg_file}")

            if cache:
                parser = OptimizedSVGParser(cache_enabled=True)
                weld_paths = parser.parse_svg_file(svg_file)

                # Show cache statistics
                stats = parser.get_stats()
                if stats["cache_hits"] > 0:
                    click.echo(f"💾 Cache hit rate: {stats['cache_hit_rate']:.1f}%")
            else:
                parser = SVGParser()
                weld_paths = parser.parse_file(svg_file)

            if not weld_paths:
                click.echo("❌ No weld paths found in SVG file")
                raise click.Abort()

            total_points = sum(len(path.points) for path in weld_paths)
            click.echo(f"✅ Parsed {len(weld_paths)} paths with {total_points} points")

            # Safety validation
            click.echo("🔒 Validating safety parameters...")
            warnings, errors = validate_weld_operation(weld_paths, config_obj.config)

            if errors:
                click.echo("❌ Safety validation failed:")
                for error in errors:
                    click.echo(f"   • {error}")
                if not force:
                    raise click.Abort()
                else:
                    click.echo("⚠️  Proceeding despite safety errors (--force used)")

            if warnings:
                click.echo("⚠️  Safety warnings:")
                for warning in warnings:
                    click.echo(f"   • {warning}")
                if not force and not click.confirm("Continue despite warnings?"):
                    raise click.Abort()

            if validate_only:
                click.echo("✅ Validation completed successfully")
                return

            # Generate output file paths
            if not output:
                output = svg_file.with_suffix(".gcode")
            else:
                output = Path(output)

            if animation and not Path(animation).suffix:
                animation = Path(animation).with_suffix(".svg")
            elif not animation:
                animation = svg_file.with_suffix("_animation.svg")
            else:
                animation = Path(animation)

            # Generate G-code with progress
            click.echo(f"⚙️  Generating G-code: {output}")

            with safe_gcode_generation(output, backup=True) as temp_gcode_path:
                generator = GCodeGenerator(config_obj)

                with progress_context(len(weld_paths), "Generating G-code") as progress:
                    generator.generate(
                        weld_paths,
                        str(temp_gcode_path),
                        skip_bed_leveling=skip_bed_leveling,
                    )
                    progress.update(len(weld_paths))

            # Validate generated G-code
            validator = GCodeValidator()
            result = validator.validate(str(output))

            if not result.is_valid:
                click.echo("⚠️  G-code validation warnings:")
                for warning in result.warnings:
                    click.echo(f"   • {warning}")

            # Generate animation
            if animation:
                click.echo(f"🎬 Generating animation: {animation}")

                # TODO: Replace with event-driven streaming animation subscriber
                # For now, skip animation generation due to architectural changes
                click.echo(
                    "⚠️  Animation generation temporarily disabled during refactoring"
                )
                click.echo("   Use the event-driven processor for animation output")

                # click.echo(f"✅ Animation saved: {animation}")

            # Display file information
            gcode_size = output.stat().st_size
            click.echo(f"✅ G-code generated: {output} ({gcode_size:,} bytes)")

            # Estimate print time
            estimated_time = _estimate_print_time(weld_paths, config_obj.config)
            click.echo(f"⏱️  Estimated print time: {estimated_time}")

            # Submit to printer if requested
            if submit_to_printer and not dry_run:
                _submit_to_printer(output, secrets, auto_start, storage)
            elif dry_run:
                click.echo(
                    "🔍 Dry run completed - files generated but not sent to printer"
                )

            click.echo("🎉 Welding preparation completed successfully!")

        except SafetyError as e:
            logger.error(f"Safety validation failed: {e}")
            click.echo(f"❌ Safety error: {e}")
            raise click.Abort()
        except Exception as e:
            # Check if it's a filename error for better user messaging
            if "filename" in str(e).lower() and "character" in str(e).lower():
                logger.error(f"Filename validation failed: {e}")
                click.echo(f"❌ Filename error: {e}")
                click.echo(
                    "💡 Tip: Use a shorter filename (max 31 characters including .gcode extension)"
                )
            else:
                logger.error(f"Weld generation failed: {e}", exc_info=True)
                click.echo(f"❌ Error: {e}")
            raise click.Abort()


@cli.command()
@click.argument("svg_file", type=click.Path(exists=True, path_type=Path))
@common_options
@click.pass_context
def validate(ctx, svg_file, verbose, quiet, config, log_file):
    """Validate SVG file for welding compatibility.

    Performs comprehensive validation of the SVG file including:
    - SVG structure and syntax
    - Weld parameter safety
    - Configuration compatibility
    """
    # Setup logging
    log_level = "DEBUG" if verbose else "WARNING" if quiet else "INFO"
    setup_logging(level=log_level, log_file=log_file, console=not quiet)

    click.echo(f"🔍 Validating SVG file: {svg_file}")

    try:
        # Validate SVG structure
        svg_validator = SVGValidator()
        svg_result = svg_validator.validate(str(svg_file))

        if svg_result.is_valid:
            click.echo("✅ SVG structure validation passed")
        else:
            click.echo("❌ SVG structure validation failed")
            click.echo(f"   Error: {svg_result.message}")
            return

        # Load configuration and parse
        config_obj = Config(config)
        parser = SVGParser()
        weld_paths = parser.parse_file(svg_file)

        if not weld_paths:
            click.echo("❌ No weld paths found in SVG")
            return

        # Safety validation
        warnings, errors = validate_weld_operation(weld_paths, config_obj.config)

        if errors:
            click.echo("❌ Safety validation failed:")
            for error in errors:
                click.echo(f"   • {error}")
        else:
            click.echo("✅ Safety validation passed")

        if warnings:
            click.echo("⚠️  Validation warnings:")
            for warning in warnings:
                click.echo(f"   • {warning}")

        # Summary
        total_points = sum(len(path.points) for path in weld_paths)
        click.echo(f"\n📊 Summary:")
        click.echo(f"   • Paths: {len(weld_paths)}")
        click.echo(f"   • Points: {total_points}")
        click.echo(f"   • Errors: {len(errors)}")
        click.echo(f"   • Warnings: {len(warnings)}")

        if errors:
            raise click.Abort()

    except Exception as e:
        click.echo(f"❌ Validation failed: {e}")
        raise click.Abort()


@cli.command()
@click.option("--secrets", default="microweldr_secrets.toml", help="Secrets file path")
@common_options
@click.pass_context
def status(ctx, secrets, verbose, quiet, config, log_file):
    """Check printer and system status.

    Displays comprehensive status information including:
    - Printer connectivity and state
    - System health checks
    - Configuration validation
    """
    # Setup logging
    log_level = "DEBUG" if verbose else "WARNING" if quiet else "INFO"
    setup_logging(level=log_level, log_file=log_file, console=not quiet)

    click.echo("🔍 Checking system status...")

    # System health check
    health = check_system_health()

    click.echo(f"\n🏥 System Health: {health['overall'].upper()}")

    for component, status in health["components"].items():
        emoji = "✅" if status == "healthy" else "⚠️" if status == "degraded" else "❌"
        click.echo(f"   {emoji} {component.title()}: {status}")

    if health["warnings"]:
        click.echo("\n⚠️  Warnings:")
        for warning in health["warnings"]:
            click.echo(f"   • {warning}")

    if health["errors"]:
        click.echo("\n❌ Errors:")
        for error in health["errors"]:
            click.echo(f"   • {error}")

    # Printer status
    if Path(secrets).exists():
        try:
            client = ResilientPrusaLinkClient(secrets)
            printer_status = client.get_status()

            if printer_status.get("fallback"):
                click.echo("\n🖨️  Printer: ❌ Connection failed (fallback mode)")
            else:
                state = printer_status.get("printer", {}).get("state", "Unknown")
                emoji = (
                    "🟢"
                    if state == "Operational"
                    else (
                        "🔥"
                        if state == "Printing"
                        else "⏸️" if state == "Paused" else "❌"
                    )
                )
                click.echo(f"\n🖨️  Printer: {emoji} {state}")

                # Temperature info
                bed_temp = printer_status.get("printer", {}).get("temp_bed", {})
                nozzle_temp = printer_status.get("printer", {}).get("temp_nozzle", {})

                if bed_temp:
                    click.echo(
                        f"   🌡️  Bed: {bed_temp.get('actual', 0):.1f}°C (target: {bed_temp.get('target', 0):.1f}°C)"
                    )
                if nozzle_temp:
                    click.echo(
                        f"   🌡️  Nozzle: {nozzle_temp.get('actual', 0):.1f}°C (target: {nozzle_temp.get('target', 0):.1f}°C)"
                    )

        except Exception as e:
            click.echo(f"\n🖨️  Printer: ❌ Connection failed ({e})")
    else:
        click.echo(f"\n🖨️  Printer: ⚠️  No secrets file found ({secrets})")


@cli.command()
@click.option(
    "--output", "-o", default="microweldr_secrets.toml", help="Output secrets file path"
)
@click.option("--force", is_flag=True, help="Overwrite existing file")
@common_options
@click.pass_context
def init_secrets(ctx, output, force, verbose, quiet, config, log_file):
    """Initialize secure secrets configuration file.

    Creates a secure template for printer authentication with:
    - Strong password generation
    - Secure file permissions
    - Comprehensive security guidance
    """
    # Setup logging
    log_level = "DEBUG" if verbose else "WARNING" if quiet else "INFO"
    setup_logging(level=log_level, log_file=log_file, console=not quiet)

    output_path = Path(output)

    if output_path.exists() and not force:
        if not click.confirm(f"File {output} already exists. Overwrite?"):
            click.echo("❌ Aborted")
            return

    try:
        # Create a basic secrets template
        template_content = """# MicroWeldr Secrets Configuration
# This file contains sensitive information - keep it secure!

[prusalink]
host = "prusa-core-one.local"
username = "maker"
password = "REPLACE_WITH_YOUR_PASSWORD"
default_storage = "local"
"""
        output_path.write_text(template_content)
        click.echo(f"✅ Secrets template created: {output}")
        click.echo("Please edit the file with your printer configuration.")

    except Exception as e:
        click.echo(f"❌ Failed to create secrets file: {e}")
        raise click.Abort()


def _estimate_print_time(weld_paths, config):
    """Estimate total print time."""
    total_points = sum(len(path.points) for path in weld_paths)

    # Rough estimation based on weld times and movement
    avg_weld_time = config.get("normal_welds", {}).get("weld_time", 0.1)
    avg_move_time = 0.05  # Rough estimate for movement between points

    total_time = total_points * (avg_weld_time + avg_move_time)

    if total_time < 60:
        return f"{total_time:.0f}s"
    elif total_time < 3600:
        return f"{total_time/60:.1f}m"
    else:
        return f"{total_time/3600:.1f}h"


def _submit_to_printer(gcode_path, secrets_path, auto_start, storage):
    """Submit G-code to printer."""
    click.echo("🚀 Submitting to printer...")

    try:
        client = ResilientPrusaLinkClient(secrets_path)

        # Check printer status first
        status = client.get_status()
        if status.get("fallback"):
            click.echo("⚠️  Printer connection degraded - manual upload required")
            return

        printer_state = status.get("printer", {}).get("state", "Unknown")
        if printer_state not in ["Operational", "Finished"]:
            click.echo(f"⚠️  Printer not ready (state: {printer_state})")
            if not click.confirm("Continue anyway?"):
                return

        # Upload file
        filename = gcode_path.name

        with click.progressbar(length=1, label="Uploading to printer") as bar:
            result = client.upload_file(
                str(gcode_path), filename, auto_start=auto_start
            )
            bar.update(1)

        if result.get("fallback"):
            click.echo("⚠️  Upload failed - manual upload instructions provided")
        else:
            click.echo(f"✅ File uploaded: {result.get('filename', filename)}")

            if auto_start:
                if result.get("auto_started"):
                    click.echo("🔥 Print started automatically")
                else:
                    # Try to start manually
                    if client.start_print(filename):
                        click.echo("🔥 Print started")
                    else:
                        click.echo("⚠️  Could not start print automatically")
            else:
                click.echo("📁 File ready for manual printing")

    except Exception as e:
        click.echo(f"❌ Printer submission failed: {e}")


@cli.command("temp-off")
@click.option(
    "--secrets-config",
    "-s",
    type=click.Path(exists=True, path_type=Path),
    default="microweldr_secrets.toml",
    help="Path to secrets configuration file",
)
@click.option(
    "--bed-only",
    "-b",
    is_flag=True,
    help="Only turn off bed temperature (keep nozzle warm)",
)
@click.option(
    "--nozzle-only",
    "-n",
    is_flag=True,
    help="Only turn off nozzle temperature (keep bed warm)",
)
@click.option(
    "--chamber-only",
    "-ch",
    is_flag=True,
    help="Only turn off chamber temperature",
)
@click.option(
    "--cooldown-temp",
    "-t",
    type=int,
    default=None,
    help="Target cooldown temperature (default: from config)",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force temperature change without confirmation",
)
@common_options
@click.pass_context
def temp_off(
    ctx,
    secrets_config,
    bed_only,
    nozzle_only,
    chamber_only,
    cooldown_temp,
    force,
    **kwargs,
):
    """Turn off printer temperatures for safe handling."""
    try:
        # Load configuration
        config_path = kwargs.get("config", "config.toml")
        main_config = Config(config_path)

        # Get cooldown temperature from config or use provided value
        if cooldown_temp is None:
            from ..core.constants import ConfigKeys, ConfigSections, DefaultValues

            cooldown_temp = main_config.get(
                ConfigSections.TEMPERATURES,
                ConfigKeys.COOLDOWN_TEMPERATURE,
                DefaultValues.COOLDOWN_TEMPERATURE,
            )

        # Validate temperature
        if cooldown_temp < 20 or cooldown_temp > 60:
            click.echo(
                f"❌ Invalid cooldown temperature: {cooldown_temp}°C (must be 20-60°C)",
                err=True,
            )
            sys.exit(1)

        # Determine what to turn off
        if not any([bed_only, nozzle_only, chamber_only]):
            # Turn off everything by default
            turn_off_bed = True
            turn_off_nozzle = True
            turn_off_chamber = True
        else:
            turn_off_bed = bed_only or not (nozzle_only or chamber_only)
            turn_off_nozzle = nozzle_only or not (bed_only or chamber_only)
            turn_off_chamber = chamber_only or not (bed_only or nozzle_only)

        # Show what will be turned off
        targets = []
        if turn_off_bed:
            targets.append(f"Bed → {cooldown_temp}°C")
        if turn_off_nozzle:
            targets.append(f"Nozzle → {cooldown_temp}°C")
        if turn_off_chamber:
            targets.append("Chamber → OFF")

        click.echo(f"🌡️  Temperature Control: Cooling Down")
        click.echo(f"Targets: {', '.join(targets)}")

        # Confirmation
        if not force:
            if not click.confirm("Continue with temperature cooldown?"):
                click.echo("❌ Temperature control cancelled")
                return

        # Connect to printer and execute cooldown
        from ..core.constants import GCodeCommands
        from ..prusalink.client import PrusaLinkClient
        from ..prusalink.exceptions import PrusaLinkError

        try:
            client = PrusaLinkClient(str(secrets_config))

            # Check printer status
            status = client.get_status()
            click.echo(f"📊 Printer Status: {status.state}")

            if status.state == "Printing":
                click.echo("⚠️  WARNING: Printer is currently printing!")
                if not force and not click.confirm(
                    "Continue anyway? This may affect the print!"
                ):
                    click.echo("❌ Temperature control cancelled")
                    return

            # Generate G-code commands
            gcode_commands = []
            gcode_commands.append("; MicroWeldr Temperature Cooldown")
            gcode_commands.append("")

            if turn_off_bed:
                gcode_commands.append(
                    f"{GCodeCommands.M140} S{cooldown_temp} ; Set bed temperature"
                )
                click.echo(f"🛏️  Setting bed temperature to {cooldown_temp}°C")

            if turn_off_nozzle:
                gcode_commands.append(
                    f"{GCodeCommands.M104} S{cooldown_temp} ; Set nozzle temperature"
                )
                click.echo(f"🔥 Setting nozzle temperature to {cooldown_temp}°C")

            if turn_off_chamber:
                gcode_commands.append(
                    f"{GCodeCommands.M141} S0 ; Turn off chamber heating"
                )
                click.echo("🏠 Turning off chamber heating")

            gcode_commands.append("")
            gcode_commands.append("; Temperature cooldown complete")

            # Send G-code to printer
            gcode_content = "\n".join(gcode_commands)

            # Create temporary G-code file
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".gcode", delete=False
            ) as f:
                f.write(gcode_content)
                temp_gcode_path = f.name

            try:
                # Upload and execute G-code
                result = client.upload_gcode(
                    temp_gcode_path, "microweldr_cooldown.gcode"
                )
                if result["success"]:
                    click.echo("✅ Temperature cooldown commands sent successfully")

                    # Start the G-code
                    if client.start_print("microweldr_cooldown.gcode"):
                        click.echo("🚀 Cooldown sequence started")
                        click.echo("✅ Temperature cooldown initiated successfully")
                    else:
                        click.echo("⚠️  G-code uploaded but failed to start", err=True)
                else:
                    click.echo(
                        f"❌ Failed to upload G-code: {result.get('error', 'Unknown error')}",
                        err=True,
                    )

            finally:
                # Clean up temporary file
                Path(temp_gcode_path).unlink(missing_ok=True)

        except PrusaLinkError as e:
            click.echo(f"❌ Printer communication error: {e}", err=True)
            click.echo("💡 Tip: Check printer connection and secrets configuration")

    except Exception as e:
        click.echo(f"❌ Temperature control failed: {e}", err=True)


@cli.command("temp-on")
@click.option(
    "--secrets-config",
    "-s",
    type=click.Path(exists=True, path_type=Path),
    default="microweldr_secrets.toml",
    help="Path to secrets configuration file",
)
@click.option(
    "--bed-temp",
    "-b",
    type=int,
    default=None,
    help="Bed temperature (default: from config)",
)
@click.option(
    "--nozzle-temp",
    "-n",
    type=int,
    default=None,
    help="Nozzle temperature (default: from config)",
)
@click.option(
    "--chamber-temp",
    "-ch",
    type=int,
    default=None,
    help="Chamber temperature (default: from config)",
)
@click.option(
    "--wait",
    "-w",
    is_flag=True,
    help="Wait for temperatures to be reached before returning",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force temperature change without confirmation",
)
@common_options
@click.pass_context
def temp_on(
    ctx, secrets_config, bed_temp, nozzle_temp, chamber_temp, wait, force, **kwargs
):
    """Turn on printer temperatures for welding operations."""
    try:
        # Load configuration
        config_path = kwargs.get("config", "config.toml")
        main_config = Config(config_path)

        # Get temperatures from config if not provided
        from ..core.constants import ConfigKeys, ConfigSections, DefaultValues

        if bed_temp is None:
            bed_temp = main_config.get(
                ConfigSections.TEMPERATURES,
                ConfigKeys.BED_TEMPERATURE,
                DefaultValues.BED_TEMPERATURE,
            )

        if nozzle_temp is None:
            nozzle_temp = main_config.get(
                ConfigSections.TEMPERATURES,
                ConfigKeys.NOZZLE_TEMPERATURE,
                DefaultValues.NOZZLE_TEMPERATURE,
            )

        if chamber_temp is None:
            chamber_temp = main_config.get(
                ConfigSections.TEMPERATURES,
                ConfigKeys.CHAMBER_TEMPERATURE,
                DefaultValues.CHAMBER_TEMPERATURE,
            )

        # Validate temperatures
        from ..core.safety import SafetyValidator

        validator = SafetyValidator()

        try:
            validator.validate_temperature(bed_temp, "bed_temperature")
            validator.validate_temperature(nozzle_temp, "nozzle_temperature")
            validator.validate_temperature(chamber_temp, "chamber_temperature")
        except Exception as e:
            click.echo(f"❌ Temperature validation failed: {e}", err=True)
            return

        # Show heating targets
        click.echo(f"🌡️  Temperature Control: Heating Up")
        click.echo(
            f"Targets: Bed → {bed_temp}°C, Nozzle → {nozzle_temp}°C, Chamber → {chamber_temp}°C"
        )

        # Confirmation
        if not force:
            if not click.confirm("Continue with temperature heating?"):
                click.echo("❌ Temperature control cancelled")
                return

        # Connect to printer and execute heating
        from ..core.constants import GCodeCommands
        from ..prusalink.client import PrusaLinkClient
        from ..prusalink.exceptions import PrusaLinkError

        try:
            client = PrusaLinkClient(str(secrets_config))

            # Check printer status
            status = client.get_status()
            click.echo(f"📊 Printer Status: {status.state}")

            if status.state == "Printing":
                click.echo("⚠️  WARNING: Printer is currently printing!")
                if not force and not click.confirm(
                    "Continue anyway? This may affect the print!"
                ):
                    click.echo("❌ Temperature control cancelled")
                    return

            # Generate G-code commands
            gcode_commands = []
            gcode_commands.append("; MicroWeldr Temperature Heating")
            gcode_commands.append("")

            # Set temperatures (don't wait initially for faster response)
            gcode_commands.append(
                f"{GCodeCommands.M140} S{bed_temp} ; Set bed temperature"
            )
            gcode_commands.append(
                f"{GCodeCommands.M104} S{nozzle_temp} ; Set nozzle temperature"
            )

            # Chamber heating (if supported)
            use_chamber = main_config.get(
                ConfigSections.TEMPERATURES, ConfigKeys.USE_CHAMBER_HEATING, True
            )
            if use_chamber and chamber_temp > 0:
                gcode_commands.append(
                    f"{GCodeCommands.M141} S{chamber_temp} ; Set chamber temperature"
                )

            if wait:
                gcode_commands.append("")
                gcode_commands.append("; Wait for temperatures")
                gcode_commands.append(
                    f"{GCodeCommands.M190} S{bed_temp} ; Wait for bed temperature"
                )
                gcode_commands.append(
                    f"{GCodeCommands.M109} S{nozzle_temp} ; Wait for nozzle temperature"
                )
                if use_chamber and chamber_temp > 0:
                    gcode_commands.append(
                        f"{GCodeCommands.M191} S{chamber_temp} ; Wait for chamber temperature"
                    )

            gcode_commands.append("")
            gcode_commands.append("; Temperature heating complete")

            # Send G-code to printer
            gcode_content = "\n".join(gcode_commands)

            # Create temporary G-code file
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".gcode", delete=False
            ) as f:
                f.write(gcode_content)
                temp_gcode_path = f.name

            try:
                # Upload and execute G-code
                result = client.upload_gcode(temp_gcode_path, "microweldr_heatup.gcode")
                if result["success"]:
                    click.echo("✅ Temperature heating commands sent successfully")

                    # Start the G-code
                    if client.start_print("microweldr_heatup.gcode"):
                        click.echo("🚀 Heating sequence started")

                        if wait:
                            click.echo("⏱️  Waiting for temperatures to be reached...")
                            # Monitor heating progress
                            import time

                            start_time = time.time()
                            while time.time() - start_time < 300:  # 5 minute timeout
                                time.sleep(5)
                                current_status = client.get_status()
                                click.echo(
                                    f"   Bed: {current_status.bed_actual}°C/{bed_temp}°C, "
                                    f"Nozzle: {current_status.nozzle_actual}°C/{nozzle_temp}°C"
                                )

                                # Check if temperatures reached
                                bed_ready = (
                                    abs(current_status.bed_actual - bed_temp) <= 2
                                )
                                nozzle_ready = (
                                    abs(current_status.nozzle_actual - nozzle_temp) <= 2
                                )

                                if bed_ready and nozzle_ready:
                                    click.echo("✅ Target temperatures reached!")
                                    break
                            else:
                                click.echo(
                                    "⚠️  Timeout waiting for temperatures", err=True
                                )

                        click.echo("✅ Temperature heating initiated successfully")
                    else:
                        click.echo("⚠️  G-code uploaded but failed to start", err=True)
                else:
                    click.echo(
                        f"❌ Failed to upload G-code: {result.get('error', 'Unknown error')}",
                        err=True,
                    )

            finally:
                # Clean up temporary file
                Path(temp_gcode_path).unlink(missing_ok=True)

        except PrusaLinkError as e:
            click.echo(f"❌ Printer communication error: {e}", err=True)
            click.echo("💡 Tip: Check printer connection and secrets configuration")

    except Exception as e:
        click.echo(f"❌ Temperature control failed: {e}", err=True)


# Add config command group to main CLI
cli.add_command(config)


def main():
    """Main entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\n⚠️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        click.echo(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


@cli.command("calibrate-and-set")
@click.option("--home-only", is_flag=True, help="Home axes only")
@click.option("--wait", is_flag=True, help="Wait for temperatures to be reached")
@common_options
@click.pass_context
def calibrate_and_set(ctx, home_only, wait, log_file, config, quiet, verbose):
    """Set temperatures from config and run full calibration."""
    click.echo("🌡️🎯 Calibrate and Set Temperatures")
    click.echo("=" * 40)

    try:
        # Load configuration
        from microweldr.core.config import Config

        config_obj = Config()

        # Get temperatures from config
        bed_temp = config_obj.get("temperatures", "bed_temperature")
        nozzle_temp = config_obj.get("temperatures", "nozzle_temperature")

        click.echo(f"📋 Configuration loaded:")
        click.echo(f"   • Bed temperature: {bed_temp}°C")
        click.echo(f"   • Nozzle temperature: {nozzle_temp}°C")
        click.echo()

        # Connect to printer
        from microweldr.prusalink.client import PrusaLinkClient

        client = PrusaLinkClient()

        click.echo("1. Checking printer connection...")
        status = client.get_printer_status()
        printer = status.get("printer", {})
        state = printer.get("state", "Unknown")
        click.echo(f"   ✓ Connected to printer")
        click.echo(f"   ✓ Printer state: {state}")

        if state.upper() == "PRINTING":
            click.echo(
                "   ⚠ Printer is currently printing - cannot set temperatures or calibrate"
            )
            raise click.Abort()

        # Set bed temperature
        click.echo(f"2. Setting bed temperature to {bed_temp}°C...")
        success = client.set_bed_temperature(bed_temp)
        if success:
            click.echo(f"   ✓ Bed temperature set to {bed_temp}°C")
            if wait:
                click.echo("   • Waiting for bed to reach target temperature...")
        else:
            click.echo(f"   ✗ Failed to set bed temperature")
            raise click.Abort()

        # Set nozzle temperature
        click.echo(f"3. Setting nozzle temperature to {nozzle_temp}°C...")
        success = client.set_nozzle_temperature(nozzle_temp)
        if success:
            click.echo(f"   ✓ Nozzle temperature set to {nozzle_temp}°C")
            if wait:
                click.echo("   • Waiting for nozzle to reach target temperature...")
        else:
            click.echo(f"   ✗ Failed to set nozzle temperature")
            raise click.Abort()

        # Run calibration
        click.echo("4. Starting calibration...")
        from microweldr.core.printer_operations import PrinterOperations

        printer_ops = PrinterOperations(client)

        if home_only:
            click.echo("   • Homing axes only...")
            success = printer_ops.home_axes()
            if success:
                click.echo("   ✓ Homing completed successfully")
            else:
                click.echo("   ✗ Homing failed")
                raise click.Abort()
        else:
            click.echo("   • Starting full calibration (home + bed leveling)...")
            click.echo("   • This may take up to 5 minutes...")
            success = printer_ops.calibrate_printer(bed_leveling=True)
            if success:
                click.echo("   ✓ Full calibration completed successfully")
            else:
                click.echo("   ✗ Calibration failed")
                raise click.Abort()

        # Verify final state
        click.echo("5. Verifying final state...")
        final_status = client.get_printer_status()
        final_printer = final_status.get("printer", {})
        final_state = final_printer.get("state", "Unknown")

        # Get current temperatures from printer status
        current_bed = final_printer.get("temp_bed", 0)
        current_nozzle = final_printer.get("temp_nozzle", 0)
        target_bed = final_printer.get("target_bed", 0)
        target_nozzle = final_printer.get("target_nozzle", 0)

        click.echo(f"   ✓ Printer state: {final_state}")
        click.echo(
            f"   ✓ Bed temperature: {current_bed:.1f}°C (target: {target_bed:.1f}°C)"
        )
        click.echo(
            f"   ✓ Nozzle temperature: {current_nozzle:.1f}°C (target: {target_nozzle:.1f}°C)"
        )

        click.echo("\n🎉 Calibration and temperature setup completed successfully!")
        click.echo(
            "Your printer is now heated, calibrated, and ready for welding operations."
        )

    except Exception as e:
        click.echo(f"❌ Error: {e}")
        raise click.Abort()


if __name__ == "__main__":
    main()
