"""Animation generation functionality."""

from pathlib import Path
from typing import List, TextIO

from svg_welder.core.config import Config
from svg_welder.core.models import WeldPath


class AnimationGenerator:
    """Generator for animated SVG files showing the welding process."""

    def __init__(self, config: Config) -> None:
        """Initialize animation generator."""
        self.config = config

    def generate_file(self, weld_paths: List[WeldPath], output_path: str | Path) -> None:
        """Generate animated SVG file from weld paths."""
        if not weld_paths:
            return
        
        output_path = Path(output_path)
        
        # Get animation configuration
        time_between_welds = self.config.get('animation', 'time_between_welds')
        pause_time = self.config.get('animation', 'pause_time')
        min_animation_duration = self.config.get('animation', 'min_animation_duration')
        
        # Calculate bounds
        bounds = self._calculate_bounds(weld_paths)
        min_x, min_y, max_x, max_y = bounds
        
        # Add padding
        padding = 20  # Increased padding for pause messages
        width = max_x - min_x + 2 * padding
        height = max_y - min_y + 2 * padding + 40  # Extra space for messages
        
        # Calculate total animation time
        total_weld_points = sum(
            len(path.points) for path in weld_paths if path.weld_type != 'stop'
        )
        total_pause_time = sum(
            pause_time for path in weld_paths if path.weld_type == 'stop'
        )
        calculated_duration = total_weld_points * time_between_welds + total_pause_time
        animation_duration = max(min_animation_duration, calculated_duration)
        
        with open(output_path, 'w') as f:
            self._write_svg_header(f, width, height)
            self._write_title_and_info(f, width, animation_duration, time_between_welds, pause_time)
            self._write_animation_elements(f, weld_paths, bounds, padding, animation_duration, 
                                         time_between_welds, pause_time)
            self._write_legend(f, height)
            self._write_svg_footer(f)

    def _calculate_bounds(self, weld_paths: List[WeldPath]) -> tuple[float, float, float, float]:
        """Calculate bounding box for all weld paths."""
        all_points = []
        for path in weld_paths:
            all_points.extend(path.points)
        
        if not all_points:
            return (0.0, 0.0, 0.0, 0.0)
        
        min_x = min(p.x for p in all_points)
        max_x = max(p.x for p in all_points)
        min_y = min(p.y for p in all_points)
        max_y = max(p.y for p in all_points)
        
        return (min_x, min_y, max_x, max_y)

    def _write_svg_header(self, f: TextIO, width: float, height: float) -> None:
        """Write SVG header."""
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">\n')
        f.write('  <rect width="100%" height="100%" fill="white"/>\n')

    def _write_title_and_info(self, f: TextIO, width: float, animation_duration: float,
                             time_between_welds: float, pause_time: float) -> None:
        """Write title and timing information."""
        f.write(f'  <text x="{width/2}" y="20" text-anchor="middle" font-family="Arial" '
                f'font-size="14" fill="black">SVG Welding Animation</text>\n')
        
        f.write(f'  <text x="{width/2}" y="35" text-anchor="middle" font-family="Arial" '
                f'font-size="10" fill="gray">Duration: {animation_duration:.1f}s | '
                f'Weld interval: {time_between_welds}s | Pause time: {pause_time}s</text>\n')

    def _write_animation_elements(self, f: TextIO, weld_paths: List[WeldPath], 
                                bounds: tuple[float, float, float, float], padding: float,
                                animation_duration: float, time_between_welds: float, 
                                pause_time: float) -> None:
        """Write animation elements for weld paths."""
        min_x, min_y, max_x, max_y = bounds
        current_time = 0.0
        
        for path in weld_paths:
            # Handle stop points (pause messages)
            if path.weld_type == 'stop':
                if path.points:
                    self._write_stop_point(f, path, min_x, min_y, padding, 
                                         animation_duration, current_time)
                current_time += pause_time
                continue
            
            # Determine color based on weld type
            color = 'blue' if path.weld_type == 'light' else 'black'
            
            # Process weld points
            for point in path.points:
                # Adjust coordinates
                x = point.x - min_x + padding
                y = point.y - min_y + padding + 40  # Offset for header
                
                # Create animated weld point circle
                f.write(f'  <circle cx="{x:.2f}" cy="{y:.2f}" r="2" fill="{color}" opacity="0">\n')
                f.write(f'    <animate attributeName="opacity" values="0;1;1;0.3" '
                        f'dur="{animation_duration}s" begin="{current_time:.2f}s" '
                        f'repeatCount="indefinite"/>\n')
                f.write('  </circle>\n')
                
                current_time += time_between_welds

    def _write_stop_point(self, f: TextIO, path: WeldPath, min_x: float, min_y: float,
                         padding: float, animation_duration: float, current_time: float) -> None:
        """Write stop point with pause message."""
        point = path.points[0]
        x = point.x - min_x + padding
        y = point.y - min_y + padding
        
        # Display pause message
        message = path.pause_message or 'Manual intervention required'
        safe_message = message.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Message background
        f.write(f'  <rect x="{x-50}" y="{y-25}" width="100" height="20" '
                f'fill="yellow" stroke="red" stroke-width="1" opacity="0">\n')
        f.write(f'    <animate attributeName="opacity" values="0;0.9;0.9;0" '
                f'dur="{animation_duration}s" begin="{current_time:.2f}s" '
                f'repeatCount="indefinite"/>\n')
        f.write('  </rect>\n')
        
        # Message text
        f.write(f'  <text x="{x}" y="{y-10}" text-anchor="middle" font-family="Arial" '
                f'font-size="8" fill="red" opacity="0">\n')
        f.write(f'    <animate attributeName="opacity" values="0;1;1;0" '
                f'dur="{animation_duration}s" begin="{current_time:.2f}s" '
                f'repeatCount="indefinite"/>\n')
        f.write(f'    {safe_message[:30]}{"..." if len(safe_message) > 30 else ""}\n')
        f.write('  </text>\n')
        
        # Stop indicator circle
        f.write(f'  <circle cx="{x:.2f}" cy="{y:.2f}" r="4" fill="red" '
                f'stroke="darkred" stroke-width="2" opacity="0">\n')
        f.write(f'    <animate attributeName="opacity" values="0;1;1;0" '
                f'dur="{animation_duration}s" begin="{current_time:.2f}s" '
                f'repeatCount="indefinite"/>\n')
        f.write('  </circle>\n')

    def _write_legend(self, f: TextIO, height: float) -> None:
        """Write legend explaining weld types."""
        legend_y = height - 15
        f.write(f'  <text x="10" y="{legend_y}" font-family="Arial" font-size="10" '
                f'fill="gray">Legend:</text>\n')
        f.write(f'  <circle cx="60" cy="{legend_y-4}" r="2" fill="black"/>\n')
        f.write(f'  <text x="70" y="{legend_y}" font-family="Arial" font-size="9" '
                f'fill="gray">Normal Welds</text>\n')
        f.write(f'  <circle cx="160" cy="{legend_y-4}" r="2" fill="blue"/>\n')
        f.write(f'  <text x="170" y="{legend_y}" font-family="Arial" font-size="9" '
                f'fill="gray">Light Welds</text>\n')
        f.write(f'  <circle cx="250" cy="{legend_y-4}" r="4" fill="red"/>\n')
        f.write(f'  <text x="260" y="{legend_y}" font-family="Arial" font-size="9" '
                f'fill="gray">Stop Points</text>\n')

    def _write_svg_footer(self, f: TextIO) -> None:
        """Write SVG footer."""
        f.write('</svg>\n')
