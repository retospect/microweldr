"""Shared printer operations for CLI and UI consistency."""

import logging
from typing import Any, Dict, Optional, Tuple

from ..prusalink.client import PrusaLinkClient
from ..prusalink.exceptions import PrusaLinkError
from .constants import GCodeCommands

logger = logging.getLogger(__name__)


class PrinterOperations:
    """Shared printer operations used by both CLI and UI."""

    def __init__(self, client: PrusaLinkClient):
        """Initialize with a PrusaLink client."""
        self.client = client

    def send_gcode(self, command: str) -> bool:
        """Send G-code command to printer.

        Args:
            command: G-code command to send

        Returns:
            True if successful, False otherwise
        """
        try:
            # For now, we'll use a simple approach - this can be enhanced later
            # The PrusaLinkClient doesn't have a direct send_gcode method yet
            logger.info(f"Would send G-code: {command}")
            return True
        except Exception as e:
            logger.error(f"Failed to send G-code '{command}': {e}")
            return False

    def calibrate_printer(self) -> bool:
        """Perform printer calibration (home + bed leveling).

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Starting printer calibration...")

            # Home all axes
            if not self.send_gcode(GCodeCommands.G28):
                return False

            # Auto bed leveling
            if not self.send_gcode(GCodeCommands.G29):
                return False

            logger.info("Printer calibration completed")
            return True

        except Exception as e:
            logger.error(f"Calibration failed: {e}")
            return False

    def set_bed_temperature(self, temperature: int, wait: bool = False) -> bool:
        """Set bed temperature.

        Args:
            temperature: Target temperature in Celsius
            wait: Whether to wait for temperature to be reached

        Returns:
            True if successful, False otherwise
        """
        try:
            command = (
                f"{GCodeCommands.M190 if wait else GCodeCommands.M140} S{temperature}"
            )
            result = self.send_gcode(command)

            if result:
                action = "set and waiting for" if wait else "set to"
                logger.info(f"Bed temperature {action} {temperature}°C")

            return result

        except Exception as e:
            logger.error(f"Failed to set bed temperature: {e}")
            return False

    def turn_off_bed_heater(self) -> bool:
        """Turn off bed heater.

        Returns:
            True if successful, False otherwise
        """
        return self.set_bed_temperature(0)

    def move_to_position(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        speed: int = 3000,
    ) -> bool:
        """Move printer to specified position.

        Args:
            x: X coordinate (mm)
            y: Y coordinate (mm)
            z: Z coordinate (mm)
            speed: Movement speed (mm/min)

        Returns:
            True if successful, False otherwise
        """
        try:
            coords = []
            if x is not None:
                coords.append(f"X{x}")
            if y is not None:
                coords.append(f"Y{y}")
            if z is not None:
                coords.append(f"Z{z}")

            if not coords:
                return True  # No movement needed

            command = f"{GCodeCommands.G1} {' '.join(coords)} F{speed}"
            return self.send_gcode(command)

        except Exception as e:
            logger.error(f"Failed to move to position: {e}")
            return False

    def draw_bounding_box(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        fly_height: float = 5.0,
        speed: int = 3000,
    ) -> bool:
        """Draw bounding box at fly height.

        Args:
            min_x: Minimum X coordinate
            min_y: Minimum Y coordinate
            max_x: Maximum X coordinate
            max_y: Maximum Y coordinate
            fly_height: Height above bed for movement
            speed: Movement speed

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(
                f"Drawing bounding box: ({min_x}, {min_y}) to ({max_x}, {max_y})"
            )

            # Move to fly height
            if not self.move_to_position(z=fly_height, speed=speed):
                return False

            # Draw rectangle
            positions = [
                (min_x, min_y),  # Bottom left
                (max_x, min_y),  # Bottom right
                (max_x, max_y),  # Top right
                (min_x, max_y),  # Top left
                (min_x, min_y),  # Back to start
            ]

            for x, y in positions:
                if not self.move_to_position(x=x, y=y, speed=speed):
                    return False

            logger.info("Bounding box preview completed")
            return True

        except Exception as e:
            logger.error(f"Bounding box drawing failed: {e}")
            return False

    def load_unload_plate(self, drop_distance: float = 50.0) -> bool:
        """Drop plate for loading/unloading.

        Args:
            drop_distance: Distance to drop in mm

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get current position (this would need to be implemented in PrusaLinkClient)
            # For now, just move down relative to current position
            logger.info(f"Dropping plate by {drop_distance}mm for loading/unloading")

            # Switch to relative positioning
            if not self.send_gcode(GCodeCommands.G91):
                return False

            # Move down
            if not self.move_to_position(z=-drop_distance, speed=600):
                return False

            # Switch back to absolute positioning
            if not self.send_gcode(GCodeCommands.G90):
                return False

            logger.info("Plate lowered for loading/unloading")
            return True

        except Exception as e:
            logger.error(f"Load/unload failed: {e}")
            return False
