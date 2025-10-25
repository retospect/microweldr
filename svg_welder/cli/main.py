"""Command line interface for the SVG welder."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from svg_welder.animation.generator import AnimationGenerator
from svg_welder.core.config import Config, ConfigError
from svg_welder.core.converter import SVGToGCodeConverter
from svg_welder.core.svg_parser import SVGParseError
from svg_welder.monitoring import MonitorMode, PrintMonitor
from svg_welder.prusalink import PrusaLinkClient, PrusaLinkError
from svg_welder.validation.validators import (
    AnimationValidator,
    GCodeValidator,
    SVGValidator,
)


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Convert SVG files to Prusa Core One G-code for plastic welding",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.svg -o output.gcode
  %(prog)s input.svg --skip-bed-leveling
  %(prog)s input.svg --weld-sequence skip
  %(prog)s input.svg -c custom_config.toml
  %(prog)s input.svg --submit-to-printer
  %(prog)s input.svg --submit-to-printer --auto-start-print
  %(prog)s input.svg --submit-to-printer --queue-only
        """,
    )

    parser.add_argument("input_svg", help="Input SVG file path")
    parser.add_argument(
        "-o", "--output", help="Output G-code file path (default: input_name.gcode)"
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.toml",
        help="Configuration file path (default: config.toml)",
    )
    parser.add_argument(
        "--skip-bed-leveling", action="store_true", help="Skip automatic bed leveling"
    )
    parser.add_argument(
        "--no-animation", action="store_true", help="Skip generating animation SVG"
    )
    parser.add_argument(
        "--no-validation", action="store_true", help="Skip validation steps"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--weld-sequence",
        choices=["linear", "binary", "farthest", "skip"],
        default="skip",
        help="Welding sequence algorithm: linear (1,2,3...), binary (binary subdivision), farthest (greedy farthest-point traversal), skip (every Nth dot first, then fill gaps, default)",
    )
    parser.add_argument(
        "--submit-to-printer",
        action="store_true",
        help="Submit G-code to PrusaLink after generation",
    )
    parser.add_argument(
        "--secrets-config",
        default="secrets.toml",
        help="Path to secrets configuration file (default: secrets.toml)",
    )
    parser.add_argument(
        "--printer-storage",
        choices=["local", "usb"],
        help="Target storage on printer (overrides config default)",
    )
    parser.add_argument(
        "--auto-start-print",
        action="store_true",
        help="Automatically start printing after upload (overrides config default)",
    )
    parser.add_argument(
        "--no-auto-start",
        action="store_true",
        help="Do not start printing after upload (overrides config default)",
    )
    parser.add_argument(
        "--queue-only",
        action="store_true",
        help="Queue the file without starting (same as --no-auto-start, but clearer intent)",
    )
    parser.add_argument(
        "--timestamp",
        action="store_true",
        help="Add timestamp (yy-mm-dd-hh-mm-ss) to output filename for uniqueness",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Monitor print progress after submission until completion",
    )
    parser.add_argument(
        "--monitor-mode",
        choices=["standard", "layed-back", "pipetting"],
        default="standard",
        help="Monitoring mode when --monitor is used (default: standard)",
    )
    parser.add_argument(
        "--monitor-interval",
        type=int,
        default=30,
        help="Monitoring check interval in seconds (default: 30)",
    )
    parser.add_argument(
        "--no-center",
        action="store_true",
        help="Disable automatic centering on bed (use SVG coordinates as-is)",
    )

    return parser


def print_validation_result(result, verbose: bool = False) -> None:
    """Print validation result."""
    if result.is_valid:
        print(f"✓ {result.message}")
    else:
        print(f"✗ {result.message}")

    if verbose and result.warnings:
        for warning in result.warnings:
            print(f"  Warning: {warning}")


