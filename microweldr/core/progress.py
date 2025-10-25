"""Progress reporting utilities for long-running operations."""

import logging
import sys
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional, Union

logger = logging.getLogger(__name__)


class ProgressReporter:
    """Thread-safe progress reporter with multiple output formats."""

    def __init__(
        self,
        total: int,
        description: str = "Processing",
        show_percentage: bool = True,
        show_eta: bool = True,
        show_rate: bool = True,
        width: int = 50,
        file=None,
    ):
        """Initialize progress reporter.

        Args:
            total: Total number of items to process
            description: Description of the operation
            show_percentage: Whether to show percentage
            show_eta: Whether to show estimated time remaining
            show_rate: Whether to show processing rate
            width: Width of progress bar
            file: Output file (default: stderr)
        """
        self.total = total
        self.description = description
        self.show_percentage = show_percentage
        self.show_eta = show_eta
        self.show_rate = show_rate
        self.width = width
        self.file = file or sys.stderr

        self.current = 0
        self.start_time = time.time()
        self.last_update = 0
        self.update_interval = 0.1  # Update at most every 100ms
        self._lock = threading.Lock()
        self._closed = False

        # Check if output supports ANSI escape codes
        self.supports_ansi = (
            hasattr(self.file, "isatty")
            and self.file.isatty()
            and sys.platform != "win32"
        )

    def update(self, increment: int = 1, message: str = None) -> None:
        """Update progress.

        Args:
            increment: Amount to increment progress
            message: Optional status message
        """
        with self._lock:
            if self._closed:
                return

            self.current = min(self.current + increment, self.total)
            current_time = time.time()

            # Throttle updates to avoid excessive output
            if (
                current_time - self.last_update < self.update_interval
                and self.current < self.total
            ):
                return

            self.last_update = current_time
            self._render(message)

    def set_progress(self, current: int, message: str = None) -> None:
        """Set absolute progress.

        Args:
            current: Current progress value
            message: Optional status message
        """
        with self._lock:
            if self._closed:
                return

            self.current = min(max(current, 0), self.total)
            self._render(message)

    def _render(self, message: str = None) -> None:
        """Render progress bar."""
        if self.total == 0:
            return

        # Calculate progress
        progress = self.current / self.total
        elapsed = time.time() - self.start_time

        # Build progress bar
        filled_width = int(self.width * progress)
        bar = "█" * filled_width + "░" * (self.width - filled_width)

        # Build status line
        status_parts = [f"{self.description}: {bar}"]

        if self.show_percentage:
            status_parts.append(f"{progress * 100:.1f}%")

        status_parts.append(f"{self.current}/{self.total}")

        if self.show_rate and elapsed > 0:
            rate = self.current / elapsed
            if rate > 1:
                status_parts.append(f"{rate:.1f}/s")
            else:
                status_parts.append(f"{1/rate:.1f}s/item")

        if self.show_eta and self.current > 0 and self.current < self.total:
            remaining = (self.total - self.current) * elapsed / self.current
            if remaining < 60:
                status_parts.append(f"ETA: {remaining:.0f}s")
            elif remaining < 3600:
                status_parts.append(f"ETA: {remaining/60:.1f}m")
            else:
                status_parts.append(f"ETA: {remaining/3600:.1f}h")

        if message:
            status_parts.append(f"| {message}")

        status_line = " ".join(status_parts)

        # Output with proper line handling
        if self.supports_ansi:
            # Use ANSI escape codes to overwrite line
            self.file.write(f"\r{status_line}")
            self.file.flush()
        else:
            # Simple output for non-ANSI terminals
            self.file.write(f"{status_line}\n")
            self.file.flush()

    def finish(self, message: str = "Complete") -> None:
        """Finish progress reporting.

        Args:
            message: Completion message
        """
        with self._lock:
            if self._closed:
                return

            self.current = self.total
            self._render(message)

            if self.supports_ansi:
                self.file.write("\n")

            self._closed = True

            elapsed = time.time() - self.start_time
            logger.info(f"{self.description} completed in {elapsed:.2f}s")

    def close(self) -> None:
        """Close progress reporter."""
        if not self._closed:
            self.finish()

    def __enter__(self):
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        if exc_type is not None:
            self.finish("Failed")
        else:
            self.finish()


