"""Event subscribers for different output generators."""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TextIO
from abc import ABC, abstractmethod
import logging

from ..core.events import (
    Event,
    EventType,
    EventSubscriber,
    ParsingEvent,
    PathEvent,
    PointEvent,
    CurveEvent,
    OutputEvent,
    ErrorEvent,
    ProgressEvent,
    ValidationEvent,
    publish_event,
)
from ..core.models import WeldPath, WeldPoint
from ..core.constants import get_valid_weld_types

logger = logging.getLogger(__name__)


class ProgressTracker(EventSubscriber):
    """Tracks progress of operations."""

    def __init__(self, verbose: bool = False):
        """Initialize progress tracker."""
        self.verbose = verbose
        self.current_stage: Optional[str] = None
        self.stage_progress: Dict[str, float] = {}
        self.start_times: Dict[str, float] = {}

    def get_subscribed_events(self) -> List[EventType]:
        """Get subscribed event types."""
        return [
            EventType.PARSING,
            EventType.PATH_PROCESSING,
            EventType.OUTPUT_GENERATION,
            EventType.PROGRESS,
        ]

    def handle_event(self, event: Event) -> None:
        """Handle progress events."""
        if event.event_type == EventType.PROGRESS:
            self._handle_progress_event(event)
        elif event.event_type == EventType.PARSING:
            self._handle_parsing_event(event)
        elif event.event_type == EventType.PATH_PROCESSING:
            self._handle_path_event(event)
        elif event.event_type == EventType.OUTPUT_GENERATION:
            self._handle_output_event(event)

    def _handle_progress_event(self, event: Event) -> None:
        """Handle progress event."""
        stage = event.data.get("stage", "unknown")
        progress = event.data.get("progress", 0)
        total = event.data.get("total")

        self.stage_progress[stage] = progress

        if self.verbose:
            if total:
                percentage = (progress / total) * 100
                print(f"   {stage}: {progress}/{total} ({percentage:.1f}%)")
            else:
                print(f"   {stage}: {progress}")

    def _handle_parsing_event(self, event: Event) -> None:
        """Handle parsing event."""
        action = event.data.get("action", "")
        if action == "start":
            self.start_times["parsing"] = time.time()
            if self.verbose:
                print("🔍 Parsing input file...")
        elif action == "complete":
            if "parsing" in self.start_times:
                duration = time.time() - self.start_times["parsing"]
                if self.verbose:
                    print(f"   ✓ Parsing completed in {duration:.2f}s")

    def _handle_path_event(self, event: Event) -> None:
        """Handle path processing event."""
        action = event.data.get("action", "")
        if action == "start_processing":
            if self.verbose:
                print("🔧 Processing weld paths...")
        elif action == "path_complete":
            path_id = event.data.get("path_id", "")
            if self.verbose:
                print(f"   ✓ Processed path: {path_id}")

    def _handle_output_event(self, event: Event) -> None:
        """Handle output generation event."""
        action = event.data.get("action", "")
        output_type = event.data.get("output_type", "")

        if action == "start":
            self.start_times[output_type] = time.time()
            if self.verbose:
                print(f"📝 Generating {output_type}...")
        elif action == "complete":
            file_path = event.data.get("file_path", "")
            if output_type in self.start_times:
                duration = time.time() - self.start_times[output_type]
                if self.verbose:
                    print(
                        f"   ✓ {output_type} generated in {duration:.2f}s: {file_path}"
                    )

    def get_progress_summary(self) -> Dict[str, float]:
        """Get progress summary."""
        return self.stage_progress.copy()


class LoggingSubscriber(EventSubscriber):
    """Logs all events for debugging."""

    def __init__(self, log_level: int = logging.INFO):
        """Initialize logging subscriber."""
        self.logger = logging.getLogger(f"{__name__}.LoggingSubscriber")
        self.logger.setLevel(log_level)

    def get_subscribed_events(self) -> List[EventType]:
        """Get subscribed event types."""
        return list(EventType)  # Subscribe to all events

    def handle_event(self, event: Event) -> None:
        """Log the event."""
        self.logger.info(f"Event: {event.event_type.value} - {event.data}")


