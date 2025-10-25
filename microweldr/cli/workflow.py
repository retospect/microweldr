#!/usr/bin/env python3
"""
Workflow commands for MicroWeldr.
Provides calibrate, load, frame, and weld commands for streamlined operation.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

from microweldr.core.config import Config, ConfigError
from microweldr.core.converter import SVGToGCodeConverter
from microweldr.prusalink.client import PrusaLinkClient
from microweldr.prusalink.exceptions import PrusaLinkError


class WorkflowCommands:
    """Workflow command implementations."""

    def __init__(
        self, config_path: str = "config.toml", secrets_path: str = "secrets.toml"
    ):
        """Initialize workflow commands."""
        self.config_path = config_path
        self.secrets_path = secrets_path
        self.calibration_file = Path("calibration.json")

        # Load configuration
        try:
            self.config = Config(config_path)
            self.config.validate()
        except ConfigError as e:
            print(f"Configuration error: {e}")
            sys.exit(1)

        # Initialize PrusaLink client
        try:
            self.client = PrusaLinkClient(secrets_path)
        except Exception as e:
            print(f"Failed to initialize printer connection: {e}")
            print("Make sure secrets.toml is configured correctly.")
            sys.exit(1)

    def calibrate(self, verbose: bool = False) -> None:
        """Perform XYZ calibration and store results persistently."""
        print("🔧 Starting XYZ calibration...")

        try:
            # Check printer status
            status = self.client.get_status()
            if verbose:
                print(
                    f"Printer status: {status.get('printer', {}).get('state', 'unknown')}"
                )

            # Generate calibration G-code
            calibration_gcode = self._generate_calibration_gcode()

            # Create temporary G-code file
            temp_gcode = Path("calibration_temp.gcode")
            with open(temp_gcode, "w") as f:
                f.write(calibration_gcode)

            print("📤 Uploading calibration G-code to printer...")

            # Upload and start calibration
            upload_result = self.client.upload_file(
                str(temp_gcode), "calibration.gcode", storage="local", auto_start=True
            )

            if verbose:
                print(f"Upload result: {upload_result}")

            print("🔄 Running calibration sequence...")
            print("   This will perform automatic bed leveling and store the results.")
            print("   Please wait for completion...")

            # Monitor calibration progress
            self._monitor_calibration(verbose)

            # Store calibration data
            calibration_data = {
                "timestamp": time.time(),
                "date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "status": "completed",
                "printer_state": status.get("printer", {}).get("state", "unknown"),
            }

            with open(self.calibration_file, "w") as f:
                json.dump(calibration_data, f, indent=2)

            print("✅ Calibration completed and stored!")
            if verbose:
                print(f"Calibration data saved to: {self.calibration_file}")

            # Cleanup
            temp_gcode.unlink()

        except PrusaLinkError as e:
            print(f"❌ Calibration failed: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error during calibration: {e}")
            sys.exit(1)

    def load(self, verbose: bool = False) -> None:
        """Lower table 10cm and set target temperature without waiting."""
        print("📥 Preparing for film loading...")

        try:
            # Get current bed temperature setting
            bed_temp = self.config.get("temperatures", "bed_temperature")

            # Generate loading G-code
            loading_gcode = self._generate_loading_gcode(bed_temp)

            # Create temporary G-code file
            temp_gcode = Path("loading_temp.gcode")
            with open(temp_gcode, "w") as f:
                f.write(loading_gcode)

            print(f"🌡️  Setting bed temperature to {bed_temp}°C (not waiting)")
            print("📉 Lowering bed by 10cm for easy film loading...")

            # Upload and start loading sequence
            upload_result = self.client.upload_file(
                str(temp_gcode), "loading.gcode", storage="local", auto_start=True
            )

            if verbose:
                print(f"Upload result: {upload_result}")

            print("✅ Load sequence started!")
            print("   - Bed temperature is heating up")
            print("   - Bed lowered for film loading")
            print("   - Ready for film placement")

            # Cleanup
            temp_gcode.unlink()

        except PrusaLinkError as e:
            print(f"❌ Load command failed: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error during load: {e}")
            sys.exit(1)

    def frame(self, svg_path: str, verbose: bool = False) -> None:
        """Run rectangle at move height to check for magnet clearance."""
        print("🔲 Running frame check...")

        try:
            svg_path = Path(svg_path)
            if not svg_path.exists():
                print(f"❌ SVG file not found: {svg_path}")
                sys.exit(1)

            # Generate frame G-code
            frame_gcode = self._generate_frame_gcode(str(svg_path))

            # Create temporary G-code file
            temp_gcode = Path("frame_temp.gcode")
            with open(temp_gcode, "w") as f:
                f.write(frame_gcode)

            print("📤 Uploading frame check G-code...")
            print("   This will trace the design boundary at move height")
            print("   Check for magnet interference with the nozzle path")

            # Upload and start frame check
            upload_result = self.client.upload_file(
                str(temp_gcode), "frame_check.gcode", storage="local", auto_start=True
            )

            if verbose:
                print(f"Upload result: {upload_result}")

            print("✅ Frame check started!")
            print("   Watch for any collisions with magnets or film holders")

            # Cleanup
            temp_gcode.unlink()

        except PrusaLinkError as e:
            print(f"❌ Frame check failed: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error during frame check: {e}")
            sys.exit(1)

    def weld(self, svg_path: str, verbose: bool = False) -> None:
        """Set bed temperature, wait for it, then run welding."""
        print("🔥 Starting welding sequence...")

        try:
            svg_path = Path(svg_path)
            if not svg_path.exists():
                print(f"❌ SVG file not found: {svg_path}")
                sys.exit(1)

            # Check if calibration exists
            if not self.calibration_file.exists():
                print(
                    "⚠️  No calibration found. Run 'microweldr-workflow calibrate' first."
                )
                response = input("Continue anyway? (y/N): ")
                if response.lower() != "y":
                    print("Welding cancelled.")
                    return

            # Generate welding G-code
            print("📋 Generating welding G-code...")
            converter = SVGToGCodeConverter(self.config)
            weld_paths = converter.convert(str(svg_path), "welding_temp.gcode")

            print(f"✅ Generated G-code with {len(weld_paths)} weld paths")

            # Get bed temperature
            bed_temp = self.config.get("temperatures", "bed_temperature")

            print(f"🌡️  Setting bed temperature to {bed_temp}°C and waiting...")
            print("📤 Uploading welding G-code...")

            # Upload and start welding
            upload_result = self.client.upload_file(
                "welding_temp.gcode", "welding.gcode", storage="local", auto_start=True
            )

            if verbose:
                print(f"Upload result: {upload_result}")

            print("🔥 Welding started!")
            print("   - Bed heating and waiting for temperature")
            print("   - Welding sequence will begin automatically")
            print("   - Monitor progress on printer display")

            # Cleanup
            Path("welding_temp.gcode").unlink()

        except PrusaLinkError as e:
            print(f"❌ Welding failed: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error during welding: {e}")
            sys.exit(1)

    def _generate_calibration_gcode(self) -> str:
        """Generate G-code for XYZ calibration."""
        return """
