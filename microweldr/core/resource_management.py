"""Resource management utilities with context managers for safe operations."""

import logging
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union

logger = logging.getLogger(__name__)


class ManagedFile:
    """Context manager for safe file operations with automatic cleanup."""

    def __init__(
        self,
        file_path: Union[str, Path],
        mode: str = "r",
        encoding: str = "utf-8",
        cleanup_on_error: bool = True,
        backup_original: bool = False,
    ):
        """Initialize managed file.

        Args:
            file_path: Path to file
            mode: File open mode
            encoding: File encoding
            cleanup_on_error: Whether to delete file on error (for write modes)
            backup_original: Whether to create backup of original file
        """
        self.file_path = Path(file_path)
        self.mode = mode
        self.encoding = encoding
        self.cleanup_on_error = cleanup_on_error
        self.backup_original = backup_original
        self.file_handle = None
        self.backup_path = None
        self._lock = threading.Lock()

    def __enter__(self):
        """Enter file context."""
        with self._lock:
            try:
                # Create backup if requested and file exists
                if (
                    self.backup_original
                    and self.file_path.exists()
                    and "w" in self.mode
                ):
                    self.backup_path = self.file_path.with_suffix(
                        self.file_path.suffix + ".backup"
                    )
                    import shutil

                    shutil.copy2(self.file_path, self.backup_path)
                    logger.debug(f"Created backup: {self.backup_path}")

                # Ensure parent directory exists for write modes
                if "w" in self.mode or "a" in self.mode:
                    self.file_path.parent.mkdir(parents=True, exist_ok=True)

                # Open file
                self.file_handle = open(
                    self.file_path, self.mode, encoding=self.encoding
                )
                logger.debug(f"Opened file: {self.file_path} (mode: {self.mode})")

                return self.file_handle

            except Exception as e:
                logger.error(f"Failed to open file {self.file_path}: {e}")
                self._cleanup_on_error()
                raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit file context with cleanup."""
        with self._lock:
            # Close file handle
            if self.file_handle:
                try:
                    self.file_handle.close()
                    logger.debug(f"Closed file: {self.file_path}")
                except Exception as e:
                    logger.warning(f"Error closing file {self.file_path}: {e}")

            # Handle errors
            if exc_type is not None:
                logger.error(f"Error in file operation for {self.file_path}: {exc_val}")
                if self.cleanup_on_error:
                    self._cleanup_on_error()
                return False  # Don't suppress the exception

            # Clean up backup if operation was successful
            if self.backup_path and self.backup_path.exists():
                try:
                    self.backup_path.unlink()
                    logger.debug(f"Removed backup: {self.backup_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove backup {self.backup_path}: {e}")

    def _cleanup_on_error(self):
        """Clean up files on error."""
        try:
            # Remove the main file if it was being written and cleanup is enabled
            if self.cleanup_on_error and "w" in self.mode and self.file_path.exists():
                self.file_path.unlink()
                logger.debug(f"Cleaned up failed file: {self.file_path}")

            # Restore backup if it exists
            if self.backup_path and self.backup_path.exists():
                import shutil

                shutil.move(self.backup_path, self.file_path)
                logger.info(f"Restored backup: {self.backup_path} -> {self.file_path}")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


class TemporaryFileManager:
    """Context manager for temporary files with automatic cleanup."""

    def __init__(
        self, suffix: str = "", prefix: str = "microweldr_", dir: Optional[str] = None
    ):
        """Initialize temporary file manager.

        Args:
            suffix: File suffix
            prefix: File prefix
            dir: Directory for temporary files
        """
        self.suffix = suffix
        self.prefix = prefix
        self.dir = dir
        self.temp_files: List[Path] = []
        self._lock = threading.Lock()

    def __enter__(self):
        """Enter temporary file context."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and clean up all temporary files."""
        self.cleanup_all()

    def create_temp_file(self, mode: str = "w+", encoding: str = "utf-8") -> Path:
        """Create a new temporary file.

        Args:
            mode: File open mode
            encoding: File encoding

        Returns:
            Path to temporary file
        """
        with self._lock:
            temp_fd, temp_path = tempfile.mkstemp(
                suffix=self.suffix, prefix=self.prefix, dir=self.dir
            )

            # Close the file descriptor since we'll manage the file ourselves
            import os

            os.close(temp_fd)

            temp_path = Path(temp_path)
            self.temp_files.append(temp_path)

            logger.debug(f"Created temporary file: {temp_path}")
            return temp_path

    def create_temp_dir(self) -> Path:
        """Create a temporary directory.

        Returns:
            Path to temporary directory
        """
        with self._lock:
            temp_dir = Path(
                tempfile.mkdtemp(suffix=self.suffix, prefix=self.prefix, dir=self.dir)
            )

            self.temp_files.append(temp_dir)
            logger.debug(f"Created temporary directory: {temp_dir}")
            return temp_dir

    def cleanup_all(self):
        """Clean up all temporary files and directories."""
        with self._lock:
            for temp_path in self.temp_files:
                try:
                    if temp_path.exists():
                        if temp_path.is_file():
                            temp_path.unlink()
                            logger.debug(f"Removed temporary file: {temp_path}")
                        elif temp_path.is_dir():
                            import shutil

                            shutil.rmtree(temp_path)
                            logger.debug(f"Removed temporary directory: {temp_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove temporary path {temp_path}: {e}")

            self.temp_files.clear()


