#!/usr/bin/env python3
"""
Quick script to run printer integration tests.

Usage:
    python scripts/test_printer.py              # Run all integration tests
    python scripts/test_printer.py --fast       # Run only fast tests
    python scripts/test_printer.py --check      # Just check if printer is available
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import after path modification
from microweldr.prusalink.client import PrusaLinkClient  # noqa: E402


def check_printer_available():
    """Check if printer is available for testing."""
    try:
        print("🔍 Checking printer connection...")
        client = PrusaLinkClient()
        if client.test_connection():
            print("✅ Printer is available and ready for testing")

            # Show basic printer info
            status = client.get_printer_status()
            printer_info = status.get("printer", {})
            state = printer_info.get("state", "Unknown")
            bed_temp = printer_info.get("temp_bed", 0)
            nozzle_temp = printer_info.get("temp_nozzle", 0)

            print(f"   State: {state}")
            print(f"   Bed: {bed_temp}°C, Nozzle: {nozzle_temp}°C")
            return True
        else:
            print("❌ Printer connection failed")
            return False
    except Exception as e:
        print(f"❌ Printer not available: {e}")
        return False


def run_integration_tests(fast_only=False):
    """Run integration tests."""
    import subprocess

    if not check_printer_available():
        print("\n⚠️  Skipping integration tests - printer not available")
        return False

    print(f"\n🧪 Running {'fast ' if fast_only else ''}integration tests...")

    # Build pytest command
    cmd = ["pytest", "tests/integration/test_printer_integration.py", "-v"]

    if fast_only:
        # Run only the faster tests
        cmd.extend(
            ["-k", "test_invalid_gcode_handling or test_error_recovery_and_halt"]
        )

    try:
        result = subprocess.run(cmd, cwd=project_root)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run printer integration tests")
    parser.add_argument(
        "--check", action="store_true", help="Just check if printer is available"
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Run only fast tests (skip slow temperature tests)",
    )

    args = parser.parse_args()

    if args.check:
        success = check_printer_available()
    else:
        success = run_integration_tests(fast_only=args.fast)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
