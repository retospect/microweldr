"""Point iterator for two-phase processing architecture.

This module provides a unified interface for iterating through points from various
file formats (SVG, DXF) using a factory pattern with dedicated iterator classes.
"""

# Re-export the main functions from the factory for backward compatibility
from .point_iterator_factory import iterate_points_from_file, count_points_in_file

__all__ = ["iterate_points_from_file", "count_points_in_file"]
