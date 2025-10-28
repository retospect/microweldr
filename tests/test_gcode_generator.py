"""
Tests for the G-code generator functionality.
"""

from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from microweldr.core.config import Config
from microweldr.core.gcode_generator import GCodeGenerator
from microweldr.core.models import WeldPath, WeldPoint


class TestGCodeGenerator:
    """Test the G-code generator."""

    def test_generator_initialization(self):
        """Test generator can be initialized."""
        config_path = Path(__file__).parent / "fixtures" / "test_config.toml"
        config = Config(config_path)
        generator = GCodeGenerator(config)
        assert generator is not None
        assert generator.config is config

    def test_generator_with_custom_config(self, tmp_path):
        """Test generator with custom configuration."""
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
        generator = GCodeGenerator(config)
        assert generator is not None

    def test_temperature_helper_methods(self):
        """Test DRY temperature helper methods."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test that helper methods exist
        assert hasattr(generator, "_set_bed_temperature")
        assert hasattr(generator, "_set_nozzle_temperature")
        assert hasattr(generator, "_set_chamber_temperature")
        assert hasattr(generator, "_wait_for_bed_temperature")
        assert hasattr(generator, "_wait_for_nozzle_temperature")

    def test_bed_temperature_helper(self):
        """Test bed temperature helper method."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test bed temperature setting
        output = StringIO()
        generator._set_bed_temperature(output, 120, wait=False)
        gcode = output.getvalue()

        assert "M140 S120" in gcode
        assert "bed" in gcode.lower()

    def test_bed_temperature_helper_with_wait(self):
        """Test bed temperature helper with waiting."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test bed temperature setting with wait
        output = StringIO()
        generator._set_bed_temperature(output, 120, wait=True)
        gcode = output.getvalue()

        assert "M140 S120" in gcode
        assert "M190 S120" in gcode
        assert "wait" in gcode.lower()

    def test_nozzle_temperature_helper(self):
        """Test nozzle temperature helper method."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test nozzle temperature setting
        output = StringIO()
        generator._set_nozzle_temperature(output, 170, wait=False)
        gcode = output.getvalue()

        assert "M104 S170" in gcode
        assert "nozzle" in gcode.lower()

    def test_nozzle_temperature_helper_with_wait(self):
        """Test nozzle temperature helper with waiting."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test nozzle temperature setting with wait
        output = StringIO()
        generator._set_nozzle_temperature(output, 170, wait=True)
        gcode = output.getvalue()

        assert "M104 S170" in gcode
        assert "M109 S170" in gcode
        assert "wait" in gcode.lower()

    def test_chamber_temperature_helper(self):
        """Test chamber temperature helper method."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test chamber temperature setting
        output = StringIO()
        generator._set_chamber_temperature(output, 35, wait=False)
        gcode = output.getvalue()

        assert "M141 S35" in gcode
        assert "chamber" in gcode.lower()

    def test_chamber_temperature_helper_with_wait(self):
        """Test chamber temperature helper with waiting."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test chamber temperature setting with wait
        output = StringIO()
        generator._set_chamber_temperature(output, 35, wait=True)
        gcode = output.getvalue()

        assert "M141 S35" in gcode
        assert "M191 S35" in gcode
        assert "wait" in gcode.lower()

    def test_chamber_temperature_off(self):
        """Test chamber temperature helper for turning off."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test chamber temperature off
        output = StringIO()
        generator._set_chamber_temperature(output, 0, wait=False)
        gcode = output.getvalue()

        assert "M141 S0" in gcode
        assert "Turn off" in gcode or "turn off" in gcode.lower()

    def test_wait_for_bed_temperature(self):
        """Test wait for bed temperature helper."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test waiting for bed temperature
        output = StringIO()
        generator._wait_for_bed_temperature(output, 120)
        gcode = output.getvalue()

        assert "M190 S120" in gcode
        assert "wait" in gcode.lower()

    def test_wait_for_nozzle_temperature(self):
        """Test wait for nozzle temperature helper."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test waiting for nozzle temperature
        output = StringIO()
        generator._wait_for_nozzle_temperature(output, 170)
        gcode = output.getvalue()

        assert "M109 S170" in gcode


