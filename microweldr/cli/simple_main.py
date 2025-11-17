"""Simplified command line interface matching newCmdOptions specification."""

import argparse
import sys
import logging
from pathlib import Path
from typing import Optional, List

from ..core.config import Config
from ..core.logging_config import setup_logging
from ..generators.point_iterator_factory import PointIteratorFactory
from ..outputs.streaming_gcode_subscriber import StreamingGCodeSubscriber
from ..outputs.gif_animation_subscriber import GIFAnimationSubscriber
from ..core.events import (
    Event,
    EventType,
    PathEvent,
    PointEvent,
    OutputEvent,
    publish_event,
)
import time


def get_version() -> str:
    """Get the current version of MicroWeldr."""
    try:
        import microweldr

        return microweldr.__version__
    except (ImportError, AttributeError):
        return "4.0.0"


def create_parser() -> argparse.ArgumentParser:
    """Create simplified command line argument parser matching newCmdOptions."""
    parser = argparse.ArgumentParser(
        prog="microweldr",
        description="MicroWeldr: Simplified plastic welding G-code generation for Prusa printers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage Examples:

  # Basic welding (single file):
  microweldr -weld device.dxf

  # Structural + frangible welds:
  microweldr -weld main.svg -frange seals.dxf -g_out complete_device.gcode

  # With animation preview:
  microweldr -weld design.svg -animation preview.gif

  # Quiet production run:
  microweldr -weld test.svg -quiet

  # With bed leveling and calibration:
  microweldr -weld device.svg -level-bed

  # Production workflow:
  microweldr -weld structure.dxf -frange ports.dxf -g_out production.gcode

File Type Detection:
  - Black elements (SVG) / Normal layers (DXF) → Structural welds (0.3mm depth)
  - Blue elements (SVG) / Frangible layers (DXF) → Breakaway welds (0.6mm depth)
  - Red elements → Stop points (user intervention)
  - Magenta elements → Pipette points (filling operations)
        """,
    )

    # Version
    parser.add_argument(
        "--version", action="version", version=f"MicroWeldr {get_version()}"
    )

    # Core Workflow Options
    parser.add_argument(
        "-weld",
        dest="weld_file",
        type=str,
        help="Main weld file (SVG or DXF) for structural welds. Supports: .svg, .dxf",
    )

    parser.add_argument(
        "-frange",
        dest="frangible_file",
        type=str,
        help="Frangible/breakaway weld file (SVG or DXF) for temporary seals and filling ports",
    )

    parser.add_argument(
        "-g_out",
        dest="gcode_output",
        type=str,
        help="Output G-code file (default: auto-generated from input). Max filename: 31 chars (Prusa compatibility)",
    )

    # Output Options
    parser.add_argument(
        "-animation",
        dest="animation",
        type=str,
        help="Generate animated GIF showing weld sequence progression",
    )

    # Process Control
    parser.add_argument(
        "-level-bed",
        dest="level_bed",
        action="store_true",
        help="Include bed leveling in G-code (default: not included). Use to ensure proper first layer adhesion",
    )

    parser.add_argument(
        "-stop-for-film",
        dest="stop_for_film",
        action="store_true",
        help="Pause for plastic film insertion (default: not included). Allows manual placement of welding material",
    )

    parser.add_argument(
        "-cool-bed-after",
        dest="cool_bed_after",
        action="store_true",
        help="Cool bed after welding (default: not included, if option is present bed is cooled to 0°C)",
    )

    # Configuration and Logging
    parser.add_argument(
        "-quiet",
        dest="quiet",
        action="store_true",
        help="Disable detailed logging output (default: normal logging). Use for production runs to reduce console output",
    )

    return parser


def validate_filename_length(filename: str) -> bool:
    """Validate G-code filename length for Prusa compatibility."""
    if len(filename) > 31:
        print(f"❌ Filename too long: '{filename}' ({len(filename)} chars)")
        print("💡 Prusa printers require filenames ≤31 characters including extension")
        print("   Try a shorter name like 'device.gcode' or 'part1.gcode'")
        return False
    return True


def auto_generate_output_filename(input_file: str) -> str:
    """Generate output filename from input file."""
    input_path = Path(input_file)
    base_name = input_path.stem

    # Truncate if too long (leave room for .gcode extension)
    max_base_length = 31 - len(".gcode")
    if len(base_name) > max_base_length:
        base_name = base_name[:max_base_length]

    return f"{base_name}.gcode"


def process_weld_file(
    file_path: str, config: Config, is_frangible: bool = False
) -> List[dict]:
    """Process a weld file and return points."""
    if not Path(file_path).exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    print(
        f"📄 Processing {'frangible' if is_frangible else 'structural'} weld file: {file_path}"
    )

    # Create iterator for the file type with config for consistent dot_spacing
    iterator = PointIteratorFactory.create_iterator(file_path, config=config)
    points = list(iterator.iterate_points(Path(file_path)))

    print(f"✅ Loaded {len(points)} points from {Path(file_path).name}")
    return points


def generate_gcode(points: List[dict], output_path: str, config: Config, args) -> bool:
    """Generate G-code using two-pass coordinate centering."""
    try:
        print(f"⚙️  Generating G-code: {output_path}")

        # Import two-pass processor
        from ..processors.two_pass_processor import TwoPassProcessor

        # Get bed size from config
        bed_size_x = config.get("printer", "bed_size_x", 250.0)
        bed_size_y = config.get("printer", "bed_size_y", 220.0)

        # Create two-pass processor (combined file includes user pause)
        processor = TwoPassProcessor(
            config, bed_size_x, bed_size_y, include_user_pause=True
        )

        # Convert points to events
        events = []
        timestamp = time.time()

        # Send points as path events with proper path management
        current_path_id = None
        for i, point in enumerate(points):
            path_id = point.get("path_id", "default_path")

            # Send path start event if this is a new path
            if path_id != current_path_id:
                if current_path_id is not None:
                    # Complete previous path
                    path_complete_event = Event(
                        event_type=EventType.PATH_PROCESSING,
                        timestamp=timestamp,
                        data={"action": "path_complete", "path_id": current_path_id},
                        source="microweldr_cli",
                    )
                    events.append(path_complete_event)

                # Start new path
                path_start_event = Event(
                    event_type=EventType.PATH_PROCESSING,
                    timestamp=timestamp,
                    data={
                        "action": "path_start",
                        "path_data": {
                            "id": path_id,
                            "weld_type": point.get("weld_type", "normal"),
                        },
                    },
                    source="microweldr_cli",
                )
                events.append(path_start_event)
                current_path_id = path_id

            # Send point event
            point_event = Event(
                event_type=EventType.PATH_PROCESSING,
                timestamp=timestamp,
                data={"action": "point_added", "point": point},
                source="microweldr_cli",
            )
            events.append(point_event)

        # Complete final path
        if current_path_id is not None:
            path_complete_event = Event(
                event_type=EventType.PATH_PROCESSING,
                timestamp=timestamp,
                data={"action": "path_complete", "path_id": current_path_id},
                source="microweldr_cli",
            )
            events.append(path_complete_event)

        # Process with two-pass coordinate centering
        success = processor.process_with_centering(
            events=events,
            output_path=Path(output_path),
            verbose=getattr(args, "verbose", False),
        )

        if success:
            # Log centering statistics
            stats = processor.get_centering_statistics()
            offset_x = stats["centering_offset"]["x"]
            offset_y = stats["centering_offset"]["y"]
            print(f"📐 Applied centering offset: ({offset_x:+.3f}, {offset_y:+.3f})mm")

        return success

    except Exception as e:
        print(f"❌ G-code generation failed: {e}")
        return False


def generate_animation(points: List[dict], output_path: str, config: Config) -> bool:
    """Generate animated GIF showing weld sequence progression."""
    try:
        output_path_obj = Path(output_path)

        # Ensure .gif extension
        if not output_path_obj.suffix.lower() == ".gif":
            output_path_obj = output_path_obj.with_suffix(".gif")
            print(f"ℹ️  Changed animation output to: {output_path_obj}")
            output_path = str(output_path_obj)  # Update the string path too

        print(f"🎨 Generating animated GIF: {output_path_obj}")
        subscriber = GIFAnimationSubscriber(output_path_obj, config)

        # Send events to generate animation
        timestamp = time.time()

        # Start processing
        start_event = Event(
            event_type=EventType.OUTPUT_GENERATION,
            timestamp=timestamp,
            data={"action": "processing_start"},
            source="microweldr_cli",
        )
        subscriber.handle_event(start_event)

        # Send points as path events with proper path management
        current_path_id = None
        for i, point in enumerate(points):
            path_id = point.get("path_id", "default_path")

            # Send path start event if this is a new path
            if path_id != current_path_id:
                if current_path_id is not None:
                    # Complete previous path
                    path_complete_event = PathEvent(
                        action="path_complete", path_id=current_path_id
                    )
                    subscriber.handle_event(path_complete_event)

                # Start new path
                path_start_event = PathEvent(action="path_start", path_id=path_id)
                subscriber.handle_event(path_start_event)
                current_path_id = path_id

            # Send point event
            point_event = PathEvent(
                action="point_added",
                path_id=path_id,
                point=point,
            )
            subscriber.handle_event(point_event)

        # Complete final path
        if current_path_id is not None:
            path_complete_event = PathEvent(
                action="path_complete", path_id=current_path_id
            )
            subscriber.handle_event(path_complete_event)

        # End processing
        end_event = Event(
            event_type=EventType.OUTPUT_GENERATION,
            timestamp=timestamp + len(points) * 0.001,
            data={"action": "processing_complete"},
            source="microweldr_cli",
        )
        subscriber.handle_event(end_event)

        # Check if file was created
        if Path(output_path).exists():
            file_size = Path(output_path).stat().st_size
            print(f"✅ PNG animation generated: {output_path} ({file_size:,} bytes)")
            return True
        else:
            print(f"❌ Failed to generate PNG animation: {output_path}")
            return False

    except Exception as e:
        print(f"❌ Animation generation failed: {e}")
        return False


def main():
    """Main entry point for simplified CLI."""
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging
    log_level = "WARNING" if args.quiet else "INFO"
    setup_logging(level=log_level, console=True)

    # Check if any weld file is provided
    if not args.weld_file and not args.frangible_file:
        print("❌ No input files specified")
        print("💡 Use -weld for structural welds or -frange for frangible welds")
        print("   Example: microweldr -weld design.svg")
        parser.print_help()
        return 1

    try:
        print("🚀 MicroWeldr - Simplified Plastic Welding")
        print("=" * 50)

        # Load configuration
        print("📋 Loading configuration...")
        config = Config()
        print("✅ Configuration loaded")

        # Process input files
        all_points = []

        if args.weld_file:
            structural_points = process_weld_file(
                args.weld_file, config, is_frangible=False
            )
            all_points.extend(structural_points)

        if args.frangible_file:
            frangible_points = process_weld_file(
                args.frangible_file, config, is_frangible=True
            )
            all_points.extend(frangible_points)

        if not all_points:
            print("❌ No weld points found in input files")
            return 1

        print(f"📊 Total points to process: {len(all_points)}")

        # Determine output filename
        if args.gcode_output:
            gcode_output = args.gcode_output
        else:
            # Auto-generate from first input file
            primary_file = args.weld_file or args.frangible_file
            gcode_output = auto_generate_output_filename(primary_file)

        # Validate filename length
        if not validate_filename_length(gcode_output):
            return 1

        # Generate G-code
        if not generate_gcode(all_points, gcode_output, config, args):
            return 1

        # Generate animation if requested
        animation_output = None
        if args.animation:
            # Ensure .gif extension for display
            animation_path = Path(args.animation)
            if not animation_path.suffix.lower() == ".gif":
                animation_output = str(animation_path.with_suffix(".gif"))
            else:
                animation_output = args.animation

            if not generate_animation(all_points, args.animation, config):
                print(
                    "⚠️  Animation generation failed, but G-code was created successfully"
                )

        print("\n🎉 Welding preparation completed successfully!")
        print(f"📁 Output files:")
        print(f"   • G-code: {gcode_output}")
        if animation_output:
            print(f"   • Animation: {animation_output}")

        return 0

    except FileNotFoundError as e:
        print(f"❌ File error: {e}")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        if not args.quiet:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
