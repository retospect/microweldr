"""Enhanced converter with event-driven architecture and curve support."""

from pathlib import Path
from typing import List, Optional, Set
import time

from .config import Config
from .models import WeldPath
from .enhanced_svg_parser import EnhancedSVGParser

# Simplified converter without event system


class EnhancedSVGToGCodeConverter:
    """Enhanced converter with event-driven architecture and full curve support."""

    def __init__(
        self, config: Config, center_on_bed: bool = True, verbose: bool = True
    ) -> None:
        """Initialize enhanced converter."""
        self.config = config
        self.config.validate()
        self.center_on_bed = center_on_bed
        self.verbose = verbose

        # Initialize enhanced parser with curve support
        dot_spacing = self.config.get("normal_welds", "dot_spacing")
        self.svg_parser = EnhancedSVGParser(dot_spacing=dot_spacing)

        # Store parsed paths and coordinate transformation
        self.weld_paths: List[WeldPath] = []
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.margin_info = None

        # Subscribers
        self.subscribers: List[EventSubscriber] = []
        self.progress_tracker: Optional[ProgressTracker] = None
        self.statistics_collector: Optional[StatisticsSubscriber] = None

    def add_subscriber(self, subscriber: EventSubscriber) -> None:
        """Add a subscriber to the event system."""
        self.subscribers.append(subscriber)
        subscribe_to_events(subscriber, subscriber.get_subscribed_events())

    def remove_subscriber(self, subscriber: EventSubscriber) -> None:
        """Remove a subscriber from the event system."""
        if subscriber in self.subscribers:
            self.subscribers.remove(subscriber)
            unsubscribe_from_events(subscriber)

    def setup_default_subscribers(
        self,
        gcode_path: Optional[Path] = None,
        animation_path: Optional[Path] = None,
        enable_statistics: bool = True,
    ) -> None:
        """Set up default subscribers for common outputs."""

        # Progress tracker
        if self.verbose:
            self.progress_tracker = ProgressTracker(verbose=True)
            self.add_subscriber(self.progress_tracker)

        # Statistics collector
        if enable_statistics:
            self.statistics_collector = StatisticsSubscriber()
            self.add_subscriber(self.statistics_collector)

        # G-code generator
        if gcode_path:
            gcode_subscriber = GCodeSubscriber(self.config, gcode_path)
            self.add_subscriber(gcode_subscriber)

        # Animation generator
        if animation_path:
            animation_subscriber = AnimationSubscriber(self.config, animation_path)
            self.add_subscriber(animation_subscriber)

    def convert_with_events(
        self,
        svg_path: str | Path,
        gcode_path: Optional[str | Path] = None,
        animation_path: Optional[str | Path] = None,
        enable_statistics: bool = True,
    ) -> List[WeldPath]:
        """Convert SVG to outputs using event-driven architecture."""

        svg_path = Path(svg_path)

        # Set up output paths
        gcode_path_obj = Path(gcode_path) if gcode_path else None
        animation_path_obj = Path(animation_path) if animation_path else None

        # Clear previous event history
        event_publisher.clear_history()

        # Set up subscribers
        self.setup_default_subscribers(
            gcode_path=gcode_path_obj,
            animation_path=animation_path_obj,
            enable_statistics=enable_statistics,
        )

        try:
            # Parse SVG with events (this will trigger all the subscribers)
            self.weld_paths = self.svg_parser.parse_file(str(svg_path))

            # Apply centering if enabled
            if self.center_on_bed and self.weld_paths:
                self._calculate_centering_offset()
                self._apply_centering_offset()

            # Publish processing completed event
            publish_event(
                Event(
                    event_type=EventType.PROCESSING_COMPLETED,
                    timestamp=time.time(),
                    data={
                        "total_paths": len(self.weld_paths),
                        "total_points": sum(
                            len(path.points) for path in self.weld_paths
                        ),
                        "svg_path": str(svg_path),
                        "outputs_generated": {
                            "gcode": gcode_path_obj is not None,
                            "animation": animation_path_obj is not None,
                        },
                    },
                )
            )

            # Print statistics if available
            if self.statistics_collector and self.verbose:
                self.statistics_collector.print_statistics()

            return self.weld_paths

        finally:
            # Clean up subscribers
            for subscriber in self.subscribers.copy():
                self.remove_subscriber(subscriber)

    def convert_streaming(
        self, svg_path: str | Path, output_subscribers: List[EventSubscriber]
    ) -> List[WeldPath]:
        """Convert with custom subscribers for streaming/real-time processing."""

        svg_path = Path(svg_path)

        # Clear previous event history
        event_publisher.clear_history()

        # Add custom subscribers
        for subscriber in output_subscribers:
            self.add_subscriber(subscriber)

        # Add progress tracker if verbose
        if self.verbose:
            self.progress_tracker = ProgressTracker(verbose=True)
            self.add_subscriber(self.progress_tracker)

        try:
            # Parse SVG - subscribers will receive events in real-time
            self.weld_paths = self.svg_parser.parse_file(str(svg_path))

            # Apply centering if enabled
            if self.center_on_bed and self.weld_paths:
                self._calculate_centering_offset()
                self._apply_centering_offset()

            return self.weld_paths

        finally:
            # Clean up subscribers
            for subscriber in self.subscribers.copy():
                self.remove_subscriber(subscriber)

    def get_supported_curve_types(self) -> Set[str]:
        """Get the set of supported SVG curve types."""
        return {
            "quadratic_bezier",  # Q command
            "cubic_bezier",  # C command
            "smooth_cubic_bezier",  # S command
            "smooth_quadratic_bezier",  # T command
            "elliptical_arc",  # A command
        }

    def get_event_history(self) -> List[Event]:
        """Get the event history from the last conversion."""
        return event_publisher.get_event_history()

    def _calculate_centering_offset(self) -> None:
        """Calculate offset needed to center the design on the bed."""
        if not self.weld_paths:
            return

        # Get bounds of all weld paths
        all_points = []
        for path in self.weld_paths:
            all_points.extend(path.points)

        if not all_points:
            return

        min_x = min(point.x for point in all_points)
        max_x = max(point.x for point in all_points)
        min_y = min(point.y for point in all_points)
        max_y = max(point.y for point in all_points)

        # Get bed dimensions from config
        bed_size_x = self.config.get("printer", "bed_size_x")
        bed_size_y = self.config.get("printer", "bed_size_y")

        # Calculate design dimensions
        design_width = max_x - min_x
        design_height = max_y - min_y

        # Calculate offset to center the design
        bed_center_x = bed_size_x / 2
        bed_center_y = bed_size_y / 2
        design_center_x = min_x + design_width / 2
        design_center_y = min_y + design_height / 2

        self.offset_x = bed_center_x - design_center_x
        self.offset_y = bed_center_y - design_center_y

        # Calculate final position after centering
        final_min_x = min_x + self.offset_x
        final_max_x = max_x + self.offset_x
        final_min_y = min_y + self.offset_y
        final_max_y = max_y + self.offset_y

        # Calculate margins from bed edges
        margin_left = final_min_x
        margin_right = bed_size_x - final_max_x
        margin_front = final_min_y  # Front is Y=0 side
        margin_back = bed_size_y - final_max_y  # Back is Y=max side

        if self.verbose:
            print(
                f"📐 Design bounds: ({min_x:.1f}, {min_y:.1f}) to ({max_x:.1f}, {max_y:.1f})"
            )
            print(f"📐 Design size: {design_width:.1f} × {design_height:.1f} mm")
            print(f"🎯 Centering offset: ({self.offset_x:.1f}, {self.offset_y:.1f}) mm")
            print(
                f"🎯 Centered position: ({final_min_x:.1f}, {final_min_y:.1f}) to ({final_max_x:.1f}, {final_max_y:.1f})"
            )
            print(
                f"📏 Bed margins: Front/Back: {margin_front/10:.1f}/{margin_back/10:.1f}cm, Left/Right: {margin_left/10:.1f}/{margin_right/10:.1f}cm"
            )

        # Store margin info for use in G-code generation
        self.margin_info = {
            "front_back": f"{margin_front/10:.1f}/{margin_back/10:.1f}cm",
            "left_right": f"{margin_left/10:.1f}/{margin_right/10:.1f}cm",
            "design_size": f"{design_width:.0f}×{design_height:.0f}mm",
        }

    def _apply_centering_offset(self) -> None:
        """Apply the centering offset to all weld points."""
        if self.offset_x == 0 and self.offset_y == 0:
            return

        for path in self.weld_paths:
            for point in path.points:
                point.x += self.offset_x
                point.y += self.offset_y

    @property
    def path_count(self) -> int:
        """Get the number of parsed weld paths."""
        return len(self.weld_paths)

    def get_bounds(self) -> tuple[float, float, float, float]:
        """Get the bounding box of all weld paths as (min_x, min_y, max_x, max_y)."""
        if not self.weld_paths:
            return (0.0, 0.0, 0.0, 0.0)

        all_bounds = [path.get_bounds() for path in self.weld_paths]

        min_x = min(bounds[0] for bounds in all_bounds)
        min_y = min(bounds[1] for bounds in all_bounds)
        max_x = max(bounds[2] for bounds in all_bounds)
        max_y = max(bounds[3] for bounds in all_bounds)

        return (min_x, min_y, max_x, max_y)


