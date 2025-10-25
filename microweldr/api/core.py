"""Core MicroWeldr library API for programmatic access."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..core.config import Config
from ..core.svg_parser import SVGParser
from ..core.gcode_generator import GCodeGenerator
from ..core.safety import validate_weld_operation, SafetyError
from ..core.caching import OptimizedSVGParser, optimize_weld_paths
from ..core.resource_management import safe_gcode_generation, TemporaryFileManager
from ..core.logging_config import setup_logging, LogContext
from ..core.models import WeldPath, WeldPoint
from ..animation.generator import AnimationGenerator
from ..validation.validators import SVGValidator, GCodeValidator, AnimationValidator

logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of validation operations."""

    def __init__(
        self, is_valid: bool, warnings: List[str] = None, errors: List[str] = None
    ):
        """Initialize validation result.

        Args:
            is_valid: Whether validation passed
            warnings: List of warning messages
            errors: List of error messages
        """
        self.is_valid = is_valid
        self.warnings = warnings or []
        self.errors = errors or []

    def __bool__(self) -> bool:
        """Return validation status."""
        return self.is_valid

    def __str__(self) -> str:
        """String representation."""
        status = "PASS" if self.is_valid else "FAIL"
        return f"ValidationResult({status}, {len(self.warnings)} warnings, {len(self.errors)} errors)"


