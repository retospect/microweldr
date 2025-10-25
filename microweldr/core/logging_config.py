"""Structured logging configuration for MicroWeldr."""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional


class WeldFormatter(logging.Formatter):
    """Custom formatter for welding operations with structured output."""

    def __init__(self):
        super().__init__()

    def format(self, record):
        # Add structured fields
        if not hasattr(record, "operation"):
            record.operation = "general"
        if not hasattr(record, "component"):
            record.component = record.name.split(".")[-1]

        # Color coding for console output
        colors = {
            "DEBUG": "\033[36m",  # Cyan
            "INFO": "\033[32m",  # Green
            "WARNING": "\033[33m",  # Yellow
            "ERROR": "\033[31m",  # Red
            "CRITICAL": "\033[35m",  # Magenta
        }
        reset = "\033[0m"

        # Format timestamp
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")

        # Build structured message
        if hasattr(sys.stderr, "isatty") and sys.stderr.isatty():
            # Colored output for terminal
            color = colors.get(record.levelname, "")
            level_str = f"{color}{record.levelname:8}{reset}"
        else:
            # Plain output for files/pipes
            level_str = f"{record.levelname:8}"

        component = f"[{record.component}]"

        # Main message
        message = record.getMessage()

        # Add operation context if available
        operation_str = ""
        if hasattr(record, "operation") and record.operation != "general":
            operation_str = f" ({record.operation})"

        return f"{timestamp} {level_str} {component:15} {message}{operation_str}"


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    console: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """Setup structured logging for MicroWeldr.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        console: Whether to log to console
        max_bytes: Maximum log file size before rotation
        backup_count: Number of backup log files to keep
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatter
    formatter = WeldFormatter()

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler with rotation
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setLevel(numeric_level)

        # Use plain formatter for files (no colors)
        file_formatter = logging.Formatter(
            "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Set specific logger levels
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    # Log setup completion
    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging initialized: level={level}, console={console}, file={log_file}"
    )


def get_logger(name: str, operation: str = "general") -> logging.Logger:
    """Get a logger with operation context.

    Args:
        name: Logger name (usually __name__)
        operation: Operation context (e.g., 'parsing', 'generation', 'upload')

    Returns:
        Configured logger with operation context
    """
    logger = logging.getLogger(name)

    # Add operation context to all log records
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.operation = operation
        return record

    # Only set factory once per logger to avoid stacking
    if not hasattr(logger, "_operation_set"):
        logging.setLogRecordFactory(record_factory)
        logger._operation_set = True

    return logger


class LogContext:
    """Context manager for operation-specific logging."""

    def __init__(self, operation: str, logger: Optional[logging.Logger] = None):
        """Initialize log context.

        Args:
            operation: Operation name
            logger: Logger to use (default: root logger)
        """
        self.operation = operation
        self.logger = logger or logging.getLogger()
        self.old_factory = None

    def __enter__(self):
        """Enter log context."""
        self.old_factory = logging.getLogRecordFactory()

        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            record.operation = self.operation
            return record

        logging.setLogRecordFactory(record_factory)
        self.logger.info(f"Started operation: {self.operation}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit log context."""
        if exc_type is not None:
            self.logger.error(f"Operation failed: {self.operation}", exc_info=True)
        else:
            self.logger.info(f"Completed operation: {self.operation}")

        # Restore original factory
        if self.old_factory:
            logging.setLogRecordFactory(self.old_factory)


def log_performance(func):
    """Decorator to log function performance."""
    import time
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        start_time = time.time()

        logger.debug(f"Starting {func.__name__}")
        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time
            logger.info(f"Completed {func.__name__} in {duration:.3f}s")
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Failed {func.__name__} after {duration:.3f}s: {e}")
            raise

    return wrapper


# Default logging setup
def init_default_logging():
    """Initialize default logging configuration."""
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Setup with reasonable defaults
    setup_logging(level="INFO", log_file=str(logs_dir / "microweldr.log"), console=True)


# Auto-initialize if imported directly
if __name__ != "__main__":
    # Only auto-initialize if no handlers are configured
    if not logging.getLogger().handlers:
        init_default_logging()
