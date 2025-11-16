"""SVG point iterator for streaming point generation."""

import logging
from pathlib import Path
from typing import Iterator, Dict, Any

from ..core.unified_config import UnifiedConfig

logger = logging.getLogger(__name__)


class SVGPointIterator:
    """Iterator for extracting points from SVG files.

    This class provides a clean interface for iterating through points in SVG files
    without loading all points into memory at once. It handles color-based weld type
    detection and path interpolation.
    """

    # Class constants
    SUPPORTED_EXTENSIONS = [".svg"]

    def __init__(self, dot_spacing: float = None):
        """Initialize SVG point iterator.

        Args:
            dot_spacing: Spacing between interpolated points in mm.
                        If None, uses unified config.
        """
        if dot_spacing is None:
            config = UnifiedConfig()
            main_config = config.get_main_config()
            self.dot_spacing = main_config.get("normal_welds", {}).get(
                "dot_spacing", 1.0
            )
        else:
            self.dot_spacing = dot_spacing

    def iterate_points(self, file_path: Path) -> Iterator[Dict[str, Any]]:
        """Iterate through points in an SVG file.

        Args:
            file_path: Path to the SVG file

        Yields:
            Dict containing point data with keys: x, y, weld_type, path_id, custom_*

        Raises:
            Exception: If SVG parsing fails
        """
        try:
            # Import SVG parser from parsers directory
            from ..parsers.svg_parser import SVGParser

            # Create parser and parse the SVG file
            parser = SVGParser(dot_spacing=self.dot_spacing)
            weld_paths = parser.parse_file(str(file_path))

            logger.info(f"Parsed {len(weld_paths)} paths from SVG file {file_path}")

            total_points = 0
            for path in weld_paths:
                path_id = path.svg_id or f"path_{total_points}"
                logger.debug(f"Path {path_id}: {len(path.points)} points")

                for point in path.points:
                    yield {
                        "x": point.x,
                        "y": point.y,
                        "weld_type": point.weld_type,
                        "path_id": path_id,
                        "weld_height": point.weld_height,
                    }
                    total_points += 1

            logger.info(f"Iterated through {total_points} total points from SVG")

        except Exception as e:
            logger.error(f"Error reading SVG file {file_path}: {e}")
            raise

    def count_points(self, file_path: Path) -> int:
        """Count total points in an SVG file without storing them.

        Args:
            file_path: Path to the SVG file

        Returns:
            Total number of points in the file
        """
        count = 0
        for _ in self.iterate_points(file_path):
            count += 1
        return count

    @staticmethod
    def supports_file(file_path: Path) -> bool:
        """Check if this iterator supports the given file type.

        Args:
            file_path: Path to check

        Returns:
            True if file is supported SVG format
        """
        return file_path.suffix.lower() in [".svg"]
