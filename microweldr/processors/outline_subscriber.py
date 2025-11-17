"""
Streaming outline subscriber that calculates bounding rectangle for coordinate centering.
"""

import logging
from typing import List, Optional, Tuple, Dict, Any
from ..core.events import Event, EventType
from ..processors.subscribers import EventSubscriber

logger = logging.getLogger(__name__)


class OutlineSubscriber(EventSubscriber):
    """Calculates bounding rectangle of all coordinates during streaming processing.

    This subscriber runs in the first pass to collect coordinate bounds,
    which are then used to calculate centering offset for the second pass.
    """

    def __init__(self, bed_size_x: float = 250.0, bed_size_y: float = 220.0):
        """Initialize outline subscriber.

        Args:
            bed_size_x: Printer bed width in mm
            bed_size_y: Printer bed depth in mm
        """
        self.bed_size_x = bed_size_x
        self.bed_size_y = bed_size_y
        self.bed_center_x = bed_size_x / 2
        self.bed_center_y = bed_size_y / 2

        # Coordinate tracking
        self.x_coords: List[float] = []
        self.y_coords: List[float] = []
        self.total_points = 0

        # Calculated bounds and offset
        self._bounds_calculated = False
        self._x_min: Optional[float] = None
        self._x_max: Optional[float] = None
        self._y_min: Optional[float] = None
        self._y_max: Optional[float] = None
        self._offset_x: Optional[float] = None
        self._offset_y: Optional[float] = None

    def get_priority(self) -> int:
        """Get subscriber priority (lower number = higher priority)."""
        return 10  # High priority - needs to run before G-code generation

    def get_subscribed_events(self) -> List[EventType]:
        """Get subscribed event types."""
        return [
            EventType.POINT_PROCESSING,
            EventType.PATH_PROCESSING,
        ]

    def handle_event(self, event: Event) -> None:
        """Handle events to collect coordinate bounds."""
        try:
            if event.event_type == EventType.POINT_PROCESSING:
                self._handle_point_event(event)
            elif event.event_type == EventType.PATH_PROCESSING:
                self._handle_path_event(event)
        except Exception as e:
            logger.exception(f"Error in outline subscriber: {e}")

    def _handle_point_event(self, event: Event) -> None:
        """Handle point processing event to collect coordinates."""
        action = event.data.get("action", "")

        if action in ["point_added", "point_processed"]:
            # Extract coordinates from different possible data structures
            point_data = event.data.get("point_data", {})
            if not point_data:
                point_data = event.data.get("point", {})

            x = point_data.get("x")
            y = point_data.get("y")

            # Also try direct coordinates in event data
            if x is None:
                x = event.data.get("x")
            if y is None:
                y = event.data.get("y")

            if x is not None and y is not None:
                self.x_coords.append(float(x))
                self.y_coords.append(float(y))
                self.total_points += 1
                logger.debug(f"OutlineSubscriber: Collected point ({x}, {y})")

    def _handle_path_event(self, event: Event) -> None:
        """Handle path processing events."""
        action = event.data.get("action", "")

        if action == "point_added":
            # Handle point added to path
            point_data = event.data.get("point", {})
            x = point_data.get("x")
            y = point_data.get("y")

            if x is not None and y is not None:
                self.x_coords.append(float(x))
                self.y_coords.append(float(y))
                self.total_points += 1
                logger.debug(f"OutlineSubscriber: Collected path point ({x}, {y})")

    def calculate_bounds_and_offset(self) -> Tuple[float, float]:
        """Calculate bounding box and centering offset.

        Returns:
            Tuple of (offset_x, offset_y) in mm
        """
        if not self.x_coords or not self.y_coords:
            logger.warning("No coordinates collected for bounds calculation")
            return 0.0, 0.0

        # Calculate bounding box
        self._x_min = min(self.x_coords)
        self._x_max = max(self.x_coords)
        self._y_min = min(self.y_coords)
        self._y_max = max(self.y_coords)

        # Calculate pattern center
        pattern_center_x = (self._x_min + self._x_max) / 2
        pattern_center_y = (self._y_min + self._y_max) / 2

        # Calculate centering offset
        self._offset_x = self.bed_center_x - pattern_center_x
        self._offset_y = self.bed_center_y - pattern_center_y

        self._bounds_calculated = True

        # Log analysis
        width = self._x_max - self._x_min
        height = self._y_max - self._y_min

        logger.info(f"Outline Analysis Complete:")
        logger.info(f"  Points collected: {self.total_points}")
        logger.info(
            f"  Pattern bounds: X({self._x_min:.3f} to {self._x_max:.3f}), Y({self._y_min:.3f} to {self._y_max:.3f})"
        )
        logger.info(f"  Pattern size: {width:.3f} x {height:.3f}mm")
        logger.info(
            f"  Pattern center: ({pattern_center_x:.3f}, {pattern_center_y:.3f})"
        )
        logger.info(f"  Bed center: ({self.bed_center_x:.3f}, {self.bed_center_y:.3f})")
        logger.info(
            f"  Centering offset: ({self._offset_x:+.3f}, {self._offset_y:+.3f})"
        )

        # Verify bounds after centering
        new_x_min = self._x_min + self._offset_x
        new_x_max = self._x_max + self._offset_x
        new_y_min = self._y_min + self._offset_y
        new_y_max = self._y_max + self._offset_y

        logger.info(
            f"  Centered bounds: X({new_x_min:.3f} to {new_x_max:.3f}), Y({new_y_min:.3f} to {new_y_max:.3f})"
        )

        # Check if pattern fits on bed
        if (
            new_x_min >= 0
            and new_x_max <= self.bed_size_x
            and new_y_min >= 0
            and new_y_max <= self.bed_size_y
        ):
            logger.info("  ✅ Centered pattern fits within bed bounds")
        else:
            logger.warning("  ⚠️ Centered pattern may exceed bed bounds")
            if new_x_min < 0:
                logger.warning(f"     X underflow: {new_x_min:.3f}mm")
            if new_x_max > self.bed_size_x:
                logger.warning(f"     X overflow: {new_x_max - self.bed_size_x:.3f}mm")
            if new_y_min < 0:
                logger.warning(f"     Y underflow: {new_y_min:.3f}mm")
            if new_y_max > self.bed_size_y:
                logger.warning(f"     Y overflow: {new_y_max - self.bed_size_y:.3f}mm")

        return self._offset_x, self._offset_y

    def get_centering_offset(self) -> Tuple[float, float]:
        """Get the calculated centering offset.

        Returns:
            Tuple of (offset_x, offset_y) in mm
        """
        if not self._bounds_calculated:
            return self.calculate_bounds_and_offset()

        return self._offset_x or 0.0, self._offset_y or 0.0

    def get_bounds(self) -> Dict[str, float]:
        """Get the calculated bounding box.

        Returns:
            Dictionary with x_min, x_max, y_min, y_max keys
        """
        if not self._bounds_calculated:
            self.calculate_bounds_and_offset()

        return {
            "x_min": self._x_min or 0.0,
            "x_max": self._x_max or 0.0,
            "y_min": self._y_min or 0.0,
            "y_max": self._y_max or 0.0,
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get outline analysis statistics."""
        stats = {
            "total_points": self.total_points,
            "bounds_calculated": self._bounds_calculated,
            "bed_size": {"width": self.bed_size_x, "height": self.bed_size_y},
            "bed_center": {"x": self.bed_center_x, "y": self.bed_center_y},
        }

        if self._bounds_calculated:
            stats.update(
                {
                    "original_bounds": self.get_bounds(),
                    "centering_offset": {
                        "x": self._offset_x or 0.0,
                        "y": self._offset_y or 0.0,
                    },
                    "pattern_size": {
                        "width": (self._x_max or 0.0) - (self._x_min or 0.0),
                        "height": (self._y_max or 0.0) - (self._y_min or 0.0),
                    },
                }
            )

        return stats

    def reset(self) -> None:
        """Reset the subscriber for a new analysis."""
        self.x_coords.clear()
        self.y_coords.clear()
        self.total_points = 0
        self._bounds_calculated = False
        self._x_min = None
        self._x_max = None
        self._y_min = None
        self._y_max = None
        self._offset_x = None
        self._offset_y = None
        logger.debug("OutlineSubscriber: Reset for new analysis")
