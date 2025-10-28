#!/usr/bin/env python3
"""
Print monitoring utility for SVG welder.
"""

import argparse
import datetime
import sys
import time

from microweldr.prusalink.client import PrusaLinkClient
from microweldr.prusalink.exceptions import PrusaLinkError


def create_parser():
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(description="Monitor SVG welder print progress")
    parser.add_argument(
        "--interval",
        "-i",
        type=int,
        default=30,
        help="Check interval in seconds (default: 30)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output"
    )
    parser.add_argument(
        "--mode",
        choices=["standard", "pipetting"],
        default="standard",
        help="Monitoring mode for different print types",
    )
    return parser


def format_time_remaining(seconds):
    """Format time remaining in human readable format."""
    if not seconds or seconds <= 0:
        return "Unknown"

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)

    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def get_mode_emoji(mode):
    """Get emoji for monitoring mode."""
    mode_emojis = {"standard": "🏢️", "pipetting": "🧪"}
    return mode_emojis.get(mode, "📊")


def print_header(mode):
    """Print monitoring header."""
    emoji = get_mode_emoji(mode)
    mode_name = mode.replace("-", " ").title()

    print(f"{emoji} SVG Welder Print Monitor - {mode_name} Mode")
    print("=" * 60)
    print(f"⏱️ Started: {datetime.datetime.now().strftime('%H:%M:%S')}")

    if mode == "pipetting":
        print("🧪 Features: Pipetting stops for microfluidic devices")
    elif mode == "standard":
        print("⬆️ Mode: Standard upright operation")

    print("=" * 60)


def print_status_update(job, elapsed_min, mode, verbose):
    """Print status update."""
    file_name = job.get("file", {}).get("name", "Unknown")
    state = job.get("state", "Unknown")
    progress_data = job.get("progress", 0)

    if isinstance(progress_data, dict):
        progress = progress_data.get("completion", 0)
        time_left = progress_data.get("printTimeLeft")
    else:
        progress = progress_data if progress_data else 0
        time_left = None

    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    emoji = get_mode_emoji(mode)

    print(f"[{timestamp}] ({elapsed_min:02d}min) 📊 {progress:.1f}% | {emoji} {state}")

    if verbose:
        print(f"    📄 File: {file_name}")

    if time_left and time_left > 0:
        print(f"    ⏰ Time remaining: {format_time_remaining(time_left)}")

    # Mode-specific status messages
    if state.lower() == "paused":
        if mode == "pipetting":
            print("    🧪 PIPETTING PAUSE - Check LCD for instructions!")
            print("    💉 Fill pouches as directed, then press continue")
        else:
            print("    ⏸️ PAUSED - Check printer LCD for instructions")


def monitor_print(args):
    """Main monitoring loop."""
    print_header(args.mode)

    try:
        client = PrusaLinkClient()
        last_progress = -1
        last_state = None
        start_time = time.time()

        while True:
            try:
                job = client.get_job_status()
                current_time = time.time()
                elapsed_min = int((current_time - start_time) / 60)

                if job:
                    state = job.get("state", "Unknown")
                    progress_data = job.get("progress", 0)

                    if isinstance(progress_data, dict):
                        progress = progress_data.get("completion", 0)
                    else:
                        progress = progress_data if progress_data else 0

                    # Print status if changed
                    if progress != last_progress or state != last_state:
                        print_status_update(job, elapsed_min, args.mode, args.verbose)
                        last_progress = progress
                        last_state = state

                    # Check for completion or failure
                    if state.lower() in ["finished", "completed", "done"]:
                        emoji = get_mode_emoji(args.mode)
                        print(f"\n🎉 Print completed successfully!")
                        print(
                            f"✅ Your {args.mode.replace('-', ' ')} print finished! {emoji}"
                        )
                        return True
                    elif state.lower() in ["error", "failed", "cancelled"]:
                        print(f"\n❌ Print failed with state: {state}")
                        return False

                else:
                    if last_state != "no_job":
                        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                        print(f"[{timestamp}] ({elapsed_min:02d}min) ❌ No job running")
                        print("    (Printer might have rebooted or job completed)")
                        last_state = "no_job"
                        return False

                time.sleep(args.interval)

            except Exception as e:
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] ⚠️ Connection error: {e}")
                print("    (Printer might be rebooting or network issue)")
                time.sleep(60)  # Wait longer on error

    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped by user")
        return False
    except PrusaLinkError as e:
        print(f"\n❌ PrusaLink error: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Monitoring error: {e}")
        return False


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    success = monitor_print(args)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
