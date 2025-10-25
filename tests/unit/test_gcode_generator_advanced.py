"""Advanced tests for G-code generator functionality."""

import tempfile
from pathlib import Path

import pytest

from microweldr.core.config import Config
from microweldr.core.gcode_generator import GCodeGenerator
from microweldr.core.models import WeldPath, WeldPoint


class TestGCodeGeneratorAdvanced:
    """Test advanced G-code generator functionality."""

    @pytest.fixture
    def config_content(self):
        """Create test configuration."""
        return """
[printer]
bed_size_x = 250
bed_size_y = 220
bed_size_z = 270
layed_back_mode = false

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
        """Create G-code generator."""
        return GCodeGenerator(config)

    def test_layed_back_mode_initialization(self, config_content):
        """Test G-code generation with layed back mode."""
        # Enable layed back mode
        modified_config = config_content.replace(
            "layed_back_mode = false", "layed_back_mode = true"
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(modified_config)
            config_path = f.name

        try:
            config = Config(config_path)
            generator = GCodeGenerator(config)

            # Create simple weld path
            points = [WeldPoint(10, 10, "normal")]
            weld_paths = [WeldPath(points, "normal", "test")]

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".gcode", delete=False
            ) as gcode_f:
                generator.generate(weld_paths, gcode_f.name)

                # Read generated G-code
                with open(gcode_f.name, "r") as f:
                    gcode_content = f.read()

                # Should contain layed back mode warnings and setup
                assert "layed back mode" in gcode_content.lower()
                assert "G92 X0 Y0" in gcode_content  # Set current position as origin
                assert "M84 S0" in gcode_content  # Disable stepper timeout

                Path(gcode_f.name).unlink()

        finally:
            Path(config_path).unlink()

    def test_custom_weld_parameters(self, generator):
        """Test G-code generation with custom weld parameters."""
        # Create weld points with custom parameters
        points = [
            WeldPoint(
                10,
                10,
                "normal",
                custom_temp=160.0,
                custom_weld_time=0.5,
                custom_weld_height=0.030,
            ),
            WeldPoint(
                20,
                10,
                "normal",
                custom_temp=170.0,
                custom_weld_time=0.2,
                custom_weld_height=0.025,
            ),
        ]
        weld_paths = [WeldPath(points, "normal", "custom_test")]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".gcode", delete=False) as f:
            generator.generate_file(weld_paths, f.name)

            # Read generated G-code
            with open(f.name, "r") as gf:
                gcode_content = gf.read()

            # Should contain custom temperature changes
            assert "M104 S160" in gcode_content or "M109 S160" in gcode_content
            assert "M104 S170" in gcode_content or "M109 S170" in gcode_content

            # Should contain custom weld times (converted to milliseconds)
            assert "G4 P500" in gcode_content  # 0.5s = 500ms
            assert "G4 P200" in gcode_content  # 0.2s = 200ms

            # Should contain custom weld heights
            assert "Z0.030" in gcode_content
            assert "Z0.025" in gcode_content

            Path(f.name).unlink()

    def test_stop_weld_type(self, generator):
        """Test G-code generation with stop weld type."""
        points = [WeldPoint(10, 10, "stop")]
        weld_paths = [
            WeldPath(points, "stop", "stop_test", pause_message="Insert component")
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".gcode", delete=False) as f:
            generator.generate_file(weld_paths, f.name)

            # Read generated G-code
            with open(f.name, "r") as gf:
                gcode_content = gf.read()

            # Should contain pause command and message
            assert "M0" in gcode_content  # Pause command
            assert "M117" in gcode_content  # Display message command
            assert "Insert component" in gcode_content

            Path(f.name).unlink()

    def test_pipette_weld_type(self, generator):
        """Test G-code generation with pipette weld type."""
        points = [WeldPoint(15, 15, "pipette")]
        weld_paths = [
            WeldPath(
                points, "pipette", "pipette_test", pause_message="Fill with reagent"
            )
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".gcode", delete=False) as f:
            generator.generate_file(weld_paths, f.name)

            # Read generated G-code
            with open(f.name, "r") as gf:
                gcode_content = gf.read()

            # Should contain pipetting pause
            assert "M0" in gcode_content
            assert "Fill with reagent" in gcode_content
            assert "Pipetting stop" in gcode_content

            Path(f.name).unlink()

    def test_multipass_welding(self, generator):
        """Test multi-pass welding generation."""
        # Create points that will trigger multiple passes
        points = [
            WeldPoint(10, 10, "normal"),
            WeldPoint(20, 10, "normal"),
            WeldPoint(30, 10, "normal"),
            WeldPoint(40, 10, "normal"),
        ]
        weld_paths = [WeldPath(points, "normal", "multipass_test")]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".gcode", delete=False) as f:
            generator.generate_file(weld_paths, f.name)

            # Read generated G-code
            with open(f.name, "r") as gf:
                gcode_content = gf.read()

            # Should contain multiple pass indicators
            assert "Multi-pass welding" in gcode_content
            assert "Pass 1/" in gcode_content
            assert "Pass 2/" in gcode_content or "passes from" in gcode_content

            # Should contain cooling time between passes
            cooling_time = int(2.0 * 1000)  # 2 seconds in milliseconds
            assert f"G4 P{cooling_time}" in gcode_content

            Path(f.name).unlink()

    def test_chamber_heating_enabled(self, config_content):
        """Test G-code generation with chamber heating enabled."""
        # Enable chamber heating
        modified_config = config_content.replace(
            "use_chamber_heating = false", "use_chamber_heating = true"
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(modified_config)
            config_path = f.name

        try:
            config = Config(config_path)
            generator = GCodeGenerator(config)

            points = [WeldPoint(10, 10, "normal")]
            weld_paths = [WeldPath(points, "normal", "chamber_test")]

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".gcode", delete=False
            ) as gcode_f:
                generator.generate(weld_paths, gcode_f.name)

                # Read generated G-code
                with open(gcode_f.name, "r") as f:
                    gcode_content = f.read()

                # Should contain chamber heating commands
                assert "M141 S35" in gcode_content  # Set chamber temperature
                assert "M191 S35" in gcode_content  # Wait for chamber temperature
                assert "M141 S0" in gcode_content  # Turn off chamber at end

                Path(gcode_f.name).unlink()

        finally:
            Path(config_path).unlink()

    def test_mixed_weld_types(self, generator):
        """Test G-code generation with mixed weld types."""
        normal_points = [WeldPoint(10, 10, "normal")]
        light_points = [WeldPoint(20, 20, "light")]
        stop_points = [WeldPoint(30, 30, "stop")]

        weld_paths = [
            WeldPath(normal_points, "normal", "normal_path"),
            WeldPath(light_points, "light", "light_path"),
            WeldPath(stop_points, "stop", "stop_path", pause_message="Check alignment"),
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".gcode", delete=False) as f:
            generator.generate_file(weld_paths, f.name)

            # Read generated G-code
            with open(f.name, "r") as gf:
                gcode_content = gf.read()

            # Should contain temperature changes for different weld types
            assert (
                "M104 S130" in gcode_content or "M109 S130" in gcode_content
            )  # Normal weld temp
            assert (
                "M104 S180" in gcode_content or "M109 S180" in gcode_content
            )  # Light weld temp

            # Should contain pause for stop type
            assert "M0" in gcode_content
            assert "Check alignment" in gcode_content

            Path(f.name).unlink()

    def test_bed_leveling_skip(self, generator):
        """Test G-code generation with bed leveling skipped."""
        points = [WeldPoint(10, 10, "normal")]
        weld_paths = [WeldPath(points, "normal", "skip_leveling_test")]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".gcode", delete=False) as f:
            generator.generate(weld_paths, f.name, skip_bed_leveling=True)

            # Read generated G-code
            with open(f.name, "r") as gf:
                gcode_content = gf.read()

            # Should not contain bed leveling command
            assert "G29" not in gcode_content
            assert (
                "Bed leveling disabled" in gcode_content
                or "skip" in gcode_content.lower()
            )

            Path(f.name).unlink()

    def test_empty_weld_paths(self, generator):
        """Test G-code generation with empty weld paths."""
        weld_paths = []

        with tempfile.NamedTemporaryFile(mode="w", suffix=".gcode", delete=False) as f:
            generator.generate_file(weld_paths, f.name)

            # Read generated G-code
            with open(f.name, "r") as gf:
                gcode_content = gf.read()

            # Should still contain basic initialization and cleanup
            assert "G90" in gcode_content  # Absolute positioning
            assert "M83" in gcode_content  # Relative extruder positioning
            assert "M104 S0" in gcode_content  # Turn off nozzle at end

            Path(f.name).unlink()

    def test_path_level_custom_parameters(self, generator):
        """Test G-code generation with path-level custom parameters."""
        points = [WeldPoint(10, 10, "normal"), WeldPoint(20, 10, "normal")]
        weld_paths = [
            WeldPath(
                points,
                "normal",
                "path_custom_test",
                custom_temp=150.0,
                custom_weld_time=0.4,
                custom_weld_height=0.035,
            )
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".gcode", delete=False) as f:
            generator.generate_file(weld_paths, f.name)

            # Read generated G-code
            with open(f.name, "r") as gf:
                gcode_content = gf.read()

            # Should contain path-level custom parameters
            assert "M104 S150" in gcode_content or "M109 S150" in gcode_content
            assert "G4 P400" in gcode_content  # 0.4s = 400ms
            assert "Z0.035" in gcode_content

            Path(f.name).unlink()

    def test_point_overrides_path_parameters(self, generator):
        """Test that point-level parameters override path-level parameters."""
        points = [
            WeldPoint(10, 10, "normal", custom_temp=165.0),  # Point overrides path temp
            WeldPoint(20, 10, "normal"),  # Uses path-level parameters
        ]
        weld_paths = [
            WeldPath(
                points,
                "normal",
                "override_test",
                custom_temp=150.0,  # Path-level temperature
                custom_weld_time=0.4,
            )
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".gcode", delete=False) as f:
            generator.generate_file(weld_paths, f.name)

            # Read generated G-code
            with open(f.name, "r") as gf:
                gcode_content = gf.read()

            # Should contain both temperatures
            assert (
                "M104 S165" in gcode_content or "M109 S165" in gcode_content
            )  # Point override
            assert (
                "M104 S150" in gcode_content or "M109 S150" in gcode_content
            )  # Path level

            Path(f.name).unlink()
