"""DXF point iterator for streaming point generation."""

import logging
from pathlib import Path
from typing import Iterator, Dict, Any

from ..core.unified_config import UnifiedConfig

logger = logging.getLogger(__name__)


class DXFPointIterator:
    """Iterator for extracting points from DXF files.

    This class provides a clean interface for iterating through points in DXF files
    without loading all points into memory at once. It handles layer-based weld type
    detection and entity conversion.
    """

    # Class constants
    SUPPORTED_EXTENSIONS = [".dxf"]

    def __init__(self, dot_spacing: float = None):
        """Initialize DXF point iterator.

        Args:
            dot_spacing: Spacing between points in mm. If None, uses unified config.
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
        """Iterate through points in a DXF file.

        Args:
            file_path: Path to the DXF file

        Yields:
            Dict containing point data with keys: x, y, weld_type, path_id, custom_*

        Raises:
            Exception: If DXF parsing fails
        """
        try:
            # Import DXF reader from parsers directory
            from ..parsers.dxf_reader import DXFReader

            # Use existing DXF reader to parse file with dot spacing
            reader = DXFReader(dot_spacing=self.dot_spacing)
            weld_paths = reader.parse_file(file_path)

            logger.info(f"DXF file contains {len(weld_paths)} paths")

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

            logger.info(f"Iterated through {total_points} total points from DXF")

        except Exception as e:
            logger.error(f"Error reading DXF file {file_path}: {e}")
            raise

    def count_points(self, file_path: Path) -> int:
        """Count total points in a DXF file without storing them.

        Args:
            file_path: Path to the DXF file

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
            True if file is supported DXF format
        """
        return file_path.suffix.lower() == ".dxf"
