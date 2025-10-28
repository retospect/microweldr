"""System monitoring and health check API."""

import logging
import time
from typing import Any, Dict, List, Optional

from ..core.health_checks import (
    HealthChecker,
    generate_health_report,
    quick_health_check,
)
from ..core.logging_config import LogContext

logger = logging.getLogger(__name__)


class HealthStatus:
    """Represents system health status."""

    def __init__(self, health_data: Dict[str, Any]):
        """Initialize health status.

        Args:
            health_data: Raw health data from health checker
        """
        self.raw_data = health_data
        self.overall = health_data.get("overall", "unknown")
        self.timestamp = health_data.get("timestamp", time.time())
        self.checks = health_data.get("checks", {})
        self.warnings = health_data.get("warnings", [])
        self.errors = health_data.get("errors", [])
        self.recommendations = health_data.get("recommendations", [])
        self.system_info = health_data.get("system_info", {})

    @property
    def is_healthy(self) -> bool:
        """Check if system is healthy."""
        return self.overall == "healthy"

    @property
    def is_degraded(self) -> bool:
        """Check if system is degraded but functional."""
        return self.overall == "degraded"

    @property
    def is_unhealthy(self) -> bool:
        """Check if system is unhealthy."""
        return self.overall == "unhealthy"

    @property
    def error_count(self) -> int:
        """Get total error count."""
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """Get total warning count."""
        return len(self.warnings)

    def get_failed_checks(self) -> List[str]:
        """Get list of failed check names.

        Returns:
            List of failed check names
        """
        return [
            name for name, data in self.checks.items() if data.get("status") == "error"
        ]

    def get_degraded_checks(self) -> List[str]:
        """Get list of degraded check names.

        Returns:
            List of degraded check names
        """
        return [
            name
            for name, data in self.checks.items()
            if data.get("status") == "warning"
        ]

    def get_check_status(self, check_name: str) -> Optional[str]:
        """Get status of specific check.

        Args:
            check_name: Name of check

        Returns:
            Check status or None if not found
        """
        check_data = self.checks.get(check_name, {})
        return check_data.get("status")

    def get_check_message(self, check_name: str) -> Optional[str]:
        """Get message for specific check.

        Args:
            check_name: Name of check

        Returns:
            Check message or None if not found
        """
        check_data = self.checks.get(check_name, {})
        return check_data.get("message")

    def __str__(self) -> str:
        """String representation."""
        return f"HealthStatus({self.overall}, {self.error_count} errors, {self.warning_count} warnings)"


