"""Simple point iterator that generates welding points without multi-pass logic."""

import logging
from pathlib import Path
from typing import Iterator, Dict, Any
from .point_iterator_factory import PointIteratorFactory

logger = logging.getLogger(__name__)


def iterate_multipass_points_from_file(
    file_path: Path, config: Dict[str, Any]
) -> Iterator[Dict[str, Any]]:
    """Iterate through welding points from a file (simplified, no multi-pass).

    This generates points directly from the parsed SVG/DXF without complex
    multi-pass spacing calculations. All generators receive the same simple points.
    """
    logger.debug(f"Starting simple point iteration from {file_path}")

    # Get iterator for the file type (using default config for now)
    iterator = PointIteratorFactory.create_iterator(str(file_path))

    total_points = 0
    for point in iterator.iterate_points(file_path):
        yield {
            "x": point.x,
            "y": point.y,
            "weld_type": point.weld_type,
            "path_id": getattr(point, "path_id", f"path_{total_points}"),
            "path_weld_type": point.weld_type,
        }
        total_points += 1

    logger.info(f"Simple iteration complete: {total_points} total welding points")
