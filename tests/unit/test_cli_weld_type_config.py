"""End-to-end tests for CLI weld type configuration flow.

Tests that config values (heights, times, temps) correctly flow through
process_weld_file() to final G-code output for both normal and frangible welds.
"""

import os
from pathlib import Path

import pytest

from microweldr.cli.simple_main import generate_gcode, process_weld_file
from microweldr.core.config import Config


@pytest.fixture
def simple_dxf_file(tmp_path):
    """Create a minimal DXF file with a simple line for testing."""
    dxf_content = """0
SECTION
2
HEADER
9
$ACADVER
1
AC1015
0
ENDSEC
0
SECTION
2
ENTITIES
0
LINE
8
0
10
10.0
20
10.0
11
20.0
21
10.0
0
ENDSEC
0
EOF
"""
    dxf_file = tmp_path / "test_weld.dxf"
    dxf_file.write_text(dxf_content)
    return dxf_file


@pytest.fixture
def custom_config(tmp_path):
    """Create a config with specific odd test values."""
    config_content = """
[printer]
bed_size_x = 250.0
bed_size_y = 220.0
max_z_height = 270.0

[nozzle]
outer_diameter = 1.4
inner_diameter = 0.2

[temperatures]
bed_temperature = 45
nozzle_temperature = 160
chamber_temperature = 35
use_chamber_heating = false
cooldown_temperature = 0
enable_cooldown = false

[movement]
move_height = 5.0
low_travel_height = 1.5
travel_speed = 3000
z_speed = 3000
weld_height = 0.02
weld_move_height = 2.0
weld_compression_offset = 0.0

[normal_welds]
weld_height = 0.123
weld_temperature = 165
weld_time = 0.456
dot_spacing = 0.8

[frangible_welds]
weld_height = 0.234
weld_temperature = 170
weld_time = 0.789
dot_spacing = 0.8

[output]
gcode_extension = ".gcode"
animation_extension = "_animation.svg"

[sequencing]
skip_base_distance = 5
passes = 4
"""
    config_file = tmp_path / "microweldr_config.toml"
    config_file.write_text(config_content)
    return config_file


class TestWeldTypeConfigFlow:
    """Test end-to-end flow from config to G-code output."""

    def test_normal_weld_config_to_gcode(
        self, simple_dxf_file, custom_config, tmp_path
    ):
        """Test that normal weld config values flow correctly to G-code output."""
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            config = Config()

            points = process_weld_file(str(simple_dxf_file), config, is_frangible=False)

            assert len(points) > 0
            for point in points:
                assert point["weld_type"] == "normal"

            output_gcode = tmp_path / "test_normal.gcode"

            class Args:
                verbose = False

            success = generate_gcode(points, str(output_gcode), config, Args())
            assert success
            assert output_gcode.exists()

            gcode_content = output_gcode.read_text()

            assert "G1 Z0.123 F3000 ; Lower to weld height" in gcode_content
            assert "G4 P456 ; Weld for 0.456s" in gcode_content
            assert "M104 S165" in gcode_content or "M109 S165" in gcode_content
        finally:
            os.chdir(original_dir)

    def test_frangible_weld_config_to_gcode(
        self, simple_dxf_file, custom_config, tmp_path
    ):
        """Test that frangible weld config values flow correctly to G-code output."""
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            config = Config()

            points = process_weld_file(str(simple_dxf_file), config, is_frangible=True)

            assert len(points) > 0
            for point in points:
                assert point["weld_type"] == "frangible"

            output_gcode = tmp_path / "test_frangible.gcode"

            class Args:
                verbose = False

            success = generate_gcode(points, str(output_gcode), config, Args())
            assert success
            assert output_gcode.exists()

            gcode_content = output_gcode.read_text()

            assert "G1 Z0.234 F3000 ; Lower to frangible weld height" in gcode_content
            assert "G4 P789 ; Frangible weld for 0.789s" in gcode_content
            assert "M104 S170" in gcode_content or "M109 S170" in gcode_content
        finally:
            os.chdir(original_dir)

    def test_mixed_weld_types_in_same_gcode(
        self, simple_dxf_file, custom_config, tmp_path
    ):
        """Test that both normal and frangible welds can coexist with correct config."""
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            config = Config()

            normal_points = process_weld_file(
                str(simple_dxf_file), config, is_frangible=False
            )
            frangible_points = process_weld_file(
                str(simple_dxf_file), config, is_frangible=True
            )

            all_points = normal_points + frangible_points

            normal_count = sum(1 for p in all_points if p["weld_type"] == "normal")
            frangible_count = sum(
                1 for p in all_points if p["weld_type"] == "frangible"
            )
            assert normal_count > 0
            assert frangible_count > 0

            output_gcode = tmp_path / "test_mixed.gcode"

            class Args:
                verbose = False

            success = generate_gcode(all_points, str(output_gcode), config, Args())
            assert success
            assert output_gcode.exists()

            gcode_content = output_gcode.read_text()

            assert "G1 Z0.123 F3000 ; Lower to weld height" in gcode_content
            assert "G4 P456 ; Weld for 0.456s" in gcode_content
            assert "G1 Z0.234 F3000 ; Lower to frangible weld height" in gcode_content
            assert "G4 P789 ; Frangible weld for 0.789s" in gcode_content
        finally:
            os.chdir(original_dir)

    def test_is_frangible_flag_overrides_layer_detection(
        self, simple_dxf_file, custom_config, tmp_path
    ):
        """Test that is_frangible=True flag overrides DXF layer-based weld type detection."""
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            config = Config()

            normal_points = process_weld_file(
                str(simple_dxf_file), config, is_frangible=False
            )
            frangible_points = process_weld_file(
                str(simple_dxf_file), config, is_frangible=True
            )

            assert len(normal_points) == len(frangible_points)

            for point in normal_points:
                assert point["weld_type"] == "normal"

            for point in frangible_points:
                assert point["weld_type"] == "frangible"
        finally:
            os.chdir(original_dir)

    def test_config_values_precision(self, simple_dxf_file, custom_config, tmp_path):
        """Test that odd decimal values are preserved with correct precision in G-code."""
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            config = Config()

            # Verify config loaded correctly with our odd test values
            assert config.get("normal_welds", "weld_height") == 0.123
            assert config.get("normal_welds", "weld_time") == 0.456

            assert config.get("frangible_welds", "weld_height") == 0.234
            assert config.get("frangible_welds", "weld_time") == 0.789

            normal_points = process_weld_file(
                str(simple_dxf_file), config, is_frangible=False
            )
            output_gcode = tmp_path / "test_precision.gcode"

            class Args:
                verbose = False

            generate_gcode(normal_points, str(output_gcode), config, Args())
            gcode_content = output_gcode.read_text()

            assert "Z0.123" in gcode_content
            assert "P456" in gcode_content
        finally:
            os.chdir(original_dir)
