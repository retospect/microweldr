"""Validate command for checking SVG and DXF files."""

import logging
from argparse import ArgumentParser, Namespace
from pathlib import Path

from .base import BaseCommand
from ...core.dxf_reader import create_dxf_reader
from ...core.svg_reader import SVGReader
from ...core.file_readers import MultiFileReader, LoggingSubscriber, StatsCollector
from ...core.error_handling import FileProcessingError
from ...core.app_constants import FileExtensions

logger = logging.getLogger(__name__)


class ValidateCommand(BaseCommand):
    """Command to validate SVG and DXF files."""

    def __init__(self):
        super().__init__(
            name="validate",
            description="Validate SVG and DXF files for welding compatibility",
        )

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Add validate command arguments."""
        parser.add_argument(
            "input_files",
            nargs="+",
            type=Path,
            help="Input SVG or DXF files to validate",
        )
        parser.add_argument(
            "--detailed",
            action="store_true",
            help="Show detailed validation information",
        )

    def execute(self, args: Namespace) -> bool:
        """Execute the validate command."""
        try:
            # Set up file readers
            file_reader = self._setup_file_readers(args)
            stats_collector = StatsCollector()
            file_reader.subscribe(stats_collector)

            all_valid = True
            total_files = len(args.input_files)

            logger.info(f"Validating {total_files} files...")

            for i, input_file in enumerate(args.input_files, 1):
                logger.info(f"[{i}/{total_files}] Validating: {input_file}")

                if not input_file.exists():
                    logger.error(f"File not found: {input_file}")
                    all_valid = False
                    continue

                if not self._is_supported_file(input_file):
                    logger.error(f"Unsupported file type: {input_file.suffix}")
                    all_valid = False
                    continue

                try:
                    paths = file_reader.parse_file(input_file)

                    if not paths:
                        logger.warning(f"No weld paths found in: {input_file}")
                        continue

                    # Perform detailed validation
                    file_valid = self._validate_paths(paths, input_file, args.detailed)
                    if not file_valid:
                        all_valid = False

                    logger.info(f"✓ {input_file}: {len(paths)} paths found")

                except FileProcessingError as e:
                    logger.error(f"✗ {input_file}: {e}")
                    all_valid = False
                    continue

            # Print summary
            self._print_summary(stats_collector, all_valid)

            return all_valid

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False

    def _setup_file_readers(self, args: Namespace) -> MultiFileReader:
        """Set up file readers."""
        file_reader = MultiFileReader()

        # Register readers
        svg_reader = SVGReader()
        file_reader.register_reader(svg_reader)

        dxf_reader = create_dxf_reader()
        if dxf_reader:
            file_reader.register_reader(dxf_reader)

        # Add logging subscriber
        verbose = hasattr(args, "verbose") and args.verbose
        file_reader.subscribe(LoggingSubscriber(verbose=verbose))

        return file_reader

    def _is_supported_file(self, file_path: Path) -> bool:
        """Check if file type is supported."""
        supported_extensions = [FileExtensions.SVG, FileExtensions.DXF]
        return file_path.suffix.lower() in supported_extensions

    def _validate_paths(self, paths: list, file_path: Path, detailed: bool) -> bool:
        """Validate weld paths from a file."""
        valid = True

        for i, path in enumerate(paths):
            if len(path.points) < 2:
                logger.error(
                    f"Path {i+1} in {file_path}: insufficient points ({len(path.points)})"
                )
                valid = False
                continue

            # Check for reasonable path length
            if path.length < 0.1:  # Less than 0.1mm
                logger.warning(
                    f"Path {i+1} in {file_path}: very short path ({path.length:.3f}mm)"
                )

            if detailed:
                logger.info(
                    f"  Path {i+1}: {len(path.points)} points, "
                    f"{path.length:.2f}mm, type: {path.weld_type.value}"
                )

        return valid

    def _print_summary(self, stats_collector: StatsCollector, all_valid: bool) -> None:
        """Print validation summary."""
        stats = stats_collector.total_stats

        logger.info("\n" + "=" * 50)
        logger.info("VALIDATION SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Files processed: {stats.files_processed}")
        logger.info(f"Total paths: {stats.total_paths}")
        logger.info(f"Total points: {stats.total_points}")
        logger.info(f"Normal welds: {stats.normal_welds}")
        logger.info(f"Frangible welds: {stats.frangible_welds}")

        if stats.errors:
            logger.info(f"Errors: {len(stats.errors)}")
            for error in stats.errors:
                logger.error(f"  - {error}")

        if stats.warnings:
            logger.info(f"Warnings: {len(stats.warnings)}")
            for warning in stats.warnings:
                logger.warning(f"  - {warning}")

        status = "✓ PASSED" if all_valid else "✗ FAILED"
        logger.info(f"\nValidation result: {status}")
        logger.info("=" * 50)
