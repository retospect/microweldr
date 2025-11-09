"""Centralized printer service for consistent API usage and status handling."""

import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..prusalink.client import PrusaLinkClient
from ..prusalink.exceptions import PrusaLinkError

logger = logging.getLogger(__name__)


class PrinterState(Enum):
    """Standardized printer states."""

    UNKNOWN = "Unknown"
    OPERATIONAL = "Operational"
    PRINTING = "Printing"
    PAUSED = "Paused"
    FINISHED = "Finished"
    ERROR = "Error"
    CANCELLED = "Cancelled"
    IDLE = "Idle"


class PrinterStatus:
    """Standardized printer status representation."""

    def __init__(self, raw_status: Dict[str, Any]):
        """Initialize from raw status data."""
        self.raw_status = raw_status
        self._parse_status()

    def _parse_status(self):
        """Parse raw status into standardized format."""
        # Handle different API response formats
        printer_info = self.raw_status.get("printer", {})

        # Normalize state
        raw_state = printer_info.get("state", "Unknown")
        self.state = self._normalize_state(raw_state)

        # Temperature data
        self.bed_temp = printer_info.get("temp_bed", 0.0)
        self.bed_target = printer_info.get("target_bed", 0.0)
        self.nozzle_temp = printer_info.get("temp_nozzle", 0.0)
        self.nozzle_target = printer_info.get("target_nozzle", 0.0)

        # Job information
        job_info = self.raw_status.get("job", {})
        self.current_file = job_info.get("file", {}).get("name")
        self.progress = job_info.get("progress", 0.0)

    def _normalize_state(self, raw_state: str) -> PrinterState:
        """Normalize state string to PrinterState enum."""
        state_upper = raw_state.upper()

        # Handle common variations
        state_mapping = {
            "OPERATIONAL": PrinterState.OPERATIONAL,
            "PRINTING": PrinterState.PRINTING,
            "PAUSED": PrinterState.PAUSED,
            "FINISHED": PrinterState.FINISHED,
            "FINISH": PrinterState.FINISHED,  # Some printers use this
            "ERROR": PrinterState.ERROR,
            "CANCELLED": PrinterState.CANCELLED,
            "CANCELED": PrinterState.CANCELLED,  # US spelling
            "IDLE": PrinterState.IDLE,
        }

        return state_mapping.get(state_upper, PrinterState.UNKNOWN)

    @property
    def is_ready_for_job(self) -> bool:
        """Check if printer is ready to accept new jobs."""
        return self.state in [
            PrinterState.OPERATIONAL,
            PrinterState.FINISHED,
            PrinterState.IDLE,
        ]

    @property
    def is_printing(self) -> bool:
        """Check if printer is currently printing."""
        return self.state == PrinterState.PRINTING

    @property
    def is_operational(self) -> bool:
        """Check if printer is operational."""
        return self.state == PrinterState.OPERATIONAL

    def __str__(self) -> str:
        """String representation."""
        return f"PrinterStatus({self.state.value}, bed: {self.bed_temp:.1f}°C, nozzle: {self.nozzle_temp:.1f}°C)"


