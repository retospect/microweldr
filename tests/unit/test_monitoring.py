"""Tests for monitoring functionality."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests_mock

pytestmark = pytest.mark.hardware

from microweldr.monitoring.monitor import PrintMonitor
from microweldr.prusalink.exceptions import PrusaLinkError


class TestPrintMonitor:
    """Test print monitoring functionality."""

    @pytest.fixture
    def secrets_file(self):
        """Create a temporary secrets file."""
        secrets_content = """[prusalink]
host = "192.168.1.100"
username = "maker"
password = "test123"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(secrets_content)
            yield f.name
        Path(f.name).unlink()

    @pytest.fixture
    def monitor(self, secrets_file):
        """Create a print monitor."""
        from unittest.mock import Mock

        from microweldr.monitoring.monitor import MonitorMode

        monitor = PrintMonitor(mode=MonitorMode.STANDARD, interval=1, verbose=False)
        # Replace the client with a mock to avoid config file issues
        monitor.client = Mock()
        return monitor

    def test_monitor_initialization(self, requests_mock, monitor):
        """Test monitor initialization."""
        assert monitor.client is not None
        assert monitor.interval == 1
        assert monitor.verbose is False

    def test_get_print_status_operational(self, requests_mock, monitor):
        """Test getting print status when operational."""
        # Mock the client methods
        job_response = {
            "file": {"name": "test.gcode", "display_name": "test.gcode"},
            "estimatedPrintTime": None,
            "progress": 0,
            "state": "Operational",
            "time_printing": 0,
        }

        printer_status_response = {
            "printer": {
                "state": "Operational",
                "temp_bed": {"actual": 25.0, "target": 0.0},
                "temp_nozzle": {"actual": 23.0, "target": 0.0},
            }
        }

        monitor.client.get_job_status.return_value = job_response
        monitor.client.get_printer_status.return_value = printer_status_response

        status = monitor.get_print_status()
        assert status is not None
        assert status["state"] == "Operational"
        assert status["file_name"] == "test.gcode"

    def test_get_print_status_printing(self, requests_mock, monitor):
        """Test getting print status when printing."""
        job_response = {
            "file": {"name": "test_weld.gcode", "display_name": "test_weld.gcode"},
            "estimatedPrintTime": 1800,
            "progress": 45.5,
            "state": "Printing",
            "time_printing": 300,
        }

        printer_status_response = {
            "printer": {
                "state": "Printing",
                "temp_bed": {"actual": 60.0, "target": 60.0},
                "temp_nozzle": {"actual": 200.0, "target": 200.0},
            }
        }

        monitor.client.get_job_status.return_value = job_response
        monitor.client.get_printer_status.return_value = printer_status_response

        status = monitor.get_print_status()
        assert status is not None
        assert status["state"] == "Printing"
        assert status["progress"] == 45.5
        assert status["file_name"] == "test_weld.gcode"

    def test_get_print_status_error(self, requests_mock, monitor):
        """Test getting print status with API error."""
        monitor.client.get_job_status.side_effect = PrusaLinkError("Connection failed")

        # The method catches exceptions and returns None
        status = monitor.get_print_status()
        assert status is None

    def test_format_time_seconds(self, monitor):
        """Test time formatting for seconds."""
        assert monitor._format_time(30) == "30s"
        assert monitor._format_time(59) == "59s"

    def test_format_time_minutes(self, monitor):
        """Test time formatting for minutes."""
        assert monitor._format_time(60) == "1m 0s"
        assert monitor._format_time(90) == "1m 30s"
        assert monitor._format_time(3599) == "59m 59s"

    def test_format_time_hours(self, monitor):
        """Test time formatting for hours."""
        assert monitor._format_time(3600) == "1h 0m"
        assert monitor._format_time(3661) == "1h 1m"
        assert monitor._format_time(7200) == "2h 0m"

    def test_format_time_none(self, monitor):
        """Test time formatting for None value."""
        assert monitor._format_time(None) == "Unknown"

    def test_get_status_emoji_operational(self, monitor):
        """Test status emoji for operational state."""
        assert monitor._get_status_emoji("Operational") == "🟢"

    def test_get_status_emoji_printing(self, monitor):
        """Test status emoji for printing state."""
        assert monitor._get_status_emoji("Printing") == "🔥"

    def test_get_status_emoji_paused(self, monitor):
        """Test status emoji for paused state."""
        assert monitor._get_status_emoji("Paused") == "⏸️"

    def test_get_status_emoji_error(self, monitor):
        """Test status emoji for error state."""
        assert monitor._get_status_emoji("Error") == "❌"

    def test_get_status_emoji_unknown(self, monitor):
        """Test status emoji for unknown state."""
        assert monitor._get_status_emoji("Unknown") == "❓"

    def test_get_welding_phase_low_z(self, monitor):
        """Test welding phase detection for low Z position."""
        phase = monitor._get_welding_phase(5.0)  # Low Z = welding
        assert "welding" in phase.lower()

    def test_get_welding_phase_medium_z(self, monitor):
        """Test welding phase detection for medium Z position."""
        phase = monitor._get_welding_phase(25.0)  # Medium Z = active welding
        assert "active" in phase.lower() or "welding" in phase.lower()

    def test_get_welding_phase_high_z(self, monitor):
        """Test welding phase detection for high Z position."""
        phase = monitor._get_welding_phase(75.0)  # High Z = high-layer welding
        assert "high" in phase.lower() or "layer" in phase.lower()

    def test_stop_print_success(self, requests_mock, monitor):
        """Test successful print stop."""
        monitor.client.get_job_status.return_value = {
            "file": {"name": "test.gcode"},
            "state": "Printing",
        }
        monitor.client.stop_print.return_value = True

        with patch("builtins.input", return_value="y"):
            result = monitor.stop_print()
        assert result is True

    def test_stop_print_failure(self, requests_mock, monitor):
        """Test print stop failure."""
        monitor.client.get_job_status.return_value = {
            "file": {"name": "test.gcode"},
            "state": "Printing",
        }
        monitor.client.stop_print.return_value = False

        with patch("builtins.input", return_value="y"):
            result = monitor.stop_print()
        assert result is False

    def test_stop_print_force(self, requests_mock, monitor):
        """Test forced print stop."""
        monitor.client.get_job_status.return_value = {
            "file": {"name": "test.gcode"},
            "state": "Printing",
        }
        monitor.client.stop_print.return_value = True

        result = monitor.stop_print(force=True)
        assert result is True

    def test_monitor_until_complete_success(self, monitor):
        """Test monitoring until completion with successful completion."""
        # Mock successful job completion
        call_count = 0

        def mock_get_job_status():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"state": "printing", "progress": {"completion": 50}}
            elif call_count == 2:
                return {"state": "finished", "progress": {"completion": 100}}
            return None

        monitor.client.get_job_status.side_effect = mock_get_job_status

        with (
            patch.object(monitor, "print_header"),
            patch.object(monitor, "print_status_update"),
            patch("time.sleep"),
        ):
            result = monitor.monitor_until_complete()

        assert result is True

    def test_monitor_mode_welding(self, monitor):
        """Test monitor with welding mode."""
        from microweldr.monitoring.monitor import MonitorMode

        assert monitor.mode == MonitorMode.STANDARD

        # Test mode emoji
        emoji = monitor.get_mode_emoji()
        assert emoji == "🏗️"

    def test_monitor_mode_pipetting(self, monitor):
        """Test monitor with pipetting mode."""
        from unittest.mock import Mock

        from microweldr.monitoring.monitor import MonitorMode

        # Create a pipetting mode monitor
        pipetting_monitor = PrintMonitor(
            mode=MonitorMode.PIPETTING, interval=1, verbose=False
        )
        pipetting_monitor.client = Mock()
        assert pipetting_monitor.mode == MonitorMode.PIPETTING

        # Test mode emoji
        emoji = pipetting_monitor.get_mode_emoji()
        assert emoji == "🧪"

    def test_monitor_keyboard_interrupt_handling(self, monitor):
        """Test monitor handles keyboard interrupt gracefully."""
        monitor.client.get_job_status.side_effect = KeyboardInterrupt()

        # Should handle KeyboardInterrupt gracefully in monitor_until_complete
        with patch.object(monitor, "print_header"):
            result = monitor.monitor_until_complete()

        assert result is False

    def test_display_status_welding_mode(self, monitor):
        """Test status display in welding mode."""
        status = {
            "state": "Printing",
            "progress": 45.5,
            "time_left": 1800,
            "filename": "test.gcode",
            "bed_temp": 60.0,
            "nozzle_temp": 200.0,
            "z_position": 5.0,
        }

        with patch("builtins.print") as mock_print:
            monitor._display_status(status, "welding")

            # Should have printed status information
            assert mock_print.called

            # Check that welding-specific information is included
            printed_text = " ".join(str(call) for call in mock_print.call_args_list)
            assert "welding" in printed_text.lower() or "🔥" in printed_text

    def test_display_status_pipetting_mode(self, monitor):
        """Test status display in pipetting mode."""
        status = {
            "state": "Paused",
            "progress": 30.0,
            "time_left": None,
            "filename": "microfluidic.gcode",
            "bed_temp": 40.0,
            "nozzle_temp": 100.0,
            "z_position": 15.0,
        }

        with patch("builtins.print") as mock_print:
            monitor._display_status(status, "pipetting")

            # Should have printed status information
            assert mock_print.called

            # Check that pipetting-specific information is included
            printed_text = " ".join(str(call) for call in mock_print.call_args_list)
            assert (
                "pipetting" in printed_text.lower() or "paused" in printed_text.lower()
            )

    def test_clear_screen(self, monitor):
        """Test screen clearing functionality."""
        with patch("os.system") as mock_system:
            monitor._clear_screen()
            mock_system.assert_called_once_with("clear")

    def test_get_current_status_returns_printer_info(self, monitor):
        """Test that get_current_status includes printer_info."""
        job_response = {
            "file": {"name": "test.gcode", "display_name": "test.gcode"},
            "state": "Printing",
            "progress": 50.0,
            "time_printing": 300,
        }

        printer_status_response = {
            "printer": {
                "state": "Printing",
                "temp_bed": {"actual": 60.0, "target": 60.0},
                "temp_nozzle": {"actual": 200.0, "target": 200.0},
                "axis": {"z": {"value": 5.5}},
            }
        }

        monitor.client.get_job_status.return_value = job_response
        monitor.client.get_printer_status.return_value = printer_status_response

        status = monitor.get_print_status()
        assert status is not None
        assert "printer_info" in status
        assert status["printer_info"]["temp_bed"]["actual"] == 60.0
