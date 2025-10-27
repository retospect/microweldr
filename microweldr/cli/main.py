"""Consolidated command line interface for MicroWeldr."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from microweldr.animation.generator import AnimationGenerator
from microweldr.core.config import Config, ConfigError
from microweldr.core.converter import SVGToGCodeConverter
from microweldr.core.printer_operations import PrinterOperations
from microweldr.core.svg_parser import SVGParseError
from microweldr.monitoring import MonitorMode, PrintMonitor
from microweldr.prusalink.client import PrusaLinkClient
from microweldr.prusalink.exceptions import PrusaLinkError
from microweldr.validation.validators import (
    AnimationValidator,
    GCodeValidator,
    SVGValidator,
)


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="MicroWeldr: SVG to G-code conversion and printer control for plastic welding",
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
        "frame", help="Draw frame around SVG design (no welding)"
    )
    frame_parser.add_argument("svg_file", help="Input SVG file")
    frame_parser.add_argument(
        "-c", "--config", default="config.toml", help="Config file"
    )
    frame_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )
    frame_parser.add_argument("--submit", action="store_true", help="Submit to printer")

    # Weld command (default - requires SVG)
    weld_parser = subparsers.add_parser(
        "weld", help="Convert SVG to G-code and weld (default command)"
    )
    weld_parser.add_argument("svg_file", help="Input SVG file")
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
    weld_parser.add_argument("--submit", action="store_true", help="Submit to printer")
    weld_parser.add_argument(
        "--auto-start", action="store_true", help="Auto-start print"
    )
    weld_parser.add_argument("--queue-only", action="store_true", help="Queue only")
    weld_parser.add_argument(
        "--no-animation", action="store_true", help="Skip animation"
    )
    weld_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )

    # Support SVG file as first argument (default to weld) - handled in main()
    parser.add_argument(
        "svg_file", nargs="?", help="Input SVG file (defaults to weld command)"
    )
    parser.add_argument("-o", "--output", help="Output G-code file")
    parser.add_argument("-c", "--config", default="config.toml", help="Config file")
    parser.add_argument(
        "--skip-bed-leveling", action="store_true", help="Skip bed leveling"
    )
    parser.add_argument("--no-calibrate", action="store_true", help="Skip calibration")
    parser.add_argument("--submit", action="store_true", help="Submit to printer")
    parser.add_argument("--auto-start", action="store_true", help="Auto-start print")
    parser.add_argument("--queue-only", action="store_true", help="Queue only")
    parser.add_argument("--no-animation", action="store_true", help="Skip animation")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    return parser


def cmd_test(args):
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


def cmd_home(args):
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


def cmd_bed_level(args):
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


def cmd_calibrate(args):
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


def cmd_temp_bed(args):
    """Set bed temperature."""
    print(f"🌡️ Setting Bed Temperature to {args.temperature}°C")
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
        current_bed = printer_info.get("temp_bed", 0)
        print(f"   ✓ Printer state: {state}")
        print(f"   ✓ Current bed temperature: {current_bed}°C")

        print(f"3. Setting bed temperature to {args.temperature}°C...")
        success = client.set_bed_temperature(args.temperature)

        if success:
            print("   ✓ Temperature command sent successfully")

            if args.wait and args.temperature > 0:
                print("   • Waiting for temperature to be reached...")
                import time

                timeout = 300  # 5 minutes timeout
                start_time = time.time()

                while time.time() - start_time < timeout:
                    status = client.get_printer_status()
                    current_temp = status.get("printer", {}).get("temp_bed", 0)
                    target_temp = status.get("printer", {}).get("target_bed", 0)

                    if args.verbose:
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


def cmd_temp_nozzle(args):
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
    """Draw frame around SVG design."""
    print("🖼️ Drawing Frame")
    print("=" * 40)

    try:
        # Load configuration
        config = Config(args.config)
        print(f"✓ Configuration loaded from {args.config}")

        # Parse SVG
        svg_path = Path(args.svg_file)
        if not svg_path.exists():
            print(f"❌ SVG file not found: {args.svg_file}")
            return False

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

        # Create converter and parse SVG
        converter = SVGToGCodeConverter(config)
        converter.parse_svg(svg_path)

        # Get SVG bounds for frame
        bounds = converter.get_bounds()

        if not bounds or bounds == (0.0, 0.0, 0.0, 0.0):
            print("❌ Could not determine SVG bounds for frame")
            return False

        min_x, min_y, max_x, max_y = bounds
        width = max_x - min_x
        height = max_y - min_y
        print(f"✓ SVG bounds: {width:.1f}x{height:.1f}mm")

        # Generate frame G-code
        print("🔧 Generating frame G-code...")

        # Get frame height from config
        frame_height = config.get("movement", "frame_height", 10.0)
        travel_speed = config.get("movement", "travel_speed", 3000)
        z_speed = config.get("movement", "z_speed", 600)

        # Create a simple frame path
        margin = 5.0  # 5mm margin around design
        print(f"📏 Frame height: {frame_height}mm (clearance check)")

        frame_commands = [
            "G90  ; Absolute positioning",
            f"G1 X{min_x - margin} Y{min_y - margin} F{travel_speed}  ; Move to start",
            f"G1 Z{frame_height} F{z_speed}  ; Lower to frame height",
            f"G1 X{max_x + margin} Y{min_y - margin} F{travel_speed}  ; Bottom edge",
            f"G1 X{max_x + margin} Y{max_y + margin} F{travel_speed}  ; Right edge",
            f"G1 X{min_x - margin} Y{max_y + margin} F{travel_speed}  ; Top edge",
            f"G1 X{min_x - margin} Y{min_y - margin} F{travel_speed}  ; Left edge",
            f"G1 Z{config.get('movement', 'move_height', 5.0)} F{z_speed}  ; Lift to safe height",
            "M117 Frame complete",
        ]

        if args.submit:
            print("📤 Submitting frame to printer...")
            client = PrusaLinkClient()
            success = client.send_and_run_gcode(
                commands=frame_commands,
                job_name=f"frame_{svg_path.stem}",
                wait_for_completion=False,
            )
            if success:
                print("✅ Frame job submitted successfully!")
            else:
                print("❌ Failed to submit frame job")
                return False
        else:
            print("📄 Frame G-code generated (use --submit to send to printer)")
            if args.verbose:
                print("\nGenerated G-code:")
                for cmd in frame_commands:
                    print(f"  {cmd}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def cmd_weld(args):
    """Convert SVG to G-code and weld (main functionality)."""
    print("🔥 MicroWeldr - SVG to G-code Conversion")
    print("=" * 50)

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
            output_gcode = Path(args.output)
        else:
            output_gcode = svg_path.with_suffix(".gcode")

        output_animation = output_gcode.with_suffix(".html")

        print(f"📄 Output G-code: {output_gcode}")
        if not args.no_animation:
            print(f"🎬 Output animation: {output_animation}")

        # Create converter and generate G-code
        print("🔧 Converting SVG to G-code...")
        converter = SVGToGCodeConverter(config)

        # Handle calibration options
        skip_bed_leveling = args.skip_bed_leveling or args.no_calibrate

        gcode_content = converter.convert_file(
            svg_path, skip_bed_leveling=skip_bed_leveling
        )

        # Validate G-code
        gcode_validator = GCodeValidator()
        gcode_result = gcode_validator.validate_content(gcode_content)

        if not gcode_result.is_valid:
            print(f"❌ G-code validation failed: {gcode_result.message}")
            print("Generated G-code may not work properly!")

        if gcode_result.warnings:
            print("⚠️ G-code validation warnings:")
            for warning in gcode_result.warnings:
                print(f"  • {warning}")

        # Write G-code file
        with open(output_gcode, "w") as f:
            f.write(gcode_content)
        print(f"✅ G-code written to {output_gcode}")

        # Generate animation if requested
        if not args.no_animation:
            print("🎬 Generating animation...")
            animation_generator = AnimationGenerator(config)
            animation_content = animation_generator.generate_from_gcode(
                gcode_content, svg_path.name
            )

            # Validate animation
            animation_validator = AnimationValidator()
            animation_result = animation_validator.validate_content(animation_content)

            if not animation_result.is_valid:
                print(f"❌ Animation validation failed: {animation_result.message}")
                print("Generated animation may not display properly!")

            if animation_result.warnings:
                print("⚠️ Animation validation warnings:")
                for warning in animation_result.warnings:
                    print(f"  • {warning}")

            with open(output_animation, "w") as f:
                f.write(animation_content)
            print(f"✅ Animation written to {output_animation}")

        # Submit to printer if requested
        if args.submit:
            print("📤 Submitting to printer...")
            try:
                client = PrusaLinkClient()

                # Upload and optionally start print
                upload_success = client.upload_gcode_file(
                    output_gcode, auto_start=args.auto_start, queue_only=args.queue_only
                )

                if upload_success:
                    if args.auto_start:
                        print("✅ G-code uploaded and print started!")

                        # Monitor print if requested
                        if not args.queue_only:
                            print("📊 Starting print monitor...")
                            monitor = PrintMonitor(client, MonitorMode.BASIC)
                            monitor.start_monitoring()
                    elif args.queue_only:
                        print("✅ G-code queued successfully!")
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
            print(f"Output files:")
            print(f"  G-code: {output_gcode}")
            if not args.no_animation:
                print(f"  Animation: {output_animation}")

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


def main():
    """Main entry point."""
    parser = create_parser()

    # Handle the argument parsing conflict between global and subcommand svg_file
    import sys

    if len(sys.argv) > 1 and sys.argv[1] in ["frame", "weld"] and len(sys.argv) > 2:
        # For subcommands that take svg_file, parse differently
        args = parser.parse_args()
        # The svg_file should be in the remaining arguments after the command
        if (
            args.command in ["frame", "weld"]
            and not hasattr(args, "svg_file")
            or args.svg_file is None
        ):
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
        print("\nQuick start:")
        print("  microweldr your_design.svg           # Convert and generate G-code")
        print("  microweldr weld your_design.svg      # Same as above")
        print("  microweldr test                      # Test printer connection")
        print("  microweldr calibrate                 # Calibrate printer")
        print("  microweldr frame your_design.svg     # Draw frame only")
        sys.exit(1)

    # Dispatch to command handlers
    command_handlers = {
        "test": cmd_test,
        "home": cmd_home,
        "bed-level": cmd_bed_level,
        "calibrate": cmd_calibrate,
        "temp-bed": cmd_temp_bed,
        "temp-nozzle": cmd_temp_nozzle,
        "frame": cmd_frame,
        "weld": cmd_weld,
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