class PrinterService:
    """Centralized printer service for consistent API usage."""

    def __init__(self):
        """Initialize printer service with unified configuration."""
        self._client = None
        self._last_status = None

    @property
    def client(self) -> PrusaLinkClient:
        """Get or create PrusaLink client (lazy initialization)."""
        if self._client is None:
            # Use unified configuration system
            from .unified_config import get_prusalink_config

            try:
                prusalink_config = get_prusalink_config()
                self._client = self._create_client_from_config(prusalink_config)
            except Exception as e:
                logger.error(f"Failed to create PrusaLink client: {e}")
                raise
        return self._client

    def _create_client_from_config(self, config: Dict[str, Any]) -> PrusaLinkClient:
        """Create PrusaLink client from configuration dictionary."""
        # Validate required fields
        required_fields = ["host", "username"]
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field in printer config: {field}")

        # Require either password or api_key
        if "password" not in config and "api_key" not in config:
            raise ValueError(
                "Missing authentication: need either 'password' or 'api_key' in printer config"
            )

        # Create a minimal client that doesn't use file-based config loading
        client = object.__new__(PrusaLinkClient)
        client.config = config
        client.base_url = f"http://{config['host']}"

        # Support both API key and LCD password authentication
        password = config.get("password") or config.get("api_key")
        from requests.auth import HTTPDigestAuth

        client.auth = HTTPDigestAuth(config["username"], password)
        client.timeout = config.get("timeout", 30)

        return client

    def test_connection(self) -> bool:
        """Test printer connection."""
        try:
            return self.client.test_connection()
        except Exception as e:
            logger.warning(f"Connection test failed: {e}")
            return False

    def get_status(self) -> PrinterStatus:
        """Get current printer status."""
        try:
            raw_status = self.client.get_printer_status()
            status = PrinterStatus(raw_status)
            self._last_status = status
            return status
        except Exception as e:
            logger.error(f"Failed to get printer status: {e}")
            raise

    def wait_for_ready_state(self, timeout: int = 30, verbose: bool = False) -> bool:
        """Wait for printer to be in a ready state.

        Args:
            timeout: Maximum time to wait in seconds
            verbose: Whether to print status updates

        Returns:
            True if printer becomes ready, False if timeout
        """
        import time

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                status = self.get_status()

                if verbose:
                    print(f"   Printer state: {status.state.value}")

                if status.is_ready_for_job:
                    return True

                if status.state == PrinterState.ERROR:
                    if verbose:
                        print("   ❌ Printer is in error state")
                    return False

                time.sleep(2)

            except Exception as e:
                if verbose:
                    print(f"   ⚠️  Status check failed: {e}")
                time.sleep(5)

        if verbose:
            print(f"   ⏰ Timeout waiting for ready state ({timeout}s)")
        return False

    def ensure_not_printing(self, allow_user_override: bool = True) -> bool:
        """Ensure printer is not currently printing.

        Args:
            allow_user_override: Whether to allow user to override printing check

        Returns:
            True if safe to proceed, False otherwise
        """
        status = self.get_status()

        if not status.is_printing:
            return True

        print(f"⚠️  WARNING: Printer is currently printing!")
        if status.current_file:
            print(f"   Current file: {status.current_file}")
            print(f"   Progress: {status.progress:.1f}%")

        if not allow_user_override:
            return False

        try:
            response = (
                input("Continue anyway? This may affect the print! (y/N): ")
                .strip()
                .lower()
            )
            return response in ["y", "yes"]
        except (KeyboardInterrupt, EOFError):
            return False

    def upload_gcode(
        self,
        gcode_path: Union[str, Path],
        remote_filename: Optional[str] = None,
        auto_start: bool = False,
        overwrite: bool = True,
    ) -> bool:
        """Upload G-code file to printer.

        Args:
            gcode_path: Path to G-code file
            remote_filename: Name for file on printer
            auto_start: Whether to start printing after upload
            overwrite: Whether to overwrite existing files

        Returns:
            True if upload successful, False otherwise
        """
        try:
            gcode_path = Path(gcode_path)
            if not remote_filename:
                remote_filename = gcode_path.name

            result = self.client.upload_gcode(
                str(gcode_path),
                remote_filename=remote_filename,
                auto_start=auto_start,
                overwrite=overwrite,
            )

            return result.get("status") == "success"

        except Exception as e:
            logger.error(f"Upload failed: {e}")
            return False

    def set_bed_temperature(self, temperature: float) -> bool:
        """Set bed temperature."""
        try:
            return self.client.set_bed_temperature(temperature)
        except Exception as e:
            logger.error(f"Failed to set bed temperature: {e}")
            return False

    def set_nozzle_temperature(self, temperature: float) -> bool:
        """Set nozzle temperature."""
        try:
            return self.client.set_nozzle_temperature(temperature)
        except Exception as e:
            logger.error(f"Failed to set nozzle temperature: {e}")
            return False

    def get_printer_info(self) -> Dict[str, Any]:
        """Get printer information."""
        try:
            return self.client.get_printer_info()
        except Exception as e:
            logger.error(f"Failed to get printer info: {e}")
            return {}

    def get_storage_info(self) -> Dict[str, Any]:
        """Get storage information."""
        try:
            return self.client.get_storage_info()
        except Exception as e:
            logger.error(f"Failed to get storage info: {e}")
            return {}

    def get_job_status(self) -> Optional[Dict[str, Any]]:
        """Get current job status."""
        try:
            return self.client.get_job_status()
        except Exception as e:
            logger.error(f"Failed to get job status: {e}")
            return None


# Global printer service instance for reuse
_printer_service: Optional[PrinterService] = None


def get_printer_service() -> PrinterService:
    """Get global printer service instance."""
    global _printer_service

    if _printer_service is None:
        _printer_service = PrinterService()

    return _printer_service


def reset_printer_service():
    """Reset global printer service (for testing)."""
    global _printer_service
    _printer_service = None
