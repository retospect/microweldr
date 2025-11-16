"""Data models for the SVG welder.

DEPRECATED: WeldPoint and WeldPath have moved to microweldr.generators.models
This file provides backward compatibility imports.
"""

# Backward compatibility imports
from ..generators.models import WeldPoint, WeldPath

# Re-export for backward compatibility
__all__ = ["WeldPoint", "WeldPath"]
