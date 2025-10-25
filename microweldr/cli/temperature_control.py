"""Temperature control commands for MicroWeldr CLI."""

import logging
import sys
from pathlib import Path
from typing import Optional

import click

from ..core.config import Config, ConfigError
from ..core.constants import (
    ConfigKeys,
    ConfigSections,
    DefaultValues,
    ErrorMessages,
    GCodeCommands,
)
from ..prusalink.client import PrusaLinkClient
from ..prusalink.exceptions import PrusaLinkError

logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--secrets-config",
    "-s",
    type=click.Path(exists=True, path_type=Path),
    default="secrets.toml",
    help="Path to secrets configuration file",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default="config.toml",
    help="Path to main configuration file",
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
def temp_off(
    secrets_config: Path,
    config: Path,
    bed_only: bool,
    nozzle_only: bool,
    chamber_only: bool,
    cooldown_temp: Optional[int],
    force: bool,
):
    """Turn off printer temperatures for safe handling.

    This command safely cools down the printer by setting temperatures
    to safe levels. Useful after welding operations or for maintenance.
    """
    try:
        # Load configuration
        main_config = Config(config)

        # Get cooldown temperature from config or use provided value
        if cooldown_temp is None:
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
                sys.exit(0)

        # Connect to printer
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
                    sys.exit(0)

            # Generate G-code commands
            gcode_commands = []
            gcode_commands.append("; MicroWeldr Temperature Cooldown")
            gcode_commands.append(f"; Generated at {click.DateTime().now()}")
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

                        # Monitor for a few seconds
                        import time

                        click.echo("⏱️  Monitoring cooldown...")
                        for i in range(5):
                            time.sleep(1)
                            current_status = client.get_status()
                            click.echo(
                                f"   Bed: {current_status.bed_actual}°C, Nozzle: {current_status.nozzle_actual}°C"
                            )

                        click.echo("✅ Temperature cooldown initiated successfully")
                    else:
                        click.echo("⚠️  G-code uploaded but failed to start", err=True)
                else:
                    click.echo(
                        f"❌ Failed to upload G-code: {result.get('error', 'Unknown error')}",
                        err=True,
                    )
                    sys.exit(1)

            finally:
                # Clean up temporary file
                Path(temp_gcode_path).unlink(missing_ok=True)

        except PrusaLinkError as e:
            click.echo(f"❌ Printer communication error: {e}", err=True)
            click.echo("💡 Tip: Check printer connection and secrets configuration")
            sys.exit(1)

    except ConfigError as e:
        click.echo(f"❌ Configuration error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        logger.exception("Temperature control failed")
        sys.exit(1)


@click.command()
@click.option(
    "--secrets-config",
    "-s",
    type=click.Path(exists=True, path_type=Path),
    default="secrets.toml",
    help="Path to secrets configuration file",
)
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default="config.toml",
    help="Path to main configuration file",
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
def temp_on(
    secrets_config: Path,
    config: Path,
    bed_temp: Optional[int],
    nozzle_temp: Optional[int],
    chamber_temp: Optional[int],
    wait: bool,
    force: bool,
):
    """Turn on printer temperatures for welding operations.

    This command heats up the printer to welding temperatures.
    Useful before starting welding operations.
    """
    try:
        # Load configuration
        main_config = Config(config)

        # Get temperatures from config if not provided
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
            sys.exit(1)

        # Show heating targets
        click.echo(f"🌡️  Temperature Control: Heating Up")
        click.echo(
            f"Targets: Bed → {bed_temp}°C, Nozzle → {nozzle_temp}°C, Chamber → {chamber_temp}°C"
        )

        # Confirmation
        if not force:
            if not click.confirm("Continue with temperature heating?"):
                click.echo("❌ Temperature control cancelled")
                sys.exit(0)

        # Connect to printer
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
                    sys.exit(0)

            # Generate G-code commands
            gcode_commands = []
            gcode_commands.append("; MicroWeldr Temperature Heating")
            gcode_commands.append(f"; Generated at {click.DateTime().now()}")
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
                        else:
                            # Just monitor for a few seconds
                            import time

                            click.echo("⏱️  Monitoring heating startup...")
                            for i in range(3):
                                time.sleep(2)
                                current_status = client.get_status()
                                click.echo(
                                    f"   Bed: {current_status.bed_actual}°C → {bed_temp}°C, "
                                    f"Nozzle: {current_status.nozzle_actual}°C → {nozzle_temp}°C"
                                )

                        click.echo("✅ Temperature heating initiated successfully")
                    else:
                        click.echo("⚠️  G-code uploaded but failed to start", err=True)
                else:
                    click.echo(
                        f"❌ Failed to upload G-code: {result.get('error', 'Unknown error')}",
                        err=True,
                    )
                    sys.exit(1)

            finally:
                # Clean up temporary file
                Path(temp_gcode_path).unlink(missing_ok=True)

        except PrusaLinkError as e:
            click.echo(f"❌ Printer communication error: {e}", err=True)
            click.echo("💡 Tip: Check printer connection and secrets configuration")
            sys.exit(1)

    except ConfigError as e:
        click.echo(f"❌ Configuration error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}", err=True)
        logger.exception("Temperature control failed")
        sys.exit(1)


if __name__ == "__main__":
    # For testing
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "off":
        temp_off()
    elif len(sys.argv) > 1 and sys.argv[1] == "on":
        temp_on()
    else:
        click.echo("Usage: python temperature_control.py [on|off]")