class SystemMonitor:
    """System monitoring and health management."""

    def __init__(self, secrets_path: Optional[str] = None):
        """Initialize system monitor.

        Args:
            secrets_path: Optional path to secrets file for printer checks
        """
        self.secrets_path = secrets_path
        self.health_checker = HealthChecker()
        self._monitoring_active = False
        self._last_health_check: Optional[HealthStatus] = None

        logger.info("System monitor initialized")

    def get_health_status(self, include_printer: bool = True) -> HealthStatus:
        """Get current system health status.

        Args:
            include_printer: Whether to include printer connectivity checks

        Returns:
            HealthStatus object
        """
        with LogContext("health_check"):
            secrets_path = self.secrets_path if include_printer else None
            health_data = self.health_checker.run_all_checks(secrets_path)

            status = HealthStatus(health_data)
            self._last_health_check = status

            logger.debug(f"Health check completed: {status}")
            return status

    def quick_check(self) -> HealthStatus:
        """Perform a quick health check (critical systems only).

        Returns:
            HealthStatus with quick check results
        """
        with LogContext("quick_health_check"):
            overall_status, critical_issues = quick_health_check()

            # Convert to health data format
            health_data = {
                "overall": overall_status,
                "timestamp": time.time(),
                "checks": {
                    "quick_check": {
                        "status": "healthy" if overall_status == "healthy" else "error",
                        "message": f"Quick check: {overall_status}",
                    }
                },
                "warnings": [],
                "errors": critical_issues,
                "recommendations": [],
                "system_info": {},
            }

            status = HealthStatus(health_data)
            logger.debug(f"Quick health check completed: {status}")
            return status

    def check_printer_connectivity(self) -> Dict[str, Any]:
        """Check printer connectivity specifically.

        Returns:
            Dictionary with printer connectivity status
        """
        if not self.secrets_path:
            return {
                "status": "skipped",
                "message": "No secrets file configured",
                "connected": False,
            }

        try:
            from .printer import PrinterConnection

            printer = PrinterConnection(self.secrets_path, validate_secrets=False)
            is_connected = printer.is_connected()

            if is_connected:
                status = printer.get_status()
                return {
                    "status": "healthy",
                    "message": f"Printer connected: {status.state}",
                    "connected": True,
                    "printer_state": status.state,
                    "bed_temp": status.bed_actual,
                    "nozzle_temp": status.nozzle_actual,
                }
            else:
                return {
                    "status": "error",
                    "message": "Printer not responding",
                    "connected": False,
                }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Printer check failed: {e}",
                "connected": False,
                "error": str(e),
            }

    def get_system_info(self) -> Dict[str, Any]:
        """Get detailed system information.

        Returns:
            Dictionary with system information
        """
        import platform
        import sys
        from pathlib import Path

        try:
            import psutil

            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            memory_info = {
                "total_gb": memory.total / (1024**3),
                "available_gb": memory.available / (1024**3),
                "percent_used": memory.percent,
            }

            disk_info = {
                "total_gb": disk.total / (1024**3),
                "free_gb": disk.free / (1024**3),
                "percent_used": (disk.used / disk.total) * 100,
            }
        except ImportError:
            memory_info = {"status": "psutil not available"}
            disk_info = {"status": "psutil not available"}

        return {
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
            },
            "python": {
                "version": platform.python_version(),
                "implementation": platform.python_implementation(),
                "executable": sys.executable,
            },
            "memory": memory_info,
            "disk": disk_info,
            "working_directory": str(Path.cwd()),
            "microweldr_version": "4.0.0",
        }

    def generate_report(self, output_path: Optional[str] = None) -> str:
        """Generate comprehensive health report.

        Args:
            output_path: Optional path to save report file

        Returns:
            Report content as string
        """
        with LogContext("health_report"):
            report = generate_health_report(output_path)
            logger.info(f"Health report generated: {len(report)} characters")
            return report

    def start_monitoring(
        self,
        interval: int = 300,
        callback: Optional[callable] = None,
        include_printer: bool = True,
    ) -> None:
        """Start continuous health monitoring.

        Args:
            interval: Check interval in seconds
            callback: Optional callback function for status updates
            include_printer: Whether to include printer checks
        """
        if self._monitoring_active:
            logger.warning("Monitoring already active")
            return

        self._monitoring_active = True
        logger.info(f"Starting health monitoring (interval: {interval}s)")

        try:
            while self._monitoring_active:
                start_time = time.time()

                # Perform health check
                status = self.get_health_status(include_printer=include_printer)

                # Call callback if provided
                if callback:
                    try:
                        callback(status)
                    except Exception as e:
                        logger.error(f"Monitoring callback failed: {e}")

                # Log status changes
                if status.is_unhealthy:
                    logger.error(f"System unhealthy: {status.error_count} errors")
                elif status.is_degraded:
                    logger.warning(f"System degraded: {status.warning_count} warnings")
                else:
                    logger.debug("System healthy")

                # Sleep until next check
                elapsed = time.time() - start_time
                sleep_time = max(0, interval - elapsed)

                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("Health monitoring stopped by user")
        except Exception as e:
            logger.error(f"Health monitoring failed: {e}")
        finally:
            self._monitoring_active = False

    def stop_monitoring(self) -> None:
        """Stop continuous monitoring."""
        if self._monitoring_active:
            self._monitoring_active = False
            logger.info("Health monitoring stopped")
        else:
            logger.warning("Monitoring not active")

    def is_monitoring(self) -> bool:
        """Check if monitoring is active.

        Returns:
            True if monitoring is active, False otherwise
        """
        return self._monitoring_active

    def get_last_status(self) -> Optional[HealthStatus]:
        """Get last health check status.

        Returns:
            Last HealthStatus or None if no checks performed
        """
        return self._last_health_check

    def wait_for_healthy(
        self,
        timeout: int = 300,
        check_interval: int = 10,
        include_printer: bool = False,
    ) -> bool:
        """Wait for system to become healthy.

        Args:
            timeout: Maximum wait time in seconds
            check_interval: Check interval in seconds
            include_printer: Whether to include printer in health check

        Returns:
            True if system became healthy, False if timeout
        """
        start_time = time.time()

        logger.info(f"Waiting for system to become healthy (timeout: {timeout}s)")

        while time.time() - start_time < timeout:
            status = self.get_health_status(include_printer=include_printer)

            if status.is_healthy:
                logger.info("System is healthy")
                return True

            logger.debug(f"System not healthy ({status.overall}), waiting...")
            time.sleep(check_interval)

        logger.warning(f"System did not become healthy within {timeout} seconds")
        return False

    def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics.

        Returns:
            Dictionary with monitoring statistics
        """
        return {
            "monitoring_active": self._monitoring_active,
            "secrets_configured": self.secrets_path is not None,
            "last_check_time": (
                self._last_health_check.timestamp if self._last_health_check else None
            ),
            "last_status": (
                str(self._last_health_check) if self._last_health_check else None
            ),
        }


def create_monitoring_callback(log_level: str = "INFO") -> callable:
    """Create a standard monitoring callback function.

    Args:
        log_level: Logging level for status updates

    Returns:
        Callback function for monitoring
    """

    def callback(status: HealthStatus):
        """Standard monitoring callback."""
        if status.is_unhealthy:
            logger.error(
                f"System Health: {status.overall} ({status.error_count} errors)"
            )
            for error in status.errors[:3]:  # Log first 3 errors
                logger.error(f"  - {error}")
        elif status.is_degraded:
            logger.warning(
                f"System Health: {status.overall} ({status.warning_count} warnings)"
            )
        else:
            if log_level == "DEBUG":
                logger.info(f"System Health: {status.overall}")

    return callback


def monitor_system_health(
    interval: int = 300,
    secrets_path: Optional[str] = None,
    include_printer: bool = True,
    log_level: str = "INFO",
) -> None:
    """Convenience function to start system monitoring.

    Args:
        interval: Check interval in seconds
        secrets_path: Optional path to secrets file
        include_printer: Whether to include printer checks
        log_level: Logging level for status updates
    """
    monitor = SystemMonitor(secrets_path)
    callback = create_monitoring_callback(log_level)

    try:
        monitor.start_monitoring(
            interval=interval, callback=callback, include_printer=include_printer
        )
    except KeyboardInterrupt:
        monitor.stop_monitoring()
        logger.info("System monitoring stopped")
