"""Workflow management API for complex welding operations."""

import logging
import time
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from ..core.logging_config import LogContext
from ..core.progress import progress_context
from .core import MicroWeldr, ValidationResult, WeldJob
from .printer import PrinterConnection, PrinterStatus

logger = logging.getLogger(__name__)


class WorkflowStepStatus(Enum):
    """Status of workflow steps."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStep:
    """Represents a single step in a welding workflow."""

    def __init__(
        self,
        name: str,
        action: Callable,
        description: str = "",
        required: bool = True,
        retry_count: int = 0,
        timeout: Optional[int] = None,
    ):
        """Initialize workflow step.

        Args:
            name: Step name
            action: Callable to execute for this step
            description: Human-readable description
            required: Whether step is required for workflow success
            retry_count: Number of retries on failure
            timeout: Step timeout in seconds
        """
        self.name = name
        self.action = action
        self.description = description
        self.required = required
        self.retry_count = retry_count
        self.timeout = timeout

        self.status = WorkflowStepStatus.PENDING
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.result: Any = None
        self.error: Optional[Exception] = None
        self.attempts = 0

    @property
    def duration(self) -> Optional[float]:
        """Get step duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None

    @property
    def is_complete(self) -> bool:
        """Check if step is complete (success or failure)."""
        return self.status in [
            WorkflowStepStatus.COMPLETED,
            WorkflowStepStatus.FAILED,
            WorkflowStepStatus.SKIPPED,
        ]

    def execute(self, context: Dict[str, Any]) -> Any:
        """Execute the step.

        Args:
            context: Workflow context dictionary

        Returns:
            Step result

        Raises:
            Exception: If step fails and retries are exhausted
        """
        self.status = WorkflowStepStatus.RUNNING
        self.start_time = time.time()

        for attempt in range(self.retry_count + 1):
            self.attempts = attempt + 1

            try:
                logger.info(f"Executing step '{self.name}' (attempt {self.attempts})")

                # Execute with timeout if specified
                if self.timeout:
                    import signal

                    def timeout_handler(signum, frame):
                        raise TimeoutError(
                            f"Step '{self.name}' timed out after {self.timeout}s"
                        )

                    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(self.timeout)

                    try:
                        self.result = self.action(context)
                    finally:
                        signal.alarm(0)
                        signal.signal(signal.SIGALRM, old_handler)
                else:
                    self.result = self.action(context)

                # Step succeeded
                self.status = WorkflowStepStatus.COMPLETED
                self.end_time = time.time()

                logger.info(
                    f"Step '{self.name}' completed successfully in {self.duration:.2f}s"
                )
                return self.result

            except Exception as e:
                self.error = e
                logger.warning(
                    f"Step '{self.name}' failed (attempt {self.attempts}): {e}"
                )

                if attempt < self.retry_count:
                    # Wait before retry
                    retry_delay = min(2**attempt, 30)  # Exponential backoff, max 30s
                    logger.info(f"Retrying step '{self.name}' in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    # All retries exhausted
                    self.status = WorkflowStepStatus.FAILED
                    self.end_time = time.time()

                    if self.required:
                        logger.error(
                            f"Required step '{self.name}' failed after {self.attempts} attempts"
                        )
                        raise
                    else:
                        logger.warning(
                            f"Optional step '{self.name}' failed, continuing workflow"
                        )
                        return None

    def skip(self, reason: str = ""):
        """Skip this step.

        Args:
            reason: Reason for skipping
        """
        self.status = WorkflowStepStatus.SKIPPED
        self.end_time = time.time()
        logger.info(f"Step '{self.name}' skipped: {reason}")

    def to_dict(self) -> Dict[str, Any]:
        """Convert step to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "required": self.required,
            "attempts": self.attempts,
            "duration": self.duration,
            "error": str(self.error) if self.error else None,
            "result_type": (
                type(self.result).__name__ if self.result is not None else None
            ),
        }


class WorkflowManager:
    """Manages complex welding workflows with multiple steps."""

    def __init__(self, name: str, welder: Optional[MicroWeldr] = None):
        """Initialize workflow manager.

        Args:
            name: Workflow name
            welder: MicroWeldr instance (creates default if None)
        """
        self.name = name
        self.welder = welder or MicroWeldr()
        self.steps: List[WorkflowStep] = []
        self.context: Dict[str, Any] = {}

        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.status = WorkflowStepStatus.PENDING

        logger.info(f"Workflow '{self.name}' initialized")

    def add_step(self, step: WorkflowStep) -> "WorkflowManager":
        """Add a step to the workflow.

        Args:
            step: WorkflowStep to add

        Returns:
            Self for method chaining
        """
        self.steps.append(step)
        logger.debug(f"Added step '{step.name}' to workflow '{self.name}'")
        return self

    def add_validation_step(
        self,
        svg_path: Union[str, Path],
        name: str = "validate_svg",
        required: bool = True,
    ) -> "WorkflowManager":
        """Add SVG validation step.

        Args:
            svg_path: Path to SVG file
            name: Step name
            required: Whether validation is required

        Returns:
            Self for method chaining
        """

        def validate_action(context):
            job = self.welder.create_job(svg_path)
            result = job.validate()
            context["validation_result"] = result
            context["weld_job"] = job

            if not result.is_valid:
                raise ValueError(f"SVG validation failed: {result.errors}")

            return result

        step = WorkflowStep(
            name=name,
            action=validate_action,
            description=f"Validate SVG file: {Path(svg_path).name}",
            required=required,
        )

        return self.add_step(step)

    def add_gcode_generation_step(
        self,
        output_path: Optional[Union[str, Path]] = None,
        name: str = "generate_gcode",
        skip_bed_leveling: bool = False,
    ) -> "WorkflowManager":
        """Add G-code generation step.

        Args:
            output_path: Output path for G-code
            name: Step name
            skip_bed_leveling: Whether to skip bed leveling

        Returns:
            Self for method chaining
        """

        def gcode_action(context):
            job = context.get("weld_job")
            if not job:
                raise ValueError("No weld job found in context")

            gcode_path = job.generate_gcode(
                output_path, skip_bed_leveling=skip_bed_leveling
            )
            context["gcode_path"] = gcode_path

            return gcode_path

        step = WorkflowStep(
            name=name,
            action=gcode_action,
            description="Generate G-code from SVG",
            required=True,
        )

        return self.add_step(step)

    def add_animation_generation_step(
        self,
        output_path: Optional[Union[str, Path]] = None,
        name: str = "generate_animation",
        required: bool = False,
    ) -> "WorkflowManager":
        """Add animation generation step.

        Args:
            output_path: Output path for animation
            name: Step name
            required: Whether animation generation is required

        Returns:
            Self for method chaining
        """

        def animation_action(context):
            job = context.get("weld_job")
            if not job:
                raise ValueError("No weld job found in context")

            animation_path = job.generate_animation(output_path)
            context["animation_path"] = animation_path

            return animation_path

        step = WorkflowStep(
            name=name,
            action=animation_action,
            description="Generate animation SVG",
            required=required,
        )

        return self.add_step(step)

    def add_printer_submission_step(
        self,
        printer_connection: PrinterConnection,
        name: str = "submit_to_printer",
        auto_start: bool = False,
        wait_for_ready: bool = True,
    ) -> "WorkflowManager":
        """Add printer submission step.

        Args:
            printer_connection: PrinterConnection instance
            name: Step name
            auto_start: Whether to start print automatically
            wait_for_ready: Whether to wait for printer readiness

        Returns:
            Self for method chaining
        """

        def submission_action(context):
            gcode_path = context.get("gcode_path")
            if not gcode_path:
                raise ValueError("No G-code path found in context")

            result = printer_connection.submit_job(
                gcode_path, auto_start=auto_start, wait_for_ready=wait_for_ready
            )

            context["submission_result"] = result
            return result

        step = WorkflowStep(
            name=name,
            action=submission_action,
            description="Submit G-code to printer",
            required=True,
            retry_count=2,
            timeout=300,  # 5 minute timeout
        )

        return self.add_step(step)

    def add_print_monitoring_step(
        self,
        printer_connection: PrinterConnection,
        name: str = "monitor_print",
        check_interval: int = 30,
    ) -> "WorkflowManager":
        """Add print monitoring step.

        Args:
            printer_connection: PrinterConnection instance
            name: Step name
            check_interval: Status check interval in seconds

        Returns:
            Self for method chaining
        """

        def monitoring_action(context):
            def status_callback(status: PrinterStatus):
                logger.info(
                    f"Print status: {status.state} ({status.job_progress:.1f}%)"
                )

            result = printer_connection.monitor_print(
                callback=status_callback, check_interval=check_interval
            )

            context["print_result"] = result
            return result

        step = WorkflowStep(
            name=name,
            action=monitoring_action,
            description="Monitor print progress",
            required=False,  # Optional since it's long-running
            timeout=None,  # No timeout for monitoring
        )

        return self.add_step(step)

    def add_custom_step(
        self,
        name: str,
        action: Callable[[Dict[str, Any]], Any],
        description: str = "",
        required: bool = True,
        retry_count: int = 0,
        timeout: Optional[int] = None,
    ) -> "WorkflowManager":
        """Add a custom step.

        Args:
            name: Step name
            action: Action function that takes context dict
            description: Step description
            required: Whether step is required
            retry_count: Number of retries on failure
            timeout: Step timeout in seconds

        Returns:
            Self for method chaining
        """
        step = WorkflowStep(
            name=name,
            action=action,
            description=description,
            required=required,
            retry_count=retry_count,
            timeout=timeout,
        )

        return self.add_step(step)

    def execute(
        self, stop_on_failure: bool = True, progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Execute the workflow.

        Args:
            stop_on_failure: Whether to stop on first failure
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary with workflow results
        """
        self.status = WorkflowStepStatus.RUNNING
        self.start_time = time.time()

        logger.info(f"Starting workflow '{self.name}' with {len(self.steps)} steps")

        try:
            with progress_context(
                len(self.steps), f"Executing {self.name}"
            ) as progress:
                for i, step in enumerate(self.steps):
                    if progress_callback:
                        progress_callback(step, i, len(self.steps))

                    try:
                        step.execute(self.context)
                        progress.update(1, f"Completed: {step.name}")

                    except Exception as e:
                        logger.error(f"Step '{step.name}' failed: {e}")

                        if stop_on_failure and step.required:
                            self.status = WorkflowStepStatus.FAILED
                            self.end_time = time.time()
                            raise
                        else:
                            progress.update(1, f"Failed: {step.name}")

            # Workflow completed
            self.status = WorkflowStepStatus.COMPLETED
            self.end_time = time.time()

            # Generate results
            results = self.get_results()
            logger.info(
                f"Workflow '{self.name}' completed successfully in {results['duration']:.2f}s"
            )

            return results

        except Exception as e:
            self.status = WorkflowStepStatus.FAILED
            self.end_time = time.time()

            logger.error(f"Workflow '{self.name}' failed: {e}")
            raise

    def get_results(self) -> Dict[str, Any]:
        """Get workflow execution results.

        Returns:
            Dictionary with workflow results and statistics
        """
        completed_steps = [
            s for s in self.steps if s.status == WorkflowStepStatus.COMPLETED
        ]
        failed_steps = [s for s in self.steps if s.status == WorkflowStepStatus.FAILED]
        skipped_steps = [
            s for s in self.steps if s.status == WorkflowStepStatus.SKIPPED
        ]

        total_duration = 0.0
        if self.start_time and self.end_time:
            total_duration = self.end_time - self.start_time

        return {
            "workflow_name": self.name,
            "status": self.status.value,
            "duration": total_duration,
            "total_steps": len(self.steps),
            "completed_steps": len(completed_steps),
            "failed_steps": len(failed_steps),
            "skipped_steps": len(skipped_steps),
            "success_rate": (
                len(completed_steps) / len(self.steps) * 100 if self.steps else 0
            ),
            "context": self.context.copy(),
            "step_details": [step.to_dict() for step in self.steps],
        }

    def get_step(self, name: str) -> Optional[WorkflowStep]:
        """Get a step by name.

        Args:
            name: Step name

        Returns:
            WorkflowStep or None if not found
        """
        for step in self.steps:
            if step.name == name:
                return step
        return None

    def reset(self) -> None:
        """Reset workflow to initial state."""
        for step in self.steps:
            step.status = WorkflowStepStatus.PENDING
            step.start_time = None
            step.end_time = None
            step.result = None
            step.error = None
            step.attempts = 0

        self.context.clear()
        self.status = WorkflowStepStatus.PENDING
        self.start_time = None
        self.end_time = None

        logger.info(f"Workflow '{self.name}' reset")


def create_standard_workflow(
    svg_path: Union[str, Path],
    gcode_path: Optional[Union[str, Path]] = None,
    animation_path: Optional[Union[str, Path]] = None,
    printer_connection: Optional[PrinterConnection] = None,
    auto_start_print: bool = False,
    monitor_print: bool = False,
) -> WorkflowManager:
    """Create a standard welding workflow.

    Args:
        svg_path: Path to SVG file
        gcode_path: Output path for G-code (auto-generated if None)
        animation_path: Output path for animation (auto-generated if None)
        printer_connection: Optional printer connection for submission
        auto_start_print: Whether to start print automatically
        monitor_print: Whether to monitor print progress

    Returns:
        Configured WorkflowManager
    """
    workflow = WorkflowManager("Standard Welding Workflow")

    # Add standard steps
    workflow.add_validation_step(svg_path)
    workflow.add_gcode_generation_step(gcode_path)

    if animation_path is not False:  # Generate animation unless explicitly disabled
        workflow.add_animation_generation_step(animation_path, required=False)

    # Add printer steps if connection provided
    if printer_connection:
        workflow.add_printer_submission_step(
            printer_connection, auto_start=auto_start_print, wait_for_ready=True
        )

        if monitor_print:
            workflow.add_print_monitoring_step(printer_connection)

    return workflow


def create_batch_workflow(
    svg_files: List[Union[str, Path]],
    output_dir: Optional[Union[str, Path]] = None,
    printer_connection: Optional[PrinterConnection] = None,
    auto_start_print: bool = False,
) -> WorkflowManager:
    """Create a batch processing workflow.

    Args:
        svg_files: List of SVG file paths
        output_dir: Output directory (uses SVG directories if None)
        printer_connection: Optional printer connection
        auto_start_print: Whether to start prints automatically

    Returns:
        Configured WorkflowManager for batch processing
    """
    workflow = WorkflowManager("Batch Processing Workflow")

    output_dir = Path(output_dir) if output_dir else None

    for i, svg_file in enumerate(svg_files):
        svg_path = Path(svg_file)

        # Determine output paths
        if output_dir:
            gcode_path = output_dir / svg_path.with_suffix(".gcode").name
            animation_path = output_dir / svg_path.with_suffix("_animation.svg").name
        else:
            gcode_path = svg_path.with_suffix(".gcode")
            animation_path = svg_path.with_suffix("_animation.svg")

        # Add steps for this file
        workflow.add_validation_step(svg_path, name=f"validate_{i}", required=False)
        workflow.add_gcode_generation_step(gcode_path, name=f"gcode_{i}")
        workflow.add_animation_generation_step(
            animation_path, name=f"animation_{i}", required=False
        )

        # Add printer submission if connection provided
        if printer_connection:
            workflow.add_printer_submission_step(
                printer_connection, name=f"submit_{i}", auto_start=auto_start_print
            )

    return workflow
