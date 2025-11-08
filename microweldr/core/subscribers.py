"""Event subscribers for different output generators."""

import time
from pathlib import Path
from typing import Dict, List, Optional, Set, TextIO
from abc import ABC, abstractmethod

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
    publish_event,
)
from .models import WeldPath, WeldPoint
from .config import Config


class ProgressTracker(EventSubscriber):
    """Tracks and displays progress of the entire pipeline."""

    def __init__(self, verbose: bool = True):
        """Initialize progress tracker."""
        self.verbose = verbose
        self.start_time = None
        self.parsing_progress = 0.0
        self.output_progress = {}  # Track progress per output type
        self.total_paths = 0
        self.processed_paths = 0
        self.total_points = 0
        self.processed_points = 0

    def get_subscribed_events(self) -> Set[EventType]:
        """Subscribe to all progress-related events."""
        return {
            EventType.PARSING_STARTED,
            EventType.PARSING_PROGRESS,
            EventType.PARSING_COMPLETED,
            EventType.PATH_STARTED,
            EventType.PATH_COMPLETED,
            EventType.POINTS_BATCH,
            EventType.CURVE_APPROXIMATED,
            EventType.OUTPUT_STARTED,
            EventType.OUTPUT_PROGRESS,
            EventType.OUTPUT_COMPLETED,
            EventType.ERROR_OCCURRED,
            EventType.WARNING_ISSUED,
        }

    def handle_event(self, event: Event) -> None:
        """Handle progress events."""
        if event.event_type == EventType.PARSING_STARTED:
            self.start_time = event.timestamp
            if self.verbose:
                parsing_event = event
                if hasattr(parsing_event, "svg_path") and parsing_event.svg_path:
                    print(f"🔍 Starting to parse {parsing_event.svg_path.name}")

        elif event.event_type == EventType.PARSING_PROGRESS:
            parsing_event = event
            if hasattr(parsing_event, "total_elements") and hasattr(
                parsing_event, "processed_elements"
            ):
                if parsing_event.total_elements and parsing_event.total_elements > 0:
                    progress = (
                        parsing_event.processed_elements / parsing_event.total_elements
                    ) * 100
                    if self.verbose and progress % 20 < 5:  # Show every 20%
                        print(
                            f"📊 Parsing progress: {progress:.0f}% ({parsing_event.processed_elements}/{parsing_event.total_elements})"
                        )

        elif event.event_type == EventType.PARSING_COMPLETED:
            parsing_event = event
            if hasattr(parsing_event, "total_elements"):
                self.total_paths = parsing_event.total_elements or 0
                if self.verbose:
                    elapsed = event.timestamp - (self.start_time or event.timestamp)
                    print(
                        f"✅ Parsing completed: {self.total_paths} paths in {elapsed:.2f}s"
                    )

        elif event.event_type == EventType.PATH_COMPLETED:
            self.processed_paths += 1

        elif event.event_type == EventType.POINTS_BATCH:
            point_event = event
            if hasattr(point_event, "points") and point_event.points:
                self.processed_points += len(point_event.points)

        elif event.event_type == EventType.CURVE_APPROXIMATED:
            if self.verbose:
                curve_event = event
                curve_type = getattr(curve_event, "curve_type", "unknown")
                points_count = len(getattr(curve_event, "approximated_points", []))
                print(f"🌊 Approximated {curve_type} curve → {points_count} points")

        elif event.event_type == EventType.OUTPUT_STARTED:
            output_event = event
            output_type = getattr(output_event, "output_type", "unknown")
            if self.verbose:
                print(f"🔧 Starting {output_type} generation...")

        elif event.event_type == EventType.OUTPUT_PROGRESS:
            output_event = event
            output_type = getattr(output_event, "output_type", "unknown")
            progress = getattr(output_event, "progress", 0.0)
            self.output_progress[output_type] = progress
            if self.verbose and progress and progress % 0.2 < 0.05:  # Show every 20%
                print(f"📈 {output_type}: {progress*100:.0f}%")

        elif event.event_type == EventType.OUTPUT_COMPLETED:
            output_event = event
            output_type = getattr(output_event, "output_type", "unknown")
            output_path = getattr(output_event, "output_path", None)
            if self.verbose:
                path_str = f" → {output_path.name}" if output_path else ""
                print(f"✅ {output_type} completed{path_str}")

        elif event.event_type == EventType.ERROR_OCCURRED:
            error_event = event
            if hasattr(error_event, "message"):
                print(f"❌ Error: {error_event.message}")

        elif event.event_type == EventType.WARNING_ISSUED:
            error_event = event
            if hasattr(error_event, "message"):
                print(f"⚠️  Warning: {error_event.message}")


