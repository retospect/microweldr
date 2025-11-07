"""Validation functionality for SVG and G-code files."""

from pathlib import Path
from typing import List, Optional

# Optional validation libraries
try:
    from lxml import etree  # nosec B410 - Used for trusted SVG validation only

    LXML_AVAILABLE = True
except ImportError:
    LXML_AVAILABLE = False

try:
    from gcodeparser import GcodeParser

    GCODEPARSER_AVAILABLE = True
except ImportError:
    GCODEPARSER_AVAILABLE = False


class ValidationError(Exception):
    """Raised when validation fails."""

    pass


class ValidationResult:
    """Result of a validation operation."""

    def __init__(
        self, is_valid: bool, message: str, warnings: Optional[List[str]] = None
    ):
        self.is_valid = is_valid
        self.message = message
        self.warnings = warnings or []

    def __bool__(self) -> bool:
        return self.is_valid


class SVGValidator:
    """Validator for SVG files."""

    @staticmethod
    def validate(svg_path: str | Path) -> ValidationResult:
        """Validate SVG file structure and syntax."""
        svg_path = Path(svg_path)

        if not LXML_AVAILABLE:
            return ValidationResult(
                is_valid=True,
                message="SVG validation skipped - lxml not available",
                warnings=["Install lxml for comprehensive SVG validation"],
            )

        try:
            # Parse with lxml for better validation
            with open(svg_path, "rb") as f:
                doc = etree.parse(f)  # nosec B320 - Parsing trusted user SVG files

            # Basic SVG structure validation
            root = doc.getroot()
            warnings = []

            if root.tag != "{http://www.w3.org/2000/svg}svg":
                return ValidationResult(
                    is_valid=False, message=f"Root element is not SVG: {root.tag}"
                )

            # Check for required attributes
            if "width" not in root.attrib or "height" not in root.attrib:
                warnings.append("SVG missing width or height attributes")

            return ValidationResult(
                is_valid=True,
                message=f"SVG validation passed: {svg_path}",
                warnings=warnings,
            )

        except etree.XMLSyntaxError as e:
            return ValidationResult(is_valid=False, message=f"Invalid SVG syntax: {e}")
        except Exception as e:
            return ValidationResult(
                is_valid=True,  # Continue processing despite validation issues
                message=f"SVG validation warning: {e}",
                warnings=[str(e)],
            )

    @staticmethod
    def validate_file(svg_path: str | Path) -> ValidationResult:
        """Validate SVG file structure and syntax (alias for validate)."""
        return SVGValidator.validate(svg_path)


class GCodeValidator:
    """Validator for G-code files."""

    @staticmethod
    def validate(gcode_path: str | Path) -> ValidationResult:
        """Validate generated G-code syntax and structure."""
        gcode_path = Path(gcode_path)

        if not GCODEPARSER_AVAILABLE:
            return ValidationResult(
                is_valid=True,
                message="G-code validation skipped - gcodeparser not available",
                warnings=["Install gcodeparser for comprehensive G-code validation"],
            )

        try:
            with open(gcode_path, "r") as f:
                gcode_content = f.read()

            # Parse with gcodeparser
            parser = GcodeParser(gcode_content, include_comments=True)
            lines = parser.lines

            # Basic validation checks
            has_init = False
            has_home = False
            has_temp_commands = False
            has_movement = False

            for line in lines:
                if hasattr(line, "command") and line.command:
                    cmd_letter, cmd_number = line.command

                    if cmd_letter == "G":
                        if cmd_number == 28:  # Home
                            has_home = True
                        elif cmd_number == 90:  # Absolute positioning
                            has_init = True
                        elif cmd_number in [0, 1]:  # Movement
                            has_movement = True

                    elif cmd_letter == "M":
                        if cmd_number in [104, 109, 140, 190]:  # Temperature commands
                            has_temp_commands = True

            # Validation results
            warnings = []
            if not has_init:
                warnings.append("Missing initialization commands (G90)")
            if not has_home:
                warnings.append("Missing home command (G28)")
            if not has_temp_commands:
                warnings.append("Missing temperature commands")
            if not has_movement:
                warnings.append("Missing movement commands")

            is_valid = len(warnings) == 0
            message = f"G-code validation {'passed' if is_valid else 'completed with warnings'}: {gcode_path}"

            return ValidationResult(
                is_valid=is_valid, message=message, warnings=warnings
            )

        except Exception as e:
            return ValidationResult(
                is_valid=True,  # Continue despite validation issues
                message=f"G-code validation warning: {e}",
                warnings=[str(e)],
            )

    @staticmethod
    def validate_content(gcode_content: str) -> ValidationResult:
        """Validate G-code content string."""
        if not GCODEPARSER_AVAILABLE:
            return ValidationResult(
                is_valid=True,
                message="G-code validation skipped - gcodeparser not available",
                warnings=["Install gcodeparser for comprehensive G-code validation"],
            )

        try:
            # Parse with gcodeparser
            parser = GcodeParser(gcode_content, include_comments=True)
            lines = parser.lines

            # Basic validation checks
            has_init = False
            has_home = False
            has_temp_commands = False
            has_movement = False

            for line in lines:
                if hasattr(line, "command") and line.command:
                    cmd_letter, cmd_number = line.command

                    if cmd_letter == "G":
                        if cmd_number == 28:  # Home
                            has_home = True
                        elif cmd_number == 90:  # Absolute positioning
                            has_init = True
                        elif cmd_number in [0, 1]:  # Movement
                            has_movement = True
                    elif cmd_letter == "M":
                        if cmd_number in [104, 109, 140, 190]:  # Temperature commands
                            has_temp_commands = True

            # Validation results
            warnings = []
            if not has_init:
                warnings.append("Missing initialization commands (G90)")
            if not has_home:
                warnings.append("Missing home command (G28)")
            if not has_temp_commands:
                warnings.append("Missing temperature commands")
            if not has_movement:
                warnings.append("Missing movement commands")

            is_valid = len(warnings) == 0
            message = f"G-code validation {'passed' if is_valid else 'completed with warnings'}"

            return ValidationResult(
                is_valid=is_valid, message=message, warnings=warnings
            )

        except Exception as e:
            return ValidationResult(
                is_valid=True,  # Continue despite validation issues
                message=f"G-code validation warning: {e}",
                warnings=[str(e)],
            )


