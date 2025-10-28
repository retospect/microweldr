"""Unit tests for configuration management."""

import tempfile
from pathlib import Path

import pytest

from microweldr.core.config import Config, ConfigError


class TestConfig:
    """Test cases for Config class."""

    def create_temp_config(self, content: str) -> Path:
        """Create a temporary config file with given content."""
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False)
        temp_file.write(content)
        temp_file.close()
        return Path(temp_file.name)

    def test_valid_config_loading(self):
        """Test loading a valid configuration file."""
        config_content = """
[printer]
bed_size_x = 250.0
bed_size_y = 210.0

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

[light_welds]
weld_height = 0.05
weld_temperature = 180
weld_time = 0.3
dot_spacing = 3.0

[output]
gcode_extension = ".gcode"

[animation]
time_between_welds = 0.1
pause_time = 3.0
min_animation_duration = 10.0
        """

        config_path = self.create_temp_config(config_content)
        try:
            config = Config(config_path)

            assert config.get("temperatures", "bed_temperature") == 60
            assert config.get("movement", "move_height") == 5.0
            assert config.get("normal_welds", "dot_spacing") == 2.0
        finally:
            config_path.unlink()

    def test_missing_config_file_raises_error(self):
        """Test that missing config file raises ConfigError."""
        with pytest.raises(ConfigError, match="Configuration file .* not found"):
            Config("nonexistent_config.toml")

    def test_invalid_toml_raises_error(self):
        """Test that invalid TOML raises ConfigError."""
        invalid_content = """
[section
invalid toml content
        """

        config_path = self.create_temp_config(invalid_content)
        try:
            with pytest.raises(ConfigError, match="Invalid TOML configuration"):
                Config(config_path)
        finally:
            config_path.unlink()

    def test_get_with_default_value(self):
        """Test getting configuration value with default."""
        config_content = """
[test_section]
existing_key = "value"
        """

        config_path = self.create_temp_config(config_content)
        try:
            config = Config(config_path)

            # Existing key
            assert config.get("test_section", "existing_key") == "value"

            # Non-existing key with default
            assert config.get("test_section", "missing_key", "default") == "default"
        finally:
            config_path.unlink()

    def test_get_missing_key_without_default_raises_error(self):
        """Test that missing key without default raises ConfigError."""
        config_content = """
[test_section]
existing_key = "value"
        """

        config_path = self.create_temp_config(config_content)
        try:
            config = Config(config_path)

            with pytest.raises(ConfigError, match="Configuration key .* not found"):
                config.get("test_section", "missing_key")
        finally:
            config_path.unlink()

    def test_get_section(self):
        """Test getting entire configuration section."""
        config_content = """
[test_section]
key1 = "value1"
key2 = 42
key3 = true
        """

        config_path = self.create_temp_config(config_content)
        try:
            config = Config(config_path)

            section = config.get_section("test_section")
            assert section == {"key1": "value1", "key2": 42, "key3": True}
        finally:
            config_path.unlink()

    def test_get_missing_section_raises_error(self):
        """Test that missing section raises ConfigError."""
        config_content = """
[existing_section]
key = "value"
        """

        config_path = self.create_temp_config(config_content)
        try:
            config = Config(config_path)

            with pytest.raises(ConfigError, match="Configuration section .* not found"):
                config.get_section("missing_section")
        finally:
            config_path.unlink()

    def test_property_accessors(self):
        """Test property accessors for common sections."""
        config_content = """
[printer]
bed_size_x = 250.0

[temperatures]
bed_temperature = 60

[movement]
move_height = 5.0

[normal_welds]
dot_spacing = 2.0

[light_welds]
dot_spacing = 3.0

[output]
gcode_extension = ".gcode"

[animation]
time_between_welds = 0.1
        """

        config_path = self.create_temp_config(config_content)
        try:
            config = Config(config_path)

            assert config.printer["bed_size_x"] == 250.0
            assert config.temperatures["bed_temperature"] == 60
            assert config.movement["move_height"] == 5.0
            assert config.normal_welds["dot_spacing"] == 2.0
            assert config.light_welds["dot_spacing"] == 3.0
            assert config.output["gcode_extension"] == ".gcode"
            assert config.animation["time_between_welds"] == 0.1
        finally:
            config_path.unlink()

    def test_validation_success(self):
        """Test successful configuration validation."""
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
weld_height = 0.05
weld_temperature = 200
weld_time = 0.5
dot_spacing = 2.0
initial_dot_spacing = 8.0
cooling_time_between_passes = 2.0

[light_welds]
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
            config = Config(config_path)
            config.validate()  # Should not raise any exception
        finally:
            config_path.unlink()

    def test_validation_missing_section_uses_defaults(self):
        """Test that missing sections are filled with defaults."""
        config_content = """
[temperatures]
bed_temperature = 60
        """

        config_path = self.create_temp_config(config_content)
        try:
            config = Config(config_path)

            # Should not raise error - defaults are used
            config.validate()

            # Verify defaults are present
            assert "printer" in config.config
            assert "nozzle" in config.config
            assert config.printer["bed_size_x"] == 250.0  # Default value
        finally:
            config_path.unlink()

    def test_validation_missing_key_uses_defaults(self):
        """Test that missing keys are filled with defaults."""
        config_content = """
[printer]
bed_size_x = 250.0

[nozzle]
outer_diameter = 1.0
inner_diameter = 0.2

[temperatures]
bed_temperature = 60
# Missing nozzle_temperature and cooldown_temperature - should use defaults

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

[light_welds]
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
            config = Config(config_path)

            # Should not raise error - defaults fill missing keys
            config.validate()

            # Verify defaults are used for missing keys
            assert config.temperatures["nozzle_temperature"] == 170  # Default value
            assert config.temperatures["cooldown_temperature"] == 50  # Default value
        finally:
            config_path.unlink()

    def test_validation_invalid_temperature_range(self):
        """Test validation with invalid temperature range."""
        config_content = """
[printer]
bed_size_x = 250.0

[nozzle]
outer_diameter = 1.0
inner_diameter = 0.2

[temperatures]
bed_temperature = 200  # Too high
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

[light_welds]
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
            config = Config(config_path)

            with pytest.raises(ConfigError, match="bed_temperature must be between"):
                config.validate()
        finally:
            config_path.unlink()

    def test_validation_negative_dot_spacing(self):
        """Test validation with negative dot spacing."""
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
weld_height = 0.05
weld_temperature = 200
weld_time = 0.5
dot_spacing = -1.0  # Invalid
initial_dot_spacing = 8.0
cooling_time_between_passes = 2.0

[light_welds]
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
            config = Config(config_path)

            with pytest.raises(ConfigError, match="dot_spacing must be positive"):
                config.validate()
        finally:
            config_path.unlink()
