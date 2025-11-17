"""
Two-pass processing system for coordinate centering.

Pass 1: Collect all coordinates using OutlineSubscriber to calculate bounding box
Pass 2: Replay events with calculated centering offset applied to G-code generation
"""

import logging
from pathlib import Path
from typing import List, Optional, Union, Tuple, Dict, Any
from ..core.events import Event, EventType, PathEvent, PointEvent, publish_event
from ..processors.subscribers import EventSubscriber
from ..processors.outline_subscriber import OutlineSubscriber
from ..outputs.streaming_gcode_subscriber import StreamingGCodeSubscriber

logger = logging.getLogger(__name__)


class EventRecorder:
    """Records events during first pass for replay in second pass."""

    def __init__(self):
        self.recorded_events: List[Event] = []

    def record_event(self, event: Event) -> None:
        """Record an event for later replay."""
        self.recorded_events.append(event)

    def replay_events(self, subscribers: List[EventSubscriber]) -> None:
        """Replay recorded events to a list of subscribers."""
        logger.info(
            f"Replaying {len(self.recorded_events)} events to {len(subscribers)} subscribers"
        )

        for event in self.recorded_events:
            for subscriber in subscribers:
                if event.event_type in subscriber.get_subscribed_events():
                    subscriber.handle_event(event)

    def clear(self) -> None:
        """Clear recorded events."""
        self.recorded_events.clear()

    def get_statistics(self) -> Dict[str, Any]:
        """Get recording statistics."""
        event_types = {}
        for event in self.recorded_events:
            event_type = (
                event.event_type.name
                if hasattr(event.event_type, "name")
                else str(event.event_type)
            )
            event_types[event_type] = event_types.get(event_type, 0) + 1

        return {
            "total_events": len(self.recorded_events),
            "event_types": event_types,
        }


