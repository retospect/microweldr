#!/usr/bin/env python3
"""
Stop current print utility.
"""

import argparse
import sys

from microweldr.prusalink.client import PrusaLinkClient
from microweldr.prusalink.exceptions import PrusaLinkError


def create_parser():
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(description="Stop the current print job")
    parser.add_argument(
        "--force", "-f", action="store_true", help="Force stop without confirmation"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output"
    )
    return parser


def confirm_stop():
    """Ask user for confirmation."""
    try:
        response = input("Are you sure you want to stop the current print? (y/N): ")
        return response.lower().startswith("y")
    except (EOFError, KeyboardInterrupt):
        print("\nOperation cancelled.")
        return False


def stop_print(args):
    """Stop the current print."""
    try:
        client = PrusaLinkClient()

        # Check if there's a job running
        job = client.get_job_status()
        if not job:
            print("❌ No job currently running")
            return False

        file_info = job.get("file", {})
        file_name = file_info.get("name", "Unknown")
        state = job.get("state", "Unknown")

        print(f"📄 Current job: {file_name}")
        print(f"🔄 State: {state}")

        if state.lower() in ["finished", "completed", "done"]:
            print("✅ Job is already completed")
            return True

        if state.lower() in ["error", "failed", "cancelled"]:
            print(f"❌ Job is already in {state} state")
            return True

        # Confirm stop unless forced
        if not args.force:
            if not confirm_stop():
                print("🛑 Stop cancelled")
                return False

        if args.verbose:
            print("🛑 Sending stop command...")

        # Stop the print
        success = client.stop_print()

        if success:
            print("✅ Print stopped successfully")
            return True
        else:
            print("❌ Failed to stop print")
            return False

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

    success = stop_print(args)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
