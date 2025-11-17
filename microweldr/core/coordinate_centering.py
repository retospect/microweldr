"""
Coordinate centering utilities for MicroWeldr.
Provides automatic centering of welding patterns on the printer bed.
"""

import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class CoordinateCentering:
    """Handles automatic centering of welding coordinates on printer bed."""

    def __init__(self, bed_size_x: float = 250.0, bed_size_y: float = 220.0):
        """Initialize coordinate centering.

        Args:
            bed_size_x: Printer bed width in mm
            bed_size_y: Printer bed depth in mm
        """
        self.bed_size_x = bed_size_x
        self.bed_size_y = bed_size_y
        self.bed_center_x = bed_size_x / 2
        self.bed_center_y = bed_size_y / 2

        # Coordinate tracking
        self.coordinates: List[Tuple[float, float]] = []
        self.offset_x: Optional[float] = None
        self.offset_y: Optional[float] = None
        self.bounds_calculated = False

    def add_coordinate(self, x: float, y: float) -> None:
        """Add a coordinate to the tracking list."""
        self.coordinates.append((x, y))

    def calculate_centering_offset(self) -> Tuple[float, float]:
        """Calculate the offset needed to center all coordinates on the bed.

        Returns:
            Tuple of (offset_x, offset_y) in mm
        """
        if not self.coordinates:
            logger.warning("No coordinates available for centering calculation")
            return 0.0, 0.0

        # Calculate bounding box
        x_coords = [x for x, y in self.coordinates]
        y_coords = [y for x, y in self.coordinates]

        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        # Calculate current pattern center
        pattern_center_x = (x_min + x_max) / 2
        pattern_center_y = (y_min + y_max) / 2

        # Calculate offset to center on bed
        self.offset_x = self.bed_center_x - pattern_center_x
        self.offset_y = self.bed_center_y - pattern_center_y

        self.bounds_calculated = True

        # Log centering information
        width = x_max - x_min
        height = y_max - y_min

        logger.info(
            f"Pattern bounds: X({x_min:.3f} to {x_max:.3f}), Y({y_min:.3f} to {y_max:.3f})"
        )
        logger.info(f"Pattern size: {width:.3f} x {height:.3f}mm")
        logger.info(f"Pattern center: ({pattern_center_x:.3f}, {pattern_center_y:.3f})")
        logger.info(f"Bed center: ({self.bed_center_x:.3f}, {self.bed_center_y:.3f})")
        logger.info(f"Centering offset: ({self.offset_x:+.3f}, {self.offset_y:+.3f})")

        # Verify bounds after centering
        new_x_min, new_x_max = x_min + self.offset_x, x_max + self.offset_x
        new_y_min, new_y_max = y_min + self.offset_y, y_max + self.offset_y

        logger.info(
            f"Centered bounds: X({new_x_min:.3f} to {new_x_max:.3f}), Y({new_y_min:.3f} to {new_y_max:.3f})"
        )

        # Check if pattern fits on bed
        if (
            new_x_min >= 0
            and new_x_max <= self.bed_size_x
            and new_y_min >= 0
            and new_y_max <= self.bed_size_y
        ):
            logger.info("✅ Centered pattern fits within bed bounds")
        else:
            logger.warning("⚠️ Centered pattern may exceed bed bounds")
            if new_x_min < 0:
                logger.warning(f"   X underflow: {new_x_min:.3f}mm")
            if new_x_max > self.bed_size_x:
                logger.warning(f"   X overflow: {new_x_max - self.bed_size_x:.3f}mm")
            if new_y_min < 0:
                logger.warning(f"   Y underflow: {new_y_min:.3f}mm")
            if new_y_max > self.bed_size_y:
                logger.warning(f"   Y overflow: {new_y_max - self.bed_size_y:.3f}mm")

        return self.offset_x, self.offset_y

    def apply_centering(self, x: float, y: float) -> Tuple[float, float]:
        """Apply centering offset to coordinates.

        Args:
            x: Original X coordinate
            y: Original Y coordinate

        Returns:
            Tuple of (centered_x, centered_y)
        """
        if not self.bounds_calculated:
            # If bounds haven't been calculated yet, return original coordinates
            # This happens during the first pass when we're collecting coordinates
            return x, y

        if self.offset_x is None or self.offset_y is None:
            logger.warning(
                "Centering offset not calculated, returning original coordinates"
            )
            return x, y

        return x + self.offset_x, y + self.offset_y

    def get_statistics(self) -> Dict:
        """Get centering statistics."""
        if not self.coordinates:
            return {"status": "no_coordinates"}

        x_coords = [x for x, y in self.coordinates]
        y_coords = [y for x, y in self.coordinates]

        stats = {
            "total_coordinates": len(self.coordinates),
            "original_bounds": {
                "x_min": min(x_coords),
                "x_max": max(x_coords),
                "y_min": min(y_coords),
                "y_max": max(y_coords),
            },
            "pattern_size": {
                "width": max(x_coords) - min(x_coords),
                "height": max(y_coords) - min(y_coords),
            },
            "bed_size": {
                "width": self.bed_size_x,
                "height": self.bed_size_y,
            },
            "bed_center": {
                "x": self.bed_center_x,
                "y": self.bed_center_y,
            },
        }

        if (
            self.bounds_calculated
            and self.offset_x is not None
            and self.offset_y is not None
        ):
            stats["centering_offset"] = {
                "x": self.offset_x,
                "y": self.offset_y,
            }
            stats["centered_bounds"] = {
                "x_min": stats["original_bounds"]["x_min"] + self.offset_x,
                "x_max": stats["original_bounds"]["x_max"] + self.offset_x,
                "y_min": stats["original_bounds"]["y_min"] + self.offset_y,
                "y_max": stats["original_bounds"]["y_max"] + self.offset_y,
            }

        return stats


