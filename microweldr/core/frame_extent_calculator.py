"""Frame extent calculator for two-phase processing architecture."""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class FrameExtentCalculator:
    """Calculates bounding box extents from points in Phase 1."""

    def __init__(self):
        """Initialize frame extent calculator."""
        self.min_x: Optional[float] = None
        self.min_y: Optional[float] = None
        self.max_x: Optional[float] = None
        self.max_y: Optional[float] = None
        self.total_points: int = 0

    def add_point(self, point: Dict[str, Any]) -> None:
        """Add a point and update bounding box."""
        x = point.get("x")
        y = point.get("y")

        if (
            x is not None
            and y is not None
            and isinstance(x, (int, float))
            and isinstance(y, (int, float))
        ):
            # Expand bounding box if point is outside current bounds
            if self.min_x is None or x < self.min_x:
                self.min_x = x
            if self.max_x is None or x > self.max_x:
                self.max_x = x
            if self.min_y is None or y < self.min_y:
                self.min_y = y
            if self.max_y is None or y > self.max_y:
                self.max_y = y

            self.total_points += 1

    def finalize(self) -> Dict[str, Any]:
        """Finalize calculation and return results."""
        if self.has_bounds():
            bounds = {
                "min_x": self.min_x,
                "min_y": self.min_y,
                "max_x": self.max_x,
                "max_y": self.max_y,
                "width": self.max_x - self.min_x,
                "height": self.max_y - self.min_y,
                "center_x": (self.min_x + self.max_x) / 2,
                "center_y": (self.min_y + self.max_y) / 2,
            }
        else:
            bounds = {
                "min_x": 0.0,
                "min_y": 0.0,
                "max_x": 0.0,
                "max_y": 0.0,
                "width": 0.0,
                "height": 0.0,
                "center_x": 0.0,
                "center_y": 0.0,
            }

        logger.info(
            f"Frame extent: {bounds['width']:.1f} × {bounds['height']:.1f}, {self.total_points} points"
        )
        return bounds

    def has_bounds(self) -> bool:
        """Check if we have valid bounds."""
        return all(
            bound is not None
            for bound in [self.min_x, self.min_y, self.max_x, self.max_y]
        )

    def get_bounds(self) -> Dict[str, float]:
        """Get current bounds without finalizing."""
        return self.finalize()
