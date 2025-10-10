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

    def generate_file(
        self,
        weld_paths: List[WeldPath],
        output_path: str | Path,
        weld_sequence: str = "farthest",
    ) -> None:
        """Generate animated SVG file from weld paths.

        Args:
            weld_paths: List of weld paths to animate
            output_path: Path to output SVG file
            weld_sequence: Welding sequence algorithm ('linear', 'binary', 'farthest')
        """
        if not weld_paths:
            return

        output_path = Path(output_path)

        # Get animation configuration
        time_between_welds = self.config.get("animation", "time_between_welds")
        pause_time = self.config.get("animation", "pause_time")
        min_animation_duration = self.config.get("animation", "min_animation_duration")

        # Calculate bounds
        bounds = self._calculate_bounds(weld_paths)
        min_x, min_y, max_x, max_y = bounds

        # Add padding and scale up canvas (triple size)
        padding = 60  # Increased padding for larger canvas
        base_width = max_x - min_x + 2 * padding
        base_height = (
            max_y - min_y + 2 * padding + 120
        )  # Extra space for messages, legend, and scale bar

        # Triple the canvas size for better text visibility
        width = base_width * 3
        height = base_height * 3

        # Calculate total animation time
        total_weld_points = sum(
            len(path.points) for path in weld_paths if path.weld_type != "stop"
        )
        total_pause_time = sum(
            pause_time for path in weld_paths if path.weld_type == "stop"
        )
        calculated_duration = total_weld_points * time_between_welds + total_pause_time
        animation_duration = max(min_animation_duration, calculated_duration)

        with open(output_path, "w") as f:
            self._write_svg_header(f, width, height)
            self._write_title_and_info(
                f, width, animation_duration, time_between_welds, pause_time
            )
            self._write_animation_elements(
                f,
                weld_paths,
                bounds,
                padding,
                animation_duration,
                time_between_welds,
                pause_time,
                weld_sequence,
            )
            self._write_legend(f, height)
            self._write_message_box(f, width, height)
            self._write_svg_footer(f)

    def _calculate_bounds(
        self, weld_paths: List[WeldPath]
    ) -> tuple[float, float, float, float]:
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
        f.write(
            f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">\n'
        )
        f.write('  <rect width="100%" height="100%" fill="white"/>\n')

    def _write_title_and_info(
        self,
        f: TextIO,
        width: float,
        animation_duration: float,
        time_between_welds: float,
        pause_time: float,
    ) -> None:
        """Write title and timing information."""
        scale_factor = 3.0

        f.write(
            f'  <text x="{width/2}" y="{20*scale_factor}" text-anchor="middle" font-family="Arial" '
            f'font-size="{8*scale_factor}" fill="black">SVG Welding Animation</text>\n'
        )

        f.write(
            f'  <text x="{width/2}" y="{35*scale_factor}" text-anchor="middle" font-family="Arial" '
            f'font-size="{6*scale_factor}" fill="gray">Duration: {animation_duration:.1f}s | '
            f"Weld interval: {time_between_welds}s | Pause time: {pause_time}s</text>\n"
        )

    def _write_animation_elements(
        self,
        f: TextIO,
        weld_paths: List[WeldPath],
        bounds: tuple[float, float, float, float],
        padding: float,
        animation_duration: float,
        time_between_welds: float,
        pause_time: float,
        weld_sequence: str,
    ) -> None:
        """Write animation elements for weld paths."""
        min_x, min_y, max_x, max_y = bounds

        # Calculate canvas dimensions (same logic as in generate_file)
        base_width = max_x - min_x + 2 * padding
        base_height = max_y - min_y + 2 * padding + 120
        width = base_width * 3
        height = base_height * 3
        current_time = 0.0
        scale_factor = 3.0  # Scale factor for tripled canvas size

        for path in weld_paths:
            # Handle stop points (pause messages)
            if path.weld_type == "stop":
                if path.points:
                    self._write_stop_point(
                        f,
                        path,
                        min_x,
                        min_y,
                        padding,
                        animation_duration,
                        current_time,
                        scale_factor,
                        pause_time,
                        width,
                        height,
                    )
                current_time += pause_time
                continue

            # Determine color based on weld type
            color = "blue" if path.weld_type == "light" else "black"

            # Process weld points in selected sequence order
            weld_order = self._generate_weld_order(path.points, weld_sequence)

            for point_index in weld_order:
                point = path.points[point_index]
                # Adjust coordinates with scale factor
                x = (point.x - min_x + padding) * scale_factor
                y = (point.y - min_y + padding + 40) * scale_factor  # Offset for header

                # Create realistic nozzle ring animation
                self._write_nozzle_ring(
                    f, x, y, color, animation_duration, current_time, scale_factor
                )

                current_time += time_between_welds

    def _generate_weld_order(self, points: list, weld_sequence: str) -> list[int]:
        """Generate welding order based on selected algorithm.

        Args:
            points: List of weld points
            weld_sequence: Algorithm to use ('linear', 'binary', 'farthest', 'skip')

        Returns:
            List of point indices in welding order
        """
        num_points = len(points)

        if weld_sequence == "linear":
            return self._generate_linear_order(num_points)
        elif weld_sequence == "binary":
            return self._generate_binary_subdivision_order(num_points)
        elif weld_sequence == "farthest":
            return self._generate_farthest_point_order(points)
        elif weld_sequence == "skip":
            return self._generate_skip_order(num_points)
        else:
            # Default to skip
            return self._generate_skip_order(num_points)

    def _generate_linear_order(self, num_points: int) -> list[int]:
        """Generate linear welding order (1, 2, 3, ...)."""
        return list(range(num_points))

    def _generate_farthest_point_order(self, points: list) -> list[int]:
        """Generate welding order using Greedy Farthest-Point Traversal.

        This algorithm places each dot at the position farthest from the most recent dot,
        which helps minimize thermal stress by maximizing distance between consecutive welds.

        Args:
            points: List of Point objects with x, y coordinates

        Returns:
            List of point indices in farthest-point order
        """
        if len(points) <= 1:
            return list(range(len(points)))

        order = []
        remaining = set(range(len(points)))

        # Start with the first point (arbitrary choice)
        current_idx = 0
        order.append(current_idx)
        remaining.remove(current_idx)

        while remaining:
            current_point = points[current_idx]
            max_distance = -1
            farthest_idx = None

            # Find the point farthest from current point
            for idx in remaining:
                candidate_point = points[idx]
                # Calculate Euclidean distance
                distance = (
                    (candidate_point.x - current_point.x) ** 2
                    + (candidate_point.y - current_point.y) ** 2
                ) ** 0.5

                if distance > max_distance:
                    max_distance = distance
                    farthest_idx = idx

            # Move to the farthest point
            order.append(farthest_idx)
            remaining.remove(farthest_idx)
            current_idx = farthest_idx

        return order

    def _generate_skip_order(self, num_points: int) -> list[int]:
        """Generate welding order using skip pattern.

        First prints every Nth dot (where N = skip_base_distance from config),
        then fills in the gaps. This provides excellent thermal distribution
        by ensuring maximum spacing between initial dots.

        Example with skip_base_distance=5 and 20 points:
        Pass 1: [0, 5, 10, 15] (every 5th dot)
        Pass 2: [1, 6, 11, 16] (offset by 1)
        Pass 3: [2, 7, 12, 17] (offset by 2)
        Pass 4: [3, 8, 13, 18] (offset by 3)
        Pass 5: [4, 9, 14, 19] (offset by 4)

        Args:
            num_points: Total number of points to weld

        Returns:
            List of point indices in skip order
        """
        if num_points <= 0:
            return []
        if num_points == 1:
            return [0]

        # Get skip distance from config
        skip_distance = self.config.sequencing.get("skip_base_distance", 5)

        order = []

        # Generate passes: first every skip_distance, then offset by 1, 2, etc.
        for offset in range(skip_distance):
            current_idx = offset
            while current_idx < num_points:
                order.append(current_idx)
                current_idx += skip_distance

        return order

    def _generate_binary_subdivision_order(self, num_points: int) -> list[int]:
        """Generate welding order using binary subdivision pattern.

        For a line with points [0,1,2,3,4,5,6], the order would be:
        1. First and last: [0, 6]
        2. Middle of entire range: [3]
        3. Middles of remaining gaps: [1, 5]
        4. Middles of remaining gaps: [2, 4]

        Args:
            num_points: Total number of points to weld

        Returns:
            List of point indices in binary subdivision order
        """
        if num_points <= 0:
            return []
        if num_points == 1:
            return [0]
        if num_points == 2:
            return [0, 1]

        order = []

        # Start with first and last points
        order.extend([0, num_points - 1])

        # Use a queue to track segments that need subdivision
        segments_to_subdivide = [(0, num_points - 1)]

        while segments_to_subdivide:
            start, end = segments_to_subdivide.pop(0)

            # Find middle point of this segment
            if end - start > 1:
                mid = (start + end) // 2
                order.append(mid)

                # Add new segments to subdivide (if they have gaps)
                if mid - start > 1:
                    segments_to_subdivide.append((start, mid))
                if end - mid > 1:
                    segments_to_subdivide.append((mid, end))

        return order

    def _write_stop_point(
        self,
        f: TextIO,
        path: WeldPath,
        min_x: float,
        min_y: float,
        padding: float,
        animation_duration: float,
        current_time: float,
        scale_factor: float,
        pause_time: float,
        width: float,
        height: float,
    ) -> None:
        """Write stop point as red circle with immediate user message display."""
        point = path.points[0]
        x = (point.x - min_x + padding) * scale_factor
        y = (point.y - min_y + padding + 40) * scale_factor  # Offset for header

        # Use original radius if it's a circle, otherwise use default
        if path.element_type == "circle" and path.element_radius is not None:
            radius = max(
                2.0, min(path.element_radius, 8.0)
            )  # Clamp between 2-8 for visibility
        else:
            radius = 3.0  # Default radius for non-circle stop points

        # Get pause message
        message = path.pause_message or "Manual intervention required"
        safe_message = (
            message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )

        # Scale message box and text for larger canvas
        box_width = 120 * scale_factor
        box_height = 25 * scale_factor
        font_size = 3 * scale_factor  # Reduced from 9 to 3 (1/3 size)

        # Update the static message box with this pause message
        # Position text in the message box (need to calculate box position)
        # For now, position relative to typical message box location
        msg_box_x = width - 360  # Approximate message box x position
        msg_box_y = height - 25  # Approximate message box text y position

        f.write(
            f'  <text x="{msg_box_x}" y="{msg_box_y}" font-family="Arial" font-size="11" fill="#e74c3c" opacity="0">\n'
        )
        f.write(
            f'    <animate attributeName="opacity" values="0;1;1;0" '
            f'dur="{pause_time:.2f}s" begin="{current_time:.2f}s" fill="freeze"/>\n'
        )
        f.write(f"    ⚠ {safe_message}\n")
        f.write("  </text>\n")

        # Red circle with flip animation (similar to nozzle rings but simpler)
        f.write(f'  <g transform="translate({x:.2f},{y:.2f})" opacity="0">\n')

        # Flip animation for stop point (preserving translation)
        f.write(
            f'    <animateTransform attributeName="transform" type="scale" '
            f'values="0,0;0.2,1.2;1.1,0.9;1,1" dur="0.3s" '
            f'begin="{current_time:.2f}s" fill="freeze" additive="sum"/>\n'
        )

        # Opacity animation - show only during pause duration
        f.write(
            f'    <animate attributeName="opacity" values="0;1;1;0" '
            f'dur="{pause_time:.2f}s" begin="{current_time:.2f}s" fill="freeze"/>\n'
        )

        # Red circle (stop indicator) - scale radius
        scaled_radius = radius * scale_factor
        f.write(
            f'    <circle cx="0" cy="0" r="{scaled_radius:.1f}" fill="red" '
            f'stroke="darkred" stroke-width="{scale_factor}"/>\n'
        )

        f.write("  </g>\n")

    def _write_nozzle_ring(
        self,
        f: TextIO,
        x: float,
        y: float,
        color: str,
        animation_duration: float,
        current_time: float,
        scale_factor: float,
    ) -> None:
        """Write animated nozzle ring that flips into existence."""
        # Get nozzle dimensions from config
        outer_radius = self.config.get("nozzle", "outer_diameter", 0.4) / 2
        inner_radius = self.config.get("nozzle", "inner_diameter", 0.2) / 2

        # Scale up for visibility and canvas size (multiply by 10 for visualization, then by scale_factor)
        outer_radius_scaled = outer_radius * 10 * scale_factor
        inner_radius_scaled = inner_radius * 10 * scale_factor

        # Create group for the nozzle ring with flip animation
        f.write(f'  <g transform="translate({x:.2f},{y:.2f})" opacity="0">\n')

        # Instant appearance - no flip animation, just immediate visibility
        f.write(
            f'    <animate attributeName="opacity" values="0;1" '
            f'dur="0.01s" begin="{current_time:.2f}s" fill="freeze"/>\n'
        )

        # Single colored circle with precise nozzle outer diameter (not enlarged for visibility)
        # Use actual scale: outer_radius * scale_factor (no 10x enlargement)
        actual_radius = outer_radius * scale_factor
        f.write(
            f'    <circle cx="0" cy="0" r="{actual_radius:.2f}" '
            f'fill="{color}" stroke="{color}" stroke-width="0.5" opacity="0.8"/>\n'
        )

        f.write("  </g>\n")

    def _get_ring_color(self, weld_color: str) -> str:
        """Get the ring color based on weld type."""
        if weld_color == "blue":
            return "#87CEEB"  # Light blue for light welds
        else:
            return "#FFB347"  # Orange for normal welds (heated metal)

    def _get_inner_ring_color(self, weld_color: str) -> str:
        """Get the inner ring color based on weld type."""
        if weld_color == "blue":
            return "#4169E1"  # Royal blue for light welds
        else:
            return "#FF6347"  # Tomato red for normal welds (hot zone)

    def _write_legend(self, f: TextIO, height: float) -> None:
        """Write legend explaining weld types with nozzle ring examples and scale bar."""
        scale_factor = 3.0
        legend_start_y = height - 140  # More space for scale bar at top
        font_size = 2.5 * scale_factor
        row_height = 20  # Space between legend rows
        icon_x = 30 * scale_factor  # X position for icons
        text_x = icon_x + 30  # X position for text (30px after icon)

        # Scale bar at the top - black rectangle with 10:1 aspect ratio
        scale_bar_length = 30  # 10mm represented as 30 pixels (3x scale)
        scale_bar_height = 3  # 1mm represented as 3 pixels (10:1 ratio)
        scale_bar_x = icon_x
        scale_bar_y = legend_start_y

        f.write(
            f'  <rect x="{scale_bar_x}" y="{scale_bar_y}" width="{scale_bar_length}" height="{scale_bar_height}" '
            f'fill="black"/>\n'
        )
        f.write(
            f'  <text x="{scale_bar_x + scale_bar_length/2}" y="{scale_bar_y + 18}" text-anchor="middle" '
            f'font-family="Arial" font-size="10" fill="black">10mm</text>\n'
        )

        # Legend title (moved down to accommodate scale bar)
        legend_title_y = scale_bar_y + 35
        f.write(
            f'  <text x="{icon_x}" y="{legend_title_y}" font-family="Arial" font-size="{font_size}" '
            f'fill="gray">Legend:</text>\n'
        )

        # Legend table group
        f.write(f'  <g id="legend-table">\n')

        # Row 1: Normal welds - larger dots for better color perception
        row1_y = legend_title_y + row_height
        dot_radius = 6  # Larger radius for better color visibility
        f.write(f'    <g id="normal-welds-row">\n')
        f.write(
            f'      <circle cx="{icon_x}" cy="{row1_y-6}" r="{dot_radius}" fill="black" stroke="black" stroke-width="1" opacity="0.9"/>\n'
        )
        f.write(
            f'      <text x="{text_x}" y="{row1_y}" font-family="Arial" font-size="{font_size*0.8}" '
            f'fill="gray">Normal Welds (Hot)</text>\n'
        )
        f.write(f"    </g>\n")

        # Row 2: Light welds - larger dots for better color perception
        row2_y = row1_y + row_height
        f.write(f'    <g id="light-welds-row">\n')
        f.write(
            f'      <circle cx="{icon_x}" cy="{row2_y-6}" r="{dot_radius}" fill="blue" stroke="blue" stroke-width="1" opacity="0.9"/>\n'
        )
        f.write(
            f'      <text x="{text_x}" y="{row2_y}" font-family="Arial" font-size="{font_size*0.8}" '
            f'fill="gray">Light Welds (Warm)</text>\n'
        )
        f.write(f"    </g>\n")

        # Row 3: Stop points - larger for consistency
        row3_y = row2_y + row_height
        f.write(f'    <g id="stop-points-row">\n')
        f.write(
            f'      <circle cx="{icon_x}" cy="{row3_y-6}" r="{dot_radius}" fill="red" stroke="red" stroke-width="1" opacity="0.9"/>\n'
        )
        f.write(
            f'      <text x="{text_x}" y="{row3_y}" font-family="Arial" font-size="{font_size*0.8}" '
            f'fill="gray">Stop Points (Pause)</text>\n'
        )
        f.write(f"    </g>\n")

        f.write(f"  </g>\n")

        # Nozzle info - positioned below legend table
        nozzle_info_y = row3_y + 30
        outer_diameter = self.config.get("nozzle", "outer_diameter", 0.4)
        inner_diameter = self.config.get("nozzle", "inner_diameter", 0.2)
        f.write(
            f'  <text x="{icon_x}" y="{nozzle_info_y}" font-family="Arial" font-size="8" '
            f'fill="gray">Nozzle: {outer_diameter}mm OD, {inner_diameter}mm ID (actual scale)</text>\n'
        )

    def _write_message_box(self, f: TextIO, width: float, height: float) -> None:
        """Write static message box near the legend for pause notifications."""
        # Message box positioned with proper margins to stay within canvas
        box_width = 350
        box_height = 60
        margin = 10  # Small margin from canvas edge

        # Position box in bottom right with margin from actual canvas width
        box_x = width - box_width - margin
        box_y = height - box_height - margin

        # Static message box background
        f.write(
            f'  <rect id="message-box" x="{box_x}" y="{box_y}" width="{box_width}" height="{box_height}" '
            f'fill="#f0f8ff" stroke="#4682b4" stroke-width="2" rx="8" ry="8" opacity="0.9"/>\n'
        )

        # Message box title
        f.write(
            f'  <text x="{box_x + 10}" y="{box_y + 20}" font-family="Arial" font-size="12" '
            f'font-weight="bold" fill="#2c3e50">Notifications:</text>\n'
        )

        # Default message (will be updated by pause messages)
        f.write(
            f'  <text id="message-text-default" x="{box_x + 10}" y="{box_y + 45}" font-family="Arial" '
            f'font-size="11" fill="#7f8c8d">No active notifications</text>\n'
        )

        # Dynamic message text for pause notifications (initially hidden)
        f.write(
            f'  <text id="message-text-active" x="{box_x + 10}" y="{box_y + 45}" font-family="Arial" '
            f'font-size="11" fill="#e74c3c" opacity="0">⚠ Pause message will appear here</text>\n'
        )

    def _write_svg_footer(self, f: TextIO) -> None:
        """Write SVG footer."""
        f.write("</svg>\n")
