"""Two-phase processor for efficient DXF/SVG processing."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from ..generators.point_iterator_factory import PointIteratorFactory
from ..generators.multipass_point_iterator import iterate_multipass_points_from_file
from ..core.config import Config

logger = logging.getLogger(__name__)


class TwoPhaseProcessor:
    """
    Two-phase processor that separates analysis from generation.

    Phase 1: Analysis (lightweight)
    - Calculate frame extents
    - Validate points (optional)
    - Gather statistics

    Phase 2: Generation (heavy)
    - Generate G-code
    - Generate animations
    - Generate PNGs
    """

    def __init__(self, config: Config, verbose: bool = False):
        """Initialize two-phase processor."""
        self.config = config
        self.verbose = verbose
        self.factory = GeneratorFactory(config.config)

        if verbose:
            logging.basicConfig(
                level=logging.DEBUG, format="%(levelname)s:%(name)s:%(message)s"
            )
            logging.getLogger().setLevel(logging.DEBUG)

    def process_file(
        self,
        input_path: Path,
        output_path: Optional[Path] = None,
        animation_path: Optional[Path] = None,
        png_path: Optional[Path] = None,
        verbose: bool = False,
    ) -> bool:
        """
        Process file using two-phase architecture.

        Args:
            input_path: Input DXF/SVG file
            output_path: Output G-code file
            animation_path: Output animation file (optional)
            png_path: Output PNG file (optional)
            verbose: Enable verbose logging

        Returns:
            True if processing succeeded, False otherwise
        """
        try:
            logger.info(f"🔥 Starting two-phase processing: {input_path}")

            # Phase 1: Analysis
            logger.info("📊 Phase 1: Analysis")
            bounds = self._run_phase1(input_path)

            if not bounds:
                logger.error("❌ Phase 1 failed - no valid bounds calculated")
                return False

            logger.info(
                f"✅ Phase 1 complete - Frame: {bounds['width']:.1f} × {bounds['height']:.1f}"
            )

            # Phase 2: Generation
            logger.info("🚀 Phase 2: Generation")
            results = self._run_phase2(
                input_path, bounds, output_path, animation_path, png_path
            )

            if not results:
                logger.error("❌ Phase 2 failed")
                return False

            logger.info("✅ Two-phase processing complete!")
            self._print_results(results)
            return True

        except Exception as e:
            logger.exception(f"❌ Two-phase processing failed: {e}")
            return False

    def _run_phase1(self, input_path: Path) -> Optional[Dict[str, float]]:
        """Run Phase 1: Analysis."""
        try:
            # Create Phase 1 generators
            generators = self.factory.create_phase1_generators()

            if self.verbose:
                logger.debug(
                    f"Phase 1 generators: {[g.__class__.__name__ for g in generators]}"
                )

            # Process all points through Phase 1 generators
            point_count = 0
            for point in iterate_points_from_file(input_path):
                for generator in generators:
                    generator.add_point(point)
                point_count += 1

                if self.verbose and point_count % 100 == 0:
                    logger.debug(f"Phase 1 processed {point_count} points...")

            # Finalize Phase 1 generators
            bounds = None
            for generator in generators:
                result = generator.finalize()
                if hasattr(generator, "get_bounds"):
                    bounds = generator.get_bounds()

            logger.info(f"Phase 1: Analyzed {point_count} points")
            return bounds

        except Exception as e:
            logger.exception(f"Phase 1 error: {e}")
            return None

    def _run_phase2(
        self,
        input_path: Path,
        bounds: Dict[str, float],
        output_path: Optional[Path],
        animation_path: Optional[Path],
        png_path: Optional[Path],
    ) -> Optional[List[Dict[str, Any]]]:
        """Run Phase 2: Generation."""
        try:
            # Create Phase 2 generators
            generators = self.factory.create_phase2_generators(
                bounds=bounds,
                output_path=output_path,
                animation_path=animation_path,
                png_path=png_path,
                no_animation=animation_path is None,
                generate_png=png_path is not None,
            )

            if not generators:
                logger.warning("No Phase 2 generators created")
                return []

            if self.verbose:
                logger.debug(
                    f"Phase 2 generators: {[g.__class__.__name__ for g in generators]}"
                )

            # Process all multipass points through Phase 2 generators
            point_count = 0
            for point in iterate_multipass_points_from_file(
                input_path, self.config._config
            ):
                for generator in generators:
                    generator.add_point(point)
                point_count += 1

                if self.verbose and point_count % 100 == 0:
                    logger.debug(f"Phase 2 processed {point_count} points...")

            # Finalize Phase 2 generators
            results = []
            for generator in generators:
                result = generator.finalize()
                results.append(result)

            logger.info(f"Phase 2: Generated outputs from {point_count} points")
            return results

        except Exception as e:
            logger.exception(f"Phase 2 error: {e}")
            return None

    def _print_results(self, results: List[Dict[str, Any]]) -> None:
        """Print processing results."""
        for result in results:
            if result.get("success"):
                output_path = result.get("output_path")
                if output_path:
                    logger.info(f"✅ Generated: {output_path}")
            else:
                error = result.get("error", "Unknown error")
                logger.error(f"❌ Generation failed: {error}")

    def get_validation_results(self) -> Dict[str, Any]:
        """Get validation results (placeholder for compatibility)."""
        return {"errors": [], "warnings": []}

    def clear_validation_results(self) -> None:
        """Clear validation results (placeholder for compatibility)."""
        pass