class StreamingCoordinateCentering:
    """Streaming coordinate centering that applies a pre-calculated offset.

    This approach requires coordinates to be pre-analyzed to calculate the centering offset,
    then applies the offset during streaming G-code generation.
    """

    def __init__(self, bed_size_x: float = 250.0, bed_size_y: float = 220.0):
        """Initialize streaming centering."""
        self.bed_size_x = bed_size_x
        self.bed_size_y = bed_size_y
        self.bed_center_x = bed_size_x / 2
        self.bed_center_y = bed_size_y / 2
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.offset_calculated = False

    def set_offset_from_coordinates(
        self, coordinates: List[Tuple[float, float]]
    ) -> None:
        """Calculate and set centering offset from a list of coordinates.

        Args:
            coordinates: List of (x, y) coordinate tuples
        """
        if not coordinates:
            logger.warning("No coordinates provided for centering calculation")
            return

        # Calculate bounding box
        x_coords = [x for x, y in coordinates]
        y_coords = [y for x, y in coordinates]

        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)

        # Calculate current pattern center
        pattern_center_x = (x_min + x_max) / 2
        pattern_center_y = (y_min + y_max) / 2

        # Calculate offset to center on bed
        self.offset_x = self.bed_center_x - pattern_center_x
        self.offset_y = self.bed_center_y - pattern_center_y
        self.offset_calculated = True

        # Log centering information
        width = x_max - x_min
        height = y_max - y_min

        logger.info(
            f"Pattern bounds: X({x_min:.3f} to {x_max:.3f}), Y({y_min:.3f} to {y_max:.3f})"
        )
        logger.info(f"Pattern size: {width:.3f} x {height:.3f}mm")
        logger.info(f"Pattern center: ({pattern_center_x:.3f}, {pattern_center_y:.3f})")
        logger.info(f"Bed center: ({self.bed_center_x:.3f}, {self.bed_center_y:.3f})")
        logger.info(f"Centering offset: ({self.offset_x:+.3f}, {self.offset_y:+.3f})")

        # Verify bounds after centering
        new_x_min, new_x_max = x_min + self.offset_x, x_max + self.offset_x
        new_y_min, new_y_max = y_min + self.offset_y, y_max + self.offset_y

        logger.info(
            f"Centered bounds: X({new_x_min:.3f} to {new_x_max:.3f}), Y({new_y_min:.3f} to {new_y_max:.3f})"
        )

        # Check if pattern fits on bed
        if (
            new_x_min >= 0
            and new_x_max <= self.bed_size_x
            and new_y_min >= 0
            and new_y_max <= self.bed_size_y
        ):
            logger.info("✅ Centered pattern fits within bed bounds")
        else:
            logger.warning("⚠️ Centered pattern may exceed bed bounds")
            if new_x_min < 0:
                logger.warning(f"   X underflow: {new_x_min:.3f}mm")
            if new_x_max > self.bed_size_x:
                logger.warning(f"   X overflow: {new_x_max - self.bed_size_x:.3f}mm")
            if new_y_min < 0:
                logger.warning(f"   Y underflow: {new_y_min:.3f}mm")
            if new_y_max > self.bed_size_y:
                logger.warning(f"   Y overflow: {new_y_max - self.bed_size_y:.3f}mm")

    def apply_centering(self, x: float, y: float) -> Tuple[float, float]:
        """Apply centering offset to coordinates.

        Args:
            x: Original X coordinate
            y: Original Y coordinate

        Returns:
            Tuple of (centered_x, centered_y)
        """
        if not self.offset_calculated:
            logger.warning(
                "Centering offset not calculated, returning original coordinates"
            )
            return x, y

        return x + self.offset_x, y + self.offset_y

    def get_statistics(self) -> Dict:
        """Get centering statistics."""
        return {
            "bed_size": {"width": self.bed_size_x, "height": self.bed_size_y},
            "bed_center": {"x": self.bed_center_x, "y": self.bed_center_y},
            "offset": (
                {"x": self.offset_x, "y": self.offset_y}
                if self.offset_calculated
                else None
            ),
            "offset_calculated": self.offset_calculated,
        }


