"""Point iterator for two-phase processing architecture."""

import logging
from pathlib import Path
from typing import Iterator, Dict, Any, Union
from .dxf_reader import DXFReader

logger = logging.getLogger(__name__)


def iterate_points_from_file(file_path: Union[str, Path]) -> Iterator[Dict[str, Any]]:
    """
    Iterator that yields points from DXF/SVG files.

    This is used in both Phase 1 (analysis) and Phase 2 (generation)
    to avoid loading all points into memory at once.

    Args:
        file_path: Path to DXF or SVG file

    Yields:
        Dict containing point data: {"x": float, "y": float, "weld_type": str, "path_id": str}
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    logger.debug(f"Starting point iteration from {file_path}")

    if file_path.suffix.lower() == ".dxf":
        yield from _iterate_dxf_points(file_path)
    elif file_path.suffix.lower() in [".svg"]:
        yield from _iterate_svg_points(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix}")


def _iterate_dxf_points(file_path: Path) -> Iterator[Dict[str, Any]]:
    """Iterate through points in a DXF file."""
    try:
        # Use existing DXF reader to parse file
        reader = DXFReader()
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
                    "path_weld_type": path.weld_type,
                }
                total_points += 1

        logger.info(f"Iterated through {total_points} total points")

    except Exception as e:
        logger.error(f"Error reading DXF file {file_path}: {e}")
        raise


def _iterate_svg_points(file_path: Path) -> Iterator[Dict[str, Any]]:
    """Iterate through points in an SVG file."""
    # TODO: Implement SVG point iteration when needed
    # For now, raise not implemented
    raise NotImplementedError("SVG point iteration not yet implemented")


def count_points_in_file(file_path: Union[str, Path]) -> int:
    """Count total points in a file without storing them."""
    count = 0
    for _ in iterate_points_from_file(file_path):
        count += 1
    return count