class WeldJob:
    """Represents a welding job with SVG input and generated outputs."""

    def __init__(self, svg_path: Union[str, Path], config: Optional[Config] = None):
        """Initialize weld job.

        Args:
            svg_path: Path to SVG file
            config: Optional configuration (uses default if None)
        """
        self.svg_path = Path(svg_path)
        self.config = config or Config()
        self.weld_paths: Optional[List[WeldPath]] = None
        self.gcode_path: Optional[Path] = None
        self.animation_path: Optional[Path] = None
        self.validation_result: Optional[ValidationResult] = None
        self._temp_manager = TemporaryFileManager(
            prefix=f"weld_job_{self.svg_path.stem}_"
        )

    def validate(self, force: bool = False) -> ValidationResult:
        """Validate the SVG file and weld parameters.

        Args:
            force: Force validation even if already validated

        Returns:
            ValidationResult object
        """
        if self.validation_result and not force:
            return self.validation_result

        with LogContext("validation"):
            try:
                # Validate SVG structure
                svg_validator = SVGValidator()
                svg_result = svg_validator.validate(str(self.svg_path))

                if not svg_result.is_valid:
                    self.validation_result = ValidationResult(
                        False, errors=[f"SVG validation failed: {svg_result.message}"]
                    )
                    return self.validation_result

                # Parse SVG to get weld paths
                if not self.weld_paths:
                    self._parse_svg()

                # Safety validation
                warnings, errors = validate_weld_operation(
                    self.weld_paths, self.config.config
                )

                self.validation_result = ValidationResult(
                    is_valid=len(errors) == 0, warnings=warnings, errors=errors
                )

                logger.info(f"Validation completed: {self.validation_result}")
                return self.validation_result

            except Exception as e:
                logger.error(f"Validation failed: {e}")
                self.validation_result = ValidationResult(
                    False, errors=[f"Validation error: {e}"]
                )
                return self.validation_result

    def _parse_svg(self, use_cache: bool = True) -> None:
        """Parse SVG file to extract weld paths.

        Args:
            use_cache: Whether to use caching for parsing
        """
        with LogContext("svg_parsing"):
            if use_cache:
                parser = OptimizedSVGParser(cache_enabled=True)
                self.weld_paths = parser.parse_svg_file(self.svg_path)
            else:
                parser = SVGParser()
                self.weld_paths = parser.parse_file(self.svg_path)

            # Optimize paths
            self.weld_paths = optimize_weld_paths(self.weld_paths)

            logger.info(
                f"Parsed {len(self.weld_paths)} weld paths from {self.svg_path}"
            )

    def generate_gcode(
        self,
        output_path: Optional[Union[str, Path]] = None,
        skip_bed_leveling: bool = False,
        validate_output: bool = True,
    ) -> Path:
        """Generate G-code for the weld job.

        Args:
            output_path: Output path for G-code (auto-generated if None)
            skip_bed_leveling: Whether to skip bed leveling in G-code
            validate_output: Whether to validate generated G-code

        Returns:
            Path to generated G-code file

        Raises:
            SafetyError: If safety validation fails
            ValueError: If job is not valid
        """
        # Validate first
        validation = self.validate()
        if not validation.is_valid:
            raise SafetyError(f"Job validation failed: {validation.errors}")

        # Parse SVG if not already done
        if not self.weld_paths:
            self._parse_svg()

        # Determine output path
        if output_path is None:
            output_path = self.svg_path.with_suffix(".gcode")
        else:
            output_path = Path(output_path)

        with LogContext("gcode_generation"):
            # Generate G-code with resource management
            with safe_gcode_generation(output_path, backup=True) as temp_gcode_path:
                generator = GCodeGenerator(self.config)
                generator.generate(
                    self.weld_paths,
                    str(temp_gcode_path),
                    skip_bed_leveling=skip_bed_leveling,
                )

            self.gcode_path = output_path

            # Validate generated G-code if requested
            if validate_output:
                validator = GCodeValidator()
                result = validator.validate(str(output_path))
                if not result.is_valid:
                    logger.warning(f"G-code validation warnings: {result.warnings}")

            logger.info(f"G-code generated: {output_path}")
            return output_path

    def generate_animation(
        self,
        output_path: Optional[Union[str, Path]] = None,
        validate_output: bool = True,
    ) -> Path:
        """Generate animation SVG for the weld job.

        Args:
            output_path: Output path for animation (auto-generated if None)
            validate_output: Whether to validate generated animation

        Returns:
            Path to generated animation file
        """
        # Parse SVG if not already done
        if not self.weld_paths:
            self._parse_svg()

        # Determine output path
        if output_path is None:
            output_path = self.svg_path.with_suffix("_animation.svg")
        else:
            output_path = Path(output_path)

        with LogContext("animation_generation"):
            generator = AnimationGenerator(self.config)
            generator.generate(self.weld_paths, str(output_path))

            self.animation_path = output_path

            # Validate generated animation if requested
            if validate_output:
                validator = AnimationValidator()
                result = validator.validate(str(output_path))
                if not result.is_valid:
                    logger.warning(f"Animation validation warnings: {result.warnings}")

            logger.info(f"Animation generated: {output_path}")
            return output_path

    def get_statistics(self) -> Dict[str, Any]:
        """Get job statistics.

        Returns:
            Dictionary with job statistics
        """
        if not self.weld_paths:
            self._parse_svg()

        total_points = sum(len(path.points) for path in self.weld_paths)
        weld_types = {}

        for path in self.weld_paths:
            weld_type = path.weld_type
            weld_types[weld_type] = weld_types.get(weld_type, 0) + len(path.points)

        return {
            "svg_file": str(self.svg_path),
            "total_paths": len(self.weld_paths),
            "total_points": total_points,
            "weld_types": weld_types,
            "gcode_generated": self.gcode_path is not None,
            "animation_generated": self.animation_path is not None,
            "validation_status": str(self.validation_result)
            if self.validation_result
            else "Not validated",
        }

    def cleanup(self) -> None:
        """Clean up temporary resources."""
        self._temp_manager.cleanup_all()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup()


