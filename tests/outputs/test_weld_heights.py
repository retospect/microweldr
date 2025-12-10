"""Tests for weld height differentiation in G-code generation."""

import tempfile
from pathlib import Path
from unittest.mock import Mock
import pytest

from microweldr.core.config import Config
from microweldr.outputs.streaming_gcode_subscriber import StreamingGCodeSubscriber
from microweldr.core.events import PathEvent, Event, EventType


@pytest.fixture
def mock_config():
    """Create a mock config with test weld height values."""
    config = Mock(spec=Config)

    def config_get(section, key, default=None):
        config_values = {
            ("printer", "bed_size_x"): 250.0,
            ("printer", "bed_size_y"): 220.0,
            ("temperatures", "bed_temperature"): 45,
            ("temperatures", "nozzle_temperature"): 160,
            ("temperatures", "use_chamber_heating"): False,
            ("temperatures", "chamber_temperature"): 35,
            ("temperatures", "enable_cooldown"): False,
            ("temperatures", "cooldown_temperature"): 0,
            ("movement", "move_height"): 5.0,
            ("movement", "low_travel_height"): 1.5,
            ("movement", "travel_speed"): 3000,
            ("movement", "z_speed"): 3000,
            ("movement", "weld_compression_offset"): 0.0,
            ("movement", "film_insertion_height"): 150.0,
            # Test weld height values
            ("normal_welds", "weld_height"): 0.1,
            ("normal_welds", "weld_time"): 0.5,
            ("normal_welds", "weld_temperature"): 160,
            ("normal_welds", "dot_spacing"): 0.8,
            ("frangible_welds", "weld_height"): 0.35,
            ("frangible_welds", "weld_time"): 0.5,
            ("frangible_welds", "weld_temperature"): 160,
            ("frangible_welds", "dot_spacing"): 0.8,
            ("output", "gcode_extension"): ".gcode",
            ("sequencing", "passes"): 4,
        }
        return config_values.get((section, key), default)

    config.get.side_effect = config_get
    return config