class TwoPassProcessor:
    """Processes files in two passes for coordinate centering.

    Pass 1: Records events and calculates coordinate bounds using OutlineSubscriber
    Pass 2: Replays events with centering offset applied to G-code generation
    """

    def __init__(
        self,
        config,
        bed_size_x: float = 250.0,
        bed_size_y: float = 220.0,
        include_user_pause: bool = True,
    ):
        """Initialize two-pass processor.

        Args:
            config: Configuration object
            bed_size_x: Printer bed width in mm
            bed_size_y: Printer bed depth in mm
            include_user_pause: Whether to include user pause for plastic insertion
        """
        self.config = config
        self.bed_size_x = bed_size_x
        self.bed_size_y = bed_size_y
        self.include_user_pause = include_user_pause

        # Event recording and replay
        self.event_recorder = EventRecorder()

        # Pass 1 subscribers
        self.outline_subscriber = OutlineSubscriber(bed_size_x, bed_size_y)

        # Centering offset (calculated after pass 1)
        self.centering_offset: Tuple[float, float] = (0.0, 0.0)

    def process_with_centering(
        self,
        events: List[Event],
        output_path: Path,
        animation_path: Optional[Path] = None,
        verbose: bool = False,
    ) -> bool:
        """Process events with two-pass coordinate centering.

        Args:
            events: List of events to process
            output_path: Path for G-code output
            animation_path: Optional path for animation output
            verbose: Enable verbose logging

        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            # Pass 1: Collect coordinates and calculate bounds
            logger.info("🔍 Pass 1: Analyzing coordinate bounds...")
            self._execute_pass_1(events)

            # Calculate centering offset
            self.centering_offset = (
                self.outline_subscriber.calculate_bounds_and_offset()
            )
            logger.info(
                f"📐 Calculated centering offset: ({self.centering_offset[0]:+.3f}, {self.centering_offset[1]:+.3f})"
            )

            # Pass 2: Generate outputs with centering
            logger.info("🎯 Pass 2: Generating centered G-code...")
            return self._execute_pass_2(output_path, animation_path, verbose)

        except Exception as e:
            logger.exception(f"Two-pass processing failed: {e}")
            return False

    def _execute_pass_1(self, events: List[Event]) -> None:
        """Execute first pass: record events and collect coordinates."""
        # Clear previous state
        self.event_recorder.clear()
        self.outline_subscriber.reset()

        # Process events for coordinate collection
        for event in events:
            # Record event for replay
            self.event_recorder.record_event(event)

            # Send to outline subscriber for bounds calculation
            if event.event_type in self.outline_subscriber.get_subscribed_events():
                self.outline_subscriber.handle_event(event)

        # Log pass 1 statistics
        recorder_stats = self.event_recorder.get_statistics()
        outline_stats = self.outline_subscriber.get_statistics()

        logger.info(
            f"Pass 1 complete: {recorder_stats['total_events']} events recorded, {outline_stats['total_points']} points collected"
        )

    def _execute_pass_2(
        self,
        output_path: Path,
        animation_path: Optional[Path] = None,
        verbose: bool = False,
    ) -> bool:
        """Execute second pass: replay events with centering applied."""
        try:
            # Create pass 2 subscribers with centering offset
            pass_2_subscribers = []

            # G-code subscriber with centering offset
            gcode_subscriber = StreamingGCodeSubscriber(
                output_path,
                self.config,
                coordinate_offset=self.centering_offset,
                include_user_pause=self.include_user_pause,
            )
            pass_2_subscribers.append(gcode_subscriber)

            # Add animation subscriber if requested
            if animation_path:
                # TODO: Add animation subscriber with centering support
                logger.info(
                    f"Animation output requested: {animation_path} (not yet implemented with centering)"
                )

            # Replay events to pass 2 subscribers
            self.event_recorder.replay_events(pass_2_subscribers)

            # Send completion event
            completion_event = Event(
                event_type=EventType.OUTPUT_GENERATION,
                timestamp=0.0,
                data={"action": "processing_complete"},
                source="two_pass_processor",
            )

            for subscriber in pass_2_subscribers:
                if EventType.OUTPUT_GENERATION in subscriber.get_subscribed_events():
                    subscriber.handle_event(completion_event)

            # Verify output was created
            if output_path.exists():
                file_size = output_path.stat().st_size
                logger.info(
                    f"✅ Centered G-code generated: {output_path} ({file_size:,} bytes)"
                )
                return True
            else:
                logger.error(f"❌ G-code file was not created: {output_path}")
                return False

        except Exception as e:
            logger.exception(f"Pass 2 execution failed: {e}")
            return False

    def get_centering_statistics(self) -> Dict[str, Any]:
        """Get comprehensive centering statistics."""
        stats = {
            "centering_offset": {
                "x": self.centering_offset[0],
                "y": self.centering_offset[1],
            },
            "bed_configuration": {
                "width": self.bed_size_x,
                "height": self.bed_size_y,
                "center_x": self.bed_size_x / 2,
                "center_y": self.bed_size_y / 2,
            },
        }

        # Add outline analysis if available
        if hasattr(self.outline_subscriber, "get_statistics"):
            stats["outline_analysis"] = self.outline_subscriber.get_statistics()

        # Add event recording stats if available
        if hasattr(self.event_recorder, "get_statistics"):
            stats["event_recording"] = self.event_recorder.get_statistics()

        return stats


def create_events_from_weld_paths(weld_paths: List) -> List[Event]:
    """Convert weld paths to events for two-pass processing.

    Args:
        weld_paths: List of WeldPath objects

    Returns:
        List of Event objects
    """
    events = []

    for i, path in enumerate(weld_paths):
        # Convert WeldType enum to string if needed
        weld_type_str = (
            path.weld_type.value if hasattr(path.weld_type, "value") else path.weld_type
        )

        # Path start event
        path_start_event = Event(
            event_type=EventType.PATH_PROCESSING,
            timestamp=0.0,
            data={
                "action": "path_start",
                "path_data": {
                    "id": getattr(path, "path_id", None)
                    or getattr(path, "svg_id", None)
                    or f"path_{i+1}",
                    "weld_type": weld_type_str,
                },
            },
            source="weld_path_converter",
        )
        events.append(path_start_event)

        # Point events
        for point in path.points:
            point_event = Event(
                event_type=EventType.POINT_PROCESSING,
                timestamp=0.0,
                data={
                    "action": "point_added",
                    "point_data": {
                        "x": point.x,
                        "y": point.y,
                        "weld_type": weld_type_str,
                    },
                },
                source="weld_path_converter",
            )
            events.append(point_event)

        # Path complete event
        path_complete_event = Event(
            event_type=EventType.PATH_PROCESSING,
            timestamp=0.0,
            data={
                "action": "path_complete",
                "path_id": getattr(path, "path_id", None)
                or getattr(path, "svg_id", None)
                or f"path_{i+1}",
            },
            source="weld_path_converter",
        )
        events.append(path_complete_event)

    return events
