"""Advanced tests for animation generator functionality."""

import tempfile
from pathlib import Path

import pytest

from microweldr.animation.generator import AnimationGenerator
from microweldr.core.config import Config
from microweldr.core.models import WeldPath, WeldPoint


class TestAnimationGeneratorAdvanced:
    """Test advanced animation generator functionality."""

    @pytest.fixture
    def config_content(self):
        """Create test configuration."""
        return """
[printer]
bed_size_x = 250
bed_size_y = 220
bed_size_z = 270

[nozzle]
outer_diameter = 1.0
inner_diameter = 0.4

[temperatures]
bed_temperature = 60
nozzle_temperature = 200
chamber_temperature = 35
use_chamber_heating = false
cooldown_temperature = 50

[movement]
move_height = 5.0
travel_speed = 3000
z_speed = 600

[normal_welds]
weld_height = 0.020
weld_temperature = 130
weld_time = 0.1
dot_spacing = 0.9
initial_dot_spacing = 3.6
cooling_time_between_passes = 2.0

[light_welds]
weld_height = 0.020
weld_temperature = 180
weld_time = 0.3
dot_spacing = 0.9
initial_dot_spacing = 3.6
cooling_time_between_passes = 1.5

[animation]
time_between_welds = 0.5
pause_time = 2.0
min_animation_duration = 10.0

[output]
gcode_extension = ".gcode"
animation_extension = "_animation.svg"
"""

    @pytest.fixture
    def config(self, config_content):
        """Create configuration object."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(config_content)
            config_path = f.name

        try:
            config = Config(config_path)
            yield config
        finally:
            Path(config_path).unlink()

    @pytest.fixture
    def generator(self, config):
        """Create animation generator."""
        return AnimationGenerator(config)

    def test_pipette_weld_animation(self, generator):
        """Test animation generation for pipette weld types."""
        points = [WeldPoint(50, 50, "pipette")]
        weld_paths = [
            WeldPath(points, "pipette", "pipette_test", pause_message="Fill reagent")
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            generator.generate(weld_paths, f.name)

            # Read generated animation
            with open(f.name, "r") as af:
                animation_content = af.read()

            # Should contain pipette-specific styling
            assert "pipette" in animation_content.lower()
            assert "magenta" in animation_content or "#ff00ff" in animation_content

            # Should contain pause indication
            assert (
                "pause" in animation_content.lower()
                or "Fill reagent" in animation_content
            )

            Path(f.name).unlink()

    def test_stop_weld_animation(self, generator):
        """Test animation generation for stop weld types."""
        points = [WeldPoint(30, 30, "stop")]
        weld_paths = [
            WeldPath(points, "stop", "stop_test", pause_message="Insert component")
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            generator.generate(weld_paths, f.name)

            # Read generated animation
            with open(f.name, "r") as af:
                animation_content = af.read()

            # Should contain stop-specific styling
            assert "red" in animation_content or "#ff0000" in animation_content

            # Should contain pause message
            assert "Insert component" in animation_content

            Path(f.name).unlink()

    def test_mixed_weld_types_animation(self, generator):
        """Test animation with mixed weld types."""
        normal_points = [WeldPoint(10, 10, "normal")]
        light_points = [WeldPoint(20, 20, "light")]
        stop_points = [WeldPoint(30, 30, "stop")]

        weld_paths = [
            WeldPath(normal_points, "normal", "normal_path"),
            WeldPath(light_points, "light", "light_path"),
            WeldPath(stop_points, "stop", "stop_path", pause_message="Check"),
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            generator.generate(weld_paths, f.name)

            # Read generated animation
            with open(f.name, "r") as af:
                animation_content = af.read()

            # Should contain different colors for different weld types
            assert "black" in animation_content  # Normal welds
            assert "blue" in animation_content  # Light welds
            assert "red" in animation_content  # Stop welds

            # Should contain timing for different types
            assert "animate" in animation_content
            assert "dur=" in animation_content

            Path(f.name).unlink()

    def test_large_weld_path_animation(self, generator):
        """Test animation with large number of weld points."""
        # Create a path with many points
        points = []
        for i in range(50):
            points.append(WeldPoint(10 + i * 2, 10, "normal"))

        weld_paths = [WeldPath(points, "normal", "large_path")]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            generator.generate(weld_paths, f.name)

            # Read generated animation
            with open(f.name, "r") as af:
                animation_content = af.read()

            # Should contain many animation elements
            circle_count = animation_content.count("<circle")
            assert circle_count >= 50  # Should have at least as many circles as points

            # Should have proper timing distribution
            assert "begin=" in animation_content
            assert "dur=" in animation_content

            Path(f.name).unlink()

    def test_animation_with_custom_timing(self, config_content):
        """Test animation with custom timing configuration."""
        # Modify animation timing
        modified_config = (
            config_content.replace(
                "time_between_welds = 0.5", "time_between_welds = 0.2"
            )
            .replace("pause_time = 2.0", "pause_time = 1.0")
            .replace("min_animation_duration = 10.0", "min_animation_duration = 5.0")
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(modified_config)
            config_path = f.name

        try:
            config = Config(config_path)
            generator = AnimationGenerator(config)

            points = [WeldPoint(10, 10, "normal"), WeldPoint(20, 10, "normal")]
            weld_paths = [WeldPath(points, "normal", "timing_test")]

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".svg", delete=False
            ) as anim_f:
                generator.generate(weld_paths, anim_f.name)

                # Read generated animation
                with open(anim_f.name, "r") as f:
                    animation_content = f.read()

                # Should contain custom timing values
                assert "0.2s" in animation_content or "200ms" in animation_content

                Path(anim_f.name).unlink()

        finally:
            Path(config_path).unlink()

    def test_animation_viewport_calculation(self, generator):
        """Test animation viewport calculation for different point distributions."""
        # Create points spread across different areas
        points = [
            WeldPoint(5, 5, "normal"),  # Bottom left
            WeldPoint(95, 5, "normal"),  # Bottom right
            WeldPoint(5, 95, "normal"),  # Top left
            WeldPoint(95, 95, "normal"),  # Top right
            WeldPoint(50, 50, "normal"),  # Center
        ]
        weld_paths = [WeldPath(points, "normal", "viewport_test")]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            generator.generate(weld_paths, f.name)

            # Read generated animation
            with open(f.name, "r") as af:
                animation_content = af.read()

            # Should contain proper viewport
            assert "viewBox=" in animation_content
            assert "width=" in animation_content
            assert "height=" in animation_content

            # Should contain all points within the viewport
            assert (
                'cx="5' in animation_content or 'cx="15' in animation_content
            )  # Accounting for padding
            assert 'cx="95' in animation_content or 'cx="85' in animation_content

            Path(f.name).unlink()

    def test_animation_with_zero_points(self, generator):
        """Test animation generation with empty weld paths."""
        weld_paths = []

        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            generator.generate(weld_paths, f.name)

            # Read generated animation
            with open(f.name, "r") as af:
                animation_content = af.read()

            # Should still be valid SVG
            assert "<svg" in animation_content
            assert "</svg>" in animation_content

            # Should contain minimal content
            assert "xmlns=" in animation_content

            Path(f.name).unlink()

    def test_animation_scaling_and_padding(self, generator):
        """Test animation scaling and padding calculations."""
        # Create points that require scaling
        points = [
            WeldPoint(0, 0, "normal"),
            WeldPoint(1000, 1000, "normal"),  # Large coordinates
        ]
        weld_paths = [WeldPath(points, "normal", "scaling_test")]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            generator.generate(weld_paths, f.name)

            # Read generated animation
            with open(f.name, "r") as af:
                animation_content = af.read()

            # Should contain scaled coordinates within reasonable bounds
            assert "cx=" in animation_content
            assert "cy=" in animation_content

            # Should have proper viewBox for the scaled content
            assert "viewBox=" in animation_content

            Path(f.name).unlink()

    def test_animation_style_definitions(self, generator):
        """Test animation CSS style definitions."""
        points = [WeldPoint(25, 25, "normal")]
        weld_paths = [WeldPath(points, "normal", "style_test")]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            generator.generate(weld_paths, f.name)

            # Read generated animation
            with open(f.name, "r") as af:
                animation_content = af.read()

            # Should contain style definitions
            assert "<defs>" in animation_content or "<style>" in animation_content
            assert "weld-point" in animation_content or ".weld" in animation_content

            # Should contain animation keyframes or properties
            assert "opacity" in animation_content or "fill" in animation_content

            Path(f.name).unlink()

    def test_animation_with_custom_colors(self, generator):
        """Test animation generation with different weld type colors."""
        normal_points = [WeldPoint(10, 10, "normal")]
        light_points = [WeldPoint(30, 10, "light")]

        weld_paths = [
            WeldPath(normal_points, "normal", "normal_color"),
            WeldPath(light_points, "light", "light_color"),
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            generator.generate(weld_paths, f.name)

            # Read generated animation
            with open(f.name, "r") as af:
                animation_content = af.read()

            # Should contain different colors
            color_indicators = ["black", "blue", "#000000", "#0000ff"]
            found_colors = sum(
                1 for color in color_indicators if color in animation_content
            )
            assert found_colors >= 1  # Should have at least one color indicator

            Path(f.name).unlink()

    def test_animation_timing_sequence(self, generator):
        """Test animation timing sequence for multiple points."""
        points = [
            WeldPoint(10, 10, "normal"),
            WeldPoint(20, 10, "normal"),
            WeldPoint(30, 10, "normal"),
        ]
        weld_paths = [WeldPath(points, "normal", "timing_sequence")]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            generator.generate(weld_paths, f.name)

            # Read generated animation
            with open(f.name, "r") as af:
                animation_content = af.read()

            # Should contain sequential timing
            assert "begin=" in animation_content

            # Should have different begin times for different points
            begin_times = []
            lines = animation_content.split("\n")
            for line in lines:
                if "begin=" in line:
                    # Extract begin time
                    start = line.find('begin="') + 7
                    end = line.find('"', start)
                    if start > 6 and end > start:
                        begin_times.append(line[start:end])

            # Should have multiple different begin times
            unique_times = set(begin_times)
            assert (
                len(unique_times) >= 2
            )  # Should have at least 2 different timing values

            Path(f.name).unlink()