def main() -> None:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Validate input file
    input_path = Path(args.input_svg)
    if not input_path.exists():
        print(f"Error: Input SVG file '{args.input_svg}' not found.")
        sys.exit(1)

    # Determine output paths
    if args.output:
        output_gcode = Path(args.output)
    else:
        base_name = input_path.stem
        if args.timestamp:
            timestamp = datetime.now().strftime("%y-%m-%d-%H-%M-%S")
            base_name = f"{base_name}_{timestamp}"
        output_gcode = input_path.with_name(base_name + ".gcode")

    # Animation path (always use timestamped name if timestamp option is used)
    animation_base = input_path.stem
    if args.timestamp:
        timestamp = datetime.now().strftime("%y-%m-%d-%H-%M-%S")
        animation_base = f"{animation_base}_{timestamp}"
    output_animation = input_path.with_name(animation_base + "_animation.svg")

    try:
        # Initialize configuration
        if args.verbose:
            print(f"Loading configuration from: {args.config}")

        config = Config(args.config)

        # Initialize converter with centering option
        center_on_bed = (
            not args.no_center
        )  # Default to centering unless --no-center is used
        converter = SVGToGCodeConverter(config, center_on_bed=center_on_bed)

        print(f"Processing SVG file: {args.input_svg}")

        # Validate input SVG
        if not args.no_validation:
            if args.verbose:
                print("Validating input SVG...")
            result = SVGValidator.validate(args.input_svg)
            print_validation_result(result, args.verbose)
            if not result.is_valid:
                print("Warning: SVG validation failed, but continuing processing...")

        # Parse SVG
        try:
            weld_paths = converter.parse_svg(args.input_svg)
            print(f"Found {len(weld_paths)} weld paths")

            if args.verbose:
                bounds = converter.get_bounds()
                print(
                    f"Bounds: ({bounds[0]:.1f}, {bounds[1]:.1f}) to ({bounds[2]:.1f}, {bounds[3]:.1f})"
                )

        except SVGParseError as e:
            print(f"Error parsing SVG: {e}")
            sys.exit(1)

        # Generate G-code
        print(f"Generating G-code: {output_gcode}")
        try:
            converter.generate_gcode(output_gcode, args.skip_bed_leveling)
        except Exception as e:
            print(f"Error generating G-code: {e}")
            sys.exit(1)

        # Validate generated G-code
        if not args.no_validation:
            if args.verbose:
                print("Validating generated G-code...")
            result = GCodeValidator.validate(output_gcode)
            print_validation_result(result, args.verbose)

        # Generate animation
        if not args.no_animation:
            print(f"Generating animation: {output_animation}")
            try:
                animation_generator = AnimationGenerator(config)
                animation_generator.generate_file(
                    weld_paths, output_animation, args.weld_sequence
                )

                # Validate generated animation
                if not args.no_validation:
                    if args.verbose:
                        print("Validating animation SVG...")
                    result = AnimationValidator.validate(output_animation)
                    print_validation_result(result, args.verbose)

            except Exception as e:
                print(f"Error generating animation: {e}")
                # Don't exit on animation errors, just warn

        # Submit to printer if requested
        if args.submit_to_printer:
            try:
                print("\nSubmitting G-code to printer...")
                client = PrusaLinkClient(args.secrets_config)

                # Test connection first
                if not client.test_connection():
                    print(
                        "Warning: Could not connect to printer. Check your configuration."
                    )
                else:
                    if args.verbose:
                        printer_info = client.get_printer_info()
                        print(
                            f"Connected to: {printer_info.get('name', 'Unknown printer')}"
                        )

                    # Determine auto-start behavior
                    if args.no_auto_start or args.queue_only:
                        will_auto_start = False
                        auto_start_override = False
                        queue_mode = args.queue_only
                    elif args.auto_start_print:
                        will_auto_start = True
                        auto_start_override = True
                        queue_mode = False
                    else:
                        will_auto_start = client.config.get("auto_start_print", False)
                        auto_start_override = None
                        queue_mode = False

                    if queue_mode:
                        print("📋 Queue mode: File will be uploaded but not started")
                    elif will_auto_start:
                        if client.is_printer_ready():
                            print(
                                "✓ Printer is ready - will start printing immediately"
                            )
                        else:
                            print(
                                "⚠ Warning: Printer may not be ready (check if it's busy or has errors)"
                            )
                            if not args.verbose:
                                print("  Use --verbose to see printer status details")
                    else:
                        print("📁 File will be uploaded without auto-starting")

                    # Upload G-code
                    upload_result = client.upload_gcode(
                        str(output_gcode),
                        storage=args.printer_storage,
                        auto_start=auto_start_override,
                        overwrite=True,  # Always overwrite for immediate printing
                    )

                    print(
                        f"✓ G-code uploaded successfully: {upload_result['filename']}"
                    )
                    if upload_result["auto_started"]:
                        print("🚀 Print started immediately - welding in progress!")
                        if not args.monitor:
                            print("  Monitor your printer to ensure proper operation")
                    elif queue_mode:
                        print(
                            "📋 File queued successfully - ready to print when you are"
                        )
                        print(
                            "  Start the print from your printer's interface or web UI"
                        )
                    else:
                        print(
                            "📁 File uploaded - use your printer's interface to start the print"
                        )

                    # Start monitoring if requested and print was started
                    if args.monitor and upload_result["auto_started"]:
                        print("\n" + "=" * 60)
                        print("🔍 Starting print monitoring...")

                        mode_map = {
                            "standard": MonitorMode.STANDARD,
                            "layed-back": MonitorMode.LAYED_BACK,
                            "pipetting": MonitorMode.PIPETTING,
                        }

                        monitor = PrintMonitor(
                            mode=mode_map[args.monitor_mode],
                            interval=args.monitor_interval,
                            verbose=args.verbose,
                        )

                        try:
                            success = monitor.monitor_until_complete()
                            if success:
                                print("\n✅ Print monitoring completed successfully!")
                            else:
                                print("\n❌ Print monitoring ended with issues")
                        except KeyboardInterrupt:
                            print("\n🛑 Monitoring stopped by user")
                        except Exception as e:
                            print(f"\n⚠️ Monitoring error: {e}")
                    elif args.monitor and not upload_result["auto_started"]:
                        print("\n⚠️ Monitoring requested but print was not auto-started")
                        print("   Use --auto-start-print to enable monitoring")

            except PrusaLinkError as e:
                print(f"Printer submission failed: {e}")
                print("G-code file was still generated successfully.")
            except Exception as e:
                print(f"Unexpected error during printer submission: {e}")
                print("G-code file was still generated successfully.")

        print("\nConversion complete!")

        if args.verbose:
            print(f"Output files:")
            print(f"  G-code: {output_gcode}")
            if not args.no_animation:
                print(f"  Animation: {output_animation}")

    except ConfigError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
