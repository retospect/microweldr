"""Command line interface for the SVG welder."""

import argparse
import sys
from pathlib import Path

from svg_welder.animation.generator import AnimationGenerator
from svg_welder.core.config import Config, ConfigError
from svg_welder.core.converter import SVGToGCodeConverter
from svg_welder.core.svg_parser import SVGParseError
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
  %(prog)s input.svg -c custom_config.toml
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
        output_gcode = input_path.with_suffix(".gcode")

    output_animation = input_path.with_name(input_path.stem + "_animation.svg")

    try:
        # Initialize configuration
        if args.verbose:
            print(f"Loading configuration from: {args.config}")

        config = Config(args.config)

        # Initialize converter
        converter = SVGToGCodeConverter(config)

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
                animation_generator.generate_file(weld_paths, output_animation)

                # Validate generated animation
                if not args.no_validation:
                    if args.verbose:
                        print("Validating animation SVG...")
                    result = AnimationValidator.validate(output_animation)
                    print_validation_result(result, args.verbose)

            except Exception as e:
                print(f"Error generating animation: {e}")
                # Don't exit on animation errors, just warn

        print("Conversion complete!")

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
