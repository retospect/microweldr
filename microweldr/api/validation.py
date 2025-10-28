"""Validation API for comprehensive quality assurance."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..core.config import Config
from ..core.logging_config import LogContext
from ..core.safety import SafetyValidator, validate_weld_operation
from ..core.security import SecretsValidator
from ..core.svg_parser import SVGParser
from ..validation.validators import AnimationValidator, GCodeValidator, SVGValidator

logger = logging.getLogger(__name__)


class ValidationReport:
    """Comprehensive validation report."""

    def __init__(self):
        """Initialize validation report."""
        self.checks: Dict[str, Dict[str, Any]] = {}
        self.overall_status = "unknown"
        self.total_errors = 0
        self.total_warnings = 0

    def add_check(
        self,
        name: str,
        is_valid: bool,
        message: str = "",
        warnings: List[str] = None,
        errors: List[str] = None,
    ):
        """Add a validation check result.

        Args:
            name: Check name
            is_valid: Whether check passed
            message: Check message
            warnings: List of warnings
            errors: List of errors
        """
        warnings = warnings or []
        errors = errors or []

        self.checks[name] = {
            "valid": is_valid,
            "message": message,
            "warnings": warnings,
            "errors": errors,
            "warning_count": len(warnings),
            "error_count": len(errors),
        }

        self.total_warnings += len(warnings)
        self.total_errors += len(errors)

        # Update overall status
        if errors:
            if self.overall_status != "failed":
                self.overall_status = "failed"
        elif warnings:
            if self.overall_status not in ["failed", "warning"]:
                self.overall_status = "warning"
        elif self.overall_status == "unknown":
            self.overall_status = "passed"

    @property
    def is_valid(self) -> bool:
        """Check if overall validation passed."""
        return self.overall_status in ["passed", "warning"]

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return self.total_errors > 0

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings."""
        return self.total_warnings > 0

    def get_summary(self) -> Dict[str, Any]:
        """Get validation summary.

        Returns:
            Summary dictionary
        """
        return {
            "overall_status": self.overall_status,
            "is_valid": self.is_valid,
            "total_checks": len(self.checks),
            "passed_checks": sum(1 for c in self.checks.values() if c["valid"]),
            "failed_checks": sum(1 for c in self.checks.values() if not c["valid"]),
            "total_warnings": self.total_warnings,
            "total_errors": self.total_errors,
            "checks": self.checks,
        }

    def get_errors(self) -> List[str]:
        """Get all error messages.

        Returns:
            List of error messages
        """
        errors = []
        for check_name, check_data in self.checks.items():
            for error in check_data["errors"]:
                errors.append(f"{check_name}: {error}")
        return errors

    def get_warnings(self) -> List[str]:
        """Get all warning messages.

        Returns:
            List of warning messages
        """
        warnings = []
        for check_name, check_data in self.checks.items():
            for warning in check_data["warnings"]:
                warnings.append(f"{check_name}: {warning}")
        return warnings

    def __str__(self) -> str:
        """String representation."""
        return f"ValidationReport({self.overall_status}, {len(self.checks)} checks, {self.total_errors} errors, {self.total_warnings} warnings)"