class SimpleProgressReporter:
    """Simple progress reporter for basic logging."""

    def __init__(
        self, total: int, description: str = "Processing", log_interval: int = 10
    ):
        """Initialize simple progress reporter.

        Args:
            total: Total number of items
            description: Operation description
            log_interval: Log every N percent
        """
        self.total = total
        self.description = description
        self.log_interval = log_interval
        self.current = 0
        self.last_logged_percent = -1
        self.start_time = time.time()

    def update(self, increment: int = 1) -> None:
        """Update progress.

        Args:
            increment: Amount to increment
        """
        self.current = min(self.current + increment, self.total)

        if self.total > 0:
            percent = int((self.current / self.total) * 100)

            # Log at intervals
            if (
                percent >= self.last_logged_percent + self.log_interval
                or self.current == self.total
            ):
                elapsed = time.time() - self.start_time
                rate = self.current / elapsed if elapsed > 0 else 0

                logger.info(
                    f"{self.description}: {percent}% ({self.current}/{self.total}) "
                    f"- {rate:.1f}/s"
                )

                self.last_logged_percent = percent

    def finish(self) -> None:
        """Finish progress reporting."""
        elapsed = time.time() - self.start_time
        logger.info(
            f"{self.description} completed: {self.total} items in {elapsed:.2f}s"
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finish()


@contextmanager
def progress_context(
    total: int, description: str = "Processing", use_fancy: bool = None, **kwargs
) -> Generator[Union[ProgressReporter, SimpleProgressReporter], None, None]:
    """Context manager for progress reporting.

    Args:
        total: Total number of items
        description: Operation description
        use_fancy: Whether to use fancy progress bar (auto-detect if None)
        **kwargs: Additional arguments for progress reporter

    Yields:
        Progress reporter instance
    """
    # Auto-detect fancy progress support
    if use_fancy is None:
        use_fancy = hasattr(sys.stderr, "isatty") and sys.stderr.isatty() and total > 10

    if use_fancy:
        with ProgressReporter(total, description, **kwargs) as reporter:
            yield reporter
    else:
        with SimpleProgressReporter(total, description) as reporter:
            yield reporter


def progress_wrapper(
    iterable, description: str = "Processing", total: int = None, **kwargs
):
    """Wrap an iterable with progress reporting.

    Args:
        iterable: Iterable to wrap
        description: Operation description
        total: Total items (auto-detected if None)
        **kwargs: Additional arguments for progress reporter

    Yields:
        Items from iterable with progress updates
    """
    # Try to get length if not provided
    if total is None:
        try:
            total = len(iterable)
        except (TypeError, AttributeError):
            # Use simple reporter for unknown length
            with SimpleProgressReporter(0, description) as reporter:
                count = 0
                for item in iterable:
                    count += 1
                    if count % 100 == 0:  # Log every 100 items
                        logger.info(f"{description}: processed {count} items")
                    yield item
                logger.info(f"{description}: completed {count} items")
            return

    with progress_context(total, description, **kwargs) as reporter:
        for item in iterable:
            yield item
            reporter.update()


class BatchProgressReporter:
    """Progress reporter for batch operations with sub-operations."""

    def __init__(self, batches: int, description: str = "Processing batches"):
        """Initialize batch progress reporter.

        Args:
            batches: Number of batches
            description: Operation description
        """
        self.batches = batches
        self.description = description
        self.current_batch = 0
        self.current_reporter: Optional[ProgressReporter] = None
        self.start_time = time.time()

    def start_batch(
        self, batch_size: int, batch_description: str = None
    ) -> ProgressReporter:
        """Start a new batch.

        Args:
            batch_size: Size of the batch
            batch_description: Description for this batch

        Returns:
            Progress reporter for the batch
        """
        if self.current_reporter:
            self.current_reporter.close()

        self.current_batch += 1

        if batch_description is None:
            batch_description = f"Batch {self.current_batch}/{self.batches}"

        logger.info(f"Starting {batch_description} ({batch_size} items)")

        self.current_reporter = ProgressReporter(
            total=batch_size, description=batch_description, width=40
        )

        return self.current_reporter

    def finish_batch(self) -> None:
        """Finish current batch."""
        if self.current_reporter:
            self.current_reporter.close()
            self.current_reporter = None

        # Log overall progress
        overall_progress = (self.current_batch / self.batches) * 100
        elapsed = time.time() - self.start_time

        logger.info(
            f"{self.description}: {overall_progress:.1f}% complete "
            f"({self.current_batch}/{self.batches} batches) - {elapsed:.1f}s elapsed"
        )

    def finish(self) -> None:
        """Finish all batch processing."""
        if self.current_reporter:
            self.current_reporter.close()

        elapsed = time.time() - self.start_time
        logger.info(
            f"{self.description} completed: {self.batches} batches in {elapsed:.2f}s"
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finish()


def with_progress(
    description: str = "Processing",
    show_progress: bool = None,
    log_progress: bool = True,
):
    """Decorator to add progress reporting to functions that process sequences.

    Args:
        description: Operation description
        show_progress: Whether to show progress bar (auto-detect if None)
        log_progress: Whether to log progress milestones
    """

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # Try to find a sequence argument to track
            sequence_arg = None
            total = 0

            # Look for common sequence parameter names
            for arg_name in ["items", "paths", "files", "data", "weld_paths"]:
                if arg_name in kwargs:
                    sequence_arg = kwargs[arg_name]
                    break

            # If no named sequence found, check positional args
            if sequence_arg is None and args:
                for arg in args:
                    if hasattr(arg, "__len__") and not isinstance(arg, str):
                        sequence_arg = arg
                        break

            # Get total if sequence found
            if sequence_arg is not None:
                try:
                    total = len(sequence_arg)
                except (TypeError, AttributeError):
                    total = 0

            # Execute with or without progress tracking
            if total > 1 and (
                show_progress is True or (show_progress is None and total > 10)
            ):
                with progress_context(total, description) as reporter:
                    # Monkey patch to track progress (simplified approach)
                    original_func = func

                    def tracked_func(*args, **kwargs):
                        result = original_func(*args, **kwargs)
                        reporter.update(1)
                        return result

                    return tracked_func(*args, **kwargs)
            else:
                if log_progress and total > 0:
                    logger.info(f"Starting {description} ({total} items)")

                start_time = time.time()
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time

                if log_progress:
                    logger.info(f"Completed {description} in {elapsed:.2f}s")

                return result

        return wrapper

    return decorator
