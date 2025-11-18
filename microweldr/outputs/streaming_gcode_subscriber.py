"""Streaming G-code subscriber that writes G-code incrementally as events flow."""

import logging
from pathlib import Path
from typing import List, Optional, TextIO, Tuple
from ..core.events import Event, EventType, OutputEvent, publish_event
from ..processors.subscribers import EventSubscriber

logger = logging.getLogger(__name__)


class FilenameError(Exception):
    """Raised when filename validation fails."""

    pass


class StreamingGCodeSubscriber(EventSubscriber):
    """Generates G-code output from events in streaming mode.

    This subscriber writes G-code incrementally as events flow through the system,
    eliminating the need to store WeldPath objects in memory.
    """

    def __init__(
        self,
        output_path: Path,
        config,
        coordinate_offset: Tuple[float, float] = (0.0, 0.0),
        include_user_pause: bool = True,
    ):
        """Initialize streaming G-code subscriber.

        Args:
            output_path: Path for G-code output file
            config: Configuration object
            coordinate_offset: Tuple of (offset_x, offset_y) for coordinate centering
            include_user_pause: Whether to include user pause for plastic insertion
        """
        self.output_path = Path(output_path)
        self.config = config
        self.file_handle: Optional[TextIO] = None
        self.current_path_id = ""
        self.current_weld_type = "normal"
        self.is_first_point_in_path = True
        self.total_paths_processed = 0
        self.total_points_processed = 0
        self.is_initialized = False

        # Store coordinate offset for centering
        self.offset_x, self.offset_y = coordinate_offset

        # User interaction control
        self.include_user_pause = include_user_pause

        # Travel height management
        self.welding_started = False  # Track if we've started welding
        self.is_first_weld_ever = True  # Track very first weld point

        logger.info(
            f"StreamingGCode: Initialized with coordinate offset ({self.offset_x:+.3f}, {self.offset_y:+.3f})"
        )

    def get_priority(self) -> int:
        """Get subscriber priority (lower number = higher priority)."""
        return 20  # Lower priority - after validation and bounding box

    def get_subscribed_events(self) -> List[EventType]:
        """Get subscribed event types."""
        return [
            EventType.PATH_PROCESSING,
            EventType.POINT_PROCESSING,
            EventType.OUTPUT_GENERATION,
        ]

    def handle_event(self, event: Event) -> None:
        """Handle events for streaming G-code generation."""
        try:
            if event.event_type == EventType.PATH_PROCESSING:
                self._handle_path_event(event)
            elif event.event_type == EventType.POINT_PROCESSING:
                self._handle_point_event(event)
            elif event.event_type == EventType.OUTPUT_GENERATION:
                self._handle_output_event(event)
        except Exception as e:
            logger.exception(f"Error in streaming G-code subscriber: {e}")

    def _handle_path_event(self, event: Event) -> None:
        """Handle path processing event - streaming mode."""
        action = event.data.get("action", "")

        if action == "path_start":
            path_data = event.data.get("path_data", {})
            self.current_path_id = path_data.get(
                "id", f"path_{self.total_paths_processed}"
            )
            self.current_weld_type = path_data.get("weld_type", "normal")
            self.is_first_point_in_path = True

            # Initialize G-code file if not already done
            if not self.file_handle:
                self._initialize_gcode_file()

            # Write path start comment
            self.file_handle.write(
                f"; Starting path: {self.current_path_id} ({self.current_weld_type})\n"
            )
            logger.debug(f"StreamingGCode: Started path {self.current_path_id}")

        elif action == "point_added":
            # Handle point added to path
            point_data = event.data.get("point", {})
            x = point_data.get("x", 0)
            y = point_data.get("y", 0)
            point_weld_type = point_data.get("weld_type", self.current_weld_type)

            # Write G-code movement command immediately
            self._write_point_gcode(x, y, point_weld_type)
            self.total_points_processed += 1

        elif action == "path_complete":
            # Write path completion comment
            if self.file_handle:
                self.file_handle.write(f"; Completed path: {self.current_path_id}\n\n")
                self.file_handle.flush()  # Ensure data is written
            self.total_paths_processed += 1
            logger.debug(f"StreamingGCode: Completed path {self.current_path_id}")

    def _handle_point_event(self, event: Event) -> None:
        """Handle point processing event - streaming mode."""
        action = event.data.get("action", "")

        if action == "point_added":
            point_data = event.data.get("point_data", {})
            x = point_data.get("x", 0)
            y = point_data.get("y", 0)
            point_weld_type = point_data.get("weld_type", self.current_weld_type)

            # Write G-code movement command immediately
            self._write_point_gcode(x, y, point_weld_type)
            self.total_points_processed += 1

    def _handle_output_event(self, event: Event) -> None:
        """Handle output generation event."""
        action = event.data.get("action", "")
        output_type = event.data.get("output_type", "")

        if action == "generate" and output_type == "gcode":
            self._finalize_gcode_file()
        elif action == "processing_complete":
            # Ensure file is finalized when processing completes
            self._finalize_gcode_file()

    def _initialize_gcode_file(self) -> None:
        """Initialize G-code file with complete setup sequence."""
        try:
            # Validate filename length for Prusa compatibility
            self._validate_filename()

            # Open file and write complete initialization sequence
            self.file_handle = open(self.output_path, "w", encoding="utf-8")
            self._write_gcode_header()
            self._write_calibration_and_heating()
            if self.include_user_pause:
                self._write_user_pause()

            self.is_initialized = True
            logger.info(f"StreamingGCode: Initialized G-code file {self.output_path}")
        except Exception as e:
            logger.error(f"Failed to initialize G-code file {self.output_path}: {e}")
            raise

    def _write_gcode_header(self) -> None:
        """Write comprehensive G-code file header."""
        if not self.file_handle:
            return

        # Get config values for header
        bed_temp = self.config.get("temperatures", "bed_temperature", 35)
        nozzle_temp = self.config.get("temperatures", "nozzle_temperature", 160)

        self.file_handle.write("; Generated by MicroWeldr - Streaming Subscriber\n")
        self.file_handle.write("; Prusa Core One Plastic Welding G-code\n")
        self.file_handle.write(f"; Output file: {self.output_path.name}\n")
        self.file_handle.write("; \n")
        self.file_handle.write("; Process Overview:\n")
        self.file_handle.write("; 1. Heat bed and calibrate\n")
        self.file_handle.write("; 2. Heat nozzle and wait\n")
        self.file_handle.write("; 3. Pause for plastic sheet insertion\n")
        self.file_handle.write("; 4. Execute welding sequence\n")
        self.file_handle.write("; 5. Cool down and finish\n")
        self.file_handle.write("; \n")
        self.file_handle.write(f"; Bed Temperature: {bed_temp}°C\n")
        self.file_handle.write(f"; Nozzle Temperature: {nozzle_temp}°C\n")
        self.file_handle.write("; \n\n")

    def _write_point_gcode(self, x: float, y: float, weld_type: str) -> None:
        """Write G-code movement command for a point."""
        if not self.file_handle:
            return

        # Apply coordinate centering offset
        centered_x = x + self.offset_x
        centered_y = y + self.offset_y

        # Get movement settings from config
        high_travel_height = self.config.get("movement", "move_height", 0.2)
        low_travel_height = self.config.get("movement", "low_travel_height", 0.2)
        z_speed = self.config.get("movement", "z_speed", 300)
        xy_speed = self.config.get("movement", "xy_speed", 3000)

        if self.is_first_weld_ever:
            # Very first weld point - apply compression offset, then use high travel height
            self._write_weld_compression_offset()
            self.file_handle.write(
                f"G1 Z{high_travel_height} F{z_speed} ; Move to high travel height\n"
            )
            self.file_handle.write(
                f"G1 X{centered_x:.3f} Y{centered_y:.3f} F{xy_speed} ; Move to start of welding\n"
            )
            self.is_first_weld_ever = False
            self.welding_started = True
        elif self.is_first_point_in_path:
            # First point of a new path - move directly (already at travel height)
            self.file_handle.write(
                f"G1 X{centered_x:.3f} Y{centered_y:.3f} F{xy_speed} ; Move to start of path\n"
            )
            self.is_first_point_in_path = False
        else:
            # Move to next point - already at travel height from previous weld
            self.file_handle.write(
                f"G1 X{centered_x:.3f} Y{centered_y:.3f} F{xy_speed} ; Move to next point\n"
            )

        # Add weld-specific commands based on weld type
        self._write_weld_commands(weld_type)

    def _write_weld_commands(self, weld_type: str) -> None:
        """Write weld-specific G-code commands."""
        if not self.file_handle:
            return

        # Get travel heights and speeds from config
        low_travel_height = self.config.get("movement", "low_travel_height", 0.2)
        z_speed = self.config.get("movement", "z_speed", 3000)

        if weld_type == "normal":
            # Normal welding commands
            weld_height = self.config.get("normal_welds", "weld_height", 0.1)
            weld_time = self.config.get("normal_welds", "weld_time", 1.0)
            self.file_handle.write(
                f"G1 Z{weld_height} F{z_speed} ; Lower to weld height\n"
            )
            self.file_handle.write(
                f"G4 P{weld_time * 1000:.0f} ; Weld for {weld_time}s\n"
            )
            self.file_handle.write(
                f"G1 Z{low_travel_height} F{z_speed} ; Raise to low travel height\n"
            )

        elif weld_type == "frangible":
            # Frangible welding commands (lighter)
            weld_height = self.config.get("frangible_welds", "weld_height", 0.15)
            weld_time = self.config.get("frangible_welds", "weld_time", 0.5)
            self.file_handle.write(
                f"G1 Z{weld_height} F{z_speed} ; Lower to frangible weld height\n"
            )
            self.file_handle.write(
                f"G4 P{weld_time * 1000:.0f} ; Frangible weld for {weld_time}s\n"
            )
            self.file_handle.write(
                f"G1 Z{low_travel_height} F{z_speed} ; Raise to low travel height\n"
            )

        elif weld_type == "stop":
            # Stop point with pause
            self.file_handle.write("M0 ; Pause for user interaction\n")

        elif weld_type == "pipette":
            # Pipette operation
            self.file_handle.write("; Pipette operation point\n")
            self.file_handle.write(f"G1 Z0.05 F{z_speed} ; Lower for pipette\n")
            self.file_handle.write("G4 P500 ; Brief pause\n")
            self.file_handle.write(
                f"G1 Z{low_travel_height} F{z_speed} ; Raise to low travel height\n"
            )

    def _finalize_gcode_file(self) -> None:
        """Finalize G-code file with proper cooldown sequence and close."""
        if self.file_handle:
            # Write statistics
            self.file_handle.write("; End of welding sequence\n")
            self.file_handle.write(
                f"; Total paths processed: {self.total_paths_processed}\n"
            )
            self.file_handle.write(
                f"; Total points processed: {self.total_points_processed}\n"
            )
            self.file_handle.write("\n")

            # Write proper cooldown sequence
            self._write_cooldown_sequence()

            # Close file
            self.file_handle.close()
            self.file_handle = None

            logger.info(f"StreamingGCode: Finalized G-code file {self.output_path}")
            logger.info(
                f"StreamingGCode: Processed {self.total_paths_processed} paths, {self.total_points_processed} points"
            )

            # Publish completion event
            publish_event(
                OutputEvent(
                    action="complete",
                    output_type="gcode",
                    file_path=self.output_path,
                    statistics={
                        "total_paths": self.total_paths_processed,
                        "total_points": self.total_points_processed,
                        "file_size": (
                            self.output_path.stat().st_size
                            if self.output_path.exists()
                            else 0
                        ),
                    },
                )
            )

    def get_statistics(self) -> dict:
        """Get G-code generation statistics."""
        return {
            "total_paths_processed": self.total_paths_processed,
            "total_points_processed": self.total_points_processed,
            "output_file": str(self.output_path),
            "file_exists": self.output_path.exists(),
            "file_size": (
                self.output_path.stat().st_size if self.output_path.exists() else 0
            ),
            "is_initialized": self.is_initialized,
        }

    def _validate_filename(self) -> None:
        """Validate G-code filename length for Prusa printer compatibility."""
        filename = self.output_path.name
        MAX_FILENAME_LENGTH = 31  # Conservative limit for Prusa compatibility

        if len(filename) > MAX_FILENAME_LENGTH:
            raise FilenameError(
                f"G-code filename '{filename}' is {len(filename)} characters long, "
                f"which exceeds the {MAX_FILENAME_LENGTH} character limit for Prusa printers. "
                f"Long filenames can cause display issues, file selection errors, or transfer failures. "
                f"Please use a shorter filename (max {MAX_FILENAME_LENGTH} characters including .gcode extension)."
            )

    def _write_calibration_and_heating(self) -> None:
        """Write calibration and heating sequence."""
        if not self.file_handle:
            return

        # Get temperatures from config
        bed_temp = self.config.get("temperatures", "bed_temperature", 35)
        nozzle_temp = self.config.get("temperatures", "nozzle_temperature", 160)
        use_chamber_heating = self.config.get(
            "temperatures", "use_chamber_heating", False
        )
        chamber_temp = self.config.get("temperatures", "chamber_temperature", 35)

        # Start bed heating (don't wait - let it heat during calibration)
        self.file_handle.write(
            f"; Start heating bed to {bed_temp}°C (heating during calibration)\n"
        )
        self.file_handle.write(
            f"M140 S{bed_temp} ; Set bed temperature (start heating)\n\n"
        )

        # Printer initialization
        self.file_handle.write("; Printer initialization\n")
        self.file_handle.write("G90 ; Absolute positioning\n")
        self.file_handle.write("M83 ; Relative extrusion\n")
        self.file_handle.write("G28 ; Home all axes\n\n")

        # Heat bed and nozzle FIRST (like working calibrate-and-set.gcode)
        self.file_handle.write(f"; Heat bed and nozzle before bed leveling\n")
        self.file_handle.write(f"M190 S{bed_temp} ; Wait for bed temperature\n")
        self.file_handle.write(f"M104 S{nozzle_temp} ; Set nozzle temperature\n")
        self.file_handle.write(f"M109 S{nozzle_temp} ; Wait for nozzle temperature\n\n")

        # Bed leveling AFTER heating (correct Z=0 reference) - if enabled
        enable_bed_leveling = self.config.get("printer", "enable_bed_leveling", False)
        if enable_bed_leveling:
            self.file_handle.write("; Bed leveling after thermal expansion\n")
            self.file_handle.write("G29 ; Auto bed leveling\n\n")
        else:
            self.file_handle.write("; Bed leveling disabled\n\n")

        # Chamber heating if enabled (Core One)
        if use_chamber_heating:
            self.file_handle.write(f"; Chamber heating (Core One)\n")
            self.file_handle.write(
                f"M141 S{chamber_temp} ; Set chamber temperature\n\n"
            )

    def _write_user_pause(self) -> None:
        """Write user pause for plastic sheet insertion."""
        if not self.file_handle:
            return

        self.file_handle.write("; Pause for user to insert plastic sheets\n")
        self.file_handle.write("M117 Insert plastic sheets...\n")
        self.file_handle.write(
            "M0 ; Pause - Insert plastic sheets and press continue\n"
        )
        self.file_handle.write("M117 Starting welding sequence...\n\n")

    def _write_weld_compression_offset(self) -> None:
        """Write Z offset for weld compression after calibration but before welding."""
        if not self.file_handle:
            return

        # Get weld compression offset from config
        compression_offset = self.config.get("movement", "weld_compression_offset", 0.3)
        z_speed = self.config.get("movement", "z_speed", 600)
        high_travel_height = self.config.get("movement", "move_height", 5.0)

        if compression_offset != 0.0:
            self.file_handle.write(
                "; Apply Z offset for weld compression (relative adjustment)\n"
            )
            self.file_handle.write(
                f"G1 Z0 F{z_speed} ; Move to Z=0 for relative offset\n"
            )
            self.file_handle.write(
                f"G92 Z{compression_offset} ; Set Z offset - printer thinks it's {compression_offset}mm above surface\n"
            )
            self.file_handle.write(
                f"G1 Z{high_travel_height} F{z_speed} ; Return to travel height\n\n"
            )

    def _write_cooldown_sequence(self) -> None:
        """Write cooldown and end sequence."""
        if not self.file_handle:
            return

        # Get cooldown settings
        enable_cooldown = self.config.get("temperatures", "enable_cooldown", False)
        cooldown_temp = self.config.get("temperatures", "cooldown_temperature", 0)
        use_chamber_heating = self.config.get(
            "temperatures", "use_chamber_heating", False
        )

        self.file_handle.write("; End sequence\n")
        self.file_handle.write("G1 Z10 F600 ; Raise nozzle to high travel height\n")
        self.file_handle.write("G28 X Y ; Home X and Y axes\n")

        # Only cool down heaters if cooldown is enabled
        if enable_cooldown:
            self.file_handle.write(
                f"M104 S{cooldown_temp} ; Cool nozzle to {cooldown_temp}°C\n"
            )
            self.file_handle.write(
                f"M140 S{cooldown_temp} ; Cool bed to {cooldown_temp}°C\n"
            )

        if use_chamber_heating:
            self.file_handle.write("M141 S0 ; Turn off chamber heating\n")

        self.file_handle.write("M107 ; Turn off part cooling fan\n")
        self.file_handle.write("M84 ; Disable steppers\n")
        self.file_handle.write("; End of G-code\n")

    def __del__(self):
        """Safety net: ensure file is closed on cleanup.

        Note: This is a fallback only. Proper cleanup should happen via
        event-driven finalization when processing_complete event is received.
        """
        if hasattr(self, "file_handle") and self.file_handle:
            try:
                logger.warning(
                    f"StreamingGCodeSubscriber: File {self.output_path} closed in destructor - this should not happen in normal operation"
                )
                self.file_handle.close()
            except Exception as e:
                # Log exceptions in destructor for debugging but don't raise
                logger.debug(f"Exception in StreamingGCodeSubscriber destructor: {e}")