# Custom subscribers for specific use cases


class RealTimeMonitorSubscriber(EventSubscriber):
    """Real-time monitoring subscriber for live feedback."""

    def __init__(self, callback_func=None):
        """Initialize with optional callback function."""
        self.callback_func = callback_func
        self.current_status = "idle"

    def get_subscribed_events(self) -> Set[EventType]:
        """Subscribe to all events for real-time monitoring."""
        return set(EventType)  # Subscribe to all event types

    def handle_event(self, event: Event) -> None:
        """Handle events for real-time monitoring."""
        # Update status based on event
        if event.event_type == EventType.PARSING_STARTED:
            self.current_status = "parsing"
        elif event.event_type == EventType.PARSING_COMPLETED:
            self.current_status = "processing"
        elif event.event_type == EventType.OUTPUT_STARTED:
            self.current_status = "generating"
        elif event.event_type == EventType.OUTPUT_COMPLETED:
            self.current_status = "completed"
        elif event.event_type == EventType.ERROR_OCCURRED:
            self.current_status = "error"

        # Call callback if provided
        if self.callback_func:
            self.callback_func(event, self.current_status)


class JSONExportSubscriber(EventSubscriber):
    """Subscriber that exports processing data to JSON."""

    def __init__(self, output_path: Path):
        """Initialize JSON export subscriber."""
        self.output_path = Path(output_path)
        self.data = {"paths": [], "statistics": {}, "events": []}

    def get_subscribed_events(self) -> Set[EventType]:
        """Subscribe to path and curve events."""
        return {
            EventType.PATH_COMPLETED,
            EventType.CURVE_APPROXIMATED,
            EventType.PROCESSING_COMPLETED,
        }

    def handle_event(self, event: Event) -> None:
        """Handle events for JSON export."""
        if event.event_type == EventType.PATH_COMPLETED:
            path_event = event
            if hasattr(path_event, "path") and path_event.path:
                path_data = {
                    "svg_id": path_event.path.svg_id,
                    "weld_type": path_event.path.weld_type,
                    "point_count": len(path_event.path.points),
                    "bounds": path_event.path.get_bounds(),
                }
                self.data["paths"].append(path_data)

        elif event.event_type == EventType.CURVE_APPROXIMATED:
            curve_event = event
            event_data = {
                "timestamp": event.timestamp,
                "curve_type": getattr(curve_event, "curve_type", "unknown"),
                "points_generated": len(
                    getattr(curve_event, "approximated_points", [])
                ),
            }
            self.data["events"].append(event_data)

        elif event.event_type == EventType.PROCESSING_COMPLETED:
            # Write JSON file
            import json

            with open(self.output_path, "w") as f:
                json.dump(self.data, f, indent=2)