class ValidationSuite:
    """Comprehensive validation suite for all MicroWeldr components."""

    def __init__(self, config: Optional[Config] = None):
        """Initialize validation suite.

        Args:
            config: Optional configuration (uses default if None)
        """
        self.config = config or Config()
        self.safety_validator = SafetyValidator()
        self.secrets_validator = SecretsValidator()

    def validate_svg_file(self, svg_path: Union[str, Path]) -> ValidationReport:
        """Validate SVG file comprehensively.

        Args:
            svg_path: Path to SVG file

        Returns:
            ValidationReport with all checks
        """
        report = ValidationReport()
        svg_path = Path(svg_path)

        with LogContext("svg_validation"):
            # File existence check
            if not svg_path.exists():
                report.add_check(
                    "file_exists",
                    False,
                    f"SVG file not found: {svg_path}",
                    errors=[f"File does not exist: {svg_path}"],
                )
                return report

            report.add_check("file_exists", True, f"SVG file found: {svg_path}")

            # SVG structure validation
            try:
                svg_validator = SVGValidator()
                svg_result = svg_validator.validate(str(svg_path))

                report.add_check(
                    "svg_structure",
                    svg_result.is_valid,
                    svg_result.message,
                    warnings=(
                        svg_result.warnings if hasattr(svg_result, "warnings") else []
                    ),
                    errors=[svg_result.message] if not svg_result.is_valid else [],
                )

            except Exception as e:
                report.add_check(
                    "svg_structure",
                    False,
                    f"SVG validation failed: {e}",
                    errors=[str(e)],
                )
                return report

            # Parse SVG and validate weld paths
            try:
                parser = SVGParser()
                weld_paths = parser.parse_file(svg_path)

                if not weld_paths:
                    report.add_check(
                        "weld_paths",
                        False,
                        "No weld paths found in SVG",
                        errors=["No weld paths extracted from SVG"],
                    )
                else:
                    total_points = sum(len(path.points) for path in weld_paths)
                    report.add_check(
                        "weld_paths",
                        True,
                        f"Found {len(weld_paths)} paths with {total_points} points",
                    )

                    # Safety validation
                    warnings, errors = validate_weld_operation(
                        weld_paths, self.config.config
                    )
                    report.add_check(
                        "safety_validation",
                        len(errors) == 0,
                        f"Safety check: {len(errors)} errors, {len(warnings)} warnings",
                        warnings=warnings,
                        errors=errors,
                    )

            except Exception as e:
                report.add_check(
                    "weld_paths",
                    False,
                    f"Failed to parse weld paths: {e}",
                    errors=[str(e)],
                )

        logger.info(f"SVG validation completed: {report}")
        return report

    def validate_gcode_file(self, gcode_path: Union[str, Path]) -> ValidationReport:
        """Validate G-code file.

        Args:
            gcode_path: Path to G-code file

        Returns:
            ValidationReport with G-code checks
        """
        report = ValidationReport()
        gcode_path = Path(gcode_path)

        with LogContext("gcode_validation"):
            # File existence check
            if not gcode_path.exists():
                report.add_check(
                    "file_exists",
                    False,
                    f"G-code file not found: {gcode_path}",
                    errors=[f"File does not exist: {gcode_path}"],
                )
                return report

            report.add_check("file_exists", True, f"G-code file found: {gcode_path}")

            # File size check
            file_size = gcode_path.stat().st_size
            if file_size == 0:
                report.add_check(
                    "file_size",
                    False,
                    "G-code file is empty",
                    errors=["G-code file has zero size"],
                )
            elif file_size > 100 * 1024 * 1024:  # 100MB
                report.add_check(
                    "file_size",
                    True,
                    f"G-code file is very large: {file_size / 1024 / 1024:.1f}MB",
                    warnings=[f"Large G-code file: {file_size / 1024 / 1024:.1f}MB"],
                )
            else:
                report.add_check(
                    "file_size", True, f"G-code file size: {file_size / 1024:.1f}KB"
                )

            # G-code structure validation
            try:
                gcode_validator = GCodeValidator()
                gcode_result = gcode_validator.validate(str(gcode_path))

                report.add_check(
                    "gcode_structure",
                    gcode_result.is_valid,
                    gcode_result.message,
                    warnings=(
                        gcode_result.warnings
                        if hasattr(gcode_result, "warnings")
                        else []
                    ),
                    errors=[gcode_result.message] if not gcode_result.is_valid else [],
                )

            except Exception as e:
                report.add_check(
                    "gcode_structure",
                    False,
                    f"G-code validation failed: {e}",
                    errors=[str(e)],
                )

        logger.info(f"G-code validation completed: {report}")
        return report

    def validate_animation_file(
        self, animation_path: Union[str, Path]
    ) -> ValidationReport:
        """Validate animation SVG file.

        Args:
            animation_path: Path to animation SVG file

        Returns:
            ValidationReport with animation checks
        """
        report = ValidationReport()
        animation_path = Path(animation_path)

        with LogContext("animation_validation"):
            # File existence check
            if not animation_path.exists():
                report.add_check(
                    "file_exists",
                    False,
                    f"Animation file not found: {animation_path}",
                    errors=[f"File does not exist: {animation_path}"],
                )
                return report

            report.add_check(
                "file_exists", True, f"Animation file found: {animation_path}"
            )

            # Animation structure validation
            try:
                animation_validator = AnimationValidator()
                animation_result = animation_validator.validate(str(animation_path))

                report.add_check(
                    "animation_structure",
                    animation_result.is_valid,
                    animation_result.message,
                    warnings=(
                        animation_result.warnings
                        if hasattr(animation_result, "warnings")
                        else []
                    ),
                    errors=(
                        [animation_result.message]
                        if not animation_result.is_valid
                        else []
                    ),
                )

            except Exception as e:
                report.add_check(
                    "animation_structure",
                    False,
                    f"Animation validation failed: {e}",
                    errors=[str(e)],
                )

        logger.info(f"Animation validation completed: {report}")
        return report

    def validate_secrets_file(self, secrets_path: Union[str, Path]) -> ValidationReport:
        """Validate secrets configuration file.

        Args:
            secrets_path: Path to secrets file

        Returns:
            ValidationReport with security checks
        """
        report = ValidationReport()
        secrets_path = Path(secrets_path)

        with LogContext("secrets_validation"):
            # File existence check
            if not secrets_path.exists():
                report.add_check(
                    "file_exists",
                    False,
                    f"Secrets file not found: {secrets_path}",
                    errors=[f"File does not exist: {secrets_path}"],
                )
                return report

            report.add_check("file_exists", True, f"Secrets file found: {secrets_path}")

            # Security validation
            try:
                warnings, errors = self.secrets_validator.validate_secrets_file(
                    str(secrets_path)
                )

                report.add_check(
                    "security_validation",
                    len(errors) == 0,
                    f"Security check: {len(errors)} errors, {len(warnings)} warnings",
                    warnings=warnings,
                    errors=errors,
                )

            except Exception as e:
                report.add_check(
                    "security_validation",
                    False,
                    f"Security validation failed: {e}",
                    errors=[str(e)],
                )

        logger.info(f"Secrets validation completed: {report}")
        return report

    def validate_configuration(
        self, config_path: Optional[Union[str, Path]] = None
    ) -> ValidationReport:
        """Validate configuration file.

        Args:
            config_path: Path to configuration file (uses current config if None)

        Returns:
            ValidationReport with configuration checks
        """
        report = ValidationReport()

        with LogContext("config_validation"):
            try:
                # Use provided config or current config
                if config_path:
                    config_path = Path(config_path)
                    if not config_path.exists():
                        report.add_check(
                            "file_exists",
                            False,
                            f"Configuration file not found: {config_path}",
                            errors=[f"File does not exist: {config_path}"],
                        )
                        return report

                    # Load and validate config
                    test_config = Config(str(config_path))
                    config_data = test_config.config
                else:
                    config_data = self.config.config

                # Safety validation of configuration
                warnings, errors = self.safety_validator.validate_config(config_data)

                report.add_check(
                    "config_safety",
                    len(errors) == 0,
                    f"Configuration safety: {len(errors)} errors, {len(warnings)} warnings",
                    warnings=warnings,
                    errors=errors,
                )

                # Structure validation
                required_sections = [
                    "printer",
                    "temperatures",
                    "normal_welds",
                    "movement",
                ]
                missing_sections = [
                    s for s in required_sections if s not in config_data
                ]

                if missing_sections:
                    report.add_check(
                        "config_structure",
                        False,
                        f"Missing required sections: {missing_sections}",
                        errors=[
                            f"Missing configuration sections: {', '.join(missing_sections)}"
                        ],
                    )
                else:
                    report.add_check(
                        "config_structure",
                        True,
                        "All required configuration sections present",
                    )

            except Exception as e:
                report.add_check(
                    "config_validation",
                    False,
                    f"Configuration validation failed: {e}",
                    errors=[str(e)],
                )

        logger.info(f"Configuration validation completed: {report}")
        return report

    def validate_complete_workflow(
        self,
        svg_path: Union[str, Path],
        gcode_path: Optional[Union[str, Path]] = None,
        animation_path: Optional[Union[str, Path]] = None,
        secrets_path: Optional[Union[str, Path]] = None,
    ) -> ValidationReport:
        """Validate complete welding workflow.

        Args:
            svg_path: Path to SVG file
            gcode_path: Optional path to G-code file
            animation_path: Optional path to animation file
            secrets_path: Optional path to secrets file

        Returns:
            Comprehensive ValidationReport
        """
        report = ValidationReport()

        with LogContext("workflow_validation"):
            logger.info("Starting complete workflow validation")

            # Validate SVG
            svg_report = self.validate_svg_file(svg_path)
            for check_name, check_data in svg_report.checks.items():
                report.add_check(
                    f"svg_{check_name}",
                    check_data["valid"],
                    check_data["message"],
                    check_data["warnings"],
                    check_data["errors"],
                )

            # Validate G-code if provided
            if gcode_path:
                gcode_report = self.validate_gcode_file(gcode_path)
                for check_name, check_data in gcode_report.checks.items():
                    report.add_check(
                        f"gcode_{check_name}",
                        check_data["valid"],
                        check_data["message"],
                        check_data["warnings"],
                        check_data["errors"],
                    )

            # Validate animation if provided
            if animation_path:
                animation_report = self.validate_animation_file(animation_path)
                for check_name, check_data in animation_report.checks.items():
                    report.add_check(
                        f"animation_{check_name}",
                        check_data["valid"],
                        check_data["message"],
                        check_data["warnings"],
                        check_data["errors"],
                    )

            # Validate secrets if provided
            if secrets_path:
                secrets_report = self.validate_secrets_file(secrets_path)
                for check_name, check_data in secrets_report.checks.items():
                    report.add_check(
                        f"secrets_{check_name}",
                        check_data["valid"],
                        check_data["message"],
                        check_data["warnings"],
                        check_data["errors"],
                    )

            # Validate configuration
            config_report = self.validate_configuration()
            for check_name, check_data in config_report.checks.items():
                report.add_check(
                    f"config_{check_name}",
                    check_data["valid"],
                    check_data["message"],
                    check_data["warnings"],
                    check_data["errors"],
                )

        logger.info(f"Complete workflow validation finished: {report}")
        return report

    def quick_validate(self, svg_path: Union[str, Path]) -> bool:
        """Quick validation check for SVG file.

        Args:
            svg_path: Path to SVG file

        Returns:
            True if basic validation passes, False otherwise
        """
        try:
            svg_path = Path(svg_path)

            # Basic checks
            if not svg_path.exists():
                return False

            # Try to parse
            parser = SVGParser()
            weld_paths = parser.parse_file(svg_path)

            if not weld_paths:
                return False

            # Basic safety check
            warnings, errors = validate_weld_operation(weld_paths, self.config.config)

            return len(errors) == 0

        except Exception:
            return False
