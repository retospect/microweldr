"""Main converter class that orchestrates the conversion process."""

from pathlib import Path
from typing import List

from svg_welder.core.config import Config
from svg_welder.core.gcode_generator import GCodeGenerator
from svg_welder.core.models import WeldPath
from svg_welder.core.svg_parser import SVGParser


class SVGToGCodeConverter:
    """Main converter class for SVG to G-code conversion."""

    def __init__(self, config: Config) -> None:
        """Initialize converter with configuration."""
        self.config = config
        self.config.validate()  # Validate configuration on initialization

        # Initialize components
        dot_spacing = self.config.get("normal_welds", "dot_spacing")
        self.svg_parser = SVGParser(dot_spacing=dot_spacing)
        self.gcode_generator = GCodeGenerator(config=self.config)

        # Store parsed paths
        self.weld_paths: List[WeldPath] = []

    def parse_svg(self, svg_path: str | Path) -> List[WeldPath]:
        """Parse SVG file and return weld paths."""
        svg_path = Path(svg_path)
        self.weld_paths = self.svg_parser.parse_file(str(svg_path))
        return self.weld_paths

    def generate_gcode(
        self, output_path: str | Path, skip_bed_leveling: bool = False
    ) -> None:
        """Generate G-code file from parsed weld paths."""
        if not self.weld_paths:
            raise ValueError("No weld paths available. Parse SVG file first.")

        self.gcode_generator.generate_file(
            weld_paths=self.weld_paths,
            output_path=output_path,
            skip_bed_leveling=skip_bed_leveling,
        )

    def convert(
        self,
        svg_path: str | Path,
        gcode_path: str | Path,
        skip_bed_leveling: bool = False,
    ) -> List[WeldPath]:
        """Complete conversion from SVG to G-code."""
        weld_paths = self.parse_svg(svg_path)
        self.generate_gcode(gcode_path, skip_bed_leveling)
        return weld_paths

    @property
    def path_count(self) -> int:
        """Get the number of parsed weld paths."""
        return len(self.weld_paths)

    def get_bounds(self) -> tuple[float, float, float, float]:
        """Get the bounding box of all weld paths as (min_x, min_y, max_x, max_y)."""
        if not self.weld_paths:
            return (0.0, 0.0, 0.0, 0.0)

        all_bounds = [path.get_bounds() for path in self.weld_paths]

        min_x = min(bounds[0] for bounds in all_bounds)
        min_y = min(bounds[1] for bounds in all_bounds)
        max_x = max(bounds[2] for bounds in all_bounds)
        max_y = max(bounds[3] for bounds in all_bounds)

        return (min_x, min_y, max_x, max_y)
