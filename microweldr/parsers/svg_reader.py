"""SVG file reader with publisher-subscriber architecture."""

import logging
import math
import re
import xml.etree.ElementTree as ET  # nosec B405 - Parsing trusted SVG files only
from pathlib import Path
from typing import List, Optional, Tuple

from ..core.app_constants import SVGNamespace
from ..core.data_models import Point, WeldPath, WeldType
from ..core.error_handling import FileProcessingError, ParsingError, handle_errors
from .file_readers import FileReaderPublisher

logger = logging.getLogger(__name__)


class SVGReader(FileReaderPublisher):
    """SVG file reader that publishes weld paths."""

    def __init__(self, dot_spacing: float = 2.0):
        super().__init__()
        self.dot_spacing = dot_spacing

    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return [".svg", ".SVG"]

    def can_read_file(self, file_path: Path) -> bool:
        """Check if this reader can handle the given file."""
        return file_path.suffix.lower() in self.get_supported_extensions()

    @handle_errors(
        error_types={
            ET.ParseError: ParsingError,
            FileNotFoundError: FileProcessingError,
        },
        default_error=FileProcessingError,
    )
    def _parse_file_internal(self, file_path: Path) -> List[WeldPath]:
        """Parse SVG file and extract weld paths."""
        logger.info(f"Parsing SVG file: {file_path}")

        # Store filename for weld type detection
        self._current_filename = file_path.stem

        try:
            tree = ET.parse(
                str(file_path)
            )  # nosec B314 - Parsing trusted user SVG files
            root = tree.getroot()
        except ET.ParseError as e:
            raise ParsingError(f"Invalid SVG file: {e}")
        except FileNotFoundError:
            raise FileProcessingError(f"SVG file '{file_path}' not found.")

        weld_paths = self._parse_elements(root)
        logger.info(f"Parsed {len(weld_paths)} weld paths from SVG")
        return weld_paths

    def _parse_elements(self, root: ET.Element) -> List[WeldPath]:
        """Parse SVG elements and return weld paths."""
        # Define SVG namespace
        namespaces = {"svg": SVGNamespace.URI}

        # First, build a dictionary of defined elements from <defs>
        defs_elements = {}
        for defs in root.findall(".//svg:defs", namespaces):
            for group in defs.findall(".//svg:g[@id]", namespaces):
                group_id = group.get("id")
                if group_id:
                    defs_elements[group_id] = group

        # Find all supported elements (excluding those inside <defs>)
        elements = []

        # Find paths, lines, circles, rectangles, and groups (but not inside <defs>)
        for element_type in ["path", "line", "circle", "rect", "g"]:
            xpath = f".//svg:{element_type}"
            for elem in root.findall(xpath, namespaces):
                # Skip if element is inside <defs>
                if self._is_inside_defs(elem, root):
                    continue
                elements.append(elem)

        # Also find <use> elements that reference defined elements
        for use_elem in root.findall(".//svg:use", namespaces):
            if self._is_inside_defs(use_elem, root):
                continue
            elements.append(use_elem)

        weld_paths = []
        for elem in elements:
            try:
                paths = self._parse_element(elem, defs_elements, namespaces)
                weld_paths.extend(paths)
            except Exception as e:
                logger.warning(f"Failed to parse element {elem.tag}: {e}")
                continue

        return weld_paths

    def _is_inside_defs(self, element: ET.Element, root: ET.Element) -> bool:
        """Check if an element is inside a <defs> section."""
        parent = element
        while parent is not None:
            if parent.tag.endswith("}defs") or parent.tag == "defs":
                return True
            # Find parent in the tree
            for potential_parent in root.iter():
                if element in potential_parent:
                    parent = potential_parent
                    break
            else:
                break
        return False

    def _parse_element(
        self, elem: ET.Element, defs_elements: dict, namespaces: dict
    ) -> List[WeldPath]:
        """Parse a single SVG element."""
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

        if tag == "path":
            return self._parse_path(elem)
        elif tag == "line":
            return self._parse_line(elem)
        elif tag == "circle":
            return self._parse_circle(elem)
        elif tag == "rect":
            return self._parse_rect(elem)
        elif tag == "g":
            return self._parse_group(elem, defs_elements, namespaces)
        elif tag == "use":
            return self._parse_use(elem, defs_elements, namespaces)
        else:
            logger.debug(f"Unsupported SVG element: {tag}")
            return []

    def _parse_path(self, elem: ET.Element) -> List[WeldPath]:
        """Parse SVG path element."""
        d = elem.get("d", "")
        if not d:
            return []

        weld_type = self._determine_weld_type(elem)
        points = self._parse_path_data(d)

        if len(points) < 2:
            return []

        path_id = elem.get("id")
        return [WeldPath(points, weld_type, path_id=path_id)]

    def _parse_line(self, elem: ET.Element) -> List[WeldPath]:
        """Parse SVG line element."""
        try:
            x1 = float(elem.get("x1", 0))
            y1 = float(elem.get("y1", 0))
            x2 = float(elem.get("x2", 0))
            y2 = float(elem.get("y2", 0))

            weld_type = self._determine_weld_type(elem)
            points = [Point(x1, y1), Point(x2, y2)]
            path_id = elem.get("id")

            return [WeldPath(points, weld_type, path_id=path_id)]
        except ValueError as e:
            logger.warning(f"Invalid line coordinates: {e}")
            return []

    def _parse_circle(self, elem: ET.Element) -> List[WeldPath]:
        """Parse SVG circle element."""
        try:
            cx = float(elem.get("cx", 0))
            cy = float(elem.get("cy", 0))
            r = float(elem.get("r", 0))

            if r <= 0:
                return []

            weld_type = self._determine_weld_type(elem)
            points = self._circle_to_points(cx, cy, r)
            path_id = elem.get("id")

            return [WeldPath(points, weld_type, path_id=path_id)]
        except ValueError as e:
            logger.warning(f"Invalid circle parameters: {e}")
            return []

    def _parse_rect(self, elem: ET.Element) -> List[WeldPath]:
        """Parse SVG rectangle element."""
        try:
            x = float(elem.get("x", 0))
            y = float(elem.get("y", 0))
            width = float(elem.get("width", 0))
            height = float(elem.get("height", 0))

            if width <= 0 or height <= 0:
                return []

            weld_type = self._determine_weld_type(elem)

            # Create rectangle as closed path
            points = [
                Point(x, y),
                Point(x + width, y),
                Point(x + width, y + height),
                Point(x, y + height),
                Point(x, y),  # Close the rectangle
            ]

            path_id = elem.get("id")
            return [WeldPath(points, weld_type, path_id=path_id)]
        except ValueError as e:
            logger.warning(f"Invalid rectangle parameters: {e}")
            return []

    def _parse_group(
        self, elem: ET.Element, defs_elements: dict, namespaces: dict
    ) -> List[WeldPath]:
        """Parse SVG group element."""
        weld_paths = []

        for child in elem:
            try:
                paths = self._parse_element(child, defs_elements, namespaces)
                weld_paths.extend(paths)
            except Exception as e:
                logger.warning(f"Failed to parse group child {child.tag}: {e}")
                continue

        return weld_paths

    def _parse_use(
        self, elem: ET.Element, defs_elements: dict, namespaces: dict
    ) -> List[WeldPath]:
        """Parse SVG use element."""
        href = elem.get("href") or elem.get("{http://www.w3.org/1999/xlink}href", "")
        if not href.startswith("#"):
            return []

        ref_id = href[1:]  # Remove the '#'
        if ref_id not in defs_elements:
            logger.warning(f"Referenced element not found: {ref_id}")
            return []

        # Parse the referenced element
        ref_element = defs_elements[ref_id]
        return self._parse_element(ref_element, defs_elements, namespaces)

    def _determine_weld_type(self, elem: ET.Element) -> WeldType:
        """Determine weld type based on element attributes and filename."""
        # Check stroke color for frangible welds (blue indicates frangible)
        stroke = elem.get("stroke", "").lower()
        if "blue" in stroke or stroke in ["#0000ff", "#00f", "blue"]:
            return WeldType.FRANGIBLE

        # Check class attribute
        class_attr = elem.get("class", "").lower()
        if any(keyword in class_attr for keyword in ["frangible", "light", "break"]):
            return WeldType.FRANGIBLE

        # Check id attribute
        id_attr = elem.get("id", "").lower()
        if any(keyword in id_attr for keyword in ["frangible", "light", "break"]):
            return WeldType.FRANGIBLE

        # Fallback: Check filename for frangible indicators
        if hasattr(self, "_current_filename") and self._current_filename:
            filename_lower = self._current_filename.lower()
            frangible_keywords = ["frangible", "light", "break", "seal", "weak"]
            if any(keyword in filename_lower for keyword in frangible_keywords):
                return WeldType.FRANGIBLE

        # Default to normal welds (black stroke)
        return WeldType.NORMAL

    def _parse_path_data(self, d: str) -> List[Point]:
        """Parse SVG path data string."""
        points = []

        # Simple path parser - handles M, L, Z commands
        # This is a simplified version; the enhanced parser handles curves
        commands = re.findall(r"[MLZHVCSQTAmlzhvcsqta][^MLZHVCSQTAmlzhvcsqta]*", d)

        current_x, current_y = 0.0, 0.0

        for command in commands:
            cmd = command[0]
            coords_str = command[1:].strip()

            if not coords_str and cmd.upper() not in ["Z"]:
                continue

            # Parse coordinates
            coords = []
            if coords_str:
                coord_matches = re.findall(r"-?\d*\.?\d+", coords_str)
                coords = [float(x) for x in coord_matches]

            if cmd.upper() == "M":  # Move to
                if len(coords) >= 2:
                    if cmd.isupper():  # Absolute
                        current_x, current_y = coords[0], coords[1]
                    else:  # Relative
                        current_x += coords[0]
                        current_y += coords[1]
                    points.append(Point(current_x, current_y))

            elif cmd.upper() == "L":  # Line to
                for i in range(0, len(coords), 2):
                    if i + 1 < len(coords):
                        if cmd.isupper():  # Absolute
                            current_x, current_y = coords[i], coords[i + 1]
                        else:  # Relative
                            current_x += coords[i]
                            current_y += coords[i + 1]
                        points.append(Point(current_x, current_y))

            elif cmd.upper() == "H":  # Horizontal line
                for coord in coords:
                    if cmd.isupper():  # Absolute
                        current_x = coord
                    else:  # Relative
                        current_x += coord
                    points.append(Point(current_x, current_y))

            elif cmd.upper() == "V":  # Vertical line
                for coord in coords:
                    if cmd.isupper():  # Absolute
                        current_y = coord
                    else:  # Relative
                        current_y += coord
                    points.append(Point(current_x, current_y))

            elif cmd.upper() == "Z":  # Close path
                if points:
                    points.append(points[0])  # Close to first point

        return points

    def _circle_to_points(
        self, cx: float, cy: float, r: float, segments: int = 36
    ) -> List[Point]:
        """Convert circle to points."""
        points = []
        for i in range(segments):
            angle = 2 * math.pi * i / segments
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            points.append(Point(x, y))

        # Close the circle
        points.append(points[0])
        return points