; MicroWeldr XYZ Calibration
; Generated automatically for bed leveling

; Start G-code
G90 ; Absolute positioning
M83 ; Relative extruder positioning
M104 S0 ; Turn off hotend
M140 S60 ; Set bed temperature
M106 S0 ; Turn off part cooling fan

; Home all axes
G28 ; Home all axes

; Automatic bed leveling
G29 ; Bed leveling (this stores the mesh)

; Move to center for verification
G1 X125 Y110 Z5 F3000

; End G-code
M140 S0 ; Turn off bed
M84 ; Disable steppers

; Calibration complete
M117 Calibration Complete
"""

    def _generate_loading_gcode(self, bed_temp: float) -> str:
        """Generate G-code for loading sequence."""
        return f"""
; MicroWeldr Loading Sequence
; Lower bed and set temperature

; Start G-code
G90 ; Absolute positioning
M83 ; Relative extruder positioning
M104 S0 ; Turn off hotend
M140 S{bed_temp} ; Set bed temperature (don't wait)
M106 S0 ; Turn off part cooling fan

; Home if needed
G28 Z ; Home Z axis only

; Lower bed by 10cm for loading
G1 Z100 F600 ; Move bed down 10cm

; Move to center for easy access
G1 X125 Y110 F3000

; Loading position ready
M117 Ready for film loading
"""

    def _generate_frame_gcode(self, svg_path: str) -> str:
        """Generate G-code for frame check at move height."""
        try:
            # Parse SVG to get bounds
            converter = SVGToGCodeConverter(self.config)
            weld_paths = converter.parse_svg(svg_path)

            if not weld_paths:
                raise ValueError("No weld paths found in SVG")

            # Get design bounds
            bounds = converter.get_bounds()
            min_x, min_y, max_x, max_y = bounds

            # Get move height from config
            move_height = self.config.get("movement", "move_height")
            travel_speed = self.config.get("movement", "travel_speed")

            return f"""
; MicroWeldr Frame Check
; Trace design boundary at move height

; Start G-code
G90 ; Absolute positioning
M83 ; Relative extruder positioning
M104 S0 ; Turn off hotend
M106 S0 ; Turn off part cooling fan

; Move to start position
G1 X{min_x:.3f} Y{min_y:.3f} Z{move_height} F{travel_speed}

; Trace rectangle boundary
G1 X{max_x:.3f} Y{min_y:.3f} F{travel_speed} ; Bottom edge
G1 X{max_x:.3f} Y{max_y:.3f} F{travel_speed} ; Right edge
G1 X{min_x:.3f} Y{max_y:.3f} F{travel_speed} ; Top edge
G1 X{min_x:.3f} Y{min_y:.3f} F{travel_speed} ; Left edge

; Return to center
G1 X{(min_x + max_x) / 2:.3f} Y{(min_y + max_y) / 2:.3f} F{travel_speed}

; Frame check complete
M117 Frame check complete
"""

        except Exception as e:
            print(f"Error generating frame G-code: {e}")
            sys.exit(1)

    def _monitor_calibration(self, verbose: bool) -> None:
        """Monitor calibration progress."""
        print("   Monitoring calibration progress...")

        start_time = time.time()
        last_status = None

        while True:
            try:
                status = self.client.get_status()
                current_status = status.get("printer", {}).get("state", "unknown")

                if current_status != last_status:
                    if verbose:
                        print(f"   Status: {current_status}")
                    last_status = current_status

                # Check if calibration is complete
                if current_status in ["idle", "finished"]:
                    break
                elif current_status in ["error", "stopped"]:
                    raise PrusaLinkError(
                        f"Calibration failed with status: {current_status}"
                    )

                # Timeout after 10 minutes
                if time.time() - start_time > 600:
                    print("   Calibration taking longer than expected...")
                    response = input("   Continue waiting? (y/N): ")
                    if response.lower() != "y":
                        break
                    start_time = time.time()  # Reset timeout

                time.sleep(5)  # Check every 5 seconds

            except KeyboardInterrupt:
                print("\n   Calibration monitoring interrupted.")
                break
            except Exception as e:
                if verbose:
                    print(f"   Monitoring error: {e}")
                time.sleep(5)


def create_parser():
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="MicroWeldr workflow commands",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Workflow Commands:
  calibrate   - Perform XYZ calibration and store results
  load        - Lower table 10cm and set temperature (no wait)
  frame       - Run rectangle at move height to check clearance
  weld        - Set temperature, wait, then run welding

Normal Workflow:
  1. microweldr-workflow calibrate
  2. microweldr-workflow load
  3. [Load film and place magnets]
  4. microweldr-workflow frame design.svg
  5. microweldr-workflow weld design.svg
  6. [Repeat steps 2-5 for next design]

Examples:
  microweldr-workflow calibrate --verbose
  microweldr-workflow load
  microweldr-workflow frame design.svg
  microweldr-workflow weld design.svg --verbose
        """,
    )

    # Global options
    parser.add_argument(
        "-c",
        "--config",
        default="config.toml",
        help="Configuration file path (default: config.toml)",
    )
    parser.add_argument(
        "-s",
        "--secrets",
        default="secrets.toml",
        help="Secrets file path (default: secrets.toml)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Calibrate command
    calibrate_parser = subparsers.add_parser(
        "calibrate", help="Perform XYZ calibration and store results"
    )

    # Load command
    load_parser = subparsers.add_parser(
        "load", help="Lower table 10cm and set temperature (no wait)"
    )

    # Frame command
    frame_parser = subparsers.add_parser(
        "frame", help="Run rectangle at move height to check clearance"
    )
    frame_parser.add_argument("svg_file", help="SVG file to check frame for")

    # Weld command
    weld_parser = subparsers.add_parser(
        "weld", help="Set temperature, wait, then run welding"
    )
    weld_parser.add_argument("svg_file", help="SVG file to weld")

    return parser


def main():
    """Main entry point for workflow commands."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize workflow commands
    workflow = WorkflowCommands(args.config, args.secrets)

    # Execute command
    try:
        if args.command == "calibrate":
            workflow.calibrate(args.verbose)
        elif args.command == "load":
            workflow.load(args.verbose)
        elif args.command == "frame":
            workflow.frame(args.svg_file, args.verbose)
        elif args.command == "weld":
            workflow.weld(args.svg_file, args.verbose)
        else:
            print(f"Unknown command: {args.command}")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)


if __name__ == "__main__":
    main()
