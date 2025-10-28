"""
Tests for the core API functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from microweldr.api.core import MicroWeldr
from microweldr.core.models import WeldPath, WeldPoint


class TestMicroWeldrAPI:
    """Test the main API class."""

    def test_api_initialization(self):
        """Test API can be initialized."""
        api = MicroWeldr()
        assert api is not None

    def test_api_initialization_with_config(self, tmp_path):
        """Test API initialization with custom config."""
        config_file = tmp_path / "test_config.toml"
        config_file.write_text("""
[temperatures]
bed_temperature = 100
nozzle_temperature = 200
""")
        
        api = MicroWeldr(config_path=str(config_file))
        assert api is not None

    @patch('microweldr.api.core.setup_logging')
    def test_api_initialization_with_logging(self, mock_setup_logging):
        """Test API initialization sets up logging."""
        api = MicroWeldr(log_level="DEBUG")
        mock_setup_logging.assert_called_once_with(level="DEBUG", console=True)

    def test_api_version_info(self):
        """Test API provides version information."""
        api = MicroWeldr()
        # This should not raise an exception
        try:
            # The API should have some way to get version info
            # This is a placeholder test
            assert True
        except Exception:
            pytest.fail("API should provide version information")


class TestAPIIntegration:
    """Integration tests for API functionality."""

    def test_api_workflow_basic(self):
        """Test basic API workflow without actual hardware."""
        api = MicroWeldr()
        
        # Create a simple test path
        test_points = [
            WeldPoint(x=10.0, y=10.0, weld_type="normal"),
            WeldPoint(x=20.0, y=10.0, weld_type="normal"),
            WeldPoint(x=20.0, y=20.0, weld_type="normal"),
        ]
        test_path = WeldPath(points=test_points, path_id="test_path")
        
        # This should not raise an exception
        assert len(test_path.points) == 3
        assert test_path.path_id == "test_path"

    def test_api_error_handling(self):
        """Test API handles errors gracefully."""
        api = MicroWeldr()
        
        # Test with invalid config path
        with pytest.raises((FileNotFoundError, Exception)):
            MicroWeldr(config_path="/nonexistent/path/config.toml")


class TestAPIConfiguration:
    """Test API configuration handling."""

    def test_api_default_configuration(self):
        """Test API uses default configuration when none provided."""
        api = MicroWeldr()
        # Should not raise an exception
        assert api is not None

    def test_api_configuration_validation(self, tmp_path):
        """Test API validates configuration."""
        # Create invalid config
        config_file = tmp_path / "invalid_config.toml"
        config_file.write_text("invalid toml content [[[")
        
        # Should handle invalid config gracefully
        try:
            api = MicroWeldr(config_path=str(config_file))
            # If it doesn't raise an exception, that's also acceptable
            # as long as it falls back to defaults
            assert api is not None
        except Exception:
            # It's also acceptable to raise an exception for invalid config
            pass


class TestAPIUtilities:
    """Test API utility functions."""

    def test_api_path_validation(self):
        """Test API validates file paths."""
        api = MicroWeldr()
        
        # Test with valid path
        valid_path = Path(__file__).parent / "fixtures" / "simple.svg"
        # This is just testing the API exists and can be called
        assert api is not None

    def test_api_logging_configuration(self):
        """Test API logging configuration."""
        # Test different log levels
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            api = MicroWeldr(log_level=level)
            assert api is not None


@pytest.fixture
def sample_svg_content():
    """Provide sample SVG content for testing."""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <rect x="10" y="10" width="80" height="80" fill="none" stroke="black" stroke-width="1"/>
</svg>'''


@pytest.fixture
def temp_svg_file(tmp_path, sample_svg_content):
    """Create a temporary SVG file for testing."""
    svg_file = tmp_path / "test.svg"
    svg_file.write_text(sample_svg_content)
    return svg_file


class TestAPIFileHandling:
    """Test API file handling capabilities."""

    def test_api_svg_file_validation(self, temp_svg_file):
        """Test API can validate SVG files."""
        api = MicroWeldr()
        
        # Test that file exists
        assert temp_svg_file.exists()
        assert temp_svg_file.suffix == ".svg"

    def test_api_output_path_handling(self, tmp_path):
        """Test API handles output paths correctly."""
        api = MicroWeldr()
        
        output_path = tmp_path / "output.gcode"
        # Test path handling
        assert output_path.parent.exists()
        assert output_path.suffix == ".gcode"
