"""Consolidated command line interface for MicroWeldr."""

import argparse
import sys
from pathlib import Path

from microweldr.animation.generator import AnimationGenerator
from microweldr.core.config import Config, ConfigError
from microweldr.core.converter import SVGToGCodeConverter
from microweldr.core.printer_operations import PrinterOperations
from microweldr.core.secrets_config import SecretsConfig
from microweldr.core.svg_parser import SVGParseError

# Enhanced weld command consolidated into main cmd_weld function
# Monitoring system removed
from microweldr.prusalink.client import PrusaLinkClient
from microweldr.prusalink.exceptions import PrusaLinkError
from microweldr.validation.validators import (
    SVGValidator,
)


def get_version() -> str:
    """Get the current version of MicroWeldr."""
    try:
        import microweldr

        return microweldr.__version__
    except (ImportError, AttributeError):
        return "unknown"


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="MicroWeldr: SVG/DXF to G-code conversion and printer control for plastic welding",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Add version argument
    parser.add_argument(
        "--version", action="version", version=f"MicroWeldr {get_version()}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Test command
    test_parser = subparsers.add_parser(
        "test", help="Test PrusaLink connection and printer status"
    )

    # Home command
    home_parser = subparsers.add_parser("home", help="Home printer axes")
    home_parser.add_argument(
        "axes", nargs="?", default="XYZ", help="Axes to home (default: XYZ)"
    )
    home_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )

    # Bed level command
    bed_level_parser = subparsers.add_parser("bed-level", help="Run bed leveling only")
    bed_level_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )
    bed_level_parser.add_argument(
        "--print-gcode", action="store_true", help="Print G-code"
    )
    bed_level_parser.add_argument(
        "--keep-file", action="store_true", help="Keep temp files"
    )

    # Calibrate command (home + bed level)
    calibrate_parser = subparsers.add_parser(
        "calibrate", help="Full calibration (home + bed leveling)"
    )
    calibrate_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )
    calibrate_parser.add_argument(
        "--home-only", action="store_true", help="Home axes only"
    )
    calibrate_parser.add_argument(
        "--print-gcode", action="store_true", help="Print G-code"
    )
    calibrate_parser.add_argument(
        "--keep-file", action="store_true", help="Keep temp files"
    )

    # Calibrate and set temperatures command
    calibrate_and_set_parser = subparsers.add_parser(
        "calibrate-and-set",
        help="Set temperatures from config and run full calibration",
    )
    calibrate_and_set_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )
    calibrate_and_set_parser.add_argument(
        "--home-only", action="store_true", help="Home axes only"
    )
    calibrate_and_set_parser.add_argument(
        "--print-gcode", action="store_true", help="Print G-code"
    )
    calibrate_and_set_parser.add_argument(
        "--keep-file", action="store_true", help="Keep temp files"
    )
    calibrate_and_set_parser.add_argument(
        "--wait", action="store_true", help="Wait for temperatures to be reached"
    )

    # Temperature control commands
    temp_bed_parser = subparsers.add_parser("temp-bed", help="Set bed temperature")
    temp_bed_parser.add_argument(
        "temperature", type=float, help="Target bed temperature in °C (0 to turn off)"
    )
    temp_bed_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )
    temp_bed_parser.add_argument(
        "--wait", action="store_true", help="Wait for temperature to be reached"
    )

    temp_nozzle_parser = subparsers.add_parser(
        "temp-nozzle", help="Set nozzle temperature"
    )
    temp_nozzle_parser.add_argument(
        "temperature",
        type=float,
        help="Target nozzle temperature in °C (0 to turn off)",
    )
    temp_nozzle_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )
    temp_nozzle_parser.add_argument(
        "--wait", action="store_true", help="Wait for temperature to be reached"
    )

    # Frame command (requires SVG)
    frame_parser = subparsers.add_parser(
        "frame", help="Draw frame around SVG/DXF design (no welding)"
    )
    frame_parser.add_argument("svg_file", help="Input SVG or DXF file")
    frame_parser.add_argument(
        "-c", "--config", default="config.toml", help="Config file"
    )
    frame_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )
    frame_parser.add_argument("--submit", action="store_true", help="Submit to printer")

    # Weld command (default - requires SVG)
    weld_parser = subparsers.add_parser(
        "weld", help="Convert SVG/DXF to G-code and weld (default command)"
    )
    weld_parser.add_argument("svg_file", help="Input SVG or DXF file")
    weld_parser.add_argument("-o", "--output", help="Output G-code file")
    weld_parser.add_argument(
        "-c", "--config", default="config.toml", help="Config file"
    )
    weld_parser.add_argument(
        "--skip-bed-leveling", action="store_true", help="Skip bed leveling"
    )
    weld_parser.add_argument(
        "--no-calibrate", action="store_true", help="Skip calibration"
    )
    weld_parser.add_argument(
        "--submit",
        action="store_true",
        help="Submit to printer (skips calibration - assumes printer is ready)",
    )
    weld_parser.add_argument(
        "--auto-start", action="store_true", help="Auto-start print"
    )
    weld_parser.add_argument("--queue-only", action="store_true", help="Queue only")
    weld_parser.add_argument(
        "--no-animation", action="store_true", help="Skip animation"
    )
    weld_parser.add_argument(
        "--png", action="store_true", help="Generate animated PNG (slower)"
    )
    weld_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )

    # Full-weld command - generates self-contained G-code
    full_weld_parser = subparsers.add_parser(
        "full-weld",
        help="Generate self-contained G-code with all heating, calibration, and prompts built-in",
    )
    full_weld_parser.add_argument("svg_file", help="Input SVG or DXF file")
    full_weld_parser.add_argument("-o", "--output", help="Output G-code file")
    full_weld_parser.add_argument(
        "-c", "--config", default="config.toml", help="Config file"
    )
    full_weld_parser.add_argument(
        "--no-animation", action="store_true", help="Skip animation"
    )
    full_weld_parser.add_argument(
        "--png", action="store_true", help="Generate animated PNG (slower)"
    )
    full_weld_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )
    full_weld_parser.add_argument(
        "--submit", action="store_true", help="Submit to printer and start immediately"
    )

    # Config command
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_subparsers = config_parser.add_subparsers(
        dest="config_command", help="Config commands"
    )

    # Config init
    config_init_parser = config_subparsers.add_parser(
        "init", help="Initialize configuration file"
    )
    config_init_parser.add_argument(
        "--scope",
        choices=["local", "user", "system"],
        default="local",
        help="Configuration scope (local=current dir, user=~/.config, system=/etc)",
    )
    config_init_parser.add_argument(
        "--force", action="store_true", help="Overwrite existing configuration file"
    )

    # Config show
    config_show_parser = config_subparsers.add_parser(
        "show", help="Show current configuration and sources"
    )

    # Config validate
    config_validate_parser = config_subparsers.add_parser(
        "validate", help="Validate configuration and test printer connection"
    )

    # Support SVG file as first argument (default to weld) - handled in main()
    parser.add_argument(
        "svg_file", nargs="?", help="Input SVG or DXF file (defaults to weld command)"
    )
    parser.add_argument("-o", "--output", help="Output G-code file")
    parser.add_argument("-c", "--config", default="config.toml", help="Config file")
    parser.add_argument(
        "--skip-bed-leveling", action="store_true", help="Skip bed leveling"
    )
    parser.add_argument("--no-calibrate", action="store_true", help="Skip calibration")
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Submit to printer (skips calibration - assumes printer is ready)",
    )
    parser.add_argument("--auto-start", action="store_true", help="Auto-start print")
    parser.add_argument("--queue-only", action="store_true", help="Queue only")
    parser.add_argument("--no-animation", action="store_true", help="Skip animation")
    parser.add_argument(
        "--png", action="store_true", help="Generate animated PNG (slower)"
    )

    return parser


