"""Tests for data models."""

import pytest
import math

from microweldr.core.data_models import (
    Point,
    WeldType,
    WeldPath,
    LineEntity,
    ArcEntity,
    CircleEntity,
    ValidationResult,
    ProcessingStats,
)


class TestPoint:
    """Test Point data model."""

    def test_point_creation(self):
        """Test point creation."""
        p = Point(1.0, 2.0)
        assert p.x == 1.0
        assert p.y == 2.0

    def test_point_validation(self):
        """Test point validation."""
        with pytest.raises(ValueError):
            Point("invalid", 2.0)

        with pytest.raises(ValueError):
            Point(1.0, "invalid")

    def test_point_distance(self):
        """Test distance calculation."""
        p1 = Point(0.0, 0.0)
        p2 = Point(3.0, 4.0)
        assert p1.distance_to(p2) == 5.0

    def test_point_arithmetic(self):
        """Test point arithmetic operations."""
        p1 = Point(1.0, 2.0)
        p2 = Point(3.0, 4.0)

        p3 = p1 + p2
        assert p3.x == 4.0
        assert p3.y == 6.0

        p4 = p2 - p1
        assert p4.x == 2.0
        assert p4.y == 2.0


class TestWeldPath:
    """Test WeldPath data model."""

    def test_weld_path_creation(self):
        """Test weld path creation."""
        points = [Point(0, 0), Point(1, 1)]
        path = WeldPath(points, WeldType.NORMAL)

        assert len(path.points) == 2
        assert path.weld_type == WeldType.NORMAL

    def test_weld_path_validation(self):
        """Test weld path validation."""
        # Empty points should raise error
        with pytest.raises(ValueError):
            WeldPath([])

        # Single point should raise error
        with pytest.raises(ValueError):
            WeldPath([Point(0, 0)])

    def test_weld_path_length(self):
        """Test path length calculation."""
        points = [Point(0, 0), Point(3, 4), Point(6, 8)]
        path = WeldPath(points)

        # Length should be 5 + 5 = 10
        assert path.length == 10.0

    def test_weld_path_bounds(self):
        """Test bounding box calculation."""
        points = [Point(1, 2), Point(5, 1), Point(3, 6)]
        path = WeldPath(points)

        min_point, max_point = path.bounds
        assert min_point.x == 1
        assert min_point.y == 1
        assert max_point.x == 5
        assert max_point.y == 6


class TestCADEntities:
    """Test CAD entity models."""

    def test_line_entity(self):
        """Test line entity."""
        line = LineEntity(layer="test_layer", start=Point(0, 0), end=Point(3, 4))

        assert line.length == 5.0
        assert not line.is_construction

        weld_path = line.to_weld_path()
        # Line length is 5mm, with default 2mm spacing should generate 3 points: 0, 2.5, 5mm
        assert (
            len(weld_path.points) >= 2
        ), f"Expected at least 2 points, got {len(weld_path.points)}"
        assert (
            len(weld_path.points) == 3
        ), f"5mm line with 2mm spacing should generate 3 points, got {len(weld_path.points)}"
        assert weld_path.weld_type == WeldType.NORMAL

        # Verify interpolated points are correct
        points = weld_path.points
        assert points[0].x == 0.0 and points[0].y == 0.0  # Start point
        assert points[-1].x == 3.0 and points[-1].y == 4.0  # End point

    def test_construction_layer_detection(self):
        """Test construction layer detection."""
        line = LineEntity(
            layer="construction_layer", start=Point(0, 0), end=Point(1, 1)
        )

        assert line.is_construction

    def test_arc_entity(self):
        """Test arc entity."""
        arc = ArcEntity(
            layer="test_layer",
            center=Point(0, 0),
            radius=5.0,
            start_angle=0,
            end_angle=90,
        )

        assert arc.radius == 5.0

        weld_path = arc.to_weld_path(segments=4)
        assert len(weld_path.points) == 5  # 4 segments + 1

    def test_arc_validation(self):
        """Test arc validation."""
        with pytest.raises(ValueError):
            ArcEntity(
                layer="test",
                center=Point(0, 0),
                radius=-1.0,  # Invalid radius
                start_angle=0,
                end_angle=90,
            )

    def test_circle_entity(self):
        """Test circle entity."""
        circle = CircleEntity(layer="test_layer", center=Point(0, 0), radius=5.0)

        weld_path = circle.to_weld_path(segments=36)
        assert len(weld_path.points) == 37  # 36 segments + close to start

        # First and last points should be the same (closed circle)
        assert weld_path.points[0].x == pytest.approx(weld_path.points[-1].x)
        assert weld_path.points[0].y == pytest.approx(weld_path.points[-1].y)


class TestValidationResult:
    """Test ValidationResult model."""

    def test_validation_result(self):
        """Test validation result."""
        result = ValidationResult(True, "All good")
        assert result.is_valid
        assert result.message == "All good"
        assert len(result.warnings) == 0
        assert len(result.errors) == 0

    def test_add_warning(self):
        """Test adding warnings."""
        result = ValidationResult(True, "OK")
        result.add_warning("Minor issue")

        assert len(result.warnings) == 1
        assert result.warnings[0] == "Minor issue"
        assert result.is_valid  # Should still be valid

    def test_add_error(self):
        """Test adding errors."""
        result = ValidationResult(True, "OK")
        result.add_error("Major issue")

        assert len(result.errors) == 1
        assert result.errors[0] == "Major issue"
        assert not result.is_valid  # Should become invalid


class TestProcessingStats:
    """Test ProcessingStats model."""

    def test_processing_stats(self):
        """Test processing statistics."""
        stats = ProcessingStats()
        assert stats.files_processed == 0
        assert stats.total_paths == 0
        assert stats.total_points == 0
        assert stats.normal_welds == 0
        assert stats.frangible_welds == 0
