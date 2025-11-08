"""Centralized error handling framework for MicroWeldr."""

import functools
import logging
import traceback
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union

logger = logging.getLogger(__name__)

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


class MicroWeldrError(Exception):
    """Base exception for all MicroWeldr errors."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(MicroWeldrError):
    """Raised when validation fails."""

    pass


class ConfigurationError(MicroWeldrError):
    """Raised when configuration is invalid."""

    pass


class FileProcessingError(MicroWeldrError):
    """Raised when file processing fails."""

    pass


class PrinterError(MicroWeldrError):
    """Raised when printer operations fail."""

    pass


class ParsingError(MicroWeldrError):
    """Raised when file parsing fails."""

    pass


class ErrorContext:
    """Context information for error handling."""

    def __init__(self, operation: str, file_path: Optional[str] = None, **kwargs):
        self.operation = operation
        self.file_path = file_path
        self.context = kwargs


def handle_errors(
    error_types: Optional[Dict[Type[Exception], Type[MicroWeldrError]]] = None,
    default_error: Type[MicroWeldrError] = MicroWeldrError,
    log_errors: bool = True,
    reraise: bool = True,
) -> Callable[[F], F]:
    """
    Decorator for standardized error handling.

    Args:
        error_types: Mapping of exception types to MicroWeldr error types
        default_error: Default error type for unmapped exceptions
        log_errors: Whether to log errors
        reraise: Whether to reraise as MicroWeldr errors
    """
    if error_types is None:
        error_types = {}

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(f"Error in {func.__name__}: {e}", exc_info=True)

                if not reraise:
                    return None

                # Map to appropriate MicroWeldr error
                error_type = error_types.get(type(e), default_error)

                # Preserve original error details
                details = {
                    "original_error": str(e),
                    "original_type": type(e).__name__,
                    "function": func.__name__,
                    "traceback": traceback.format_exc(),
                }

                raise error_type(
                    f"Error in {func.__name__}: {e}", details=details
                ) from e

        return wrapper

    return decorator


@contextmanager
def error_context(operation: str, **context_kwargs):
    """
    Context manager for error handling with operation context.

    Args:
        operation: Description of the operation being performed
        **context_kwargs: Additional context information
    """
    try:
        yield ErrorContext(operation, **context_kwargs)
    except Exception as e:
        logger.error(f"Error during {operation}: {e}", exc_info=True)

        # Add context to the error if it's a MicroWeldr error
        if isinstance(e, MicroWeldrError):
            e.details.update({"operation": operation, **context_kwargs})

        raise


def safe_execute(
    func: Callable,
    *args,
    default_return: Any = None,
    error_message: Optional[str] = None,
    log_errors: bool = True,
    **kwargs,
) -> Any:
    """
    Safely execute a function with error handling.

    Args:
        func: Function to execute
        *args: Function arguments
        default_return: Value to return on error
        error_message: Custom error message
        log_errors: Whether to log errors
        **kwargs: Function keyword arguments

    Returns:
        Function result or default_return on error
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_errors:
            message = error_message or f"Error executing {func.__name__}"
            logger.error(f"{message}: {e}", exc_info=True)
        return default_return


class ErrorCollector:
    """Collects multiple errors for batch processing."""

    def __init__(self):
        self.errors: list[MicroWeldrError] = []
        self.warnings: list[str] = []

    def add_error(self, error: Union[str, MicroWeldrError], **details):
        """Add an error to the collection."""
        if isinstance(error, str):
            error = MicroWeldrError(error, details)
        elif details:
            error.details.update(details)

        self.errors.append(error)

    def add_warning(self, warning: str):
        """Add a warning to the collection."""
        self.warnings.append(warning)

    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return len(self.warnings) > 0

    def raise_if_errors(self):
        """Raise a combined error if there are any errors."""
        if self.has_errors():
            messages = [str(error) for error in self.errors]
            combined_message = "Multiple errors occurred:\n" + "\n".join(
                f"- {msg}" for msg in messages
            )

            combined_details = {
                "error_count": len(self.errors),
                "warning_count": len(self.warnings),
                "errors": [error.details for error in self.errors],
                "warnings": self.warnings,
            }

            raise MicroWeldrError(combined_message, combined_details)

    def clear(self):
        """Clear all errors and warnings."""
        self.errors.clear()
        self.warnings.clear()


# Common error type mappings
COMMON_ERROR_MAPPINGS = {
    FileNotFoundError: FileProcessingError,
    PermissionError: FileProcessingError,
    ValueError: ValidationError,
    KeyError: ConfigurationError,
    TypeError: ValidationError,
}
