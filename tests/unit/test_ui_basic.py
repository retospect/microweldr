"""Basic tests for UI module."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from microweldr.ui.curses_ui import MicroWeldrUI


class TestMicroWeldrUI:
    """Basic UI tests."""

    def test_ui_creation(self):
        """Test UI can be created."""
        ui = MicroWeldrUI()
        assert ui is not None
        assert ui.running is True
        assert ui.calibrated is False
        assert ui.plate_heater_on is False

    def test_ui_with_svg_file(self):
        """Test UI creation with SVG file."""
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            svg_path = Path(f.name)

        ui = MicroWeldrUI(svg_file=svg_path)
        assert ui.svg_file == svg_path

    def test_bounds_info_empty(self):
        """Test bounds info with no weld paths."""
        ui = MicroWeldrUI()
        bounds = ui.get_bounds_info()
        assert bounds == (0, 0, 0, 0)

    @patch("microweldr.ui.curses_ui.Config")
    def test_initialize_without_config(self, mock_config):
        """Test initialization without existing config file."""
        mock_config.create_default.return_value = Mock()

        ui = MicroWeldrUI()
        ui.initialize()

        assert ui.config is not None

    def test_status_monitoring_lifecycle(self):
        """Test starting and stopping status monitoring."""
        ui = MicroWeldrUI()
        ui.printer_connected = (
            False  # No connection, but should still start monitoring thread
        )

        ui.start_status_monitoring()
        assert (
            ui.status_thread is not None
        )  # Thread should start regardless of connection

        ui.stop_status_monitoring()
        assert ui.running is False
