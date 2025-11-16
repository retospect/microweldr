"""Tests for DXF line segment handling, specifically straight line interpolation."""

import tempfile
from pathlib import Path
import pytest

from microweldr.generators.point_iterator_factory import PointIteratorFactory


class TestDXFLineSegments:
    """Test DXF line segment parsing and interpolation."""

    def create_test_dxf(self, content: str) -> Path:
        """Create a temporary DXF file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".dxf", delete=False) as f:
            f.write(content)
            return Path(f.name)

    def test_straight_line_interpolation(self):
        """Test that straight lines get proper point interpolation."""
        # Create a simple DXF with a long straight line (40mm)
        dxf_content = """0
SECTION
2
HEADER
9
$INSUNITS
70
4
0
ENDSEC
0
SECTION
2
ENTITIES
0
LINE
8
0
10
0.0
20
0.0
11
40.0
21
0.0
0
ENDSEC
0
EOF
"""

        dxf_path = self.create_test_dxf(dxf_content)
        try:
            # Parse with 2mm dot spacing
            iterator = PointIteratorFactory.create_iterator(
                str(dxf_path), dot_spacing=2.0
            )
            points = list(iterator.iterate_points(dxf_path))

            print(f"40mm line generated {len(points)} points with 2mm spacing")
            for i, point in enumerate(points):
                print(f"  Point {i}: ({point['x']:.2f}, {point['y']:.2f})")

            # Should have ~20 points for 40mm line with 2mm spacing
            assert (
                len(points) >= 18
            ), f"Expected at least 18 points for 40mm line with 2mm spacing, got {len(points)}"

            # Points should be evenly spaced along the line
            assert points[0]["x"] == pytest.approx(0.0, abs=0.1)
            assert points[-1]["x"] == pytest.approx(40.0, abs=0.1)

            # Check spacing between consecutive points
            if len(points) > 2:
                spacing = points[1]["x"] - points[0]["x"]
                assert spacing == pytest.approx(
                    2.0, abs=0.5
                ), f"Expected ~2mm spacing, got {spacing:.2f}mm"

        finally:
            dxf_path.unlink()

    def test_lwpolyline_straight_segments(self):
        """Test that straight segments in LWPOLYLINE get proper interpolation."""
        # Create LWPOLYLINE with straight segments (bulge = 0)
        dxf_content = """0
SECTION
2
HEADER
9
$INSUNITS
70
4
0
ENDSEC
0
SECTION
2
ENTITIES
0
LWPOLYLINE
8
0
100
AcDbEntity
100
AcDbPolyline
90
3
70
0
43
0.0
10
0.0
20
0.0
42
0.0
10
20.0
20
0.0
42
0.0
10
20.0
20
20.0
0
ENDSEC
0
EOF
"""

        dxf_path = self.create_test_dxf(dxf_content)
        try:
            # Parse with 2mm dot spacing
            iterator = PointIteratorFactory.create_iterator(
                str(dxf_path), dot_spacing=2.0
            )
            points = list(iterator.iterate_points(dxf_path))

            print(f"L-shaped polyline generated {len(points)} points")
            for i, point in enumerate(points):
                print(f"  Point {i}: ({point['x']:.2f}, {point['y']:.2f})")

            # Should have points for both segments: 20mm + 20mm = 40mm total
            # With 2mm spacing, expect ~20 points
            assert (
                len(points) >= 18
            ), f"Expected at least 18 points for L-shaped polyline, got {len(points)}"

            # Should start at origin and end at (20, 20)
            assert points[0]["x"] == pytest.approx(0.0, abs=0.1)
            assert points[0]["y"] == pytest.approx(0.0, abs=0.1)
            assert points[-1]["x"] == pytest.approx(20.0, abs=0.1)
            assert points[-1]["y"] == pytest.approx(20.0, abs=0.1)

        finally:
            dxf_path.unlink()

    def test_flask_dxf_straight_segments(self):
        """Test the actual flask.dxf file to verify straight segment handling."""
        flask_dxf = Path("examples/flask.dxf")
        if not flask_dxf.exists():
            pytest.skip("Flask DXF file not found")

        # Parse the flask DXF
        iterator = PointIteratorFactory.create_iterator(str(flask_dxf), dot_spacing=2.0)
        points = list(iterator.iterate_points(flask_dxf))

        print(f"Flask DXF generated {len(points)} points")

        # The flask should have both straight and curved segments
        assert (
            len(points) > 50
        ), f"Expected substantial points for flask, got {len(points)}"

        # Check that we have points distributed across the flask shape
        x_coords = [p["x"] for p in points]
        y_coords = [p["y"] for p in points]

        x_range = max(x_coords) - min(x_coords)
        y_range = max(y_coords) - min(y_coords)

        print(f"Flask dimensions: {x_range:.1f}mm x {y_range:.1f}mm")

        # Flask should span a reasonable area
        assert (
            x_range > 15
        ), f"Flask should span more than 15mm horizontally, got {x_range:.1f}mm"
        assert (
            y_range > 20
        ), f"Flask should span more than 20mm vertically, got {y_range:.1f}mm"
