"""Tests for error handling framework."""

import pytest
import logging

from microweldr.core.error_handling import (
    MicroWeldrError,
    ValidationError,
    ConfigurationError,
    FileProcessingError,
    handle_errors,
    error_context,
    safe_execute,
    ErrorCollector,
)


class TestMicroWeldrError:
    """Test MicroWeldr error classes."""

    def test_base_error(self):
        """Test base MicroWeldr error."""
        error = MicroWeldrError("Test error", {"key": "value"})
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.details == {"key": "value"}

    def test_specific_errors(self):
        """Test specific error types."""
        validation_error = ValidationError("Invalid input")
        assert isinstance(validation_error, MicroWeldrError)

        config_error = ConfigurationError("Bad config")
        assert isinstance(config_error, MicroWeldrError)

        file_error = FileProcessingError("File not found")
        assert isinstance(file_error, MicroWeldrError)


class TestHandleErrors:
    """Test error handling decorator."""

    def test_successful_execution(self):
        """Test decorator with successful function."""

        @handle_errors()
        def successful_function():
            return "success"

        result = successful_function()
        assert result == "success"

    def test_error_mapping(self):
        """Test error type mapping."""

        @handle_errors(error_types={ValueError: ValidationError}, reraise=True)
        def failing_function():
            raise ValueError("Invalid value")

        with pytest.raises(ValidationError) as exc_info:
            failing_function()

        assert "Invalid value" in str(exc_info.value)
        assert "original_error" in exc_info.value.details

    def test_no_reraise(self):
        """Test decorator with reraise=False."""

        @handle_errors(reraise=False)
        def failing_function():
            raise ValueError("Test error")

        result = failing_function()
        assert result is None


class TestErrorContext:
    """Test error context manager."""

    def test_successful_context(self):
        """Test context manager with successful operation."""
        with error_context("test_operation", file="test.txt") as ctx:
            assert ctx.operation == "test_operation"
            assert ctx.context["file"] == "test.txt"

    def test_error_context_enhancement(self):
        """Test error context enhancement."""
        with pytest.raises(MicroWeldrError) as exc_info:
            with error_context("test_operation", file="test.txt"):
                raise MicroWeldrError("Test error")

        error = exc_info.value
        assert error.details["operation"] == "test_operation"
        assert error.details["file"] == "test.txt"


class TestSafeExecute:
    """Test safe execution utility."""

    def test_successful_execution(self):
        """Test safe execution with successful function."""

        def add_numbers(a, b):
            return a + b

        result = safe_execute(add_numbers, 2, 3)
        assert result == 5

    def test_failed_execution(self):
        """Test safe execution with failing function."""

        def failing_function():
            raise ValueError("Test error")

        result = safe_execute(failing_function, default_return="default")
        assert result == "default"

    def test_with_kwargs(self):
        """Test safe execution with keyword arguments."""

        def multiply(a, b=1):
            return a * b

        result = safe_execute(multiply, 5, b=3)
        assert result == 15


class TestErrorCollector:
    """Test error collector utility."""

    def test_empty_collector(self):
        """Test empty error collector."""
        collector = ErrorCollector()
        assert not collector.has_errors()
        assert not collector.has_warnings()

    def test_add_errors(self):
        """Test adding errors."""
        collector = ErrorCollector()
        collector.add_error("First error")
        collector.add_error(ValidationError("Second error"))

        assert collector.has_errors()
        assert len(collector.errors) == 2

    def test_add_warnings(self):
        """Test adding warnings."""
        collector = ErrorCollector()
        collector.add_warning("First warning")
        collector.add_warning("Second warning")

        assert collector.has_warnings()
        assert len(collector.warnings) == 2

    def test_raise_if_errors(self):
        """Test raising combined error."""
        collector = ErrorCollector()
        collector.add_error("Error 1")
        collector.add_error("Error 2")
        collector.add_warning("Warning 1")

        with pytest.raises(MicroWeldrError) as exc_info:
            collector.raise_if_errors()

        error = exc_info.value
        assert "Multiple errors occurred" in str(error)
        assert error.details["error_count"] == 2
        assert error.details["warning_count"] == 1

    def test_no_raise_without_errors(self):
        """Test no raise when no errors."""
        collector = ErrorCollector()
        collector.add_warning("Just a warning")

        # Should not raise
        collector.raise_if_errors()

    def test_clear(self):
        """Test clearing collector."""
        collector = ErrorCollector()
        collector.add_error("Error")
        collector.add_warning("Warning")

        collector.clear()

        assert not collector.has_errors()
        assert not collector.has_warnings()
