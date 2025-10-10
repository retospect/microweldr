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
        
        # Add padding and scale up canvas (triple size)
        padding = 60  # Increased padding for larger canvas
        base_width = max_x - min_x + 2 * padding
        base_height = max_y - min_y + 2 * padding + 120  # Extra space for messages, legend, and scale bar
        
        # Triple the canvas size for better text visibility
        width = base_width * 3
        height = base_height * 3
        
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
        scale_factor = 3.0
        
        f.write(f'  <text x="{width/2}" y="{60*scale_factor}" text-anchor="middle" font-family="Arial" '
                f'font-size="{42*scale_factor}" fill="black">SVG Welding Animation</text>\n')
        
        f.write(f'  <text x="{width/2}" y="{105*scale_factor}" text-anchor="middle" font-family="Arial" '
                f'font-size="{30*scale_factor}" fill="gray">Duration: {animation_duration:.1f}s | '
                f'Weld interval: {time_between_welds}s | Pause time: {pause_time}s</text>\n')

    def _write_animation_elements(self, f: TextIO, weld_paths: List[WeldPath], 
                                bounds: tuple[float, float, float, float], padding: float,
                                animation_duration: float, time_between_welds: float, 
                                pause_time: float) -> None:
        """Write animation elements for weld paths."""
        min_x, min_y, max_x, max_y = bounds
        current_time = 0.0
        scale_factor = 3.0  # Scale factor for tripled canvas size
        
        for path in weld_paths:
            # Handle stop points (pause messages)
            if path.weld_type == 'stop':
                if path.points:
                    self._write_stop_point(f, path, min_x, min_y, padding, 
                                         animation_duration, current_time, scale_factor)
                current_time += pause_time
                continue
            
            # Determine color based on weld type
            color = 'blue' if path.weld_type == 'light' else 'black'
            
            # Process weld points
            for point in path.points:
                # Adjust coordinates with scale factor
                x = (point.x - min_x + padding) * scale_factor
                y = (point.y - min_y + padding + 40) * scale_factor  # Offset for header
                
                # Create realistic nozzle ring animation
                self._write_nozzle_ring(f, x, y, color, animation_duration, current_time, scale_factor)
                
                current_time += time_between_welds

    def _write_stop_point(self, f: TextIO, path: WeldPath, min_x: float, min_y: float,
                         padding: float, animation_duration: float, current_time: float, 
                         scale_factor: float) -> None:
        """Write stop point as red circle with immediate user message display."""
        point = path.points[0]
        x = (point.x - min_x + padding) * scale_factor
        y = (point.y - min_y + padding + 40) * scale_factor  # Offset for header
        
        # Use original radius if it's a circle, otherwise use default
        if path.element_type == 'circle' and path.element_radius is not None:
            radius = max(2.0, min(path.element_radius, 8.0))  # Clamp between 2-8 for visibility
        else:
            radius = 3.0  # Default radius for non-circle stop points
        
        # Get pause message
        message = path.pause_message or 'Manual intervention required'
        safe_message = message.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Scale message box and text for larger canvas
        box_width = 120 * scale_factor
        box_height = 25 * scale_factor
        font_size = 9 * scale_factor
        
        # Message background - appears immediately, no fade-in
        f.write(f'  <rect x="{x-box_width/2}" y="{y-box_height-10}" width="{box_width}" height="{box_height}" '
                f'fill="yellow" stroke="red" stroke-width="{2*scale_factor}" opacity="0">\n')
        f.write(f'    <animate attributeName="opacity" values="0;0.95" '
                f'dur="0.1s" begin="{current_time:.2f}s" fill="freeze"/>\n')
        f.write('  </rect>\n')
        
        # Message text - appears immediately, no fade-in
        f.write(f'  <text x="{x}" y="{y-box_height/2}" text-anchor="middle" font-family="Arial" '
                f'font-size="{font_size}" font-weight="bold" fill="red" opacity="0">\n')
        f.write(f'    <animate attributeName="opacity" values="0;1" '
                f'dur="0.1s" begin="{current_time:.2f}s" fill="freeze"/>\n')
        f.write(f'    {safe_message[:25]}{"..." if len(safe_message) > 25 else ""}\n')
        f.write('  </text>\n')
        
        # Red circle with flip animation (similar to nozzle rings but simpler)
        f.write(f'  <g transform="translate({x:.2f},{y:.2f})" opacity="0">\n')
        
        # Flip animation for stop point (preserving translation)
        f.write(f'    <animateTransform attributeName="transform" type="scale" '
                f'values="0,0;0.2,1.2;1.1,0.9;1,1" dur="0.3s" '
                f'begin="{current_time:.2f}s" fill="freeze" additive="sum"/>\n')
        
        # Opacity animation
        f.write(f'    <animate attributeName="opacity" values="0;1;1;0.8" '
                f'dur="{animation_duration}s" begin="{current_time:.2f}s" '
                f'repeatCount="indefinite"/>\n')
        
        # Red circle (stop indicator) - scale radius
        scaled_radius = radius * scale_factor
        f.write(f'    <circle cx="0" cy="0" r="{scaled_radius:.1f}" fill="red" '
                f'stroke="darkred" stroke-width="{scale_factor}"/>\n')
        
        f.write('  </g>\n')

    def _write_nozzle_ring(self, f: TextIO, x: float, y: float, color: str, 
                          animation_duration: float, current_time: float, scale_factor: float) -> None:
        """Write animated nozzle ring that flips into existence."""
        # Get nozzle dimensions from config
        outer_radius = self.config.get('nozzle', 'outer_diameter', 0.4) / 2
        inner_radius = self.config.get('nozzle', 'inner_diameter', 0.2) / 2
        
        # Scale up for visibility and canvas size (multiply by 10 for visualization, then by scale_factor)
        outer_radius_scaled = outer_radius * 10 * scale_factor
        inner_radius_scaled = inner_radius * 10 * scale_factor
        
        # Create group for the nozzle ring with flip animation
        f.write(f'  <g transform="translate({x:.2f},{y:.2f})" opacity="0">\n')
        
        # Flip animation: scale from 0 to 1 with a "flip" effect (preserving translation)
        f.write(f'    <animateTransform attributeName="transform" type="scale" '
                f'values="0,0;0.2,1.2;1.1,0.9;1,1" dur="0.3s" '
                f'begin="{current_time:.2f}s" fill="freeze" additive="sum"/>\n')
        
        # Opacity animation
        f.write(f'    <animate attributeName="opacity" values="0;1;1;0.7" '
                f'dur="{animation_duration}s" begin="{current_time:.2f}s" '
                f'repeatCount="indefinite"/>\n')
        
        # Outer ring (nozzle contact area)
        ring_color = self._get_ring_color(color)
        f.write(f'    <circle cx="0" cy="0" r="{outer_radius_scaled:.2f}" '
                f'fill="{ring_color}" stroke="{color}" stroke-width="{0.5*scale_factor}" opacity="0.8"/>\n')
        
        # Inner ring (heated zone)
        inner_color = self._get_inner_ring_color(color)
        f.write(f'    <circle cx="0" cy="0" r="{inner_radius_scaled:.2f}" '
                f'fill="{inner_color}" opacity="0.9"/>\n')
        
        # Heat effect (subtle glow)
        f.write(f'    <circle cx="0" cy="0" r="{outer_radius_scaled * 1.3:.2f}" '
                f'fill="{ring_color}" opacity="0.1">\n')
        f.write(f'      <animate attributeName="opacity" values="0.1;0.3;0.1" '
                f'dur="1s" begin="{current_time:.2f}s" repeatCount="indefinite"/>\n')
        f.write('    </circle>\n')
        
        # Center dot (weld point) - scale radius
        center_dot_radius = 0.5 * scale_factor
        f.write(f'    <circle cx="0" cy="0" r="{center_dot_radius}" fill="{color}"/>\n')
        
        f.write('  </g>\n')

    def _get_ring_color(self, weld_color: str) -> str:
        """Get the ring color based on weld type."""
        if weld_color == 'blue':
            return '#87CEEB'  # Light blue for light welds
        else:
            return '#FFB347'  # Orange for normal welds (heated metal)

    def _get_inner_ring_color(self, weld_color: str) -> str:
        """Get the inner ring color based on weld type."""
        if weld_color == 'blue':
            return '#4169E1'  # Royal blue for light welds
        else:
            return '#FF6347'  # Tomato red for normal welds (hot zone)

    def _write_legend(self, f: TextIO, height: float) -> None:
        """Write legend explaining weld types with nozzle ring examples and scale bar."""
        scale_factor = 3.0
        legend_y = height - 80  # More space for scale bar
        font_size = 10 * scale_factor
        
        f.write(f'  <text x="{30*scale_factor}" y="{legend_y}" font-family="Arial" font-size="{font_size}" '
                f'fill="gray">Legend:</text>\n')
        
        # Normal welds - orange nozzle ring (scaled)
        normal_x = 180 * scale_factor
        f.write(f'  <g transform="translate({normal_x},{legend_y-12*scale_factor})">\n')
        f.write(f'    <circle cx="0" cy="0" r="{6*scale_factor}" fill="#FFB347" stroke="black" stroke-width="{scale_factor}"/>\n')
        f.write(f'    <circle cx="0" cy="0" r="{3*scale_factor}" fill="#FF6347"/>\n')
        f.write(f'    <circle cx="0" cy="0" r="{scale_factor}" fill="black"/>\n')
        f.write('  </g>\n')
        f.write(f'  <text x="{210*scale_factor}" y="{legend_y}" font-family="Arial" font-size="{9*scale_factor}" '
                f'fill="gray">Normal Welds (Hot)</text>\n')
        
        # Light welds - blue nozzle ring (scaled)
        light_x = 540 * scale_factor
        f.write(f'  <g transform="translate({light_x},{legend_y-12*scale_factor})">\n')
        f.write(f'    <circle cx="0" cy="0" r="{6*scale_factor}" fill="#87CEEB" stroke="blue" stroke-width="{scale_factor}"/>\n')
        f.write(f'    <circle cx="0" cy="0" r="{3*scale_factor}" fill="#4169E1"/>\n')
        f.write(f'    <circle cx="0" cy="0" r="{scale_factor}" fill="blue"/>\n')
        f.write('  </g>\n')
        f.write(f'  <text x="{570*scale_factor}" y="{legend_y}" font-family="Arial" font-size="{9*scale_factor}" '
                f'fill="gray">Light Welds (Warm)</text>\n')
        
        # Stop points (scaled)
        stop_x = 960 * scale_factor
        f.write(f'  <circle cx="{stop_x}" cy="{legend_y-12*scale_factor}" r="{12*scale_factor}" fill="red"/>\n')
        f.write(f'  <text x="{990*scale_factor}" y="{legend_y}" font-family="Arial" font-size="{9*scale_factor}" '
                f'fill="gray">Stop Points</text>\n')
        
        # Scale bar
        scale_bar_y = legend_y + 40 * scale_factor
        scale_bar_length = 10 * scale_factor  # 10mm scale bar
        scale_bar_x = 30 * scale_factor
        
        f.write(f'  <line x1="{scale_bar_x}" y1="{scale_bar_y}" x2="{scale_bar_x + scale_bar_length}" y2="{scale_bar_y}" '
                f'stroke="black" stroke-width="{2*scale_factor}"/>\n')
        f.write(f'  <line x1="{scale_bar_x}" y1="{scale_bar_y-5*scale_factor}" x2="{scale_bar_x}" y2="{scale_bar_y+5*scale_factor}" '
                f'stroke="black" stroke-width="{2*scale_factor}"/>\n')
        f.write(f'  <line x1="{scale_bar_x + scale_bar_length}" y1="{scale_bar_y-5*scale_factor}" x2="{scale_bar_x + scale_bar_length}" y2="{scale_bar_y+5*scale_factor}" '
                f'stroke="black" stroke-width="{2*scale_factor}"/>\n')
        f.write(f'  <text x="{scale_bar_x + scale_bar_length/2}" y="{scale_bar_y + 20*scale_factor}" text-anchor="middle" '
                f'font-family="Arial" font-size="{8*scale_factor}" fill="black">10mm</text>\n')
        
        # Nozzle info (scaled)
        outer_diameter = self.config.get('nozzle', 'outer_diameter', 0.4)
        inner_diameter = self.config.get('nozzle', 'inner_diameter', 0.2)
        f.write(f'  <text x="{30*scale_factor}" y="{legend_y+80*scale_factor}" font-family="Arial" font-size="{8*scale_factor}" '
                f'fill="gray">Nozzle: {outer_diameter}mm OD, {inner_diameter}mm ID (30x scale)</text>\n')

    def _write_svg_footer(self, f: TextIO) -> None:
        """Write SVG footer."""
        f.write('</svg>\n')