class ResourcePool:
    """Generic resource pool with context management."""

    def __init__(self, max_size: int = 10):
        """Initialize resource pool.

        Args:
            max_size: Maximum number of resources in pool
        """
        self.max_size = max_size
        self.resources: List[Any] = []
        self.in_use: Dict[int, Any] = {}
        self._lock = threading.Lock()
        self._resource_id = 0

    def acquire(self, factory_func, *args, **kwargs):
        """Acquire a resource from the pool.

        Args:
            factory_func: Function to create new resource if needed
            *args, **kwargs: Arguments for factory function

        Returns:
            Resource context manager
        """
        return ResourceContext(self, factory_func, *args, **kwargs)

    def _get_resource(self, factory_func, *args, **kwargs):
        """Get resource from pool or create new one."""
        with self._lock:
            if self.resources:
                resource = self.resources.pop()
                logger.debug(
                    f"Reused resource from pool (pool size: {len(self.resources)})"
                )
            else:
                resource = factory_func(*args, **kwargs)
                logger.debug("Created new resource")

            self._resource_id += 1
            resource_id = self._resource_id
            self.in_use[resource_id] = resource

            return resource_id, resource

    def _return_resource(self, resource_id: int, resource: Any):
        """Return resource to pool."""
        with self._lock:
            if resource_id in self.in_use:
                del self.in_use[resource_id]

            if len(self.resources) < self.max_size:
                self.resources.append(resource)
                logger.debug(
                    f"Returned resource to pool (pool size: {len(self.resources)})"
                )
            else:
                # Pool is full, discard resource
                if hasattr(resource, "close"):
                    try:
                        resource.close()
                    except Exception as e:
                        logger.warning(f"Error closing discarded resource: {e}")
                logger.debug("Discarded resource (pool full)")

    def cleanup(self):
        """Clean up all resources in pool."""
        with self._lock:
            # Clean up pooled resources
            for resource in self.resources:
                if hasattr(resource, "close"):
                    try:
                        resource.close()
                    except Exception as e:
                        logger.warning(f"Error closing pooled resource: {e}")

            # Clean up in-use resources
            for resource in self.in_use.values():
                if hasattr(resource, "close"):
                    try:
                        resource.close()
                    except Exception as e:
                        logger.warning(f"Error closing in-use resource: {e}")

            self.resources.clear()
            self.in_use.clear()
            logger.debug("Cleaned up resource pool")


class ResourceContext:
    """Context manager for pooled resources."""

    def __init__(self, pool: ResourcePool, factory_func, *args, **kwargs):
        """Initialize resource context.

        Args:
            pool: Resource pool
            factory_func: Function to create resource
            *args, **kwargs: Arguments for factory function
        """
        self.pool = pool
        self.factory_func = factory_func
        self.args = args
        self.kwargs = kwargs
        self.resource_id = None
        self.resource = None

    def __enter__(self):
        """Enter resource context."""
        self.resource_id, self.resource = self.pool._get_resource(
            self.factory_func, *self.args, **self.kwargs
        )
        return self.resource

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit resource context."""
        if self.resource_id is not None and self.resource is not None:
            self.pool._return_resource(self.resource_id, self.resource)


@contextmanager
def safe_gcode_generation(
    output_path: Union[str, Path], backup: bool = True
) -> Generator[Path, None, None]:
    """Context manager for safe G-code generation with backup and cleanup.

    Args:
        output_path: Target output path
        backup: Whether to create backup of existing file

    Yields:
        Path object for the output file
    """
    output_path = Path(output_path)
    backup_path = None
    temp_path = None

    try:
        # Create backup if file exists and backup is requested
        if backup and output_path.exists():
            backup_path = output_path.with_suffix(output_path.suffix + ".backup")
            import shutil

            shutil.copy2(output_path, backup_path)
            logger.info(f"Created backup: {backup_path}")

        # Create temporary file for generation
        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        yield temp_path

        # Move temporary file to final location on success
        if temp_path.exists():
            temp_path.replace(output_path)
            logger.info(f"G-code generation completed: {output_path}")

        # Remove backup on success
        if backup_path and backup_path.exists():
            backup_path.unlink()
            logger.debug(f"Removed backup: {backup_path}")

    except Exception as e:
        logger.error(f"G-code generation failed: {e}")

        # Clean up temporary file
        if temp_path and temp_path.exists():
            temp_path.unlink()
            logger.debug(f"Cleaned up temporary file: {temp_path}")

        # Restore backup if it exists
        if backup_path and backup_path.exists():
            if output_path.exists():
                output_path.unlink()
            backup_path.replace(output_path)
            logger.info(f"Restored backup: {output_path}")

        raise


@contextmanager
def managed_printer_operation(
    operation_name: str,
) -> Generator[Dict[str, Any], None, None]:
    """Context manager for printer operations with status tracking.

    Args:
        operation_name: Name of the operation

    Yields:
        Status dictionary for tracking operation state
    """
    status = {
        "operation": operation_name,
        "started": False,
        "completed": False,
        "error": None,
        "cleanup_needed": False,
    }

    logger.info(f"Starting printer operation: {operation_name}")

    try:
        status["started"] = True
        yield status

        if not status.get("error"):
            status["completed"] = True
            logger.info(f"Printer operation completed: {operation_name}")

    except Exception as e:
        status["error"] = str(e)
        logger.error(f"Printer operation failed: {operation_name} - {e}")
        raise

    finally:
        # Perform any necessary cleanup
        if status.get("cleanup_needed"):
            logger.info(f"Performing cleanup for: {operation_name}")
            # Add specific cleanup logic here if needed