class ValidationSubscriber(EventSubscriber):
    """Validates data during processing."""

    def __init__(self):
        """Initialize validation subscriber."""
        self.validation_errors: List[str] = []
        self.validation_warnings: List[str] = []

    def get_subscribed_events(self) -> List[EventType]:
        """Get subscribed event types."""
        return [
            EventType.PATH_PROCESSING,
            EventType.POINT_PROCESSING,
            EventType.VALIDATION,
        ]

    def handle_event(self, event: Event) -> None:
        """Handle validation events."""
        if event.event_type == EventType.VALIDATION:
            self._handle_validation_event(event)
        elif event.event_type == EventType.PATH_PROCESSING:
            self._validate_path_event(event)
        elif event.event_type == EventType.POINT_PROCESSING:
            self._validate_point_event(event)

    def _handle_validation_event(self, event: Event) -> None:
        """Handle validation event."""
        result = event.data.get("result", True)
        message = event.data.get("message", "")

        if not result:
            self.validation_errors.append(message)

    def _validate_path_event(self, event: Event) -> None:
        """Validate path processing event."""
        action = event.data.get("action", "")
        if action == "path_complete":
            path_data = event.data.get("path_data", {})
            if not path_data.get("points"):
                self.validation_warnings.append(
                    f"Path {event.data.get('path_id')} has no points"
                )

    def _validate_point_event(self, event: Event) -> None:
        """Validate point processing event."""
        point_data = event.data.get("point_data", {})
        x = point_data.get("x")
        y = point_data.get("y")

        if x is None or y is None:
            self.validation_errors.append("Point missing coordinates")
        elif not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            self.validation_errors.append("Point coordinates must be numeric")

    def has_errors(self) -> bool:
        """Check if there are validation errors."""
        return len(self.validation_errors) > 0

    def has_warnings(self) -> bool:
        """Check if there are validation warnings."""
        return len(self.validation_warnings) > 0

    def get_errors(self) -> List[str]:
        """Get validation errors."""
        return self.validation_errors.copy()

    def get_warnings(self) -> List[str]:
        """Get validation warnings."""
        return self.validation_warnings.copy()

    def clear(self) -> None:
        """Clear validation results."""
        self.validation_errors.clear()
        self.validation_warnings.clear()


class GCodeSubscriber(EventSubscriber):
    """Generates G-code output from events in streaming mode."""

    def __init__(self, output_path: Path, config):
        """Initialize G-code subscriber."""
        self.output_path = Path(output_path)
        self.config = config
        self.file_handle = None
        self.current_path_id = ""
        self.current_weld_type = "normal"
        self.is_first_point_in_path = True
        self.total_paths_processed = 0

    def get_subscribed_events(self) -> List[EventType]:
        """Get subscribed event types."""
        return [EventType.PATH_PROCESSING, EventType.OUTPUT_GENERATION]

    def handle_event(self, event: Event) -> None:
        """Handle events for G-code generation."""
        if event.event_type == EventType.PATH_PROCESSING:
            self._handle_path_event(event)
        elif event.event_type == EventType.OUTPUT_GENERATION:
            self._handle_output_event(event)

    def _handle_path_event(self, event: Event) -> None:
        """Handle path processing event."""
        action = event.data.get("action", "")

        if action == "path_start":
            # Start new path - store data but don't create WeldPath yet
            self.current_path_data = event.data.get("path_data", {})
            self.current_points = []
            self.current_path = None
        elif action == "point_added" and self.current_path_data is not None:
            # Add point to current path
            point_data = event.data.get("point_data", {})
            point = WeldPoint(
                x=point_data.get("x", 0),
                y=point_data.get("y", 0),
                weld_type=point_data.get("weld_type", "normal"),
            )
            self.current_points.append(point)
        elif action == "path_complete":
            # Write path completion comment
            if self.file_handle:
                self.file_handle.write(f"; Completed path: {self.current_path_id}\n\n")
            self.total_paths_processed += 1

    def _handle_output_event(self, event: Event) -> None:
        """Handle output generation event."""
        action = event.data.get("action", "")
        output_type = event.data.get("output_type", "")

        if action == "generate" and output_type == "gcode":
            self._finalize_gcode_file()

    def _generate_gcode(self) -> None:
        """Generate G-code file."""
        from ..outputs.streaming_gcode_subscriber import StreamingGCodeSubscriber
        from ..core.events import Event, EventType

        subscriber = StreamingGCodeSubscriber(self.output_path, self.config)

        # Convert WeldPaths to events for streaming processing
        for path in self.weld_paths:
            # Path start event
            path_event = Event(
                event_type=EventType.PATH_PROCESSING,
                data={
                    "action": "path_start",
                    "path_data": {"id": path.svg_id, "weld_type": path.weld_type},
                },
            )
            subscriber.handle_event(path_event)

            # Point events
            for point in path.points:
                point_event = Event(
                    event_type=EventType.POINT_PROCESSING,
                    data={
                        "action": "point_processed",
                        "x": point.x,
                        "y": point.y,
                        "weld_type": point.weld_type,
                    },
                )
                subscriber.handle_event(point_event)

            # Path end event
            path_end_event = Event(
                event_type=EventType.PATH_PROCESSING, data={"action": "path_end"}
            )
            subscriber.handle_event(path_end_event)

        # Finalize
        finalize_event = Event(
            event_type=EventType.OUTPUT_GENERATION,
            data={"action": "processing_complete"},
        )
        subscriber.handle_event(finalize_event)

        # Publish completion event
        publish_event(
            OutputEvent(
                action="complete", output_type="gcode", file_path=self.output_path
            )
        )


