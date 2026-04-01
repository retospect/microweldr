"""Bambu 3MF output subscriber — wraps generated G-code into a .gcode.3mf file.

Listens for the ``OutputEvent(action="complete")`` emitted by
``StreamingGCodeSubscriber`` after the plain ``.gcode`` file has been written,
reads it back, and packages it as plate 1 inside a Bambu-compatible
``.gcode.3mf`` archive using the *bambuuzle* library.

If weld-point data is available the weld pattern is rendered as the plate
thumbnail so Bambu Studio shows a preview of the weld layout.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

from bambuuzle import BambuFile

from ..core.events import Event, EventSubscriber, EventType
from .weld_renderer import DEFAULT_COLORS, render_weld_overview

logger = logging.getLogger(__name__)

# Bambu Studio thumbnail dimensions (matches slicer convention)
THUMBNAIL_WIDTH = 400
THUMBNAIL_HEIGHT = 300


class Bambu3mfSubscriber(EventSubscriber):
    """Packages generated G-code into a Bambu ``.gcode.3mf`` file.

    This subscriber collects weld-point data as it flows through the event
    system so it can render a thumbnail, then writes the 3MF archive once
    the G-code file is finalized.
    """

    def __init__(
        self,
        gcode_path: Path,
        output_3mf_path: Path,
        weld_spot_diameter: float = 2.0,
        colors: dict[str, str] | None = None,
    ):
        """Initialize Bambu 3MF subscriber.

        Args:
            gcode_path: Path to the plain ``.gcode`` file that will be written
                by ``StreamingGCodeSubscriber``.
            output_3mf_path: Path for the output ``.gcode.3mf`` file.
            weld_spot_diameter: Nozzle outer diameter in mm (for thumbnail).
            colors: Optional weld-type colour map for the thumbnail.
        """
        self.gcode_path = Path(gcode_path)
        self.output_3mf_path = Path(output_3mf_path)
        self.weld_spot_diameter = weld_spot_diameter
        self.colors = colors or dict(DEFAULT_COLORS)

        # Collect weld points for thumbnail rendering
        self.weld_sequence: list[dict] = []
        self.current_path_id: str | None = None

    def get_priority(self) -> int:
        """Run after StreamingGCodeSubscriber (priority 20)."""
        return 30

    def get_subscribed_events(self) -> list[EventType]:
        """Subscribe to path events (for thumbnail) and output events (to trigger save)."""
        return [EventType.PATH_PROCESSING, EventType.OUTPUT_GENERATION]

    def handle_event(self, event: Event) -> None:
        """Handle incoming events."""
        try:
            if event.event_type == EventType.PATH_PROCESSING:
                self._handle_path_event(event)
            elif event.event_type == EventType.OUTPUT_GENERATION:
                self._handle_output_event(event)
        except Exception as e:
            logger.exception(f"Error in Bambu 3MF subscriber: {e}")

    # ------------------------------------------------------------------
    # Path events — collect points for thumbnail
    # ------------------------------------------------------------------

    def _handle_path_event(self, event: Event) -> None:
        """Collect weld points for thumbnail rendering."""
        if hasattr(event, "action"):
            action = event.action
        else:
            action = event.data.get("action", "")

        if action == "path_start":
            if hasattr(event, "path_id"):
                self.current_path_id = event.path_id
            else:
                self.current_path_id = event.data.get("path_id", "path")

        elif action == "point_added":
            if hasattr(event, "point"):
                point_data = event.point
            else:
                point_data = event.data.get("point", {})

            if point_data:
                self.weld_sequence.append(
                    {
                        "x": float(point_data.get("x", 0)),
                        "y": float(point_data.get("y", 0)),
                        "weld_type": point_data.get("weld_type", "normal"),
                    }
                )

    # ------------------------------------------------------------------
    # Output event — build the .gcode.3mf
    # ------------------------------------------------------------------

    def _handle_output_event(self, event: Event) -> None:
        """When gcode generation is complete, package into .gcode.3mf."""
        action = event.data.get("action", "")

        if action in ("complete", "processing_complete"):
            self._write_3mf()

    def _write_3mf(self) -> None:
        """Read the finished .gcode file and wrap it in a .gcode.3mf archive."""
        if not self.gcode_path.exists():
            logger.error(
                f"Bambu3mf: G-code file {self.gcode_path} not found — skipping 3MF generation"
            )
            return

        gcode = self.gcode_path.read_text(encoding="utf-8")

        bf = BambuFile()
        bf.add_plate(gcode=gcode, number=1)

        # Render weld pattern as plate thumbnail
        thumbnail_bytes = self._render_thumbnail()
        if thumbnail_bytes is not None:
            bf.plate(1).thumbnail_png = thumbnail_bytes

        bf.save(str(self.output_3mf_path))

        size = self.output_3mf_path.stat().st_size
        logger.info(
            f"Bambu3mf: Saved {self.output_3mf_path} ({size:,} bytes, "
            f"{len(self.weld_sequence)} weld points)"
        )

    def _render_thumbnail(self) -> bytes | None:
        """Render the weld pattern to PNG bytes for use as a plate thumbnail."""
        if not self.weld_sequence:
            logger.debug("Bambu3mf: No weld points — skipping thumbnail")
            return None

        try:
            img = render_weld_overview(
                self.weld_sequence,
                width=THUMBNAIL_WIDTH,
                height=THUMBNAIL_HEIGHT,
                margin=20,
                weld_spot_diameter=self.weld_spot_diameter,
                colors=self.colors,
                title="MicroWeldr",
                show_legend=False,
            )

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

        except Exception as e:
            logger.warning(f"Bambu3mf: Failed to render thumbnail: {e}")
            return None
