"""Simple tests for configuration management."""

import pytest
from microweldr.core.config import Config


class TestConfigSimple:
    """Test basic configuration functionality."""

    def test_default_config_creation(self):
        """Test creating config with defaults."""
        config = Config()
        assert config is not None

    def test_config_has_basic_properties(self):
        """Test config has expected basic properties."""
        config = Config()

        # Should be able to get temperature settings
        bed_temp = config.get("temperatures", "bed_temperature", 35)
        nozzle_temp = config.get("temperatures", "nozzle_temperature", 160)

        # Should have reasonable default values
        assert isinstance(bed_temp, (int, float))
        assert isinstance(nozzle_temp, (int, float))
        assert bed_temp > 0
        assert nozzle_temp > 0
