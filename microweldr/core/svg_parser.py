"""SVG parsing functionality."""

import math
import re
import xml.etree.ElementTree as ET
from typing import List, Optional, Tuple

from microweldr.core.models import WeldPath, WeldPoint


class SVGParseError(Exception):
    """Raised when there's an error parsing SVG."""

    pass


class SVGParser:
    """Parser for SVG files to extract weld paths."""

    def __init__(self, dot_spacing: float = 2.0) -> None:
        """Initialize SVG parser."""
        self.dot_spacing = dot_spacing

    def parse_file(self, svg_path: str) -> List[WeldPath]:
        """Parse SVG file and extract weld paths."""
        try:
            tree = ET.parse(svg_path)
            root = tree.getroot()
        except ET.ParseError as e:
            raise SVGParseError(f"Invalid SVG file: {e}")
        except FileNotFoundError:
            raise SVGParseError(f"SVG file '{svg_path}' not found.")

        return self._parse_elements(root)

    def _parse_elements(self, root: ET.Element) -> List[WeldPath]:
        """Parse SVG elements and return weld paths."""
        # Define SVG namespace
        namespaces = {"svg": "http://www.w3.org/2000/svg"}

        # Find all supported elements
        elements = []

        # Get paths
        for path in root.findall(".//svg:path", namespaces):
            elements.append(("path", path))

        # Get lines
        for line in root.findall(".//svg:line", namespaces):
            elements.append(("line", line))

        # Get circles
        for circle in root.findall(".//svg:circle", namespaces):
            elements.append(("circle", circle))

        # Get rectangles
        for rect in root.findall(".//svg:rect", namespaces):
            elements.append(("rect", rect))

        # Sort by ID if available
        elements.sort(key=self._get_sort_key)

        # Process each element and ensure unique IDs
        weld_paths = []
        used_ids = set()

        for element_type, element in elements:
            weld_type, pause_message = self._determine_weld_type(element)

            # Ensure unique SVG ID
            base_id = element.get("id", f"{element_type}_{len(weld_paths) + 1}")
            svg_id = base_id
            counter = 1
            while svg_id in used_ids:
                svg_id = f"{base_id}_{counter}"
                counter += 1
            used_ids.add(svg_id)

            points = self._parse_element(element_type, element)

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

        return weld_paths

    def _get_sort_key(self, element_tuple: Tuple[str, ET.Element]) -> float:
        """Get sort key for element ordering."""
        element_type, element = element_tuple
        element_id = element.get("id", "")
        # Try to extract numeric part for sorting
        match = re.search(r"(\d+)", element_id)
        return int(match.group(1)) if match else float("inf")

    def _determine_weld_type(self, element: ET.Element) -> Tuple[str, Optional[str]]:
        """Determine weld type based on element color and extract pause message."""
        from .constants import Colors, WeldType, SVGAttributes, get_color_weld_type
        
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
            
            # Check for light weld colors
            for color_alias in Colors.LIGHT_ALIASES:
                if color_alias in color_info:
                    return WeldType.LIGHT.value, None
            
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

    def _parse_element(self, element_type: str, element: ET.Element) -> List[WeldPoint]:
        """Parse individual SVG element."""
        if element_type == "path":
            return self._parse_path_element(element)
        elif element_type == "line":
            return self._parse_line_element(element)
        elif element_type == "circle":
            return self._parse_circle_element(element)
        elif element_type == "rect":
            return self._parse_rect_element(element)
        else:
            return []

    def _parse_path_element(self, path_element: ET.Element) -> List[WeldPoint]:
        """Parse SVG path element and return weld points."""
        d = path_element.get("d", "")
        if not d:
            return []

        points = []
        # Simple path parser - handles M, L, Z commands
        commands = re.findall(r"[MLZ][^MLZ]*", d)
        current_x, current_y = 0.0, 0.0
        start_x, start_y = 0.0, 0.0  # Track start point for Z command

        for command in commands:
            cmd = command[0]
            coords = re.findall(r"-?\d+\.?\d*", command[1:])
            coords = [float(c) for c in coords]

            if cmd == "M" and len(coords) >= 2:  # Move to
                current_x, current_y = coords[0], coords[1]
                start_x, start_y = current_x, current_y  # Remember start point
                points.append(WeldPoint(current_x, current_y, "normal"))
            elif cmd == "L" and len(coords) >= 2:  # Line to
                current_x, current_y = coords[0], coords[1]
                points.append(WeldPoint(current_x, current_y, "normal"))
            elif cmd == "Z":  # Close path - return to start point
                if points and (current_x != start_x or current_y != start_y):
                    points.append(WeldPoint(start_x, start_y, "normal"))
                    current_x, current_y = start_x, start_y

        return self._interpolate_points(points)

    def _parse_line_element(self, line_element: ET.Element) -> List[WeldPoint]:
        """Parse SVG line element."""
        x1 = float(line_element.get("x1", 0))
        y1 = float(line_element.get("y1", 0))
        x2 = float(line_element.get("x2", 0))
        y2 = float(line_element.get("y2", 0))

        # Extract custom parameters from line element
        custom_temp = self._get_float_attr(line_element, "data-temp")
        custom_weld_time = self._get_float_attr(line_element, "data-weld-time")
        custom_bed_temp = self._get_float_attr(line_element, "data-bed-temp")
        custom_weld_height = self._get_float_attr(line_element, "data-weld-height")

        points = [
            WeldPoint(
                x1,
                y1,
                "normal",
                custom_temp,
                custom_weld_time,
                custom_bed_temp,
                custom_weld_height,
            ),
            WeldPoint(
                x2,
                y2,
                "normal",
                custom_temp,
                custom_weld_time,
                custom_bed_temp,
                custom_weld_height,
            ),
        ]

        return self._interpolate_points(points)

    def _parse_circle_element(self, circle_element: ET.Element) -> List[WeldPoint]:
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

        return self._interpolate_points(points)

    def _parse_rect_element(self, rect_element: ET.Element) -> List[WeldPoint]:
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

        return self._interpolate_points(points)

    def _interpolate_points(self, points: List[WeldPoint]) -> List[WeldPoint]:
        """Interpolate points along the path using initial dot spacing for multi-pass welding."""
        if len(points) < 2:
            return points

        interpolated = []

        for i in range(len(points) - 1):
            start = points[i]
            end = points[i + 1]

            # Calculate distance
            dx = end.x - start.x
            dy = end.y - start.y
            distance = math.sqrt(dx * dx + dy * dy)

            if distance == 0:
                continue

            # Use initial dot spacing for first pass - this will be refined later
            # The actual multi-pass logic will be handled in the G-code generator
            num_points = max(1, int(distance / self.dot_spacing))

            # Add interpolated points
            for j in range(num_points + 1):
                t = j / num_points if num_points > 0 else 0
                x = start.x + t * dx
                y = start.y + t * dy
                interpolated.append(WeldPoint(x, y, start.weld_type))

        return interpolated
