"""DXF file reader with publisher-subscriber architecture."""

import logging
import math
from pathlib import Path
from typing import List, Optional, Dict, Any

from ..core.app_constants import DXFEntities, LayerTypes
from ..core.data_models import (
    Point,
    WeldType,
    WeldPath as DataWeldPath,
    LineEntity,
    ArcEntity,
    CircleEntity,
    CADEntity,
)
from ..core.models import WeldPath, WeldPoint
from ..core.error_handling import FileProcessingError, ParsingError, handle_errors
from .file_readers import FileReaderPublisher

logger = logging.getLogger(__name__)

try:
    import ezdxf

    DXF_AVAILABLE = True
except ImportError:
    DXF_AVAILABLE = False
    logger.warning("ezdxf not available - DXF reading disabled")


class DXFReader(FileReaderPublisher):
    """DXF file reader that publishes weld paths."""

    def __init__(self, dot_spacing: float = 2.0):
        super().__init__()
        if not DXF_AVAILABLE:
            raise ImportError(
                "ezdxf library is required for DXF reading. Install with: pip install ezdxf"
            )
        self.dot_spacing = dot_spacing  # Distance between points in mm

    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return [".dxf", ".DXF"]

    def can_read_file(self, file_path: Path) -> bool:
        """Check if this reader can handle the given file."""
        return file_path.suffix.lower() in self.get_supported_extensions()

    @handle_errors(
        error_types={
            **(
                {
                    ezdxf.DXFError: ParsingError,
                    ezdxf.DXFStructureError: ParsingError,
                }
                if DXF_AVAILABLE
                else {}
            ),
            ValueError: ParsingError,
        },
        default_error=FileProcessingError,
    )
    def _parse_file_internal(self, file_path: Path) -> List[WeldPath]:
        """Parse DXF file and extract weld paths."""
        logger.info(f"Parsing DXF file: {file_path}")

        # Store filename for weld type detection
        self._current_filename = file_path.stem

        try:
            # Load DXF document
            doc = ezdxf.readfile(str(file_path))

            # Validate units
            self._validate_units(doc)

            # Get model space
            msp = doc.modelspace()

            # Parse entities
            entities = self._parse_entities(msp)

            # Convert to weld paths
            weld_paths = self._entities_to_weld_paths(entities)

            logger.info(
                f"Parsed {len(weld_paths)} weld paths from {len(entities)} entities"
            )
            return weld_paths

        except ezdxf.DXFError as e:
            raise ParsingError(f"DXF parsing error: {e}")
        except Exception as e:
            raise FileProcessingError(f"Failed to parse DXF file {file_path}: {e}")

    def _validate_units(self, doc: "ezdxf.document.Drawing") -> None:
        """Validate that DXF units are in millimeters."""
        header = doc.header

        # Check INSUNITS (insertion units)
        insunits = header.get("$INSUNITS", 0)

        # INSUNITS values: 0=Unitless, 1=Inches, 2=Feet, 4=Millimeters, 5=Centimeters, 6=Meters
        if insunits == 4:
            logger.debug("DXF units confirmed as millimeters")
            return
        elif insunits == 0:
            logger.warning("DXF units are unitless - assuming millimeters")
            return
        else:
            unit_names = {1: "inches", 2: "feet", 5: "centimeters", 6: "meters"}
            unit_name = unit_names.get(insunits, f"unknown ({insunits})")
            raise ParsingError(
                f"DXF file must use millimeter units, but found {unit_name}. "
                f"Please convert your DXF file to use millimeter units."
            )

    def _parse_entities(self, msp) -> List[CADEntity]:
        """Parse entities from model space."""
        entities = []

        for entity in msp:
            try:
                parsed_entity = self._parse_entity(entity)
                if parsed_entity:
                    # Handle both single entities and lists (from polylines)
                    if isinstance(parsed_entity, list):
                        entities.extend(parsed_entity)
                    else:
                        entities.append(parsed_entity)
            except Exception as e:
                logger.warning(f"Failed to parse entity {entity.dxftype()}: {e}")
                continue

        return entities

    def _parse_entity(self, entity):
        """Parse a single DXF entity."""
        entity_type = entity.dxftype()
        layer = entity.dxf.layer or "0"

        if entity_type == DXFEntities.LINE:
            return self._parse_line(entity, layer)
        elif entity_type == DXFEntities.ARC:
            return self._parse_arc(entity, layer)
        elif entity_type == DXFEntities.CIRCLE:
            return self._parse_circle(entity, layer)
        elif entity_type in [DXFEntities.POLYLINE, DXFEntities.LWPOLYLINE]:
            # For polylines, we'll handle them directly in _entities_to_weld_paths to avoid duplicate points
            # Return a special marker that indicates this is a polyline to be processed later
            return {"type": "polyline", "entity": entity, "layer": layer}
        else:
            logger.debug(f"Unsupported entity type: {entity_type}")
            return None

    def _parse_line(self, entity, layer: str) -> LineEntity:
        """Parse a LINE entity."""
        start_point = entity.dxf.start
        end_point = entity.dxf.end

        return LineEntity(
            layer=layer,
            start=Point(start_point.x, start_point.y),
            end=Point(end_point.x, end_point.y),
        )

    def _parse_arc(self, entity, layer: str) -> ArcEntity:
        """Parse an ARC entity."""
        center = entity.dxf.center
        radius = entity.dxf.radius
        start_angle = entity.dxf.start_angle
        end_angle = entity.dxf.end_angle

        return ArcEntity(
            layer=layer,
            center=Point(center.x, center.y),
            radius=radius,
            start_angle=start_angle,
            end_angle=end_angle,
        )

    def _parse_circle(self, entity, layer: str) -> CircleEntity:
        """Parse a CIRCLE entity."""
        center = entity.dxf.center
        radius = entity.dxf.radius

        return CircleEntity(
            layer=layer,
            center=Point(center.x, center.y),
            radius=radius,
        )

    def _parse_polyline(self, entity, layer: str) -> List[LineEntity]:
        """Parse POLYLINE/LWPOLYLINE entities as connected line segments with proper arc support.

        DEPRECATED: This method creates overlapping endpoints. Use _parse_polyline_to_weld_path instead.
        """
        import math

        line_entities = []
        points = []
        bulges = []

        if entity.dxftype() == DXFEntities.POLYLINE:
            # POLYLINE - extract points and bulges
            for vertex in entity.vertices():
                if hasattr(vertex.dxf, "location"):
                    loc = vertex.dxf.location
                    points.append(Point(loc.x, loc.y))
                    bulges.append(getattr(vertex.dxf, "bulge", 0.0))
        else:
            # LWPOLYLINE - extract points and bulges
            for point in entity.lwpoints:
                points.append(Point(point[0], point[1]))
                # LWPOLYLINE format: [x, y, start_width, end_width, bulge]
                bulges.append(point[4] if len(point) > 4 else 0.0)

        if len(points) < 2:
            return []

        # Check if polyline is closed
        is_closed = hasattr(entity.dxf, "flags") and (entity.dxf.flags & 1)

        # Process each segment
        num_segments = len(points) if is_closed else len(points) - 1

        for i in range(num_segments):
            start_point = points[i]
            end_point = points[
                (i + 1) % len(points)
            ]  # Wrap around for closed polylines
            bulge = bulges[i]

            if abs(bulge) < 1e-10:  # Straight line segment
                line_entities.append(
                    LineEntity(
                        layer=layer,
                        start=start_point,
                        end=end_point,
                    )
                )
            else:  # Arc segment - convert to multiple line segments
                arc_segments = self._bulge_to_line_segments(
                    start_point, end_point, bulge
                )
                line_entities.extend(
                    [
                        LineEntity(layer=layer, start=seg[0], end=seg[1])
                        for seg in arc_segments
                    ]
                )

        return line_entities

    def _parse_polyline_to_weld_path(
        self, entity, layer: str, weld_type: WeldType
    ) -> Optional[DataWeldPath]:
        """Parse POLYLINE/LWPOLYLINE entities directly to weld path with continuous points.

        This method generates points directly without creating intermediate LineEntity objects,
        avoiding duplicate points at segment boundaries.
        """
        import math

        points = []
        bulges = []

        if entity.dxftype() == DXFEntities.POLYLINE:
            # POLYLINE - extract points and bulges
            for vertex in entity.vertices():
                if hasattr(vertex.dxf, "location"):
                    loc = vertex.dxf.location
                    points.append(Point(loc.x, loc.y))
                    bulges.append(getattr(vertex.dxf, "bulge", 0.0))
        else:
            # LWPOLYLINE - extract points and bulges
            for point in entity.lwpoints:
                points.append(Point(point[0], point[1]))
                # LWPOLYLINE format: [x, y, start_width, end_width, bulge]
                bulges.append(point[4] if len(point) > 4 else 0.0)

        if len(points) < 2:
            return None

        # Check if polyline is closed
        is_closed = hasattr(entity.dxf, "flags") and (entity.dxf.flags & 1)

        # Generate continuous weld points
        weld_points = []

        # Always add the first point
        weld_points.append(points[0])

        # Process each segment
        num_segments = len(points) if is_closed else len(points) - 1

        for i in range(num_segments):
            start_point = points[i]
            end_point = points[
                (i + 1) % len(points)
            ]  # Wrap around for closed polylines
            bulge = bulges[i]

            if abs(bulge) < 1e-10:  # Straight line segment
                # Interpolate points along the line (excluding start point to avoid duplicates)
                segment_length = start_point.distance_to(end_point)
                if segment_length > self.dot_spacing:
                    num_points = int(segment_length / self.dot_spacing)
                    for j in range(1, num_points + 1):
                        t = j / num_points
                        x = start_point.x + t * (end_point.x - start_point.x)
                        y = start_point.y + t * (end_point.y - start_point.y)
                        weld_points.append(Point(x, y))
                else:
                    # Short segment - just add the end point
                    weld_points.append(end_point)
            else:  # Arc segment
                # Generate points directly along the arc
                arc_points = self._bulge_to_weld_points(start_point, end_point, bulge)
                # Add arc points (excluding start point to avoid duplicates)
                weld_points.extend(arc_points[1:])

        # Close the path if needed
        if is_closed and len(weld_points) > 1:
            # Only close if we're not already at the start point
            first_point = weld_points[0]
            last_point = weld_points[-1]
            if first_point.distance_to(last_point) > 1e-6:
                weld_points.append(first_point)

        return DataWeldPath(weld_points, weld_type, layer)

    def _bulge_to_line_segments(
        self, start: Point, end: Point, bulge: float
    ) -> List[tuple]:
        """Convert a bulge arc to multiple line segments.

        DXF Bulge specification (Autodesk DXF Reference):
        - Bulge = tan(included_angle / 4)
        - Positive bulge: Counter-clockwise arc
        - Negative bulge: Clockwise arc
        - Bulge of 1 = semicircle (180°)
        """
        import math

        # Calculate chord length
        chord_length = start.distance_to(end)
        if chord_length < 1e-10:  # Degenerate case
            return [(start, end)]

        # Calculate the included angle from bulge
        included_angle = 4 * math.atan(bulge)

        # If angle is too small, treat as straight line
        if abs(included_angle) < 1e-10:
            return [(start, end)]

        # Calculate radius using: R = chord_length / (2 * sin(|included_angle|/2))
        # Use absolute value to ensure positive radius
        half_angle = abs(included_angle) / 2
        if abs(math.sin(half_angle)) < 1e-10:
            return [(start, end)]

        radius = chord_length / (2 * math.sin(half_angle))

        # Calculate arc length and determine segments based on dot spacing
        arc_length = radius * abs(included_angle)
        segments = max(2, int(arc_length / self.dot_spacing))

        # Calculate chord midpoint
        chord_mid_x = (start.x + end.x) / 2
        chord_mid_y = (start.y + end.y) / 2

        # Calculate the distance from chord midpoint to arc center
        # This is the "height" of the arc segment
        h = radius * math.cos(half_angle)

        # Unit vector along chord (start to end)
        chord_dx = (end.x - start.x) / chord_length
        chord_dy = (end.y - start.y) / chord_length

        # Unit vector perpendicular to chord (90° counter-clockwise)
        perp_dx = -chord_dy
        perp_dy = chord_dx

        # For positive bulge (counter-clockwise), center is on the left side of chord
        # For negative bulge (clockwise), center is on the right side of chord
        if bulge < 0:
            perp_dx = -perp_dx
            perp_dy = -perp_dy

        # Calculate arc center
        center_x = chord_mid_x + h * perp_dx
        center_y = chord_mid_y + h * perp_dy

        # Calculate start and end angles
        start_angle = math.atan2(start.y - center_y, start.x - center_x)
        end_angle = math.atan2(end.y - center_y, end.x - center_x)

        # Calculate sweep angle - use the included_angle directly
        # The DXF bulge already encodes the correct direction and magnitude
        sweep_angle = included_angle

        # Adjust the end_angle to match the intended sweep
        end_angle = start_angle + sweep_angle

        # Generate line segments along the arc
        line_segments = []
        for i in range(segments):
            t1 = i / segments
            t2 = (i + 1) / segments

            if i == 0:
                # First segment: start with exact start point
                p1 = start
            else:
                angle1 = start_angle + t1 * sweep_angle
                x1 = center_x + radius * math.cos(angle1)
                y1 = center_y + radius * math.sin(angle1)
                p1 = Point(x1, y1)

            if i == segments - 1:
                # Last segment: end with exact end point
                p2 = end
            else:
                angle2 = start_angle + t2 * sweep_angle
                x2 = center_x + radius * math.cos(angle2)
                y2 = center_y + radius * math.sin(angle2)
                p2 = Point(x2, y2)

            line_segments.append((p1, p2))

        return line_segments

    def _bulge_to_weld_points(
        self, start: Point, end: Point, bulge: float
    ) -> List[Point]:
        """Convert a bulge arc directly to weld points.

        This method generates points directly along the arc without creating intermediate
        line segments, avoiding duplicate points at segment boundaries.
        """
        import math

        # Calculate chord length
        chord_length = start.distance_to(end)
        if chord_length < 1e-10:  # Degenerate case
            return [start, end]

        # Calculate the included angle from bulge
        included_angle = 4 * math.atan(bulge)

        # If angle is too small, treat as straight line
        if abs(included_angle) < 1e-10:
            return [start, end]

        # Calculate radius using: R = chord_length / (2 * sin(|included_angle|/2))
        half_angle = abs(included_angle) / 2
        if abs(math.sin(half_angle)) < 1e-10:
            return [start, end]

        radius = chord_length / (2 * math.sin(half_angle))

        # Calculate arc length and determine number of points based on dot spacing
        arc_length = radius * abs(included_angle)
        num_points = max(2, int(arc_length / self.dot_spacing) + 1)

        # Calculate chord midpoint
        chord_mid_x = (start.x + end.x) / 2
        chord_mid_y = (start.y + end.y) / 2

        # Calculate the distance from chord midpoint to arc center
        h = radius * math.cos(half_angle)

        # Unit vector along chord (start to end)
        chord_dx = (end.x - start.x) / chord_length
        chord_dy = (end.y - start.y) / chord_length

        # Unit vector perpendicular to chord (90° counter-clockwise)
        perp_dx = -chord_dy
        perp_dy = chord_dx

        # For positive bulge (counter-clockwise), center is on the left side of chord
        # For negative bulge (clockwise), center is on the right side of chord
        if bulge < 0:
            perp_dx = -perp_dx
            perp_dy = -perp_dy

        # Calculate arc center
        center_x = chord_mid_x + h * perp_dx
        center_y = chord_mid_y + h * perp_dy

        # Calculate start and end angles
        start_angle = math.atan2(start.y - center_y, start.x - center_x)
        sweep_angle = included_angle

        # Generate points along the arc
        weld_points = []
        for i in range(num_points):
            t = i / (num_points - 1) if num_points > 1 else 0

            if i == 0:
                # First point: use exact start point
                weld_points.append(start)
            elif i == num_points - 1:
                # Last point: use exact end point
                weld_points.append(end)
            else:
                # Intermediate points: calculate along arc
                angle = start_angle + t * sweep_angle
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                weld_points.append(Point(x, y))

        return weld_points

    def _entities_to_weld_paths(self, entities: List[CADEntity]) -> List[WeldPath]:
        """Convert CAD entities to weld paths."""
        weld_paths = []
        entity_counter = 0  # Add unique counter for each entity

        for entity in entities:
            # Handle polyline markers (dict objects)
            if isinstance(entity, dict) and entity.get("type") == "polyline":
                # Process polyline directly to avoid duplicate points
                layer = entity["layer"]
                polyline_entity = entity["entity"]

                # Skip construction entities
                construction_patterns = [
                    "construction",
                    "const",
                    "guide",
                    "reference",
                    "ref",
                ]
                if any(pattern in layer.lower() for pattern in construction_patterns):
                    logger.debug(f"Skipping construction polyline on layer: {layer}")
                    continue

                # Determine weld type based on layer name
                weld_type = self._determine_weld_type(layer)

                try:
                    # Use direct polyline-to-weld-path conversion
                    data_path = self._parse_polyline_to_weld_path(
                        polyline_entity, layer, weld_type
                    )
                    if data_path:
                        # Convert data_models.WeldPath to models.WeldPath
                        path = self._convert_to_models_weld_path(
                            data_path, layer, entity_counter
                        )
                        weld_paths.append(path)
                        entity_counter += 1
                        logger.debug(
                            f"Converted polyline on layer '{layer}' to {weld_type.value} weld path with {len(data_path.points)} points"
                        )
                except Exception as e:
                    logger.error(f"Failed to convert polyline to weld path: {e}")
                continue

            # Skip construction entities
            if entity.is_construction:
                logger.debug(f"Skipping construction entity on layer: {entity.layer}")
                continue

            # Determine weld type based on layer name
            weld_type = self._determine_weld_type(entity.layer)

            try:
                if isinstance(entity, LineEntity):
                    data_path = entity.to_weld_path(
                        weld_type, dot_spacing=self.dot_spacing
                    )
                elif isinstance(entity, ArcEntity):
                    # Calculate arc length and determine segments based on dot spacing
                    arc_length = (
                        abs(entity.end_angle - entity.start_angle)
                        * math.pi
                        / 180
                        * entity.radius
                    )
                    segments = max(2, int(arc_length / self.dot_spacing))
                    logger.debug(
                        f"Processing arc: center={entity.center}, radius={entity.radius}, angles={entity.start_angle}-{entity.end_angle}, length={arc_length:.1f}mm, segments={segments}"
                    )
                    data_path = entity.to_weld_path(
                        segments=segments, weld_type=weld_type
                    )
                    logger.debug(f"Arc converted to {len(data_path.points)} points")
                elif isinstance(entity, CircleEntity):
                    # Calculate circle circumference and determine segments based on dot spacing
                    circumference = 2 * math.pi * entity.radius
                    segments = max(3, int(circumference / self.dot_spacing))
                    logger.debug(
                        f"Processing circle: radius={entity.radius}, circumference={circumference:.1f}mm, segments={segments}"
                    )
                    data_path = entity.to_weld_path(
                        segments=segments, weld_type=weld_type
                    )
                else:
                    logger.warning(f"Unknown entity type: {type(entity)}")
                    continue

                # Convert data_models.WeldPath to models.WeldPath
                path = self._convert_to_models_weld_path(
                    data_path, entity.layer, entity_counter
                )
                weld_paths.append(path)
                entity_counter += 1  # Increment counter for next entity
                logger.debug(
                    f"Converted {entity.entity_type} on layer '{entity.layer}' to {weld_type.value} weld path"
                )

            except Exception as e:
                logger.error(
                    f"Failed to convert entity {entity.entity_type} to weld path: {e}"
                )
                continue

        return weld_paths

    def _convert_to_models_weld_path(
        self, data_path: DataWeldPath, layer_name: str, entity_id: int
    ) -> WeldPath:
        """Convert data_models.WeldPath to models.WeldPath for event system compatibility."""
        # Convert Point objects to WeldPoint objects
        weld_points = []
        for point in data_path.points:
            weld_point = WeldPoint(
                x=point.x,
                y=point.y,
                weld_type=data_path.weld_type.value,  # Convert enum to string
            )
            weld_points.append(weld_point)

        # Create models.WeldPath with unique svg_id
        return WeldPath(
            points=weld_points,
            weld_type=data_path.weld_type.value,  # Convert enum to string
            svg_id=f"dxf_entity_{entity_id}_{layer_name}_{len(weld_points)}pts",  # Generate unique svg_id
        )

    def _determine_weld_type(self, layer_name: str) -> WeldType:
        """Determine weld type based on layer name and filename."""
        layer_lower = layer_name.lower()

        # First check layer name for frangible indicators
        frangible_keywords = ["frangible", "light", "break", "seal", "weak"]
        if any(keyword in layer_lower for keyword in frangible_keywords):
            return WeldType.FRANGIBLE

        # Fallback: Check filename for frangible indicators
        if hasattr(self, "_current_filename") and self._current_filename:
            filename_lower = self._current_filename.lower()
            if any(keyword in filename_lower for keyword in frangible_keywords):
                return WeldType.FRANGIBLE

        # Default to normal welds
        return WeldType.NORMAL

    def get_layer_info(self, file_path: Path) -> Dict[str, Any]:
        """Get information about layers in the DXF file."""
        if not DXF_AVAILABLE:
            return {}

        try:
            doc = ezdxf.readfile(str(file_path))
            layer_info = {}

            for layer in doc.layers:
                layer_name = layer.dxf.name
                layer_info[layer_name] = {
                    "color": layer.dxf.color,
                    "linetype": layer.dxf.linetype,
                    "is_construction": any(
                        pattern in layer_name.lower()
                        for pattern in [
                            "construction",
                            "const",
                            "guide",
                            "reference",
                            "ref",
                        ]
                    ),
                }

            return layer_info

        except Exception as e:
            logger.error(f"Failed to get layer info from {file_path}: {e}")
            return {}


# Factory function for easy instantiation
def create_dxf_reader() -> Optional[DXFReader]:
    """Create a DXF reader if ezdxf is available."""
    try:
        return DXFReader()
    except ImportError as e:
        logger.warning(f"Cannot create DXF reader: {e}")
        return None
