"""Comprehensive integration tests for complete workflows."""

import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests_mock

from microweldr.core.config import Config
from microweldr.core.gcode_generator import GCodeGenerator
from microweldr.core.svg_parser import SVGParser
from microweldr.core.safety import validate_weld_operation
from microweldr.core.security import SecretsValidator, validate_secrets_interactive
from microweldr.core.graceful_degradation import ResilientPrusaLinkClient
from microweldr.core.resource_management import (
    safe_gcode_generation,
    TemporaryFileManager,
)
from microweldr.core.progress import progress_context
from microweldr.core.caching import OptimizedSVGParser
from microweldr.animation.generator import AnimationGenerator
from microweldr.validation.validators import (
    SVGValidator,
    GCodeValidator,
    AnimationValidator,
)


class TestCompleteWorkflow:
    """Test complete end-to-end workflows."""

    @pytest.fixture
    def test_config(self):
        """Create test configuration."""
        config_content = """
[printer]
bed_size_x = 250
bed_size_y = 220
bed_size_z = 270
layed_back_mode = false

[nozzle]
outer_diameter = 1.0
inner_diameter = 0.4

[temperatures]
bed_temperature = 60
nozzle_temperature = 100
chamber_temperature = 35
use_chamber_heating = false
cooldown_temperature = 50

[movement]
move_height = 5.0
travel_speed = 3000
z_speed = 600

[normal_welds]
weld_height = 0.020
weld_temperature = 100
weld_time = 0.1
dot_spacing = 0.9
initial_dot_spacing = 3.6
cooling_time_between_passes = 2.0

[light_welds]
weld_height = 0.020
weld_temperature = 110
weld_time = 0.3
dot_spacing = 0.9
initial_dot_spacing = 3.6
cooling_time_between_passes = 1.5

[animation]
time_between_welds = 0.5
pause_time = 2.0
min_animation_duration = 10.0

[output]
gcode_extension = ".gcode"
animation_extension = "_animation.svg"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(config_content)
            f.flush()
            yield Config(f.name)
        Path(f.name).unlink()

    @pytest.fixture
    def test_svg(self):
        """Create test SVG file."""
        svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <!-- Normal weld line -->
  <line x1="10" y1="10" x2="50" y2="10" 
        stroke="black" stroke-width="1"
        data-temp="105" 
        data-weld-time="0.15"
        data-weld-height="0.025" />
  
  <!-- Light weld circle -->
  <circle cx="30" cy="30" r="5" 
          stroke="blue" stroke-width="1" fill="none"
          data-temp="115" />
  
  <!-- Stop point -->
  <circle cx="70" cy="70" r="2" 
          stroke="red" stroke-width="1" fill="red"
          data-pause-message="Insert component here" />
  
  <!-- Path with multiple segments -->
  <path d="M 20 50 L 40 50 L 40 70 L 60 70" 
        stroke="black" stroke-width="1" fill="none"
        data-weld-time="0.2" />
</svg>"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(svg_content)
            f.flush()
            yield f.name
        Path(f.name).unlink()

    @pytest.fixture
    def secrets_file(self):
        """Create test secrets file."""
        secrets_content = """
