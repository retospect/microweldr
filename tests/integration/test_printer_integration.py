"""Integration tests for printer operations - requires actual printer connection."""

import pytest

from microweldr.prusalink.client import PrusaLinkClient
from microweldr.prusalink.exceptions import (
    PrusaLinkConnectionError,
    PrusaLinkOperationError,
    PrusaLinkValidationError,
)


def printer_available():
    """Check if printer is available for testing."""
    try:
        client = PrusaLinkClient()
        return client.test_connection()
    except Exception:
        return False


# Skip all tests if no printer available
pytestmark = pytest.mark.skipif(
    not printer_available(), reason="Printer not available - skipping integration tests"
)


class TestPrinterIntegration:
    """Integration tests for actual printer operations."""

    @pytest.fixture
    def client(self):
        """Create PrusaLink client for testing."""
        return PrusaLinkClient()

    def test_temperature_readback_verification(self, client):
        """Test temperature readback catches clamping (fast, safe test)."""
        # Test 1: Normal temperature should work
        result = client.set_bed_temperature(60)
        assert result is True

        # Verify it was actually set
        import time

        time.sleep(1)
        status = client.get_printer_status()
        target_bed = status.get("printer", {}).get("target_bed", 0)
        assert abs(target_bed - 60) <= 1  # Allow 1°C tolerance

        # Test 2: Extreme temperature should be caught by validation
        with pytest.raises(PrusaLinkValidationError) as exc_info:
            client.set_bed_temperature(500)
        assert "exceeds safe maximum" in str(exc_info.value)

        # Test 3: Force mode bypasses validation but readback catches clamping
        with pytest.raises(PrusaLinkOperationError) as exc_info:
            # Use direct G-code to bypass validation, trigger readback verification
            client.send_and_run_gcode(
                commands=["M140 S200  ; Set extreme temp"], job_name="test_clamping"
            )
            # Manually verify to trigger clamping detection
            client._verify_temperature_set(200, "bed")
        assert "clamped" in str(exc_info.value).lower()

        # Clean up - set back to safe temperature
        client.set_bed_temperature(0)

    def test_invalid_gcode_handling(self, client):
        """Test how system handles invalid G-code commands (fast test)."""
        # Test 1: Malformed G-code should be ignored by printer
        result = client.send_and_run_gcode(
            commands=["G999 INVALID_COMMAND"],
            job_name="test_invalid",
            wait_for_completion=True,
        )
        # Should succeed (printer ignores invalid commands)
        assert result is True

        # Test 2: Movement beyond limits should be validated
        with pytest.raises(PrusaLinkValidationError) as exc_info:
            client.move_to_position(x=500, y=500)
        assert "outside safe range" in str(exc_info.value)

        # Test 3: Verify printer is still operational after invalid commands
        status = client.get_printer_status()
        state = status.get("printer", {}).get("state", "Unknown")
        assert state.upper() in ["IDLE", "FINISHED", "READY"]

    def test_error_recovery_and_halt(self, client):
        """Test error recovery and halt functionality (safe test)."""
        # Test halt operations method
        result = client.halt_print_operations("Integration test halt")
        assert result is True

        # Verify printer is in safe state after halt
        import time

        time.sleep(2)  # Give time for halt commands to execute

        status = client.get_printer_status()
        printer_info = status.get("printer", {})

        # Check that heaters were turned off
        target_bed = printer_info.get("target_bed", 0)
        target_nozzle = printer_info.get("target_nozzle", 0)

        # Should be 0 or very low after halt
        assert target_bed <= 5  # Allow small tolerance for cooling
        assert target_nozzle <= 5

        # Printer should still be operational (may be PRINTING due to halt commands)
        state = printer_info.get("state", "Unknown")
        assert state.upper() in ["IDLE", "FINISHED", "READY", "PRINTING"]


class TestPrinterValidationLimits:
    """Test validation limits match actual printer capabilities."""

    @pytest.fixture
    def client(self):
        """Create PrusaLink client for testing."""
        return PrusaLinkClient()

    def test_temperature_limits_realistic(self, client):
        """Test that our validation limits are realistic for the printer."""
        # Test bed temperature at validation limit (should work)
        result = client.set_bed_temperature(120)  # Our max limit
        assert result is True

        # Verify printer accepted it
        import time

        time.sleep(1)
        status = client.get_printer_status()
        target_bed = status.get("printer", {}).get("target_bed", 0)
        assert target_bed >= 115  # Should be close to requested

        # Clean up
        client.set_bed_temperature(0)

    def test_movement_limits_realistic(self, client):
        """Test that movement limits are appropriate (validation only)."""
        # Test that our validation limits work
        with pytest.raises(PrusaLinkValidationError) as exc_info:
            client.move_to_position(x=500, y=500, z=500)
        assert "outside safe range" in str(exc_info.value)

        # Test that reasonable coordinates are accepted (without actual movement)
        try:
            # This should pass validation (but we won't actually move)
            result = client.move_to_position(x=100, y=100, z=50, verify_movement=False)
            assert result is True
        except PrusaLinkValidationError:
            pytest.fail("Valid coordinates should not raise validation error")


# Pytest configuration for integration tests
def pytest_configure(config):
    """Configure pytest markers for integration tests."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (requires printer)"
    )


# Mark all tests in this module as integration tests
pytestmark = [
    pytestmark,  # Skip if no printer
    pytest.mark.integration,  # Mark as integration test
]
