#!/usr/bin/env python3
"""
Prusa USB Terminal - Direct serial communication with Prusa printer.

Usage:
    python scripts/prusa_usb_terminal.py                    # Interactive mode
    python scripts/prusa_usb_terminal.py "M115"             # Send single command
    python scripts/prusa_usb_terminal.py --scan             # Just scan for printers
    python scripts/prusa_usb_terminal.py --interactive      # Interactive terminal
    python scripts/prusa_usb_terminal.py --gcode file.gcode # Send G-code file
    python scripts/prusa_usb_terminal.py -g file.gcode -v   # Send G-code file (verbose)
    python scripts/prusa_usb_terminal.py -g file.gcode -d   # Send G-code file and enter dev mode
    python scripts/prusa_usb_terminal.py --dev-mode         # Standalone developer mode

Developer Mode Features:
    • G-code file simulation - commands sent with proper flow control
    • Background keepalive - maintains printer connection during idle periods
    • Command history with ↑↓ arrows (persistent across sessions)
    • Line editing with ←→ arrows, backspace, etc.
    • Tab completion for G-code commands
    • Perfect for testing, debugging, and interactive development
"""

import argparse
import sys
import time
import threading
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("❌ PySerial not installed. Install with: pip install pyserial")
    sys.exit(1)

try:
    import readline

    # Enable command history and editing
    readline.parse_and_bind("tab: complete")
    readline.parse_and_bind("set editing-mode emacs")
