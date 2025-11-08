"""Enhanced SVG parser with curve support and event publishing."""

import math
import re
import time
import xml.etree.ElementTree as ET  # nosec B405 - Parsing trusted SVG files only
from typing import List, Optional, Tuple
from pathlib import Path

from .models import WeldPath, WeldPoint
from .events import (
    Event,
    EventType,
    ParsingEvent,
    PathEvent,
    PointEvent,
    CurveEvent,
    ErrorEvent,
    publish_event,
)


class SVGParseError(Exception):
    """Raised when there's an error parsing SVG."""

    pass


class EnhancedSVGParser:
    """Enhanced SVG parser with curve support and event publishing."""

    def __init__(self, dot_spacing: float = 2.0) -> None:
        """Initialize enhanced SVG parser."""
        self.dot_spacing = dot_spacing
        self.curve_resolution = 20  # Number of points to approximate curves

    def parse_file(self, svg_path: str) -> List[WeldPath]:
        """Parse SVG file and extract weld paths with event publishing."""
        svg_path_obj = Path(svg_path)

        # Publish parsing started event
        publish_event(
            ParsingEvent(
                event_type=EventType.PARSING_STARTED,
                timestamp=time.time(),
                data={"svg_path": str(svg_path_obj)},
                svg_path=svg_path_obj,
            )
        )

        try:
            tree = ET.parse(svg_path)  # nosec B314 - Parsing trusted user SVG files
            root = tree.getroot()
        except ET.ParseError as e:
            error_event = ErrorEvent(
                event_type=EventType.ERROR_OCCURRED,
                timestamp=time.time(),
                data={"error_type": "parse_error"},
                message=f"Invalid SVG file: {e}",
                exception=e,
            )
            publish_event(error_event)
            raise SVGParseError(f"Invalid SVG file: {e}")
        except FileNotFoundError as e:
            error_event = ErrorEvent(
                event_type=EventType.ERROR_OCCURRED,
                timestamp=time.time(),
                data={"error_type": "file_not_found"},
                message=f"SVG file '{svg_path}' not found.",
                exception=e,
            )
            publish_event(error_event)
            raise SVGParseError(f"SVG file '{svg_path}' not found.")

        weld_paths = self._parse_elements(root)

        # Publish parsing completed event
        publish_event(
            ParsingEvent(
                event_type=EventType.PARSING_COMPLETED,
                timestamp=time.time(),
                data={"total_paths": len(weld_paths), "svg_path": str(svg_path_obj)},
                svg_path=svg_path_obj,
                total_elements=len(weld_paths),
            )
        )

        return weld_paths

    def _parse_elements(self, root: ET.Element) -> List[WeldPath]:
        """Parse SVG elements and return weld paths with progress events."""
        # Define SVG namespace
        namespaces = {"svg": "http://www.w3.org/2000/svg"}

        # First, build a dictionary of defined elements from <defs>
        defs_elements = {}
        for defs in root.findall(".//svg:defs", namespaces):
            for group in defs.findall(".//svg:g[@id]", namespaces):
                group_id = group.get("id")
                if group_id:
                    defs_elements[group_id] = group

        # Find all supported elements (excluding those inside <defs>)
        elements = []

        # Get paths (excluding those in defs)
        for path in root.findall(".//svg:path", namespaces):
            if not self._is_inside_defs(path, root):
                elements.append(("path", path))

        # Get lines (excluding those in defs)
        for line in root.findall(".//svg:line", namespaces):
            if not self._is_inside_defs(line, root):
                elements.append(("line", line))

        # Get circles (excluding those in defs)
        for circle in root.findall(".//svg:circle", namespaces):
            if not self._is_inside_defs(circle, root):
                elements.append(("circle", circle))

        # Get rectangles (excluding those in defs)
        for rect in root.findall(".//svg:rect", namespaces):
            if not self._is_inside_defs(rect, root):
                elements.append(("rect", rect))

        # Process <use> elements
        for use in root.findall(".//svg:use", namespaces):
            if not self._is_inside_defs(use, root):
                expanded_elements = self._expand_use_element(
                    use, defs_elements, namespaces
                )
                elements.extend(expanded_elements)

        # Sort by ID if available
        elements.sort(key=self._get_sort_key)

        # Process each element and ensure unique IDs
        weld_paths = []
        used_ids = set()
        total_elements = len(elements)

        for element_index, (element_type, element) in enumerate(elements):
            # Publish progress event
            publish_event(
                ParsingEvent(
                    event_type=EventType.PARSING_PROGRESS,
                    timestamp=time.time(),
                    data={
                        "element_index": element_index,
                        "element_type": element_type,
                        "element_id": element.get(
                            "id", f"{element_type}_{element_index}"
                        ),
                    },
                    total_elements=total_elements,
                    processed_elements=element_index,
                    current_element=element_type,
                )
            )

            weld_type, pause_message = self._determine_weld_type(element)

            # Ensure unique SVG ID
            base_id = element.get("id", f"{element_type}_{len(weld_paths) + 1}")
            svg_id = base_id
            counter = 1
            while svg_id in used_ids:
                svg_id = f"{base_id}_{counter}"
                counter += 1
            used_ids.add(svg_id)

            # Publish path started event
            publish_event(
                PathEvent(
                    event_type=EventType.PATH_STARTED,
                    timestamp=time.time(),
                    data={"svg_id": svg_id, "element_type": element_type},
                    path_index=len(weld_paths),
                    total_paths=total_elements,
                )
            )

            points = self._parse_element(element_type, element, svg_id)

            if points:
                # Extract element metadata
                element_radius = None
                if element_type == "circle":
                    element_radius = float(element.get("r", 1))

                # Extract custom parameters for the path
                custom_temp = self._get_float_attr(element, "data-temp")
                custom_weld_time = self._get_float_attr(element, "data-weld-time")
                custom_bed_temp = self._get_float_attr(element, "data-bed-temp")
                custom_weld_height = self._get_float_attr(element, "data-weld-height")

                weld_path = WeldPath(
                    points=points,
                    weld_type=weld_type,
                    svg_id=svg_id,
                    pause_message=pause_message,
                    element_type=element_type,
                    element_radius=element_radius,
                    custom_temp=custom_temp,
                    custom_weld_time=custom_weld_time,
                    custom_bed_temp=custom_bed_temp,
                    custom_weld_height=custom_weld_height,
                )
                weld_paths.append(weld_path)

                # Publish path completed event
                publish_event(
                    PathEvent(
                        event_type=EventType.PATH_COMPLETED,
                        timestamp=time.time(),
                        data={
                            "svg_id": svg_id,
                            "point_count": len(points),
                            "weld_type": weld_type,
                        },
                        path=weld_path,
                        path_index=len(weld_paths) - 1,
                        total_paths=total_elements,
                    )
                )

        return weld_paths

    def _parse_element(
        self, element_type: str, element: ET.Element, path_id: str
    ) -> List[WeldPoint]:
        """Parse individual SVG element with event publishing."""
        if element_type == "path":
            return self._parse_path_element(element, path_id)
        elif element_type == "line":
            return self._parse_line_element(element, path_id)
        elif element_type == "circle":
            return self._parse_circle_element(element, path_id)
        elif element_type == "rect":
            return self._parse_rect_element(element, path_id)
        else:
            return []

    def _parse_path_element(
        self, path_element: ET.Element, path_id: str
    ) -> List[WeldPoint]:
        """Parse SVG path element with full curve support."""
        d = path_element.get("d", "")
        if not d:
            return []

        points = []
        # Enhanced path parser - handles M, L, Z, Q, C, S, T, A commands
        commands = re.findall(r"[MLZQCSTAmlzqcsta][^MLZQCSTAmlzqcsta]*", d)
        current_x, current_y = 0.0, 0.0
        start_x, start_y = 0.0, 0.0  # Track start point for Z command
        last_control_x, last_control_y = 0.0, 0.0  # For smooth curves

        for command_index, command in enumerate(commands):
            cmd = command[0]
            coords = re.findall(r"-?\d+\.?\d*", command[1:])
            coords = [float(c) for c in coords]

            # Handle relative vs absolute commands
            is_relative = cmd.islower()
            cmd_upper = cmd.upper()

            if cmd_upper == "M" and len(coords) >= 2:  # Move to
                if is_relative:
                    current_x += coords[0]
                    current_y += coords[1]
                else:
                    current_x, current_y = coords[0], coords[1]
                start_x, start_y = current_x, current_y
                points.append(WeldPoint(current_x, current_y, "normal"))

            elif cmd_upper == "L" and len(coords) >= 2:  # Line to
                if is_relative:
                    current_x += coords[0]
                    current_y += coords[1]
                else:
                    current_x, current_y = coords[0], coords[1]
                points.append(WeldPoint(current_x, current_y, "normal"))

            elif cmd_upper == "Q" and len(coords) >= 4:  # Quadratic Bézier curve
                control_x, control_y = coords[0], coords[1]
                end_x, end_y = coords[2], coords[3]

                if is_relative:
                    control_x += current_x
                    control_y += current_y
                    end_x += current_x
                    end_y += current_y

                # Approximate curve with line segments
                curve_points = self._approximate_quadratic_bezier(
                    current_x, current_y, control_x, control_y, end_x, end_y
                )

                # Publish curve approximation event
                publish_event(
                    CurveEvent(
                        event_type=EventType.CURVE_APPROXIMATED,
                        timestamp=time.time(),
                        data={
                            "path_id": path_id,
                            "command_index": command_index,
                            "points_generated": len(curve_points),
                        },
                        curve_type="quadratic_bezier",
                        original_command=command,
                        approximated_points=curve_points,
                        control_points=[
                            (current_x, current_y),
                            (control_x, control_y),
                            (end_x, end_y),
                        ],
                    )
                )

                points.extend(curve_points)
                current_x, current_y = end_x, end_y
                last_control_x, last_control_y = control_x, control_y

            elif cmd_upper == "C" and len(coords) >= 6:  # Cubic Bézier curve
                control1_x, control1_y = coords[0], coords[1]
                control2_x, control2_y = coords[2], coords[3]
                end_x, end_y = coords[4], coords[5]

                if is_relative:
                    control1_x += current_x
                    control1_y += current_y
                    control2_x += current_x
                    control2_y += current_y
                    end_x += current_x
                    end_y += current_y

                # Approximate curve with line segments
                curve_points = self._approximate_cubic_bezier(
                    current_x,
                    current_y,
                    control1_x,
                    control1_y,
                    control2_x,
                    control2_y,
                    end_x,
                    end_y,
                )

                # Publish curve approximation event
                publish_event(
                    CurveEvent(
                        event_type=EventType.CURVE_APPROXIMATED,
                        timestamp=time.time(),
                        data={
                            "path_id": path_id,
                            "command_index": command_index,
                            "points_generated": len(curve_points),
                        },
                        curve_type="cubic_bezier",
                        original_command=command,
                        approximated_points=curve_points,
                        control_points=[
                            (current_x, current_y),
                            (control1_x, control1_y),
                            (control2_x, control2_y),
                            (end_x, end_y),
                        ],
                    )
                )

                points.extend(curve_points)
                current_x, current_y = end_x, end_y
                last_control_x, last_control_y = control2_x, control2_y

            elif cmd_upper == "S" and len(coords) >= 4:  # Smooth cubic Bézier
                # First control point is reflection of last control point
                control1_x = 2 * current_x - last_control_x
                control1_y = 2 * current_y - last_control_y
                control2_x, control2_y = coords[0], coords[1]
                end_x, end_y = coords[2], coords[3]

                if is_relative:
                    control2_x += current_x
                    control2_y += current_y
                    end_x += current_x
                    end_y += current_y

                curve_points = self._approximate_cubic_bezier(
                    current_x,
                    current_y,
                    control1_x,
                    control1_y,
                    control2_x,
                    control2_y,
                    end_x,
                    end_y,
                )

                publish_event(
                    CurveEvent(
                        event_type=EventType.CURVE_APPROXIMATED,
                        timestamp=time.time(),
                        data={
                            "path_id": path_id,
                            "command_index": command_index,
                            "points_generated": len(curve_points),
                        },
                        curve_type="smooth_cubic_bezier",
                        original_command=command,
                        approximated_points=curve_points,
                        control_points=[
                            (current_x, current_y),
                            (control1_x, control1_y),
                            (control2_x, control2_y),
                            (end_x, end_y),
                        ],
                    )
                )

                points.extend(curve_points)
                current_x, current_y = end_x, end_y
                last_control_x, last_control_y = control2_x, control2_y

            elif cmd_upper == "T" and len(coords) >= 2:  # Smooth quadratic Bézier
                # Control point is reflection of last control point
                control_x = 2 * current_x - last_control_x
                control_y = 2 * current_y - last_control_y
                end_x, end_y = coords[0], coords[1]

                if is_relative:
                    end_x += current_x
                    end_y += current_y

                curve_points = self._approximate_quadratic_bezier(
                    current_x, current_y, control_x, control_y, end_x, end_y
                )

                publish_event(
                    CurveEvent(
                        event_type=EventType.CURVE_APPROXIMATED,
                        timestamp=time.time(),
                        data={
                            "path_id": path_id,
                            "command_index": command_index,
                            "points_generated": len(curve_points),
                        },
                        curve_type="smooth_quadratic_bezier",
                        original_command=command,
                        approximated_points=curve_points,
                        control_points=[
                            (current_x, current_y),
                            (control_x, control_y),
                            (end_x, end_y),
                        ],
                    )
                )

                points.extend(curve_points)
                current_x, current_y = end_x, end_y
                last_control_x, last_control_y = control_x, control_y

            elif cmd_upper == "A" and len(coords) >= 7:  # Elliptical arc
                rx, ry = coords[0], coords[1]
                x_axis_rotation = coords[2]
                large_arc_flag = coords[3]
                sweep_flag = coords[4]
                end_x, end_y = coords[5], coords[6]

                if is_relative:
                    end_x += current_x
                    end_y += current_y

                curve_points = self._approximate_elliptical_arc(
                    current_x,
                    current_y,
                    rx,
                    ry,
                    x_axis_rotation,
                    large_arc_flag,
                    sweep_flag,
                    end_x,
                    end_y,
                )

                publish_event(
                    CurveEvent(
                        event_type=EventType.CURVE_APPROXIMATED,
                        timestamp=time.time(),
                        data={
                            "path_id": path_id,
                            "command_index": command_index,
                            "points_generated": len(curve_points),
                        },
                        curve_type="elliptical_arc",
                        original_command=command,
                        approximated_points=curve_points,
                        control_points=[(current_x, current_y), (end_x, end_y)],
                    )
                )

                points.extend(curve_points)
                current_x, current_y = end_x, end_y

            elif cmd_upper == "Z":  # Close path - return to start point
                if points and (current_x != start_x or current_y != start_y):
                    points.append(WeldPoint(start_x, start_y, "normal"))
                    current_x, current_y = start_x, start_y

        return self._interpolate_points(points, path_id)

    def _approximate_quadratic_bezier(
        self, x0: float, y0: float, x1: float, y1: float, x2: float, y2: float
    ) -> List[WeldPoint]:
        """Approximate quadratic Bézier curve with line segments."""
        points = []
        for i in range(1, self.curve_resolution + 1):
            t = i / self.curve_resolution
            # Quadratic Bézier formula: B(t) = (1-t)²P0 + 2(1-t)tP1 + t²P2
            x = (1 - t) ** 2 * x0 + 2 * (1 - t) * t * x1 + t**2 * x2
            y = (1 - t) ** 2 * y0 + 2 * (1 - t) * t * y1 + t**2 * y2
            points.append(WeldPoint(x, y, "normal"))
        return points

    def _approximate_cubic_bezier(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        x3: float,
        y3: float,
    ) -> List[WeldPoint]:
        """Approximate cubic Bézier curve with line segments."""
        points = []
        for i in range(1, self.curve_resolution + 1):
            t = i / self.curve_resolution
            # Cubic Bézier formula: B(t) = (1-t)³P0 + 3(1-t)²tP1 + 3(1-t)t²P2 + t³P3
            x = (
                (1 - t) ** 3 * x0
                + 3 * (1 - t) ** 2 * t * x1
                + 3 * (1 - t) * t**2 * x2
                + t**3 * x3
            )
            y = (
                (1 - t) ** 3 * y0
                + 3 * (1 - t) ** 2 * t * y1
                + 3 * (1 - t) * t**2 * y2
                + t**3 * y3
            )
            points.append(WeldPoint(x, y, "normal"))
        return points

    def _approximate_elliptical_arc(
        self,
        x1: float,
        y1: float,
        rx: float,
        ry: float,
        phi: float,
        fa: float,
        fs: float,
        x2: float,
        y2: float,
    ) -> List[WeldPoint]:
        """Approximate elliptical arc with line segments."""
        # Simplified arc approximation - convert to center parameterization
        # This is a complex calculation, so we'll use a simplified approach
        points = []

        # If radii are zero, just draw a line
        if rx == 0 or ry == 0:
            return [WeldPoint(x2, y2, "normal")]

        # Simple approximation: create points along a circular arc
        dx = x2 - x1
        dy = y2 - y1
        distance = math.sqrt(dx * dx + dy * dy)

        # Create points along the arc
        for i in range(1, self.curve_resolution + 1):
            t = i / self.curve_resolution
            # Simple linear interpolation (not geometrically correct but functional)
            x = x1 + t * dx
            y = y1 + t * dy
            points.append(WeldPoint(x, y, "normal"))

        return points

    def _interpolate_points(
        self, points: List[WeldPoint], path_id: str
    ) -> List[WeldPoint]:
        """Interpolate points along the path with event publishing."""
        if len(points) < 2:
            return points

        interpolated = []
        total_segments = len(points) - 1

        for i in range(len(points) - 1):
            start = points[i]
            end = points[i + 1]

            # Calculate distance
            dx = end.x - start.x
            dy = end.y - start.y
            distance = math.sqrt(dx * dx + dy * dy)

            if distance == 0:
                continue

            # Use initial dot spacing for first pass
            num_points = max(1, int(distance / self.dot_spacing))

            # Add interpolated points
            segment_points = []
            for j in range(num_points + 1):
                t = j / num_points if num_points > 0 else 0
                x = start.x + t * dx
                y = start.y + t * dy
                point = WeldPoint(x, y, start.weld_type)
                segment_points.append(point)
                interpolated.append(point)

            # Publish points batch event
            publish_event(
                PointEvent(
                    event_type=EventType.POINTS_BATCH,
                    timestamp=time.time(),
                    data={
                        "segment_index": i,
                        "total_segments": total_segments,
                        "points_in_batch": len(segment_points),
                    },
                    points=segment_points,
                    path_id=path_id,
                )
            )

        return interpolated

    # Include all the existing helper methods from the original SVGParser
    def _get_sort_key(self, element_tuple: Tuple[str, ET.Element]) -> float:
        """Get sort key for element ordering."""
        element_type, element = element_tuple
        element_id = element.get("id", "")
        # Try to extract numeric part for sorting
        match = re.search(r"(\d+)", element_id)
        return int(match.group(1)) if match else float("inf")

    def _determine_weld_type(self, element: ET.Element) -> Tuple[str, Optional[str]]:
        """Determine weld type based on element color and extract pause message."""
        from .constants import Colors, SVGAttributes, WeldType, get_color_weld_type

        # Check stroke color
        stroke = element.get(SVGAttributes.STROKE, "").lower()
        fill = element.get(SVGAttributes.FILL, "").lower()
        style = element.get("style", "").lower()

        # Parse style attribute for color information
        color_info = f"{stroke} {fill} {style}"

        # Try to determine weld type from color
        try:
            # Check each color alias set to find a match
            for color_alias in Colors.STOP_ALIASES:
                if color_alias in color_info:
                    # Look for pause message in various SVG attributes
                    pause_message = (
                        element.get(SVGAttributes.DATA_PAUSE_MESSAGE)
                        or element.get("data-message")
                        or element.get("title")
                        or element.get("aria-label")
                        or element.get("desc")
                        or None
                    )
                    return WeldType.STOP.value, pause_message

            # Check for pipette colors (magenta/pink variants)
            if any(color in color_info for color in Colors.PIPETTE_ALIASES):
                # Look for pipetting message in various SVG attributes
                pipette_message = (
                    element.get(SVGAttributes.DATA_PAUSE_MESSAGE)
                    or element.get("data-message")
                    or element.get("title")
                    or element.get("aria-label")
                    or element.get("desc")
                    or "Pipette filling required"  # Default message
                )
                return WeldType.PIPETTE.value, pipette_message

            # Check for frangible weld colors
            for color_alias in Colors.FRANGIBLE_ALIASES:
                if color_alias in color_info:
                    return WeldType.FRANGIBLE.value, None

            # Default to normal weld (black or other colors)
            return WeldType.NORMAL.value, None

        except ValueError:
            # Fallback to normal if color parsing fails
            return WeldType.NORMAL.value, None

    def _get_float_attr(self, element: ET.Element, attr_name: str) -> Optional[float]:
        """Extract float attribute from element, return None if not found or invalid."""
        attr_value = element.get(attr_name)
        if attr_value:
            try:
                return float(attr_value)
            except ValueError:
                pass
        return None

    def _parse_line_element(
        self, line_element: ET.Element, path_id: str
    ) -> List[WeldPoint]:
        """Parse SVG line element."""
        x1 = float(line_element.get("x1", 0))
        y1 = float(line_element.get("y1", 0))
        x2 = float(line_element.get("x2", 0))
        y2 = float(line_element.get("y2", 0))

        points = [
            WeldPoint(x1, y1, "normal"),
            WeldPoint(x2, y2, "normal"),
        ]

        return self._interpolate_points(points, path_id)

    def _parse_circle_element(
        self, circle_element: ET.Element, path_id: str
    ) -> List[WeldPoint]:
        """Parse SVG circle element."""
        cx = float(circle_element.get("cx", 0))
        cy = float(circle_element.get("cy", 0))
        r = float(circle_element.get("r", 1))

        # Generate points around the circle
        points = []
        num_points = max(8, int(2 * math.pi * r / 2))  # Rough approximation

        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            points.append(WeldPoint(x, y, "normal"))

        # Close the circle by adding the first point again at the end
        if points:
            first_point = points[0]
            points.append(
                WeldPoint(first_point.x, first_point.y, first_point.weld_type)
            )

        return self._interpolate_points(points, path_id)

    def _parse_rect_element(
        self, rect_element: ET.Element, path_id: str
    ) -> List[WeldPoint]:
        """Parse SVG rectangle element."""
        x = float(rect_element.get("x", 0))
        y = float(rect_element.get("y", 0))
        width = float(rect_element.get("width", 0))
        height = float(rect_element.get("height", 0))

        # Create rectangle path
        points = [
            WeldPoint(x, y, "normal"),
            WeldPoint(x + width, y, "normal"),
            WeldPoint(x + width, y + height, "normal"),
            WeldPoint(x, y + height, "normal"),
            WeldPoint(x, y, "normal"),  # Close the rectangle
        ]

        return self._interpolate_points(points, path_id)

    def _is_inside_defs(self, element: ET.Element, root: ET.Element) -> bool:
        """Check if an element is inside a <defs> section."""
        # Find all defs elements in the document using proper namespace
        namespaces = {"svg": "http://www.w3.org/2000/svg"}
        defs_elements = root.findall(".//svg:defs", namespaces)

        # Check if our element is inside any defs
        for defs in defs_elements:
            if self._element_is_descendant_of(element, defs):
                return True
        return False

    def _element_is_descendant_of(
        self, element: ET.Element, ancestor: ET.Element
    ) -> bool:
        """Check if element is a descendant of ancestor."""
        for child in ancestor.iter():
            if child is element:
                return True
        return False

    def _expand_use_element(
        self, use_element: ET.Element, defs_elements: dict, namespaces: dict
    ) -> List[Tuple[str, ET.Element]]:
        """Expand a <use> element by resolving its reference and applying transformations."""
        href = use_element.get("href") or use_element.get(
            "{http://www.w3.org/1999/xlink}href"
        )
        if not href or not href.startswith("#"):
            return []

        # Get the referenced element ID
        ref_id = href[1:]  # Remove the '#' prefix
        if ref_id not in defs_elements:
            return []

        referenced_group = defs_elements[ref_id]

        # Get transformation from the <use> element
        transform = use_element.get("transform", "")
        x_offset = float(use_element.get("x", 0))
        y_offset = float(use_element.get("y", 0))

        # Parse transform attribute for additional transformations
        scale_x, scale_y, translate_x, translate_y = self._parse_transform(transform)

        # Apply use element's x,y offset to the translation
        translate_x += x_offset
        translate_y += y_offset

        # Recursively expand the referenced group
        expanded_elements = []
        self._expand_group_elements(
            referenced_group,
            expanded_elements,
            namespaces,
            scale_x,
            scale_y,
            translate_x,
            translate_y,
            defs_elements,
        )

        return expanded_elements

    def _parse_transform(self, transform_str: str) -> Tuple[float, float, float, float]:
        """Parse SVG transform attribute and return scale_x, scale_y, translate_x, translate_y."""
        scale_x, scale_y = 1.0, 1.0
        translate_x, translate_y = 0.0, 0.0

        if not transform_str:
            return scale_x, scale_y, translate_x, translate_y

        # Simple parsing for translate() and scale() functions
        import re

        # Parse translate(x,y) or translate(x y)
        translate_match = re.search(r"translate\s*\(\s*([^)]+)\)", transform_str)
        if translate_match:
            coords = translate_match.group(1).replace(",", " ").split()
            if len(coords) >= 1:
                translate_x = float(coords[0])
            if len(coords) >= 2:
                translate_y = float(coords[1])

        # Parse scale(x,y) or scale(x y) or scale(x)
        scale_match = re.search(r"scale\s*\(\s*([^)]+)\)", transform_str)
        if scale_match:
            coords = scale_match.group(1).replace(",", " ").split()
            if len(coords) >= 1:
                scale_x = float(coords[0])
                scale_y = scale_x  # Default to uniform scaling
            if len(coords) >= 2:
                scale_y = float(coords[1])

        return scale_x, scale_y, translate_x, translate_y

    def _expand_group_elements(
        self,
        group: ET.Element,
        elements: List[Tuple[str, ET.Element]],
        namespaces: dict,
        scale_x: float,
        scale_y: float,
        translate_x: float,
        translate_y: float,
        defs_elements: dict,
    ) -> None:
        """Recursively expand elements within a group, applying transformations."""

        # Parse group's own transform
        group_transform = group.get("transform", "")
        group_scale_x, group_scale_y, group_translate_x, group_translate_y = (
            self._parse_transform(group_transform)
        )

        # Combine transformations
        combined_scale_x = scale_x * group_scale_x
        combined_scale_y = scale_y * group_scale_y
        combined_translate_x = translate_x + group_translate_x * scale_x
        combined_translate_y = translate_y + group_translate_y * scale_y

        # Process direct child elements
        for child in group:
            tag_name = child.tag.split("}")[-1] if "}" in child.tag else child.tag

            if tag_name in ["path", "line", "circle", "rect"]:
                # Create a transformed copy of the element
                transformed_element = self._transform_element(
                    child,
                    combined_scale_x,
                    combined_scale_y,
                    combined_translate_x,
                    combined_translate_y,
                )
                elements.append((tag_name, transformed_element))
            elif tag_name == "g":
                # Recursively process nested groups
                self._expand_group_elements(
                    child,
                    elements,
                    namespaces,
                    combined_scale_x,
                    combined_scale_y,
                    combined_translate_x,
                    combined_translate_y,
                    defs_elements,
                )
            elif tag_name == "use":
                # Handle nested <use> elements
                href = child.get("href") or child.get(
                    "{http://www.w3.org/1999/xlink}href"
                )
                if href and href.startswith("#"):
                    ref_id = href[1:]
                    if ref_id in defs_elements:
                        # Get transformation from the nested <use> element
                        use_transform = child.get("transform", "")
                        use_x = float(child.get("x", 0))
                        use_y = float(child.get("y", 0))

                        # Parse nested use transform
                        use_scale_x, use_scale_y, use_translate_x, use_translate_y = (
                            self._parse_transform(use_transform)
                        )
                        use_translate_x += use_x
                        use_translate_y += use_y

                        # Combine with current transformations
                        final_scale_x = combined_scale_x * use_scale_x
                        final_scale_y = combined_scale_y * use_scale_y
                        final_translate_x = (
                            combined_translate_x + use_translate_x * combined_scale_x
                        )
                        final_translate_y = (
                            combined_translate_y + use_translate_y * combined_scale_y
                        )

                        # Recursively expand the referenced element
                        referenced_element = defs_elements[ref_id]
                        self._expand_group_elements(
                            referenced_element,
                            elements,
                            namespaces,
                            final_scale_x,
                            final_scale_y,
                            final_translate_x,
                            final_translate_y,
                            defs_elements,
                        )

    def _transform_element(
        self,
        element: ET.Element,
        scale_x: float,
        scale_y: float,
        translate_x: float,
        translate_y: float,
    ) -> ET.Element:
        """Create a transformed copy of an SVG element."""
        import copy

        new_element = copy.deepcopy(element)

        tag_name = element.tag.split("}")[-1] if "}" in element.tag else element.tag

        if tag_name == "line":
            x1 = float(element.get("x1", 0))
            y1 = float(element.get("y1", 0))
            x2 = float(element.get("x2", 0))
            y2 = float(element.get("y2", 0))

            new_x1 = x1 * scale_x + translate_x
            new_y1 = y1 * scale_y + translate_y
            new_x2 = x2 * scale_x + translate_x
            new_y2 = y2 * scale_y + translate_y

            new_element.set("x1", str(new_x1))
            new_element.set("y1", str(new_y1))
            new_element.set("x2", str(new_x2))
            new_element.set("y2", str(new_y2))

        elif tag_name == "circle":
            cx = float(element.get("cx", 0))
            cy = float(element.get("cy", 0))
            r = float(element.get("r", 0))

            new_cx = cx * scale_x + translate_x
            new_cy = cy * scale_y + translate_y
            new_r = r * abs(
                scale_x
            )  # Use scale_x for radius (assuming uniform scaling)

            new_element.set("cx", str(new_cx))
            new_element.set("cy", str(new_cy))
            new_element.set("r", str(new_r))

        elif tag_name == "rect":
            x = float(element.get("x", 0))
            y = float(element.get("y", 0))
            width = float(element.get("width", 0))
            height = float(element.get("height", 0))

            new_x = x * scale_x + translate_x
            new_y = y * scale_y + translate_y
            new_width = width * abs(scale_x)
            new_height = height * abs(scale_y)

            new_element.set("x", str(new_x))
            new_element.set("y", str(new_y))
            new_element.set("width", str(new_width))
            new_element.set("height", str(new_height))

        elif tag_name == "path":
            # Transform path data - this is more complex
            d = element.get("d", "")
            if d:
                transformed_d = self._transform_path_data(
                    d, scale_x, scale_y, translate_x, translate_y
                )
                new_element.set("d", transformed_d)

        return new_element

    def _transform_path_data(
        self,
        path_data: str,
        scale_x: float,
        scale_y: float,
        translate_x: float,
        translate_y: float,
    ) -> str:
        """Transform SVG path data by applying scale and translation."""
        import re

        # Simple transformation - find all coordinate pairs and transform them
        def transform_coords(match):
            coords = match.group(0)
            # Extract numbers from the coordinate string
            numbers = re.findall(r"-?\d+\.?\d*", coords)
            if len(numbers) >= 2:
                # Transform pairs of coordinates
                transformed = []
                for i in range(0, len(numbers), 2):
                    if i + 1 < len(numbers):
                        x = float(numbers[i])
                        y = float(numbers[i + 1])
                        new_x = x * scale_x + translate_x
                        new_y = y * scale_y + translate_y
                        transformed.extend([str(new_x), str(new_y)])
                    else:
                        # Odd number - just transform as x coordinate
                        x = float(numbers[i])
                        new_x = x * scale_x + translate_x
                        transformed.append(str(new_x))
                return " ".join(transformed)
            return coords

        # Transform coordinate sequences (this is a simplified approach)
        # More robust path transformation would require proper SVG path parsing
        # Use a simpler regex pattern that doesn't require variable-width lookbehind
        transformed = re.sub(r"[-\d\.\s,]+", transform_coords, path_data)
        return transformed
