"""Tests for Bézier curve parsing in SVG files."""

import tempfile
from pathlib import Path
import pytest

from microweldr.parsers.svg_parser import SVGParser


class TestBezierCurves:
    """Test parsing of SVG Bézier curves."""

    def create_test_svg(self, content: str) -> Path:
        """Create a temporary SVG file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(content)
            return Path(f.name)

    def test_quadratic_bezier_parsing(self):
        """Test parsing of quadratic Bézier curves (Q command)."""
        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <path d="M 10 10 Q 50 50 90 10" stroke="black" fill="none"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)
        try:
            parser = SVGParser(dot_spacing=1.0)
            weld_paths = parser.parse_file(svg_path)

            assert len(weld_paths) > 0, "Should parse at least one path"

            # Get all points from all paths
            all_points = []
            for path in weld_paths:
                all_points.extend(path.points)

            assert (
                len(all_points) > 3
            ), f"Quadratic Bézier should generate multiple points, got {len(all_points)}"

            # Check that we have points along the curve (not just endpoints)
            x_coords = [p.x for p in all_points]
            y_coords = [p.y for p in all_points]

            # Should have points between start (10,10) and end (90,10)
            assert min(x_coords) <= 15, "Should have points near start x"
            assert max(x_coords) >= 85, "Should have points near end x"

            # Should have points that go up (curve peak) - y should vary
            assert max(y_coords) > min(
                y_coords
            ), "Curve should have varying y coordinates"

        finally:
            svg_path.unlink()

    def test_cubic_bezier_parsing(self):
        """Test parsing of cubic Bézier curves (C command)."""
        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <path d="M 10 10 C 30 50 70 50 90 10" stroke="black" fill="none"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)
        try:
            parser = SVGParser(dot_spacing=1.0)
            weld_paths = parser.parse_file(svg_path)

            assert len(weld_paths) > 0, "Should parse at least one path"

            # Get all points from all paths
            all_points = []
            for path in weld_paths:
                all_points.extend(path.points)

            assert (
                len(all_points) > 3
            ), f"Cubic Bézier should generate multiple points, got {len(all_points)}"

        finally:
            svg_path.unlink()

    def test_flask_bottom_curve(self):
        """Test parsing the flask bottom curve specifically."""
        # Simplified version of the flask bottom curve
        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="60" height="80" viewBox="0 0 60 80" xmlns="http://www.w3.org/2000/svg">
  <path d="Q 12.5 72.5 30 75" stroke="black" fill="none"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)
        try:
            parser = SVGParser(dot_spacing=1.0)
            weld_paths = parser.parse_file(svg_path)

            assert len(weld_paths) > 0, "Should parse flask bottom curve"

            # Get all points
            all_points = []
            for path in weld_paths:
                all_points.extend(path.points)

            print(f"Flask bottom curve generated {len(all_points)} points")
            for i, point in enumerate(all_points):
                print(f"  Point {i}: ({point.x:.2f}, {point.y:.2f})")

            assert len(all_points) > 1, "Should generate multiple points for curve"

        finally:
            svg_path.unlink()

    def test_complete_flask_parsing(self):
        """Test parsing the complete flask with all curves."""
        flask_svg = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="60mm" height="80mm" viewBox="0 0 60 80" xmlns="http://www.w3.org/2000/svg">
  <path d="M 32.5 10
           L 32.5 35
           Q 32.5 37 32.2 39
           L 31 42
           Q 31 45 34 45
           Q 47.5 52.5 47.5 62.5
           Q 47.5 72.5 30 75"
        stroke="black" fill="none"/>
  <path d="M 27.5 10
           L 27.5 35
           Q 27.5 37 27.8 39
           L 29 42
           Q 29 45 26 45
           Q 12.5 52.5 12.5 62.5
           Q 12.5 72.5 30 75"
        stroke="black" fill="none"/>
</svg>"""

        svg_path = self.create_test_svg(flask_svg)
        try:
            parser = SVGParser(dot_spacing=1.0)
            weld_paths = parser.parse_file(svg_path)

            assert len(weld_paths) > 0, "Should parse flask paths"

            # Get all points
            all_points = []
            for path in weld_paths:
                all_points.extend(path.points)

            print(f"Complete flask generated {len(all_points)} points")

            # Should have points at the bottom (y around 75)
            y_coords = [p.y for p in all_points]
            max_y = max(y_coords)

            print(f"Max Y coordinate: {max_y}")
            assert (
                max_y >= 70
            ), f"Should have points near bottom (y=75), max found: {max_y}"

            # Should have a reasonable number of points for the curves
            assert (
                len(all_points) >= 20
            ), f"Should have sufficient points for flask curves, got {len(all_points)}"

        finally:
            svg_path.unlink()
