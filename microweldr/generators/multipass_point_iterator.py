"""Simple point iterator that generates welding points without multi-pass logic."""

import logging
from pathlib import Path
from typing import Iterator, Dict, Any
from .point_iterator_factory import PointIteratorFactory

logger = logging.getLogger(__name__)


def iterate_multipass_points_from_file(
    file_path: Path, config: Dict[str, Any], enable_deduplication: bool = True
) -> Iterator[Dict[str, Any]]:
    """Iterate through welding points from a file (simplified, no multi-pass).

    This generates points directly from the parsed SVG/DXF without complex
    multi-pass spacing calculations. All generators receive the same simple points.

    Args:
        file_path: Path to the file to process
        config: Configuration dictionary
        enable_deduplication: If True, filters duplicate points at same coordinates
    """
    logger.debug(f"Starting simple point iteration from {file_path}")

    # Use the main iterate_points_from_file function with deduplication
    from .point_iterator_factory import iterate_points_from_file

    total_points = 0
    for point_data in iterate_points_from_file(
        file_path, config=config, enable_deduplication=enable_deduplication
    ):
        yield {
            "x": point_data["x"],
            "y": point_data["y"],
            "weld_type": point_data["weld_type"],
            "path_id": point_data.get("path_id", f"path_{total_points}"),
            "path_weld_type": point_data["weld_type"],
        }
        total_points += 1

    logger.info(f"Simple iteration complete: {total_points} total welding points")
