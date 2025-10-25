"""Tests for SVG element endpoints and closure behavior."""

import math
import tempfile
from pathlib import Path

import pytest

from microweldr.core.config import Config
from microweldr.core.models import WeldPoint
from microweldr.core.svg_parser import SVGParser


class TestSVGEndpoints:
    """Test cases for SVG element start and end points."""

    def create_temp_config(self, content: str) -> Path:
        """Create a temporary config file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(content)
            return Path(f.name)

    def create_test_config(self) -> Config:
        """Create a test configuration."""
        config_content = """
[printer]
bed_size_x = 250.0

[nozzle]
outer_diameter = 1.0
inner_diameter = 0.2

[temperatures]
bed_temperature = 60
nozzle_temperature = 200
cooldown_temperature = 50

[movement]
move_height = 5.0
travel_speed = 6000
z_speed = 300

[normal_welds]
weld_height = 0.05
weld_temperature = 200
weld_time = 0.5
dot_spacing = 2.0
initial_dot_spacing = 8.0
cooling_time_between_passes = 2.0

[light_welds]
weld_height = 0.05
weld_temperature = 180
weld_time = 0.3
dot_spacing = 3.0
initial_dot_spacing = 12.0
cooling_time_between_passes = 1.5

[output]
gcode_extension = ".gcode"