except ImportError:
    print("⚠️  Readline not available - no command history/editing")
    readline = None

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class PrusaUSBTerminal:
    """Direct USB serial communication with Prusa printer."""

    def __init__(self, baudrate: int = 115200, timeout: float = 2.0):
        self.baudrate = baudrate
        self.timeout = timeout
        self.connection: Optional[serial.Serial] = None
        self.printer_info = {}
        self.keepalive_thread: Optional[threading.Thread] = None
        self.keepalive_stop = threading.Event()
        self.last_user_activity = time.time()
        self.last_line_was_keepalive = False

    def scan_usb_ports(self) -> List[Tuple[str, str, str]]:
        """Scan for potential Prusa printers on USB ports."""
        print("🔍 Scanning USB ports for Prusa printers...")

        ports = serial.tools.list_ports.comports()
        prusa_ports = []

        for port in ports:
            port_info = (port.device, port.description, port.manufacturer or "Unknown")
            print(
                f"   Found: {port.device} - {port.description} ({port.manufacturer or 'Unknown'})"
            )

            # Look for Prusa-like devices
            description_lower = port.description.lower()
            manufacturer_lower = (port.manufacturer or "").lower()

            if any(
                keyword in description_lower or keyword in manufacturer_lower
                for keyword in ["prusa", "usb", "serial", "ch340", "ftdi", "arduino"]
            ):
                prusa_ports.append(port_info)
                print(f"   ✅ Potential Prusa device: {port.device}")

        if not prusa_ports:
            print("   ⚠️  No obvious Prusa devices found, will try all ports")
            prusa_ports = [
                (port.device, port.description, port.manufacturer or "Unknown")
                for port in ports
            ]

        return prusa_ports

    def connect_to_printer(self, port: str = None) -> bool:
        """Connect to Prusa printer on specified port or auto-detect."""
        if port:
            return self._try_connect_port(port)

        # Auto-detect
        ports = self.scan_usb_ports()
        if not ports:
            print("❌ No USB ports found")
            return False

        print(f"\n🔌 Trying to connect to {len(ports)} potential ports...")

        for port_device, description, manufacturer in ports:
            print(f"\n📡 Attempting connection to {port_device}...")
            if self._try_connect_port(port_device):
                print(f"✅ Connected to Prusa printer on {port_device}")
                print(f"   Description: {description}")
                print(f"   Manufacturer: {manufacturer}")
                return True

        print("❌ Failed to connect to any USB port")
        return False

    def _try_connect_port(self, port: str) -> bool:
        """Try to connect to a specific port."""
        try:
            print(f"   Connecting to {port} at {self.baudrate} baud...")

            # Open serial connection
            self.connection = serial.Serial(
                port=port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout,
            )

            # Wait for printer to initialize
            time.sleep(2)

            # Clear any startup messages
            self._clear_buffer()

            # Test with M115 (get firmware info)
            response = self.send_command("M115")
            if response and (
                "FIRMWARE_NAME" in response
                or "Prusa" in response
                or "ok" in response.lower()
            ):
                # Parse printer info
                self._parse_printer_info(response)
                return True
            else:
                print(f"   ❌ No valid response from {port}")
                self.disconnect()
                return False

        except Exception as e:
            print(f"   ❌ Failed to connect to {port}: {e}")
            if self.connection:
                try:
                    self.connection.close()
                except:
                    pass
                self.connection = None
            return False

    def _clear_buffer(self):
        """Clear any pending data in the serial buffer."""
        if not self.connection:
            return

        # Read any startup messages
        start_time = time.time()
        while time.time() - start_time < 1.0:  # Read for 1 second
            if self.connection.in_waiting > 0:
                data = (
                    self.connection.readline().decode("utf-8", errors="ignore").strip()
                )
                if data:
                    print(f"   Startup: {data}")
            else:
                time.sleep(0.1)

    def _parse_printer_info(self, response: str):
        """Parse printer information from M115 response."""
        lines = response.split("\n")
        for line in lines:
            if "FIRMWARE_NAME" in line:
                # Extract firmware info
                parts = line.split()
                for part in parts:
                    if ":" in part:
                        key, value = part.split(":", 1)
                        self.printer_info[key] = value

    def send_command(
        self, command: str, verbose: bool = True, wait_for_idle: bool = False
    ) -> str:
        """Send G-code command and return response."""
        if not self.connection:
            return "❌ Not connected to printer"

        try:
            # If printer is busy and we need to wait, do so
            if wait_for_idle:
                self._wait_for_idle()

            # Determine timeout based on command type
            cmd_upper = command.strip().upper()
            if cmd_upper.startswith("G29"):  # Bed leveling
                timeout = 600.0  # 10 minutes for bed leveling
            elif cmd_upper.startswith("G28"):  # Homing
                timeout = 120.0  # 2 minutes for homing
            elif cmd_upper.startswith(("M109", "M190")):  # Wait for temperature
                timeout = 300.0  # 5 minutes for heating
            elif cmd_upper.startswith(("G1", "G0")):  # Movement
                timeout = 60.0  # 1 minute for movements
            else:
                timeout = self.timeout  # Default timeout

            # Send command
            cmd_line = command.strip() + "\n"
            if verbose:
                print(f"📤 Sending: {command}")
                if timeout > self.timeout:
                    print(f"⏱️  Using extended timeout: {timeout:.0f}s for this command")
            self.connection.write(cmd_line.encode("utf-8"))

            # Read response with better busy state handling
            response_lines = []
            start_time = time.time()
            got_ok = False

            last_progress_time = start_time

            while time.time() - start_time < timeout and not got_ok:
                if self.connection.in_waiting > 0:
                    line = (
                        self.connection.readline()
                        .decode("utf-8", errors="ignore")
                        .strip()
                    )
                    if line:
                        response_lines.append(line)
                        if verbose:
                            print(f"📥 Response: {line}")

                        # Check for completion - handle busy state
                        if line.lower().startswith("ok"):
                            got_ok = True
                            break
                        elif "error" in line.lower():
                            break
                        elif "echo:busy: processing" in line.lower():
                            # Printer is busy, extend timeout and continue
                            start_time = time.time()  # Reset timeout
                else:
                    time.sleep(0.1)

                # Show progress for long-running commands
                if timeout > 60 and time.time() - last_progress_time > 10:
                    elapsed = time.time() - start_time
                    if verbose:
                        print(f"⏳ Still processing... ({elapsed:.0f}s elapsed)")
                    last_progress_time = time.time()

            return "\n".join(response_lines)

        except Exception as e:
            return f"❌ Communication error: {e}"

    def _wait_for_idle(self, max_wait: float = 120.0) -> bool:
        """Wait for printer to become idle (not busy)."""
        if not self.connection:
            return False

        start_time = time.time()
        consecutive_ok_count = 0
        required_ok_count = 2  # Need 2 consecutive "ok" responses to be sure

        while time.time() - start_time < max_wait:
            # Send M105 to check status
            self.connection.write(b"M105\n")
            time.sleep(0.3)

            # Read responses
            busy_detected = False
            ok_received = False

            while self.connection.in_waiting > 0:
                line = (
                    self.connection.readline().decode("utf-8", errors="ignore").strip()
                )
                if line:
                    if "echo:busy: processing" in line.lower():
                        busy_detected = True
                        consecutive_ok_count = 0  # Reset counter
                    elif line.lower().startswith("ok"):
                        ok_received = True

            # Count consecutive OK responses without busy
            if ok_received and not busy_detected:
                consecutive_ok_count += 1
                if consecutive_ok_count >= required_ok_count:
                    return True
            else:
                consecutive_ok_count = 0

            time.sleep(0.5)

        return False

    def _start_keepalive(self, interval: float = 30.0):
        """Start background keepalive to maintain printing mode."""
        if self.keepalive_thread and self.keepalive_thread.is_alive():
            return  # Already running

        self.keepalive_stop.clear()
        self.keepalive_thread = threading.Thread(
            target=self._keepalive_worker, args=(interval,), daemon=True
        )
        self.keepalive_thread.start()
        print(f"🔄 Started keepalive (every {interval}s)")

    def _stop_keepalive(self):
        """Stop background keepalive."""
        if self.keepalive_thread:
            self.keepalive_stop.set()
            self.keepalive_thread.join(timeout=1.0)
            print("⏹️  Stopped keepalive")

    def _keepalive_worker(self, interval: float):
        """Background worker that sends keepalive commands."""
        while not self.keepalive_stop.wait(interval):
            if not self.connection:
                break

            # Check if user has been idle
            idle_time = time.time() - self.last_user_activity
            if idle_time >= interval:
                try:
                    # Send M105 to get temperatures
                    self.connection.write(b"M105\n")

                    # Read response and parse temperature data
                    temp_data = ""
                    start_time = time.time()
                    while time.time() - start_time < 1.0:
                        if self.connection.in_waiting > 0:
                            line = (
                                self.connection.readline()
                                .decode("utf-8", errors="ignore")
                                .strip()
                            )
                            if line and "T:" in line:
                                temp_data = line
                            elif line.lower().startswith("ok"):
                                break
                        else:
                            time.sleep(0.05)

                    # Parse and display temperature info
                    if temp_data:
                        temps = self._parse_temperature_data(temp_data)
                        temp_display = f"💓 T:{temps.get('nozzle', '?')}°C B:{temps.get('bed', '?')}°C idle:{idle_time:.0f}s"
                    else:
                        temp_display = f"💓 Keepalive (idle {idle_time:.0f}s)"

                    # Overwrite previous keepalive line or print new line
                    if self.last_line_was_keepalive:
                        print(f"\r{temp_display}", end="", flush=True)
                    else:
                        print(f"\n{temp_display}", end="", flush=True)

                    self.last_line_was_keepalive = True

                except:
                    break  # Connection lost

    def _parse_temperature_data(self, temp_line: str) -> dict:
        """Parse temperature data from M105 response."""
        temps = {}
        try:
            # Parse T:current/target format
            if "T:" in temp_line:
                t_part = temp_line.split("T:")[1].split()[0]
                if "/" in t_part:
                    current = t_part.split("/")[0]
                    temps["nozzle"] = f"{float(current):.0f}"

            if "B:" in temp_line:
                b_part = temp_line.split("B:")[1].split()[0]
                if "/" in b_part:
                    current = b_part.split("/")[0]
                    temps["bed"] = f"{float(current):.0f}"
        except:
            pass
        return temps

    def _explain_gcode_command(self, command: str) -> str:
        """Provide a human-readable explanation of what a G-code command does."""
        cmd = command.strip().upper()

        # Movement commands
        if cmd.startswith("G1 "):
            parts = cmd.split()
            moves = []
            feedrate = ""
            extrude = ""

            for part in parts[1:]:
                if part.startswith("X"):
                    moves.append(f"X to {part[1:]}mm")
                elif part.startswith("Y"):
                    moves.append(f"Y to {part[1:]}mm")
                elif part.startswith("Z"):
                    moves.append(f"Z to {part[1:]}mm")
                elif part.startswith("F"):
                    feedrate = f" at {part[1:]}mm/min"
                elif part.startswith("E"):
                    extrude = f" extruding {part[1:]}mm"

            if moves:
                move_desc = "Move " + ", ".join(moves) + feedrate + extrude
                return move_desc

        # Common G-codes
        if cmd == "G28":
            return "Home all axes (move to origin)"
        elif cmd.startswith("G28 "):
            axes = cmd.replace("G28 ", "").replace(" ", "")
            return f"Home {axes} axis/axes"
        elif cmd == "G29":
            return "Auto bed leveling (probe bed surface)"
        elif cmd == "G90":
            return "Set absolute positioning mode"
        elif cmd == "G91":
            return "Set relative positioning mode"
        elif cmd == "G92":
            return "Set current position as origin"

        # M-codes
        elif cmd == "M105":
            return "Get current temperatures"
        elif cmd == "M115":
            return "Get firmware info and capabilities"
        elif cmd.startswith("M104 "):
            temp = cmd.replace("M104 S", "")
            return f"Set nozzle temperature to {temp}°C"
        elif cmd.startswith("M109 "):
            temp = cmd.replace("M109 S", "")
            return f"Set nozzle temperature to {temp}°C and wait"
        elif cmd.startswith("M140 "):
            temp = cmd.replace("M140 S", "")
            return f"Set bed temperature to {temp}°C"
        elif cmd.startswith("M190 "):
            temp = cmd.replace("M190 S", "")
            return f"Set bed temperature to {temp}°C and wait"
        elif cmd == "M82":
            return "Set absolute extrusion mode"
        elif cmd == "M83":
            return "Set relative extrusion mode"
        elif cmd == "M84":
            return "Disable stepper motors"

        return ""  # No explanation available

    def _update_activity(self):
        """Update last user activity timestamp."""
        self.last_user_activity = time.time()
        # Reset keepalive line flag when user is active
        if self.last_line_was_keepalive:
            print()  # Move to new line
            self.last_line_was_keepalive = False

    def interactive_mode(self):
        """Interactive terminal mode."""
        print("\n🖥️  Interactive Prusa Terminal")
        print("   Type G-code commands (e.g., M115, M503, G28)")
        print("   Type 'quit' or 'exit' to quit")
        print("   Type 'help' for common commands")
        print("   Type 'wait' to wait for printer to become idle")
        print("   Add '!' to force wait for idle before command (e.g., '!G1 X10')")

        while True:
            try:
                command = input("\nPrusa> ").strip()

                if command.lower() in ["quit", "exit", "q"]:
                    break
                elif command.lower() == "help":
                    self._show_help()
                elif command.lower() == "wait":
                    self._wait_for_idle()
                elif command.startswith("!"):
                    # Force wait for idle before sending command
                    actual_command = command[1:].strip()
                    if actual_command:
                        response = self.send_command(actual_command, wait_for_idle=True)
                        if not response:
                            print("   (No response)")
                elif command:
                    response = self.send_command(command)
                    if not response:
                        print("   (No response)")

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except EOFError:
                break

    def gcode_simulation_mode(self):
        """G-code file simulation mode - treat each input like a file command."""
        print("\n📄 G-code File Simulation Mode")
        print("   Each command you type is sent with G-code file flow control")
        print("   Use ↑↓ arrows for command history, ←→ for editing")
        print("   Type 'quit' or 'exit' to quit")
        print("   Type 'help' for common commands")

        # Start keepalive to maintain printing mode
        # Use 2 second interval for real-time temperature monitoring
        keepalive_interval = 2.0
        self._start_keepalive(interval=keepalive_interval)

        # Set up command history if readline is available
        if readline:
            # Set history file for persistence across sessions
            history_file = Path.home() / ".microweldr_gcode_history"
            try:
                readline.read_history_file(str(history_file))
            except FileNotFoundError:
                pass  # No history file yet

            # Set up completion for common G-code commands
            def gcode_completer(text, state):
                commands = [
                    "G1 ",
                    "G28",
                    "G29",
                    "G90",
                    "G91",
                    "G92 ",
                    "M104 S",
                    "M105",
                    "M109 S",
                    "M114",
                    "M115",
                    "M140 S",
                    "M190 S",
                    "M220 S",
                    "M221 S",
                    "M25",
                    "M24",
                    "M524",
                    "M27",
                    "M84",
                    "help",
                    "quit",
                    "exit",
                ]
                matches = [cmd for cmd in commands if cmd.startswith(text.upper())]
                try:
                    return matches[state]
                except IndexError:
                    return None

            readline.set_completer(gcode_completer)
            readline.set_completer_delims(" \t\n")

        command_count = 0

        try:
            while True:
                try:
                    command = input(f"\nG-code[{command_count + 1}]> ").strip()

                    # Update activity timestamp whenever user types something
                    self._update_activity()

                    if command.lower() in ["quit", "exit", "q"]:
                        break
                    elif command.lower() == "help":
                        self._show_help()
                    elif command and not command.startswith(";"):
                        # Send command with file-like flow control (non-verbose)
                        command_count += 1

                        # Explain what the command does
                        explanation = self._explain_gcode_command(command)
                        if explanation:
                            print(f"🎯 About to: {explanation}")

                        print(f"📤 [{command_count}] Sending: {command}")
                        response = self.send_command(command, verbose=False)

                        # Show important responses with explanations
                        if response:
                            lines = response.split("\n")
                            for line in lines:
                                if line.strip():
                                    if "error" in line.lower():
                                        print(f"❌ Error: {line}")
                                    elif "echo:busy: processing" in line.lower():
                                        print(f"⏳ Printer busy: {line}")
                                    elif line.lower().startswith("ok"):
                                        print(f"✅ Command completed: {line}")
                                    elif "T:" in line and "B:" in line:
                                        # Parse temperature data
                                        temps = self._parse_temperature_data(line)
                                        nozzle = temps.get("nozzle", "?")
                                        bed = temps.get("bed", "?")
                                        print(
                                            f"🌡️  Temperatures: Nozzle {nozzle}°C, Bed {bed}°C"
                                        )
                                        print(f"📊 Full data: {line}")
                                    elif "echo:" in line.lower():
                                        print(f"💬 Printer says: {line}")
                                    else:
                                        print(f"📥 Response: {line}")

                        # Small delay like file sending
                        time.sleep(0.1)
                    elif command.startswith(";"):
                        print(f"💬 Comment: {command}")

                except KeyboardInterrupt:
                    print("\n👋 Goodbye!")
                    break
                except EOFError:
                    break
        finally:
            # Stop keepalive
            self._stop_keepalive()

            # Save command history
            if readline:
                try:
                    readline.write_history_file(str(history_file))
                    # Keep only last 1000 commands
                    readline.set_history_length(1000)
                except:
                    pass

    def send_gcode_file(self, filename: str, verbose: bool = False) -> bool:
        """Send entire G-code file to printer."""
        if not self.connection:
            print("❌ Not connected to printer")
            return False

        try:
            filepath = Path(filename)
            if not filepath.exists():
                print(f"❌ File not found: {filename}")
                return False

            print(f"📁 Reading G-code file: {filename}")
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Filter out comments and empty lines for cleaner output
            gcode_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith(";"):
                    gcode_lines.append(line)

            print(f"📊 Found {len(gcode_lines)} G-code commands to send")
            print(f"📡 Starting transmission...")

            success_count = 0
            error_count = 0

            for i, command in enumerate(gcode_lines, 1):
                if verbose:
                    print(f"\n[{i}/{len(gcode_lines)}] Processing: {command}")
                else:
                    # Show progress every 50 commands
                    if i % 50 == 0 or i == len(gcode_lines):
                        print(f"📈 Progress: {i}/{len(gcode_lines)} commands sent")

                # Send command with proper flow control
                response = self.send_command(
                    command, verbose=verbose, wait_for_idle=True
                )

                if "error" in response.lower():
                    error_count += 1
                    print(f"⚠️  Error on line {i}: {command}")
                    print(f"   Response: {response}")

                    # Ask user if they want to continue on errors
                    if not verbose:
                        user_input = input(
                            "Continue sending? (y/n/v for verbose): "
                        ).lower()
                        if user_input == "n":
                            break
                        elif user_input == "v":
                            verbose = True
                else:
                    success_count += 1

                # Adaptive delay based on command type
                if command.startswith(("G1", "G0")):  # Movement commands
                    time.sleep(0.5)  # Longer delay for movements
                elif command.startswith("G4"):  # Dwell commands
                    time.sleep(0.2)  # Medium delay for dwells
                else:
                    time.sleep(0.1)  # Short delay for other commands

            print(f"\n✅ G-code transmission complete!")
            print(f"   Successful: {success_count}")
            print(f"   Errors: {error_count}")
            print(f"   Total: {len(gcode_lines)}")

            return error_count == 0

        except Exception as e:
            print(f"❌ Error sending G-code file: {e}")
            return False

    def _show_help(self):
        """Show common G-code commands."""
        print("\n📚 Common Prusa G-code Commands:")
        print("   M115    - Get firmware version and capabilities")
        print("   M503    - Get current settings")
        print("   M105    - Get temperatures")
        print("   M114    - Get current position")
        print("   G28     - Home all axes")
        print("   M84     - Disable steppers")
        print("   M220    - Get/set speed factor")
        print("   M221    - Get/set flow rate")
        print("   M92     - Get/set steps per unit")
        print("\n🖨️  Print Control Commands:")
        print("   M524    - Abort current print")
        print("   M25     - Pause print")
        print("   M24     - Resume print")
        print("   M27     - Get print progress")
        print("   M73     - Set print progress")
        print("\n🌡️  Temperature Commands:")
        print("   M104 S160 - Set nozzle temperature")
        print("   M140 S35  - Set bed temperature")
        print("   M106 S255 - Turn on part cooling fan")
        print("   M107      - Turn off part cooling fan")
        print("\n⚡ Special Interactive Commands:")
        print("   wait      - Wait for printer to become idle")
        print("   !<cmd>    - Wait for idle, then send command")
        print("   !G1 X10   - Example: wait for idle, then move")
        print("   quit/exit - Exit terminal")

    def disconnect(self):
        """Disconnect from printer."""
        # Stop keepalive first
        self._stop_keepalive()

        if self.connection:
            try:
                self.connection.close()
            except:
                pass
            self.connection = None
            print("🔌 Disconnected from printer")

    def get_printer_info(self) -> dict:
        """Get parsed printer information."""
        return self.printer_info.copy()


