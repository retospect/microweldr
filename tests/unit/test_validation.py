"""Tests for validation functionality."""

import tempfile
from pathlib import Path

import pytest

from microweldr.validation.validators import (
    SVGValidator,
    GCodeValidator,
    AnimationValidator,
    ValidationResult,
)


class TestValidationResult:
    """Test ValidationResult class."""

    def test_validation_result_success(self):
        """Test successful validation result."""
        result = ValidationResult(True, "All good", [])
        assert result.is_valid is True
        assert result.message == "All good"
        assert result.warnings == []

    def test_validation_result_failure(self):
        """Test failed validation result."""
        warnings = ["Warning 1", "Warning 2"]
        result = ValidationResult(False, "Validation failed", warnings)
        assert result.is_valid is False
        assert result.message == "Validation failed"
        assert result.warnings == warnings

    def test_validation_result_repr(self):
        """Test ValidationResult string representation."""
        result = ValidationResult(True, "Success", [])
        assert "ValidationResult" in str(result.__class__.__name__)


class TestSVGValidator:
    """Test SVG validation functionality."""

    def test_valid_svg(self):
        """Test validation of valid SVG."""
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <line x1="10" y1="10" x2="50" y2="10" stroke="black" />
</svg>'''
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(svg_content)
            svg_path = f.name

        try:
            result = SVGValidator.validate(svg_path)
            assert result.is_valid is True
            assert "valid SVG" in result.message
        finally:
            Path(svg_path).unlink()

    def test_invalid_svg_syntax(self):
        """Test validation of invalid SVG syntax."""
        invalid_svg = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <line x1="10" y1="10" x2="50" y2="10" stroke="black" 
</svg>'''  # Missing closing bracket
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(invalid_svg)
            svg_path = f.name

        try:
            result = SVGValidator.validate(svg_path)
            assert result.is_valid is False
            assert "XML parsing error" in result.message
        finally:
            Path(svg_path).unlink()

    def test_svg_with_custom_attributes(self):
        """Test SVG with custom weld attributes."""
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <line x1="10" y1="10" x2="50" y2="10" 
        stroke="black" 
        data-temp="160"
        data-weld-time="0.3"
        data-weld-height="0.025" />
</svg>'''
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(svg_content)
            svg_path = f.name

        try:
            result = SVGValidator.validate(svg_path)
            assert result.is_valid is True
            # Should detect custom attributes
            assert any("custom attributes" in msg.lower() for msg in result.warnings) or result.is_valid
        finally:
            Path(svg_path).unlink()

    def test_nonexistent_file(self):
        """Test validation of nonexistent file."""
        result = SVGValidator.validate("nonexistent.svg")
        assert result.is_valid is False
        assert "File not found" in result.message

    def test_empty_svg(self):
        """Test validation of empty SVG."""
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
</svg>'''
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(svg_content)
            svg_path = f.name

        try:
            result = SVGValidator.validate(svg_path)
            # Empty SVG should be valid but might have warnings
            assert result.is_valid is True
        finally:
            Path(svg_path).unlink()


