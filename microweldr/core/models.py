"""Data models for the SVG welder."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class WeldPoint:
    """Represents a single weld point."""

    x: float
    y: float
    weld_type: str  # 'normal', 'light', 'stop', or 'pipette'
    custom_temp: Optional[float] = None  # Custom temperature for this point
    custom_dwell: Optional[float] = None  # Custom dwell time for this point
    custom_bed_temp: Optional[float] = None  # Custom bed temperature
    custom_height: Optional[float] = None  # Custom weld height (compression depth)

    def __post_init__(self) -> None:
        """Validate weld point data."""
        if self.weld_type not in ("normal", "light", "stop", "pipette"):
            raise ValueError(f"Invalid weld_type: {self.weld_type}")


@dataclass
class WeldPath:
    """Represents a path with multiple weld points."""

    points: List[WeldPoint]
    weld_type: str
    svg_id: str
    pause_message: Optional[str] = None  # Custom message for stop points
    element_type: Optional[str] = None  # Original SVG element type (circle, rect, etc.)
    element_radius: Optional[float] = None  # Original radius for circles
    custom_temp: Optional[float] = None  # Custom temperature for this path
    custom_dwell: Optional[float] = None  # Custom dwell time for this path
    custom_bed_temp: Optional[float] = None  # Custom bed temperature
    custom_height: Optional[float] = None  # Custom weld height (compression depth)

    def __post_init__(self) -> None:
        """Validate weld path data."""
        if self.weld_type not in ("normal", "light", "stop", "pipette"):
            raise ValueError(f"Invalid weld_type: {self.weld_type}")

        if not self.points:
            raise ValueError("WeldPath must contain at least one point")

        if not self.svg_id:
            raise ValueError("WeldPath must have a valid svg_id")

    @property
    def point_count(self) -> int:
        """Get the number of points in this path."""
        return len(self.points)

    def get_bounds(self) -> tuple[float, float, float, float]:
        """Get the bounding box of this path as (min_x, min_y, max_x, max_y)."""
        if not self.points:
            return (0.0, 0.0, 0.0, 0.0)

        x_coords = [p.x for p in self.points]
        y_coords = [p.y for p in self.points]

        return (min(x_coords), min(y_coords), max(x_coords), max(y_coords))
