"""Generator factory for two-phase processing architecture."""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from .simple_gcode_generator import SimpleGCodeGenerator

logger = logging.getLogger(__name__)


class GeneratorFactory:
    """Factory for creating generators based on command line arguments."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize factory with configuration."""
        self.config = config

    def create_phase1_generators(self) -> List[Any]:
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
        bounds: Dict[str, float],
        output_path: Optional[Path] = None,
        animation_path: Optional[Path] = None,
        png_path: Optional[Path] = None,
        **kwargs,
    ) -> List[Any]:
        """Create generators for Phase 2 (generation)."""
        generators = []

        # Always create G-code generator if output path provided
        if output_path:
            generators.append(
                SimpleGCodeGenerator(
                    output_path=output_path, bounds=bounds, config=self.config
                )
            )
            logger.debug(f"Added G-code generator: {output_path}")

        # Add animation generator if requested
        if animation_path and not kwargs.get("no_animation", False):
            try:
                # Check if this is PNG generation based on file extension
                if animation_path.suffix.lower() == ".png":
                    generators.append(
                        SimplePNGGenerator(
                            output_path=animation_path,
                            bounds=bounds,
                            config=self.config,
                        )
                    )
                    logger.debug(f"Added PNG generator: {animation_path}")
                else:
                    generators.append(
                        SimpleAnimationGenerator(
                            output_path=animation_path,
                            bounds=bounds,
                            config=self.config,
                        )
                    )
                    logger.debug(f"Added animation generator: {animation_path}")
            except ImportError:
                logger.warning("Animation generator not available")

        # Add PNG generator if requested
        if png_path and kwargs.get("generate_png", False):
            try:
                generators.append(
                    SimplePNGGenerator(
                        output_path=png_path, bounds=bounds, config=self.config
                    )
                )
                logger.debug(f"Added PNG generator: {png_path}")
            except ImportError:
                logger.warning("PNG generator not available")

        logger.info(f"Created {len(generators)} Phase 2 generators")
        return generators


# Placeholder classes for future implementation
class SimpleAnimationGenerator:
    """Simple animation generator (placeholder)."""

    def __init__(
        self, output_path: Path, bounds: Dict[str, float], config: Dict[str, Any]
    ):
        self.output_path = output_path
        self.bounds = bounds
        self.config = config
        logger.info(f"Animation generator initialized: {output_path}")

    def add_point(self, point: Dict[str, Any]) -> None:
        """Add point to animation (placeholder)."""
        pass

    def finalize(self) -> Dict[str, Any]:
        """Finalize animation (placeholder)."""
        logger.info(f"Animation generation complete: {self.output_path}")
        return {"success": True, "output_path": self.output_path}


class SimplePNGGenerator:
    """PNG generator using the real AnimationGenerator."""

    def __init__(
        self, output_path: Path, bounds: Dict[str, float], config: Dict[str, Any]
    ):
        from ..animation.generator import AnimationGenerator
        from ..core.config import Config

        self.output_path = output_path
        self.bounds = bounds

        # Create Config object from dict
        config_obj = Config()
        config_obj._config = config

        # Initialize real animation generator
        self.animation_generator = AnimationGenerator(config_obj)
        self.animation_generator.initialize_for_png(output_path, bounds)

        logger.info(f"PNG generator initialized: {output_path}")

    def add_point(self, point: Dict[str, Any]) -> None:
        """Add point to PNG generation."""
        self.animation_generator.add_point(point)

    def finalize(self) -> Dict[str, Any]:
        """Finalize PNG generation."""
        result = self.animation_generator.finalize_png()
        if result.get("success"):
            logger.info(f"PNG generation complete: {self.output_path}")
        else:
            logger.error(f"PNG generation failed: {result.get('error')}")
        return result
