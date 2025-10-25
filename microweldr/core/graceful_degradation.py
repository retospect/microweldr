"""Graceful degradation utilities for printer communication and operations."""

import logging
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from ..prusalink.client import PrusaLinkClient
from ..prusalink.exceptions import (
    PrusaLinkAuthError,
    PrusaLinkConnectionError,
    PrusaLinkError,
)

logger = logging.getLogger(__name__)


class FallbackMode:
    """Manages fallback operations when primary systems fail."""

    def __init__(self):
        self.fallback_active = False
        self.fallback_reason = ""
        self.manual_instructions: List[str] = []

    def activate(self, reason: str, instructions: List[str] = None):
        """Activate fallback mode.

        Args:
            reason: Reason for fallback activation
            instructions: Manual instructions for user
        """
        self.fallback_active = True
        self.fallback_reason = reason
        self.manual_instructions = instructions or []
        logger.warning(f"Fallback mode activated: {reason}")

    def deactivate(self):
        """Deactivate fallback mode."""
        if self.fallback_active:
            logger.info("Fallback mode deactivated")
        self.fallback_active = False
        self.fallback_reason = ""
        self.manual_instructions.clear()

    def is_active(self) -> bool:
        """Check if fallback mode is active."""
        return self.fallback_active

    def get_instructions(self) -> List[str]:
        """Get manual instructions for current fallback."""
        return self.manual_instructions.copy()


# Global fallback mode instance
fallback_mode = FallbackMode()


