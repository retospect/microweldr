"""GIF animation subscriber that generates animated GIF files from weld points."""

import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import time

try:
    from PIL import Image, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from ..core.events import Event, EventType, EventSubscriber
from ..core.config import Config

logger = logging.getLogger(__name__)


class GIFAnimationSubscriber(EventSubscriber):
    """Generates animated GIF from weld points using PIL."""

    def __init__(self, output_path: Path, config: Config):
        """Initialize GIF animation subscriber."""
        if not PIL_AVAILABLE:
            raise ImportError("PIL (Pillow) is required for GIF animation generation")

        self.output_path = Path(output_path)
        self.config = config
        self.points = []
        self.paths = {}
        self.current_path_id = None
        self.bounds = {"min_x": None, "min_y": None, "max_x": None, "max_y": None}
        # Track points in welding sequence for animation
        self.weld_sequence = []

        # Animation settings
        self.width = 800
        self.height = 600
        self.margin = 50
        # Point radius will be calculated based on nozzle size and scale
        self.base_point_radius = (
            0.5  # Minimum radius in pixels (allows very small dots)
        )
        self.colors = {
            "normal": "#000080",  # Blue
            "frangible": "#FF0000",  # Red
            "stop": "#800080",  # Purple
            "pipette": "#FF00FF",  # Magenta
        }

    def get_subscribed_events(self) -> List[EventType]:
        """Return list of events this subscriber handles."""
        return [EventType.PATH_PROCESSING, EventType.OUTPUT_GENERATION]

    def handle_event(self, event: Event) -> None:
        """Handle incoming events."""
        try:
            if event.event_type == EventType.PATH_PROCESSING:
                self._handle_path_event(event)
            elif event.event_type == EventType.OUTPUT_GENERATION:
                self._handle_output_event(event)
        except Exception as e:
            logger.exception(f"Error in PNG animation subscriber: {e}")

    def _handle_path_event(self, event: Event) -> None:
        """Handle path processing events."""
        # Extract action from event data
        if hasattr(event, "action"):
            action = event.action
        else:
            action = event.data.get("action", "")

        if action == "path_start":
            if hasattr(event, "path_id"):
                self.current_path_id = event.path_id
            else:
                self.current_path_id = event.data.get(
                    "path_id", f"path_{len(self.paths)}"
                )

            self.paths[self.current_path_id] = {"points": [], "weld_type": "normal"}

        elif action == "point_added":
            if self.current_path_id:
                # Extract point data
                if hasattr(event, "point"):
                    point_data = event.point
                else:
                    point_data = event.data.get("point", {})

                if point_data:
                    x = float(point_data.get("x", 0))
                    y = float(point_data.get("y", 0))
                    weld_type = point_data.get("weld_type", "normal")

                    point_info = {"x": x, "y": y, "weld_type": weld_type}

                    self.paths[self.current_path_id]["points"].append(point_info)
                    self.paths[self.current_path_id]["weld_type"] = weld_type

                    # Add to weld sequence for animation (in order received)
                    self.weld_sequence.append(
                        {
                            "x": x,
                            "y": y,
                            "weld_type": weld_type,
                            "path_id": self.current_path_id,
                        }
                    )

                    # Update bounds
                    self._update_bounds(x, y)

        elif action == "path_complete":
            # Path is complete, nothing special to do
            pass

    def _handle_output_event(self, event: Event) -> None:
        """Handle output generation events."""
        action = event.data.get("action", "")

        if action == "processing_complete":
            self._generate_png_animation()

    def _update_bounds(self, x: float, y: float) -> None:
        """Update coordinate bounds for proper scaling."""
        if self.bounds["min_x"] is None or x < self.bounds["min_x"]:
            self.bounds["min_x"] = x
        if self.bounds["max_x"] is None or x > self.bounds["max_x"]:
            self.bounds["max_x"] = x
        if self.bounds["min_y"] is None or y < self.bounds["min_y"]:
            self.bounds["min_y"] = y
        if self.bounds["max_y"] is None or y > self.bounds["max_y"]:
            self.bounds["max_y"] = y

    def _calculate_transform(self) -> Tuple[float, float, float]:
        """Calculate transformation parameters for coordinate mapping."""
        if self.bounds["min_x"] is None:
            return 1.0, 0.0, 0.0  # No points, use identity transform

        # Calculate data dimensions
        data_width = self.bounds["max_x"] - self.bounds["min_x"]
        data_height = self.bounds["max_y"] - self.bounds["min_y"]

        # Avoid division by zero
        if data_width == 0:
            data_width = 1
        if data_height == 0:
            data_height = 1

        # Calculate available space (with margins)
        available_width = self.width - 2 * self.margin
        available_height = self.height - 2 * self.margin

        # Calculate scale to fit data in available space
        scale_x = available_width / data_width
        scale_y = available_height / data_height
        scale = min(scale_x, scale_y)  # Use smaller scale to maintain aspect ratio

        # Calculate offsets to center the data
        offset_x = (
            self.margin
            + (available_width - data_width * scale) / 2
            - self.bounds["min_x"] * scale
        )
        offset_y = (
            self.margin
            + (available_height - data_height * scale) / 2
            - self.bounds["min_y"] * scale
        )

        return scale, offset_x, offset_y

    def _calculate_point_radius(self, scale: float) -> int:
        """Calculate point radius based on actual welding spot size from nozzle configuration."""
        # Get welding spot diameter from nozzle outer diameter configuration
        weld_spot_diameter = self.config.get("nozzle", "outer_diameter", 2.0)  # mm

        # Calculate radius in pixels based on real-world welding spot size
        weld_spot_radius_pixels = (weld_spot_diameter / 2) * scale

        # Use the larger of: scaled weld spot size or minimum base radius
        point_radius = max(self.base_point_radius, int(weld_spot_radius_pixels))

        # Cap at reasonable maximum to avoid huge points
        return min(point_radius, 20)

    def _transform_point(
        self, x: float, y: float, scale: float, offset_x: float, offset_y: float
    ) -> Tuple[int, int]:
        """Transform data coordinates to image coordinates."""
        img_x = int(x * scale + offset_x)
        img_y = int(y * scale + offset_y)
        return img_x, img_y

    def _generate_png_animation(self) -> None:
        """Generate animated GIF showing weld progression."""
        try:
            if not self.paths:
                logger.warning("No paths to animate")
                return

            self._generate_animated_gif()

        except Exception as e:
            logger.error(f"Failed to generate animation: {e}")
            raise

    def _generate_animated_gif(self) -> None:
        """Generate animated GIF showing weld sequence progression."""
        # Calculate transformation
        scale, offset_x, offset_y = self._calculate_transform()

        # Calculate point radius based on nozzle size and scale
        point_radius = self._calculate_point_radius(scale)

        # Use the weld sequence (points in order they were received)
        if not self.weld_sequence:
            logger.warning("No points to animate")
            return

        frames = []
        frame_duration = 50  # milliseconds per frame (faster, uniform animation)

        # Create frames showing progressive welding - show every single point
        for frame_num in range(len(self.weld_sequence)):
            # Create frame
            img = Image.new("RGB", (self.width, self.height), "white")
            draw = ImageDraw.Draw(img)

            # Draw title
            try:
                font = ImageFont.truetype("Arial.ttf", 16)
            except:
                font = ImageFont.load_default()

            title = f"MicroWeldr - Weld Progress ({frame_num + 1}/{len(self.weld_sequence)} points)"
            draw.text((10, 10), title, fill="black", font=font)

            # Draw points up to current frame (no connecting lines)
            points_to_show = self.weld_sequence[: frame_num + 1]

            # Draw completed points (smaller, faded)
            for i, point in enumerate(points_to_show[:-1]):  # All but the last
                x, y = self._transform_point(
                    point["x"], point["y"], scale, offset_x, offset_y
                )
                color = self.colors.get(point["weld_type"], self.colors["normal"])

                # Draw completed point using configured nozzle diameter
                completed_radius = self._calculate_point_radius(scale)
                draw.ellipse(
                    [
                        x - completed_radius,
                        y - completed_radius,
                        x + completed_radius,
                        y + completed_radius,
                    ],
                    fill=color,
                )

            # Draw current point (larger and highlighted)
            if points_to_show:
                current_point = points_to_show[-1]
                x, y = self._transform_point(
                    current_point["x"], current_point["y"], scale, offset_x, offset_y
                )
                color = self.colors.get(
                    current_point["weld_type"], self.colors["normal"]
                )

                # Draw larger current point with bright outline
                draw.ellipse(
                    [
                        x - point_radius,
                        y - point_radius,
                        x + point_radius,
                        y + point_radius,
                    ],
                    fill=color,
                    outline="red",
                    width=3,
                )

                # Draw point number
                try:
                    small_font = ImageFont.truetype("Arial.ttf", 10)
                except:
                    small_font = ImageFont.load_default()

                draw.text(
                    (x + 5, y - 5), str(frame_num + 1), fill="red", font=small_font
                )

            # Draw legend
            self._draw_legend(draw)

            frames.append(img)

        # Create a clean final frame with all points in normal size (no highlight/number)
        if frames and self.weld_sequence:
            logger.info("Creating clean final frame with all points in normal size")
            img = Image.new("RGB", (self.width, self.height), "white")
            draw = ImageDraw.Draw(img)

            # Draw title
            title = f"MicroWeldr - Weld Complete ({len(self.weld_sequence)} points)"
            draw.text((10, 10), title, fill="black", font=font)

            # Draw all points in normal size with proper colors
            for point in self.weld_sequence:
                x, y = self._transform_point(
                    point["x"], point["y"], scale, offset_x, offset_y
                )
                color = self.colors.get(point["weld_type"], self.colors["normal"])

                # Draw normal-sized point (2mm diameter welding spot)
                final_radius = self._calculate_point_radius(scale)
                draw.ellipse(
                    [
                        x - final_radius,
                        y - final_radius,
                        x + final_radius,
                        y + final_radius,
                    ],
                    fill=color,
                )

            # Draw legend
            self._draw_legend(draw)

            # Replace the last frame with the clean version
            frames[-1] = img

        # Add 3-second pause at the end by duplicating the final frame
        if frames:
            final_frame = frames[-1]
            pause_frames = int(3000 / frame_duration)  # 3 seconds worth of frames
            logger.info(f"Adding {pause_frames} pause frames for 3-second end pause")
            for _ in range(pause_frames):
                frames.append(final_frame.copy())

        # Save animated GIF
        if frames:
            logger.info(f"Saving GIF with {len(frames)} total frames")
            frames[0].save(
                self.output_path,
                save_all=True,
                append_images=frames[1:],
                duration=frame_duration,
                loop=0,  # Infinite loop
            )
            logger.info(
                f"Animated GIF saved to {self.output_path} ({len(frames)} frames)"
            )
        else:
            logger.warning("No frames generated for animation")

    def _draw_legend(self, draw: ImageDraw.Draw) -> None:
        """Draw legend showing weld types and colors."""
        try:
            font = ImageFont.truetype("Arial.ttf", 12)
        except:
            font = ImageFont.load_default()

        legend_x = self.width - 150
        legend_y = 50

        draw.text((legend_x, legend_y - 20), "Weld Types:", fill="black", font=font)

        y_offset = 0
        for weld_type, color in self.colors.items():
            # Draw color circle
            draw.ellipse(
                [
                    legend_x,
                    legend_y + y_offset,
                    legend_x + 10,
                    legend_y + y_offset + 10,
                ],
                fill=color,
            )

            # Draw label
            draw.text(
                (legend_x + 15, legend_y + y_offset - 2),
                weld_type.capitalize(),
                fill="black",
                font=font,
            )

            y_offset += 20

    def __del__(self):
        """Cleanup when subscriber is destroyed."""
        # Nothing to clean up for PNG generation
        pass
