"""SVG to G-code Welder - Convert SVG files to Prusa Core One G-code for plastic welding."""

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from svg_welder.core.config import Config
from svg_welder.core.converter import SVGToGCodeConverter
from svg_welder.core.models import WeldPath, WeldPoint

__all__ = [
    "WeldPoint",
    "WeldPath",
    "SVGToGCodeConverter",
    "Config",
]
