"""Event subscribers for different output generators."""

import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TextIO
from abc import ABC, abstractmethod
import logging

from .events import (
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
    publish_event,
)
from .models import WeldPath, WeldPoint

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
    """Generates G-code output from events."""

    def __init__(self, output_path: Path, config):
        """Initialize G-code subscriber."""
        self.output_path = Path(output_path)
        self.config = config
        self.weld_paths: List[WeldPath] = []
        self.current_path: Optional[WeldPath] = None

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
            # Start new path
            path_data = event.data.get("path_data", {})
            self.current_path = WeldPath(
                id=path_data.get("id", ""),
                weld_type=path_data.get("weld_type", "normal"),
                points=[],
            )
        elif action == "point_added" and self.current_path:
            # Add point to current path
            point_data = event.data.get("point_data", {})
            point = WeldPoint(
                x=point_data.get("x", 0),
                y=point_data.get("y", 0),
                weld_type=point_data.get("weld_type", "normal"),
            )
            self.current_path.points.append(point)
        elif action == "path_complete" and self.current_path:
            # Complete current path
            self.weld_paths.append(self.current_path)
            self.current_path = None

    def _handle_output_event(self, event: Event) -> None:
        """Handle output generation event."""
        action = event.data.get("action", "")
        output_type = event.data.get("output_type", "")

        if action == "generate" and output_type == "gcode":
            self._generate_gcode()

    def _generate_gcode(self) -> None:
        """Generate G-code file."""
        from .gcode_generator import GCodeGenerator

        generator = GCodeGenerator(self.config)
        generator.generate_gcode(self.weld_paths, self.output_path)

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
            # Start new path
            path_data = event.data.get("path_data", {})
            self.current_path = WeldPath(
                id=path_data.get("id", ""),
                weld_type=path_data.get("weld_type", "normal"),
                points=[],
            )
        elif action == "point_added" and self.current_path:
            # Add point to current path
            point_data = event.data.get("point_data", {})
            point = WeldPoint(
                x=point_data.get("x", 0),
                y=point_data.get("y", 0),
                weld_type=point_data.get("weld_type", "normal"),
            )
            self.current_path.points.append(point)
        elif action == "path_complete" and self.current_path:
            # Complete current path
            self.weld_paths.append(self.current_path)
            self.current_path = None

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
