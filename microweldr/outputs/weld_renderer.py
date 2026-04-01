"""Shared weld pattern rendering utilities.

Renders a static overview image of weld points using PIL. Used by both
GIFAnimationSubscriber (for the final frame) and Bambu3mfSubscriber
(for the plate thumbnail).
"""

from __future__ import annotations

import logging

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Default weld-type colour map
DEFAULT_COLORS: dict[str, str] = {
    "normal": "#000080",  # Blue
    "frangible": "#FF0000",  # Red
    "stop": "#800080",  # Purple
    "pipette": "#FF00FF",  # Magenta
}


def compute_bounds(
    weld_sequence: list[dict],
) -> dict[str, float | None]:
    """Compute min/max coordinate bounds from a weld sequence."""
    bounds: dict[str, float | None] = {
        "min_x": None,
        "min_y": None,
        "max_x": None,
        "max_y": None,
    }
    for pt in weld_sequence:
        x, y = float(pt["x"]), float(pt["y"])
        if bounds["min_x"] is None or x < bounds["min_x"]:
            bounds["min_x"] = x
        if bounds["max_x"] is None or x > bounds["max_x"]:
            bounds["max_x"] = x
        if bounds["min_y"] is None or y < bounds["min_y"]:
            bounds["min_y"] = y
        if bounds["max_y"] is None or y > bounds["max_y"]:
            bounds["max_y"] = y
    return bounds


def calculate_transform(
    bounds: dict[str, float | None],
    width: int,
    height: int,
    margin: int,
) -> tuple[float, float, float]:
    """Calculate scale and offset to map data coordinates into image pixels."""
    if bounds["min_x"] is None:
        return 1.0, 0.0, 0.0

    data_width = bounds["max_x"] - bounds["min_x"]
    data_height = bounds["max_y"] - bounds["min_y"]

    if data_width == 0:
        data_width = 1
    if data_height == 0:
        data_height = 1

    available_width = width - 2 * margin
    available_height = height - 2 * margin

    scale_x = available_width / data_width
    scale_y = available_height / data_height
    scale = min(scale_x, scale_y)

    offset_x = (
        margin + (available_width - data_width * scale) / 2 - bounds["min_x"] * scale
    )
    offset_y = (
        margin + (available_height - data_height * scale) / 2 - bounds["min_y"] * scale
    )

    return scale, offset_x, offset_y


def calculate_point_radius(
    scale: float,
    weld_spot_diameter: float = 2.0,
    base_radius: float = 0.5,
    max_radius: int = 20,
) -> int:
    """Calculate point radius in pixels from real-world nozzle size and scale."""
    weld_spot_radius_pixels = (weld_spot_diameter / 2) * scale
    point_radius = max(base_radius, int(weld_spot_radius_pixels))
    return min(int(point_radius), max_radius)


def transform_point(
    x: float, y: float, scale: float, offset_x: float, offset_y: float
) -> tuple[int, int]:
    """Transform data coordinates to image coordinates."""
    return int(x * scale + offset_x), int(y * scale + offset_y)


def draw_legend(
    draw: ImageDraw.Draw,
    colors: dict[str, str],
    width: int,
) -> None:
    """Draw a weld-type colour legend in the top-right corner."""
    try:
        font = ImageFont.truetype("Arial.ttf", 12)
    except OSError:
        font = ImageFont.load_default()

    legend_x = width - 150
    legend_y = 50

    draw.text((legend_x, legend_y - 20), "Weld Types:", fill="black", font=font)

    y_offset = 0
    for weld_type, color in colors.items():
        draw.ellipse(
            [legend_x, legend_y + y_offset, legend_x + 10, legend_y + y_offset + 10],
            fill=color,
        )
        draw.text(
            (legend_x + 15, legend_y + y_offset - 2),
            weld_type.capitalize(),
            fill="black",
            font=font,
        )
        y_offset += 20


def render_weld_overview(
    weld_sequence: list[dict],
    width: int = 800,
    height: int = 600,
    margin: int = 50,
    weld_spot_diameter: float = 2.0,
    colors: dict[str, str] | None = None,
    title: str | None = None,
    show_legend: bool = True,
) -> Image.Image:
    """Render a static overview image of all weld points.

    Args:
        weld_sequence: List of dicts with keys ``x``, ``y``, ``weld_type``.
        width: Image width in pixels.
        height: Image height in pixels.
        margin: Margin around the pattern in pixels.
        weld_spot_diameter: Real-world nozzle outer diameter in mm.
        colors: Optional colour map overriding *DEFAULT_COLORS*.
        title: Optional title drawn at the top of the image.
        show_legend: Whether to draw the weld-type legend.

    Returns:
        A PIL Image with the rendered weld pattern.
    """
    if colors is None:
        colors = DEFAULT_COLORS

    bounds = compute_bounds(weld_sequence)
    scale, off_x, off_y = calculate_transform(bounds, width, height, margin)
    point_radius = calculate_point_radius(scale, weld_spot_diameter)

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    # Title
    if title:
        try:
            font = ImageFont.truetype("Arial.ttf", 16)
        except OSError:
            font = ImageFont.load_default()
        draw.text((10, 10), title, fill="black", font=font)

    # Draw all points
    for pt in weld_sequence:
        x, y = transform_point(float(pt["x"]), float(pt["y"]), scale, off_x, off_y)
        color = colors.get(
            pt.get("weld_type", "normal"), colors.get("normal", "#000080")
        )
        draw.ellipse(
            [x - point_radius, y - point_radius, x + point_radius, y + point_radius],
            fill=color,
        )

    if show_legend:
        draw_legend(draw, colors, width)

    return img
