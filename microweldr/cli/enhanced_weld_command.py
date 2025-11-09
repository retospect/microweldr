"""Enhanced weld command using factory pattern for file processing."""

from pathlib import Path
import logging

from ..core.config import Config
from ..core.event_processor import EventDrivenProcessor
from ..core.error_handling import FileProcessingError

logger = logging.getLogger(__name__)


def cmd_weld_enhanced(args):
    """Enhanced weld command using factory pattern for SVG/DXF processing."""
    print("🔥 MicroWeldr - SVG/DXF to G-code Conversion")
    print("=" * 50)

    try:
        # Load configuration
        config = Config(args.config)
        if args.verbose:
            print(f"✓ Configuration loaded from {args.config}")

        # Validate input file
        input_path = Path(args.svg_file)
        if not input_path.exists():
            print(f"❌ Input file not found: {args.svg_file}")
            return False

        if args.verbose:
            print(f"✓ Input file found: {args.svg_file}")

        # Create event-driven processor
        processor = EventDrivenProcessor(config)

        # Check if input file type is supported
        supported_inputs = processor.get_supported_input_extensions()
        if input_path.suffix.lower() not in supported_inputs:
            print(f"❌ Unsupported input file type: {input_path.suffix}")
            print(f"   Supported types: {', '.join(supported_inputs)}")
            return False

        # Determine output paths
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = input_path.with_suffix(".gcode")

        # Determine animation path
        animation_path = None
        if not getattr(args, "no_animation", False):
            if getattr(args, "png", False):
                animation_path = output_path.with_name(
                    f"{output_path.stem}_animation.png"
                )
            else:
                animation_path = output_path.with_name(
                    f"{output_path.stem}_animation.svg"
                )

        if args.verbose:
            print(f"✓ Output G-code: {output_path}")
            if animation_path:
                print(f"✓ Animation: {animation_path}")

        # Process file using factory pattern
        print(f"🔧 Processing {input_path.suffix.upper()} file...")

        success = processor.process_file(
            input_path=input_path,
            output_path=output_path,
            animation_path=animation_path,
            skip_bed_leveling=getattr(args, "skip_bed_leveling", False),
            no_calibrate=getattr(args, "no_calibrate", False),
            verbose=getattr(args, "verbose", False),
        )

        if success:
            print(f"✅ G-code written to: {output_path}")
            if animation_path and animation_path.exists():
                print(f"🎬 Animation written to: {animation_path}")
                print(
                    f"🌐 Open {animation_path} in a web browser to view the animation"
                )

            # Show weld statistics
            print("\n📊 Processing Summary:")
            print(f"   Input: {input_path.name} ({input_path.suffix.upper()})")
            print(f"   Output: {output_path.name}")
            if animation_path:
                print(f"   Animation: {animation_path.name}")

            return True
        else:
            print("❌ File processing failed")
            return False

    except FileProcessingError as e:
        print(f"❌ File processing error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return False


def cmd_full_weld_enhanced(args):
    """Enhanced full-weld command using factory pattern."""
    print("🔥 MicroWeldr - Self-Contained G-code Generation")
    print("=" * 50)

    try:
        # Load configuration
        config = Config(args.config)
        if args.verbose:
            print(f"✓ Configuration loaded from {args.config}")

        # Validate input file
        input_path = Path(args.svg_file)
        if not input_path.exists():
            print(f"❌ Input file not found: {args.svg_file}")
            return False

        # Create event-driven processor
        processor = EventDrivenProcessor(config)

        # Determine output paths
        if args.output:
            output_path = Path(args.output)
        else:
            output_path = input_path.with_suffix(".gcode")

        # Determine animation path
        animation_path = None
        if not getattr(args, "no_animation", False):
            if getattr(args, "png", False):
                animation_path = output_path.with_name(
                    f"{output_path.stem}_animation.png"
                )
            else:
                animation_path = output_path.with_name(
                    f"{output_path.stem}_animation.svg"
                )

        print(
            f"🔧 Processing {input_path.suffix.upper()} file for self-contained G-code..."
        )

        # Process with full-weld options (no calibration skipping)
        success = processor.process_file(
            input_path=input_path,
            output_path=output_path,
            animation_path=animation_path,
            skip_bed_leveling=False,  # Full weld includes everything
            no_calibrate=False,  # Full weld includes calibration
            full_weld=True,  # Special flag for self-contained mode
            verbose=getattr(args, "verbose", False),
        )

        if success:
            print(f"✅ Self-contained G-code written to: {output_path}")
            if animation_path and animation_path.exists():
                print(f"🎬 Animation written to: {animation_path}")

            print("\n🎯 Ready for printing!")
            print(
                "   This G-code includes all heating, calibration, and safety procedures."
            )

            return True
        else:
            print("❌ File processing failed")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        if getattr(args, "verbose", False):
            import traceback

            traceback.print_exc()
        return False