def main():
    parser = argparse.ArgumentParser(description="Prusa USB Terminal")
    parser.add_argument("command", nargs="?", help="G-code command to send")
    parser.add_argument("--scan", action="store_true", help="Just scan for printers")
    parser.add_argument(
        "--interactive", "-i", action="store_true", help="Interactive mode"
    )
    parser.add_argument("--gcode", "-g", help="Send G-code file to printer")
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output for G-code file sending",
    )
    parser.add_argument(
        "--dev-mode",
        "-d",
        action="store_true",
        help="Developer mode - G-code simulation with keepalive (works standalone or after file)",
    )
    parser.add_argument(
        "--stay-connected",
        "-s",
        action="store_true",
        help="Legacy alias for --dev-mode",
    )
    parser.add_argument(
        "--test-keepalive",
        action="store_true",
        help="Use 10s keepalive interval for testing (instead of 30s)",
    )
    parser.add_argument("--port", "-p", help="Specific USB port to use")
    parser.add_argument(
        "--baudrate", "-b", type=int, default=115200, help="Baud rate (default: 115200)"
    )

    args = parser.parse_args()

    # Handle legacy flag
    dev_mode = args.dev_mode or args.stay_connected

    terminal = PrusaUSBTerminal(baudrate=args.baudrate)

    # Set test mode for shorter keepalive if requested
    if args.test_keepalive:
        terminal._test_mode = True

    try:
        if args.scan:
            # Just scan and exit
            ports = terminal.scan_usb_ports()
            print(f"\n📊 Found {len(ports)} potential USB ports")
            return

        # Connect to printer
        if not terminal.connect_to_printer(args.port):
            print("\n❌ Could not connect to Prusa printer")
            print("\n💡 Troubleshooting:")
            print("   • Make sure printer is connected via USB")
            print("   • Check that printer is powered on")
            print("   • Try different baud rates: --baudrate 250000")
            print("   • Check USB cable connection")
            sys.exit(1)

        # Show printer info
        info = terminal.get_printer_info()
        if info:
            print(f"\n🖨️  Printer Information:")
            for key, value in info.items():
                print(f"   {key}: {value}")

        if args.gcode:
            # G-code file mode
            print(f"\n📄 Sending G-code file: {args.gcode}")
            success = terminal.send_gcode_file(args.gcode, verbose=args.verbose)
            if success:
                print("🎉 G-code file sent successfully!")
            else:
                print("⚠️  G-code file transmission had errors")
                if not dev_mode:
                    sys.exit(1)

            # Enter dev mode after file if requested
            if dev_mode:
                print("\n🔧 Entering Developer Mode...")
                print("   Printer is now in printing mode")
                print(
                    "   Each command you type will be sent with G-code file flow control"
                )
                terminal.gcode_simulation_mode()
        elif dev_mode:
            # Standalone dev mode
            print("\n🔧 Developer Mode - Standalone G-code Simulation")
            print("   Direct G-code simulation with keepalive")
            print("   Perfect for testing and development")
            terminal.gcode_simulation_mode()
        elif args.interactive or not args.command:
            # Interactive mode
            terminal.interactive_mode()
        else:
            # Single command mode
            response = terminal.send_command(args.command)
            print(f"\n📋 Final Response:\n{response}")

    finally:
        terminal.disconnect()


if __name__ == "__main__":
    main()
