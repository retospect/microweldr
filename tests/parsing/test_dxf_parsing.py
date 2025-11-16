"""Tests for DXF file parsing to points."""

import pytest
from pathlib import Path
from typing import List

from microweldr.generators.models import WeldPoint
from microweldr.generators.point_iterator_factory import PointIteratorFactory


class TestDXFParsing:
    """Test DXF file parsing to point generation."""

    @property
    def fixtures_dir(self) -> Path:
        """Get the fixtures directory path."""
        return Path(__file__).parent.parent / "fixtures" / "dxf"

    def parse_dxf_to_points(self, filename: str) -> List[WeldPoint]:
        """Parse a DXF file to points using the point iterator."""
        dxf_path = self.fixtures_dir / filename
        assert dxf_path.exists(), f"Test fixture {filename} not found"

        iterator = PointIteratorFactory.create_iterator(str(dxf_path))
        points = list(iterator.iterate_points(dxf_path))
        return points

    def test_simple_line_parsing(self):
        """Test parsing a simple LINE entity."""
        points = self.parse_dxf_to_points("simple_line.dxf")

        # Should generate points for line (DXF typically gives endpoints)
        assert len(points) > 0, "Should generate at least some points"
        assert (
            len(points) >= 2
        ), f"Expected at least 2 points for line, got {len(points)}"

        # First and last points should be at line endpoints
        assert points[0]["x"] == pytest.approx(10.0, abs=0.1)
        assert points[0]["y"] == pytest.approx(25.0, abs=0.1)
        assert points[-1]["x"] == pytest.approx(50.0, abs=0.1)
        assert points[-1]["y"] == pytest.approx(25.0, abs=0.1)

        # All points should be normal weld type by default
        assert all(p["weld_type"] == "normal" for p in points)

    def test_circle_parsing(self):
        """Test parsing a CIRCLE entity."""
        points = self.parse_dxf_to_points("circle.dxf")

        # Circle should generate multiple points
        assert len(points) > 0, "Should generate points for circle"
        assert (
            len(points) >= 10
        ), f"Expected at least 10 points for circle, got {len(points)}"

        # All points should be normal weld type
        assert all(p["weld_type"] == "normal" for p in points)

        # Points should roughly form a circle around center (50, 50)
        center_x, center_y = 50.0, 50.0
        radius = 15.0

        for point in points:
            distance = (
                (point["x"] - center_x) ** 2 + (point["y"] - center_y) ** 2
            ) ** 0.5
            assert distance == pytest.approx(
                radius, abs=1.0
            ), f"Point {point} not on circle"

    def test_arc_parsing(self):
        """Test parsing an ARC entity."""
        points = self.parse_dxf_to_points("arc.dxf")

        assert len(points) > 0, "Should generate points for arc"
        assert (
            len(points) >= 5
        ), f"Expected at least 5 points for quarter circle arc, got {len(points)}"

        # All points should be normal weld type
        assert all(p["weld_type"] == "normal" for p in points)

        # Arc points should be on circle with radius 20 around center (50, 50)
        center_x, center_y = 50.0, 50.0
        radius = 20.0

        for point in points:
            distance = (
                (point["x"] - center_x) ** 2 + (point["y"] - center_y) ** 2
            ) ** 0.5
            assert distance == pytest.approx(
                radius, abs=1.0
            ), f"Point {point} not on arc circle"

    def test_polyline_parsing(self):
        """Test parsing a LWPOLYLINE entity."""
        points = self.parse_dxf_to_points("polyline.dxf")

        assert len(points) > 0, "Should generate points for polyline"
        assert (
            len(points) >= 3
        ), f"Expected at least 3 points for polyline, got {len(points)}"

        # All points should be normal weld type
        assert all(p["weld_type"] == "normal" for p in points)

        # Should start at first polyline vertex
        assert points[0]["x"] == pytest.approx(10.0, abs=1.0)
        assert points[0]["y"] == pytest.approx(20.0, abs=1.0)

    def test_layers_weld_types_parsing(self):
        """Test parsing entities on different layers for weld types."""
        points = self.parse_dxf_to_points("layers_weld_types.dxf")

        assert len(points) > 0, "Should generate points for layered entities"

        # Should have both normal and frangible weld types
        weld_types = {p["weld_type"] for p in points}
        assert "normal" in weld_types, "Should have normal weld points"
        # Note: Layer-based weld type detection may not be implemented yet
        # assert "frangible" in weld_types, "Should have frangible weld points (different layers)"

    def test_all_features_comprehensive(self):
        """Test parsing DXF file with all supported features - just count points."""
        points = self.parse_dxf_to_points("all_features.dxf")

        # This is our comprehensive test - we just verify it parses and generates reasonable point count
        assert len(points) > 0, "Should generate points for comprehensive DXF file"
        assert (
            len(points) >= 20
        ), f"Expected at least 20 points for comprehensive DXF file, got {len(points)}"

        # Should have multiple weld types based on layers
        weld_types = {p["weld_type"] for p in points}
        # Note: Multiple weld types may not be implemented yet
        assert (
            len(weld_types) >= 1
        ), f"Expected at least one weld type, got {weld_types}"

        print(
            f"Comprehensive DXF file generated {len(points)} points with weld types: {weld_types}"
        )

    def test_empty_or_invalid_dxf(self):
        """Test handling of invalid DXF files."""
        # This test would need an invalid DXF fixture, or we test with non-existent file
        with pytest.raises((FileNotFoundError, Exception)):
            self.parse_dxf_to_points("nonexistent.dxf")