class GCodeSubscriber(EventSubscriber):
    """Subscribes to events and generates G-code output."""

    def __init__(self, config: Config, output_path: Path):
        """Initialize G-code subscriber."""
        self.config = config
        self.output_path = Path(output_path)
        self.weld_paths: List[WeldPath] = []
        self.file_handle: Optional[TextIO] = None
        self.current_path_index = 0
        self.total_paths = 0

    def get_subscribed_events(self) -> Set[EventType]:
        """Subscribe to path and processing events."""
        return {
            EventType.PARSING_STARTED,
            EventType.PARSING_COMPLETED,
            EventType.PATH_COMPLETED,
            EventType.PROCESSING_STARTED,
            EventType.PROCESSING_COMPLETED,
        }

    def handle_event(self, event: Event) -> None:
        """Handle events for G-code generation."""
        if event.event_type == EventType.PARSING_STARTED:
            # Initialize G-code file
            self._start_gcode_generation()

        elif event.event_type == EventType.PATH_COMPLETED:
            path_event = event
            if hasattr(path_event, "path") and path_event.path:
                self.weld_paths.append(path_event.path)
                # Generate G-code for this path immediately (streaming approach)
                self._write_path_gcode(path_event.path)

        elif event.event_type == EventType.PARSING_COMPLETED:
            # Finalize G-code file
            self._finish_gcode_generation()

    def _start_gcode_generation(self) -> None:
        """Start G-code file generation."""
        publish_event(
            OutputEvent(
                event_type=EventType.OUTPUT_STARTED,
                timestamp=time.time(),
                data={"output_type": "gcode"},
                output_type="gcode",
                output_path=self.output_path,
            )
        )

        self.file_handle = open(self.output_path, "w")
        self._write_gcode_header()

    def _write_gcode_header(self) -> None:
        """Write G-code header."""
        if not self.file_handle:
            return

        self.file_handle.write("; Generated by MicroWeldr (Event-Driven)\n")
        self.file_handle.write("; Prusa Core One Plastic Welding G-code\n")
        self.file_handle.write(
            f"; Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )

        # Write initialization sequence
        self._write_initialization()

    def _write_initialization(self) -> None:
        """Write printer initialization commands."""
        if not self.file_handle:
            return

        bed_temp = self.config.get("temperatures", "bed_temperature")
        nozzle_temp = self.config.get("temperatures", "nozzle_temperature")

        self.file_handle.write("; Initialization\n")
        self.file_handle.write("G90 ; Absolute positioning\n")
        self.file_handle.write("M83 ; Relative extruder positioning\n")
        self.file_handle.write("G28 ; Home all axes\n")
        self.file_handle.write("G29 ; Auto bed leveling\n\n")

        self.file_handle.write("; Heating\n")
        self.file_handle.write(f"M140 S{bed_temp} ; Set bed temperature\n")
        self.file_handle.write(f"M190 S{bed_temp} ; Wait for bed temperature\n")
        self.file_handle.write(f"M104 S{nozzle_temp} ; Set nozzle temperature\n")
        self.file_handle.write(f"M109 S{nozzle_temp} ; Wait for nozzle temperature\n\n")

        self.file_handle.write("; Pause for plastic insertion\n")
        self.file_handle.write("M117 Insert plastic sheets\n")
        self.file_handle.write(
            "M0 ; Pause - Insert plastic sheets and press continue\n"
        )
        self.file_handle.write("M117 Starting welding...\n\n")

    def _write_path_gcode(self, path: WeldPath) -> None:
        """Write G-code for a single path."""
        if not self.file_handle:
            return

        self.current_path_index += 1

        # Publish progress
        progress = self.current_path_index / max(1, len(self.weld_paths))
        publish_event(
            OutputEvent(
                event_type=EventType.OUTPUT_PROGRESS,
                timestamp=time.time(),
                data={"path_index": self.current_path_index},
                output_type="gcode",
                progress=progress,
            )
        )

        self.file_handle.write(f"; Path: {path.svg_id} (type: {path.weld_type})\n")

        if path.weld_type in ["stop", "pipette"]:
            # Handle pause points
            message = path.pause_message or "Manual intervention required"
            safe_message = message.replace('"', "'").replace(";", ",")[:64]
            self.file_handle.write(f"M117 {safe_message}\n")
            self.file_handle.write("M0 ; Pause for user action\n")
            self.file_handle.write("M117 Continuing...\n\n")
            return

        # Write welding points
        move_height = self.config.get("movement", "move_height")
        weld_height = self.config.get(f"{path.weld_type}_welds", "weld_height")
        weld_time = self.config.get(f"{path.weld_type}_welds", "weld_time")
        travel_speed = self.config.get("movement", "travel_speed")
        z_speed = self.config.get("movement", "z_speed")

        for point in path.points:
            # Move to position at safe height
            self.file_handle.write(
                f"G1 X{point.x:.3f} Y{point.y:.3f} Z{move_height} F{travel_speed}\n"
            )
            # Lower to welding height
            self.file_handle.write(f"G1 Z{weld_height:.3f} F{z_speed}\n")
            # Weld time
            weld_ms = int(weld_time * 1000)
            self.file_handle.write(f"G4 P{weld_ms} ; Weld time\n")
            # Raise to safe height
            self.file_handle.write(f"G1 Z{move_height} F{z_speed}\n")

        self.file_handle.write("\n")

    def _finish_gcode_generation(self) -> None:
        """Finish G-code generation."""
        if not self.file_handle:
            return

        # Write cooldown sequence
        cooldown_temp = self.config.get("temperatures", "cooldown_temperature")
        self.file_handle.write("; Cooldown\n")
        self.file_handle.write(f"M104 S{cooldown_temp} ; Cool nozzle\n")
        self.file_handle.write(f"M140 S{cooldown_temp} ; Cool bed\n")
        self.file_handle.write("G28 X Y ; Home X and Y\n")
        self.file_handle.write("M84 ; Disable steppers\n")
        self.file_handle.write("; End of G-code\n")

        self.file_handle.close()
        self.file_handle = None

        publish_event(
            OutputEvent(
                event_type=EventType.OUTPUT_COMPLETED,
                timestamp=time.time(),
                data={"total_paths": len(self.weld_paths)},
                output_type="gcode",
                output_path=self.output_path,
            )
        )


class AnimationSubscriber(EventSubscriber):
    """Subscribes to events and generates animation output."""

    def __init__(self, config: Config, output_path: Path):
        """Initialize animation subscriber."""
        self.config = config
        self.output_path = Path(output_path)
        self.weld_paths: List[WeldPath] = []
        self.bounds = None

    def get_subscribed_events(self) -> Set[EventType]:
        """Subscribe to path completion events."""
        return {EventType.PARSING_COMPLETED, EventType.PATH_COMPLETED}

    def handle_event(self, event: Event) -> None:
        """Handle events for animation generation."""
        if event.event_type == EventType.PATH_COMPLETED:
            path_event = event
            if hasattr(path_event, "path") and path_event.path:
                self.weld_paths.append(path_event.path)

        elif event.event_type == EventType.PARSING_COMPLETED:
            # Generate animation after all paths are collected
            self._generate_animation()

    def _generate_animation(self) -> None:
        """Generate animation file."""
        if not self.weld_paths:
            return

        publish_event(
            OutputEvent(
                event_type=EventType.OUTPUT_STARTED,
                timestamp=time.time(),
                data={"output_type": "animation"},
                output_type="animation",
                output_path=self.output_path,
            )
        )

        # Calculate bounds
        self.bounds = self._calculate_bounds()

        # Generate SVG animation
        self._write_svg_animation()

        publish_event(
            OutputEvent(
                event_type=EventType.OUTPUT_COMPLETED,
                timestamp=time.time(),
                data={"total_paths": len(self.weld_paths)},
                output_type="animation",
                output_path=self.output_path,
            )
        )

    def _calculate_bounds(self) -> tuple:
        """Calculate bounding box for all paths."""
        all_points = []
        for path in self.weld_paths:
            all_points.extend(path.points)

        if not all_points:
            return (0.0, 0.0, 0.0, 0.0)

        min_x = min(p.x for p in all_points)
        max_x = max(p.x for p in all_points)
        min_y = min(p.y for p in all_points)
        max_y = max(p.y for p in all_points)

        return (min_x, min_y, max_x, max_y)

    def _write_svg_animation(self) -> None:
        """Write SVG animation file."""
        if not self.bounds:
            return

        min_x, min_y, max_x, max_y = self.bounds
        padding = 2.0
        width = (max_x - min_x + 2 * padding) * 3
        height = (max_y - min_y + 2 * padding) * 3

        with open(self.output_path, "w") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write(
                f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">\n'
            )
            f.write('  <rect width="100%" height="100%" fill="white"/>\n')

            # Write animated elements
            current_time = 0.0
            time_between_welds = self.config.get("animation", "time_between_welds")

            for path in self.weld_paths:
                if path.weld_type in ["stop", "pipette"]:
                    continue

                color = "blue" if path.weld_type == "frangible" else "black"

                for point in path.points:
                    x = (point.x - min_x + padding) * 3
                    y = (point.y - min_y + padding) * 3

                    f.write(f'  <g transform="translate({x},{y})" opacity="0">\n')
                    f.write(
                        f'    <animate attributeName="opacity" values="0;1" dur="0.01s" begin="{current_time:.2f}s" fill="freeze"/>\n'
                    )
                    f.write(
                        f'    <circle cx="0" cy="0" r="1.65" fill="{color}" stroke="{color}" stroke-width="0.5" opacity="0.8"/>\n'
                    )
                    f.write("  </g>\n")

                    current_time += time_between_welds

            f.write("</svg>\n")


class StatisticsSubscriber(EventSubscriber):
    """Collects statistics about the processing pipeline."""

    def __init__(self):
        """Initialize statistics subscriber."""
        self.stats = {
            "total_paths": 0,
            "total_points": 0,
            "curves_approximated": 0,
            "curve_types": {},
            "weld_types": {},
            "processing_time": 0.0,
            "start_time": None,
            "end_time": None,
        }

    def get_subscribed_events(self) -> Set[EventType]:
        """Subscribe to all relevant events."""
        return {
            EventType.PARSING_STARTED,
            EventType.PARSING_COMPLETED,
            EventType.PATH_COMPLETED,
            EventType.POINTS_BATCH,
            EventType.CURVE_APPROXIMATED,
        }

    def handle_event(self, event: Event) -> None:
        """Handle events for statistics collection."""
        if event.event_type == EventType.PARSING_STARTED:
            self.stats["start_time"] = event.timestamp

        elif event.event_type == EventType.PARSING_COMPLETED:
            self.stats["end_time"] = event.timestamp
            if self.stats["start_time"]:
                self.stats["processing_time"] = (
                    self.stats["end_time"] - self.stats["start_time"]
                )

        elif event.event_type == EventType.PATH_COMPLETED:
            self.stats["total_paths"] += 1
            path_event = event
            if hasattr(path_event, "path") and path_event.path:
                weld_type = path_event.path.weld_type
                self.stats["weld_types"][weld_type] = (
                    self.stats["weld_types"].get(weld_type, 0) + 1
                )

        elif event.event_type == EventType.POINTS_BATCH:
            point_event = event
            if hasattr(point_event, "points") and point_event.points:
                self.stats["total_points"] += len(point_event.points)

        elif event.event_type == EventType.CURVE_APPROXIMATED:
            self.stats["curves_approximated"] += 1
            curve_event = event
            if hasattr(curve_event, "curve_type"):
                curve_type = curve_event.curve_type
                self.stats["curve_types"][curve_type] = (
                    self.stats["curve_types"].get(curve_type, 0) + 1
                )

    def get_statistics(self) -> Dict:
        """Get collected statistics."""
        return self.stats.copy()

    def print_statistics(self) -> None:
        """Print formatted statistics."""
        print("\n📊 Processing Statistics:")
        print(f"   Total paths: {self.stats['total_paths']}")
        print(f"   Total points: {self.stats['total_points']}")
        print(f"   Curves approximated: {self.stats['curves_approximated']}")
        print(f"   Processing time: {self.stats['processing_time']:.2f}s")

        if self.stats["weld_types"]:
            print("   Weld types:")
            for weld_type, count in self.stats["weld_types"].items():
                print(f"     {weld_type}: {count}")

        if self.stats["curve_types"]:
            print("   Curve types:")
            for curve_type, count in self.stats["curve_types"].items():
                print(f"     {curve_type}: {count}")
