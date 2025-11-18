"""Fixed data models for structured data in MicroWeldr."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path


@dataclass
class Point:
    """Represents a 2D point."""

    x: float
    y: float

    def __post_init__(self):
        """Validate point coordinates."""
        if not isinstance(self.x, (int, float)) or not isinstance(self.y, (int, float)):
            raise ValueError(
                f"Point coordinates must be numeric, got x={type(self.x)}, y={type(self.y)}"
            )

    def distance_to(self, other: "Point") -> float:
        """Calculate distance to another point."""
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5

    def __add__(self, other: "Point") -> "Point":
        """Add two points."""
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Point") -> "Point":
        """Subtract two points."""
        return Point(self.x - other.x, self.y - other.y)


class WeldType(Enum):
    """Types of welds supported."""

    NORMAL = "normal"
    FRANGIBLE = "frangible"  # Formerly light welds


@dataclass
class WeldConfig:
    """Configuration for weld parameters."""

    weld_height: float
    weld_temperature: float
    weld_time: float
    dot_spacing: float

    def __post_init__(self):
        """Validate weld configuration values."""
        if self.weld_height < 0:
            raise ValueError("Weld height must be non-negative")
        if self.weld_temperature < 0:
            raise ValueError("Weld temperature must be non-negative")
        if self.weld_time <= 0:
            raise ValueError("Weld time must be positive")
        if self.dot_spacing <= 0:
            raise ValueError("Dot spacing must be positive")


@dataclass
class WeldSettings:
    """Settings for a specific weld type."""

    weld_height: float
    weld_temperature: float
    weld_time: float
    dot_spacing: float

    def __post_init__(self):
        """Validate weld settings."""
        if self.weld_height < 0:
            raise ValueError("Weld height must be non-negative")
        if self.weld_temperature < 0:
            raise ValueError("Weld temperature must be non-negative")
        if self.weld_time <= 0:
            raise ValueError("Weld time must be positive")


@dataclass
class WeldPath:
    """Represents a path to be welded."""

    points: List[Point]
    weld_type: WeldType = field(default_factory=lambda: WeldType.NORMAL)
    layer_name: Optional[str] = None
    path_id: Optional[str] = None

    def __post_init__(self):
        """Validate weld path."""
        if not self.points:
            raise ValueError("Weld path must have at least one point")
        if len(self.points) < 2:
            raise ValueError("Weld path must have at least two points for welding")

    @property
    def svg_id(self) -> Optional[str]:
        """Backward compatibility property for svg_id."""
        return self.path_id

    @property
    def length(self) -> float:
        """Calculate total path length."""
        if len(self.points) < 2:
            return 0.0

        total = 0.0
        for i in range(1, len(self.points)):
            total += self.points[i - 1].distance_to(self.points[i])
        return total

    @property
    def bounds(self) -> Tuple[Point, Point]:
        """Get bounding box of the path."""
        if not self.points:
            return Point(0, 0), Point(0, 0)

        min_x = min(p.x for p in self.points)
        max_x = max(p.x for p in self.points)
        min_y = min(p.y for p in self.points)
        max_y = max(p.y for p in self.points)

        return Point(min_x, min_y), Point(max_x, max_y)


@dataclass
class PrinterStatus:
    """Structured printer status information."""

    state: str
    bed_actual: float
    bed_target: float
    nozzle_actual: float
    nozzle_target: float
    axis_x: Optional[float] = None
    axis_y: Optional[float] = None
    axis_z: Optional[float] = None

    @property
    def is_ready(self) -> bool:
        """Check if printer is ready for operations."""
        return self.state.lower() in ["operational", "ready", "finished"]

    @property
    def temperatures_stable(self, tolerance: float = 5.0) -> bool:
        """Check if temperatures are stable within tolerance."""
        bed_stable = abs(self.bed_actual - self.bed_target) <= tolerance
        nozzle_stable = abs(self.nozzle_actual - self.nozzle_target) <= tolerance
        return bed_stable and nozzle_stable


@dataclass
class JobStatus:
    """Structured job status information."""

    state: str
    progress: float
    time_printing: Optional[float] = None
    time_remaining: Optional[float] = None
    file_name: Optional[str] = None

    @property
    def is_printing(self) -> bool:
        """Check if a job is currently printing."""
        return self.state.lower() in ["printing", "paused"]

    @property
    def is_finished(self) -> bool:
        """Check if job is finished."""
        return self.state.lower() in ["finished", "completed"]


@dataclass
class FileInfo:
    """Information about a processed file."""

    path: Path
    file_type: str  # 'svg', 'dxf', etc.
    size_bytes: int
    paths_count: int
    points_count: int
    processing_time: Optional[float] = None

    @property
    def size_mb(self) -> float:
        """File size in megabytes."""
        return self.size_bytes / (1024 * 1024)


@dataclass
class ValidationResult:
    """Result of validation operations."""

    is_valid: bool
    message: str
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    details: Dict[str, any] = field(default_factory=dict)

    def add_warning(self, warning: str):
        """Add a warning to the result."""
        self.warnings.append(warning)

    def add_error(self, error: str):
        """Add an error to the result."""
        self.errors.append(error)
        self.is_valid = False


@dataclass
class ProcessingStats:
    """Statistics from file processing."""

    files_processed: int = 0
    total_paths: int = 0
    total_points: int = 0
    normal_welds: int = 0
    frangible_welds: int = 0
    processing_time: float = 0.0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_file_stats(self, file_info: FileInfo, paths: List[WeldPath]):
        """Add statistics from a processed file."""
        self.files_processed += 1
        self.total_paths += len(paths)
        self.total_points += sum(len(path.points) for path in paths)

        for path in paths:
            if path.weld_type == WeldType.NORMAL:
                self.normal_welds += 1
            elif path.weld_type == WeldType.FRANGIBLE:
                self.frangible_welds += 1

        if file_info.processing_time:
            self.processing_time += file_info.processing_time


# Simplified CAD entities without inheritance issues
@dataclass
class LineEntity:
    """Represents a line entity from CAD files."""

    layer: str
    start: Point
    end: Point

    @property
    def entity_type(self) -> str:
        """Entity type."""
        return "LINE"

    @property
    def is_construction(self) -> bool:
        """Check if this is a construction entity."""
        construction_patterns = ["construction", "const", "guide", "reference", "ref"]
        return any(pattern in self.layer.lower() for pattern in construction_patterns)

    @property
    def length(self) -> float:
        """Calculate line length."""
        return self.start.distance_to(self.end)

    def to_weld_path(
        self, weld_type: WeldType = WeldType.NORMAL, dot_spacing: float = 2.0
    ) -> WeldPath:
        """Convert to weld path with interpolated points."""
        import math

        # Calculate line length and number of segments
        length = self.length
        if length < 1e-10:  # Degenerate line
            return WeldPath([self.start], weld_type, self.layer)

        # For very short lines, use only one point (the midpoint) to avoid duplicates
        if length < dot_spacing * 0.5:
            # Use midpoint for very short lines
            mid_x = (self.start.x + self.end.x) / 2
            mid_y = (self.start.y + self.end.y) / 2
            points = [Point(mid_x, mid_y)]
        else:
            # Calculate number of points based on dot spacing
            num_points = max(2, int(length / dot_spacing) + 1)

            # Generate interpolated points along the line
            points = []
            for i in range(num_points):
                t = i / (num_points - 1) if num_points > 1 else 0
                x = self.start.x + t * (self.end.x - self.start.x)
                y = self.start.y + t * (self.end.y - self.start.y)
                points.append(Point(x, y))

        return WeldPath(points, weld_type, self.layer)


@dataclass
class ArcEntity:
    """Represents an arc entity from CAD files."""

    layer: str
    center: Point
    radius: float
    start_angle: float  # in degrees
    end_angle: float  # in degrees

    def __post_init__(self):
        """Validate arc."""
        if self.radius <= 0:
            raise ValueError("Arc radius must be positive")

    @property
    def entity_type(self) -> str:
        """Entity type."""
        return "ARC"

    @property
    def is_construction(self) -> bool:
        """Check if this is a construction entity."""
        construction_patterns = ["construction", "const", "guide", "reference", "ref"]
        return any(pattern in self.layer.lower() for pattern in construction_patterns)

    def to_weld_path(
        self, segments: int = 20, weld_type: WeldType = WeldType.NORMAL
    ) -> WeldPath:
        """Convert arc to weld path with line segments."""
        import math

        points = []
        angle_range = self.end_angle - self.start_angle

        # Handle angle wrapping
        if angle_range < 0:
            angle_range += 360

        for i in range(segments + 1):
            angle = self.start_angle + (angle_range * i / segments)
            angle_rad = math.radians(angle)

            x = self.center.x + self.radius * math.cos(angle_rad)
            y = self.center.y + self.radius * math.sin(angle_rad)
            points.append(Point(x, y))

        return WeldPath(points, weld_type, self.layer)


@dataclass
class CircleEntity:
    """Represents a circle entity from CAD files."""

    layer: str
    center: Point
    radius: float

    def __post_init__(self):
        """Validate circle."""
        if self.radius <= 0:
            raise ValueError("Circle radius must be positive")

    @property
    def entity_type(self) -> str:
        """Entity type."""
        return "CIRCLE"

    @property
    def is_construction(self) -> bool:
        """Check if this is a construction entity."""
        construction_patterns = ["construction", "const", "guide", "reference", "ref"]
        return any(pattern in self.layer.lower() for pattern in construction_patterns)

    def to_weld_path(
        self, segments: int = 36, weld_type: WeldType = WeldType.NORMAL
    ) -> WeldPath:
        """Convert circle to weld path with line segments."""
        import math

        points = []
        for i in range(segments):
            angle = 2 * math.pi * i / segments
            x = self.center.x + self.radius * math.cos(angle)
            y = self.center.y + self.radius * math.sin(angle)
            points.append(Point(x, y))

        # Close the circle
        points.append(points[0])

        return WeldPath(points, weld_type, self.layer)


# Union type for all CAD entities
CADEntity = Union[LineEntity, ArcEntity, CircleEntity]
