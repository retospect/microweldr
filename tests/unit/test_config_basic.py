"""Basic tests for configuration management."""

import tempfile

from microweldr.core.config import Config


class TestConfigBasics:
    """Basic configuration tests."""

    def test_config_creation(self):
        """Test basic config creation."""
        # Use default config instead of deprecated path-based constructor
        config = Config()
        assert config is not None
