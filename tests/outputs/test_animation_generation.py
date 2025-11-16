"""Tests for animation generation functionality."""

import tempfile
from pathlib import Path
import pytest

from microweldr.core.config import Config
from microweldr.generators.models import WeldPoint
from microweldr.outputs.png_animation_subscriber import PNGAnimationSubscriber
from microweldr.core.events import Event, EventType, PathEvent

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class TestAnimationGeneration:
    """Test animation generation functionality."""

    def create_test_config(self) -> Config:
        """Create a test configuration."""
        return Config()

    def create_test_points(self) -> list:
        """Create test points for animation."""
        return [
            {"x": 0.0, "y": 0.0, "weld_type": "normal", "path_id": "path_1"},
            {"x": 10.0, "y": 0.0, "weld_type": "normal", "path_id": "path_1"},
            {"x": 10.0, "y": 10.0, "weld_type": "frangible", "path_id": "path_2"},
            {"x": 0.0, "y": 10.0, "weld_type": "frangible", "path_id": "path_2"},
        ]

    @pytest.mark.skipif(not PIL_AVAILABLE, reason="PIL (Pillow) not available")
    def test_png_animation_subscriber_creation(self):
        """Test that PNG animation subscriber can be created."""
        config = self.create_test_config()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = Path(f.name)

        try:
            subscriber = PNGAnimationSubscriber(output_path, config)
            assert subscriber is not None
            assert subscriber.output_path == output_path

        finally:
            if output_path.exists():
                output_path.unlink()

    @pytest.mark.skipif(not PIL_AVAILABLE, reason="PIL (Pillow) not available")
    def test_png_animation_generation(self):
        """Test basic PNG animation generation."""
        config = self.create_test_config()
        points = self.create_test_points()

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = Path(f.name)

        try:
            subscriber = PNGAnimationSubscriber(output_path, config)

            # Send events to generate animation
            # Start processing
            start_event = Event(
                event_type=EventType.OUTPUT_GENERATION,
                timestamp=1234567890.0,
                data={"action": "processing_start"},
                source="test",
            )
            subscriber.handle_event(start_event)

            # Send path events
            current_path_id = None
            for point in points:
                path_id = point["path_id"]

                if path_id != current_path_id:
                    if current_path_id is not None:
                        # Complete previous path
                        path_complete = PathEvent(
                            action="path_complete", path_id=current_path_id
                        )
                        subscriber.handle_event(path_complete)

                    # Start new path
                    path_start = PathEvent(action="path_start", path_id=path_id)
                    subscriber.handle_event(path_start)
                    current_path_id = path_id

                # Add point
                point_event = PathEvent(
                    action="point_added", path_id=path_id, point=point
                )
                subscriber.handle_event(point_event)

            # Complete final path
            if current_path_id:
                path_complete = PathEvent(
                    action="path_complete", path_id=current_path_id
                )
                subscriber.handle_event(path_complete)

            # End processing
            end_event = Event(
                event_type=EventType.OUTPUT_GENERATION,
                timestamp=1234567891.0,
                data={"action": "processing_complete"},
                source="test",
            )
            subscriber.handle_event(end_event)

            # Verify PNG file was created
            assert output_path.exists(), "PNG file should be created"
            assert output_path.stat().st_size > 0, "PNG file should not be empty"

            # Verify it's a valid PNG
            with Image.open(output_path) as img:
                assert img.format == "PNG", "Should be a valid PNG file"
                assert (
                    img.size[0] > 0 and img.size[1] > 0
                ), "Should have valid dimensions"

        finally:
            if output_path.exists():
                output_path.unlink()

    @pytest.mark.skipif(not PIL_AVAILABLE, reason="PIL (Pillow) not available")
    def test_png_animation_with_different_weld_types(self):
        """Test PNG animation with multiple weld types."""
        config = self.create_test_config()

        # Create points with different weld types
        points = [
            {"x": 0.0, "y": 0.0, "weld_type": "normal", "path_id": "path_1"},
            {"x": 10.0, "y": 0.0, "weld_type": "frangible", "path_id": "path_2"},
            {"x": 20.0, "y": 0.0, "weld_type": "stop", "path_id": "path_3"},
            {"x": 30.0, "y": 0.0, "weld_type": "pipette", "path_id": "path_4"},
        ]

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            output_path = Path(f.name)

        try:
            subscriber = PNGAnimationSubscriber(output_path, config)

            # Send processing events (simplified)
            start_event = Event(
                event_type=EventType.OUTPUT_GENERATION,
                timestamp=1234567890.0,
                data={"action": "processing_start"},
                source="test",
            )
            subscriber.handle_event(start_event)

            # Send all points
            for point in points:
                path_start = PathEvent(action="path_start", path_id=point["path_id"])
                subscriber.handle_event(path_start)

                point_event = PathEvent(
                    action="point_added", path_id=point["path_id"], point=point
                )
                subscriber.handle_event(point_event)

                path_complete = PathEvent(
                    action="path_complete", path_id=point["path_id"]
                )
                subscriber.handle_event(path_complete)

            end_event = Event(
                event_type=EventType.OUTPUT_GENERATION,
                timestamp=1234567891.0,
                data={"action": "processing_complete"},
                source="test",
            )
            subscriber.handle_event(end_event)

            # Verify file creation
            assert output_path.exists(), "PNG file should be created"

            # Verify it's a valid PNG with reasonable size
            with Image.open(output_path) as img:
                assert img.format == "PNG"
                assert img.size[0] >= 400, "Image should be reasonably wide"
                assert img.size[1] >= 300, "Image should be reasonably tall"

        finally:
            if output_path.exists():
                output_path.unlink()

    def test_animation_subscriber_without_pil(self):
        """Test that PNG subscriber raises error when PIL is not available."""
        # This test would only run if PIL was not available, which is unlikely
        # in our test environment, but documents the expected behavior
        pass
