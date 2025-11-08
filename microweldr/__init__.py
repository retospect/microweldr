"""MicroWeldr - Convert SVG files to Prusa Core One G-code for plastic welding."""

__version__ = "5.1.5"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from microweldr.core.config import Config
from microweldr.core.converter import SVGToGCodeConverter
from microweldr.core.models import WeldPath, WeldPoint

__all__ = [
    "WeldPoint",
    "WeldPath",
    "SVGToGCodeConverter",
    "Config",
]