def with_fallback(
    fallback_func: Optional[Callable] = None,
    fallback_value: Any = None,
    exceptions: tuple = (Exception,),
    max_retries: int = 3,
    retry_delay: float = 1.0,
    escalate_after: int = 1,
):
    """Decorator for graceful degradation with fallback options.

    Args:
        fallback_func: Function to call on failure
        fallback_value: Value to return on failure (if no fallback_func)
        exceptions: Exceptions to catch and handle
        max_retries: Maximum number of retries
        retry_delay: Delay between retries in seconds
        escalate_after: Number of failures before escalating to fallback
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            failure_count = 0

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    if failure_count > 0:
                        logger.info(
                            f"Operation recovered after {failure_count} failures"
                        )
                    return result

                except exceptions as e:
                    last_exception = e
                    failure_count += 1

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}"
                    )

                    if attempt < max_retries:
                        time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                        continue

                    # All retries exhausted
                    if failure_count >= escalate_after:
                        logger.error(
                            f"Operation failed after {max_retries + 1} attempts, using fallback"
                        )

                        if fallback_func:
                            try:
                                return fallback_func(*args, **kwargs)
                            except Exception as fallback_error:
                                logger.error(
                                    f"Fallback function also failed: {fallback_error}"
                                )

                        if fallback_value is not None:
                            return fallback_value

                    # Re-raise the last exception if no fallback worked
                    raise last_exception

        return wrapper

    return decorator


class ResilientPrusaLinkClient:
    """PrusaLink client with graceful degradation capabilities."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize resilient client.

        Args:
            config_path: Path to secrets configuration
        """
        self.config_path = config_path
        self._client: Optional[PrusaLinkClient] = None
        self._connection_healthy = True
        self._last_health_check = 0
        self._health_check_interval = 30  # seconds

    def _get_client(self) -> Optional[PrusaLinkClient]:
        """Get PrusaLink client with health checking."""
        current_time = time.time()

        # Periodic health check
        if current_time - self._last_health_check > self._health_check_interval:
            self._check_connection_health()
            self._last_health_check = current_time

        if not self._connection_healthy:
            return None

        if self._client is None:
            try:
                self._client = PrusaLinkClient(self.config_path)
                logger.info("PrusaLink client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize PrusaLink client: {e}")
                self._connection_healthy = False
                return None

        return self._client

    def _check_connection_health(self):
        """Check if PrusaLink connection is healthy."""
        try:
            if self._client:
                # Quick health check
                self._client.get_status()
                self._connection_healthy = True
        except Exception as e:
            logger.warning(f"PrusaLink health check failed: {e}")
            self._connection_healthy = False
            self._client = None

    @with_fallback(
        exceptions=(PrusaLinkError, PrusaLinkConnectionError, PrusaLinkAuthError),
        max_retries=2,
        retry_delay=2.0,
    )
    def upload_file(
        self, file_path: str, filename: str = None, auto_start: bool = False
    ) -> Dict:
        """Upload file with fallback to manual instructions.

        Args:
            file_path: Path to file to upload
            filename: Target filename (optional)
            auto_start: Whether to start print automatically

        Returns:
            Upload result or fallback instructions
        """
        client = self._get_client()
        if not client:
            return self._manual_upload_fallback(file_path, filename)

        return client.upload_file(file_path, filename, auto_start=auto_start)

    def _manual_upload_fallback(self, file_path: str, filename: str = None) -> Dict:
        """Provide manual upload instructions as fallback."""
        file_path = Path(file_path)
        target_name = filename or file_path.name

        instructions = [
            f"PrusaLink connection failed. Please manually upload the file:",
            f"1. Open your printer's web interface",
            f"2. Navigate to the Files section",
            f"3. Upload the file: {file_path.absolute()}",
            f"4. Rename it to: {target_name}",
            f"5. Start the print manually when ready",
        ]

        fallback_mode.activate("PrusaLink upload failed", instructions)

        # Print instructions to console for immediate visibility
        print("\n" + "=" * 60)
        print("🔄 MANUAL UPLOAD REQUIRED")
        print("=" * 60)
        for instruction in instructions:
            print(f"   {instruction}")
        print("=" * 60 + "\n")

        return {
            "success": False,
            "fallback": True,
            "instructions": instructions,
            "file_path": str(file_path.absolute()),
            "target_name": target_name,
        }

    @with_fallback(
        exceptions=(PrusaLinkError,),
        fallback_value={"state": "Unknown", "fallback": True},
        max_retries=1,
    )
    def get_status(self) -> Dict:
        """Get printer status with fallback."""
        client = self._get_client()
        if not client:
            return {"state": "Disconnected", "fallback": True}

        return client.get_status()

    @with_fallback(exceptions=(PrusaLinkError,), fallback_value=False, max_retries=1)
    def start_print(self, filename: str) -> bool:
        """Start print with fallback to manual instructions."""
        client = self._get_client()
        if not client:
            self._manual_start_fallback(filename)
            return False

        result = client.start_print(filename)
        return result.get("started", False)

    def _manual_start_fallback(self, filename: str):
        """Provide manual print start instructions."""
        instructions = [
            f"Cannot start print automatically. Please:",
            f"1. Go to your printer's web interface",
            f"2. Navigate to Files",
            f"3. Find and select: {filename}",
            f"4. Click 'Print' to start the job",
        ]

        print("\n" + "=" * 50)
        print("🖨️  MANUAL PRINT START REQUIRED")
        print("=" * 50)
        for instruction in instructions:
            print(f"   {instruction}")
        print("=" * 50 + "\n")

    @with_fallback(exceptions=(PrusaLinkError,), fallback_value=False, max_retries=1)
    def stop_print(self) -> bool:
        """Stop print with fallback to manual instructions."""
        client = self._get_client()
        if not client:
            self._manual_stop_fallback()
            return False

        result = client.stop_print()
        return result.get("stopped", False)

    def _manual_stop_fallback(self):
        """Provide manual print stop instructions."""
        instructions = [
            "Cannot stop print automatically. Please:",
            "1. Use the printer's physical controls, OR",
            "2. Go to the printer's web interface",
            "3. Click 'Stop' or 'Cancel' on the current job",
        ]

        print("\n" + "=" * 50)
        print("🛑 MANUAL PRINT STOP REQUIRED")
        print("=" * 50)
        for instruction in instructions:
            print(f"   {instruction}")
        print("=" * 50 + "\n")


def safe_file_operation(operation: str):
    """Decorator for safe file operations with cleanup."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            temp_files = []
            try:
                result = func(*args, **kwargs)

                # Track temporary files for cleanup
                if hasattr(result, "temp_files"):
                    temp_files.extend(result.temp_files)

                return result

            except Exception as e:
                logger.error(f"File operation '{operation}' failed: {e}")

                # Clean up any temporary files
                for temp_file in temp_files:
                    try:
                        Path(temp_file).unlink(missing_ok=True)
                        logger.debug(f"Cleaned up temporary file: {temp_file}")
                    except Exception as cleanup_error:
                        logger.warning(
                            f"Failed to clean up {temp_file}: {cleanup_error}"
                        )

                raise

        return wrapper

    return decorator


def check_system_health() -> Dict[str, Any]:
    """Check overall system health and return status."""
    health_status = {
        "overall": "healthy",
        "components": {},
        "warnings": [],
        "errors": [],
    }

    # Check PrusaLink connectivity
    try:
        client = ResilientPrusaLinkClient()
        status = client.get_status()
        if status.get("fallback"):
            health_status["components"]["prusalink"] = "degraded"
            health_status["warnings"].append("PrusaLink connection degraded")
        else:
            health_status["components"]["prusalink"] = "healthy"
    except Exception as e:
        health_status["components"]["prusalink"] = "failed"
        health_status["errors"].append(f"PrusaLink: {e}")

    # Check file system access
    try:
        test_file = Path("temp_health_check.txt")
        test_file.write_text("test")
        test_file.unlink()
        health_status["components"]["filesystem"] = "healthy"
    except Exception as e:
        health_status["components"]["filesystem"] = "failed"
        health_status["errors"].append(f"File system: {e}")

    # Check logging system
    try:
        logger.debug("Health check logging test")
        health_status["components"]["logging"] = "healthy"
    except Exception as e:
        health_status["components"]["logging"] = "failed"
        health_status["errors"].append(f"Logging: {e}")

    # Determine overall health
    if health_status["errors"]:
        health_status["overall"] = "unhealthy"
    elif health_status["warnings"]:
        health_status["overall"] = "degraded"

    return health_status
