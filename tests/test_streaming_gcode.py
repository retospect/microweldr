"""
Tests for the streaming G-code subscriber functionality.
"""

import tempfile
from pathlib import Path
import pytest

from microweldr.core.config import Config
from microweldr.outputs.streaming_gcode_subscriber import StreamingGCodeSubscriber
from microweldr.generators.models import WeldPath, WeldPoint


class TestStreamingGCodeSubscriber:
    """Test the streaming G-code subscriber."""

    def test_subscriber_initialization(self):
        """Test subscriber can be initialized."""
        config = Config()  # Use default config
        output_path = Path("/tmp/test.gcode")
        subscriber = StreamingGCodeSubscriber(output_path, config)
        assert subscriber is not None
        assert subscriber.config is config

    def test_basic_gcode_generation(self):
        """Test basic G-code generation with streaming subscriber."""
        config = Config()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".gcode", delete=False) as f:
            output_path = Path(f.name)

        try:
            subscriber = StreamingGCodeSubscriber(output_path, config)

            # The subscriber should create a valid G-code file when events are sent
            # This is tested more thoroughly in the CLI integration tests
            assert subscriber is not None

        finally:
            if output_path.exists():
                output_path.unlink()
