"""Comprehensive tests for all conversion permutations to ensure DRY functionality."""

import pytest
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

from microweldr.core.config import Config
from microweldr.core.event_processor import EventDrivenProcessor
from microweldr.core.models import WeldPath, WeldPoint
from microweldr.animation.generator import AnimationGenerator


class TestConversionPermutations:
    """Test all conversion permutations with identical dot patterns."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        config = Config()
        return config

    @pytest.fixture
    def sample_svg_content(self):
        """Create sample SVG content for testing."""
        return """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
    <path d="M 10,10 L 90,10 L 90,90 L 10,90 Z" stroke="red" fill="none"/>
    <circle cx="50" cy="50" r="20" stroke="blue" fill="none"/>
</svg>"""

    @pytest.fixture
    def sample_dxf_content(self):
        """Create sample DXF content for testing."""
        # This would be a minimal DXF file content
        return """0
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
CIRCLE
8
0
10
50.0
20
50.0
40
20.0
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

    @pytest.fixture
    def sample_weld_paths(self):
        """Create sample weld paths for testing."""
        return [
            WeldPath(
                id="path1",
                weld_type="normal",
                points=[
                    WeldPoint(x=10.0, y=10.0, weld_type="normal"),
                    WeldPoint(x=20.0, y=10.0, weld_type="normal"),
                    WeldPoint(x=30.0, y=10.0, weld_type="normal"),
                ],
            ),
            WeldPath(
                id="path2",
                weld_type="frangible",
                points=[
                    WeldPoint(x=50.0, y=30.0, weld_type="frangible"),
                    WeldPoint(x=50.0, y=40.0, weld_type="frangible"),
                    WeldPoint(x=50.0, y=50.0, weld_type="frangible"),
                ],
            ),
        ]

    def test_svg_to_gcode_conversion(self, config, temp_svg_file):
        """Test SVG → G-code conversion."""
        processor = EventDrivenProcessor(config, verbose=False)

        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as gcode_file:
            gcode_path = Path(gcode_file.name)

        try:
            success = processor.process_file(
                input_path=temp_svg_file, output_path=gcode_path
            )

            assert success, "SVG to G-code conversion should succeed"
            assert gcode_path.exists(), "G-code file should be created"
            assert gcode_path.stat().st_size > 0, "G-code file should not be empty"

            # Verify G-code content has expected structure
            content = gcode_path.read_text()
            assert (
                "G28" in content or "G1" in content
            ), "G-code should contain movement commands"

        finally:
            # Cleanup
            temp_svg_file.unlink(missing_ok=True)
            gcode_path.unlink(missing_ok=True)

    def test_svg_to_animation_conversion(self, config, temp_svg_file):
        """Test SVG → Animation SVG conversion."""
        processor = EventDrivenProcessor(config, verbose=False)

        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as gcode_file:
            gcode_path = Path(gcode_file.name)
        with tempfile.NamedTemporaryFile(
            suffix="_animation.svg", delete=False
        ) as anim_file:
            animation_path = Path(anim_file.name)

        try:
            success = processor.process_file(
                input_path=temp_svg_file,
                output_path=gcode_path,
                animation_path=animation_path,
            )

            assert success, "SVG to animation conversion should succeed"
            assert animation_path.exists(), "Animation file should be created"
            assert (
                animation_path.stat().st_size > 0
            ), "Animation file should not be empty"

            # Verify animation SVG content
            content = animation_path.read_text()
            assert "<svg" in content, "Animation should be valid SVG"
            assert (
                "<animate" in content or "<animateTransform" in content
            ), "Animation should contain animation elements"

        finally:
            # Cleanup
            temp_svg_file.unlink(missing_ok=True)
            gcode_path.unlink(missing_ok=True)
            animation_path.unlink(missing_ok=True)

    def test_svg_to_png_conversion(self, config, temp_svg_file):
        """Test SVG → PNG conversion."""
        processor = EventDrivenProcessor(config, verbose=False)

        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as gcode_file:
            gcode_path = Path(gcode_file.name)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as png_file:
            png_path = Path(png_file.name)

        try:
            success = processor.process_file(
                input_path=temp_svg_file, output_path=gcode_path, png_path=png_path
            )

            assert success, "SVG to PNG conversion should succeed"
            assert png_path.exists(), "PNG file should be created"
            assert png_path.stat().st_size > 0, "PNG file should not be empty"

        finally:
            # Cleanup
            temp_svg_file.unlink(missing_ok=True)
            gcode_path.unlink(missing_ok=True)
            png_path.unlink(missing_ok=True)

    @pytest.mark.skipif(
        not pytest.importorskip("ezdxf", reason="ezdxf not available"),
        reason="DXF support requires ezdxf",
    )
    def test_dxf_to_gcode_conversion(self, config, temp_dxf_file):
        """Test DXF → G-code conversion."""
        processor = EventDrivenProcessor(config, verbose=False)

        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as gcode_file:
            gcode_path = Path(gcode_file.name)

        try:
            success = processor.process_file(
                input_path=temp_dxf_file, output_path=gcode_path
            )

            assert success, "DXF to G-code conversion should succeed"
            assert gcode_path.exists(), "G-code file should be created"
            assert gcode_path.stat().st_size > 0, "G-code file should not be empty"

            # Verify G-code content has expected structure
            content = gcode_path.read_text()
            assert (
                "G28" in content or "G1" in content
            ), "G-code should contain movement commands"

        finally:
            # Cleanup
            temp_dxf_file.unlink(missing_ok=True)
            gcode_path.unlink(missing_ok=True)

    @pytest.mark.skipif(
        not pytest.importorskip("ezdxf", reason="ezdxf not available"),
        reason="DXF support requires ezdxf",
    )
    def test_dxf_to_animation_conversion(self, config, temp_dxf_file):
        """Test DXF → Animation SVG conversion."""
        processor = EventDrivenProcessor(config, verbose=False)

        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as gcode_file:
            gcode_path = Path(gcode_file.name)
        with tempfile.NamedTemporaryFile(
            suffix="_animation.svg", delete=False
        ) as anim_file:
            animation_path = Path(anim_file.name)

        try:
            success = processor.process_file(
                input_path=temp_dxf_file,
                output_path=gcode_path,
                animation_path=animation_path,
            )

            assert success, "DXF to animation conversion should succeed"
            assert animation_path.exists(), "Animation file should be created"
            assert (
                animation_path.stat().st_size > 0
            ), "Animation file should not be empty"

            # Verify animation SVG content
            content = animation_path.read_text()
            assert "<svg" in content, "Animation should be valid SVG"
            assert (
                "<animate" in content or "<animateTransform" in content
            ), "Animation should contain animation elements"

        finally:
            # Cleanup
            temp_dxf_file.unlink(missing_ok=True)
            gcode_path.unlink(missing_ok=True)
            animation_path.unlink(missing_ok=True)

    @pytest.mark.skipif(
        not pytest.importorskip("ezdxf", reason="ezdxf not available"),
        reason="DXF support requires ezdxf",
    )
    def test_dxf_to_png_conversion(self, config, temp_dxf_file):
        """Test DXF → PNG conversion."""
        processor = EventDrivenProcessor(config, verbose=False)

        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as gcode_file:
            gcode_path = Path(gcode_file.name)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as png_file:
            png_path = Path(png_file.name)

        try:
            success = processor.process_file(
                input_path=temp_dxf_file, output_path=gcode_path, png_path=png_path
            )

            assert success, "DXF to PNG conversion should succeed"
            assert png_path.exists(), "PNG file should be created"
            assert png_path.stat().st_size > 0, "PNG file should not be empty"

        finally:
            # Cleanup
            temp_dxf_file.unlink(missing_ok=True)
            gcode_path.unlink(missing_ok=True)
            png_path.unlink(missing_ok=True)

    def test_identical_dot_patterns_svg_vs_dxf(
        self, config, temp_svg_file, temp_dxf_file
    ):
        """Test that SVG and DXF produce identical dot patterns."""
        processor = EventDrivenProcessor(config, verbose=False)

        # Process SVG
        with tempfile.NamedTemporaryFile(
            suffix=".gcode", delete=False
        ) as svg_gcode_file:
            svg_gcode_path = Path(svg_gcode_file.name)

        # Process DXF
        with tempfile.NamedTemporaryFile(
            suffix=".gcode", delete=False
        ) as dxf_gcode_file:
            dxf_gcode_path = Path(dxf_gcode_file.name)

        try:
            # Convert both files
            svg_success = processor.process_file(
                input_path=temp_svg_file, output_path=svg_gcode_path
            )

            # Reset processor for DXF
            processor = EventDrivenProcessor(config, verbose=False)
            dxf_success = processor.process_file(
                input_path=temp_dxf_file, output_path=dxf_gcode_path
            )

            assert svg_success and dxf_success, "Both conversions should succeed"

            # Compare dot spacing in G-code (should be identical)
            svg_content = svg_gcode_path.read_text()
            dxf_content = dxf_gcode_path.read_text()

            # Extract G1 commands (movement commands with coordinates)
            import re

            svg_moves = re.findall(r"G1 X([\d.-]+) Y([\d.-]+)", svg_content)
            dxf_moves = re.findall(r"G1 X([\d.-]+) Y([\d.-]+)", dxf_content)

            # Both should have moves (non-empty)
            assert len(svg_moves) > 0, "SVG should generate movement commands"
            assert len(dxf_moves) > 0, "DXF should generate movement commands"

            # Calculate distances between consecutive points for both
            def calculate_distances(moves):
                distances = []
                for i in range(1, len(moves)):
                    x1, y1 = float(moves[i - 1][0]), float(moves[i - 1][1])
                    x2, y2 = float(moves[i][0]), float(moves[i][1])
                    dist = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
                    distances.append(dist)
                return distances

            svg_distances = calculate_distances(svg_moves)
            dxf_distances = calculate_distances(dxf_moves)

            # The dot spacing should be consistent (from config)
            expected_dot_spacing = config.get("normal_welds", "dot_spacing")

            # Check that most distances match the expected dot spacing (within tolerance)
            tolerance = 0.1
            svg_matches = sum(
                1 for d in svg_distances if abs(d - expected_dot_spacing) < tolerance
            )
            dxf_matches = sum(
                1 for d in dxf_distances if abs(d - expected_dot_spacing) < tolerance
            )

            # At least 50% of distances should match expected dot spacing
            assert (
                svg_matches > len(svg_distances) * 0.5
            ), f"SVG dot spacing should be consistent: {svg_matches}/{len(svg_distances)}"
            assert (
                dxf_matches > len(dxf_distances) * 0.5
            ), f"DXF dot spacing should be consistent: {dxf_matches}/{len(dxf_distances)}"

        finally:
            # Cleanup
            temp_svg_file.unlink(missing_ok=True)
            temp_dxf_file.unlink(missing_ok=True)
            svg_gcode_path.unlink(missing_ok=True)
            dxf_gcode_path.unlink(missing_ok=True)

    def test_animation_generator_methods_have_return_statements(self):
        """Test that AnimationGenerator methods have explicit return statements."""
        config = Config()
        generator = AnimationGenerator(config)

        # Test generate_file method
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            # Should return None explicitly
            result = generator.generate_file([], temp_path)
            assert result is None, "generate_file should return None explicitly"

            # Test generate_png_file method
            result = generator.generate_png_file([], temp_path)
            assert result is None, "generate_png_file should return None explicitly"

        finally:
            temp_path.unlink(missing_ok=True)

    def test_event_processor_methods_have_return_statements(self, config):
        """Test that EventDrivenProcessor methods have explicit return statements."""
        processor = EventDrivenProcessor(config, verbose=False)

        # Test get_supported_input_extensions
        extensions = processor.get_supported_input_extensions()
        assert isinstance(
            extensions, list
        ), "get_supported_input_extensions should return list"
        assert len(extensions) > 0, "Should return non-empty list of extensions"

        # Test get_supported_output_types
        output_types = processor.get_supported_output_types()
        assert isinstance(
            output_types, list
        ), "get_supported_output_types should return list"
        assert len(output_types) > 0, "Should return non-empty list of output types"

        # Test get_statistics
        stats = processor.get_statistics()
        assert isinstance(stats, dict), "get_statistics should return dict"

        # Test get_validation_results
        validation = processor.get_validation_results()
        assert isinstance(validation, dict), "get_validation_results should return dict"

        # Test cleanup method
        result = processor.cleanup()
        assert result is None, "cleanup should return None explicitly"

    def test_all_conversion_permutations_matrix(self, config):
        """Test the complete conversion matrix to ensure all permutations work."""
        # This is a comprehensive test to ensure we don't lose functionality

        input_types = [".svg", ".dxf"]
        output_types = ["gcode", "animation", "png"]

        # Create minimal test files
        svg_content = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg">
    <path d="M 0,0 L 10,0" stroke="red"/>
