"""Constants and enums for MicroWeldr to eliminate magic strings and values."""

from enum import Enum
from typing import List


class WeldType(Enum):
    """Types of welding operations."""

    NORMAL = "normal"  # Standard welding with full heat
    FRANGIBLE = "frangible"  # Frangible welding with reduced heat/time
    STOP = "stop"  # Stop point with pause message
    PIPETTE = "pipette"  # Pipetting operation point


class PrinterState(Enum):
    """Printer operational states."""

    OPERATIONAL = "Operational"
    PRINTING = "Printing"
    PAUSED = "Paused"
    FINISHED = "Finished"
    ERROR = "Error"
    OFFLINE = "Offline"
    UNKNOWN = "Unknown"


class ValidationStatus(Enum):
    """Validation result statuses."""

    VALID = "valid"
    WARNING = "warning"
    ERROR = "error"
    SKIPPED = "skipped"


class WorkflowStatus(Enum):
    """Workflow execution statuses."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class HealthStatus(Enum):
    """System health statuses."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class FileExtensions:
    """File extensions used throughout the system."""

    SVG = ".svg"
    GCODE = ".gcode"
    ANIMATION = "_animation.svg"
    CONFIG = ".toml"
    BACKUP = ".backup"
    TEMP = ".tmp"
    LOG = ".log"


class ConfigSections:
    """Configuration file section names."""

    PRINTER = "printer"
    NOZZLE = "nozzle"
    TEMPERATURES = "temperatures"
    MOVEMENT = "movement"
    NORMAL_WELDS = "normal_welds"
    FRANGIBLE_WELDS = "frangible_welds"
    ANIMATION = "animation"
    OUTPUT = "output"
    PRUSALINK = "prusalink"


class ConfigKeys:
    """Configuration parameter keys."""

    # Printer settings
    BED_SIZE_X = "bed_size_x"
    BED_SIZE_Y = "bed_size_y"
    BED_SIZE_Z = "bed_size_z"

    # Nozzle settings
    OUTER_DIAMETER = "outer_diameter"
    INNER_DIAMETER = "inner_diameter"

    # Temperature settings
    BED_TEMPERATURE = "bed_temperature"
    NOZZLE_TEMPERATURE = "nozzle_temperature"
    CHAMBER_TEMPERATURE = "chamber_temperature"
    USE_CHAMBER_HEATING = "use_chamber_heating"
    COOLDOWN_TEMPERATURE = "cooldown_temperature"

    # Movement settings
    MOVE_HEIGHT = "move_height"
    TRAVEL_SPEED = "travel_speed"
    Z_SPEED = "z_speed"

    # Weld settings
    WELD_HEIGHT = "weld_height"
    WELD_TEMPERATURE = "weld_temperature"
    WELD_TIME = "weld_time"
    DOT_SPACING = "dot_spacing"
    INITIAL_DOT_SPACING = "initial_dot_spacing"
    COOLING_TIME_BETWEEN_PASSES = "cooling_time_between_passes"

    # Animation settings
    TIME_BETWEEN_WELDS = "time_between_welds"
    PAUSE_TIME = "pause_time"
    MIN_ANIMATION_DURATION = "min_animation_duration"

    # Output settings
    GCODE_EXTENSION = "gcode_extension"
    ANIMATION_EXTENSION = "animation_extension"

    # PrusaLink settings
    HOST = "host"
    USERNAME = "username"
    PASSWORD = (
        "password"  # nosec B105 - This is a config key name, not a hardcoded password
    )
    API_KEY = "api_key"
    TIMEOUT = "timeout"


class SVGAttributes:
    """SVG element attributes used for welding parameters."""

    DATA_TEMP = "data-temp"
    DATA_WELD_TIME = "data-weld-time"
    DATA_WELD_HEIGHT = "data-weld-height"
    DATA_BED_TEMP = "data-bed-temp"
    DATA_PAUSE_MESSAGE = "data-pause-message"

    # Legacy attributes (for backward compatibility)
    DATA_WELDING_TIME = "data-welding-time"
    DATA_WELDING_HEIGHT = "data-welding-height"

    # Standard SVG attributes
    STROKE = "stroke"
    STROKE_WIDTH = "stroke-width"
    FILL = "fill"
    D = "d"  # Path data
    X1 = "x1"
    Y1 = "y1"
    X2 = "x2"
    Y2 = "y2"
    CX = "cx"
    CY = "cy"
    R = "r"
    WIDTH = "width"
    HEIGHT = "height"


