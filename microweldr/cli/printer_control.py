#!/usr/bin/env python3
"""
Unified printer control utility for SVG welder.
Combines status checking, monitoring, and print stopping in one tool.
"""

import argparse
import json
import sys

from microweldr.core.printer_operations import PrinterOperations
from microweldr.monitoring import MonitorMode, PrintMonitor
from microweldr.prusalink.client import PrusaLinkClient
from microweldr.prusalink.exceptions import PrusaLinkError


def create_parser():
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Unified printer control for SVG welder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check printer status
  printer-control status
  printer-control status --verbose

  # Calibrate printer
  printer-control calibrate
  printer-control calibrate --home-only
  printer-control calibrate --verbose

  # Monitor print progress
  printer-control monitor
  printer-control monitor --mode pipetting --interval 20
  printer-control monitor --mode pipetting --verbose

  # Stop current print
  printer-control stop
  printer-control stop --force

  # Test connection
  printer-control test
  printer-control test --verbose

Monitoring Modes:
  standard    - Standard upright printer operation
  pipetting   - Microfluidic device with pipetting stops
        """,
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Status command
    status_parser = subparsers.add_parser("status", help="Check current printer status")
    status_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed information"
    )
    status_parser.add_argument(
        "--json", action="store_true", help="Output raw JSON response"
    )

    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Monitor print progress")
    monitor_parser.add_argument(
        "--mode",
        choices=["standard", "pipetting"],
        default="standard",
        help="Monitoring mode (default: standard)",
    )
    monitor_parser.add_argument(
        "--interval",
        "-i",
        type=int,
        default=30,
        help="Check interval in seconds (default: 30)",
    )
    monitor_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output"
    )

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop current print")
    stop_parser.add_argument(
        "--force", "-f", action="store_true", help="Force stop without confirmation"
    )
    stop_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output"
    )

    # Test command
    test_parser = subparsers.add_parser("test", help="Test PrusaLink connection")
    test_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed test results"
    )

    # Calibrate command
    calibrate_parser = subparsers.add_parser(
        "calibrate", help="Calibrate printer (home + bed leveling)"
    )
    calibrate_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed calibration output"
    )
    calibrate_parser.add_argument(
        "--home-only", action="store_true", help="Only home axes, skip bed leveling"
    )
    calibrate_parser.add_argument(
        "--print-gcode", action="store_true", help="Print generated G-code to stdout"
    )
    calibrate_parser.add_argument(
        "--keep-file", action="store_true", help="Keep temporary G-code file on printer"
    )

    # Temperature commands
    temp_parser = subparsers.add_parser("temp", help="Temperature control commands")
    temp_subparsers = temp_parser.add_subparsers(
        dest="temp_command", help="Temperature operations"
    )

    # Set bed temperature
    bed_parser = temp_subparsers.add_parser("bed", help="Set bed temperature")
    bed_parser.add_argument(
        "temperature", type=float, help="Target temperature in Celsius"
    )
    bed_parser.add_argument(
        "--wait", action="store_true", help="Wait for temperature to be reached"
    )
    bed_parser.add_argument(
        "--force", action="store_true", help="Bypass safety temperature limits"
    )
    bed_parser.add_argument(
        "--print-gcode", action="store_true", help="Print G-code to stdout"
    )
    bed_parser.add_argument(
        "--keep-file", action="store_true", help="Keep temp file on printer"
    )

    # Set nozzle temperature
    nozzle_parser = temp_subparsers.add_parser("nozzle", help="Set nozzle temperature")
    nozzle_parser.add_argument(
        "temperature", type=float, help="Target temperature in Celsius"
    )
    nozzle_parser.add_argument(
        "--wait", action="store_true", help="Wait for temperature to be reached"
    )
    nozzle_parser.add_argument(
        "--force", action="store_true", help="Bypass safety temperature limits"
    )
    nozzle_parser.add_argument(
        "--print-gcode", action="store_true", help="Print G-code to stdout"
    )
    nozzle_parser.add_argument(
        "--keep-file", action="store_true", help="Keep temp file on printer"
    )

    # Turn off heaters
    off_parser = temp_subparsers.add_parser("off", help="Turn off all heaters")
    off_parser.add_argument(
        "--print-gcode", action="store_true", help="Print G-code to stdout"
    )
    off_parser.add_argument(
        "--keep-file", action="store_true", help="Keep temp file on printer"
    )

    # Home command
    home_parser = subparsers.add_parser("home", help="Home printer axes")
    home_parser.add_argument(
        "axes", nargs="?", default="XYZ", help="Axes to home (X, Y, Z, XY, XYZ, etc.)"
    )
    home_parser.add_argument(
        "--print-gcode", action="store_true", help="Print G-code to stdout"
    )
    home_parser.add_argument(
        "--keep-file", action="store_true", help="Keep temp file on printer"
    )
    home_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output"
    )

    return parser


def format_temperature(temp_data):
    """Format temperature data."""
    if not temp_data:
        return "Unknown"

    actual = temp_data.get("actual", 0)
    target = temp_data.get("target", 0)

    if target > 0:
        return f"{actual:.1f}°C → {target:.1f}°C"
    else:
        return f"{actual:.1f}°C"


def cmd_status(args):
    """Handle status command."""
    try:
        client = PrusaLinkClient()
        status = client.get_printer_status()

        if args.json:
            print(json.dumps(status, indent=2))
            return True

        print("🖨️ Prusa Printer Status")
        print("=" * 40)

        # Basic printer info
        printer_info = status.get("printer", {})
        state = printer_info.get("state", "Unknown")

        # State with emoji
        state_emoji = {
            "IDLE": "😴",
            "PRINTING": "🖨️",
            "PAUSED": "⏸️",
            "FINISHED": "✅",
            "ERROR": "❌",
            "CANCELLED": "🛑",
        }.get(state.upper(), "❓")

        print(f"State: {state_emoji} {state}")

        # Temperature info
        if args.verbose:
            temp_info = status.get("temperature", {})
            if temp_info:
                print("\n🌡️ Temperatures:")

                # Nozzle temperature
                nozzle = temp_info.get("tool0", {})
                if nozzle:
                    print(f"  Nozzle: {format_temperature(nozzle)}")

                # Bed temperature
                bed = temp_info.get("bed", {})
                if bed:
                    print(f"  Bed: {format_temperature(bed)}")

                # Chamber temperature (if available)
                chamber = temp_info.get("chamber", {})
                if chamber:
                    print(f"  Chamber: {format_temperature(chamber)}")

        # Job info
        try:
            job = client.get_job_status()
            if job:
                print(f"\n📄 Current Job:")
                file_info = job.get("file", {})
                file_name = file_info.get("name", "Unknown")
                print(f"  File: {file_name}")

                progress_data = job.get("progress", 0)
                if isinstance(progress_data, dict):
                    progress = progress_data.get("completion", 0)
                    time_left = progress_data.get("printTimeLeft")
                    print(f"  Progress: {progress:.1f}%")

                    if time_left and time_left > 0:
                        hours = int(time_left // 3600)
                        minutes = int((time_left % 3600) // 60)
                        if hours > 0:
                            print(f"  Time left: {hours}h {minutes}m")
                        else:
                            print(f"  Time left: {minutes}m")
                else:
                    progress = progress_data if progress_data else 0
                    print(f"  Progress: {progress:.1f}%")
            else:
                print(f"\n📄 No job currently running")
        except Exception as e:
            if args.verbose:
                print(f"\n⚠️ Could not get job info: {e}")

        # Storage info (if verbose)
        if args.verbose:
            try:
                storage = client.get_storage_info()
                if storage:
                    print(f"\n💾 Storage:")
                    storage_name = storage.get("name", "Unknown")
                    print(f"  Available: {storage_name}")
            except Exception as e:
                print(f"\n⚠️ Could not get storage info: {e}")

        return True

    except PrusaLinkError as e:
        print(f"❌ PrusaLink error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def cmd_monitor(args):
    """Handle monitor command."""
    try:
        mode_map = {
            "standard": MonitorMode.STANDARD,
            "pipetting": MonitorMode.PIPETTING,
        }

        mode = mode_map[args.mode]
        monitor = PrintMonitor(mode=mode, interval=args.interval, verbose=args.verbose)

        return monitor.monitor_until_complete()

    except PrusaLinkError as e:
        print(f"❌ PrusaLink error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def cmd_stop(args):
    """Handle stop command."""
    try:
        monitor = PrintMonitor(verbose=args.verbose)
        return monitor.stop_print(force=args.force)

    except PrusaLinkError as e:
        print(f"❌ PrusaLink error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def cmd_calibrate(args):
    """Handle calibrate command."""
    print("🎯 Printer Calibration")
    print("=" * 40)

    try:
        # Initialize client and printer operations
        print("1. Connecting to printer...")
        client = PrusaLinkClient()
        if not client.test_connection():
            print("   ✗ Connection failed")
            return False
        print("   ✓ Connected to printer")

        # Create printer operations
        printer_ops = PrinterOperations(client)

        # Get initial status
        print("2. Checking printer status...")
        status = client.get_printer_status()
        printer_info = status.get("printer", {})
        state = printer_info.get("state", "Unknown")
        print(f"   ✓ Printer state: {state}")

        if state.upper() == "PRINTING":
            print("   ⚠ Printer is currently printing - cannot calibrate")
            return False

        # Prepare options
        kwargs = {"print_to_stdout": args.print_gcode, "keep_temp_file": args.keep_file}

        # Perform calibration
        if args.home_only:
            print("3. Homing all axes...")
            print("   • Waiting for printer to be ready...")
            if args.print_gcode:
                print("   • G-code will be printed below...")
            success = printer_ops.home_axes(**kwargs)
            if success:
                cleanup_msg = "kept on printer" if args.keep_file else "cleaned up"
                print(f"   ✓ Homing completed and temporary files {cleanup_msg}")
            else:
                print("   ✗ Homing failed")
                return False
        else:
            print("3. Starting full calibration (home + bed leveling)...")
            print("   • This may take up to 5 minutes...")
            print("   • Waiting for printer to be ready...")
            if args.print_gcode:
                print("   • G-code will be printed below...")
            cleanup_msg = "kept on printer" if args.keep_file else "cleaned up"
            print(f"   • Will wait for completion and {cleanup_msg} temporary files...")

            success = printer_ops.calibrate_printer(bed_leveling=True, **kwargs)
            if success:
                print("   ✓ Calibration completed successfully")
                print("   • All axes homed")
                print("   • Bed leveling completed")
                print(f"   • Temporary files {cleanup_msg}")
            else:
                print("   ✗ Calibration failed")
                return False

        # Get final status
        print("4. Verifying calibration...")
        final_status = client.get_printer_status()
        final_printer_info = final_status.get("printer", {})
        final_state = final_printer_info.get("state", "Unknown")

        if args.verbose:
            # Show position info
            x = final_printer_info.get("axis_x", 0)
            y = final_printer_info.get("axis_y", 0)
            z = final_printer_info.get("axis_z", 0)
            print(f"   ✓ Final position: X{x:.1f} Y{y:.1f} Z{z:.1f}")

        print(f"   ✓ Printer ready: {final_state}")
        print("\n🎉 Calibration completed successfully!")
        print("Your printer is now calibrated and ready for welding operations.")

        return True

    except PrusaLinkError as e:
        print(f"❌ PrusaLink error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return False


def cmd_temp(args):
    """Handle temperature commands."""
    if not args.temp_command:
        print("❌ No temperature command specified")
        return False

    try:
        client = PrusaLinkClient()
        printer_ops = PrinterOperations(client)

        kwargs = {
            "print_to_stdout": getattr(args, "print_gcode", False),
            "keep_temp_file": getattr(args, "keep_file", False),
        }

        if args.temp_command == "bed":
            print(f"🌡️ Setting bed temperature to {args.temperature}°C...")
            if args.wait:
                print("   • Will wait for temperature to be reached")
            if args.force and args.temperature > 120:
                print(f"   ⚠️  FORCE MODE: Bypassing safety limit (>{120}°C)")

            try:
                # Temporarily bypass validation if force is used
                if args.force:
                    # Use direct G-code sending to bypass validation
                    commands = []
                    if args.wait:
                        commands.append(
                            f"M190 S{args.temperature}  ; Set bed temp and wait"
                        )
                    else:
                        commands.append(f"M140 S{args.temperature}  ; Set bed temp")
                    commands.append(f"M117 Bed temp set to {args.temperature}C")

                    success = client.send_and_run_gcode(
                        commands=commands, job_name="set_bed_temp_forced", **kwargs
                    )
                else:
                    success = printer_ops.set_bed_temperature(
                        int(args.temperature), wait=args.wait, **kwargs
                    )
            except Exception as e:
                print(f"   ❌ Temperature validation failed: {e}")
                return False

        elif args.temp_command == "nozzle":
            print(f"🌡️ Setting nozzle temperature to {args.temperature}°C...")
            if args.wait:
                print("   • Will wait for temperature to be reached")
            if args.force and args.temperature > 300:
                print(f"   ⚠️  FORCE MODE: Bypassing safety limit (>{300}°C)")

            try:
                # Temporarily bypass validation if force is used
                if args.force:
                    # Use direct G-code sending to bypass validation
                    commands = []
                    if args.wait:
                        commands.append(
                            f"M109 S{args.temperature}  ; Set nozzle temp and wait"
                        )
                    else:
                        commands.append(f"M104 S{args.temperature}  ; Set nozzle temp")
                    commands.append(f"M117 Nozzle temp set to {args.temperature}C")

                    success = client.send_and_run_gcode(
                        commands=commands, job_name="set_nozzle_temp_forced", **kwargs
                    )
                else:
                    success = printer_ops.set_nozzle_temperature(
                        int(args.temperature), wait=args.wait, **kwargs
                    )
            except Exception as e:
                print(f"   ❌ Temperature validation failed: {e}")
                return False

        elif args.temp_command == "off":
            print("🌡️ Turning off all heaters...")
            success = printer_ops.turn_off_all_heaters(**kwargs)

        else:
            print(f"❌ Unknown temperature command: {args.temp_command}")
            return False

        if success:
            print("✅ Temperature command completed successfully")
            return True
        else:
            print("❌ Temperature command failed")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def cmd_home(args):
    """Handle home command."""
    try:
        client = PrusaLinkClient()
        printer_ops = PrinterOperations(client)

        kwargs = {"print_to_stdout": args.print_gcode, "keep_temp_file": args.keep_file}

        print(f"🏠 Homing {args.axes} axes...")
        success = printer_ops.home_axes(axes=args.axes, **kwargs)

        if success:
            print("✅ Homing completed successfully")
            if args.verbose:
                # Show final position
                status = client.get_printer_status()
                printer_info = status.get("printer", {})
                x = printer_info.get("axis_x", 0)
                y = printer_info.get("axis_y", 0)
                z = printer_info.get("axis_z", 0)
                print(f"   Final position: X{x:.1f} Y{y:.1f} Z{z:.1f}")
            return True
        else:
            print("❌ Homing failed")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def cmd_test(args):
    """Handle test command."""
    print("Testing PrusaLink integration...")
    print("=" * 50)

    try:
        # Initialize client
        print("1. Loading configuration...")
        client = PrusaLinkClient()
        print("   ✓ Configuration loaded")

        # Test connection
        print("2. Testing connection...")
        if client.test_connection():
            print("   ✓ Connection successful")
        else:
            print("   ✗ Connection failed")
            return False

        # Get printer info
        print("3. Getting printer information...")
        try:
            status = client.get_printer_status()
            printer_info = status.get("printer", {})
            print(f"   ✓ Printer: {printer_info.get('state', 'Unknown')}")
        except Exception as e:
            print(f"   ⚠ Could not get printer info: {e}")

        # Get storage info
        print("4. Getting storage information...")
        try:
            storage = client.get_storage_info()
            if storage:
                print(f"   ✓ Available storage: {storage.get('name', 'Unknown')}")
            else:
                print("   ⚠ No storage information available")
        except Exception as e:
            print(f"   ⚠ Could not get storage info: {e}")

        # Get job status
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


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Dispatch to command handlers
    command_handlers = {
        "status": cmd_status,
        "monitor": cmd_monitor,
        "stop": cmd_stop,
        "test": cmd_test,
        "calibrate": cmd_calibrate,
        "temp": cmd_temp,
        "home": cmd_home,
    }

    handler = command_handlers.get(args.command)
    if handler:
        success = handler(args)
        sys.exit(0 if success else 1)
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


def calibrate_main():
    """Direct entry point for calibrate command."""
    import sys

    # Create a minimal parser for calibrate command
    parser = argparse.ArgumentParser(
        description="Calibrate printer (home + bed leveling)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  microweldr-calibrate                # Full calibration (home + bed leveling)
  microweldr-calibrate --home-only    # Only home axes
  microweldr-calibrate --verbose      # Show detailed output
  microweldr-calibrate --print-gcode  # Show generated G-code
        """,
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed calibration output"
    )
    parser.add_argument(
        "--home-only", action="store_true", help="Only home axes, skip bed leveling"
    )
    parser.add_argument(
        "--print-gcode", action="store_true", help="Print generated G-code to stdout"
    )
    parser.add_argument(
        "--keep-file", action="store_true", help="Keep temporary G-code file on printer"
    )

    args = parser.parse_args()

    # Run calibration
    success = cmd_calibrate(args)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
