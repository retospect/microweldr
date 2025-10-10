"""Tests for the animation generator module."""

import tempfile
from pathlib import Path

import pytest

from svg_welder.animation.generator import AnimationGenerator
from svg_welder.core.config import Config
from svg_welder.core.models import WeldPath, WeldPoint


class TestAnimationGenerator:
    """Test cases for AnimationGenerator class."""

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
weld_height = 0.2
weld_temperature = 200
spot_dwell_time = 0.5
dot_spacing = 2.0
initial_dot_spacing = 8.0
cooling_time_between_passes = 2.0

[light_welds]
weld_height = 0.5
weld_temperature = 180
spot_dwell_time = 0.3
dot_spacing = 3.0
initial_dot_spacing = 12.0
cooling_time_between_passes = 1.5

[output]
gcode_extension = ".gcode"

[animation]
time_between_welds = 0.1
pause_time = 3.0
min_animation_duration = 10.0

[sequencing]
skip_base_distance = 5
        """
        config_path = self.create_temp_config(config_content)
        try:
            return Config(config_path)
        finally:
            config_path.unlink()

    def test_animation_generator_initialization(self):
        """Test animation generator initialization."""
        config = self.create_test_config()
        generator = AnimationGenerator(config)

        assert generator.config == config

    def test_generate_basic_animation(self):
        """Test generating basic animation."""
        config = self.create_test_config()
        generator = AnimationGenerator(config)

        weld_paths = [
            WeldPath(
                svg_id="test1",
                weld_type="normal",
                points=[
                    WeldPoint(10.0, 10.0, "normal"),
                    WeldPoint(20.0, 10.0, "normal"),
                    WeldPoint(30.0, 10.0, "normal"),
                ],
            )
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            output_path = Path(f.name)

        try:
            generator.generate_file(weld_paths, output_path)

            # Verify file was created
            assert output_path.exists()
            assert output_path.stat().st_size > 0

            # Read and verify content
            content = output_path.read_text()

            # Check for SVG structure
            assert '<?xml version="1.0" encoding="UTF-8"?>' in content
            assert "<svg" in content
            assert "</svg>" in content

            # Check for animation elements
            assert "animate" in content
            assert "circle" in content

            # Check for title and timing info
            assert "SVG Welding Animation" in content
            assert "Duration:" in content

        finally:
            if output_path.exists():
                output_path.unlink()

    def test_generate_animation_with_different_weld_types(self):
        """Test generating animation with different weld types."""
        config = self.create_test_config()
        generator = AnimationGenerator(config)

        weld_paths = [
            WeldPath(
                svg_id="normal1",
                weld_type="normal",
                points=[WeldPoint(10.0, 10.0, "normal")],
            ),
            WeldPath(
                svg_id="light1",
                weld_type="light",
                points=[WeldPoint(20.0, 10.0, "light")],
            ),
            WeldPath(
                svg_id="stop1",
                weld_type="stop",
                points=[WeldPoint(30.0, 10.0, "stop")],
                pause_message="Test pause",
            ),
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            output_path = Path(f.name)

        try:
            generator.generate_file(weld_paths, output_path)

            content = output_path.read_text()

            # Check for different colors/types
            assert 'fill="black"' in content  # Normal welds
            assert 'fill="blue"' in content  # Light welds
            assert 'fill="red"' in content  # Stop points

            # Check for pause message
            assert "Test pause" in content

        finally:
            if output_path.exists():
                output_path.unlink()

    def test_generate_animation_with_different_sequences(self):
        """Test generating animation with different weld sequences."""
        config = self.create_test_config()
        generator = AnimationGenerator(config)

        weld_paths = [
            WeldPath(
                svg_id="test1",
                weld_type="normal",
                points=[WeldPoint(float(i), 10.0, "normal") for i in range(10, 50, 5)],
            )
        ]

        sequences = ["linear", "binary", "farthest", "skip"]

        for sequence in sequences:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".svg", delete=False
            ) as f:
                output_path = Path(f.name)

            try:
                generator.generate_file(weld_paths, output_path, weld_sequence=sequence)

                # Verify file was created
                assert output_path.exists()
                content = output_path.read_text()

                # Should contain animation elements
                assert "animate" in content
                assert "circle" in content

            finally:
                if output_path.exists():
                    output_path.unlink()

    def test_generate_animation_with_legend(self):
        """Test that animation includes legend."""
        config = self.create_test_config()
        generator = AnimationGenerator(config)

        weld_paths = [
            WeldPath(
                svg_id="test1",
                weld_type="normal",
                points=[WeldPoint(10.0, 10.0, "normal")],
            )
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            output_path = Path(f.name)

        try:
            generator.generate_file(weld_paths, output_path)

            content = output_path.read_text()

            # Check for legend elements
            assert "Legend:" in content
            assert "Normal Welds" in content
            assert "Light Welds" in content
            assert "Stop Points" in content
            assert "10mm" in content  # Scale bar

        finally:
            if output_path.exists():
                output_path.unlink()

    def test_generate_animation_with_message_box(self):
        """Test that animation includes message box."""
        config = self.create_test_config()
        generator = AnimationGenerator(config)

        weld_paths = [
            WeldPath(
                svg_id="stop1",
                weld_type="stop",
                points=[WeldPoint(10.0, 10.0, "stop")],
                pause_message="Test notification",
            )
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            output_path = Path(f.name)

        try:
            generator.generate_file(weld_paths, output_path)

            content = output_path.read_text()

            # Check for message box
            assert 'id="message-box"' in content
            assert "Notifications:" in content
            assert "No active notifications" in content

        finally:
            if output_path.exists():
                output_path.unlink()

    def test_generate_empty_animation(self):
        """Test generating animation with no weld paths."""
        config = self.create_test_config()
        generator = AnimationGenerator(config)

        weld_paths = []

        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            output_path = Path(f.name)

        try:
            # Empty weld paths should not crash but may not generate content
            # The animation generator might skip generation for empty paths
            generator.generate_file(weld_paths, output_path)

            # File should exist (even if empty or minimal)
            assert output_path.exists()

        finally:
            if output_path.exists():
                output_path.unlink()

    def test_weld_order_generation_linear(self):
        """Test linear weld order generation."""
        config = self.create_test_config()
        generator = AnimationGenerator(config)

        # Test linear order
        points = [WeldPoint(float(i), 10.0, "normal") for i in range(5)]
        order = generator._generate_weld_order(points, "linear")

        # Linear should be [0, 1, 2, 3, 4]
        assert order == list(range(len(points)))

    def test_weld_order_generation_skip(self):
        """Test skip weld order generation."""
        config = self.create_test_config()
        generator = AnimationGenerator(config)

        # Test skip order with 10 points
        points = [WeldPoint(float(i), 10.0, "normal") for i in range(10)]
        order = generator._generate_weld_order(points, "skip")

        # Skip should start with every 5th point (0, 5), then fill gaps
        assert len(order) == len(points)
        assert 0 in order
        assert 5 in order

    def test_calculate_bounds(self):
        """Test bounds calculation."""
        config = self.create_test_config()
        generator = AnimationGenerator(config)

        weld_paths = [
            WeldPath(
                svg_id="test1",
                weld_type="normal",
                points=[
                    WeldPoint(10.0, 20.0, "normal"),
                    WeldPoint(50.0, 80.0, "normal"),
                    WeldPoint(30.0, 40.0, "normal"),
                ],
            )
        ]

        bounds = generator._calculate_bounds(weld_paths)

        # Should return (min_x, min_y, max_x, max_y)
        assert bounds == (10.0, 20.0, 50.0, 80.0)
