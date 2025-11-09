"""Integration tests for the full SVG to G-code workflow."""

import tempfile
from pathlib import Path

import pytest

from microweldr.animation.generator import AnimationGenerator
from microweldr.core.config import Config
from microweldr.core.converter import SVGToGCodeConverter


class TestFullWorkflow:
    """Integration tests for the complete workflow."""

    def create_temp_config(self) -> Path:
        """Create a temporary config file."""
        config_content = """
[printer]
bed_size_x = 250.0
bed_size_y = 210.0
max_z_height = 270.0

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
weld_time = 0.5
dot_spacing = 2.0
initial_dot_spacing = 8.0
cooling_time_between_passes = 2.0

[frangible_welds]
weld_height = 0.5
weld_temperature = 180
weld_time = 0.3
dot_spacing = 3.0
initial_dot_spacing = 12.0
cooling_time_between_passes = 1.5

[output]
gcode_extension = ".gcode"
animation_extension = "_animation.svg"

[animation]
time_between_welds = 0.1
pause_time = 3.0
min_animation_duration = 10.0
        """

        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False)
        temp_file.write(config_content)
        temp_file.close()
        return Path(temp_file.name)

    def create_temp_svg(self) -> Path:
        """Create a temporary SVG file."""
        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <line id="line1" x1="10" y1="10" x2="90" y2="10" stroke="black" stroke-width="2"/>
  <circle id="circle1" cx="50" cy="30" r="15" fill="none" stroke="blue" stroke-width="1"/>
  <circle id="stop1" cx="50" cy="50" r="2" fill="red" data-message="Check quality"/>
  <rect id="rect1" x="20" y="60" width="60" height="20" fill="none" stroke="black" stroke-width="1"/>