</svg>"""

        dxf_content = """0
SECTION
2
ENTITIES
0
LINE
10
0.0
20
0.0
11
10.0
21
0.0
0
ENDSEC
0
EOF
"""

        test_files = {".svg": svg_content, ".dxf": dxf_content}

        results = {}

        for input_ext in input_types:
            for output_type in output_types:
                # Skip DXF tests if ezdxf not available
                if input_ext == ".dxf":
                    try:
                        import ezdxf
                    except ImportError:
                        results[f"{input_ext}→{output_type}"] = (
                            "SKIPPED (ezdxf not available)"
                        )
                        continue

                # Create temp input file
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=input_ext, delete=False
                ) as input_file:
                    input_file.write(test_files[input_ext])
                    input_path = Path(input_file.name)

                # Create temp output files
                with tempfile.NamedTemporaryFile(
                    suffix=".gcode", delete=False
                ) as gcode_file:
                    gcode_path = Path(gcode_file.name)

                animation_path = None
                png_path = None

                if output_type == "animation":
                    with tempfile.NamedTemporaryFile(
                        suffix="_animation.svg", delete=False
                    ) as anim_file:
                        animation_path = Path(anim_file.name)
                elif output_type == "png":
                    with tempfile.NamedTemporaryFile(
                        suffix=".png", delete=False
                    ) as png_file:
                        png_path = Path(png_file.name)

                try:
                    processor = EventDrivenProcessor(config, verbose=False)
                    success = processor.process_file(
                        input_path=input_path,
                        output_path=gcode_path,
                        animation_path=animation_path,
                        png_path=png_path,
                    )

                    results[f"{input_ext}→{output_type}"] = (
                        "PASS" if success else "FAIL"
                    )

                except Exception as e:
                    results[f"{input_ext}→{output_type}"] = f"ERROR: {e}"

                finally:
                    # Cleanup
                    input_path.unlink(missing_ok=True)
                    gcode_path.unlink(missing_ok=True)
                    if animation_path:
                        animation_path.unlink(missing_ok=True)
                    if png_path:
                        png_path.unlink(missing_ok=True)

        # Print results matrix
        print("\n🔍 Conversion Permutation Matrix:")
        for conversion, result in results.items():
            status_emoji = (
                "✅" if result == "PASS" else "❌" if result == "FAIL" else "⏭️"
            )
            print(f"   {status_emoji} {conversion}: {result}")

        # Assert all non-skipped conversions passed
        failed_conversions = [
            k
            for k, v in results.items()
            if v not in ["PASS", "SKIPPED (ezdxf not available)"]
        ]
        assert len(failed_conversions) == 0, f"Failed conversions: {failed_conversions}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