class Colors:
    """Color mappings for weld types."""

    NORMAL_WELD = "black"
    FRANGIBLE_WELD = "blue"
    STOP_POINT = "red"
    PIPETTE_POINT = "magenta"  # Changed from green to magenta for pipette

    # Alternative color names
    NORMAL_ALIASES = {"black", "#000000", "#000", "rgb(0,0,0)"}
    FRANGIBLE_ALIASES = {"blue", "#0000ff", "#00f", "rgb(0,0,255)"}
    STOP_ALIASES = {"red", "#ff0000", "#f00", "rgb(255,0,0)"}
    PIPETTE_ALIASES = {
        "magenta",
        "pink",
        "fuchsia",
        "#ff00ff",
        "#f0f",
        "#ff69b4",
        "#ffc0cb",
        "rgb(255,0,255)",
        "rgb(255,105,180)",
        "rgb(255,192,203)",
    }


class SafetyLimits:
    """Safety limits for welding operations."""

    # Temperature limits (°C)
    MAX_TEMPERATURE = 120.0
    MIN_TEMPERATURE = 50.0
    MAX_BED_TEMP = 80.0

    # Physical limits (mm)
    MAX_WELD_HEIGHT = 0.5
    MIN_WELD_HEIGHT = 0.001

    # Time limits (seconds)
    MAX_WELD_TIME = 5.0
    MIN_WELD_TIME = 0.05

    # Speed limits (mm/min)
    MAX_TRAVEL_SPEED = 3000
    MAX_Z_SPEED = 1000

    # File size limits
    MAX_FILE_SIZE_MB = 100
    MAX_PATH_LENGTH = 1000


class GCodeCommands:
    """G-code command constants."""

    # Movement commands
    G0 = "G0"  # Rapid positioning
    G1 = "G1"  # Linear interpolation
    G28 = "G28"  # Auto home
    G90 = "G90"  # Absolute positioning
    G91 = "G91"  # Relative positioning

    # Temperature commands
    M104 = "M104"  # Set extruder temperature
    M109 = "M109"  # Set extruder temperature and wait
    M140 = "M140"  # Set bed temperature
    M190 = "M190"  # Set bed temperature and wait
    M141 = "M141"  # Set chamber temperature (Core One)
    M191 = "M191"  # Set chamber temperature and wait (Core One)

    # Extruder commands
    M82 = "M82"  # Absolute extruder mode
    M83 = "M83"  # Relative extruder mode

    # Utility commands
    G4 = "G4"  # Dwell/pause
    M117 = "M117"  # Display message
    M300 = "M300"  # Play tone

    # Bed leveling
    G29 = "G29"  # Auto bed leveling

    # End commands
    M84 = "M84"  # Disable steppers


class DefaultValues:
    """Default configuration values."""

    # Printer dimensions (Prusa Core One)
    BED_SIZE_X = 250
    BED_SIZE_Y = 220
    BED_SIZE_Z = 270

    # Default temperatures
    BED_TEMPERATURE = 60
    NOZZLE_TEMPERATURE = 200
    CHAMBER_TEMPERATURE = 35
    COOLDOWN_TEMPERATURE = 50

    # Default movement settings
    MOVE_HEIGHT = 5.0
    TRAVEL_SPEED = 3000
    Z_SPEED = 600

    # Default weld settings
    NORMAL_WELD_HEIGHT = 0.020
    NORMAL_WELD_TEMPERATURE = 100
    NORMAL_WELD_TIME = 0.1
    FRANGIBLE_WELD_HEIGHT = 0.020
    FRANGIBLE_WELD_TEMPERATURE = 110
    FRANGIBLE_WELD_TIME = 0.3
    DOT_SPACING = 0.9
    INITIAL_DOT_SPACING = 3.6
    COOLING_TIME = 2.0

    # Default animation settings
    TIME_BETWEEN_WELDS = 0.5
    PAUSE_TIME = 2.0
    MIN_ANIMATION_DURATION = 10.0

    # Default timeouts and intervals
    PRUSALINK_TIMEOUT = 30
    HEALTH_CHECK_INTERVAL = 300
    PROGRESS_UPDATE_INTERVAL = 0.1