</svg>"""

        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False)
        temp_file.write(svg_content)
        temp_file.close()
        return Path(temp_file.name)

    def test_complete_svg_to_gcode_workflow(self):
        """Test the complete workflow from SVG to G-code."""
        config_path = self.create_temp_config()
        svg_path = self.create_temp_svg()

        try:
            # Initialize components
            config = Config(config_path)
            converter = SVGToGCodeConverter(config)

            # Parse SVG
            weld_paths = converter.parse_svg(svg_path)

            # Verify parsing results
            assert len(weld_paths) == 4  # line, circle, stop, rect

            # Check weld types
            path_types = {path.svg_id: path.weld_type for path in weld_paths}
            assert path_types["line1"] == "normal"
            assert path_types["circle1"] == "frangible"
            assert path_types["stop1"] == "stop"
            assert path_types["rect1"] == "normal"

            # Check pause message
            stop_path = next(p for p in weld_paths if p.svg_id == "stop1")
            assert stop_path.pause_message == "Check quality"

            # Generate G-code
            with tempfile.NamedTemporaryFile(
                suffix=".gcode", delete=False
            ) as gcode_file:
                gcode_path = Path(gcode_file.name)

            converter.generate_gcode(gcode_path)

            # Verify G-code file was created and has content
            assert gcode_path.exists()
            gcode_content = gcode_path.read_text()
            assert len(gcode_content) > 0

            # Check for expected G-code elements
            assert "G90" in gcode_content  # Absolute positioning
            assert "G28" in gcode_content  # Home
            assert "M140" in gcode_content  # Bed temperature
            assert "M104" in gcode_content  # Nozzle temperature
            assert "M0" in gcode_content  # User pause
            assert "Check quality" in gcode_content  # Custom pause message

            # Clean up G-code file
            gcode_path.unlink()

        finally:
            config_path.unlink()
            svg_path.unlink()

    def test_animation_generation(self):
        """Test animation generation."""
        config_path = self.create_temp_config()
        svg_path = self.create_temp_svg()

        try:
            # Initialize components
            config = Config(config_path)
            converter = SVGToGCodeConverter(config)
            animation_generator = AnimationGenerator(config)

            # Parse SVG
            weld_paths = converter.parse_svg(svg_path)

            # Generate animation
            with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as anim_file:
                anim_path = Path(anim_file.name)

            animation_generator.generate_file(weld_paths, anim_path)

            # Verify animation file was created and has content
            assert anim_path.exists()
            anim_content = anim_path.read_text()
            assert len(anim_content) > 0

            # Check for expected animation elements
            assert "<svg" in anim_content
            assert "<animate" in anim_content
            assert "<circle" in anim_content
            assert "10mm" in anim_content  # Scale bar text

            # Clean up animation file
            anim_path.unlink()

        finally:
            config_path.unlink()
            svg_path.unlink()

    def test_converter_bounds_calculation(self):
        """Test bounds calculation for converter."""
        config_path = self.create_temp_config()
        svg_path = self.create_temp_svg()

        try:
            config = Config(config_path)
            converter = SVGToGCodeConverter(config)

            # Parse SVG
            converter.parse_svg(svg_path)

            # Check bounds calculation
            bounds = converter.get_bounds()
            assert len(bounds) == 4
            min_x, min_y, max_x, max_y = bounds

            # Bounds should be reasonable for our test SVG
            assert min_x >= 0
            assert min_y >= 0
            assert max_x > min_x
            assert max_y > min_y

        finally:
            config_path.unlink()
            svg_path.unlink()

    def test_convert_method(self):
        """Test the convenience convert method."""
        config_path = self.create_temp_config()
        svg_path = self.create_temp_svg()

        try:
            config = Config(config_path)
            converter = SVGToGCodeConverter(config)

            # Use convert method for complete workflow
            with tempfile.NamedTemporaryFile(
                suffix=".gcode", delete=False
            ) as gcode_file:
                gcode_path = Path(gcode_file.name)

            weld_paths = converter.convert(svg_path, gcode_path)

            # Verify results
            assert len(weld_paths) == 4
            assert gcode_path.exists()
            assert converter.path_count == 4

            # Clean up
            gcode_path.unlink()

        finally:
            config_path.unlink()
            svg_path.unlink()

    def test_error_handling_missing_svg(self):
        """Test error handling for missing SVG file."""
        config_path = self.create_temp_config()

        try:
            config = Config(config_path)
            converter = SVGToGCodeConverter(config)

            with pytest.raises(Exception):  # Should raise SVGParseError
                converter.parse_svg("nonexistent_file.svg")

        finally:
            config_path.unlink()

    def test_error_handling_no_paths_for_gcode(self):
        """Test error handling when generating G-code without parsed paths."""
        config_path = self.create_temp_config()

        try:
            config = Config(config_path)
            converter = SVGToGCodeConverter(config)

            with tempfile.NamedTemporaryFile(
                suffix=".gcode", delete=False
            ) as gcode_file:
                gcode_path = Path(gcode_file.name)

            # Try to generate G-code without parsing SVG first
            with pytest.raises(ValueError, match="No weld paths available"):
                converter.generate_gcode(gcode_path)

            # Clean up
            gcode_path.unlink()

        finally:
            config_path.unlink()


class TestExampleFiles:
    """Integration tests for example files in the examples directory."""

    def test_example_svg(self):
        """Test processing the basic example.svg file."""
        examples_dir = Path(__file__).parent.parent.parent / "examples"
        example_svg = examples_dir / "example.svg"
        config_file = examples_dir / "config.toml"

        # Skip if example files don't exist
        if not example_svg.exists() or not config_file.exists():
            pytest.skip("Example files not found")

        config = Config(config_file)
        converter = SVGToGCodeConverter(config)

        # Test parsing
        weld_paths = converter.parse_svg(example_svg)
        assert len(weld_paths) > 0

        # Test G-code generation
        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as gcode_file:
            gcode_path = Path(gcode_file.name)

        try:
            converter.generate_gcode(gcode_path)
            assert gcode_path.exists()

            # Verify G-code content
            gcode_content = gcode_path.read_text()
            assert "G90" in gcode_content  # Absolute positioning
            assert "G28" in gcode_content  # Home
            assert "Multi-pass welding" in gcode_content  # Multi-pass feature

        finally:
            gcode_path.unlink()

    def test_all_examples_complete_workflow(self):
        """Test complete workflow (SVG → G-code → Animation) for all examples."""
        examples_dir = Path(__file__).parent.parent.parent / "examples"
        config_file = examples_dir / "config.toml"

        if not config_file.exists():
            pytest.skip("Config file not found")

        # List of example SVG files to test
        example_files = [
            "example.svg",
            "comprehensive_sample.svg",
            "pause_examples.svg",
        ]

        config = Config(config_file)

        for svg_filename in example_files:
            svg_path = examples_dir / svg_filename

            if not svg_path.exists():
                continue  # Skip missing files

            converter = SVGToGCodeConverter(config)

            # Complete workflow test
            weld_paths = converter.parse_svg(svg_path)
            assert len(weld_paths) > 0, f"No weld paths found in {svg_filename}"

            # Generate G-code
            with tempfile.NamedTemporaryFile(
                suffix=".gcode", delete=False
            ) as gcode_file:
                gcode_path = Path(gcode_file.name)

            # Generate animation
            with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as anim_file:
                anim_path = Path(anim_file.name)

            try:
                converter.generate_gcode(gcode_path)

                from microweldr.animation.generator import AnimationGenerator

                animation_generator = AnimationGenerator(config)
                animation_generator.generate_file(weld_paths, anim_path)

                # Verify both files were created
                assert gcode_path.exists(), f"G-code not generated for {svg_filename}"
                assert anim_path.exists(), f"Animation not generated for {svg_filename}"

                # Basic content verification
                gcode_content = gcode_path.read_text()
                anim_content = anim_path.read_text()

                assert len(gcode_content) > 100, f"G-code too short for {svg_filename}"
                assert (
                    len(anim_content) > 100
                ), f"Animation too short for {svg_filename}"

            finally:
                gcode_path.unlink()
                anim_path.unlink()
