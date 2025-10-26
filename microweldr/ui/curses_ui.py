"""Curses-based terminal UI for MicroWeldr operations."""

import curses
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from ..core.config import Config
from ..core.converter import SVGToGCodeConverter
from ..core.models import WeldPath
from ..prusalink.client import PrusaLinkClient
from ..prusalink.exceptions import PrusaLinkError


class MicroWeldrUI:
    """Interactive curses-based UI for MicroWeldr operations."""

    def __init__(
        self, svg_file: Optional[Path] = None, config_file: Optional[Path] = None
    ):
        """Initialize the UI with optional SVG file and config."""
        self.svg_file = svg_file
        self.config_file = config_file or Path("config.toml")
        self.config = None
        self.converter = None
        self.weld_paths = []
        self.gcode_file = None

        # Printer state
        self.printer_client = None
        self.printer_connected = False
        self.printer_status = {}
        self.last_update = None
        self.calibrated = False
        self.plate_heater_on = False
        self.target_bed_temp = 60  # Default, will be updated from config

        # UI state
        self.stdscr = None
        self.running = True
        self.status_thread = None
        self.current_screen = "main"

        # Setup logging to file to avoid interfering with curses
        logging.basicConfig(
            filename="microweldr_ui.log",
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

    def initialize(self):
        """Initialize configuration and converter."""
        try:
            if self.config_file.exists():
                self.config = Config(str(self.config_file))
            else:
                # Create default config
                self.config = Config.create_default(str(self.config_file))

            self.converter = SVGToGCodeConverter(self.config)

            # Load printer settings from config
            self._load_printer_settings()

            # Initialize printer client
            self._initialize_printer_connection()

        except Exception as e:
            self.logger.error(f"Initialization failed: {e}")
            raise

    def _load_printer_settings(self):
        """Load printer settings from config file."""
        if not self.config:
            return

        try:
            # Load bed temperature from config
            self.target_bed_temp = self.config.get(
                "temperatures", "bed_temperature", 60
            )

            # Load other useful settings
            self.nozzle_temp = self.config.get(
                "temperatures", "nozzle_temperature", 200
            )
            self.chamber_temp = self.config.get(
                "temperatures", "chamber_temperature", 35
            )
            self.use_chamber = self.config.get(
                "temperatures", "use_chamber_heating", False
            )

            # Movement settings
            self.move_height = self.config.get("movement", "move_height", 5.0)
            self.travel_speed = self.config.get("movement", "travel_speed", 3000)
            self.z_speed = self.config.get("movement", "z_speed", 600)

            self.logger.info(
                f"Loaded config: bed_temp={self.target_bed_temp}°C, nozzle_temp={self.nozzle_temp}°C"
            )

        except Exception as e:
            self.logger.warning(f"Failed to load printer settings from config: {e}")
            # Keep defaults

    def _initialize_printer_connection(self):
        """Initialize printer connection using secrets.toml or config.toml."""
        self.printer_connected = False

        try:
            # Method 1: Try secrets.toml first (preferred for security)
            secrets_file = Path("secrets.toml")
            if secrets_file.exists():
                self.printer_client = PrusaLinkClient(str(secrets_file))
                self.printer_connected = True
                self.logger.info("Connected to printer using secrets.toml")
                return

        except Exception as e:
            self.logger.warning(f"Failed to connect using secrets.toml: {e}")

        try:
            # Method 2: Try config.toml printer connection settings
            if self.config and self._has_printer_connection_config():
                self.printer_client = self._create_client_from_config()
                self.printer_connected = True
                self.logger.info("Connected to printer using config.toml")
                return

        except Exception as e:
            self.logger.warning(f"Failed to connect using config.toml: {e}")

        # No connection available
        self.logger.info(
            "No printer connection configured (secrets.toml or config.toml)"
        )

    def _has_printer_connection_config(self) -> bool:
        """Check if config has printer connection settings."""
        try:
            host = self.config.get("printer", "host", None)
            username = self.config.get("printer", "username", None)
            password = self.config.get("printer", "password", None)
            return host is not None and username is not None and password is not None
        except:
            return False

    def _create_client_from_config(self):
        """Create PrusaLinkClient from main config file."""
        # Create a temporary config dict in the format expected by PrusaLinkClient
        printer_config = {
            "host": self.config.get("printer", "host"),
            "username": self.config.get("printer", "username"),
            "password": self.config.get("printer", "password"),
            "timeout": self.config.get("printer", "timeout", 30),
        }

        # Create client directly with config dict
        from ..prusalink.client import PrusaLinkClient

        client = PrusaLinkClient.__new__(PrusaLinkClient)
        client.config = printer_config
        client.base_url = f"http://{printer_config['host']}"

        from requests.auth import HTTPDigestAuth

        client.auth = HTTPDigestAuth(
            printer_config["username"], printer_config["password"]
        )
        client.timeout = printer_config["timeout"]

        return client

    def load_svg(self, svg_path: Path):
        """Load and convert SVG file."""
        try:
            self.svg_file = svg_path
            self.weld_paths = self.converter.parse_svg(str(svg_path))

            # Generate G-code
            output_path = svg_path.with_suffix(".gcode")
            self.converter.convert_to_gcode(str(svg_path), str(output_path))
            self.gcode_file = output_path

            self.logger.info(f"Loaded SVG: {svg_path}, Generated G-code: {output_path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to load SVG: {e}")
            return False

    def start_status_monitoring(self):
        """Start background thread for printer status monitoring."""
        if not self.printer_connected or self.status_thread:
            return

        def monitor_status():
            while self.running and self.printer_connected:
                try:
                    if self.printer_client:
                        self.printer_status = self.printer_client.get_status()
                        self.last_update = datetime.now()
                except Exception as e:
                    self.logger.warning(f"Status update failed: {e}")
                    self.printer_connected = False
                time.sleep(2)  # Update every 2 seconds

        self.status_thread = threading.Thread(target=monitor_status, daemon=True)
        self.status_thread.start()

    def stop_status_monitoring(self):
        """Stop the status monitoring thread."""
        self.running = False
        if self.status_thread:
            self.status_thread.join(timeout=1)

    def get_bounds_info(self) -> Tuple[float, float, float, float]:
        """Get bounding box information from loaded weld paths."""
        if not self.weld_paths:
            return (0, 0, 0, 0)

        all_points = []
        for path in self.weld_paths:
            all_points.extend(path.points)

        if not all_points:
            return (0, 0, 0, 0)

        x_coords = [p.x for p in all_points]
        y_coords = [p.y for p in all_points]

        return (min(x_coords), min(y_coords), max(x_coords), max(y_coords))

    def draw_header(self, stdscr, y: int) -> int:
        """Draw the header section."""
        stdscr.addstr(y, 0, "═" * (curses.COLS - 1), curses.A_BOLD)
        y += 1
        stdscr.addstr(
            y, 0, "🔧 MicroWeldr UI - Interactive Plastic Welding Control", curses.A_BOLD
        )
        y += 1
        stdscr.addstr(y, 0, "═" * (curses.COLS - 1), curses.A_BOLD)
        return y + 2

    def draw_file_info(self, stdscr, y: int) -> int:
        """Draw file and conversion information."""
        stdscr.addstr(y, 0, "📁 File Information:", curses.A_BOLD)
        y += 1

        if self.svg_file:
            stdscr.addstr(y, 2, f"SVG File: {self.svg_file.name}")
            y += 1
            if self.gcode_file:
                stdscr.addstr(y, 2, f"G-code: {self.gcode_file.name}")
                y += 1

            # Show bounds
            min_x, min_y, max_x, max_y = self.get_bounds_info()
            width = max_x - min_x
            height = max_y - min_y
            stdscr.addstr(y, 2, f"Dimensions: {width:.1f} × {height:.1f} mm")
            y += 1
            stdscr.addstr(
                y,
                2,
                f"Bounds: X({min_x:.1f} to {max_x:.1f}) Y({min_y:.1f} to {max_y:.1f})",
            )
            y += 1
            stdscr.addstr(y, 2, f"Weld Paths: {len(self.weld_paths)}")
            y += 1
        else:
            stdscr.addstr(y, 2, "No SVG file loaded")
            y += 1

        return y + 1

    def draw_printer_status(self, stdscr, y: int) -> int:
        """Draw printer connection and status information."""
        stdscr.addstr(y, 0, "🖨️  Printer Status:", curses.A_BOLD)
        y += 1

        if self.printer_connected:
            stdscr.addstr(y, 2, "Connection: ✅ Connected", curses.color_pair(2))
            y += 1

            if self.last_update:
                seconds_ago = (datetime.now() - self.last_update).seconds
                stdscr.addstr(y, 2, f"Last Update: {seconds_ago}s ago")
                y += 1

            if self.printer_status:
                # Temperature info
                if "temperature" in self.printer_status:
                    temp_info = self.printer_status["temperature"]
                    if "bed" in temp_info:
                        bed_temp = temp_info["bed"].get("actual", 0)
                        bed_target = temp_info["bed"].get("target", 0)
                        stdscr.addstr(
                            y, 2, f"Bed Temp: {bed_temp:.1f}°C / {bed_target:.1f}°C"
                        )
                        y += 1

                # Position info
                if "printer" in self.printer_status:
                    printer_info = self.printer_status["printer"]
                    if "axes" in printer_info:
                        axes = printer_info["axes"]
                        x = axes.get("x", {}).get("value", 0)
                        y_pos = axes.get("y", {}).get("value", 0)
                        z = axes.get("z", {}).get("value", 0)
                        stdscr.addstr(y, 2, f"Position: X{x:.1f} Y{y_pos:.1f} Z{z:.1f}")
                        y += 1
        else:
            stdscr.addstr(y, 2, "Connection: ❌ Disconnected", curses.color_pair(1))
            y += 1

        return y + 1

    def draw_menu(self, stdscr, y: int) -> int:
        """Draw the main menu options."""
        stdscr.addstr(y, 0, "🎛️  Controls:", curses.A_BOLD)
        y += 1

        # Menu items with status indicators
        menu_items = [
            (1, "Calibrate", "✅" if self.calibrated else "⏸️"),
            (
                2,
                f"Plate Heater ({'ON' if self.plate_heater_on else 'OFF'}) ({self.target_bed_temp}°C)",
                "🔥" if self.plate_heater_on else "❄️",
            ),
            (3, "Bounding Box Preview", "📐"),
            (4, "Load/Unload Plate", "📤"),
            (5, "Start Print", "▶️"),
            (6, "Settings", "⚙️"),
        ]

        for num, desc, icon in menu_items:
            stdscr.addstr(y, 2, f"{num}. {desc} {icon}")
            y += 1

        y += 1
        stdscr.addstr(y, 0, "Press number key to select, 'q' to quit, 'r' to refresh")
        y += 1

        return y

    def draw_main_screen(self, stdscr):
        """Draw the main screen."""
        stdscr.clear()
        y = 0

        y = self.draw_header(stdscr, y)
        y = self.draw_file_info(stdscr, y)
        y = self.draw_printer_status(stdscr, y)
        y = self.draw_menu(stdscr, y)

        stdscr.refresh()

    def handle_calibrate(self):
        """Handle calibration process."""
        if not self.printer_connected:
            return False

        try:
            # Send calibration G-code commands
            self.printer_client.send_gcode("G28")  # Home all axes
            self.printer_client.send_gcode("G29")  # Auto bed leveling
            self.calibrated = True
            self.logger.info("Calibration completed")
            return True
        except Exception as e:
            self.logger.error(f"Calibration failed: {e}")
            return False

    def handle_plate_heater(self):
        """Toggle plate heater on/off."""
        if not self.printer_connected:
            return False

        try:
            if self.plate_heater_on:
                # Turn off heater
                self.printer_client.send_gcode("M140 S0")
                self.plate_heater_on = False
                self.logger.info("Plate heater turned OFF")
            else:
                # Turn on heater
                self.printer_client.send_gcode(f"M140 S{self.target_bed_temp}")
                self.plate_heater_on = True
                self.logger.info(f"Plate heater turned ON ({self.target_bed_temp}°C)")
            return True
        except Exception as e:
            self.logger.error(f"Heater control failed: {e}")
            return False

    def handle_bounding_box(self):
        """Draw bounding box at fly height."""
        if not self.printer_connected or not self.weld_paths:
            return False

        try:
            min_x, min_y, max_x, max_y = self.get_bounds_info()
            fly_height = getattr(
                self, "move_height", 5.0
            )  # Use config value or default

            # Move to fly height
            travel_speed = getattr(
                self, "travel_speed", 3000
            )  # Use config value or default
            self.printer_client.send_gcode(f"G1 Z{fly_height} F{travel_speed}")

            # Draw rectangle
            commands = [
                f"G1 X{min_x} Y{min_y} F{travel_speed}",  # Bottom left
                f"G1 X{max_x} Y{min_y}",  # Bottom right
                f"G1 X{max_x} Y{max_y}",  # Top right
                f"G1 X{min_x} Y{max_y}",  # Top left
                f"G1 X{min_x} Y{min_y}",  # Back to start
            ]

            for cmd in commands:
                self.printer_client.send_gcode(cmd)

            self.logger.info("Bounding box preview completed")
            return True
        except Exception as e:
            self.logger.error(f"Bounding box preview failed: {e}")
            return False

    def handle_load_unload(self):
        """Drop plate 5cm for loading/unloading."""
        if not self.printer_connected:
            return False

        try:
            # Get current Z position
            status = self.printer_client.get_status()
            current_z = 0
            if "printer" in status and "axes" in status["printer"]:
                current_z = status["printer"]["axes"].get("z", {}).get("value", 0)

            # Drop 5cm
            new_z = current_z - 50
            z_speed = getattr(self, "z_speed", 600)  # Use config value or default
            self.printer_client.send_gcode(f"G1 Z{new_z} F{z_speed}")

            self.logger.info(
                f"Plate lowered by 50mm for loading (Z: {current_z} -> {new_z})"
            )
            return True
        except Exception as e:
            self.logger.error(f"Load/unload failed: {e}")
            return False

    def handle_start_print(self):
        """Start the welding print job."""
        if not self.printer_connected or not self.gcode_file:
            return False

        try:
            # Upload and start the G-code file
            with open(self.gcode_file, "r") as f:
                gcode_content = f.read()

            # Send G-code line by line
            for line in gcode_content.split("\n"):
                line = line.strip()
                if line and not line.startswith(";"):
                    self.printer_client.send_gcode(line)

            self.logger.info(f"Print started: {self.gcode_file}")
            return True
        except Exception as e:
            self.logger.error(f"Print start failed: {e}")
            return False

    def run(self):
        """Main UI loop."""

        def main(stdscr):
            # Initialize colors
            curses.start_color()
            curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
            curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
            curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)

            # Configure curses
            curses.curs_set(0)  # Hide cursor
            stdscr.timeout(100)  # Non-blocking input with 100ms timeout

            self.stdscr = stdscr

            # Initialize and start monitoring
            self.initialize()
            self.start_status_monitoring()

            # Load SVG if provided
            if self.svg_file:
                self.load_svg(self.svg_file)

            try:
                while self.running:
                    if self.current_screen == "main":
                        self.draw_main_screen(stdscr)

                    # Handle input
                    key = stdscr.getch()
                    if key == ord("q"):
                        self.running = False
                    elif key == ord("r"):
                        continue  # Refresh screen
                    elif key == ord("1"):
                        self.handle_calibrate()
                    elif key == ord("2"):
                        self.handle_plate_heater()
                    elif key == ord("3"):
                        self.handle_bounding_box()
                    elif key == ord("4"):
                        self.handle_load_unload()
                    elif key == ord("5"):
                        self.handle_start_print()
                    elif key == ord("6"):
                        # TODO: Implement settings screen
                        pass

            finally:
                self.stop_status_monitoring()

        curses.wrapper(main)


def main():
    """Entry point for microweldr-ui command."""
    import argparse

    parser = argparse.ArgumentParser(description="MicroWeldr Interactive UI")
    parser.add_argument("svg_file", nargs="?", help="SVG file to load")
    parser.add_argument("--config", "-c", help="Configuration file path")

    args = parser.parse_args()

    svg_file = Path(args.svg_file) if args.svg_file else None
    config_file = Path(args.config) if args.config else None

    ui = MicroWeldrUI(svg_file, config_file)
    ui.run()


if __name__ == "__main__":
    main()
