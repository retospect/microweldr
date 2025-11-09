"""Animation generation functionality."""

import io
from pathlib import Path
from typing import List, TextIO

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import PillowWriter
from PIL import Image

from microweldr.core.config import Config
from microweldr.core.models import WeldPath


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

        # Add 2mm boundary around SVG content
        padding = 2.0  # 2mm boundary as requested
        base_width = max_x - min_x + 2 * padding
        base_height = (
            max_y - min_y + 2 * padding + 30
        )  # Space for scale bar below content

        # Triple the canvas size for better text visibility
        width = base_width * 3
        height = base_height * 3

        # Calculate total animation time
        total_weld_points = sum(
            len(path.points)
            for path in weld_paths
            if path.weld_type not in ["stop", "pipette"]
        )
        total_pause_time = sum(
            pause_time for path in weld_paths if path.weld_type in ["stop", "pipette"]
        )
        calculated_duration = total_weld_points * time_between_welds + total_pause_time
        animation_duration = max(min_animation_duration, calculated_duration)

        with open(output_path, "w") as f:
            self._write_svg_header(f, width, height)
            # Title and timing info removed per user request
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
            self._write_scale_bar(f, width, height, bounds, padding)
            self._write_svg_footer(f)

    def generate_png_file(
        self,
        weld_paths: List[WeldPath],
        output_path: Path,
        weld_sequence: str = "linear",
    ) -> None:
        """Generate animated PNG file showing the welding process."""
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

        # Add 2mm boundary around SVG content
        padding = 2.0  # 2mm boundary as requested

        # Calculate content dimensions in mm
        content_width_mm = max_x - min_x + 2 * padding
        content_height_mm = max_y - min_y + 2 * padding

        # Set up matplotlib figure with proper aspect ratio
        dpi = 100
        fig_width = content_width_mm / 25.4 * 2  # Convert mm to inches, scale up 2x
        fig_height = content_height_mm / 25.4 * 2

        fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)
        ax.set_xlim(min_x - padding, max_x + padding)
        ax.set_ylim(min_y - padding, max_y + padding)
        ax.set_aspect("equal")
        ax.axis("off")  # Remove axes for clean appearance

        # Set white background
        fig.patch.set_facecolor("white")

        # Calculate total animation time
        total_weld_points = sum(
            len(path.points)
            for path in weld_paths
            if path.weld_type not in ["stop", "pipette"]
        )
        total_pause_time = sum(
            pause_time for path in weld_paths if path.weld_type in ["stop", "pipette"]
        )
        calculated_duration = total_weld_points * time_between_welds + total_pause_time
        animation_duration = max(min_animation_duration, calculated_duration)

        # Generate animation frames
        frames = self._generate_png_frames(
            weld_paths,
            bounds,
            padding,
            animation_duration,
            time_between_welds,
            pause_time,
            weld_sequence,
            ax,
        )

        # Create animated PNG
        fps = 10  # 10 frames per second
        frame_duration = 1000 / fps  # Duration in milliseconds

        # Save as animated PNG using Pillow
        if frames:
            frames[0].save(
                output_path,
                save_all=True,
                append_images=frames[1:],
                duration=frame_duration,
                loop=0,  # Loop forever
                optimize=True,
            )

        plt.close(fig)

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
            # Handle pipette stops (microfluidic filling)
            elif path.weld_type == "pipette":
                if path.points:
                    self._write_pipette_point(
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
            color = "blue" if path.weld_type == "frangible" else "black"

            # Process weld points using multi-pass logic to match G-code execution
            multipass_points = self._generate_multipass_points_for_animation(
                path.points, path.weld_type
            )

            for point in multipass_points:
                # Adjust coordinates with scale factor
                x = (point.x - min_x + padding) * scale_factor
                y = (
                    point.y - min_y + padding
                ) * scale_factor  # No header offset needed

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
        y = (point.y - min_y + padding) * scale_factor  # No header offset needed

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

    def _write_pipette_point(
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
        """Write pipette point as pink/magenta circle with pipetting message display."""
        point = path.points[0]
        x = (point.x - min_x + padding) * scale_factor
        y = (point.y - min_y + padding) * scale_factor  # No header offset needed

        # Use element radius if available, otherwise default
        if path.element_type == "circle" and path.element_radius:
            radius = max(
                2.0, min(path.element_radius, 8.0)
            )  # Clamp between 2-8 for visibility
        else:
            radius = 3.0  # Default radius for non-circle pipette points

        # Get pipette message
        message = path.pause_message or "Pipette filling required"

        # Message display area - positioned above the pipette point
        message_x = x
        message_y = y - (radius + 5) * scale_factor - 20

        # Ensure message stays within bounds
        message_x = max(10, min(message_x, width - 200))
        message_y = max(30, message_y)

        # Message background and text
        f.write(f'  <g opacity="0">\n')

        # Opacity animation for message - show during pause
        f.write(
            f'    <animate attributeName="opacity" values="0;1;1;0" '
            f'dur="{pause_time:.2f}s" begin="{current_time:.2f}s" fill="freeze"/>\n'
        )

        # Message background (rounded rectangle)
        f.write(
            f'    <rect x="{message_x-5}" y="{message_y-15}" width="190" height="25" '
            f'fill="rgba(255,0,255,0.9)" stroke="magenta" stroke-width="1" rx="3"/>\n'
        )

        # Message text
        f.write(
            f'    <text x="{message_x}" y="{message_y}" font-family="Arial, sans-serif" '
            f'font-size="12" fill="white" font-weight="bold">{message}</text>\n'
        )

        f.write("  </g>\n")

        # Pipette point with flip animation
        f.write(f'  <g transform="translate({x:.2f},{y:.2f})" opacity="0">\n')

        # Flip animation for pipette point
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

        # Pink/magenta circle (pipette indicator) - scale radius
        scaled_radius = radius * scale_factor
        f.write(
            f'    <circle cx="0" cy="0" r="{scaled_radius:.1f}" fill="magenta" '
            f'stroke="darkmagenta" stroke-width="{scale_factor}"/>\n'
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
        # Get nozzle dimensions from config (these are diameters, not radii)
        outer_diameter = self.config.get("nozzle", "outer_diameter", 1.1)  # mm
        inner_diameter = self.config.get("nozzle", "inner_diameter", 0.2)  # mm

        # Convert to radius
        outer_radius = outer_diameter / 2
        inner_radius = inner_diameter / 2

        # Create group for the nozzle ring with flip animation
        f.write(f'  <g transform="translate({x:.2f},{y:.2f})" opacity="0">\n')

        # Instant appearance - no flip animation, just immediate visibility
        f.write(
            f'    <animate attributeName="opacity" values="0;1" '
            f'dur="0.01s" begin="{current_time:.2f}s" fill="freeze"/>\n'
        )

        # Single colored circle with precise nozzle outer radius scaled properly
        actual_radius = outer_radius * scale_factor
        f.write(
            f'    <circle cx="0" cy="0" r="{actual_radius:.2f}" '
            f'fill="{color}" stroke="{color}" stroke-width="0.5" opacity="0.8"/>\n'
        )

        f.write("  </g>\n")

    def _get_ring_color(self, weld_color: str) -> str:
        """Get the ring color based on weld type."""
        if weld_color == "blue":
            return "#87CEEB"  # Light blue for frangible welds
        else:
            return "#FFB347"  # Orange for normal welds (heated metal)

    def _get_inner_ring_color(self, weld_color: str) -> str:
        """Get the inner ring color based on weld type."""
        if weld_color == "blue":
            return "#4169E1"  # Royal blue for frangible welds
        else:
            return "#FF6347"  # Tomato red for normal welds (hot zone)

    def _write_scale_bar(
        self,
        f: TextIO,
        width: float,
        height: float,
        bounds: tuple[float, float, float, float],
        padding: float,
    ) -> None:
        """Write red scale bar right outside the bounding box margin."""
        scale_factor = 3.0
        min_x, min_y, max_x, max_y = bounds

        # Position scale bar right outside the bounding box (below content area)
        scale_bar_length = 30  # 10mm represented as 30 pixels (3x scale)
        scale_bar_height = 3  # 1mm represented as 3 pixels (10:1 ratio)

        # Position just below the content bounding box (outside the 2mm margin)
        content_bottom_y = (max_y - min_y + padding) * scale_factor
        scale_bar_x = padding * scale_factor  # Align with left edge of content
        scale_bar_y = content_bottom_y + 10  # 10 pixels below content area

        f.write(
            f'  <rect x="{scale_bar_x}" y="{scale_bar_y}" width="{scale_bar_length}" height="{scale_bar_height}" '
            f'fill="red"/>\n'
        )
        f.write(
            f'  <text x="{scale_bar_x + scale_bar_length/2}" y="{scale_bar_y + 18}" text-anchor="middle" '
            f'font-family="Arial" font-size="10" fill="red">10mm</text>\n'
        )

    def _generate_png_frames(
        self,
        weld_paths: List[WeldPath],
        bounds: tuple[float, float, float, float],
        padding: float,
        animation_duration: float,
        time_between_welds: float,
        pause_time: float,
        weld_sequence: str,
        ax,
    ) -> List[Image.Image]:
        """Generate PNG frames for animated PNG."""
        frames = []
        min_x, min_y, max_x, max_y = bounds
        current_time = 0.0

        # Calculate total frames needed
        fps = 10
        total_frames = int(animation_duration * fps)
        frame_duration = animation_duration / total_frames

        # Track which points have been welded at each frame
        welded_points = set()

        for frame_idx in range(total_frames):
            ax.clear()
            ax.set_xlim(min_x - padding, max_x + padding)
            ax.set_ylim(
                min_y - padding, max_y + padding + 20
            )  # Extra space for scale bar
            ax.set_aspect("equal")
            ax.axis("off")
            ax.set_facecolor("white")

            # Add scale bar
            self._add_scale_bar_to_plot(ax, bounds, padding)

            # Process each weld path
            path_time = 0.0
            for path in weld_paths:
                if path.weld_type in ["stop", "pipette"]:
                    # Handle pause points
                    if path_time <= current_time < path_time + pause_time:
                        point = path.points[0]
                        color = "red" if path.weld_type == "stop" else "magenta"
                        radius = 3.0
                        circle = patches.Circle(
                            (point.x, point.y),
                            radius,
                            color=color,
                            alpha=0.8,
                            zorder=10,
                        )
                        ax.add_patch(circle)
                    path_time += pause_time
                else:
                    # Handle weld points - use multi-pass logic to match G-code execution
                    multipass_points = self._generate_multipass_points_for_animation(
                        path.points, path.weld_type
                    )
                    for i, point in enumerate(multipass_points):
                        point_time = path_time + (i * time_between_welds)
                        if point_time <= current_time:
                            color = "blue" if path.weld_type == "frangible" else "black"
                            # Use actual nozzle diameter from config
                            nozzle_diameter = self.config.get(
                                "nozzle", "outer_diameter", 1.1
                            )
                            radius = nozzle_diameter / 2  # Convert diameter to radius
                            circle = patches.Circle(
                                (point.x, point.y),
                                radius,
                                facecolor=color,
                                edgecolor="none",
                                alpha=0.8,
                                zorder=5,
                                antialiased=False,
                            )
                            ax.add_patch(circle)
                    path_time += len(multipass_points) * time_between_welds

            # Convert plot to PIL Image
            buf = io.BytesIO()
            plt.savefig(
                buf,
                format="png",
                dpi=300,
                bbox_inches="tight",
                facecolor="white",
                edgecolor="none",
            )
            buf.seek(0)
            frame = Image.open(buf)
            frames.append(frame.copy())
            buf.close()

            current_time += frame_duration

        return frames

    def _generate_multipass_points_for_animation(self, original_points, weld_type):
        """Generate points for animation that match G-code multi-pass execution order exactly."""
        from ..core.weld_point_generator import WeldPointGenerator
        from ..core.models import WeldPoint

        # Get config values for multi-pass welding (same as G-code generator)
        config_section = (
            "frangible_welds" if weld_type == "frangible" else "normal_welds"
        )
        # Use exact same spacing as G-code generator for accurate preview
        final_spacing = self.config.get(config_section, "dot_spacing", 0.5)  # mm
        initial_spacing = self.config.get(
            config_section, "initial_dot_spacing", 6.0
        )  # mm
        num_passes = self.config.get("sequencing", "passes", 4)

        # Use shared WeldPointGenerator to ensure exact match with G-code
        return WeldPointGenerator.get_all_weld_points(
            original_points, initial_spacing, final_spacing, num_passes
        )

    def _add_scale_bar_to_plot(
        self, ax, bounds: tuple[float, float, float, float], padding: float
    ) -> None:
        """Add red scale bar to matplotlib plot."""
        min_x, min_y, max_x, max_y = bounds

        # Position scale bar (same logic as SVG version but in plot coordinates)
        scale_bar_length = 10.0  # 10mm in real coordinates
        scale_bar_height = 2.0  # 2mm in real coordinates (make it more visible)

        # Position with significant clearance from content area to avoid overlap
        scale_bar_x = min_x - padding + 1  # Align with left edge of content
        scale_bar_y = (
            max_y + padding + 15
        )  # Far above content area with large clearance

        # Add scale bar rectangle with thicker appearance
        rect = patches.Rectangle(
            (scale_bar_x, scale_bar_y),
            scale_bar_length,
            scale_bar_height,
            facecolor="red",
            edgecolor="darkred",
            linewidth=1,
            zorder=15,
        )
        ax.add_patch(rect)

        # Add scale bar text
        ax.text(
            scale_bar_x + scale_bar_length / 2,
            scale_bar_y + scale_bar_height + 1,
            "10mm",
            ha="center",
            va="bottom",
            fontsize=10,
            color="red",
            weight="bold",
            zorder=15,
        )

    def _write_svg_footer(self, f: TextIO) -> None:
        """Write SVG footer."""
        f.write("</svg>\n")
