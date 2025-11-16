"""Tests for animation generation functionality.

NOTE: The old AnimationGenerator class has been replaced with streaming animation subscribers.
The new architecture uses:
- PNGAnimationSubscriber for PNG output
- StreamingAnimationSubscriber for SVG output

See tests/outputs/test_animation_generation.py for current tests.
"""

import pytest
from microweldr.core.config import Config

try:
    from microweldr.outputs.png_animation_subscriber import PNGAnimationSubscriber

    ANIMATION_AVAILABLE = True
except ImportError:
    ANIMATION_AVAILABLE = False


@pytest.mark.skipif(
    not ANIMATION_AVAILABLE, reason="Animation dependencies not available"
)
class TestAnimationGenerator:
    """Legacy test class - replaced by streaming architecture."""

    def test_animation_architecture_transition(self):
        """Test that new animation architecture is available."""
        config = Config()

        # Verify new PNG animation subscriber can be imported and created
        from microweldr.outputs.png_animation_subscriber import PNGAnimationSubscriber
        from pathlib import Path
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            subscriber = PNGAnimationSubscriber(Path(f.name), config)
            assert subscriber is not None

        # This test documents that the transition to streaming architecture is complete
        assert True, "New streaming animation architecture is available"
