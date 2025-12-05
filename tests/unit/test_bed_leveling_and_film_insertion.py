"""Unit tests for bed leveling and film insertion workflow.

Tests ensure that:
1. Bed leveling (G29) is included when -level-bed flag is set
2. Film insertion pause happens AFTER bed leveling (if enabled) but BEFORE welding
3. Film insertion raises Z to configurable height for user access
4. Workflow is correct with different combinations of flags
"""

import os
import tempfile
from pathlib import Path

import pytest

from microweldr.cli.simple_main import generate_gcode, process_weld_file
from microweldr.core.config import Config


@pytest.fixture
def simple_dxf_file(tmp_path):
    """Create a minimal DXF file for testing."""
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
def test_config(tmp_path):
    """Create a test config with film_insertion_height."""
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
film_insertion_height = 150.0

[normal_welds]
weld_height = 0.02
weld_temperature = 160
weld_time = 0.3
dot_spacing = 0.8

[frangible_welds]
weld_height = 0.04
weld_temperature = 160
weld_time = 0.5
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


class TestBedLevelingAndFilmInsertion:
    """Test bed leveling and film insertion workflow."""

    def test_bed_leveling_included_when_flag_set(
        self, simple_dxf_file, test_config, tmp_path
    ):
        """Test that G29 bed leveling is included when -level-bed flag is set."""
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            config = Config()

            points = process_weld_file(str(simple_dxf_file), config, is_frangible=False)
            output_gcode = tmp_path / "test_with_leveling.gcode"

            # Simulate -level-bed flag
            class Args:
                verbose = False
                level_bed = True
                stop_for_film = True

            success = generate_gcode(points, str(output_gcode), config, Args())
            assert success
            assert output_gcode.exists()

            gcode_content = output_gcode.read_text()

            # Verify bed leveling is included
            assert "G29 ; Auto bed leveling" in gcode_content
            assert "; Bed leveling after thermal expansion" in gcode_content
        finally:
            os.chdir(original_dir)

    def test_bed_leveling_excluded_when_flag_not_set(
        self, simple_dxf_file, test_config, tmp_path
    ):
        """Test that G29 bed leveling is NOT included when -level-bed flag is not set."""
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            config = Config()

            points = process_weld_file(str(simple_dxf_file), config, is_frangible=False)
            output_gcode = tmp_path / "test_without_leveling.gcode"

            # Simulate NO -level-bed flag
            class Args:
                verbose = False
                level_bed = False
                stop_for_film = True

            success = generate_gcode(points, str(output_gcode), config, Args())
            assert success
            assert output_gcode.exists()

            gcode_content = output_gcode.read_text()

            # Verify bed leveling is NOT included
            assert "G29 ; Auto bed leveling" not in gcode_content
            assert "; Bed leveling disabled" in gcode_content
        finally:
            os.chdir(original_dir)

    def test_film_insertion_pause_after_bed_leveling(
        self, simple_dxf_file, test_config, tmp_path
    ):
        """Test that film insertion pause happens AFTER bed leveling but BEFORE welding."""
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            config = Config()

            points = process_weld_file(str(simple_dxf_file), config, is_frangible=False)
            output_gcode = tmp_path / "test_sequence.gcode"

            class Args:
                verbose = False
                level_bed = True
                stop_for_film = True

            success = generate_gcode(points, str(output_gcode), config, Args())
            assert success

            gcode_content = output_gcode.read_text()

            # Find positions of key events
            bed_leveling_pos = gcode_content.find("G29 ; Auto bed leveling")
            film_pause_pos = gcode_content.find("M0 ; Pause - Insert plastic sheets")
            first_weld_pos = gcode_content.find("; Starting path:")

            # Verify sequence: bed leveling -> film pause -> welding
            assert (
                bed_leveling_pos < film_pause_pos < first_weld_pos
            ), "Sequence should be: bed leveling -> film pause -> welding"
        finally:
            os.chdir(original_dir)

    def test_film_insertion_raises_z_to_configured_height(
        self, simple_dxf_file, test_config, tmp_path
    ):
        """Test that film insertion pause raises Z to configured height (150mm default)."""
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            config = Config()

            points = process_weld_file(str(simple_dxf_file), config, is_frangible=False)
            output_gcode = tmp_path / "test_z_height.gcode"

            class Args:
                verbose = False
                level_bed = False
                stop_for_film = True

            success = generate_gcode(points, str(output_gcode), config, Args())
            assert success

            gcode_content = output_gcode.read_text()

            # Verify Z is raised to film_insertion_height before pause
            assert "G1 Z150.0 F3000 ; Raise Z for film insertion" in gcode_content

            # Verify pause message follows
            lines = gcode_content.split("\n")
            z_raise_idx = None
            pause_idx = None

            for i, line in enumerate(lines):
                if "Raise Z for film insertion" in line:
                    z_raise_idx = i
                if "M0 ; Pause - Insert plastic sheets" in line:
                    pause_idx = i

            assert z_raise_idx is not None, "Z raise command not found"
            assert pause_idx is not None, "Pause command not found"
            assert z_raise_idx < pause_idx, "Z should be raised BEFORE pause"
        finally:
            os.chdir(original_dir)

    def test_no_film_pause_when_flag_not_set(
        self, simple_dxf_file, test_config, tmp_path
    ):
        """Test that film insertion pause is NOT included when -stop-for-film flag is not set."""
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            config = Config()

            points = process_weld_file(str(simple_dxf_file), config, is_frangible=False)
            output_gcode = tmp_path / "test_no_pause.gcode"

            class Args:
                verbose = False
                level_bed = False
                stop_for_film = False

            success = generate_gcode(points, str(output_gcode), config, Args())
            assert success

            gcode_content = output_gcode.read_text()

            # Verify no film insertion pause
            assert "M0 ; Pause - Insert plastic sheets" not in gcode_content
            assert "Insert plastic sheets" not in gcode_content
        finally:
            os.chdir(original_dir)

    def test_bed_leveling_without_film_pause(
        self, simple_dxf_file, test_config, tmp_path
    ):
        """Test bed leveling can be enabled without film pause."""
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            config = Config()

            points = process_weld_file(str(simple_dxf_file), config, is_frangible=False)
            output_gcode = tmp_path / "test_leveling_no_pause.gcode"

            class Args:
                verbose = False
                level_bed = True
                stop_for_film = False

            success = generate_gcode(points, str(output_gcode), config, Args())
            assert success

            gcode_content = output_gcode.read_text()

            # Verify bed leveling is included
            assert "G29 ; Auto bed leveling" in gcode_content

            # Verify no film pause
            assert "M0 ; Pause - Insert plastic sheets" not in gcode_content
        finally:
            os.chdir(original_dir)

    def test_default_film_insertion_height(
        self, simple_dxf_file, test_config, tmp_path
    ):
        """Test that default film_insertion_height (150mm) is used when not specified."""
        original_dir = os.getcwd()
        try:
            os.chdir(tmp_path)
            config = Config()

            points = process_weld_file(str(simple_dxf_file), config, is_frangible=False)
            output_gcode = tmp_path / "test_default_height.gcode"

            class Args:
                verbose = False
                level_bed = False
                stop_for_film = True

            success = generate_gcode(points, str(output_gcode), config, Args())
            assert success

            gcode_content = output_gcode.read_text()

            # Verify default Z height (150mm) is used
            # This ensures film insertion happens at a reasonable height for user access
            assert "G1 Z150.0 F3000 ; Raise Z for film insertion" in gcode_content
        finally:
            os.chdir(original_dir)
