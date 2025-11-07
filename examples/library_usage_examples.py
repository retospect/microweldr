"""Examples of using MicroWeldr as a library.

This file demonstrates various ways to use MicroWeldr programmatically
for building custom applications and workflows.
"""

import logging
from pathlib import Path

# Import the MicroWeldr library API
from microweldr.api import (
    HealthStatus,
    MicroWeldr,
    PrinterConnection,
    PrinterStatus,
    SystemMonitor,
    ValidationResult,
    ValidationSuite,
    WeldJob,
    WorkflowManager,
    WorkflowStep
)


def example_basic_usage():
    """Basic usage example - simple SVG to G-code conversion."""
    print("=== Basic Usage Example ===")

    # Initialize MicroWeldr
    welder = MicroWeldr(log_level="INFO")

    # Create a weld job
    with welder.create_job("examples/calibration_test.svg") as job:
        # Validate the SVG
        validation = job.validate()
        print(f"Validation: {validation}")

        if validation.is_valid:
            # Generate G-code
            gcode_path = job.generate_gcode("output/test.gcode")
            print(f"G-code generated: {gcode_path}")

            # Generate animation
            animation_path = job.generate_animation("output/test_animation.svg")
            print(f"Animation generated: {animation_path}")

            # Get job statistics
            stats = job.get_statistics()
            print(
                f"Job stats: {stats['total_points']} points in {stats['total_paths']} paths"
            )


def example_printer_integration():
    """Example with printer integration."""
    print("\n=== Printer Integration Example ===")

    try:
        # Connect to printer
        printer = PrinterConnection("secrets.toml")

        # Check printer status
        status = printer.get_status()
        print(f"Printer status: {status}")

        if status.is_ready:
            # Create and process job
            welder = MicroWeldr()
            with welder.create_job("examples/calibration_test.svg") as job:
                # Generate G-code
                gcode_path = job.generate_gcode("output/printer_test.gcode")

                # Submit to printer
                result = printer.submit_job(gcode_path, auto_start=False)
                print(f"Submission result: {result}")

                if result["success"]:
                    # Start print
                    if printer.start_print(result["filename"]):
                        print("Print started successfully")

                        # Monitor progress (for demonstration, just check once)
                        progress = printer.get_job_progress()
                        if progress:
                            print(
                                f"Print progress: {progress['progress_percent']:.1f}%"
                            )
        else:
            print(f"Printer not ready: {status.state}")

    except Exception as e:
        print(f"Printer integration failed: {e}")


def example_workflow_management():
    """Example using workflow management for complex operations."""
    print("\n=== Workflow Management Example ===")

    # Create a custom workflow
    workflow = WorkflowManager("Custom Welding Workflow")

    # Add validation step
    workflow.add_validation_step("examples/calibration_test.svg")

    # Add G-code generation step
    workflow.add_gcode_generation_step("output/workflow_test.gcode")

    # Add animation generation step
    workflow.add_animation_generation_step(
        "output/workflow_animation.svg", required=False
    )

    # Add custom step
    def custom_processing_step(context):
        """Custom processing step."""
        gcode_path = context.get("gcode_path")
        if gcode_path:
            # Example: add custom post-processing
            print(f"Custom processing of {gcode_path}")
            return f"Processed {gcode_path}"
        return None

    workflow.add_custom_step(
        "custom_processing",
        custom_processing_step,
        description="Custom post-processing",
        required=False,
    )

    # Execute workflow
    try:
        results = workflow.execute()
        print(f"Workflow completed: {results['success_rate']:.1f}% success rate")
        print(f"Duration: {results['duration']:.2f} seconds")

        # Print step details
        for step_detail in results["step_details"]:
            status = step_detail["status"]
            name = step_detail["name"]
            duration = step_detail["duration"] or 0
            print(f"  {name}: {status} ({duration:.2f}s)")

    except Exception as e:
        print(f"Workflow failed: {e}")


def example_batch_processing():
    """Example of batch processing multiple SVG files."""
    print("\n=== Batch Processing Example ===")

    # List of SVG files to process
    svg_files = [
        "examples/calibration_test.svg",
        # Add more SVG files here
    ]

    # Initialize welder
    welder = MicroWeldr()

    # Process batch
    results = welder.batch_process(
        svg_files,
        output_dir="output/batch",
        generate_animations=True,
        continue_on_error=True,
    )

    print(f"Batch processing completed:")
    print(f"  Total processed: {results['total_processed']}")
    print(f"  Successful: {len(results['successful'])}")
    print(f"  Failed: {len(results['failed'])}")
    print(f"  Total points: {results['total_points']}")

    # Show failed files
    for failure in results["failed"]:
        print(f"  Failed: {failure['file']} - {failure['error']}")


def example_validation_suite():
    """Example using comprehensive validation."""
    print("\n=== Validation Suite Example ===")

    # Create validation suite
    validator = ValidationSuite()

    # Validate complete workflow
    report = validator.validate_complete_workflow(
        svg_path="examples/calibration_test.svg",
        gcode_path="output/test.gcode",  # If exists
        secrets_path="secrets.toml",  # If exists
    )

    print(f"Validation report: {report}")
    print(f"Overall status: {report.overall_status}")
    print(f"Total checks: {len(report.checks)}")

    # Show errors and warnings
    if report.has_errors:
        print("Errors:")
        for error in report.get_errors():
            print(f"  - {error}")

    if report.has_warnings:
        print("Warnings:")
        for warning in report.get_warnings():
            print(f"  - {warning}")

    # Quick validation
    is_valid = validator.quick_validate("examples/calibration_test.svg")
    print(f"Quick validation: {'PASS' if is_valid else 'FAIL'}")


