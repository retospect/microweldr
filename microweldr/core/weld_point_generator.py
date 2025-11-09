"""Shared utility for generating interpolated weld points for multi-pass welding."""

import math
from typing import List, Tuple
from .models import WeldPoint


class WeldPointGenerator:
    """Generates interpolated weld points for multi-pass welding operations."""

    @staticmethod
    def generate_multipass_points(
        original_points: List[WeldPoint],
        initial_spacing: float,
        final_spacing: float,
        num_passes: int,
    ) -> List[List[WeldPoint]]:
        """Generate points for each pass of multi-pass welding.

        Args:
            original_points: Original path points from DXF/SVG
            initial_spacing: Spacing for first pass (mm)
            final_spacing: Spacing for final pass (mm)
            num_passes: Number of welding passes

        Returns:
            List of point lists, one for each pass
        """
        if num_passes == 1:
            return [original_points]

        # Create a continuous path from all points with interpolation
        all_path_points = []
        for i in range(len(original_points) - 1):
            start = original_points[i]
            end = original_points[i + 1]

            # Calculate distance
            dx = end.x - start.x
            dy = end.y - start.y
            distance = math.sqrt(dx * dx + dy * dy)

            if distance == 0:
                continue

            # Generate points at final spacing along this segment
            num_points = max(1, int(distance / final_spacing))

            for j in range(num_points + 1):
                t = j / num_points if num_points > 0 else 0
                x = start.x + t * dx
                y = start.y + t * dy
                all_path_points.append((x, y, start.weld_type))

        # Now distribute these points across passes
        passes = [[] for _ in range(num_passes)]

        # First pass: every 2^(num_passes-1) point
        step = 2 ** (num_passes - 1)
        for i in range(0, len(all_path_points), step):
            x, y, weld_type = all_path_points[i]
            passes[0].append(WeldPoint(x, y, weld_type))

        # Subsequent passes: fill in between previous pass points
        for pass_num in range(1, num_passes):
            step = 2 ** (num_passes - 1 - pass_num)
            offset = step

            for i in range(offset, len(all_path_points), step * 2):
                if i < len(all_path_points):
                    x, y, weld_type = all_path_points[i]
                    passes[pass_num].append(WeldPoint(x, y, weld_type))

        return passes

    @staticmethod
    def get_all_weld_points(
        original_points: List[WeldPoint],
        initial_spacing: float,
        final_spacing: float,
        num_passes: int,
    ) -> List[WeldPoint]:
        """Get all weld points that will be welded (flattened from all passes).

        This is useful for animation generation to show exactly what will be welded.
        """
        passes = WeldPointGenerator.generate_multipass_points(
            original_points, initial_spacing, final_spacing, num_passes
        )

        # Flatten all passes into a single list
        all_points = []
        for pass_points in passes:
            all_points.extend(pass_points)

        return all_points

    @staticmethod
    def get_weld_point_count(
        original_points: List[WeldPoint],
        initial_spacing: float,
        final_spacing: float,
        num_passes: int,
    ) -> int:
        """Get the total number of weld operations that will be performed."""
        all_points = WeldPointGenerator.get_all_weld_points(
            original_points, initial_spacing, final_spacing, num_passes
        )
        return len(all_points)