class AnimationSubscriber(EventSubscriber):
    """Generates animation output from events."""

    def __init__(self, output_path: Path, config):
        """Initialize animation subscriber."""
        self.output_path = Path(output_path)
        self.config = config
        self.weld_paths: List[WeldPath] = []
        self.current_path: Optional[WeldPath] = None
        self.current_path_data: Optional[dict] = None
        self.current_points: List[WeldPoint] = []

    def get_subscribed_events(self) -> List[EventType]:
        """Get subscribed event types."""
        return [EventType.PATH_PROCESSING, EventType.OUTPUT_GENERATION]

    def handle_event(self, event: Event) -> None:
        """Handle events for animation generation."""
        if event.event_type == EventType.PATH_PROCESSING:
            self._handle_path_event(event)
        elif event.event_type == EventType.OUTPUT_GENERATION:
            self._handle_output_event(event)

    def _handle_path_event(self, event: Event) -> None:
        """Handle path processing event."""
        action = event.data.get("action", "")

        if action == "path_start":
            # Start new path - store data but don't create WeldPath yet
            self.current_path_data = event.data.get("path_data", {})
            self.current_points = []
            self.current_path = None
        elif action == "point_added" and self.current_path_data is not None:
            # Add point to current path
            point_data = event.data.get("point_data", {})
            point = WeldPoint(
                x=point_data.get("x", 0),
                y=point_data.get("y", 0),
                weld_type=point_data.get("weld_type", "normal"),
            )
            self.current_points.append(point)
        elif action == "path_complete" and self.current_path_data is not None:
            # Complete current path - now create WeldPath with points
            if self.current_points:  # Only create if we have points
                self.current_path = WeldPath(
                    svg_id=self.current_path_data.get("id", ""),
                    weld_type=self.current_path_data.get("weld_type", "normal"),
                    points=self.current_points,
                )
                self.weld_paths.append(self.current_path)
            # Reset for next path
            self.current_path = None
            self.current_path_data = None
            self.current_points = []

    def _handle_output_event(self, event: Event) -> None:
        """Handle output generation event."""
        action = event.data.get("action", "")
        output_type = event.data.get("output_type", "")

        if action == "generate" and output_type in ["animation", "png"]:
            self._generate_animation(output_type)

    def _generate_animation(self, output_type: str) -> None:
        """Generate animation file."""
        from ..animation.generator import AnimationGenerator

        generator = AnimationGenerator(self.config)

        if output_type == "animation":
            generator.generate_file(self.weld_paths, self.output_path)
        elif output_type == "png":
            generator.generate_png_file(self.weld_paths, self.output_path)

        # Publish completion event
        publish_event(
            OutputEvent(
                action="complete", output_type=output_type, file_path=self.output_path
            )
        )