class TwoPassCoordinateCentering:
    """Two-pass coordinate centering for streaming G-code generation.

    Pass 1: Collect all coordinates to calculate bounds
    Pass 2: Apply centering offset during actual G-code generation
    """

    def __init__(self, bed_size_x: float = 250.0, bed_size_y: float = 220.0):
        """Initialize two-pass centering."""
        self.centering = CoordinateCentering(bed_size_x, bed_size_y)
        self.pass_number = 1
        self.coordinates_collected = False

    def process_coordinate(self, x: float, y: float) -> Tuple[float, float]:
        """Process coordinate based on current pass.

        Pass 1: Collect coordinate for bounds calculation
        Pass 2: Apply centering and return centered coordinate

        Args:
            x: Original X coordinate
            y: Original Y coordinate

        Returns:
            Tuple of (processed_x, processed_y)
        """
        if self.pass_number == 1:
            # First pass: collect coordinates
            self.centering.add_coordinate(x, y)
            return x, y  # Return original coordinates for now
        else:
            # Second pass: apply centering
            return self.centering.apply_centering(x, y)

    def finish_pass_1(self) -> None:
        """Finish first pass and calculate centering offset."""
        if self.pass_number == 1:
            self.centering.calculate_centering_offset()
            self.coordinates_collected = True
            self.pass_number = 2
            logger.info("Coordinate collection complete, centering offset calculated")

    def start_pass_2(self) -> None:
        """Start second pass with centering applied."""
        if not self.coordinates_collected:
            logger.warning("Starting pass 2 without completing pass 1")
        self.pass_number = 2

    def get_statistics(self) -> Dict:
        """Get centering statistics."""
        stats = self.centering.get_statistics()
        stats["pass_number"] = self.pass_number
        stats["coordinates_collected"] = self.coordinates_collected
        return stats