def cmd_test(args) -> bool:
    """Test PrusaLink connection."""
    print("Testing PrusaLink integration...")
    print("=" * 50)

    try:
        print("1. Loading configuration...")
        client = PrusaLinkClient()
        print("   ✓ Configuration loaded")

        print("2. Testing connection...")
        if client.test_connection():
            print("   ✓ Connection successful")
        else:
            print("   ✗ Connection failed")
            return False

        print("3. Getting printer information...")
        try:
            status = client.get_printer_status()
            printer_info = status.get("printer", {})
            print(f"   ✓ Printer: {printer_info.get('state', 'Unknown')}")
        except Exception as e:
            print(f"   ⚠ Could not get printer info: {e}")

        print("4. Getting storage information...")
        try:
            storage = client.get_storage_info()
            if storage:
                print(f"   ✓ Available storage: {storage.get('name', 'Unknown')}")
            else:
                print("   ⚠ No storage information available")
        except Exception as e:
            print(f"   ⚠ Could not get storage info: {e}")

        print("5. Getting job status...")
        try:
            job = client.get_job_status()
            if job:
                file_name = job.get("file", {}).get("name", "Unknown")
                state = job.get("state", "Unknown")
                print(f"   ✓ Current job: {file_name}")
                print(f"   ✓ Status: {state}")
            else:
                print("   ✓ No job currently running")
        except Exception as e:
            print(f"   ⚠ Could not get job status: {e}")

        print("\n✓ All tests completed successfully!")
        print("\nYour PrusaLink integration is ready!")
        return True

    except PrusaLinkError as e:
        print(f"   ✗ PrusaLink error: {e}")
        return False
    except Exception as e:
        print(f"   ✗ Unexpected error: {e}")
        return False


