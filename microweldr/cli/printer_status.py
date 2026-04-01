#!/usr/bin/env python3
"""
Quick printer status check utility.
"""

import argparse
import sys

from microweldr.prusalink.client import PrusaLinkClient
from microweldr.prusalink.exceptions import PrusaLinkError


def create_parser():
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(description="Check current printer status")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed printer information"
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON response")
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


def print_status(args):
    """Print printer status."""
    try:
        client = PrusaLinkClient()

        # Get printer status
        status = client.get_printer_status()

        if args.json:
            import json

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
                print("\n📄 Current Job:")
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
                print("\n📄 No job currently running")
        except Exception as e:
            if args.verbose:
                print(f"\n⚠️ Could not get job info: {e}")

        # Storage info (if verbose)
        if args.verbose:
            try:
                storage = client.get_storage_info()
                if storage:
                    print("\n💾 Storage:")
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


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    success = print_status(args)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