class TestWeldHeights:
    """Test weld height differentiation between normal and frangible welds."""

    def test_normal_weld_height(self, mock_config):
        """Test that normal welds use correct height (0.1mm)."""
        config = mock_config

        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            subscriber = StreamingGCodeSubscriber(tmp_path, config)

            # Start processing
            start_event = Event(
                event_type=EventType.OUTPUT_GENERATION,
                timestamp=0.0,
                data={"action": "processing_start"},
                source="test",
            )
            subscriber.handle_event(start_event)

            # Start a path
            path_start = PathEvent(action="path_start", path_id="test_path")
            subscriber.handle_event(path_start)

            # Add a normal weld point
            point_event = PathEvent(
                action="point_added",
                path_id="test_path",
                point={"x": 10.0, "y": 20.0, "weld_type": "normal"},
            )
            subscriber.handle_event(point_event)

            # Complete path
            path_complete = PathEvent(action="path_complete", path_id="test_path")
            subscriber.handle_event(path_complete)

            # End processing
            end_event = Event(
                event_type=EventType.OUTPUT_GENERATION,
                timestamp=1.0,
                data={"action": "processing_complete"},
                source="test",
            )
            subscriber.handle_event(end_event)

            # Check G-code content
            with open(tmp_path, "r") as f:
                gcode_content = f.read()

            # Verify normal weld height (0.1mm)
            assert "G1 Z0.1 F3000 ; Lower to weld height" in gcode_content
            assert "G4 P500 ; Weld for 0.5s" in gcode_content

        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_frangible_weld_height(self, mock_config):
        """Test that frangible welds use correct height (0.35mm)."""
        config = mock_config

        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            subscriber = StreamingGCodeSubscriber(tmp_path, config)

            # Start processing
            start_event = Event(
                event_type=EventType.OUTPUT_GENERATION,
                timestamp=0.0,
                data={"action": "processing_start"},
                source="test",
            )
            subscriber.handle_event(start_event)

            # Start a path
            path_start = PathEvent(action="path_start", path_id="test_path")
            subscriber.handle_event(path_start)

            # Add a frangible weld point
            point_event = PathEvent(
                action="point_added",
                path_id="test_path",
                point={"x": 10.0, "y": 20.0, "weld_type": "frangible"},
            )
            subscriber.handle_event(point_event)

            # Complete path
            path_complete = PathEvent(action="path_complete", path_id="test_path")
            subscriber.handle_event(path_complete)

            # End processing
            end_event = Event(
                event_type=EventType.OUTPUT_GENERATION,
                timestamp=1.0,
                data={"action": "processing_complete"},
                source="test",
            )
            subscriber.handle_event(end_event)

            # Check G-code content
            with open(tmp_path, "r") as f:
                gcode_content = f.read()

            # Verify frangible weld height (0.35mm) and time (0.5s)
            assert "G1 Z0.35 F3000 ; Lower to frangible weld height" in gcode_content
            assert "G4 P500 ; Frangible weld for 0.5s" in gcode_content

        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_mixed_weld_types_heights(self, mock_config):
        """Test that mixed normal and frangible welds use correct heights."""
        config = mock_config

        with tempfile.NamedTemporaryFile(suffix=".gcode", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            subscriber = StreamingGCodeSubscriber(tmp_path, config)

            # Start processing
            start_event = Event(
                event_type=EventType.OUTPUT_GENERATION,
                timestamp=0.0,
                data={"action": "processing_start"},
                source="test",
            )
            subscriber.handle_event(start_event)

            # Process normal weld
            path_start1 = PathEvent(action="path_start", path_id="normal_path")
            subscriber.handle_event(path_start1)

            normal_point = PathEvent(
                action="point_added",
                path_id="normal_path",
                point={"x": 5.0, "y": 10.0, "weld_type": "normal"},
            )
            subscriber.handle_event(normal_point)

            path_complete1 = PathEvent(action="path_complete", path_id="normal_path")
            subscriber.handle_event(path_complete1)

            # Process frangible weld
            path_start2 = PathEvent(action="path_start", path_id="frangible_path")
            subscriber.handle_event(path_start2)

            frangible_point = PathEvent(
                action="point_added",
                path_id="frangible_path",
                point={"x": 15.0, "y": 25.0, "weld_type": "frangible"},
            )
            subscriber.handle_event(frangible_point)

            path_complete2 = PathEvent(action="path_complete", path_id="frangible_path")
            subscriber.handle_event(path_complete2)

            # End processing
            end_event = Event(
                event_type=EventType.OUTPUT_GENERATION,
                timestamp=2.0,
                data={"action": "processing_complete"},
                source="test",
            )
            subscriber.handle_event(end_event)

            # Check G-code content
            with open(tmp_path, "r") as f:
                gcode_content = f.read()

            # Verify both weld types have correct heights and times
            assert "G1 Z0.1 F3000 ; Lower to weld height" in gcode_content
            assert "G4 P500 ; Weld for 0.5s" in gcode_content
            assert "G1 Z0.35 F3000 ; Lower to frangible weld height" in gcode_content
            assert "G4 P500 ; Frangible weld for 0.5s" in gcode_content

            # Verify point counts
            normal_count = gcode_content.count("G1 Z0.1 F3000")
            frangible_count = gcode_content.count("G1 Z0.35 F3000")

            assert normal_count == 1, f"Expected 1 normal weld, got {normal_count}"
            assert (
                frangible_count == 1
            ), f"Expected 1 frangible weld, got {frangible_count}"

        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def test_weld_height_configuration_values(self, mock_config):
        """Test that configuration values match expected weld heights."""
        config = mock_config

        normal_height = config.get("normal_welds", "weld_height")
        frangible_height = config.get("frangible_welds", "weld_height")

        # Verify configuration values
        assert (
            normal_height == 0.1
        ), f"Expected normal weld height 0.1mm, got {normal_height}mm"
        assert (
            frangible_height == 0.35
        ), f"Expected frangible weld height 0.35mm, got {frangible_height}mm"

        # Verify weld times as well
        normal_time = config.get("normal_welds", "weld_time")
        frangible_time = config.get("frangible_welds", "weld_time")

        assert normal_time == 0.5, f"Expected normal weld time 0.5s, got {normal_time}s"
        assert (
            frangible_time == 0.5
        ), f"Expected frangible weld time 0.5s, got {frangible_time}s"