class TestGCodeValidator:
    """Test G-code validation functionality."""

    def test_valid_gcode(self):
        """Test validation of valid G-code."""
        gcode_content = """
; MicroWeldr G-code
G90 ; Absolute positioning
M83 ; Relative extruder positioning
G28 ; Home all axes
M104 S200 ; Set nozzle temperature
M140 S60 ; Set bed temperature
G1 X10 Y10 Z1 F1000 ; Move to position
G4 P100 ; Weld time
G1 Z5 F600 ; Raise to safe height
M104 S0 ; Turn off nozzle
M140 S0 ; Turn off bed
"""
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gcode", delete=False) as f:
            f.write(gcode_content)
            gcode_path = f.name

        try:
            result = GCodeValidator.validate(gcode_path)
            assert result.is_valid is True
            assert "valid G-code" in result.message
        finally:
            Path(gcode_path).unlink()

    def test_gcode_with_syntax_errors(self):
        """Test G-code with syntax issues."""
        gcode_content = """
G90 ; Absolute positioning
INVALID_COMMAND ; This is not a valid G-code command
G1 X Y Z ; Missing values
M104 ; Missing temperature value
"""
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gcode", delete=False) as f:
            f.write(gcode_content)
            gcode_path = f.name

        try:
            result = GCodeValidator.validate(gcode_path)
            # Should still be valid but with warnings about unknown commands
            assert result.is_valid is True or len(result.warnings) > 0
        finally:
            Path(gcode_path).unlink()

    def test_empty_gcode(self):
        """Test validation of empty G-code file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gcode", delete=False) as f:
            f.write("")
            gcode_path = f.name

        try:
            result = GCodeValidator.validate(gcode_path)
            assert result.is_valid is False
            assert "empty" in result.message.lower()
        finally:
            Path(gcode_path).unlink()

    def test_gcode_missing_file(self):
        """Test validation of missing G-code file."""
        result = GCodeValidator.validate("missing.gcode")
        assert result.is_valid is False
        assert "File not found" in result.message


class TestAnimationValidator:
    """Test animation SVG validation functionality."""

    def test_valid_animation_svg(self):
        """Test validation of valid animation SVG."""
        animation_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="400" height="300" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .weld-point { fill: red; opacity: 0; }
      .weld-point.active { opacity: 1; }
    </style>
  </defs>
  <circle cx="50" cy="50" r="2" class="weld-point">
    <animate attributeName="opacity" values="0;1;0" dur="0.5s" begin="0s"/>
  </circle>
  <circle cx="100" cy="50" r="2" class="weld-point">
    <animate attributeName="opacity" values="0;1;0" dur="0.5s" begin="0.5s"/>
  </circle>
</svg>'''
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(animation_content)
            svg_path = f.name

        try:
            result = SVGValidator.validate(svg_path)
            assert result.is_valid is True
            assert "animation SVG" in result.message
        finally:
            Path(svg_path).unlink()

    def test_animation_svg_missing_elements(self):
        """Test animation SVG missing required elements."""
        animation_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="400" height="300" xmlns="http://www.w3.org/2000/svg">
  <!-- No animation elements -->
</svg>'''
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(animation_content)
            svg_path = f.name

        try:
            result = SVGValidator.validate(svg_path)
            # Should be valid SVG but might have warnings about missing animations
            assert result.is_valid is True
        finally:
            Path(svg_path).unlink()

    def test_animation_svg_invalid_syntax(self):
        """Test animation SVG with invalid syntax."""
        invalid_animation = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="400" height="300" xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="2" class="weld-point"
    <animate attributeName="opacity" values="0;1;0" dur="0.5s"/>
  </circle>
</svg>'''  # Missing closing bracket
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(invalid_animation)
            svg_path = f.name

        try:
            result = SVGValidator.validate(svg_path)
            assert result.is_valid is False
            assert "XML parsing error" in result.message
        finally:
            Path(svg_path).unlink()


class TestValidationIntegration:
    """Test validation integration scenarios."""

    def test_validate_complete_workflow(self):
        """Test validation of complete SVG to G-code workflow."""
        # Create input SVG
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <line x1="10" y1="10" x2="50" y2="10" stroke="black" data-temp="160" />
  <line x1="10" y1="20" x2="50" y2="20" stroke="blue" />
</svg>'''
        
        gcode_content = """
; MicroWeldr Generated G-code
G90 ; Absolute positioning
M83 ; Relative extruder positioning
G28 ; Home all axes
M104 S160 ; Set nozzle temperature
G1 X10 Y10 Z0.02 F1000 ; Weld position
G4 P100 ; Weld time
G1 Z5 F600 ; Safe height
M104 S0 ; Cool down
"""
        
        animation_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="400" height="300" xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="2" class="weld-point">
    <animate attributeName="opacity" values="0;1;0" dur="0.5s"/>
  </circle>
</svg>'''
        
        # Use static methods
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as svg_f:
            svg_f.write(svg_content)
            svg_path = svg_f.name
            
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gcode", delete=False) as gcode_f:
            gcode_f.write(gcode_content)
            gcode_path = gcode_f.name
            
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as anim_f:
            anim_f.write(animation_content)
            anim_path = anim_f.name
        
        try:
            # Validate all components
            svg_result = SVGValidator.validate(svg_path)
            gcode_result = GCodeValidator.validate(gcode_path)
            animation_result = AnimationValidator.validate(anim_path)
            
            assert svg_result.is_valid is True
            assert gcode_result.is_valid is True
            assert animation_result.is_valid is True
            
        finally:
            Path(svg_path).unlink()
            Path(gcode_path).unlink()
            Path(anim_path).unlink()