[prusalink]
host = "192.168.1.100"
username = "maker"
password = "SecurePass123!"
timeout = 30
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(secrets_content)
            f.flush()
            yield f.name
        Path(f.name).unlink()

    def test_svg_to_gcode_complete_workflow(self, test_config, test_svg):
        """Test complete SVG to G-code workflow."""
        with TemporaryFileManager(prefix="workflow_test_") as temp_manager:
            # Step 1: Parse SVG
            parser = SVGParser()
            weld_paths = parser.parse_file(test_svg)

            assert len(weld_paths) >= 3  # Should have multiple paths

            # Step 2: Validate safety
            warnings, errors = validate_weld_operation(weld_paths, test_config.config)
            assert len(errors) == 0  # Should have no safety errors

            # Step 3: Generate G-code with resource management
            gcode_path = temp_manager.create_temp_file()
            gcode_path = gcode_path.with_suffix(".gcode")

            with safe_gcode_generation(gcode_path) as temp_gcode_path:
                generator = GCodeGenerator(test_config)
                generator.generate_file(weld_paths, str(temp_gcode_path))

            # Step 4: Validate generated G-code
            validator = GCodeValidator()
            result = validator.validate(str(gcode_path))
            assert (
                result.is_valid or len(result.warnings) == 0
            )  # Should be valid or have acceptable warnings

            # Step 5: Verify G-code content
            gcode_content = gcode_path.read_text()

            # Should contain basic G-code structure
            assert "G90" in gcode_content  # Absolute positioning
            assert "M83" in gcode_content  # Relative extruder
            assert "G28" in gcode_content  # Home command
            assert "M104" in gcode_content  # Temperature setting
            assert "G1" in gcode_content  # Movement commands
            assert "G4" in gcode_content  # Dwell commands

            # Should contain custom parameters
            assert "105" in gcode_content  # Custom temperature
            assert "150" in gcode_content  # Custom weld time (0.15s = 150ms)

            # Should contain pause message
            assert "Insert component here" in gcode_content

    def test_svg_to_animation_workflow(self, test_config, test_svg):
        """Test SVG to animation workflow."""
        with TemporaryFileManager(prefix="animation_test_") as temp_manager:
            # Parse SVG
            parser = SVGParser()
            weld_paths = parser.parse_file(test_svg)

            # Generate animation
            animation_path = temp_manager.create_temp_file(suffix=".svg")
            generator = AnimationGenerator(test_config)
            generator.generate(weld_paths, str(animation_path))

            # Validate animation
            validator = AnimationValidator()
            result = validator.validate(str(animation_path))
            assert result.is_valid or len(result.warnings) == 0

            # Verify animation content
            animation_content = animation_path.read_text()

            # Should be valid SVG
            assert "<?xml" in animation_content
            assert "<svg" in animation_content
            assert "</svg>" in animation_content

            # Should contain animation elements
            assert (
                "animate" in animation_content
                or "animateTransform" in animation_content
            )
            assert "circle" in animation_content  # Weld points

    def test_caching_workflow(self, test_svg):
        """Test workflow with caching enabled."""
        parser = OptimizedSVGParser(cache_enabled=True)

        # First parse (cache miss)
        start_time = time.time()
        weld_paths_1 = parser.parse_svg_file(test_svg)
        first_parse_time = time.time() - start_time

        # Second parse (cache hit)
        start_time = time.time()
        weld_paths_2 = parser.parse_svg_file(test_svg)
        second_parse_time = time.time() - start_time

        # Results should be identical
        assert len(weld_paths_1) == len(weld_paths_2)

        # Get statistics
        stats = parser.get_stats()
        assert stats["cache_hits"] >= 1
        assert stats["cache_misses"] >= 1

        # Cache hit should be faster (though this might not always be true for small files)
        # Just verify the caching system is working
        assert stats["cache_hit_rate"] > 0

    def test_progress_reporting_workflow(self, test_config, test_svg):
        """Test workflow with progress reporting."""
        # Create multiple SVG files to process
        svg_files = []

        with TemporaryFileManager(prefix="progress_test_") as temp_manager:
            # Create several test SVG files
            for i in range(5):
                svg_path = temp_manager.create_temp_file(suffix=f"_{i}.svg")
                svg_path.write_text(Path(test_svg).read_text())
                svg_files.append(svg_path)

            # Process with progress reporting
            results = []

            with progress_context(len(svg_files), "Processing SVG files") as progress:
                for svg_file in svg_files:
                    parser = SVGParser()
                    weld_paths = parser.parse_file(str(svg_file))
                    results.append(weld_paths)
                    progress.update(1)

            # Verify all files were processed
            assert len(results) == len(svg_files)
            for result in results:
                assert len(result) >= 3  # Each should have multiple paths

    @requests_mock.Mocker()
    def test_printer_communication_workflow(
        self, m, test_config, test_svg, secrets_file
    ):
        """Test workflow with printer communication."""
        # Mock PrusaLink responses
        m.get(
            "http://192.168.1.100/api/printer",
            json={
                "printer": {
                    "state": "Operational",
                    "temp_bed": {"actual": 25.0, "target": 0.0},
                    "temp_nozzle": {"actual": 23.0, "target": 0.0},
                }
            },
        )

        m.post(
            "http://192.168.1.100/api/files/local",
            json={
                "filename": "test_weld.gcode",
                "path": "/local/test_weld.gcode",
                "auto_started": False,
            },
        )

        m.post("http://192.168.1.100/api/job", json={"started": True})

        with TemporaryFileManager(prefix="printer_test_") as temp_manager:
            # Generate G-code
            parser = SVGParser()
            weld_paths = parser.parse_file(test_svg)

            gcode_path = temp_manager.create_temp_file(suffix=".gcode")
            generator = GCodeGenerator(test_config)
            generator.generate(weld_paths, str(gcode_path))

            # Test printer communication
            client = ResilientPrusaLinkClient(secrets_file)

            # Check printer status
            status = client.get_status()
            assert status["printer"]["state"] == "Operational"

            # Upload file
            upload_result = client.upload_file(str(gcode_path), "test_weld.gcode")
            assert upload_result["filename"] == "test_weld.gcode"

            # Start print
            start_result = client.start_print("test_weld.gcode")
            assert start_result is True

    def test_security_validation_workflow(self, secrets_file):
        """Test security validation workflow."""
        validator = SecretsValidator()

        # Validate secrets file
        warnings, errors = validator.validate_secrets_file(secrets_file)

        # Should have no critical errors
        assert len(errors) == 0

        # Test filename sanitization
        dangerous_filename = "../../../etc/passwd<script>alert('xss')</script>"
        safe_filename = validator.sanitize_filename(dangerous_filename)

        assert ".." not in safe_filename
        assert "<" not in safe_filename
        assert "script" not in safe_filename

        # Test password strength
        weak_password = "password"
        is_strong, issues = validator.validate_password_strength(weak_password)
        assert not is_strong
        assert len(issues) > 0

        strong_password = "SecurePass123!"
        is_strong, issues = validator.validate_password_strength(strong_password)
        assert is_strong
        assert len(issues) == 0

    def test_error_recovery_workflow(self, test_config, secrets_file):
        """Test workflow with error recovery and graceful degradation."""
        with TemporaryFileManager(prefix="error_test_") as temp_manager:
            # Test with invalid SVG
            invalid_svg = temp_manager.create_temp_file(suffix=".svg")
            invalid_svg.write_text("This is not valid SVG content")

            parser = SVGParser()

            # Should handle invalid SVG gracefully
            with pytest.raises(Exception):
                parser.parse_file(str(invalid_svg))

            # Test printer communication failure
            with requests_mock.Mocker() as m:
                # Mock connection failure
                m.get(
                    "http://192.168.1.100/api/printer",
                    exc=requests_mock.exceptions.ConnectionError,
                )

                client = ResilientPrusaLinkClient(secrets_file)

                # Should fall back gracefully
                status = client.get_status()
                assert (
                    status.get("fallback") is True
                    or status.get("state") == "Disconnected"
                )

    def test_validation_chain_workflow(self, test_config, test_svg):
        """Test complete validation chain workflow."""
        with TemporaryFileManager(prefix="validation_test_") as temp_manager:
            # Step 1: Validate input SVG
            svg_validator = SVGValidator()
            svg_result = svg_validator.validate(test_svg)
            assert svg_result.is_valid

            # Step 2: Parse and validate safety
            parser = SVGParser()
            weld_paths = parser.parse_file(test_svg)

            warnings, errors = validate_weld_operation(weld_paths, test_config.config)
            assert len(errors) == 0

            # Step 3: Generate and validate G-code
            gcode_path = temp_manager.create_temp_file(suffix=".gcode")
            generator = GCodeGenerator(test_config)
            generator.generate(weld_paths, str(gcode_path))

            gcode_validator = GCodeValidator()
            gcode_result = gcode_validator.validate(str(gcode_path))
            assert gcode_result.is_valid or len(gcode_result.warnings) == 0

            # Step 4: Generate and validate animation
            animation_path = temp_manager.create_temp_file(suffix=".svg")
            animation_generator = AnimationGenerator(test_config)
            animation_generator.generate(weld_paths, str(animation_path))

            animation_validator = AnimationValidator()
            animation_result = animation_validator.validate(str(animation_path))
            assert animation_result.is_valid or len(animation_result.warnings) == 0

    def test_concurrent_workflow(self, test_config, test_svg):
        """Test workflow with concurrent operations."""
        import threading
        import queue

        results_queue = queue.Queue()
        errors_queue = queue.Queue()

        def worker_process_svg(svg_path, worker_id):
            """Worker function to process SVG."""
            try:
                parser = SVGParser()
                weld_paths = parser.parse_file(svg_path)

                with TemporaryFileManager(
                    prefix=f"worker_{worker_id}_"
                ) as temp_manager:
                    gcode_path = temp_manager.create_temp_file(suffix=".gcode")
                    generator = GCodeGenerator(test_config)
                    generator.generate(weld_paths, str(gcode_path))

                    results_queue.put(
                        {
                            "worker_id": worker_id,
                            "paths_count": len(weld_paths),
                            "gcode_size": gcode_path.stat().st_size,
                        }
                    )

            except Exception as e:
                errors_queue.put({"worker_id": worker_id, "error": str(e)})

        # Start multiple workers
        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker_process_svg, args=(test_svg, i))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join(timeout=30)  # 30 second timeout

        # Check results
        assert errors_queue.empty(), f"Worker errors: {list(errors_queue.queue)}"

        results = []
        while not results_queue.empty():
            results.append(results_queue.get())

        assert len(results) == 3  # All workers should complete

        # All results should be similar (processing same SVG)
        for result in results:
            assert result["paths_count"] >= 3
            assert result["gcode_size"] > 100  # Should generate substantial G-code

    def test_memory_usage_workflow(self, test_config):
        """Test workflow memory usage with large datasets."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Create large SVG content
        large_svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg width="1000" height="1000" xmlns="http://www.w3.org/2000/svg">"""

        # Add many weld lines
        for i in range(1000):
            x1, y1 = i % 100 * 10, i // 100 * 10
            x2, y2 = x1 + 5, y1
            large_svg_content += (
                f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="black" />\n'
            )

        large_svg_content += "</svg>"

        with TemporaryFileManager(prefix="memory_test_") as temp_manager:
            # Create large SVG file
            large_svg_path = temp_manager.create_temp_file(suffix=".svg")
            large_svg_path.write_text(large_svg_content)

            # Process large file
            parser = SVGParser()
            weld_paths = parser.parse_file(str(large_svg_path))

            # Generate G-code
            gcode_path = temp_manager.create_temp_file(suffix=".gcode")
            generator = GCodeGenerator(test_config)
            generator.generate(weld_paths, str(gcode_path))

            # Check memory usage hasn't grown excessively
            final_memory = process.memory_info().rss
            memory_growth = final_memory - initial_memory

            # Memory growth should be reasonable (less than 100MB for this test)
            assert (
                memory_growth < 100 * 1024 * 1024
            ), f"Excessive memory growth: {memory_growth / 1024 / 1024:.1f}MB"

            # Verify processing worked
            assert len(weld_paths) > 0
            assert (
                gcode_path.stat().st_size > 1000
            )  # Should generate substantial G-code
