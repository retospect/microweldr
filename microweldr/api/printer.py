"""Printer connection and management API."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..core.graceful_degradation import ResilientPrusaLinkClient, check_system_health
from ..core.logging_config import LogContext
from ..core.security import validate_secrets_interactive

logger = logging.getLogger(__name__)


class PrinterStatus:
    """Represents printer status information."""

    def __init__(self, status_data: Dict[str, Any]):
        """Initialize printer status.

        Args:
            status_data: Raw status data from printer
        """
        self.raw_data = status_data
        self.is_fallback = status_data.get("fallback", False)

        printer_data = status_data.get("printer", {})
        self.state = printer_data.get("state", "Unknown")

        # Temperature data
        bed_temp = printer_data.get("temp_bed", {})
        self.bed_actual = bed_temp.get("actual", 0.0)
        self.bed_target = bed_temp.get("target", 0.0)

        nozzle_temp = printer_data.get("temp_nozzle", {})
        self.nozzle_actual = nozzle_temp.get("actual", 0.0)
        self.nozzle_target = nozzle_temp.get("target", 0.0)

        # Job data
        job_data = status_data.get("job", {})
        self.job_file = job_data.get("file", {}).get("name")
        self.job_progress = job_data.get("progress", {}).get("completion", 0.0)
        self.job_time_remaining = job_data.get("progress", {}).get("printTimeLeft")

    @property
    def is_operational(self) -> bool:
        """Check if printer is operational."""
        return self.state == "Operational" and not self.is_fallback

    @property
    def is_printing(self) -> bool:
        """Check if printer is currently printing."""
        return self.state == "Printing"

    @property
    def is_ready(self) -> bool:
        """Check if printer is ready for new jobs."""
        return self.state in ["Operational", "Finished"] and not self.is_fallback

    def __str__(self) -> str:
        """String representation."""
        if self.is_fallback:
            return f"PrinterStatus(FALLBACK - {self.state})"
        return f"PrinterStatus({self.state}, bed: {self.bed_actual:.1f}°C, nozzle: {self.nozzle_actual:.1f}°C)"


class PrinterConnection:
    """High-level printer connection and job management."""

    def __init__(self, secrets_path: Union[str, Path], validate_secrets: bool = True):
        """Initialize printer connection.

        Args:
            secrets_path: Path to secrets configuration file
            validate_secrets: Whether to validate secrets on initialization

        Raises:
            FileNotFoundError: If secrets file doesn't exist
            SecurityError: If secrets validation fails
        """
        self.secrets_path = Path(secrets_path)

        if not self.secrets_path.exists():
            raise FileNotFoundError(f"Secrets file not found: {self.secrets_path}")

        if validate_secrets:
            if not validate_secrets_interactive(str(self.secrets_path)):
                raise SecurityError("Secrets validation failed")

        self.client = ResilientPrusaLinkClient(str(self.secrets_path))
        logger.info(f"Printer connection initialized with {self.secrets_path}")

    def get_status(self) -> PrinterStatus:
        """Get current printer status.

        Returns:
            PrinterStatus object
        """
        with LogContext("printer_status"):
            status_data = self.client.get_status()
            return PrinterStatus(status_data)

    def is_connected(self) -> bool:
        """Check if printer is connected and responsive.

        Returns:
            True if connected, False otherwise
        """
        try:
            status = self.get_status()
            return not status.is_fallback
        except Exception as e:
            logger.warning(f"Connection check failed: {e}")
            return False

    def wait_for_ready(self, timeout: int = 300, check_interval: int = 5) -> bool:
        """Wait for printer to become ready.

        Args:
            timeout: Maximum wait time in seconds
            check_interval: Check interval in seconds

        Returns:
            True if printer became ready, False if timeout
        """
        import time

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                status = self.get_status()
                if status.is_ready:
                    logger.info("Printer is ready")
                    return True

                logger.debug(f"Printer not ready (state: {status.state}), waiting...")
                time.sleep(check_interval)

            except Exception as e:
                logger.warning(f"Status check failed: {e}")
                time.sleep(check_interval)

        logger.warning(f"Printer did not become ready within {timeout} seconds")
        return False

    def submit_job(
        self,
        gcode_path: Union[str, Path],
        filename: Optional[str] = None,
        auto_start: bool = False,
        wait_for_ready: bool = True,
        storage: str = "local",
    ) -> Dict[str, Any]:
        """Submit a G-code job to the printer.

        Args:
            gcode_path: Path to G-code file
            filename: Target filename on printer (uses original if None)
            auto_start: Whether to start printing automatically
            wait_for_ready: Whether to wait for printer to be ready
            storage: Storage location ('local' or 'usb')

        Returns:
            Dictionary with submission results

        Raises:
            FileNotFoundError: If G-code file doesn't exist
            RuntimeError: If printer is not ready and wait_for_ready is False
        """
        gcode_path = Path(gcode_path)

        if not gcode_path.exists():
            raise FileNotFoundError(f"G-code file not found: {gcode_path}")

        if filename is None:
            filename = gcode_path.name

        with LogContext("job_submission"):
            # Check printer readiness
            if wait_for_ready:
                if not self.wait_for_ready():
                    raise RuntimeError("Printer is not ready for job submission")
            else:
                status = self.get_status()
                if not status.is_ready:
                    raise RuntimeError(f"Printer not ready (state: {status.state})")

            # Submit job
            logger.info(f"Submitting job: {gcode_path} -> {filename}")

            result = self.client.upload_file(
                str(gcode_path), filename, auto_start=auto_start
            )

            if result.get("fallback"):
                logger.warning("Job submission fell back to manual mode")
                return {
                    "success": False,
                    "fallback": True,
                    "instructions": result.get("instructions", []),
                    "filename": filename,
                }
            else:
                logger.info(f"Job submitted successfully: {filename}")
                return {
                    "success": True,
                    "fallback": False,
                    "filename": result.get("filename", filename),
                    "auto_started": result.get("auto_started", False),
                }

    def start_print(self, filename: str) -> bool:
        """Start printing a previously uploaded file.

        Args:
            filename: Name of file to print

        Returns:
            True if print started successfully, False otherwise
        """
        with LogContext("start_print"):
            logger.info(f"Starting print: {filename}")
            return self.client.start_print(filename)

    def stop_print(self) -> bool:
        """Stop current print job.

        Returns:
            True if print stopped successfully, False otherwise
        """
        with LogContext("stop_print"):
            logger.info("Stopping current print")
            return self.client.stop_print()

    def get_job_progress(self) -> Optional[Dict[str, Any]]:
        """Get current job progress information.

        Returns:
            Dictionary with job progress or None if no job
        """
        status = self.get_status()

        if not status.job_file:
            return None

        return {
            "filename": status.job_file,
            "progress_percent": status.job_progress,
            "time_remaining": status.job_time_remaining,
            "state": status.state,
        }

    def monitor_print(self, callback=None, check_interval: int = 10) -> Dict[str, Any]:
        """Monitor print progress until completion.

        Args:
            callback: Optional callback function called with status updates
            check_interval: Status check interval in seconds

        Returns:
            Dictionary with final print results
        """
        import time

        logger.info("Starting print monitoring")
        start_time = time.time()

        try:
            while True:
                status = self.get_status()

                if callback:
                    callback(status)

                # Check if print is complete
                if status.state in ["Finished", "Operational"]:
                    if status.state == "Finished":
                        logger.info("Print completed successfully")
                        return {
                            "success": True,
                            "state": "completed",
                            "duration": time.time() - start_time,
                        }
                    elif status.state == "Operational" and status.job_file is None:
                        logger.info("Print finished (no active job)")
                        return {
                            "success": True,
                            "state": "completed",
                            "duration": time.time() - start_time,
                        }

                # Check for error states
                elif status.state in ["Error", "Offline"]:
                    logger.error(f"Print failed with state: {status.state}")
                    return {
                        "success": False,
                        "state": status.state,
                        "duration": time.time() - start_time,
                    }

                # Continue monitoring
                time.sleep(check_interval)

        except KeyboardInterrupt:
            logger.info("Print monitoring stopped by user")
            return {
                "success": False,
                "state": "interrupted",
                "duration": time.time() - start_time,
            }
        except Exception as e:
            logger.error(f"Print monitoring failed: {e}")
            return {
                "success": False,
                "state": "error",
                "error": str(e),
                "duration": time.time() - start_time,
            }

    def list_files(self, location: str = "local") -> List[Dict[str, Any]]:
        """List files on printer storage.

        Args:
            location: Storage location ('local' or 'usb')

        Returns:
            List of file information dictionaries
        """
        # This would need to be implemented in the PrusaLink client
        # For now, return empty list as placeholder
        logger.warning("File listing not yet implemented")
        return []

    def delete_file(self, filename: str, location: str = "local") -> bool:
        """Delete a file from printer storage.

        Args:
            filename: Name of file to delete
            location: Storage location ('local' or 'usb')

        Returns:
            True if file deleted successfully, False otherwise
        """
        # This would need to be implemented in the PrusaLink client
        # For now, return False as placeholder
        logger.warning("File deletion not yet implemented")
        return False

    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information.

        Returns:
            Dictionary with connection details
        """
        return {
            "secrets_file": str(self.secrets_path),
            "connected": self.is_connected(),
            "client_type": "ResilientPrusaLinkClient",
        }


class SecurityError(Exception):
    """Raised when security validation fails."""

    pass
