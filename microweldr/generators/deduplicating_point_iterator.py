"""Deduplicating point iterator wrapper that filters duplicate weld points."""

import logging
from pathlib import Path
from typing import Iterator, Dict, Any, Set, Tuple

from .point_iterator_factory import PointIteratorFactory

logger = logging.getLogger(__name__)


class DeduplicatingPointIterator:
    """Wrapper that filters duplicate weld points based on rounded coordinates.

    This iterator wraps existing point iterators and maintains a hash set of
    previously seen coordinates (rounded to 0.1mm precision) to prevent
    duplicate welds at the same location.
    """

    def __init__(self, precision_mm: float = 0.1):
        """Initialize deduplicating iterator.

        Args:
            precision_mm: Rounding precision in mm for coordinate comparison.
                         Default 0.1mm means coordinates are rounded to nearest 0.1mm.
        """
        self.precision_mm = precision_mm
        self.seen_coordinates: Set[Tuple[float, float, str]] = set()

    def _round_coordinate(self, value: float) -> float:
        """Round coordinate to specified precision.

        Args:
            value: Coordinate value to round

        Returns:
            Rounded coordinate value
        """
        return round(value / self.precision_mm) * self.precision_mm

    def _get_coordinate_key(
        self, x: float, y: float, weld_type: str
    ) -> Tuple[float, float, str]:
        """Get coordinate key for duplicate detection.

        Args:
            x: X coordinate
            y: Y coordinate
            weld_type: Type of weld

        Returns:
            Tuple of (rounded_x, rounded_y, weld_type) for use as hash key
        """
        rounded_x = self._round_coordinate(x)
        rounded_y = self._round_coordinate(y)
        return (rounded_x, rounded_y, weld_type)

    def iterate_points(self, file_path: Path, config=None) -> Iterator[Dict[str, Any]]:
        """Iterate through points, filtering duplicates.

        Args:
            file_path: Path to the file to process
            config: Configuration object

        Yields:
            Dict containing point data, with duplicates filtered out
        """
        # Clear seen coordinates for new file
        self.seen_coordinates.clear()

        logger.info(
            f"🔍 Starting deduplication for {file_path.name} with {self.precision_mm}mm precision"
        )

        # Get the underlying iterator
        iterator = PointIteratorFactory.create_iterator(file_path, config=config)

        total_points = 0
        filtered_points = 0

        for point_data in iterator.iterate_points(file_path):
            total_points += 1

            # Extract coordinates and weld type
            x = point_data["x"]
            y = point_data["y"]
            weld_type = point_data["weld_type"]

            # Create coordinate key
            coord_key = self._get_coordinate_key(x, y, weld_type)

            # Check if we've seen this coordinate before
            if coord_key in self.seen_coordinates:
                filtered_points += 1
                logger.info(
                    f"🚫 Filtered duplicate {weld_type} weld at "
                    f"({coord_key[0]:.1f}, {coord_key[1]:.1f})"
                )
                continue

            # Add to seen coordinates and yield the point
            self.seen_coordinates.add(coord_key)
            yield point_data

        if filtered_points > 0:
            logger.info(
                f"Filtered {filtered_points} duplicate points out of {total_points} total points "
                f"from {file_path.name}"
            )
        else:
            logger.debug(f"No duplicate points found in {file_path.name}")

    def count_points(self, file_path: Path, config=None) -> int:
        """Count total unique points in a file.

        Args:
            file_path: Path to the file
            config: Configuration object

        Returns:
            Total number of unique points in the file
        """
        return sum(1 for _ in self.iterate_points(file_path, config=config))


def iterate_points_from_file_deduplicated(
    file_path: Path, config=None, precision_mm: float = 0.1
) -> Iterator[Dict[str, Any]]:
    """Iterate through points from a file with duplicate filtering.

    Args:
        file_path: Path to the file to process
        config: Configuration object
        precision_mm: Rounding precision in mm for coordinate comparison

    Yields:
        Dict containing point data with duplicates filtered out
    """
    dedup_iterator = DeduplicatingPointIterator(precision_mm=precision_mm)
    yield from dedup_iterator.iterate_points(file_path, config=config)
