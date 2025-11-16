"""Multipass point iterator that generates the final welding points."""

import logging
from pathlib import Path
from typing import Iterator, Dict, Any, List
from .point_iterator_factory import PointIteratorFactory
from .weld_point_generator import WeldPointGenerator
from .models import WeldPoint

logger = logging.getLogger(__name__)


def iterate_multipass_points_from_file(
    file_path: Path, config: Dict[str, Any]
) -> Iterator[Dict[str, Any]]:
    """Iterate through multipass welding points from a file.

    This generates the exact same points that will be welded, with proper
    multipass spacing applied. All generators (G-code, SVG, PNG) receive
    the same points.
    """
    logger.debug(f"Starting multipass point iteration from {file_path}")

    # Group points by path
    paths_dict = {}
    for point in iterate_points_from_file(file_path):
        path_id = point["path_id"]
        if path_id not in paths_dict:
            paths_dict[path_id] = []
        paths_dict[path_id].append(point)

    logger.info(
        f"Grouped {sum(len(points) for points in paths_dict.values())} points into {len(paths_dict)} paths"
    )

    # Process each path with multipass logic
    total_output_points = 0
    for path_id, path_points in paths_dict.items():
        logger.debug(f"Processing path {path_id}: {len(path_points)} input points")

        # Convert to WeldPoint objects
        weld_points = []
        for point in path_points:
            weld_points.append(
                WeldPoint(x=point["x"], y=point["y"], weld_type=point["weld_type"])
            )

        # Determine if this is an arc (many points) or line (few points)
        if (
            len(weld_points) > 10
        ):  # Likely an arc - apply multipass along tessellated curve
            logger.debug(
                f"Path {path_id}: Arc detected, applying multipass along {len(weld_points)} tessellated points"
            )
            # Get config for this weld type
            weld_type = path_points[0]["weld_type"]
            config_section = (
                "frangible_welds" if weld_type == "frangible" else "normal_welds"
            )
            initial_spacing = config.get(config_section, {}).get(
                "initial_dot_spacing", 8.0
            )
            final_spacing = config.get(config_section, {}).get("final_dot_spacing", 0.5)

            # Apply multipass to the tessellated arc
            multipass_points = WeldPointGenerator.get_all_weld_points(
                weld_points, initial_spacing, final_spacing
            )
        else:  # Line - apply multipass spacing
            # Get config for this weld type
            weld_type = path_points[0]["weld_type"]
            config_section = (
                "frangible_welds" if weld_type == "frangible" else "normal_welds"
            )
            initial_spacing = config.get(config_section, {}).get(
                "initial_dot_spacing", 8.0
            )
            final_spacing = config.get(config_section, {}).get("final_dot_spacing", 0.5)

            logger.debug(
                f"Path {path_id}: Line detected, applying multipass spacing {initial_spacing}→{final_spacing}mm"
            )
            multipass_points = WeldPointGenerator.get_all_weld_points(
                weld_points, initial_spacing, final_spacing
            )

        # Yield all multipass points for this path
        path_output_count = 0
        for point in multipass_points:
            yield {
                "x": point.x,
                "y": point.y,
                "weld_type": point.weld_type,
                "path_id": path_id,
                "path_weld_type": path_points[0]["path_weld_type"],
            }
            path_output_count += 1
            total_output_points += 1

        logger.debug(f"Path {path_id}: Generated {path_output_count} multipass points")

    logger.info(
        f"Multipass iteration complete: {total_output_points} total welding points"
    )
