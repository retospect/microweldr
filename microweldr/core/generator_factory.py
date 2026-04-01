"""Generator factory for two-phase processing architecture."""

import logging
from pathlib import Path
from typing import Any

from .unified_generators import GCodeGenerator, PNGGenerator, SVGGenerator

logger = logging.getLogger(__name__)


class GeneratorFactory:
    """Factory for creating generators based on command line arguments."""

    def __init__(self, config: dict[str, Any]):
        """Initialize factory with configuration."""
        self.config = config

    def create_phase1_generators(self) -> list[Any]:
        """Create generators for Phase 1 (analysis)."""
        from .frame_extent_calculator import FrameExtentCalculator

        generators = [FrameExtentCalculator()]

        # TODO: Add PointValidatorAndErrorGenerator if validation is enabled
        # if self.config.get("enable_validation", True):
        #     generators.append(PointValidatorAndErrorGenerator())

        logger.debug(f"Created {len(generators)} Phase 1 generators")
        return generators

    def create_phase2_generators(
        self,
        bounds: dict[str, float],
        output_path: Path | None = None,
        animation_path: Path | None = None,
        png_path: Path | None = None,
        **kwargs,
    ) -> list[Any]:
        """Create generators for Phase 2 (generation)."""
        generators = []

        # Always create G-code generator if output path provided
        if output_path:
            generators.append(
                GCodeGenerator(
                    output_path=output_path, bounds=bounds, config=self.config
                )
            )
            logger.debug(f"Added G-code generator: {output_path}")

        # Add animation generator if requested
        if animation_path and not kwargs.get("no_animation", False):
            # Check if this is PNG generation based on file extension
            if animation_path.suffix.lower() == ".png":
                generators.append(
                    PNGGenerator(
                        output_path=animation_path, bounds=bounds, config=self.config
                    )
                )
                logger.debug(f"Added PNG generator: {animation_path}")
            else:
                generators.append(
                    SVGGenerator(
                        output_path=animation_path, bounds=bounds, config=self.config
                    )
                )
                logger.debug(f"Added SVG generator: {animation_path}")

        logger.info(f"Created {len(generators)} Phase 2 generators")
        return generators