class StatisticsSubscriber(EventSubscriber):
    """Collects statistics during processing."""

    def __init__(self):
        """Initialize statistics subscriber."""
        self.stats: Dict[str, Any] = {
            "paths_processed": 0,
            "points_processed": 0,
            "curves_processed": 0,
            "errors_encountered": 0,
            "processing_time": 0.0,
            "start_time": None,
        }

    def get_subscribed_events(self) -> List[EventType]:
        """Get subscribed event types."""
        return [
            EventType.PARSING,
            EventType.PATH_PROCESSING,
            EventType.POINT_PROCESSING,
            EventType.CURVE_PROCESSING,
            EventType.ERROR,
        ]

    def handle_event(self, event: Event) -> None:
        """Handle events for statistics collection."""
        if event.event_type == EventType.PARSING:
            self._handle_parsing_event(event)
        elif event.event_type == EventType.PATH_PROCESSING:
            self._handle_path_event(event)
        elif event.event_type == EventType.POINT_PROCESSING:
            self._handle_point_event(event)
        elif event.event_type == EventType.CURVE_PROCESSING:
            self._handle_curve_event(event)
        elif event.event_type == EventType.ERROR:
            self._handle_error_event(event)

    def _handle_parsing_event(self, event: Event) -> None:
        """Handle parsing event."""
        action = event.data.get("action", "")
        if action == "start":
            self.stats["start_time"] = event.timestamp
        elif action == "complete" and self.stats["start_time"]:
            self.stats["processing_time"] = event.timestamp - self.stats["start_time"]

    def _handle_path_event(self, event: Event) -> None:
        """Handle path processing event."""
        action = event.data.get("action", "")
        if action == "path_complete":
            self.stats["paths_processed"] += 1

    def _handle_point_event(self, event: Event) -> None:
        """Handle point processing event."""
        self.stats["points_processed"] += 1

    def _handle_curve_event(self, event: Event) -> None:
        """Handle curve processing event."""
        self.stats["curves_processed"] += 1

    def _handle_error_event(self, event: Event) -> None:
        """Handle error event."""
        self.stats["errors_encountered"] += 1

    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return self.stats.copy()

    def reset_statistics(self) -> None:
        """Reset statistics."""
        self.stats = {
            "paths_processed": 0,
            "points_processed": 0,
            "curves_processed": 0,
            "errors_encountered": 0,
            "processing_time": 0.0,
            "start_time": None,
        }


