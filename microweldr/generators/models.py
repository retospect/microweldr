"""Data models for point generation and welding operations."""

from dataclasses import dataclass
from typing import List, Optional

from ..core.constants import (
    ErrorMessages,
    WeldType,
    get_valid_weld_types,
    get_weld_type_enum,
)


@dataclass
class WeldPoint:
    """Represents a single weld point with spatial properties only.

    Temperature, timing, and other process parameters are managed
    at the time-based execution level, not at the point level.
    """

    x: float
    y: float
    weld_type: (
        str  # Use WeldType enum values: 'normal', 'frangible', 'stop', or 'pipette'
    )
    weld_height: Optional[float] = None  # Weld height (compression depth) in mm

    def __post_init__(self) -> None:
        """Validate weld point data."""
        valid_types = get_valid_weld_types()
        if self.weld_type not in valid_types:
            raise ValueError(
                ErrorMessages.INVALID_WELD_TYPE.format(
                    weld_type=self.weld_type, valid_types=", ".join(valid_types)
                )
            )

    @property
    def weld_type_enum(self) -> WeldType:
        """Get weld type as enum."""
        return get_weld_type_enum(self.weld_type)


@dataclass
class WeldPath:
    """Represents a path with multiple weld points.

    Only contains spatial/geometric properties. Process parameters like
    temperature and timing are managed at the execution level.
    """

    points: List[WeldPoint]
    weld_type: str
    svg_id: str
    pause_message: Optional[str] = None  # Custom message for stop points
    element_type: Optional[str] = None  # Original SVG element type (circle, rect, etc.)
    element_radius: Optional[float] = None  # Original radius for circles
    default_weld_height: Optional[float] = (
        None  # Default weld height for points in this path
    )

    def __post_init__(self) -> None:
        """Validate weld path data and apply default weld height to points."""
        # Validate points list
        if not self.points:
            raise ValueError("WeldPath must contain at least one point")

        # Validate svg_id
        if not self.svg_id or not self.svg_id.strip():
            raise ValueError("WeldPath must have a valid svg_id")

        # Validate weld_type
        valid_types = get_valid_weld_types()
        if self.weld_type not in valid_types:
            raise ValueError(
                ErrorMessages.INVALID_WELD_TYPE.format(
                    weld_type=self.weld_type, valid_types=", ".join(valid_types)
                )
            )

        # Apply default weld height to points that don't have their own
        self.apply_default_weld_height()

    @property
    def weld_type_enum(self) -> WeldType:
        """Get weld type as enum."""
        return get_weld_type_enum(self.weld_type)

    @property
    def point_count(self) -> int:
        """Get the number of points in this path."""
        return len(self.points)

    @property
    def name(self) -> str:
        """Get path name (alias for svg_id for backward compatibility)."""
        return self.svg_id

    def apply_default_weld_height(self) -> None:
        """Apply default weld height to points that don't have their own value.

        Point-level weld_height always takes precedence over path-level default.
        """
        if self.default_weld_height is not None:
            for point in self.points:
                if point.weld_height is None:
                    point.weld_height = self.default_weld_height

    def add_point(self, point: WeldPoint) -> None:
        """Add a point to the path and apply default weld height if needed.

        Args:
            point: The WeldPoint to add to this path
        """
        self.points.append(point)
        # Apply default weld height to the newly added point if it doesn't have one
        if point.weld_height is None and self.default_weld_height is not None:
            point.weld_height = self.default_weld_height

    def get_total_length(self) -> float:
        """Calculate total path length in mm."""
        if len(self.points) < 2:
            return 0.0

        total_length = 0.0
        for i in range(1, len(self.points)):
            prev_point = self.points[i - 1]
            curr_point = self.points[i]
            dx = curr_point.x - prev_point.x
            dy = curr_point.y - prev_point.y
            total_length += (dx**2 + dy**2) ** 0.5

        return total_length

    def get_bounds(self) -> tuple[float, float, float, float]:
        """Get bounding box of the path.

        Returns:
            Tuple of (min_x, min_y, max_x, max_y)
        """
        if not self.points:
            return (0.0, 0.0, 0.0, 0.0)

        x_coords = [p.x for p in self.points]
        y_coords = [p.y for p in self.points]

        return (min(x_coords), min(y_coords), max(x_coords), max(y_coords))

    def get_weld_height_summary(self) -> dict:
        """Get a summary of weld height settings across the path.

        Returns:
            Dictionary with weld height information
        """
        points_with_height = [p for p in self.points if p.weld_height is not None]
        points_using_default = [
            p for p in self.points if p.weld_height == self.default_weld_height
        ]
        points_with_custom = [
            p
            for p in self.points
            if p.weld_height is not None and p.weld_height != self.default_weld_height
        ]

        return {
            "default_weld_height": self.default_weld_height,
            "total_points": len(self.points),
            "points_with_height": len(points_with_height),
            "points_using_default": len(points_using_default),
            "points_with_custom_height": len(points_with_custom),
            "height_values": list(set(p.weld_height for p in points_with_height)),
        }
