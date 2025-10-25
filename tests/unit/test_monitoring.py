"""Tests for monitoring functionality."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests_mock

from microweldr.monitoring.monitor import PrintMonitor
from microweldr.prusalink.exceptions import PrusaLinkError


class TestPrintMonitor:
    """Test print monitoring functionality."""

    @pytest.fixture
    def secrets_file(self):
        """Create a temporary secrets file."""
        secrets_content = """
[prusalink]
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
        return PrintMonitor(secrets_file)

    @requests_mock.Mocker()
    def test_monitor_initialization(self, m, monitor):
        """Test monitor initialization."""
        assert monitor.client is not None
        assert monitor.monitoring is False

    @requests_mock.Mocker()
    def test_get_print_status_operational(self, m, monitor):
        """Test getting print status when operational."""
        mock_response = {
            "printer": {
                "state": "Operational",
                "temp_bed": {"actual": 25.0, "target": 0.0},
                "temp_nozzle": {"actual": 23.0, "target": 0.0}
            },
            "job": {
                "file": {"name": None},
                "estimatedPrintTime": None,
                "progress": {"completion": None}
            }
        }
        
        m.get("http://192.168.1.100/api/printer", json=mock_response["printer"])
        m.get("http://192.168.1.100/api/job", json=mock_response["job"])
        
        status = monitor.get_print_status()
        assert status["state"] == "Operational"
        assert status["bed_temp"] == 25.0
        assert status["nozzle_temp"] == 23.0

    @requests_mock.Mocker()
    def test_get_print_status_printing(self, m, monitor):
        """Test getting print status when printing."""
        printer_response = {
            "state": "Printing",
            "temp_bed": {"actual": 60.0, "target": 60.0},
            "temp_nozzle": {"actual": 200.0, "target": 200.0}
        }
        
        job_response = {
            "file": {"name": "test_weld.gcode"},
            "estimatedPrintTime": 1800,
            "progress": {"completion": 45.5, "printTimeLeft": 990}
        }
        
        m.get("http://192.168.1.100/api/printer", json={"printer": printer_response})
        m.get("http://192.168.1.100/api/job", json={"job": job_response})
        
        status = monitor.get_print_status()
        assert status["state"] == "Printing"
        assert status["progress"] == 45.5
        assert status["time_left"] == 990
        assert status["filename"] == "test_weld.gcode"

    @requests_mock.Mocker()
    def test_get_print_status_error(self, m, monitor):
        """Test getting print status with API error."""
        m.get("http://192.168.1.100/api/printer", status_code=500)
        
        with pytest.raises(PrusaLinkError):
            monitor.get_print_status()

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

    @requests_mock.Mocker()
    def test_stop_print_success(self, m, monitor):
        """Test successful print stop."""
        m.delete("http://192.168.1.100/api/job", json={"stopped": True})
        
        result = monitor.stop_print()
        assert result is True

    @requests_mock.Mocker()
    def test_stop_print_failure(self, m, monitor):
        """Test print stop failure."""
        m.delete("http://192.168.1.100/api/job", status_code=409)
        
        result = monitor.stop_print()
        assert result is False

    @requests_mock.Mocker()
    def test_stop_print_force(self, m, monitor):
        """Test forced print stop."""
        # First attempt fails, second succeeds
        m.delete("http://192.168.1.100/api/job", [
            {"status_code": 409},
            {"json": {"stopped": True}}
        ])
        
        result = monitor.stop_print(force=True)
        assert result is True

    @patch('time.sleep')
    @requests_mock.Mocker()
    def test_monitor_print_completion(self, m, mock_sleep, monitor):
        """Test monitoring a print to completion."""
        # Simulate print progress
        responses = [
            # First check - printing
            {
                "printer": {
                    "state": "Printing",
                    "temp_bed": {"actual": 60.0, "target": 60.0},
                    "temp_nozzle": {"actual": 200.0, "target": 200.0}
                }
            },
            # Second check - still printing
            {
                "printer": {
                    "state": "Printing",
                    "temp_bed": {"actual": 60.0, "target": 60.0},
                    "temp_nozzle": {"actual": 200.0, "target": 200.0}
                }
            },
            # Third check - completed
            {
                "printer": {
                    "state": "Operational",
                    "temp_bed": {"actual": 30.0, "target": 0.0},
                    "temp_nozzle": {"actual": 25.0, "target": 0.0}
                }
            }
        ]
        
        job_responses = [
            {"job": {"progress": {"completion": 25.0}}},
            {"job": {"progress": {"completion": 75.0}}},
            {"job": {"progress": {"completion": 100.0}}}
        ]
        
        for i, (printer_resp, job_resp) in enumerate(zip(responses, job_responses)):
            m.get(f"http://192.168.1.100/api/printer", json=printer_resp)
            m.get(f"http://192.168.1.100/api/job", json=job_resp)
        
        # Mock the monitor method to stop after a few iterations
        original_monitoring = monitor.monitoring
        call_count = 0
        
        def mock_get_status():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                monitor.monitoring = False
            return monitor.get_print_status()
        
        with patch.object(monitor, 'get_print_status', side_effect=mock_get_status):
            monitor.monitor_print(update_interval=0.1)
        
        # Should have made multiple status checks
        assert call_count >= 3

    def test_monitor_print_mode_welding(self, monitor):
        """Test monitor print with welding mode."""
        # Test that welding mode is properly set
        with patch.object(monitor, 'get_print_status') as mock_status:
            mock_status.side_effect = [
                {
                    "state": "Printing",
                    "progress": 50.0,
                    "z_position": 5.0,
                    "bed_temp": 60.0,
                    "nozzle_temp": 200.0
                },
                {
                    "state": "Operational",
                    "progress": 100.0,
                    "z_position": 10.0,
                    "bed_temp": 30.0,
                    "nozzle_temp": 25.0
                }
            ]
            
            call_count = 0
            def stop_after_two():
                nonlocal call_count
                call_count += 1
                if call_count >= 2:
                    monitor.monitoring = False
                return mock_status.return_value
            
            mock_status.side_effect = stop_after_two
            
            monitor.monitor_print(mode="welding", update_interval=0.1)
            
            assert call_count >= 2

    def test_monitor_print_mode_pipetting(self, monitor):
        """Test monitor print with pipetting mode."""
        with patch.object(monitor, 'get_print_status') as mock_status:
            mock_status.return_value = {
                "state": "Paused",
                "progress": 30.0,
                "z_position": 15.0,
                "bed_temp": 40.0,
                "nozzle_temp": 100.0
            }
            
            # Stop monitoring after first check
            def stop_immediately():
                monitor.monitoring = False
                return mock_status.return_value
            
            mock_status.side_effect = stop_immediately
            
            monitor.monitor_print(mode="pipetting", update_interval=0.1)
            
            mock_status.assert_called_once()

    @patch('builtins.input', return_value='y')
    def test_monitor_print_keyboard_interrupt(self, mock_input, monitor):
        """Test monitor print with keyboard interrupt."""
        with patch.object(monitor, 'get_print_status') as mock_status:
            mock_status.side_effect = KeyboardInterrupt()
            
            # Should handle KeyboardInterrupt gracefully
            monitor.monitor_print(update_interval=0.1)
            
            # Should have attempted to get status
            mock_status.assert_called_once()

    def test_display_status_welding_mode(self, monitor):
        """Test status display in welding mode."""
        status = {
            "state": "Printing",
            "progress": 45.5,
            "time_left": 1800,
            "filename": "test.gcode",
            "bed_temp": 60.0,
            "nozzle_temp": 200.0,
            "z_position": 5.0
        }
        
        with patch('builtins.print') as mock_print:
            monitor._display_status(status, "welding")
            
            # Should have printed status information
            assert mock_print.called
            
            # Check that welding-specific information is included
            printed_text = ' '.join(str(call) for call in mock_print.call_args_list)
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
            "z_position": 15.0
        }
        
        with patch('builtins.print') as mock_print:
            monitor._display_status(status, "pipetting")
            
            # Should have printed status information
            assert mock_print.called
            
            # Check that pipetting-specific information is included
            printed_text = ' '.join(str(call) for call in mock_print.call_args_list)
            assert "pipetting" in printed_text.lower() or "paused" in printed_text.lower()

    def test_clear_screen(self, monitor):
        """Test screen clearing functionality."""
        with patch('os.system') as mock_system:
            monitor._clear_screen()
            mock_system.assert_called_once_with('clear')

    @requests_mock.Mocker()
    def test_get_print_status_with_z_position(self, m, monitor):
        """Test getting print status with Z position information."""
        printer_response = {
            "state": "Printing",
            "temp_bed": {"actual": 60.0, "target": 60.0},
            "temp_nozzle": {"actual": 200.0, "target": 200.0},
            "axis": {"z": {"value": 5.5}}
        }
        
        job_response = {
            "file": {"name": "test.gcode"},
            "progress": {"completion": 50.0}
        }
        
        m.get("http://192.168.1.100/api/printer", json={"printer": printer_response})
        m.get("http://192.168.1.100/api/job", json={"job": job_response})
        
        status = monitor.get_print_status()
        assert status["z_position"] == 5.5

    @requests_mock.Mocker()
    def test_get_print_status_missing_z_position(self, m, monitor):
        """Test getting print status when Z position is missing."""
        printer_response = {
            "state": "Printing",
            "temp_bed": {"actual": 60.0, "target": 60.0},
            "temp_nozzle": {"actual": 200.0, "target": 200.0}
            # No axis information
        }
        
        job_response = {
            "file": {"name": "test.gcode"},
            "progress": {"completion": 50.0}
        }
        
        m.get("http://192.168.1.100/api/printer", json={"printer": printer_response})
        m.get("http://192.168.1.100/api/job", json={"job": job_response})
        
        status = monitor.get_print_status()
        assert status["z_position"] is None
