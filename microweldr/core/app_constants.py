"""Application-wide constants for MicroWeldr."""

from typing import Final


# HTTP Status Codes
class HTTPStatus:
    """HTTP status codes used throughout the application."""

    OK: Final[int] = 200
    UNAUTHORIZED: Final[int] = 401
    NOT_FOUND: Final[int] = 404
    CONFLICT: Final[int] = 409
    INTERNAL_SERVER_ERROR: Final[int] = 500


# Timeouts and Intervals
class Timeouts:
    """Timeout values in seconds."""

    DEFAULT_REQUEST: Final[int] = 30
    LONG_REQUEST: Final[int] = 60
    MONITORING_INTERVAL: Final[int] = 30
    ERROR_RETRY_DELAY: Final[int] = 60
    SHORT_DELAY: Final[int] = 5


# Temperature Constants
class Temperatures:
    """Temperature-related constants in Celsius."""

    DEFAULT_BED: Final[int] = 35
    DEFAULT_NOZZLE: Final[int] = 160
    DEFAULT_CHAMBER: Final[int] = 35
    COOLDOWN: Final[int] = 50
    MIN_SAFE_NOZZLE: Final[int] = 100
    MAX_SAFE_NOZZLE: Final[int] = 250
    TOLERANCE: Final[int] = 10


# G-code Command Numbers
class GCodeCommands:
    """G-code and M-code command numbers."""

    # G-codes
    RAPID_MOVE: Final[int] = 0
    LINEAR_MOVE: Final[int] = 1
    HOME_ALL: Final[int] = 28
    ABSOLUTE_POSITIONING: Final[int] = 90
    RELATIVE_POSITIONING: Final[int] = 91

    # M-codes
    SET_EXTRUDER_TEMP: Final[int] = 104
    SET_BED_TEMP: Final[int] = 140
    WAIT_EXTRUDER_TEMP: Final[int] = 109
    WAIT_BED_TEMP: Final[int] = 190


# File Extensions
class FileExtensions:
    """Supported file extensions."""

    SVG: Final[str] = ".svg"
    DXF: Final[str] = ".dxf"
    GCODE: Final[str] = ".gcode"
    TOML: Final[str] = ".toml"
    PNG: Final[str] = ".png"


# SVG Namespace
class SVGNamespace:
    """SVG XML namespace constants."""

    URI: Final[str] = "http://www.w3.org/2000/svg"
    PREFIX: Final[str] = "svg"


# DXF Entity Types
class DXFEntities:
    """DXF entity type names."""

    LINE: Final[str] = "LINE"
    ARC: Final[str] = "ARC"
    CIRCLE: Final[str] = "CIRCLE"
    POLYLINE: Final[str] = "POLYLINE"
    LWPOLYLINE: Final[str] = "LWPOLYLINE"


# Layer Types
class LayerTypes:
    """Layer classification for CAD files."""

    CONSTRUCTION: Final[str] = "construction"
    WELDING: Final[str] = "welding"
    FRANGIBLE: Final[str] = "frangible"


# Geometric Constants
class Geometry:
    """Geometric calculation constants."""

    TOLERANCE_MM: Final[float] = 0.001


# Progress and Status
class Progress:
    """Progress tracking constants."""

    INITIAL_THRESHOLD: Final[float] = 5.0
    FINAL_THRESHOLD: Final[float] = 95.0
    LOW_Z_THRESHOLD: Final[float] = 10.0
    MID_Z_THRESHOLD: Final[float] = 50.0


# Terminal Display
class Display:
    """Display formatting constants."""

    SEPARATOR_LENGTH: Final[int] = 60
    SHORT_SEPARATOR_LENGTH: Final[int] = 40
    PROGRESS_BAR_WIDTH: Final[int] = 20
    MAX_FILENAME_DISPLAY: Final[int] = 50


# Validation Limits
class ValidationLimits:
    """Limits for validation checks."""

    MAX_FILE_SIZE_MB: Final[int] = 100
    MAX_POINTS_PER_PATH: Final[int] = 10000
    MIN_WELD_TIME: Final[float] = 0.05
    MAX_WELD_TIME: Final[float] = 5.0
    MAX_TRAVEL_SPEED: Final[int] = 3000