class MicroWeldr:
    """Main MicroWeldr library interface."""

    def __init__(
        self, config_path: Optional[Union[str, Path]] = None, log_level: str = "INFO"
    ):
        """Initialize MicroWeldr library.

        Args:
            config_path: Path to configuration file (uses default if None)
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        # Setup logging
        setup_logging(level=log_level, console=True)

        # Load configuration
        if config_path:
            self.config = Config(str(config_path))
        else:
            self.config = Config()

        logger.info("MicroWeldr library initialized")

    def create_job(self, svg_path: Union[str, Path]) -> WeldJob:
        """Create a new weld job.

        Args:
            svg_path: Path to SVG file

        Returns:
            WeldJob instance
        """
        return WeldJob(svg_path, self.config)

    def validate_svg(self, svg_path: Union[str, Path]) -> ValidationResult:
        """Validate an SVG file for welding compatibility.

        Args:
            svg_path: Path to SVG file

        Returns:
            ValidationResult
        """
        job = self.create_job(svg_path)
        return job.validate()

    def quick_weld(
        self,
        svg_path: Union[str, Path],
        gcode_path: Optional[Union[str, Path]] = None,
        animation_path: Optional[Union[str, Path]] = None,
        skip_validation: bool = False,
    ) -> Dict[str, Path]:
        """Quick welding workflow - parse, validate, and generate outputs.

        Args:
            svg_path: Path to SVG file
            gcode_path: Output path for G-code (auto-generated if None)
            animation_path: Output path for animation (auto-generated if None)
            skip_validation: Skip safety validation (not recommended)

        Returns:
            Dictionary with paths to generated files

        Raises:
            SafetyError: If validation fails and skip_validation is False
        """
        with self.create_job(svg_path) as job:
            # Validate unless skipped
            if not skip_validation:
                validation = job.validate()
                if not validation.is_valid:
                    raise SafetyError(f"Validation failed: {validation.errors}")

            # Generate outputs
            results = {}

            # Generate G-code
            gcode_output = job.generate_gcode(gcode_path)
            results["gcode"] = gcode_output

            # Generate animation if requested
            if animation_path is not None or animation_path != False:
                animation_output = job.generate_animation(animation_path)
                results["animation"] = animation_output

            logger.info(f"Quick weld completed: {results}")
            return results

    def batch_process(
        self,
        svg_files: List[Union[str, Path]],
        output_dir: Optional[Union[str, Path]] = None,
        generate_animations: bool = True,
        continue_on_error: bool = True,
    ) -> Dict[str, Any]:
        """Process multiple SVG files in batch.

        Args:
            svg_files: List of SVG file paths
            output_dir: Output directory (uses SVG directory if None)
            generate_animations: Whether to generate animations
            continue_on_error: Continue processing if one file fails

        Returns:
            Dictionary with batch processing results
        """
        results = {
            "successful": [],
            "failed": [],
            "total_processed": 0,
            "total_points": 0,
        }

        output_dir = Path(output_dir) if output_dir else None

        for svg_file in svg_files:
            svg_path = Path(svg_file)

            try:
                with self.create_job(svg_path) as job:
                    # Validate
                    validation = job.validate()
                    if not validation.is_valid:
                        if continue_on_error:
                            results["failed"].append(
                                {
                                    "file": str(svg_path),
                                    "error": f"Validation failed: {validation.errors}",
                                }
                            )
                            continue
                        else:
                            raise SafetyError(
                                f"Validation failed for {svg_path}: {validation.errors}"
                            )

                    # Determine output paths
                    if output_dir:
                        gcode_path = output_dir / svg_path.with_suffix(".gcode").name
                        animation_path = (
                            output_dir / svg_path.with_suffix("_animation.svg").name
                            if generate_animations
                            else None
                        )
                    else:
                        gcode_path = svg_path.with_suffix(".gcode")
                        animation_path = (
                            svg_path.with_suffix("_animation.svg")
                            if generate_animations
                            else None
                        )

                    # Generate outputs
                    job.generate_gcode(gcode_path)
                    if generate_animations:
                        job.generate_animation(animation_path)

                    # Record success
                    stats = job.get_statistics()
                    results["successful"].append(
                        {
                            "file": str(svg_path),
                            "gcode": str(gcode_path),
                            "animation": str(animation_path)
                            if animation_path
                            else None,
                            "points": stats["total_points"],
                        }
                    )

                    results["total_points"] += stats["total_points"]

            except Exception as e:
                if continue_on_error:
                    results["failed"].append({"file": str(svg_path), "error": str(e)})
                    logger.error(f"Failed to process {svg_path}: {e}")
                else:
                    raise

            results["total_processed"] += 1

        logger.info(
            f"Batch processing completed: {len(results['successful'])} successful, {len(results['failed'])} failed"
        )
        return results

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration.

        Returns:
            Configuration dictionary
        """
        return self.config.config.copy()

    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update configuration parameters.

        Args:
            updates: Dictionary of configuration updates
        """

        # Deep merge updates into config
        def deep_update(base_dict, update_dict):
            for key, value in update_dict.items():
                if (
                    key in base_dict
                    and isinstance(base_dict[key], dict)
                    and isinstance(value, dict)
                ):
                    deep_update(base_dict[key], value)
                else:
                    base_dict[key] = value

        deep_update(self.config.config, updates)
        logger.info(f"Configuration updated: {list(updates.keys())}")

    def get_version(self) -> str:
        """Get MicroWeldr version.

        Returns:
            Version string
        """
        return "4.0.0"