class ValidationSubscriber(EventSubscriber):
    """Validates weld data as events flow through the system.

    This subscriber validates all events in real-time, providing immediate
    feedback on data quality issues.
    """

    def __init__(self):
        """Initialize validation subscriber."""
        self.validation_errors: List[str] = []
        self.validation_warnings: List[str] = []
        self.current_path_id: str = ""
        self.current_path_has_points: bool = False
        self.current_path_point_count: int = 0
        self.valid_weld_types: set = set(get_valid_weld_types())
        self.path_stats: Dict[str, Dict[str, Any]] = {}

    def get_priority(self) -> int:
        """Get subscriber priority (lower number = higher priority)."""
        return 0  # Highest priority - validate first

    def get_subscribed_events(self) -> List[EventType]:
        """Get subscribed event types."""
        return [
            EventType.PATH_PROCESSING,
            EventType.POINT_PROCESSING,
            EventType.PARSING,
            EventType.OUTPUT_GENERATION,
        ]

    def handle_event(self, event: Event) -> None:
        """Validate events as they flow through the system."""
        try:
            if event.event_type == EventType.PATH_PROCESSING:
                self._validate_path_event(event)
            elif event.event_type == EventType.POINT_PROCESSING:
                self._validate_point_event(event)
            elif event.event_type == EventType.PARSING:
                self._validate_parsing_event(event)
        except Exception as e:
            self._add_error(f"Validation error: {e}")

    def _validate_path_event(self, event: Event) -> None:
        """Validate path-level events."""
        action = event.data.get("action", "")

        if action == "path_start":
            path_data = event.data.get("path_data", {})
            path_id = path_data.get("id", "")
            weld_type = path_data.get("weld_type", "")

            # Validate svg_id
            if not path_id or not path_id.strip():
                self._add_error(f"Path missing or empty svg_id")
                path_id = f"unknown_path_{len(self.path_stats)}"

            # Validate weld_type
            if weld_type not in self.valid_weld_types:
                self._add_error(f"Invalid weld_type '{weld_type}' for path {path_id}")

            # Initialize path tracking
            self.current_path_id = path_id
            self.current_path_has_points = False
            self.current_path_point_count = 0
            self.path_stats[path_id] = {
                "weld_type": weld_type,
                "point_count": 0,
                "has_errors": False,
                "errors": [],
            }

        elif action == "path_complete":
            # Validate that path had points
            if not self.current_path_has_points:
                error_msg = f"Path {self.current_path_id} has no points"
                self._add_error(error_msg)
                if self.current_path_id in self.path_stats:
                    self.path_stats[self.current_path_id]["has_errors"] = True
                    self.path_stats[self.current_path_id]["errors"].append(error_msg)

    def _validate_point_event(self, event: Event) -> None:
        """Validate point-level events."""
        action = event.data.get("action", "")

        if action == "point_added":
            self.current_path_has_points = True
            self.current_path_point_count += 1

            point_data = event.data.get("point_data", {})
            x = point_data.get("x")
            y = point_data.get("y")
            weld_type = point_data.get("weld_type", "")

            # Validate coordinates
            if x is None or y is None:
                self._add_error(
                    f"Point in path {self.current_path_id} missing coordinates"
                )
            elif not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                self._add_error(
                    f"Point in path {self.current_path_id} has invalid coordinate types"
                )

            # Validate point weld_type
            if weld_type and weld_type not in self.valid_weld_types:
                self._add_error(
                    f"Invalid point weld_type '{weld_type}' in path {self.current_path_id}"
                )

            # Update path stats
            if self.current_path_id in self.path_stats:
                self.path_stats[self.current_path_id][
                    "point_count"
                ] = self.current_path_point_count

    def _validate_parsing_event(self, event: Event) -> None:
        """Validate parsing events."""
        action = event.data.get("action", "")

        if action == "parsing_error":
            error_msg = event.data.get("error", "Unknown parsing error")
            self._add_error(f"Parsing error: {error_msg}")

    def _add_error(self, error: str) -> None:
        """Add validation error and publish event."""
        self.validation_errors.append(error)

        # Publish validation event for real-time error handling
        publish_event(
            ValidationEvent(result=False, message=error, error_type="validation_error")
        )

    def _add_warning(self, warning: str) -> None:
        """Add validation warning."""
        self.validation_warnings.append(warning)

        # Publish validation event for warnings
        publish_event(
            ValidationEvent(
                result=True, message=warning, error_type="validation_warning"
            )
        )

    def get_validation_results(self) -> Dict[str, Any]:
        """Get comprehensive validation results."""
        return {
            "has_errors": len(self.validation_errors) > 0,
            "has_warnings": len(self.validation_warnings) > 0,
            "errors": self.validation_errors.copy(),
            "warnings": self.validation_warnings.copy(),
            "error_count": len(self.validation_errors),
            "warning_count": len(self.validation_warnings),
            "path_stats": self.path_stats.copy(),
            "total_paths": len(self.path_stats),
            "valid_paths": len(
                [p for p in self.path_stats.values() if not p["has_errors"]]
            ),
            "total_points": sum(p["point_count"] for p in self.path_stats.values()),
        }

    def reset(self) -> None:
        """Reset validation state for new processing."""
        self.validation_errors.clear()
        self.validation_warnings.clear()
        self.current_path_id = ""
        self.current_path_has_points = False
        self.current_path_point_count = 0
        self.path_stats.clear()

    def is_valid(self) -> bool:
        """Check if all validation passed."""
        return len(self.validation_errors) == 0