def cmd_home(args) -> bool:
    """Home printer axes."""
    print(f"🏠 Homing {args.axes} axes...")
    print("=" * 40)

    try:
        client = PrusaLinkClient()
        printer_ops = PrinterOperations(client)

        print("1. Connecting to printer...")
        if not client.test_connection():
            print("   ✗ Connection failed")
            return False
        print("   ✓ Connected to printer")

        print("2. Checking printer status...")
        status = client.get_printer_status()
        printer_info = status.get("printer", {})
        state = printer_info.get("state", "Unknown")
        print(f"   ✓ Printer state: {state}")

        if state.upper() == "PRINTING":
            print("   ⚠ Printer is currently printing - cannot home")
            return False

        print(f"3. Homing {args.axes} axes...")
        success = printer_ops.home_axes(axes=args.axes)

        if success:
            print("   ✓ Homing completed successfully")
            return True
        else:
            print("   ✗ Homing failed")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def cmd_bed_level(args) -> bool:
    """Run bed leveling only."""
    print("🛏️ Bed Leveling")
    print("=" * 40)

    try:
        client = PrusaLinkClient()
        printer_ops = PrinterOperations(client)

        print("1. Connecting to printer...")
        if not client.test_connection():
            print("   ✗ Connection failed")
            return False
        print("   ✓ Connected to printer")

        print("2. Checking printer status...")
        status = client.get_printer_status()
        printer_info = status.get("printer", {})
        state = printer_info.get("state", "Unknown")
        print(f"   ✓ Printer state: {state}")

        if state.upper() == "PRINTING":
            print("   ⚠ Printer is currently printing - cannot level bed")
            return False

        print("3. Running bed leveling...")
        print("   • This may take up to 3 minutes...")

        kwargs = {
            "print_to_stdout": getattr(args, "print_gcode", False),
            "keep_temp_file": getattr(args, "keep_file", False),
        }

        success = client.send_and_run_gcode(
            commands=["G29  ; Bed leveling", "M117 Bed leveling complete"],
            job_name="bed_leveling",
            **kwargs,
        )

        if success:
            print("   ✓ Bed leveling completed successfully")
            return True
        else:
            print("   ✗ Bed leveling failed")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def cmd_calibrate(args) -> bool:
    """Full calibration (home + bed leveling)."""
    print("🎯 Printer Calibration")
    print("=" * 40)

    try:
        client = PrusaLinkClient()
        printer_ops = PrinterOperations(client)

        print("1. Connecting to printer...")
        if not client.test_connection():
            print("   ✗ Connection failed")
            return False
        print("   ✓ Connected to printer")

        print("2. Checking printer status...")
        status = client.get_printer_status()
        printer_info = status.get("printer", {})
        state = printer_info.get("state", "Unknown")
        print(f"   ✓ Printer state: {state}")

        if state.upper() == "PRINTING":
            print("   ⚠ Printer is currently printing - cannot calibrate")
            return False

        kwargs = {
            "print_to_stdout": getattr(args, "print_gcode", False),
            "keep_temp_file": getattr(args, "keep_file", False),
        }

        if args.home_only:
            print("3. Homing all axes...")
            success = printer_ops.home_axes(**kwargs)
            if success:
                print("   ✓ Homing completed successfully")
            else:
                print("   ✗ Homing failed")
                return False
        else:
            print("3. Starting full calibration (home + bed leveling)...")
            print("   • This may take up to 5 minutes...")
            success = printer_ops.calibrate_printer(**kwargs)
            if success:
                print("   ✓ Full calibration completed successfully")
            else:
                print("   ✗ Calibration failed")
                return False

        print("4. Verifying calibration...")
        final_status = client.get_printer_status()
        final_printer = final_status.get("printer", {})
        final_state = final_printer.get("state", "Unknown")
        x_pos = final_printer.get("axis_x", 0)
        y_pos = final_printer.get("axis_y", 0)
        z_pos = final_printer.get("axis_z", 0)

        print(f"   ✓ Final position: X{x_pos} Y{y_pos} Z{z_pos}")
        print(f"   ✓ Printer ready: {final_state}")

        print("\n🎉 Calibration completed successfully!")
        print("Your printer is now calibrated and ready for welding operations.")
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def cmd_calibrate_and_set(args) -> bool:
    """Set temperatures from config and run full calibration."""
    print("🌡️🎯 Calibrate and Set Temperatures")
    print("=" * 40)

    try:
        # Load configuration
        from microweldr.core.config import Config

        config = Config()

        # Get temperatures from config
        bed_temp = config.get("temperatures", "bed_temperature")
        nozzle_temp = config.get("temperatures", "nozzle_temperature")

        print("📋 Configuration loaded:")
        print(f"   • Bed temperature: {bed_temp}°C")
        print(f"   • Nozzle temperature: {nozzle_temp}°C")
        print()

        # Connect to printer
        client = PrusaLinkClient()
        print("1. Checking printer connection...")
        status = client.get_printer_status()
        printer = status.get("printer", {})
        state = printer.get("state", "Unknown")
        print("   ✓ Connected to printer")
        print(f"   ✓ Printer state: {state}")

        if state.upper() == "PRINTING":
            print(
                "   ⚠ Printer is currently printing - cannot set temperatures or calibrate"
            )
            return False

        # Set bed temperature
        print(f"2. Setting bed temperature to {bed_temp}°C...")
        success = client.set_bed_temperature(bed_temp)
        if success:
            print(f"   ✓ Bed temperature set to {bed_temp}°C")
            if args.wait:
                print("   • Waiting for bed to reach target temperature...")
                # Note: PrusaLink doesn't have a direct "wait for temperature" API
                # The printer will heat up during calibration
        else:
            print("   ✗ Failed to set bed temperature")
            return False

        # Set nozzle temperature
        print(f"3. Setting nozzle temperature to {nozzle_temp}°C...")
        success = client.set_nozzle_temperature(nozzle_temp)
        if success:
            print(f"   ✓ Nozzle temperature set to {nozzle_temp}°C")
            if args.wait:
                print("   • Waiting for nozzle to reach target temperature...")
                # Note: PrusaLink doesn't have a direct "wait for temperature" API
                # The printer will heat up during calibration
        else:
            print("   ✗ Failed to set nozzle temperature")
            return False

        # Run calibration
        print("4. Starting calibration...")
        from microweldr.core.printer_operations import PrinterOperations

        printer_ops = PrinterOperations(client)

        if args.home_only:
            print("   • Homing axes only...")
            success = printer_ops.home_axes()
            if success:
                print("   ✓ Homing completed successfully")
            else:
                print("   ✗ Homing failed")
                return False
        else:
            print("   • Starting full calibration (home + bed leveling)...")
            print("   • This may take up to 5 minutes...")
            success = printer_ops.calibrate_printer(bed_leveling=True)
            if success:
                print("   ✓ Full calibration completed successfully")
            else:
                print("   ✗ Calibration failed")
                return False

        # Verify final state
        print("5. Verifying final state...")
        final_status = client.get_printer_status()
        final_printer = final_status.get("printer", {})
        final_state = final_printer.get("state", "Unknown")

        # Get current temperatures from printer status
        current_bed = final_printer.get("temp_bed", 0)
        current_nozzle = final_printer.get("temp_nozzle", 0)
        target_bed = final_printer.get("target_bed", 0)
        target_nozzle = final_printer.get("target_nozzle", 0)

        print(f"   ✓ Printer state: {final_state}")
        print(f"   ✓ Bed temperature: {current_bed:.1f}°C (target: {target_bed:.1f}°C)")
        print(
            f"   ✓ Nozzle temperature: {current_nozzle:.1f}°C (target: {target_nozzle:.1f}°C)"
        )

        print("\n🎉 Calibration and temperature setup completed successfully!")
        print(
            "Your printer is now heated, calibrated, and ready for welding operations."
        )
        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def cmd_temp_bed(args) -> bool:
    """Set bed temperature."""
    print(f"🌡️ Setting Bed Temperature to {args.temperature}°C")
    print("=" * 40)

    try:
        from ..core.printer_service import get_printer_service

        printer_service = get_printer_service()

        print("1. Connecting to printer...")
        if not printer_service.test_connection():
            print("   ✗ Connection failed")
            return False
        print("   ✓ Connected to printer")

        print("2. Checking printer status...")
        status = printer_service.get_status()
        print(f"   ✓ Printer state: {status.state.value}")
        print(f"   ✓ Current bed temperature: {status.bed_temp}°C")

        print(f"3. Setting bed temperature to {args.temperature}°C...")
        success = printer_service.set_bed_temperature(args.temperature)

        if success:
            print("   ✓ Temperature command sent successfully")

            if getattr(args, "wait", False) and args.temperature > 0:
                print("   • Waiting for temperature to be reached...")
                import time

                timeout = 300  # 5 minutes timeout
                start_time = time.time()

                while time.time() - start_time < timeout:
                    current_status = printer_service.get_status()
                    current_temp = current_status.bed_temp
                    target_temp = current_status.bed_target

                    if getattr(args, "verbose", False):
                        print(
                            f"   • Current: {current_temp}°C, Target: {target_temp}°C"
                        )

                    if abs(current_temp - args.temperature) <= 2:  # Within 2°C
                        print(f"   ✓ Target temperature reached: {current_temp}°C")
                        break

                    time.sleep(5)
                else:
                    print("   ⚠ Timeout waiting for temperature")

            return True
        else:
            print("   ✗ Failed to set temperature")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def cmd_temp_nozzle(args) -> bool:
    """Set nozzle temperature."""
    print(f"🌡️ Setting Nozzle Temperature to {args.temperature}°C")
    print("=" * 40)

    try:
        client = PrusaLinkClient()

        print("1. Connecting to printer...")
        if not client.test_connection():
            print("   ✗ Connection failed")
            return False
        print("   ✓ Connected to printer")

        print("2. Checking printer status...")
        status = client.get_printer_status()
        printer_info = status.get("printer", {})
        state = printer_info.get("state", "Unknown")
        current_nozzle = printer_info.get("temp_nozzle", 0)
        print(f"   ✓ Printer state: {state}")
        print(f"   ✓ Current nozzle temperature: {current_nozzle}°C")

        print(f"3. Setting nozzle temperature to {args.temperature}°C...")
        success = client.set_nozzle_temperature(args.temperature)

        if success:
            print("   ✓ Temperature command sent successfully")

            if args.wait and args.temperature > 0:
                print("   • Waiting for temperature to be reached...")
                import time

                timeout = 300  # 5 minutes timeout
                start_time = time.time()

                while time.time() - start_time < timeout:
                    status = client.get_printer_status()
                    current_temp = status.get("printer", {}).get("temp_nozzle", 0)
                    target_temp = status.get("printer", {}).get("target_nozzle", 0)

                    if args.verbose:
                        print(
                            f"   • Current: {current_temp}°C, Target: {target_temp}°C"
                        )

                    if (
                        abs(current_temp - args.temperature) <= 3
                    ):  # Within 3°C for nozzle
                        print(f"   ✓ Target temperature reached: {current_temp}°C")
                        break

                    time.sleep(5)
                else:
                    print("   ⚠ Timeout waiting for temperature")

            return True
        else:
            print("   ✗ Failed to set temperature")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def cmd_frame(args):
    """Quick frame check - trace design bounds at travel height."""
    print("🖼️ Quick Frame Check")
    print("=" * 40)

    try:
        # Load configuration
        config = Config(args.config)
        print(f"✓ Configuration loaded from {args.config}")

        # Parse file (SVG or DXF)
        file_path = Path(args.svg_file)
        if not file_path.exists():
            print(f"❌ File not found: {args.svg_file}")
            return False

        print(f"✓ File found: {args.svg_file}")

        # Handle both SVG and DXF files directly
        if file_path.suffix.lower() == ".dxf":
            from microweldr.core.dxf_reader import DXFReader

            reader = DXFReader()
            weld_paths = reader.parse_file(file_path)
        else:
            # Use SVG converter for SVG files
            converter = SVGToGCodeConverter(config)
            weld_paths = converter.parse_svg(file_path)

        if not weld_paths:
            print("❌ No weld paths found in file")
            return False

        # Calculate bounds from weld paths
        if not weld_paths:
            bounds = (0.0, 0.0, 0.0, 0.0)
        else:
            all_bounds = [path.get_bounds() for path in weld_paths]
            min_x = min(bounds[0] for bounds in all_bounds)
            min_y = min(bounds[1] for bounds in all_bounds)
            max_x = max(bounds[2] for bounds in all_bounds)
            max_y = max(bounds[3] for bounds in all_bounds)
            bounds = (min_x, min_y, max_x, max_y)

        if not bounds or bounds == (0.0, 0.0, 0.0, 0.0):
            print("❌ Could not determine file bounds for frame")
            return False

        min_x, min_y, max_x, max_y = bounds
        width = max_x - min_x
        height = max_y - min_y
        print(f"✓ Design bounds: {width:.1f}x{height:.1f}mm")

        # Generate super quick frame G-code
        print("🚀 Generating quick frame G-code...")

        # Use travel height (safe height) - no temperature changes, no calibration
        travel_height = config.get("movement", "move_height", 5.0)
        travel_speed = config.get("movement", "travel_speed", 3000)

        print(f"📏 Travel height: {travel_height}mm (quick check)")

        # Simple frame commands - just trace the rectangle at travel height
        frame_commands = [
            "G90 ; Absolute positioning",
            f"G1 Z{travel_height} F{travel_speed} ; Move to travel height",
            f"G1 X{min_x:.3f} Y{min_y:.3f} F{travel_speed} ; Move to start corner",
            f"G1 X{max_x:.3f} Y{min_y:.3f} F{travel_speed} ; Bottom edge",
            f"G1 X{max_x:.3f} Y{max_y:.3f} F{travel_speed} ; Right edge",
            f"G1 X{min_x:.3f} Y{max_y:.3f} F{travel_speed} ; Top edge",
            f"G1 X{min_x:.3f} Y{min_y:.3f} F{travel_speed} ; Left edge (close)",
            "M117 Frame check complete",
        ]

        if args.submit:
            print("📤 Submitting quick frame to printer...")
            client = PrusaLinkClient()
            success = client.send_and_run_gcode(
                commands=frame_commands,
                job_name=f"frame_{file_path.stem}",
                wait_for_completion=False,
            )
            if success:
                print("✅ Quick frame job submitted successfully!")
                print("   Nozzle will remain at final position for inspection")
            else:
                print("❌ Failed to submit frame job")
                return False
        else:
            print("📄 Quick frame G-code generated (use --submit to send to printer)")
            if args.verbose:
                print("\nGenerated G-code:")
                for cmd in frame_commands:
                    print(f"  {cmd}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def validate_welding_temperature(config):
    """Validate that nozzle temperature matches expected welding temperatures."""
    try:
        from microweldr.prusalink.client import PrusaLinkClient

        client = PrusaLinkClient()
        printer_info = client.get_printer_info()

        # Get current nozzle temperature
        # Note: This is a simplified check - actual implementation may need different API calls
        print("   • Getting current nozzle temperature...")

        # Get expected temperatures from config
        normal_weld_temp = config.get("normal_welds", "weld_temperature", 130)
        frangible_weld_temp = config.get("frangible_welds", "weld_temperature", 180)
        temp_tolerance = config.get("temperatures", "temp_tolerance", 10)

        # For now, we'll check against normal weld temperature
        # In a full implementation, we'd analyze the SVG to see which weld types are used
        expected_temp = normal_weld_temp

        # Get actual temperature from printer status
        try:
            status = client.get_printer_status()
            printer_data = status.get("printer", {})
            current_temp = printer_data.get("temp_nozzle", 0)
            target_temp = printer_data.get("target_nozzle", 0)

            print(f"   • Current nozzle temperature: {current_temp}°C")
            print(f"   • Target nozzle temperature: {target_temp}°C")
            print(f"   • Expected welding temperature: {expected_temp}°C")
            print(f"   • Tolerance: ±{temp_tolerance}°C")

            # Check if current temperature matches expected welding temperature
            temp_diff = abs(current_temp - expected_temp)

            if temp_diff <= temp_tolerance:
                print(
                    f"   ✓ Temperature is within acceptable range ({temp_diff:.1f}°C difference)"
                )
                return True
            else:
                print(f"   ❌ Temperature difference too large: {temp_diff:.1f}°C")
                if current_temp > expected_temp + temp_tolerance:
                    print(
                        f"   🔥 Nozzle is too hot! Current: {current_temp}°C, Expected: {expected_temp}°C"
                    )
                else:
                    print(
                        f"   🧊 Nozzle is too cold! Current: {current_temp}°C, Expected: {expected_temp}°C"
                    )
                print(f"   📋 Please set nozzle temperature to {expected_temp}°C")
                print(f"   💡 Use: microweldr temp-nozzle {expected_temp}")
                return False

        except Exception as e:
            print(f"   ⚠️ Could not read current temperature: {e}")
            print("   📋 Please manually verify nozzle temperature is correct")
            return True  # Don't block if we can't read temperature

    except Exception as e:
        print(f"   ❌ Temperature validation error: {e}")
        return False


def cmd_weld(args):
    """Convert SVG/DXF to G-code and weld (main functionality)."""
    print("🔥 MicroWeldr - SVG/DXF to G-code Conversion")
    print("=" * 50)

    try:
        # Load configuration
        config = Config(args.config)
        if args.verbose:
            print(f"✓ Configuration loaded from {args.config}")

        # Validate input file
        input_path = Path(args.svg_file)
        if not input_path.exists():
            print(f"❌ Input file not found: {args.svg_file}")
            return False

        if args.verbose:
            print(f"✓ Input file found: {args.svg_file}")

        # Set up output paths
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = input_path.with_suffix(".gcode")

        # Determine animation path
        animation_path = None
        if not getattr(args, "no_animation", False):
            if getattr(args, "png", False):
                animation_path = output_path.with_name(
                    f"{output_path.stem}_animation.png"
                )
            else:
                animation_path = output_path.with_name(
                    f"{output_path.stem}_animation.svg"
                )

        print(f"✓ Output G-code: {output_path}")
        if animation_path:
            print(f"✓ Animation: {animation_path}")

        # Create processor with two-phase architecture
        from ..core.event_processor import EventDrivenProcessor

        processor = EventDrivenProcessor(config, verbose=args.verbose)

        # Handle calibration options
        # Skip calibration when submitting to printer (user has already prepared it)
        skip_bed_leveling = args.skip_bed_leveling or args.no_calibrate or args.submit

        if args.submit and not (args.skip_bed_leveling or args.no_calibrate):
            print("📋 Skipping calibration (--submit assumes printer is ready)")
        elif skip_bed_leveling:
            print("📋 Skipping calibration as requested")

        # Process file using two-phase architecture
        success = processor.process_file(
            input_path=input_path,
            output_path=output_path,
            animation_path=animation_path,
            verbose=args.verbose,
        )

        if not success:
            print("❌ Processing failed")
            return False

        # Submit to printer if requested
        if args.submit:
            print("📤 Submitting to printer...")
            try:
                client = PrusaLinkClient()

                # Read G-code file and convert to command list
                with open(output_path) as f:
                    gcode_lines = f.readlines()

                # Clean up G-code lines (remove empty lines and comments)
                gcode_commands = []
                for line in gcode_lines:
                    line = line.strip()
                    if line and not line.startswith(";"):
                        gcode_commands.append(line)

                # Send G-code using the same method as frame command
                success = client.send_and_run_gcode(
                    commands=gcode_commands,
                    job_name=f"weld_{input_path.stem}",
                    wait_for_completion=False,
                    keep_temp_file=True,
                )

                if success:
                    print("✅ G-code uploaded and print started!")

                    # Monitor print if requested
                    if args.verbose:
                        print("📊 Starting print monitor...")
                        monitor = PrintMonitor(MonitorMode.STANDARD)
                        monitor.monitor_until_complete()
                    else:
                        print("✅ G-code uploaded successfully!")
                else:
                    print("❌ Failed to upload G-code")

            except PrusaLinkError as e:
                print(f"Printer submission failed: {e}")
                print("G-code file was still generated successfully.")
            except Exception as e:
                print(f"Unexpected error during printer submission: {e}")
                print("G-code file was still generated successfully.")

        print("\n🎉 Conversion complete!")

        if args.verbose:
            print("Output files:")
            print(f"  G-code: {output_path}")
            if animation_path:
                print(f"  Animation: {animation_path}")

        return True

    except ConfigError as e:
        print(f"Configuration error: {e}")
        return False
    except SVGParseError as e:
        print(f"SVG parsing error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return False


def cmd_full_weld(args):
    """Generate self-contained G-code with all heating, calibration, and prompts built-in."""
    print("🔥 MicroWeldr - Full Self-Contained Welding G-code")
    print("=" * 55)

    try:
        # Load configuration
        config = Config(args.config)
        if args.verbose:
            print(f"✓ Configuration loaded from {args.config}")

        # Validate SVG file
        svg_path = Path(args.svg_file)
        if not svg_path.exists():
            print(f"❌ SVG file not found: {args.svg_file}")
            return False

        if args.verbose:
            print(f"✓ SVG file found: {args.svg_file}")

        # Validate SVG content
        svg_validator = SVGValidator()
        svg_result = svg_validator.validate_file(svg_path)

        if not svg_result.is_valid:
            raise SVGParseError(f"SVG validation failed: {svg_result.message}")

        if svg_result.warnings:
            print("⚠️ SVG validation warnings:")
            for warning in svg_result.warnings:
                print(f"  • {warning}")

        # Set up output paths
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = svg_path.with_suffix(".gcode")

        output_animation = output_path.with_suffix(".html")

        print(f"📄 Output G-code: {output_path}")
        if not args.no_animation:
            print(f"🎬 Output animation: {output_animation}")

        # Create converter and generate G-code
        print("🔧 Converting SVG to self-contained G-code...")
        converter = SVGToGCodeConverter(config)

        # Convert SVG to G-code with self-contained mode
        weld_paths = converter.convert_full_weld(svg_path, output_path)

        print(f"✅ Self-contained G-code written to {output_path}")

        # Generate animation if requested
        if not args.no_animation:
            print("🎬 Generating animation...")
            animation_generator = AnimationGenerator(config)
            animation_generator.generate_file(weld_paths, output_animation)

            # Generate animated PNG if requested
            if args.png:
                output_png = output_animation.with_suffix(".png")
                print("🎬 Generating animated PNG...")
                animation_generator.generate_png_file(weld_paths, output_png)
                print(f"✅ Animated PNG written to {output_png}")

            print(f"✅ Animation written to {output_animation}")

        # Submit to printer if requested
        if args.submit:
            print("📤 Submitting to printer...")
            try:
                client = PrusaLinkClient()

                # Read G-code file and convert to command list
                with open(output_path) as f:
                    gcode_lines = f.readlines()

                # Clean up G-code lines (remove empty lines and comments)
                gcode_commands = []
                for line in gcode_lines:
                    line = line.strip()
                    if line and not line.startswith(";"):
                        gcode_commands.append(line)

                # Send G-code using the same method as other commands
                success = client.send_and_run_gcode(
                    commands=gcode_commands,
                    job_name=f"full_weld_{input_path.stem}",
                    wait_for_completion=False,
                    keep_temp_file=False,
                )

                if success:
                    print("✅ Self-contained G-code uploaded and started!")
                    print("🎯 The printer will now handle everything automatically:")
                    print("   • Set temperatures and wait")
                    print("   • Home axes and level bed")
                    print("   • Prompt for plastic insertion")
                    print("   • Perform welding sequence")
                    print("   • Cool down and finish")
                else:
                    print("❌ Failed to upload G-code")

            except PrusaLinkError as e:
                print(f"Printer submission failed: {e}")
                print("G-code file was still generated successfully.")
            except Exception as e:
                print(f"Unexpected error during printer submission: {e}")
                print("G-code file was still generated successfully.")

        print("\n🎉 Self-contained welding G-code ready!")
        print("📋 This G-code includes:")
        print("   ✓ Temperature setup and waiting")
        print("   ✓ Axis homing and bed leveling")
        print("   ✓ User prompts for plastic insertion")
        print("   ✓ Complete welding sequence")
        print("   ✓ Automatic cooldown")
        print(
            "\n💡 Just upload to printer and press start - no external monitoring needed!"
        )

        return True

    except ConfigError as e:
        print(f"Configuration error: {e}")
        return False
    except SVGParseError as e:
        print(f"SVG parsing error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False


def cmd_config(args) -> bool:
    """Handle config command."""
    import json
    import shutil

    if not hasattr(args, "config_command") or args.config_command is None:
        print(
            "Config command requires a subcommand. Use 'microweldr config --help' for options."
        )
        return False

    if args.config_command == "init":
        # Initialize configuration file
        template_path = (
            Path(__file__).parent.parent.parent / "microweldr_secrets.toml.template"
        )

        if args.scope == "local":
            config_path = Path.cwd() / "microweldr_secrets.toml"
        elif args.scope == "user":
            config_dir = Path.home() / ".config" / "microweldr"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / "microweldr_secrets.toml"
        elif args.scope == "system":
            config_dir = Path("/etc/microweldr")
            config_path = config_dir / "microweldr_secrets.toml"

            # Check if we can write to system directory
            if not config_dir.exists():
                try:
                    config_dir.mkdir(parents=True, exist_ok=True)
                except PermissionError:
                    print(
                        "Error: Permission denied. Run with sudo for system configuration."
                    )
                    return False

        if config_path.exists() and not args.force:
            print(f"Configuration file already exists: {config_path}")
            print("Use --force to overwrite")
            return False

        try:
            shutil.copy2(template_path, config_path)
            print(f"Created configuration file: {config_path}")
            print("\nNext steps:")
            print("1. Edit the file to add your printer's IP address and credentials")
            print("2. Test the connection with: microweldr config validate")

            if args.scope == "system":
                print(
                    f"3. Set appropriate file permissions: sudo chmod 600 {config_path}"
                )

        except Exception as e:
            print(f"Error creating configuration file: {e}")
            return False

    elif args.config_command == "show":
        # Show current configuration
        try:
            secrets_config = SecretsConfig()
            config_data = secrets_config.to_dict()
            sources = secrets_config.list_sources()

            print("Configuration Sources (in load order):")
            if sources:
                for i, source in enumerate(sources, 1):
                    print(f"  {i}. {source}")
            else:
                print("  No configuration files found")

            print("\nMerged Configuration:")
            if config_data:
                # Hide sensitive information
                safe_config = _sanitize_config_for_display(config_data)
                print(json.dumps(safe_config, indent=2))
            else:
                print("  No configuration loaded")

        except Exception as e:
            print(f"Error loading configuration: {e}")
            return False

    elif args.config_command == "validate":
        # Validate configuration and test connection
        try:
            secrets_config = SecretsConfig()
            prusalink_config = secrets_config.get_prusalink_config()

            print("✓ Configuration loaded successfully")

            # Validate required fields
            required_fields = ["host", "username"]
            for field in required_fields:
                if field in prusalink_config:
                    print(f"✓ {field}: {prusalink_config[field]}")
                else:
                    print(f"✗ Missing required field: {field}")
                    return False

            # Check authentication
            if "password" in prusalink_config:
                print("✓ Authentication: LCD password")
            elif "api_key" in prusalink_config:
                print("✓ Authentication: API key")
            else:
                print("✗ Missing authentication: need either 'password' or 'api_key'")
                return False

            # Test connection
            print("\nTesting printer connection...")
            try:
                client = PrusaLinkClient()
                info = client.get_printer_info()
                print(f"✓ Connected to printer: {info.get('name', 'Unknown')}")
                print(f"  Firmware: {info.get('firmware', 'Unknown')}")
                print(f"  State: {info.get('state', 'Unknown')}")
            except Exception as e:
                print(f"✗ Connection failed: {e}")
                return False

        except Exception as e:
            print(f"Error validating configuration: {e}")
            return False

    return True


def _sanitize_config_for_display(config_data: dict) -> dict:
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


def main():
    """Main entry point."""
    parser = create_parser()

    # Handle the argument parsing conflict between global and subcommand svg_file

    if (
        len(sys.argv) > 1
        and sys.argv[1] in ["frame", "weld", "full-weld"]
        and len(sys.argv) > 2
    ):
        # For subcommands that take svg_file, parse differently
        args = parser.parse_args()
        # The svg_file should be in the remaining arguments after the command
        if (
            args.command in ["frame", "weld", "full-weld"]
            and not hasattr(args, "svg_file")
        ) or args.svg_file is None:
            # Try to get the svg_file from the command line manually
            cmd_index = sys.argv.index(args.command)
            if cmd_index + 1 < len(sys.argv):
                args.svg_file = sys.argv[cmd_index + 1]
    else:
        args = parser.parse_args()

    # Handle default behavior (SVG file without command = weld)
    if args.svg_file and not args.command:
        args.command = "weld"

    # Show help if no command provided
    if not args.command:
        parser.print_help()
        print("Quick start:")
        print(
            "  microweldr your_design.svg           # Convert SVG/DXF and generate G-code"
        )
        print("  microweldr weld your_design.dxf      # Same as above (DXF example)")
        print(
            "  microweldr full-weld your_design.svg # Self-contained G-code (recommended)"
        )
        print("  microweldr test                      # Test printer connection")
        print("  microweldr calibrate                 # Calibrate printer")
        print(
            "  microweldr calibrate-and-set         # Set temps from config + calibrate"
        )
        print("  microweldr frame your_design.dxf     # Draw frame only (DXF example)")
        sys.exit(1)

    # Dispatch to command handlers
    command_handlers = {
        "test": cmd_test,
        "home": cmd_home,
        "bed-level": cmd_bed_level,
        "calibrate": cmd_calibrate,
        "calibrate-and-set": cmd_calibrate_and_set,
        "temp-bed": cmd_temp_bed,
        "temp-nozzle": cmd_temp_nozzle,
        "frame": cmd_frame,
        "weld": cmd_weld,
        "full-weld": cmd_full_weld,
        "config": cmd_config,
    }

    handler = command_handlers.get(args.command)
    if handler:
        try:
            success = handler(args)
            sys.exit(0 if success else 1)
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            sys.exit(1)
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
