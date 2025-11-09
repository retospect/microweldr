"""Tests for the SVG to G-code converter module."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from microweldr.core.config import Config
from microweldr.core.converter import SVGToGCodeConverter
from microweldr.core.models import WeldPath, WeldPoint


class TestSVGToGCodeConverter:
    """Test cases for SVGToGCodeConverter class."""

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
bed_size_y = 220.0
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
weld_height = 0.05
weld_temperature = 200
weld_time = 0.5
dot_spacing = 2.0
initial_dot_spacing = 8.0
cooling_time_between_passes = 2.0

[frangible_welds]
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

    def test_converter_initialization(self):
        """Test converter initialization."""
        config = self.create_test_config()
        converter = SVGToGCodeConverter(config)

        assert converter.config == config
        assert converter.svg_parser is not None
        assert converter.gcode_generator is not None

    def test_convert_basic_svg(self):
        """Test converting a basic SVG file."""
        config = self.create_test_config()
        converter = SVGToGCodeConverter(config)

        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <line x1="10" y1="10" x2="90" y2="10" stroke="black" stroke-width="2"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".gcode", delete=False
            ) as gcode_file:
                gcode_path = Path(gcode_file.name)

            # Test conversion
            converter.convert(svg_path, gcode_path)

            # Verify G-code file was created
            assert gcode_path.exists()
            assert gcode_path.stat().st_size > 0

            # Verify content contains expected G-code commands
            content = gcode_path.read_text()
            assert "G90" in content  # Absolute positioning
            assert "G28" in content  # Home axes
            assert "M104" in content or "M109" in content  # Set temperature

        finally:
            svg_path.unlink()
            if gcode_path.exists():
                gcode_path.unlink()

    def test_convert_circle_svg(self):
        """Test converting SVG with circle element."""
        config = self.create_test_config()
        converter = SVGToGCodeConverter(config)

        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="20" fill="none" stroke="blue" stroke-width="1"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".gcode", delete=False
            ) as gcode_file:
                gcode_path = Path(gcode_file.name)

            # Test conversion
            weld_paths = converter.convert(svg_path, gcode_path)

            # Verify G-code file was created
            assert gcode_path.exists()
            assert gcode_path.stat().st_size > 0

            # Verify weld paths were returned
            assert len(weld_paths) > 0
            assert (
                weld_paths[0].weld_type == "frangible"
            )  # Blue stroke = frangible weld

        finally:
            svg_path.unlink()
            if gcode_path.exists():
                gcode_path.unlink()

    def test_convert_rectangle_svg(self):
        """Test converting SVG with rectangle element."""
        config = self.create_test_config()
        converter = SVGToGCodeConverter(config)

        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <rect x="10" y="10" width="80" height="80" fill="none" stroke="black"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".gcode", delete=False
            ) as gcode_file:
                gcode_path = Path(gcode_file.name)

            # Test conversion
            weld_paths = converter.convert(svg_path, gcode_path)

            # Verify G-code file was created
            assert gcode_path.exists()
            assert gcode_path.stat().st_size > 0

            # Verify weld paths were returned
            assert len(weld_paths) > 0
            assert weld_paths[0].weld_type == "normal"  # Black stroke = normal weld

        finally:
            svg_path.unlink()
            if gcode_path.exists():
                gcode_path.unlink()

    def test_convert_with_skip_bed_leveling(self):
        """Test converting with bed leveling disabled."""
        config = self.create_test_config()
        converter = SVGToGCodeConverter(config)

        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <line x1="10" y1="10" x2="90" y2="10" stroke="black"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".gcode", delete=False
            ) as gcode_file:
                gcode_path = Path(gcode_file.name)

            # Test conversion with skip bed leveling
            converter.convert(svg_path, gcode_path, skip_bed_leveling=True)

            # Verify G-code file was created
            assert gcode_path.exists()

            # Verify bed leveling command is not present
            content = gcode_path.read_text()
            assert "G29" not in content  # Auto bed leveling should be skipped

        finally:
            svg_path.unlink()
            if gcode_path.exists():
                gcode_path.unlink()

    def test_convert_path_svg(self):
        """Test converting SVG with path element."""
        config = self.create_test_config()
        converter = SVGToGCodeConverter(config)

        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <path d="M 10 10 L 50 10 L 90 10" stroke="black" fill="none"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".gcode", delete=False
            ) as gcode_file:
                gcode_path = Path(gcode_file.name)

            # Test conversion
            weld_paths = converter.convert(svg_path, gcode_path)

            # Verify G-code file was created
            assert gcode_path.exists()
            assert gcode_path.stat().st_size > 0

            # Verify weld paths were returned
            assert len(weld_paths) > 0
            assert weld_paths[0].weld_type == "normal"  # Black stroke = normal weld

        finally:
            svg_path.unlink()
            if gcode_path.exists():
                gcode_path.unlink()

    def test_convert_invalid_svg_file(self):
        """Test converting an invalid SVG file."""
        config = self.create_test_config()
        converter = SVGToGCodeConverter(config)

        # Create invalid SVG
        invalid_svg = """This is not valid SVG content"""
        svg_path = self.create_test_svg(invalid_svg)

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".gcode", delete=False
            ) as gcode_file:
                gcode_path = Path(gcode_file.name)

            # Test should handle invalid SVG gracefully
            with pytest.raises(Exception):  # Should raise some kind of parsing error
                converter.convert(svg_path, gcode_path)

        finally:
            svg_path.unlink()
            if gcode_path.exists():
                gcode_path.unlink()

    def test_convert_nonexistent_file(self):
        """Test converting a nonexistent file."""
        config = self.create_test_config()
        converter = SVGToGCodeConverter(config)

        nonexistent_path = Path("/nonexistent/file.svg")

        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as gcode_file:
            gcode_path = Path(gcode_file.name)

        try:
            # Test should handle nonexistent file gracefully
            from microweldr.core.svg_parser import SVGParseError

            with pytest.raises(SVGParseError):
                converter.convert(nonexistent_path, gcode_path)
        finally:
            if gcode_path.exists():
                gcode_path.unlink()

    def test_get_bounds(self):
        """Test getting bounds of weld paths."""
        config = self.create_test_config()
        converter = SVGToGCodeConverter(config)

        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <line x1="10" y1="20" x2="90" y2="80" stroke="black"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".gcode", delete=False
            ) as gcode_file:
                gcode_path = Path(gcode_file.name)

            # Parse SVG and get bounds
            converter.parse_svg(svg_path)
            bounds = converter.get_bounds()

            # Should return (min_x, min_y, max_x, max_y)
            assert len(bounds) == 4
            assert bounds[0] <= bounds[2]  # min_x <= max_x
            assert bounds[1] <= bounds[3]  # min_y <= max_y

        finally:
            svg_path.unlink()
            if gcode_path.exists():
                gcode_path.unlink()

    def test_path_count(self):
        """Test getting path count."""
        config = self.create_test_config()
        converter = SVGToGCodeConverter(config)

        # Initially should be 0
        assert converter.path_count == 0

        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <line x1="10" y1="10" x2="90" y2="10" stroke="black"/>
  <circle cx="50" cy="50" r="20" fill="none" stroke="blue"/>
</svg>"""

        svg_path = self.create_test_svg(svg_content)

        try:
            # Parse SVG
            converter.parse_svg(svg_path)

            # Should now have 2 paths
            assert converter.path_count == 2

        finally:
            svg_path.unlink()
