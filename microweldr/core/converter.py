"""Main converter class that orchestrates the conversion process."""

from pathlib import Path
from typing import List

from microweldr.core.config import Config
from microweldr.core.gcode_generator import GCodeGenerator
from microweldr.core.models import WeldPath
from microweldr.core.svg_parser import SVGParser


class SVGToGCodeConverter:
    """Main converter class for SVG to G-code conversion."""

    def __init__(self, config: Config, center_on_bed: bool = True) -> None:
        """Initialize converter with configuration."""
        self.config = config
        self.config.validate()  # Validate configuration on initialization
        self.center_on_bed = center_on_bed

        # Initialize components
        dot_spacing = self.config.get("normal_welds", "dot_spacing")
        self.svg_parser = SVGParser(dot_spacing=dot_spacing)
        self.gcode_generator = GCodeGenerator(config=self.config)

        # Store parsed paths and coordinate transformation
        self.weld_paths: List[WeldPath] = []
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.margin_info = None

    def parse_svg(self, svg_path: str | Path) -> List[WeldPath]:
        """Parse SVG file and return weld paths."""
        svg_path = Path(svg_path)
        self.weld_paths = self.svg_parser.parse_file(str(svg_path))

        # Calculate centering offset if enabled
        if self.center_on_bed and self.weld_paths:
            self._calculate_centering_offset()
            self._apply_centering_offset()

        return self.weld_paths

    def _calculate_centering_offset(self) -> None:
        """Calculate offset needed to center the design on the bed."""
        if not self.weld_paths:
            return

        # Get bounds of all weld paths
        all_points = []
        for path in self.weld_paths:
            all_points.extend(path.points)

        if not all_points:
            return

        min_x = min(point.x for point in all_points)
        max_x = max(point.x for point in all_points)
        min_y = min(point.y for point in all_points)
        max_y = max(point.y for point in all_points)

        # Get bed dimensions from config
        bed_size_x = self.config.get("printer", "bed_size_x")
        bed_size_y = self.config.get("printer", "bed_size_y")

        # Calculate design dimensions
        design_width = max_x - min_x
        design_height = max_y - min_y

        # Calculate offset to center the design
        bed_center_x = bed_size_x / 2
        bed_center_y = bed_size_y / 2
        design_center_x = min_x + design_width / 2
        design_center_y = min_y + design_height / 2

        self.offset_x = bed_center_x - design_center_x
        self.offset_y = bed_center_y - design_center_y

        # Calculate final position after centering
        final_min_x = min_x + self.offset_x
        final_max_x = max_x + self.offset_x
        final_min_y = min_y + self.offset_y
        final_max_y = max_y + self.offset_y

        # Calculate margins from bed edges
        margin_left = final_min_x
        margin_right = bed_size_x - final_max_x
        margin_front = final_min_y  # Front is Y=0 side
        margin_back = bed_size_y - final_max_y  # Back is Y=max side

        print(
            f"📐 Design bounds: ({min_x:.1f}, {min_y:.1f}) to ({max_x:.1f}, {max_y:.1f})"
        )
        print(f"📐 Design size: {design_width:.1f} × {design_height:.1f} mm")
        print(f"🎯 Centering offset: ({self.offset_x:.1f}, {self.offset_y:.1f}) mm")
        print(
            f"🎯 Centered position: ({final_min_x:.1f}, {final_min_y:.1f}) to ({final_max_x:.1f}, {final_max_y:.1f})"
        )
        print(
            f"📏 Bed margins: Front/Back: {margin_front/10:.1f}/{margin_back/10:.1f}cm, Left/Right: {margin_left/10:.1f}/{margin_right/10:.1f}cm"
        )

        # Store margin info for use in G-code generation
        self.margin_info = {
            "front_back": f"{margin_front/10:.1f}/{margin_back/10:.1f}cm",
            "left_right": f"{margin_left/10:.1f}/{margin_right/10:.1f}cm",
            "design_size": f"{design_width:.0f}×{design_height:.0f}mm",
        }

    def _apply_centering_offset(self) -> None:
        """Apply the centering offset to all weld points."""
        if self.offset_x == 0 and self.offset_y == 0:
            return

        for path in self.weld_paths:
            for point in path.points:
                point.x += self.offset_x
                point.y += self.offset_y

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
            margin_info=self.margin_info,
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
