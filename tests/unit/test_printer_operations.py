"""Unit tests for printer operations."""

from unittest.mock import Mock, patch

import pytest

from microweldr.core.printer_operations import PrinterOperations
from microweldr.prusalink.client import PrusaLinkClient


class TestPrinterOperations:
    """Test cases for PrinterOperations class."""

    def test_printer_operations_creation(self):
        """Test creating PrinterOperations instance."""
        mock_client = Mock(spec=PrusaLinkClient)
        ops = PrinterOperations(mock_client)
        assert ops.client == mock_client

    def test_send_gcode_success(self):
        """Test successful G-code sending."""
        mock_client = Mock(spec=PrusaLinkClient)
        mock_client.send_gcode.return_value = True
        ops = PrinterOperations(mock_client)

        result = ops.send_gcode("G28")
        assert result is True
        mock_client.send_gcode.assert_called_once_with("G28")

    def test_calibrate_printer(self):
        """Test printer calibration."""
        mock_client = Mock(spec=PrusaLinkClient)
        ops = PrinterOperations(mock_client)

        with patch.object(ops, "send_gcode", return_value=True) as mock_send:
            result = ops.calibrate_printer()
            assert result is True
            assert mock_send.call_count == 2  # G28 and G29

    def test_set_bed_temperature(self):
        """Test setting bed temperature."""
        mock_client = Mock(spec=PrusaLinkClient)
        ops = PrinterOperations(mock_client)

        with patch.object(ops, "send_gcode", return_value=True) as mock_send:
            result = ops.set_bed_temperature(60)
            assert result is True
            mock_send.assert_called_once()

    def test_turn_off_bed_heater(self):
        """Test turning off bed heater."""
        mock_client = Mock(spec=PrusaLinkClient)
        ops = PrinterOperations(mock_client)

        with patch.object(ops, "set_bed_temperature", return_value=True) as mock_set:
            result = ops.turn_off_bed_heater()
            assert result is True
            mock_set.assert_called_once_with(0)

    def test_move_to_position(self):
        """Test moving to position."""
        mock_client = Mock(spec=PrusaLinkClient)
        ops = PrinterOperations(mock_client)

        with patch.object(ops, "send_gcode", return_value=True) as mock_send:
            result = ops.move_to_position(x=100, y=200, z=5)
            assert result is True
            mock_send.assert_called_once()

    def test_draw_bounding_box(self):
        """Test drawing bounding box."""
        mock_client = Mock(spec=PrusaLinkClient)
        ops = PrinterOperations(mock_client)

        with patch.object(ops, "move_to_position", return_value=True) as mock_move:
            result = ops.draw_bounding_box(10, 10, 50, 50)
            assert result is True
            assert mock_move.call_count == 6  # Z move + 5 corner moves

    def test_load_unload_plate(self):
        """Test load/unload plate operation."""
        mock_client = Mock(spec=PrusaLinkClient)
        ops = PrinterOperations(mock_client)

        with patch.object(
            ops, "send_gcode", return_value=True
        ) as mock_send, patch.object(
            ops, "move_to_position", return_value=True
        ) as mock_move:
            result = ops.load_unload_plate()
            assert result is True
            assert mock_send.call_count == 2  # G91 and G90
            mock_move.assert_called_once()