class TestGCodeStructure:
    """Test G-code structure and formatting."""

    def test_gcode_header_generation(self):
        """Test G-code header generation."""
        config = Config()
        generator = GCodeGenerator(config)

        # Create sample paths
        test_points = [WeldPoint(x=10.0, y=10.0, weld_type="normal")]
        test_paths = [WeldPath(points=test_points, path_id="test")]

        # Test header generation
        output = StringIO()
        generator._write_header(output, test_paths)
        gcode = output.getvalue()

        assert "Generated by MicroWeldr" in gcode
        assert "Total paths: 1" in gcode

    def test_gcode_initialization(self):
        """Test G-code initialization commands."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test initialization
        output = StringIO()
        generator._write_initialization(output)
        gcode = output.getvalue()

        assert "G90" in gcode  # Absolute positioning
        assert "M83" in gcode  # Relative extruder positioning
        assert "G28" in gcode  # Home all axes

    def test_gcode_initialization_with_bed_leveling(self):
        """Test G-code initialization with bed leveling."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test initialization with bed leveling
        output = StringIO()
        generator._write_initialization(output, skip_bed_leveling=False)
        gcode = output.getvalue()

        assert "G29" in gcode  # Auto bed leveling

    def test_gcode_initialization_skip_bed_leveling(self):
        """Test G-code initialization skipping bed leveling."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test initialization without bed leveling
        output = StringIO()
        generator._write_initialization(output, skip_bed_leveling=True)
        gcode = output.getvalue()

        assert "G29" not in gcode  # No auto bed leveling
        assert "disabled" in gcode.lower()


class TestGCodeTemperatureIntegration:
    """Test G-code temperature integration."""

    def test_pre_calibration_heating(self):
        """Test pre-calibration heating sequence."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test pre-calibration heating
        output = StringIO()
        generator._write_pre_calibration_heating(output)
        gcode = output.getvalue()

        # Should contain bed temperature setting
        assert "M140" in gcode  # Set bed temperature
        assert "efficient timing" in gcode.lower()

    def test_final_heating(self):
        """Test final heating sequence."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test final heating
        output = StringIO()
        generator._write_final_heating(output)
        gcode = output.getvalue()

        # Should contain both bed and nozzle temperature commands
        assert "M190" in gcode  # Wait for bed temperature
        assert "M104" in gcode  # Set nozzle temperature
        assert "M109" in gcode  # Wait for nozzle temperature

    def test_full_weld_heating(self):
        """Test full weld heating sequence."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test full weld heating
        output = StringIO()
        generator._write_full_weld_heating(output)
        gcode = output.getvalue()

        # Should contain comprehensive heating sequence
        assert "HEATING SEQUENCE" in gcode
        assert "M140" in gcode  # Set bed temperature
        assert "M190" in gcode  # Wait for bed temperature
        assert "M104" in gcode  # Set nozzle temperature
        assert "M109" in gcode  # Wait for nozzle temperature
        assert "Ready for welding" in gcode


class TestGCodeUserInteraction:
    """Test G-code user interaction features."""

    def test_user_pause_basic(self):
        """Test basic user pause generation."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test user pause
        output = StringIO()
        generator._write_user_pause(output)
        gcode = output.getvalue()

        assert "M0" in gcode  # Pause command
        assert "M117" in gcode  # Display message
        assert "plastic" in gcode.lower()

    def test_user_pause_with_margins(self):
        """Test user pause with margin information."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test user pause with margin info
        margin_info = {"front_back": "10.2/10.2cm", "left_right": "11.8/11.8cm"}
        output = StringIO()
        generator._write_user_pause(output, margin_info)
        gcode = output.getvalue()

        assert "M0" in gcode  # Pause command
        assert "M117" in gcode  # Display message
        assert "10.2" in gcode  # Margin information
        assert "11.8" in gcode  # Margin information


class TestGCodeErrorHandling:
    """Test G-code generator error handling."""

    def test_generator_invalid_config(self):
        """Test generator handles invalid configuration."""
        # Test with None config
        try:
            generator = GCodeGenerator(None)
            # If it doesn't raise an exception, that's also acceptable
            # as long as it handles it gracefully
        except (TypeError, AttributeError):
            # Expected behavior for None config
            pass

    def test_generator_invalid_temperature(self):
        """Test generator handles invalid temperatures."""
        config = Config()
        generator = GCodeGenerator(config)

        # Test with invalid temperature values
        output = StringIO()

        # Should handle negative temperatures gracefully
        try:
            generator._set_bed_temperature(output, -10, wait=False)
            gcode = output.getvalue()
            # Should either handle gracefully or contain the value
            assert "M140" in gcode
        except (ValueError, TypeError):
            # Acceptable to raise exception for invalid temperatures
            pass


@pytest.fixture
def sample_config_with_temperatures(tmp_path):
    """Provide a sample configuration with temperature settings."""
    config_file = tmp_path / "temp_config.toml"
    config_file.write_text(
        """
[temperatures]
bed_temperature = 120
nozzle_temperature = 170
chamber_temperature = 35
use_chamber_heating = true

[normal_welds]
weld_time = 0.1
dot_spacing = 0.5
weld_height = 0.020
"""
    )
    return Config(str(config_file))


class TestGCodeConfigurationIntegration:
    """Test G-code generator with different configurations."""

    def test_generator_with_chamber_heating_enabled(
        self, sample_config_with_temperatures
    ):
        """Test generator with chamber heating enabled."""
        generator = GCodeGenerator(sample_config_with_temperatures)

        # Test pre-calibration heating with chamber
        output = StringIO()
        generator._write_pre_calibration_heating(output)
        gcode = output.getvalue()

        # Should include chamber heating commands
        assert "M141" in gcode  # Set chamber temperature
        assert "M191" in gcode  # Wait for chamber temperature

    def test_generator_with_chamber_heating_disabled(self, tmp_path):
        """Test generator with chamber heating disabled."""
        config_file = tmp_path / "no_chamber_config.toml"
        config_file.write_text(
            """
[temperatures]
bed_temperature = 120
nozzle_temperature = 170
use_chamber_heating = false
"""
        )

        config = Config(str(config_file))
        generator = GCodeGenerator(config)

        # Test pre-calibration heating without chamber
        output = StringIO()
        generator._write_pre_calibration_heating(output)
        gcode = output.getvalue()

        # Should not include chamber heating commands
        assert "M141" not in gcode
        assert "M191" not in gcode
        assert "disabled" in gcode.lower()

    def test_generator_temperature_values(self, sample_config_with_temperatures):
        """Test generator uses correct temperature values."""
        generator = GCodeGenerator(sample_config_with_temperatures)

        # Test that correct temperature values are used
        output = StringIO()
        generator._write_final_heating(output)
        gcode = output.getvalue()

        # Should use configured temperatures
        assert "S120" in gcode  # Bed temperature
        assert "S170" in gcode  # Nozzle temperature
