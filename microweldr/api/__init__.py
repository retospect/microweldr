"""MicroWeldr Library API - Main entry point for programmatic access.

This module provides a high-level API for using MicroWeldr as a library,
exposing all the main functionality that's available from the command line.

Example usage:
    from microweldr.api import MicroWeldr, WeldJob, PrinterConnection

    # Create a welding job
    welder = MicroWeldr()
    job = welder.create_job('design.svg')

    # Generate G-code
    gcode_path = job.generate_gcode('output.gcode')

    # Submit to printer
    printer = PrinterConnection('secrets.toml')
    printer.submit_job(gcode_path, auto_start=True)
"""

from .core import MicroWeldr, ValidationResult, WeldJob
from .monitoring import HealthStatus, SystemMonitor
from .printer import PrinterConnection, PrinterStatus
from .validation import ValidationSuite
from .workflow import WorkflowManager, WorkflowStep

__all__ = [
    # Core API
    "MicroWeldr",
    "WeldJob",
    "ValidationResult",
    # Printer API
    "PrinterConnection",
    "PrinterStatus",
    # Workflow API
    "WorkflowManager",
    "WorkflowStep",
    # Validation API
    "ValidationSuite",
    # Monitoring API
    "SystemMonitor",
    "HealthStatus",
]

# Version info
__version__ = "4.0.0"
__author__ = "MicroWeldr Team"