def example_system_monitoring():
    """Example of system health monitoring."""
    print("\n=== System Monitoring Example ===")

    # Create system monitor
    monitor = SystemMonitor(secrets_path="secrets.toml")

    # Get current health status
    health = monitor.get_health_status()
    print(f"System health: {health}")

    # Check specific components
    print(f"Is healthy: {health.is_healthy}")
    print(f"Error count: {health.error_count}")
    print(f"Warning count: {health.warning_count}")

    # Get system information
    sys_info = monitor.get_system_info()
    print(
        f"Platform: {sys_info['platform']['system']} {sys_info['platform']['release']}"
    )
    print(f"Python: {sys_info['python']['version']}")

    # Quick health check
    quick_status = monitor.quick_check()
    print(f"Quick check: {quick_status.overall}")

    # Check printer connectivity specifically
    printer_status = monitor.check_printer_connectivity()
    print(f"Printer connectivity: {printer_status['status']}")


def example_advanced_workflow():
    """Advanced workflow example with error handling and monitoring."""
    print("\n=== Advanced Workflow Example ===")

    # Create workflow with printer integration
    workflow = WorkflowManager("Advanced Production Workflow")

    # Add steps with error handling
    workflow.add_validation_step(
        "examples/calibration_test.svg", name="validate_input", required=True
    )

    workflow.add_gcode_generation_step("output/production.gcode", name="generate_gcode")

    # Add printer steps if secrets exist
    secrets_path = Path("secrets.toml")
    if secrets_path.exists():
        try:
            printer = PrinterConnection(str(secrets_path))

            workflow.add_printer_submission_step(
                printer, name="submit_to_printer", auto_start=False, wait_for_ready=True
            )

            # Add monitoring step (optional)
            workflow.add_print_monitoring_step(printer, name="monitor_print")

        except Exception as e:
            print(f"Printer setup failed: {e}")

    # Progress callback
    def progress_callback(step, current, total):
        print(f"Progress: {current}/{total} - {step.name}")

    # Execute with monitoring
    try:
        results = workflow.execute(
            stop_on_failure=False,  # Continue on non-critical failures
            progress_callback=progress_callback,
        )

        print(f"Advanced workflow completed:")
        print(f"  Status: {results['status']}")
        print(f"  Success rate: {results['success_rate']:.1f}%")
        print(f"  Duration: {results['duration']:.2f}s")

        # Check if any critical steps failed
        failed_steps = [s for s in results["step_details"] if s["status"] == "failed"]
        if failed_steps:
            print("Failed steps:")
            for step in failed_steps:
                print(f"  - {step['name']}: {step.get('error', 'Unknown error')}")

    except Exception as e:
        print(f"Advanced workflow failed: {e}")


def example_configuration_management():
    """Example of configuration management."""
    print("\n=== Configuration Management Example ===")

    # Initialize with custom configuration
    welder = MicroWeldr(config_path="config.toml")

    # Get current configuration
    config = welder.get_config()
    print(f"Current bed temperature: {config['temperatures']['bed_temperature']}°C")

    # Update configuration
    welder.update_config(
        {
            "temperatures": {"bed_temperature": 65},  # Increase bed temperature
            "normal_welds": {"weld_time": 0.15},  # Increase weld time
        }
    )

    # Create job with updated configuration
    with welder.create_job("examples/calibration_test.svg") as job:
        # The job will use the updated configuration
        validation = job.validate()
        if validation.is_valid:
            gcode_path = job.generate_gcode("output/custom_config.gcode")
            print(f"G-code generated with custom config: {gcode_path}")


def example_error_handling():
    """Example demonstrating error handling patterns."""
    print("\n=== Error Handling Example ===")

    welder = MicroWeldr()

    # Example 1: Handle missing file
    try:
        with welder.create_job("nonexistent.svg") as job:
            job.validate()
    except FileNotFoundError as e:
        print(f"File not found (handled): {e}")

    # Example 2: Handle validation errors
    try:
        # This would fail if SVG has safety issues
        result = welder.quick_weld(
            "examples/calibration_test.svg", skip_validation=False  # Force validation
        )
        print(f"Quick weld successful: {result}")
    except Exception as e:
        print(f"Quick weld failed (handled): {e}")

    # Example 3: Graceful degradation
    try:
        # Try printer operation with fallback
        printer = PrinterConnection("secrets.toml")
        status = printer.get_status()

        if status.is_fallback:
            print("Printer in fallback mode - manual operation required")
        else:
            print(f"Printer operational: {status.state}")

    except Exception as e:
        print(f"Printer connection failed (handled): {e}")


if __name__ == "__main__":
    """Run all examples."""

    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Create output directory
    Path("output").mkdir(exist_ok=True)
    Path("output/batch").mkdir(exist_ok=True)

    print("MicroWeldr Library Usage Examples")
    print("=" * 50)

    # Run examples
    example_basic_usage()
    example_printer_integration()
    example_workflow_management()
    example_batch_processing()
    example_validation_suite()
    example_system_monitoring()
    example_advanced_workflow()
    example_configuration_management()
    example_error_handling()

    print("\n" + "=" * 50)
    print("All examples completed!")
    print("\nNext steps:")
    print("1. Review the generated files in the 'output' directory")
    print("2. Modify the examples for your specific use case")
    print("3. Check the MicroWeldr API documentation for more details")
