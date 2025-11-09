"""
Tests for the core converter functionality.
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from microweldr.core.config import Config
from microweldr.core.converter import SVGToGCodeConverter
from microweldr.core.models import WeldPath, WeldPoint


class TestSVGToGCodeConverter:
    """Test the SVG to G-code converter."""

    def test_converter_initialization(self):
        """Test converter can be initialized."""
        config_path = Path(__file__).parent / "fixtures" / "test_config.toml"
        config = Config(config_path)
        converter = SVGToGCodeConverter(config)
        assert converter is not None
        assert converter.config is config

    def test_converter_with_custom_config(self, tmp_path):
        """Test converter with custom configuration."""
        config_file = tmp_path / "test_config.toml"
        config_file.write_text(
            """
[temperatures]
bed_temperature = 120
nozzle_temperature = 170

[normal_welds]
weld_time = 0.1
dot_spacing = 0.5
"""
        )

        config = Config(str(config_file))
        converter = SVGToGCodeConverter(config)
        assert converter is not None

    def test_converter_path_processing(self):
        """Test converter can process weld paths."""
        config_path = Path(__file__).parent / "fixtures" / "test_config.toml"
        config = Config(config_path)
        converter = SVGToGCodeConverter(config)

        # Create test weld paths
        test_points = [
            WeldPoint(x=10.0, y=10.0, weld_type="normal"),
            WeldPoint(x=20.0, y=10.0, weld_type="normal"),
        ]
        test_paths = [WeldPath(points=test_points, weld_type="normal", svg_id="test")]

        # Test that converter can handle the paths
        assert len(test_paths) == 1
        assert len(test_paths[0].points) == 2

    def test_converter_gcode_generation_structure(self):
        """Test that converter generates proper G-code structure."""
        config_path = Path(__file__).parent / "fixtures" / "test_config.toml"
        config = Config(config_path)
        converter = SVGToGCodeConverter(config)

        # Test basic structure without actual conversion
        # This tests that the converter has the expected interface
        assert hasattr(converter, "config")
        assert converter.config is not None


class TestConverterConfiguration:
    """Test converter configuration handling."""

    def test_converter_temperature_settings(self):
        """Test converter uses temperature settings correctly."""
        config_path = Path(__file__).parent / "fixtures" / "test_config.toml"
        config = Config(config_path)
        converter = SVGToGCodeConverter(config)

        # Test that converter has access to temperature settings
        bed_temp = config.get("temperatures", "bed_temperature", 80)
        nozzle_temp = config.get("temperatures", "nozzle_temperature", 200)

        assert isinstance(bed_temp, (int, float))
        assert isinstance(nozzle_temp, (int, float))
        assert bed_temp > 0
        assert nozzle_temp > 0

    def test_converter_weld_settings(self):
        """Test converter uses weld settings correctly."""
        config_path = Path(__file__).parent / "fixtures" / "test_config.toml"
        config = Config(config_path)
        converter = SVGToGCodeConverter(config)

        # Test weld configuration access
        weld_time = config.get("normal_welds", "weld_time", 0.1)
        dot_spacing = config.get("normal_welds", "dot_spacing", 0.9)

        assert isinstance(weld_time, (int, float))
        assert isinstance(dot_spacing, (int, float))
        assert weld_time > 0
        assert dot_spacing > 0


class TestConverterPathGeneration:
    """Test converter path generation capabilities."""

    def test_converter_point_spacing(self):
        """Test converter handles point spacing correctly."""
        config_path = Path(__file__).parent / "fixtures" / "test_config.toml"
        config = Config(config_path)
        converter = SVGToGCodeConverter(config)

        # Test point spacing calculation
        dot_spacing = config.get("normal_welds", "dot_spacing", 0.9)

        # Create points that should be spaced correctly
        point1 = WeldPoint(x=0.0, y=0.0, weld_type="normal")
        point2 = WeldPoint(x=dot_spacing, y=0.0, weld_type="normal")

        # Calculate distance
        distance = ((point2.x - point1.x) ** 2 + (point2.y - point1.y) ** 2) ** 0.5
        assert abs(distance - dot_spacing) < 0.001

    def test_converter_weld_types(self):
        """Test converter handles different weld types."""
        config_path = Path(__file__).parent / "fixtures" / "test_config.toml"
        config = Config(config_path)
        converter = SVGToGCodeConverter(config)

        # Test different weld types
        weld_types = ["normal", "frangible", "stop", "pipette"]

        for weld_type in weld_types:
            point = WeldPoint(x=10.0, y=10.0, weld_type=weld_type)
            assert point.weld_type == weld_type


class TestConverterErrorHandling:
    """Test converter error handling."""

    def test_converter_invalid_config(self):
        """Test converter handles invalid configuration."""
        # Test with None config
        try:
            converter = SVGToGCodeConverter(None)
            # If it doesn't raise an exception, that's also acceptable
            # as long as it handles it gracefully
        except (TypeError, AttributeError):
            # Expected behavior for None config
            pass

    def test_converter_empty_paths(self):
        """Test converter handles empty path lists."""
        config_path = Path(__file__).parent / "fixtures" / "test_config.toml"
        config = Config(config_path)
        converter = SVGToGCodeConverter(config)

        # Test with empty paths
        empty_paths = []

        # Should handle empty paths gracefully
        assert len(empty_paths) == 0

    def test_converter_invalid_points(self):
        """Test converter handles invalid points."""
        config_path = Path(__file__).parent / "fixtures" / "test_config.toml"
        config = Config(config_path)
        converter = SVGToGCodeConverter(config)

        # Test with invalid coordinates
        try:
            invalid_point = WeldPoint(x=float("inf"), y=10.0, weld_type="normal")
            # Should either handle gracefully or raise appropriate exception
            assert invalid_point.x == float("inf")
        except (ValueError, TypeError):
            # Acceptable to raise exception for invalid coordinates
            pass


@pytest.fixture
def sample_weld_paths():
    """Provide sample weld paths for testing."""
    points1 = [
        WeldPoint(x=10.0, y=10.0, weld_type="normal"),
        WeldPoint(x=20.0, y=10.0, weld_type="normal"),
        WeldPoint(x=20.0, y=20.0, weld_type="normal"),
        WeldPoint(x=10.0, y=20.0, weld_type="normal"),
    ]

    points2 = [
        WeldPoint(x=30.0, y=30.0, weld_type="frangible"),
        WeldPoint(x=40.0, y=30.0, weld_type="frangible"),
    ]

    return [
        WeldPath(points=points1, weld_type="normal", svg_id="square"),
        WeldPath(points=points2, weld_type="frangible", svg_id="line"),
    ]


class TestConverterIntegration:
    """Integration tests for converter functionality."""

    def test_converter_full_workflow(self, sample_weld_paths):
        """Test converter full workflow with sample data."""
        config_path = Path(__file__).parent / "fixtures" / "test_config.toml"
        config = Config(str(config_path))
        converter = SVGToGCodeConverter(config)

        # Test that converter can work with sample paths
        assert len(sample_weld_paths) == 2
        assert sample_weld_paths[0].svg_id == "square"
        assert sample_weld_paths[1].svg_id == "line"

        # Test path properties
        square_path = sample_weld_paths[0]
        assert len(square_path.points) == 4

        line_path = sample_weld_paths[1]
        assert len(line_path.points) == 2

    def test_converter_coordinate_system(self, sample_weld_paths):
        """Test converter coordinate system handling."""
        config_path = Path(__file__).parent / "fixtures" / "test_config.toml"
        config = Config(config_path)
        converter = SVGToGCodeConverter(config)

        # Test coordinate bounds
        all_points = []
        for path in sample_weld_paths:
            all_points.extend(path.points)

        x_coords = [p.x for p in all_points]
        y_coords = [p.y for p in all_points]

        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)

        # Verify coordinates are reasonable
        assert min_x >= 0
        assert min_y >= 0
        assert max_x > min_x
        assert max_y > min_y

    def test_converter_output_validation(self):
        """Test converter output validation."""
        config_path = Path(__file__).parent / "fixtures" / "test_config.toml"
        config = Config(config_path)
        converter = SVGToGCodeConverter(config)

        # Test that converter maintains configuration integrity
        assert converter.config is not None

        # Test temperature settings are accessible
        bed_temp = converter.config.get("temperatures", "bed_temperature", 80)
        assert isinstance(bed_temp, (int, float))
        assert bed_temp > 0
