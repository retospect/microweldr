"""Enhanced weld command using factory pattern for file processing."""

from pathlib import Path
import logging

from ..core.config import Config
from ..core.event_processor import EventDrivenProcessor
from ..core.error_handling import FileProcessingError

logger = logging.getLogger(__name__)


def cmd_weld_enhanced(args) -> bool:
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
        processor = EventDrivenProcessor(config, verbose=args.verbose)

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
        if args.no_animation:
            animation_path = None
        else:
            animation_path = input_path.with_suffix("_animation.svg")

        if args.verbose:
            print(f"✓ Output G-code: {output_path}")
            if animation_path:
                print(f"✓ Animation: {animation_path}")

        # Process the file using event-driven architecture
        success = processor.process_file(
            input_path=input_path,
            output_path=output_path,
            animation_path=animation_path,
            verbose=args.verbose,
        )

        if success:
            print("✅ G-code written to:", output_path)
            if animation_path and animation_path.exists():
                print("🎬 Animation written to:", animation_path)
                print(
                    "🌐 Open", animation_path, "in a web browser to view the animation"
                )

            # Submit to printer if requested
            if args.submit or args.auto_start:
                submit_success = _submit_to_printer(
                    output_path,
                    args.submit,
                    args.auto_start,
                    args.queue_only,
                    args.verbose,
                )
                if not submit_success:
                    success = False
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


def _submit_to_printer(
    gcode_path: Path, submit: bool, auto_start: bool, queue_only: bool, verbose: bool
) -> bool:
    """Submit G-code to printer using centralized printer service."""
    print("🚀 Submitting to printer...")

    try:
        from ..core.printer_service import get_printer_service

        # Get printer service
        printer_service = get_printer_service()

        # Test connection
        if verbose:
            print("🔍 Testing printer connection...")

        if not printer_service.test_connection():
            print("❌ Failed to connect to printer")
            print("   Please check your printer configuration and network connection")
            return False

        # Check printer status
        if verbose:
            print("🔍 Checking printer status...")

        status = printer_service.get_status()

        if verbose:
            print(f"   Printer state: {status.state.value}")

        if not status.is_ready_for_job:
            print(f"⚠️  Printer not ready (state: {status.state.value})")
            if status.is_printing:
                print("   Printer is currently printing")
            return False

        # Upload file
        filename = gcode_path.name
        print(f"📤 Uploading {filename}...")

        upload_success = printer_service.upload_gcode(
            gcode_path,
            remote_filename=filename,
            auto_start=auto_start and not queue_only,
            overwrite=True,
        )

        if upload_success:
            print(f"✅ File uploaded successfully: {filename}")

            if auto_start and not queue_only:
                print("🔥 Print started automatically")
            elif queue_only:
                print("📋 File queued for later printing")
            else:
                print("📁 File ready for manual printing")

            return True
        else:
            print("❌ Failed to upload file to printer")
            return False

    except Exception as e:
        print(f"❌ Printer submission failed: {e}")
        if verbose:
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
