"""Test filename-based weld type detection."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from microweldr.core.dxf_reader import DXFReader
from microweldr.core.svg_reader import SVGReader
from microweldr.core.data_models import WeldType


class TestFilenameDetection:
    """Test filename-based weld type detection for both DXF and SVG readers."""

    def test_dxf_filename_frangible_detection(self):
        """Test DXF reader detects frangible welds from filename."""
        reader = DXFReader()

        # Test frangible keywords in filename
        frangible_filenames = [
            "frangible_seals.dxf",
            "frangible_welds.dxf",
            "break_points.dxf",
            "seal_layer.dxf",
            "weak_connections.dxf",
        ]

        for filename in frangible_filenames:
            reader._current_filename = Path(filename).stem
            weld_type = reader._determine_weld_type("normal_layer")
            assert weld_type == WeldType.FRANGIBLE, f"Failed for {filename}"

    def test_dxf_filename_normal_detection(self):
        """Test DXF reader defaults to normal welds for non-frangible filenames."""
        reader = DXFReader()

        # Test normal filenames
        normal_filenames = [
            "main_structure.dxf",
            "primary_welds.dxf",
            "device_outline.dxf",
            "channels.dxf",
        ]

        for filename in normal_filenames:
            reader._current_filename = Path(filename).stem
            weld_type = reader._determine_weld_type("normal_layer")
            assert weld_type == WeldType.NORMAL, f"Failed for {filename}"

    def test_dxf_layer_overrides_filename(self):
        """Test that layer name takes precedence over filename."""
        reader = DXFReader()
        reader._current_filename = "normal_structure"  # Normal filename

        # Frangible layer should override normal filename
        weld_type = reader._determine_weld_type("frangible_layer")
        assert weld_type == WeldType.FRANGIBLE

    def test_svg_filename_frangible_detection(self):
        """Test SVG reader detects frangible welds from filename."""
        reader = SVGReader()

        # Mock element with no frangible indicators
        elem = Mock()
        elem.get.return_value = ""  # No stroke, class, or id indicators

        frangible_filenames = [
            "frangible_design.svg",
            "frangible_channels.svg",
            "break_seals.svg",
            "seal_points.svg",
            "weak_joints.svg",
        ]

        for filename in frangible_filenames:
            reader._current_filename = Path(filename).stem
            weld_type = reader._determine_weld_type(elem)
            assert weld_type == WeldType.FRANGIBLE, f"Failed for {filename}"

    def test_svg_filename_normal_detection(self):
        """Test SVG reader defaults to normal welds for non-frangible filenames."""
        reader = SVGReader()

        # Mock element with no indicators
        elem = Mock()
        elem.get.return_value = ""

        normal_filenames = [
            "main_design.svg",
            "structure.svg",
            "channels.svg",
            "outline.svg",
        ]

        for filename in normal_filenames:
            reader._current_filename = Path(filename).stem
            weld_type = reader._determine_weld_type(elem)
            assert weld_type == WeldType.NORMAL, f"Failed for {filename}"

    def test_svg_color_overrides_filename(self):
        """Test that SVG color takes precedence over filename."""
        reader = SVGReader()
        reader._current_filename = "normal_design"  # Normal filename

        # Mock element with blue stroke (frangible indicator)
        elem = Mock()
        elem.get.side_effect = lambda attr, default="": {
            "stroke": "blue",
            "class": "",
            "id": "",
        }.get(attr, default)

        weld_type = reader._determine_weld_type(elem)
        assert weld_type == WeldType.FRANGIBLE

    def test_filename_case_insensitive(self):
        """Test that filename detection is case insensitive."""
        reader = DXFReader()

        case_variations = [
            "FRANGIBLE_seals",
            "Light_Welds",
            "Break_Points",
            "SEAL_layer",
            "weak_CONNECTIONS",
        ]

        for filename in case_variations:
            reader._current_filename = filename
            weld_type = reader._determine_weld_type("normal_layer")
            assert weld_type == WeldType.FRANGIBLE, f"Failed for {filename}"

    def test_no_filename_fallback(self):
        """Test behavior when no filename is set."""
        reader = DXFReader()
        # Don't set _current_filename

        weld_type = reader._determine_weld_type("normal_layer")
        assert weld_type == WeldType.NORMAL

    def test_empty_filename_fallback(self):
        """Test behavior with empty filename."""
        reader = DXFReader()
        reader._current_filename = ""

        weld_type = reader._determine_weld_type("normal_layer")
        assert weld_type == WeldType.NORMAL
