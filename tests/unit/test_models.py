"""Unit tests for data models."""

import pytest

from svg_welder.core.models import WeldPath, WeldPoint


class TestWeldPoint:
    """Test cases for WeldPoint model."""

    def test_valid_weld_point_creation(self):
        """Test creating a valid weld point."""
        point = WeldPoint(x=10.5, y=20.3, weld_type='normal')
        assert point.x == 10.5
        assert point.y == 20.3
        assert point.weld_type == 'normal'

    def test_weld_point_with_light_type(self):
        """Test creating a weld point with light type."""
        point = WeldPoint(x=0.0, y=0.0, weld_type='light')
        assert point.weld_type == 'light'

    def test_weld_point_with_stop_type(self):
        """Test creating a weld point with stop type."""
        point = WeldPoint(x=5.0, y=5.0, weld_type='stop')
        assert point.weld_type == 'stop'

    def test_invalid_weld_type_raises_error(self):
        """Test that invalid weld type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid weld_type: invalid"):
            WeldPoint(x=0.0, y=0.0, weld_type='invalid')

    def test_weld_point_equality(self):
        """Test weld point equality comparison."""
        point1 = WeldPoint(x=1.0, y=2.0, weld_type='normal')
        point2 = WeldPoint(x=1.0, y=2.0, weld_type='normal')
        point3 = WeldPoint(x=1.0, y=2.0, weld_type='light')
        
        assert point1 == point2
        assert point1 != point3


class TestWeldPath:
    """Test cases for WeldPath model."""

    def test_valid_weld_path_creation(self):
        """Test creating a valid weld path."""
        points = [
            WeldPoint(x=0.0, y=0.0, weld_type='normal'),
            WeldPoint(x=10.0, y=10.0, weld_type='normal')
        ]
        path = WeldPath(points=points, weld_type='normal', svg_id='test_path')
        
        assert len(path.points) == 2
        assert path.weld_type == 'normal'
        assert path.svg_id == 'test_path'
        assert path.pause_message is None

    def test_weld_path_with_pause_message(self):
        """Test creating a weld path with pause message."""
        points = [WeldPoint(x=0.0, y=0.0, weld_type='stop')]
        path = WeldPath(
            points=points, 
            weld_type='stop', 
            svg_id='stop_path',
            pause_message='Check quality'
        )
        
        assert path.pause_message == 'Check quality'

    def test_empty_points_raises_error(self):
        """Test that empty points list raises ValueError."""
        with pytest.raises(ValueError, match="WeldPath must contain at least one point"):
            WeldPath(points=[], weld_type='normal', svg_id='test')

    def test_invalid_weld_type_raises_error(self):
        """Test that invalid weld type raises ValueError."""
        points = [WeldPoint(x=0.0, y=0.0, weld_type='normal')]
        with pytest.raises(ValueError, match="Invalid weld_type: invalid"):
            WeldPath(points=points, weld_type='invalid', svg_id='test')

    def test_empty_svg_id_raises_error(self):
        """Test that empty svg_id raises ValueError."""
        points = [WeldPoint(x=0.0, y=0.0, weld_type='normal')]
        with pytest.raises(ValueError, match="WeldPath must have a valid svg_id"):
            WeldPath(points=points, weld_type='normal', svg_id='')

    def test_point_count_property(self):
        """Test point_count property."""
        points = [
            WeldPoint(x=0.0, y=0.0, weld_type='normal'),
            WeldPoint(x=10.0, y=10.0, weld_type='normal'),
            WeldPoint(x=20.0, y=20.0, weld_type='normal')
        ]
        path = WeldPath(points=points, weld_type='normal', svg_id='test')
        
        assert path.point_count == 3

    def test_get_bounds_single_point(self):
        """Test get_bounds with single point."""
        points = [WeldPoint(x=5.0, y=10.0, weld_type='normal')]
        path = WeldPath(points=points, weld_type='normal', svg_id='test')
        
        bounds = path.get_bounds()
        assert bounds == (5.0, 10.0, 5.0, 10.0)

    def test_get_bounds_multiple_points(self):
        """Test get_bounds with multiple points."""
        points = [
            WeldPoint(x=0.0, y=5.0, weld_type='normal'),
            WeldPoint(x=10.0, y=0.0, weld_type='normal'),
            WeldPoint(x=5.0, y=15.0, weld_type='normal')
        ]
        path = WeldPath(points=points, weld_type='normal', svg_id='test')
        
        bounds = path.get_bounds()
        assert bounds == (0.0, 0.0, 10.0, 15.0)

    def test_get_bounds_empty_points(self):
        """Test get_bounds with empty points (should not happen due to validation)."""
        # This test is for completeness, though it shouldn't occur in practice
        path = WeldPath.__new__(WeldPath)  # Bypass __init__ validation
        path.points = []
        path.weld_type = 'normal'
        path.svg_id = 'test'
        path.pause_message = None
        
        bounds = path.get_bounds()
        assert bounds == (0.0, 0.0, 0.0, 0.0)