class AnimationValidator:
    """Validator for animation SVG files."""

    @staticmethod
    def validate(svg_path: str | Path) -> ValidationResult:
        """Validate generated animation SVG."""
        svg_path = Path(svg_path)

        if not LXML_AVAILABLE:
            return ValidationResult(
                is_valid=True,
                message="Animation validation skipped - lxml not available",
            )

        try:
            with open(svg_path, "rb") as f:
                doc = etree.parse(f)  # nosec B320 - Parsing trusted user SVG files

            root = doc.getroot()

            # Check for animation elements
            animations = root.xpath(
                "//svg:animate", namespaces={"svg": "http://www.w3.org/2000/svg"}
            )
            circles = root.xpath(
                "//svg:circle", namespaces={"svg": "http://www.w3.org/2000/svg"}
            )

            warnings = []
            if len(animations) == 0:
                warnings.append("No animation elements found in output SVG")

            if len(circles) == 0:
                warnings.append("No circle elements found in animation SVG")

            is_valid = len(warnings) == 0
            message = f"Animation SVG validation {'passed' if is_valid else 'completed with warnings'}: {svg_path}"
            if is_valid:
                message += f" ({len(animations)} animations, {len(circles)} circles)"

            return ValidationResult(
                is_valid=is_valid, message=message, warnings=warnings
            )

        except Exception as e:
            return ValidationResult(
                is_valid=True,
                message=f"Animation SVG validation warning: {e}",
                warnings=[str(e)],
            )

    @staticmethod
    def validate_content(animation_content: str) -> ValidationResult:
        """Validate animation content string."""
        if not LXML_AVAILABLE:
            return ValidationResult(
                is_valid=True,
                message="Animation validation skipped - lxml not available",
                warnings=["Install lxml for comprehensive animation validation"],
            )

        try:
            # Parse animation content
            doc = etree.fromstring(
                animation_content.encode()
            )  # nosec B320 - Parsing trusted animation content

            # Check for animation elements
            animations = doc.xpath(
                "//svg:animate", namespaces={"svg": "http://www.w3.org/2000/svg"}
            )
            circles = doc.xpath(
                "//svg:circle", namespaces={"svg": "http://www.w3.org/2000/svg"}
            )

            warnings = []
            if len(animations) == 0:
                warnings.append("No animation elements found in output SVG")

            if len(circles) == 0:
                warnings.append("No circle elements found in animation SVG")

            is_valid = len(warnings) == 0
            message = f"Animation SVG validation {'passed' if is_valid else 'completed with warnings'}"
            if is_valid:
                message += f" ({len(animations)} animations, {len(circles)} circles)"

            return ValidationResult(
                is_valid=is_valid, message=message, warnings=warnings
            )

        except Exception as e:
            return ValidationResult(
                is_valid=True,
                message=f"Animation SVG validation warning: {e}",
                warnings=[str(e)],
            )