class ErrorMessages:
    """Standard error messages."""

    # File errors
    FILE_NOT_FOUND = "File not found: {path}"
    FILE_EMPTY = "File is empty: {path}"
    FILE_TOO_LARGE = "File too large: {path} ({size}MB > {limit}MB)"

    # Validation errors
    INVALID_WELD_TYPE = "Invalid weld_type: {weld_type}. Must be one of: {valid_types}"
    TEMPERATURE_TOO_HIGH = "{param} {temp}°C exceeds maximum safe limit of {limit}°C"
    TEMPERATURE_TOO_LOW = "{param} {temp}°C is below minimum of {limit}°C"
    HEIGHT_TOO_HIGH = "{param} {height}mm exceeds maximum safe limit of {limit}mm"
    TIME_TOO_LONG = "{param} {time}s exceeds maximum safe limit of {limit}s"

    # Configuration errors
    MISSING_CONFIG_SECTION = "Missing required configuration section: {section}"
    INVALID_CONFIG_VALUE = "Invalid configuration value for {key}: {value}"

    # Printer errors
    PRINTER_NOT_READY = "Printer not ready (state: {state})"
    CONNECTION_FAILED = "Failed to connect to printer: {error}"
    UPLOAD_FAILED = "Failed to upload file to printer: {error}"

    # Security errors
    WEAK_PASSWORD = "Password is too weak: {reason}"  # nosec B105 - This is an error message template, not a hardcoded password
    INSECURE_FILE_PERMISSIONS = "File has insecure permissions: {path}"
    INVALID_IP_ADDRESS = "Invalid IP address: {ip}"


class WarningMessages:
    """Standard warning messages."""

    LOW_TEMPERATURE = "{param} {temp}°C is below recommended minimum of {limit}°C"
    HIGH_FILE_SIZE = "Large file size: {size}MB may cause performance issues"
    DEPRECATED_ATTRIBUTE = "Deprecated SVG attribute '{old}' used, please use '{new}'"
    FALLBACK_MODE = "Operating in fallback mode: {reason}"


class LogMessages:
    """Standard log messages."""

    OPERATION_STARTED = "Started {operation}"
    OPERATION_COMPLETED = "Completed {operation} in {duration:.2f}s"
    OPERATION_FAILED = "Failed {operation}: {error}"
    FILE_PROCESSED = "Processed {file}: {points} points in {paths} paths"
    VALIDATION_PASSED = "Validation passed: {file}"
    VALIDATION_FAILED = (
        "Validation failed: {file} - {errors} errors, {warnings} warnings"
    )


# Utility functions for working with constants
def get_valid_weld_types() -> List[str]:
    """Get list of valid weld type strings."""
    return [wt.value for wt in WeldType]


def get_weld_type_enum(weld_type_str: str) -> WeldType:
    """Convert string to WeldType enum.

    Args:
        weld_type_str: String representation of weld type

    Returns:
        WeldType enum value

    Raises:
        ValueError: If weld type is invalid
    """
    try:
        return WeldType(weld_type_str.lower())
    except ValueError:
        valid_types = get_valid_weld_types()
        raise ValueError(
            ErrorMessages.INVALID_WELD_TYPE.format(
                weld_type=weld_type_str, valid_types=", ".join(valid_types)
            )
        )


def get_color_weld_type(color: str) -> WeldType:
    """Get weld type from color string.

    Args:
        color: Color string (name, hex, or rgb)

    Returns:
        WeldType enum value

    Raises:
        ValueError: If color doesn't map to a weld type
    """
    color = color.lower().strip()

    if color in Colors.NORMAL_ALIASES:
        return WeldType.NORMAL
    elif color in Colors.FRANGIBLE_ALIASES:
        return WeldType.FRANGIBLE
    elif color in Colors.STOP_ALIASES:
        return WeldType.STOP
    elif color in Colors.PIPETTE_ALIASES:
        return WeldType.PIPETTE
    else:
        raise ValueError(f"Unknown color for weld type: {color}")


# Configuration validation helpers
REQUIRED_CONFIG_SECTIONS = [
    ConfigSections.PRINTER,
    ConfigSections.TEMPERATURES,
    ConfigSections.MOVEMENT,
    ConfigSections.NORMAL_WELDS,
]

TEMPERATURE_CONFIG_KEYS = [
    ConfigKeys.BED_TEMPERATURE,
    ConfigKeys.NOZZLE_TEMPERATURE,
    ConfigKeys.CHAMBER_TEMPERATURE,
    ConfigKeys.COOLDOWN_TEMPERATURE,
    ConfigKeys.WELD_TEMPERATURE,
]

SAFETY_CRITICAL_KEYS = [
    ConfigKeys.WELD_TEMPERATURE,
    ConfigKeys.WELD_HEIGHT,
    ConfigKeys.WELD_TIME,
    ConfigKeys.TRAVEL_SPEED,
    ConfigKeys.Z_SPEED,
]
