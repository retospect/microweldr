"""Convert command for processing SVG and DXF files."""

import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import List

from .base import BaseCommand
from ...core.config import Config
from ...core.dxf_reader import create_dxf_reader
from ...core.svg_reader import SVGReader
from ...core.file_readers import MultiFileReader, LoggingSubscriber, StatsCollector
from ...core.error_handling import FileProcessingError, ConfigurationError
from ...core.app_constants import FileExtensions

logger = logging.getLogger(__name__)


class ConvertCommand(BaseCommand):
    """Command to convert SVG and DXF files to G-code."""

    def __init__(self):
        super().__init__(
            name="convert",
            description="Convert SVG and DXF files to G-code for welding",
        )

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add convert command arguments."""
        parser.add_argument(
            "input_files",
            nargs="+",
            type=Path,
            help="Input SVG or DXF files to convert",
        )
        parser.add_argument(
            "-o",
            "--output",
            type=Path,
            help="Output G-code file (default: input_file.gcode)",
        )
        parser.add_argument(
            "--animation", action="store_true", help="Generate animation SVG file"
        )
        parser.add_argument(
            "--validate-only",
            action="store_true",
            help="Only validate files, don't generate output",
        )
        parser.add_argument(
            "--weld-type",
            choices=["normal", "frangible", "auto"],
            default="auto",
            help="Override weld type (auto-detect by default)",
        )

    def execute(self, args: Namespace) -> bool:
        """Execute the convert command."""
        try:
            # Load configuration
            config = Config(args.config if hasattr(args, "config") else None)

            # Set up file readers
            file_reader = self._setup_file_readers(args)

            # Process input files
            all_paths = []
            for input_file in args.input_files:
                if not input_file.exists():
                    logger.error(f"Input file not found: {input_file}")
                    return False

                if not self._is_supported_file(input_file):
                    logger.error(f"Unsupported file type: {input_file.suffix}")
                    return False

                try:
                    paths = file_reader.parse_file(input_file)
                    all_paths.extend(paths)
                    logger.info(f"Processed {input_file}: {len(paths)} paths found")
                except FileProcessingError as e:
                    logger.error(f"Failed to process {input_file}: {e}")
                    return False

            if not all_paths:
                logger.error("No weld paths found in input files")
                return False

            logger.info(f"Total paths found: {len(all_paths)}")

            # If validation only, we're done
            if args.validate_only:
                logger.info("Validation completed successfully")
                return True

            # Generate outputs
            return self._generate_outputs(args, config, all_paths)

        except ConfigurationError as e:
            logger.error(f"Configuration error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False

    def _setup_file_readers(self, args: Namespace) -> MultiFileReader:
        """Set up file readers with appropriate subscribers."""
        file_reader = MultiFileReader()

        # Register SVG reader
        svg_reader = SVGReader()
        file_reader.register_reader(svg_reader)

        # Register DXF reader if available
        dxf_reader = create_dxf_reader()
        if dxf_reader:
            file_reader.register_reader(dxf_reader)
            logger.info("DXF reader available")
        else:
            logger.warning("DXF reader not available - install ezdxf for DXF support")

        # Add subscribers
        verbose = hasattr(args, "verbose") and args.verbose
        file_reader.subscribe(LoggingSubscriber(verbose=verbose))
        file_reader.subscribe(StatsCollector())

        return file_reader

    def _is_supported_file(self, file_path: Path) -> bool:
        """Check if file type is supported."""
        supported_extensions = [FileExtensions.SVG, FileExtensions.DXF]
        return file_path.suffix.lower() in supported_extensions

    def _generate_outputs(
        self, args: Namespace, config: Config, weld_paths: List
    ) -> bool:
        """Generate G-code and optional animation outputs."""
        try:
            # Determine output file
            if args.output:
                output_file = args.output
            else:
                # Use first input file as base for output name
                base_name = args.input_files[0].stem
                output_file = Path(f"{base_name}.gcode")

            # Generate G-code
            from ...core.gcode_generator import GCodeGenerator

            gcode_gen = GCodeGenerator(config)
            gcode_content = gcode_gen.generate_gcode(weld_paths)

            # Write G-code file
            with open(output_file, "w") as f:
                f.write(gcode_content)

            logger.info(f"G-code written to: {output_file}")

            # Generate animation if requested
            if args.animation:
                animation_file = output_file.with_suffix("_animation.svg")

                from ...animation.generator import AnimationGenerator

                anim_gen = AnimationGenerator(config)
                animation_content = anim_gen.generate_animation(weld_paths)

                with open(animation_file, "w") as f:
                    f.write(animation_content)

                logger.info(f"Animation written to: {animation_file}")

            return True

        except Exception as e:
            logger.error(f"Failed to generate outputs: {e}")
            return False
