"""Safety validation and checks for welding operations."""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..core.models import WeldPath, WeldPoint

logger = logging.getLogger(__name__)


class SafetyError(Exception):
    """Raised when safety validation fails."""

    pass


class SafetyValidator:
    """Validates welding parameters for safety compliance."""

    # Safety limits for plastic welding
    MAX_TEMPERATURE = 120.0  # °C - Safe limit for most plastics
    MIN_TEMPERATURE = 50.0  # °C - Minimum effective welding temperature
    MAX_WELD_HEIGHT = 0.5  # mm - Maximum safe compression depth
    MIN_WELD_HEIGHT = 0.001  # mm - Minimum effective compression
    MAX_WELD_TIME = 5.0  # seconds - Maximum safe heating time
    MIN_WELD_TIME = 0.05  # seconds - Minimum effective weld time
    MAX_TRAVEL_SPEED = 3000  # mm/min - Maximum safe travel speed
    MAX_Z_SPEED = 1000  # mm/min - Maximum safe Z-axis speed
    MAX_BED_TEMP = 80.0  # °C - Maximum safe bed temperature

    def __init__(self):
        """Initialize safety validator."""
        self.warnings: List[str] = []
        self.errors: List[str] = []

    def validate_temperature(
        self, temp: float, param_name: str = "temperature"
    ) -> None:
        """Validate temperature is within safe limits.

        Args:
            temp: Temperature in Celsius
            param_name: Name of the parameter for error messages

        Raises:
            SafetyError: If temperature is outside safe limits
        """
        if not isinstance(temp, (int, float)):
            raise SafetyError(f"{param_name} must be a number, got {type(temp)}")

        if temp > self.MAX_TEMPERATURE:
            raise SafetyError(
                f"{param_name} {temp}°C exceeds maximum safe limit of {self.MAX_TEMPERATURE}°C"
            )

        if temp < self.MIN_TEMPERATURE:
            self.warnings.append(
                f"{param_name} {temp}°C is below recommended minimum of {self.MIN_TEMPERATURE}°C"
            )

        logger.debug(f"Temperature validation passed: {param_name}={temp}°C")

    def validate_weld_height(
        self, height: float, param_name: str = "weld_height"
    ) -> None:
        """Validate weld height is within safe limits.

        Args:
            height: Weld height in mm
            param_name: Name of the parameter for error messages

        Raises:
            SafetyError: If height is outside safe limits
        """
        if not isinstance(height, (int, float)):
            raise SafetyError(f"{param_name} must be a number, got {type(height)}")

        if height > self.MAX_WELD_HEIGHT:
            raise SafetyError(
                f"{param_name} {height}mm exceeds maximum safe limit of {self.MAX_WELD_HEIGHT}mm"
            )

        if height < self.MIN_WELD_HEIGHT:
            self.warnings.append(
                f"{param_name} {height}mm is below recommended minimum of {self.MIN_WELD_HEIGHT}mm"
            )

        logger.debug(f"Weld height validation passed: {param_name}={height}mm")

    def validate_weld_time(self, time: float, param_name: str = "weld_time") -> None:
        """Validate weld time is within safe limits.

        Args:
            time: Weld time in seconds
            param_name: Name of the parameter for error messages

        Raises:
            SafetyError: If time is outside safe limits
        """
        if not isinstance(time, (int, float)):
            raise SafetyError(f"{param_name} must be a number, got {type(time)}")

        if time > self.MAX_WELD_TIME:
            raise SafetyError(
                f"{param_name} {time}s exceeds maximum safe limit of {self.MAX_WELD_TIME}s"
            )

        if time < self.MIN_WELD_TIME:
            self.warnings.append(
                f"{param_name} {time}s is below recommended minimum of {self.MIN_WELD_TIME}s"
            )

        logger.debug(f"Weld time validation passed: {param_name}={time}s")

    def validate_speed(self, speed: float, param_name: str, max_speed: float) -> None:
        """Validate movement speed is within safe limits.

        Args:
            speed: Speed in mm/min
            param_name: Name of the parameter for error messages
            max_speed: Maximum allowed speed for this parameter

        Raises:
            SafetyError: If speed exceeds safe limits
        """
        if not isinstance(speed, (int, float)):
            raise SafetyError(f"{param_name} must be a number, got {type(speed)}")

        if speed <= 0:
            raise SafetyError(f"{param_name} must be positive, got {speed}")

        if speed > max_speed:
            raise SafetyError(
                f"{param_name} {speed}mm/min exceeds maximum safe limit of {max_speed}mm/min"
            )

        logger.debug(f"Speed validation passed: {param_name}={speed}mm/min")

    def validate_weld_point(self, point: WeldPoint) -> None:
        """Validate a single weld point for safety.

        Args:
            point: WeldPoint to validate

        Raises:
            SafetyError: If point parameters are unsafe
        """
        # Validate custom temperature if specified
        if point.custom_temp is not None:
            self.validate_temperature(point.custom_temp, "custom_temp")

        # Validate custom weld time if specified
        if point.custom_weld_time is not None:
            self.validate_weld_time(point.custom_weld_time, "custom_weld_time")

        # Validate custom weld height if specified
        if point.custom_weld_height is not None:
            self.validate_weld_height(point.custom_weld_height, "custom_weld_height")

        # Validate custom bed temperature if specified
        if point.custom_bed_temp is not None:
            if point.custom_bed_temp > self.MAX_BED_TEMP:
                raise SafetyError(
                    f"custom_bed_temp {point.custom_bed_temp}°C exceeds maximum safe limit of {self.MAX_BED_TEMP}°C"
                )

        logger.debug(f"Weld point validation passed: {point}")

    def validate_weld_path(self, path: WeldPath) -> None:
        """Validate a weld path for safety.

        Args:
            path: WeldPath to validate

        Raises:
            SafetyError: If path parameters are unsafe
        """
        # Validate path-level custom parameters
        if path.custom_temp is not None:
            self.validate_temperature(path.custom_temp, "path custom_temp")

        if path.custom_weld_time is not None:
            self.validate_weld_time(path.custom_weld_time, "path custom_weld_time")

        if path.custom_weld_height is not None:
            self.validate_weld_height(
                path.custom_weld_height, "path custom_weld_height"
            )

        # Validate all points in the path
        for i, point in enumerate(path.points):
            try:
                self.validate_weld_point(point)
            except SafetyError as e:
                raise SafetyError(f"Path '{path.name}' point {i}: {e}")

        logger.debug(
            f"Weld path validation passed: {path.name} ({len(path.points)} points)"
        )

    def validate_config(self, config: Dict) -> Tuple[List[str], List[str]]:
        """Validate configuration parameters for safety.

        Args:
            config: Configuration dictionary

        Returns:
            Tuple of (warnings, errors)
        """
        self.warnings.clear()
        self.errors.clear()

        try:
            # Validate temperature settings
            temps = config.get("temperatures", {})
            if "bed_temperature" in temps:
                if temps["bed_temperature"] > self.MAX_BED_TEMP:
                    self.errors.append(
                        f"bed_temperature {temps['bed_temperature']}°C exceeds safe limit of {self.MAX_BED_TEMP}°C"
                    )

            if "nozzle_temperature" in temps:
                self.validate_temperature(
                    temps["nozzle_temperature"], "nozzle_temperature"
                )

            # Validate weld type configurations
            for weld_type in ["normal_welds", "frangible_welds"]:
                if weld_type in config:
                    weld_config = config[weld_type]

                    if "weld_temperature" in weld_config:
                        self.validate_temperature(
                            weld_config["weld_temperature"],
                            f"{weld_type}.weld_temperature",
                        )

                    if "weld_height" in weld_config:
                        self.validate_weld_height(
                            weld_config["weld_height"], f"{weld_type}.weld_height"
                        )

                    if "weld_time" in weld_config:
                        self.validate_weld_time(
                            weld_config["weld_time"], f"{weld_type}.weld_time"
                        )

            # Validate movement settings
            movement = config.get("movement", {})
            if "travel_speed" in movement:
                self.validate_speed(
                    movement["travel_speed"], "travel_speed", self.MAX_TRAVEL_SPEED
                )

            if "z_speed" in movement:
                self.validate_speed(movement["z_speed"], "z_speed", self.MAX_Z_SPEED)

        except SafetyError as e:
            self.errors.append(str(e))

        return self.warnings.copy(), self.errors.copy()

    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal and invalid characters.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename safe for filesystem use
        """
        if not filename:
            raise SafetyError("Filename cannot be empty")

        # Remove or replace dangerous characters
        safe_chars = re.sub(r"[^\w\-_\.]", "_", filename)

        # Prevent directory traversal
        safe_name = Path(safe_chars).name

        # Ensure reasonable length
        if len(safe_name) > 255:
            name_part = safe_name[:240]
            ext_part = safe_name[-10:] if "." in safe_name[-15:] else ""
            safe_name = name_part + ext_part

        # Prevent hidden files and reserved names
        if safe_name.startswith("."):
            safe_name = "file_" + safe_name[1:]

        reserved_names = (
            ["CON", "PRN", "AUX", "NUL"]
            + [f"COM{i}" for i in range(1, 10)]
            + [f"LPT{i}" for i in range(1, 10)]
        )
        if safe_name.upper().split(".")[0] in reserved_names:
            safe_name = "file_" + safe_name

        if not safe_name:
            safe_name = "unnamed_file"

        logger.debug(f"Filename sanitized: '{filename}' -> '{safe_name}'")
        return safe_name

    def validate_file_path(self, file_path: str, must_exist: bool = True) -> Path:
        """Validate and sanitize file path.

        Args:
            file_path: File path to validate
            must_exist: Whether the file must exist

        Returns:
            Validated Path object

        Raises:
            SafetyError: If path is invalid or unsafe
        """
        if not file_path:
            raise SafetyError("File path cannot be empty")

        try:
            path = Path(file_path).resolve()
        except (OSError, ValueError) as e:
            raise SafetyError(f"Invalid file path '{file_path}': {e}")

        # Check if file exists when required
        if must_exist and not path.exists():
            raise SafetyError(f"File does not exist: {path}")

        # Ensure path is within reasonable bounds (prevent extremely long paths)
        if len(str(path)) > 1000:
            raise SafetyError(f"File path too long: {len(str(path))} characters")

        logger.debug(f"File path validated: {path}")
        return path


def validate_weld_operation(
    weld_paths: List[WeldPath], config: Dict
) -> Tuple[List[str], List[str]]:
    """Validate complete weld operation for safety.

    Args:
        weld_paths: List of weld paths to validate
        config: Configuration dictionary

    Returns:
        Tuple of (warnings, errors)

    Raises:
        SafetyError: If critical safety violations are found
    """
    validator = SafetyValidator()
    all_warnings = []
    all_errors = []

    # Validate configuration
    config_warnings, config_errors = validator.validate_config(config)
    all_warnings.extend(config_warnings)
    all_errors.extend(config_errors)

    # Validate all weld paths
    for path in weld_paths:
        try:
            validator.validate_weld_path(path)
        except SafetyError as e:
            all_errors.append(str(e))

    # Add any additional warnings from point validation
    all_warnings.extend(validator.warnings)

    # Log summary
    if all_errors:
        logger.error(f"Safety validation failed with {len(all_errors)} errors")
        for error in all_errors:
            logger.error(f"  - {error}")

    if all_warnings:
        logger.warning(f"Safety validation completed with {len(all_warnings)} warnings")
        for warning in all_warnings:
            logger.warning(f"  - {warning}")
    else:
        logger.info("Safety validation passed with no warnings")

    return all_warnings, all_errors