[animation]
time_between_welds = 0.1
pause_time = 3.0
min_animation_duration = 10.0
        """
        config_path = self.create_temp_config(config_content)
        try:
            return Config(config_path)
        finally:
            config_path.unlink()

    def create_test_svg(self, content: str) -> Path:
        """Create a temporary SVG file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(content)
            return Path(f.name)

    def test_line_endpoints(self):
        """Test that lines have correct start and end points."""
        config = self.create_test_config()
        dot_spacing = config.get("normal_welds", "dot_spacing")
        parser = SVGParser(dot_spacing=dot_spacing)

        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <line x1="10" y1="20" x2="90" y2="80" stroke="black" stroke-width="2"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)

        try:
            weld_paths = parser.parse_file(str(svg_path))

            assert len(weld_paths) == 1
            path = weld_paths[0]

            # Line should have at least 2 points (start and end)
            assert len(path.points) >= 2

            # First point should be the start (10, 20)
            first_point = path.points[0]
            assert abs(first_point.x - 10.0) < 0.1
            assert abs(first_point.y - 20.0) < 0.1

            # Last point should be the end (90, 80)
            last_point = path.points[-1]
            assert abs(last_point.x - 90.0) < 0.1
            assert abs(last_point.y - 80.0) < 0.1

        finally:
            svg_path.unlink()

    def test_circle_closure(self):
        """Test that circles are properly closed (first point == last point)."""
        config = self.create_test_config()
        dot_spacing = config.get("normal_welds", "dot_spacing")
        parser = SVGParser(dot_spacing=dot_spacing)

        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="20" fill="none" stroke="black" stroke-width="1"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)

        try:
            weld_paths = parser.parse_file(str(svg_path))

            assert len(weld_paths) == 1
            path = weld_paths[0]

            # Circle should have multiple points
            assert len(path.points) > 8  # At least 8 points around circle

            # First and last points should be the same (circle closure)
            first_point = path.points[0]
            last_point = path.points[-1]

            assert abs(first_point.x - last_point.x) < 0.001
            assert abs(first_point.y - last_point.y) < 0.001
            assert first_point.weld_type == last_point.weld_type

            # Verify points are actually on the circle
            cx, cy, r = 50.0, 50.0, 20.0
            for point in path.points:
                distance = math.sqrt((point.x - cx) ** 2 + (point.y - cy) ** 2)
                assert abs(distance - r) < 0.1  # Should be on circle circumference

        finally:
            svg_path.unlink()

    def test_rectangle_closure(self):
        """Test that rectangles are properly closed."""
        config = self.create_test_config()
        dot_spacing = config.get("normal_welds", "dot_spacing")
        parser = SVGParser(dot_spacing=dot_spacing)

        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <rect x="10" y="20" width="60" height="40" fill="none" stroke="black" stroke-width="1"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)

        try:
            weld_paths = parser.parse_file(str(svg_path))

            assert len(weld_paths) == 1
            path = weld_paths[0]

            # Rectangle should have at least 5 points (4 corners + closure)
            assert len(path.points) >= 5

            # First and last points should be the same (rectangle closure)
            first_point = path.points[0]
            last_point = path.points[-1]

            assert abs(first_point.x - last_point.x) < 0.001
            assert abs(first_point.y - last_point.y) < 0.001
            assert first_point.weld_type == last_point.weld_type

            # Verify corner points are correct
            # Rectangle corners should be at (10,20), (70,20), (70,60), (10,60)
            expected_corners = [(10, 20), (70, 20), (70, 60), (10, 60)]

            # Check that we have points at or near the expected corners
            for expected_x, expected_y in expected_corners:
                found_corner = False
                for point in path.points:
                    if (
                        abs(point.x - expected_x) < 0.1
                        and abs(point.y - expected_y) < 0.1
                    ):
                        found_corner = True
                        break
                assert (
                    found_corner
                ), f"Corner ({expected_x}, {expected_y}) not found in rectangle points"

        finally:
            svg_path.unlink()

    def test_path_with_z_command_closure(self):
        """Test that paths with Z (close) command are properly closed."""
        config = self.create_test_config()
        dot_spacing = config.get("normal_welds", "dot_spacing")
        parser = SVGParser(dot_spacing=dot_spacing)

        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <path d="M 10 10 L 50 10 L 50 50 L 10 50 Z" fill="none" stroke="black" stroke-width="1"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)

        try:
            weld_paths = parser.parse_file(str(svg_path))

            assert len(weld_paths) == 1
            path = weld_paths[0]

            # Path should have multiple points
            assert len(path.points) >= 4

            # First and last points should be the same due to Z command
            first_point = path.points[0]
            last_point = path.points[-1]

            assert abs(first_point.x - last_point.x) < 0.001
            assert abs(first_point.y - last_point.y) < 0.001
            assert first_point.weld_type == last_point.weld_type

            # Verify the path follows the expected coordinates
            expected_points = [(10, 10), (50, 10), (50, 50), (10, 50)]

            for expected_x, expected_y in expected_points:
                found_point = False
                for point in path.points:
                    if (
                        abs(point.x - expected_x) < 0.1
                        and abs(point.y - expected_y) < 0.1
                    ):
                        found_point = True
                        break
                assert (
                    found_point
                ), f"Expected point ({expected_x}, {expected_y}) not found in path"

        finally:
            svg_path.unlink()

    def test_path_without_z_command_open(self):
        """Test that paths without Z command remain open."""
        config = self.create_test_config()
        dot_spacing = config.get("normal_welds", "dot_spacing")
        parser = SVGParser(dot_spacing=dot_spacing)

        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <path d="M 10 10 L 50 10 L 50 50 L 10 50" fill="none" stroke="black" stroke-width="1"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)

        try:
            weld_paths = parser.parse_file(str(svg_path))

            assert len(weld_paths) == 1
            path = weld_paths[0]

            # Path should have multiple points
            assert len(path.points) >= 4

            # First and last points should NOT be the same (no Z command)
            first_point = path.points[0]
            last_point = path.points[-1]

            # Should start at (10, 10) and end at (10, 50)
            assert abs(first_point.x - 10.0) < 0.1
            assert abs(first_point.y - 10.0) < 0.1
            assert abs(last_point.x - 10.0) < 0.1
            assert abs(last_point.y - 50.0) < 0.1

            # They should be different points
            assert abs(first_point.y - last_point.y) > 30  # Should be 40 units apart

        finally:
            svg_path.unlink()

    def test_multiple_circles_all_closed(self):
        """Test that multiple circles are all properly closed."""
        config = self.create_test_config()
        dot_spacing = config.get("normal_welds", "dot_spacing")
        parser = SVGParser(dot_spacing=dot_spacing)

        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="200" height="100" xmlns="http://www.w3.org/2000/svg">
  <circle cx="30" cy="30" r="15" fill="none" stroke="black" stroke-width="1"/>
  <circle cx="70" cy="30" r="10" fill="none" stroke="blue" stroke-width="1"/>
  <circle cx="110" cy="30" r="20" fill="none" stroke="red" stroke-width="1"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)

        try:
            weld_paths = parser.parse_file(str(svg_path))

            assert len(weld_paths) == 3

            for i, path in enumerate(weld_paths):
                # Each circle should be closed
                assert len(path.points) > 8

                first_point = path.points[0]
                last_point = path.points[-1]

                assert (
                    abs(first_point.x - last_point.x) < 0.001
                ), f"Circle {i} not closed in X"
                assert (
                    abs(first_point.y - last_point.y) < 0.001
                ), f"Circle {i} not closed in Y"
                assert (
                    first_point.weld_type == last_point.weld_type
                ), f"Circle {i} weld types don't match"

        finally:
            svg_path.unlink()

    def test_mixed_elements_endpoints(self):
        """Test endpoints of mixed SVG elements."""
        config = self.create_test_config()
        dot_spacing = config.get("normal_welds", "dot_spacing")
        parser = SVGParser(dot_spacing=dot_spacing)

        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
  <line x1="10" y1="10" x2="50" y2="10" stroke="black"/>
  <circle cx="100" cy="50" r="15" fill="none" stroke="blue"/>
  <rect x="10" y="100" width="40" height="30" fill="none" stroke="black"/>
  <path d="M 100 100 L 140 100 L 140 130 Z" fill="none" stroke="black"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)

        try:
            weld_paths = parser.parse_file(str(svg_path))

            assert len(weld_paths) == 4

            # Test basic properties without assuming specific order
            closed_paths = []
            open_paths = []

            for path in weld_paths:
                first_point = path.points[0]
                last_point = path.points[-1]

                # Check if path is closed (first == last point)
                if (
                    abs(first_point.x - last_point.x) < 0.001
                    and abs(first_point.y - last_point.y) < 0.001
                ):
                    closed_paths.append(path)
                else:
                    open_paths.append(path)

            # We should have 3 closed paths (circle, rectangle, path with Z) and 1 open (line)
            assert (
                len(closed_paths) == 3
            ), f"Expected 3 closed paths, got {len(closed_paths)}"
            assert len(open_paths) == 1, f"Expected 1 open path, got {len(open_paths)}"

            # The open path should be the line
            line_path = open_paths[0]
            assert len(line_path.points) >= 2

            # All closed paths should have their first and last points identical
            for i, path in enumerate(closed_paths):
                first_point = path.points[0]
                last_point = path.points[-1]
                assert (
                    abs(first_point.x - last_point.x) < 0.001
                ), f"Closed path {i} not closed in X"
                assert (
                    abs(first_point.y - last_point.y) < 0.001
                ), f"Closed path {i} not closed in Y"

        finally:
            svg_path.unlink()

    def test_circle_point_distribution(self):
        """Test that circle points are evenly distributed around circumference."""
        config = self.create_test_config()
        dot_spacing = config.get("normal_welds", "dot_spacing")
        parser = SVGParser(dot_spacing=dot_spacing)

        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="20" fill="none" stroke="black" stroke-width="1"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)

        try:
            weld_paths = parser.parse_file(str(svg_path))

            assert len(weld_paths) == 1
            path = weld_paths[0]

            # Remove the duplicate closing point for angle calculation
            points = path.points[:-1]  # Exclude last point (duplicate of first)

            cx, cy, r = 50.0, 50.0, 20.0

            # Calculate angles for each point
            angles = []
            for point in points:
                angle = math.atan2(point.y - cy, point.x - cx)
                angles.append(angle)

            # Sort angles to check distribution
            angles.sort()

            # Check that angles are reasonably distributed
            if (
                len(angles) > 2
            ):  # Need at least 3 points for meaningful distribution check
                expected_angle_step = 2 * math.pi / len(angles)

                # Check most angle differences, allowing for some variation
                good_angles = 0
                for i in range(1, len(angles)):
                    angle_diff = angles[i] - angles[i - 1]
                    # Allow generous tolerance in angle distribution due to interpolation
                    if (
                        abs(angle_diff - expected_angle_step)
                        < expected_angle_step * 2.0
                    ):
                        good_angles += 1

                # Most angles should be reasonably distributed
                assert (
                    good_angles >= len(angles) * 0.5
                ), f"Only {good_angles}/{len(angles)-1} angles well distributed"

        finally:
            svg_path.unlink()

    def test_small_circle_minimum_points(self):
        """Test that even small circles have minimum number of points."""
        config = self.create_test_config()
        dot_spacing = config.get("normal_welds", "dot_spacing")
        parser = SVGParser(dot_spacing=dot_spacing)

        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="1" fill="none" stroke="black" stroke-width="1"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)

        try:
            weld_paths = parser.parse_file(str(svg_path))

            assert len(weld_paths) == 1
            path = weld_paths[0]

            # Even small circles should have at least 8 points + 1 closure point
            assert len(path.points) >= 9  # 8 + 1 for closure

            # Should still be closed
            first_point = path.points[0]
            last_point = path.points[-1]

            assert abs(first_point.x - last_point.x) < 0.001
            assert abs(first_point.y - last_point.y) < 0.001

        finally:
            svg_path.unlink()

    def test_large_circle_adequate_points(self):
        """Test that large circles have adequate number of points."""
        config = self.create_test_config()
        dot_spacing = config.get("normal_welds", "dot_spacing")
        parser = SVGParser(dot_spacing=dot_spacing)

        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
  <circle cx="100" cy="100" r="80" fill="none" stroke="black" stroke-width="1"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)

        try:
            weld_paths = parser.parse_file(str(svg_path))

            assert len(weld_paths) == 1
            path = weld_paths[0]

            # Large circles should have more points for smooth curves
            # With radius 80, circumference is ~502, so expect many points
            assert len(path.points) > 50  # Should have plenty of points

            # Should still be closed
            first_point = path.points[0]
            last_point = path.points[-1]

            assert abs(first_point.x - last_point.x) < 0.001
            assert abs(first_point.y - last_point.y) < 0.001

        finally:
            svg_path.unlink()
