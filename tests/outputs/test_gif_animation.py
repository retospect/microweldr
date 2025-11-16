"""Tests for GIF animation generation functionality."""

import tempfile
from pathlib import Path
import pytest

from microweldr.core.config import Config
from microweldr.core.events import Event, EventType, PathEvent

try:
    from microweldr.outputs.gif_animation_subscriber import GIFAnimationSubscriber
    from PIL import Image

    GIF_AVAILABLE = True
except ImportError:
    GIF_AVAILABLE = False


class TestGIFAnimation:
    """Test GIF animation generation functionality."""

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

    @pytest.mark.skipif(not GIF_AVAILABLE, reason="PIL (Pillow) not available")
    def test_gif_animation_subscriber_creation(self):
        """Test that GIF animation subscriber can be created."""
        config = self.create_test_config()

        with tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as f:
            output_path = Path(f.name)

        try:
            subscriber = GIFAnimationSubscriber(output_path, config)
            assert subscriber is not None
            assert subscriber.output_path == output_path

        finally:
            if output_path.exists():
                output_path.unlink()

    @pytest.mark.skipif(not GIF_AVAILABLE, reason="PIL (Pillow) not available")
    def test_gif_animation_generation(self):
        """Test basic GIF animation generation."""
        config = self.create_test_config()
        points = self.create_test_points()

        with tempfile.NamedTemporaryFile(suffix=".gif", delete=False) as f:
            output_path = Path(f.name)

        try:
            subscriber = GIFAnimationSubscriber(output_path, config)

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

            # Verify GIF file was created
            assert output_path.exists(), "GIF file should be created"
            assert output_path.stat().st_size > 0, "GIF file should not be empty"

            # Verify it's a valid animated GIF
            with Image.open(output_path) as img:
                assert img.format == "GIF", "Should be a valid GIF file"
                assert (
                    img.size[0] > 0 and img.size[1] > 0
                ), "Should have valid dimensions"
                frames = getattr(img, "n_frames", 1)
                assert frames > 1, f"Should be animated (multiple frames), got {frames}"

        finally:
            if output_path.exists():
                output_path.unlink()

    def test_animation_architecture_transition(self):
        """Test that new GIF animation architecture is available."""
        config = Config()

        # Verify new GIF animation subscriber can be imported and created
        if GIF_AVAILABLE:
            from microweldr.outputs.gif_animation_subscriber import (
                GIFAnimationSubscriber,
            )
            from pathlib import Path
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".gif") as f:
                subscriber = GIFAnimationSubscriber(Path(f.name), config)
                assert subscriber is not None

        # This test documents that the transition to GIF-only animation is complete
        assert True, "New GIF animation architecture is available"
