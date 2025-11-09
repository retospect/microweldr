"""Enhanced file writers using event-driven architecture."""

from pathlib import Path
from typing import List
import logging

from .processing_events import FileWriterSubscriber
from .data_models import WeldPath

logger = logging.getLogger(__name__)


class GCodeWriterSubscriber(FileWriterSubscriber):
    """G-code writer that subscribes to processing events."""

    def can_write_file(self, file_path: Path) -> bool:
        """Check if this writer can handle G-code files."""
        return file_path.suffix.lower() in [".gcode", ".g", ".nc"]

    def write_output(self, output_path: Path, **kwargs) -> bool:
        """Write G-code file using weld paths from events."""
        from ..core.gcode_generator import GCodeGenerator

        logger.info(f"Writing G-code to: {output_path}")

        generator = GCodeGenerator(self.config)

        # Extract options from kwargs
        skip_bed_leveling = kwargs.get("skip_bed_leveling", False)

        # Convert to old-style WeldPath with WeldPoint objects for compatibility
        from ..core.models import WeldPath as OldWeldPath, WeldPoint

        enhanced_paths = []
        for i, path in enumerate(self._weld_paths):
            # Convert WeldType enum to string
            weld_type_str = (
                path.weld_type.value
                if hasattr(path.weld_type, "value")
                else path.weld_type
            )

            # Convert Point objects to WeldPoint objects
            weld_points = []
            for point in path.points:
                weld_point = WeldPoint(x=point.x, y=point.y, weld_type=weld_type_str)
                weld_points.append(weld_point)

            # Create old-style WeldPath
            old_path = OldWeldPath(
                points=weld_points,
                weld_type=weld_type_str,
                svg_id=path.path_id or f"path_{i+1}",
            )

            enhanced_paths.append(old_path)

        generator.generate_file(
            enhanced_paths, output_path, skip_bed_leveling=skip_bed_leveling
        )

        logger.info(f"G-code written successfully: {output_path}")
        return True


class AnimationWriterSubscriber(FileWriterSubscriber):
    """Animation writer that subscribes to processing events."""

    def can_write_file(self, file_path: Path) -> bool:
        """Check if this writer can handle animation files."""
        return file_path.suffix.lower() in [".svg", ".png"]

    def write_output(self, output_path: Path, **kwargs) -> bool:
        """Write animation file using weld paths from events."""
        from ..animation.generator import AnimationGenerator
        from ..core.models import WeldPath as OldWeldPath, WeldPoint

        logger.info(f"Writing animation to: {output_path}")

        generator = AnimationGenerator(self.config)

        # Convert to old-style WeldPath objects for AnimationGenerator compatibility
        old_paths = []
        for i, path in enumerate(self._weld_paths):
            # Convert WeldType enum to string
            weld_type_str = (
                path.weld_type.value
                if hasattr(path.weld_type, "value")
                else path.weld_type
            )

            # Convert Point objects to WeldPoint objects
            weld_points = []
            for point in path.points:
                weld_point = WeldPoint(x=point.x, y=point.y, weld_type=weld_type_str)
                weld_points.append(weld_point)

            # Create old-style WeldPath
            old_path = OldWeldPath(
                points=weld_points,
                weld_type=weld_type_str,
                svg_id=path.path_id or f"path_{i+1}",
            )
            old_paths.append(old_path)

        # Determine format and use appropriate method
        is_png = output_path.suffix.lower() == ".png"

        if is_png:
            generator.generate_png_file(old_paths, output_path)
        else:
            generator.generate_file(old_paths, output_path)

        logger.info(f"Animation written successfully: {output_path}")
        return True
