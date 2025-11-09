"""Full integration tests for the complete DXF/SVG processing pipeline.

These tests ensure that the entire pipeline works end-to-end:
- File parsing (SVG/DXF)
- Event system processing
- Subscriber handling
- Output generation (G-code, Animation, PNG)

This prevents integration bugs that unit tests might miss.
"""

import pytest
import tempfile
from pathlib import Path
from typing import Any
import os

from microweldr.core.config import Config
from microweldr.core.event_processor import EventDrivenProcessor


class TestFullIntegrationPipeline:
    """Full integration tests for the complete processing pipeline."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return Config()

    @pytest.fixture
    def sample_svg_content(self):
        """Create sample SVG content for testing."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
    <rect x="10" y="10" width="80" height="80" stroke="red" fill="none"/>
    <circle cx="50" cy="50" r="15" stroke="blue" fill="none"/>
</svg>"""

    @pytest.fixture
    def sample_dxf_content(self):
        """Create sample DXF content for testing."""
        return """0
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
90.0
21
10.0
0
LINE
8
0
10
90.0
20
10.0
11
90.0
21
90.0
0
LINE
8
0
10
90.0
20
90.0
11
10.0
21
90.0
0
LINE
8
0
10
10.0
20
90.0
11
10.0
21
10.0
0
CIRCLE
8
0
10
50.0
20
50.0
40
15.0
0
ENDSEC
0
EOF
"""

    @pytest.fixture
    def temp_svg_file(self, sample_svg_content):
        """Create temporary SVG file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(sample_svg_content)
            return Path(f.name)

    @pytest.fixture
    def temp_dxf_file(self, sample_dxf_content):
        """Create temporary DXF file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".dxf", delete=False) as f:
            f.write(sample_dxf_content)
            return Path(f.name)

    def test_svg_full_pipeline_integration(self, config, temp_svg_file):
        """Test complete SVG processing pipeline end-to-end."""
        processor = EventDrivenProcessor(config, verbose=False)

        # Create output files
        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as gcode_file:
            gcode_path = Path(gcode_file.name)
        with tempfile.NamedTemporaryFile(
            suffix="_animation.svg", delete=False
        ) as anim_file:
            animation_path = Path(anim_file.name)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as png_file:
            png_path = Path(png_file.name)

        try:
            # Process file through complete pipeline
            success = processor.process_file(
                input_path=temp_svg_file,
                output_path=gcode_path,
                animation_path=animation_path,
                png_path=png_path,
                verbose=False,
            )

            # Verify processing succeeded
            assert success, "SVG processing pipeline should succeed"

            # Verify all output files were created
            assert gcode_path.exists(), "G-code file should be created"
            assert gcode_path.stat().st_size > 0, "G-code file should not be empty"

            # Verify G-code content structure
            gcode_content = gcode_path.read_text()
            assert any(
                cmd in gcode_content for cmd in ["G1", "G28", "M104"]
            ), "G-code should contain movement or heating commands"

            # Animation file should be created (if requested)
            if animation_path:
                assert animation_path.exists(), "Animation file should be created"
                assert (
                    animation_path.stat().st_size > 0
                ), "Animation file should not be empty"

                # Verify animation SVG content
                anim_content = animation_path.read_text()
                assert "<svg" in anim_content, "Animation should be valid SVG"

            # PNG file should be created (if requested)
            if png_path:
                assert png_path.exists(), "PNG file should be created"
                assert png_path.stat().st_size > 0, "PNG file should not be empty"

        finally:
            # Cleanup
            for path in [temp_svg_file, gcode_path, animation_path, png_path]:
                if path and path.exists():
                    path.unlink(missing_ok=True)

    @pytest.mark.skipif(
        not pytest.importorskip("ezdxf", reason="ezdxf not available"),
        reason="DXF support requires ezdxf",
    )
    def test_dxf_full_pipeline_integration(self, config, temp_dxf_file):
        """Test complete DXF processing pipeline end-to-end."""
        processor = EventDrivenProcessor(config, verbose=False)

        # Create output files
        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as gcode_file:
            gcode_path = Path(gcode_file.name)
        with tempfile.NamedTemporaryFile(
            suffix="_animation.svg", delete=False
        ) as anim_file:
            animation_path = Path(anim_file.name)

        try:
            # Process file through complete pipeline
            success = processor.process_file(
                input_path=temp_dxf_file,
                output_path=gcode_path,
                animation_path=animation_path,
                verbose=False,
            )

            # Verify processing succeeded
            assert success, "DXF processing pipeline should succeed"

            # Verify all output files were created
            assert gcode_path.exists(), "G-code file should be created"
            assert gcode_path.stat().st_size > 0, "G-code file should not be empty"

            # Verify G-code content structure
            gcode_content = gcode_path.read_text()
            assert any(
                cmd in gcode_content for cmd in ["G1", "G28", "M104"]
            ), "G-code should contain movement or heating commands"

            # Animation file should be created
            assert animation_path.exists(), "Animation file should be created"
            assert (
                animation_path.stat().st_size > 0
            ), "Animation file should not be empty"

            # Verify animation SVG content
            anim_content = animation_path.read_text()
            assert "<svg" in anim_content, "Animation should be valid SVG"

        except Exception as e:
            # If DXF processing fails, provide detailed error info
            pytest.fail(f"DXF pipeline integration failed: {e}")

        finally:
            # Cleanup
            for path in [temp_dxf_file, gcode_path, animation_path]:
                if path and path.exists():
                    path.unlink(missing_ok=True)

    def test_event_system_integration(self, config, temp_svg_file):
        """Test that the event system properly integrates with subscribers."""
        processor = EventDrivenProcessor(config, verbose=False)

        # Create output file
        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as gcode_file:
            gcode_path = Path(gcode_file.name)

        try:
            # Process file and capture any subscriber errors
            success = processor.process_file(
                input_path=temp_svg_file, output_path=gcode_path, verbose=False
            )

            # Should succeed without subscriber errors
            assert success, "Event system integration should work without errors"

            # Verify statistics were collected
            stats = processor.get_statistics()
            assert isinstance(stats, dict), "Statistics should be collected"
            assert (
                stats.get("paths_processed", 0) > 0
            ), "Should have processed some paths"

            # Verify validation results
            validation = processor.get_validation_results()
            assert isinstance(
                validation, dict
            ), "Validation results should be available"
            assert not validation.get(
                "has_errors", True
            ), "Should not have validation errors"

        finally:
            # Cleanup
            for path in [temp_svg_file, gcode_path]:
                if path and path.exists():
                    path.unlink(missing_ok=True)

    def test_model_compatibility_integration(self, config):
        """Test that different model types are properly converted and compatible."""
        processor = EventDrivenProcessor(config, verbose=False)

        # Test that the processor can handle both SVG and DXF model types
        extensions = processor.get_supported_input_extensions()
        assert ".svg" in extensions, "Should support SVG input"
        assert ".dxf" in extensions, "Should support DXF input"

        output_types = processor.get_supported_output_types()
        assert "gcode" in output_types, "Should support G-code output"
        assert "animation" in output_types, "Should support animation output"
        assert "png" in output_types, "Should support PNG output"

    def test_error_handling_integration(self, config):
        """Test that the pipeline handles errors gracefully."""
        processor = EventDrivenProcessor(config, verbose=False)

        # Test with non-existent file
        non_existent_file = Path("/tmp/non_existent_file.svg")
        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as gcode_file:
            gcode_path = Path(gcode_file.name)

        try:
            success = processor.process_file(
                input_path=non_existent_file, output_path=gcode_path, verbose=False
            )

            # Should fail gracefully
            assert not success, "Should fail for non-existent file"

        finally:
            # Cleanup
            if gcode_path.exists():
                gcode_path.unlink(missing_ok=True)

    def test_configuration_integration(self, config):
        """Test that configuration is properly integrated throughout the pipeline."""
        processor = EventDrivenProcessor(config, verbose=False)

        # Verify config is accessible
        assert processor.config is not None, "Processor should have config"

        # Verify config has required sections
        normal_welds = config.get("normal_welds", "dot_spacing")
        assert isinstance(normal_welds, (int, float)), "Should have numeric dot spacing"

        frangible_welds = config.get("frangible_welds", "dot_spacing")
        assert isinstance(
            frangible_welds, (int, float)
        ), "Should have frangible dot spacing"


class TestCLIIntegration:
    """Integration tests for CLI commands."""

    @pytest.fixture
    def sample_svg_file(self):
        """Create a sample SVG file for CLI testing."""
        content = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50">
    <rect x="10" y="10" width="30" height="30" stroke="red" fill="none"/>
</svg>"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(content)
            return Path(f.name)

    def test_cli_weld_command_integration(self, sample_svg_file):
        """Test that the CLI weld command works end-to-end."""
        # Import here to avoid circular imports
        from microweldr.cli.enhanced_weld_command import cmd_weld_enhanced
        from argparse import Namespace

        # Create output directory
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "output.gcode"

            # Create mock args
            args = Namespace(
                svg_file=str(sample_svg_file),
                output=str(output_path),
                no_animation=True,
                submit=False,
                auto_start=False,
                queue_only=False,
                verbose=False,
            )

            try:
                # Run the command
                success = cmd_weld_enhanced(args)

                # Should succeed
                assert success, "CLI weld command should succeed"

                # Output file should be created
                assert output_path.exists(), "Output G-code file should be created"
                assert output_path.stat().st_size > 0, "Output file should not be empty"

            finally:
                # Cleanup
                if sample_svg_file.exists():
                    sample_svg_file.unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
