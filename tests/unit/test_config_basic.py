"""Basic tests for configuration management."""

import tempfile

from microweldr.core.config import Config


class TestConfigBasics:
    """Basic configuration tests."""

    def test_config_creation(self):
        """Test basic config creation with temp file."""
        with tempfile.NamedTemporaryFile(suffix=".toml", delete=False) as f:
            f.write(b"[printer]\nbed_width = 250\nbed_height = 220\n")
            f.flush()
            config = Config(f.name)
            assert config is not None
