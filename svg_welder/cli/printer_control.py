#!/usr/bin/env python3
"""
Unified printer control utility for SVG welder.
Combines status checking, monitoring, and print stopping in one tool.
"""

import argparse
import json
import sys

from svg_welder.monitoring import MonitorMode, PrintMonitor
from svg_welder.prusalink.client import PrusaLinkClient
from svg_welder.prusalink.exceptions import PrusaLinkError


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
  
  # Monitor print progress
  printer-control monitor
  printer-control monitor --mode layed-back --interval 20
  printer-control monitor --mode pipetting --verbose
  
  # Stop current print
  printer-control stop
  printer-control stop --force
  
  # Test connection
  printer-control test
  printer-control test --verbose

Monitoring Modes:
  standard    - Standard upright printer operation
  layed-back  - Printer on its back (door pointing up)
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
        choices=["standard", "layed-back", "pipetting"],
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
            "layed-back": MonitorMode.LAYED_BACK,
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
    }

    handler = command_handlers.get(args.command)
    if handler:
        success = handler(args)
        sys.exit(0 if success else 1)
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
