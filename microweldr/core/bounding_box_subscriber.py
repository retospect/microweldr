"""Bounding box subscriber for real-time extent measurement in streaming architecture."""

import logging
from typing import List, Dict, Any, Optional
from .events import Event, EventType
from .subscribers import EventSubscriber

logger = logging.getLogger(__name__)


class BoundingBoxSubscriber(EventSubscriber):
    """Calculates bounding box extents from point events.

    Simple subscriber that tracks min/max X/Y coordinates from all points.
    """

    def __init__(self):
        """Initialize bounding box subscriber."""
        # Overall bounding box - just track the extents
        self.min_x: Optional[float] = None
        self.min_y: Optional[float] = None
        self.max_x: Optional[float] = None
        self.max_y: Optional[float] = None
        self.total_points: int = 0

    def get_priority(self) -> int:
        """Get subscriber priority (lower number = higher priority)."""
        return 10  # Medium priority - after validation but before output generation

    def get_subscribed_events(self) -> List[EventType]:
        """Get subscribed event types."""
        return [EventType.POINT_PROCESSING]

    def handle_event(self, event: Event) -> None:
        """Handle point events and update bounding box."""
        if event.event_type == EventType.POINT_PROCESSING:
            self._handle_point_event(event)

    def _handle_point_event(self, event: Event) -> None:
        """Handle point events and update bounding box."""
        action = event.data.get("action", "")

        if action == "point_added":
            point_data = event.data.get("point_data", {})
            x = point_data.get("x")
            y = point_data.get("y")

            if (
                x is not None
                and y is not None
                and isinstance(x, (int, float))
                and isinstance(y, (int, float))
            ):
                self._update_bounds(x, y)
                self.total_points += 1

    def _update_bounds(self, x: float, y: float) -> None:
        """Update bounding box with new point - expand if point is outside current box."""
        # Is this x/y outside the box? Make box larger so it's on the boundary
        if self.min_x is None or x < self.min_x:
            self.min_x = x
        if self.max_x is None or x > self.max_x:
            self.max_x = x
        if self.min_y is None or y < self.min_y:
            self.min_y = y
        if self.max_y is None or y > self.max_y:
            self.max_y = y

    def has_bounds(self) -> bool:
        """Check if we have valid bounds."""
        return all(
            bound is not None
            for bound in [self.min_x, self.min_y, self.max_x, self.max_y]
        )

    def get_bounds(self) -> Dict[str, float]:
        """Get the bounding box extents."""
        if not self.has_bounds():
            return {
                "min_x": 0.0,
                "min_y": 0.0,
                "max_x": 0.0,
                "max_y": 0.0,
                "width": 0.0,
                "height": 0.0,
            }

        return {
            "min_x": self.min_x,
            "min_y": self.min_y,
            "max_x": self.max_x,
            "max_y": self.max_y,
            "width": self.max_x - self.min_x,
            "height": self.max_y - self.min_y,
        }

    def reset(self) -> None:
        """Reset bounding box for new processing."""
        self.min_x = None
        self.min_y = None
        self.max_x = None
        self.max_y = None
        self.total_points = 0
