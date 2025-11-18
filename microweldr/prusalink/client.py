"""PrusaLink API client for G-code submission."""

import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
import toml
from requests.auth import HTTPDigestAuth

from ..core.secrets_config import load_prusalink_config
from .exceptions import (
    PrusaLinkAuthError,
    PrusaLinkConfigError,
    PrusaLinkConnectionError,
    PrusaLinkError,
    PrusaLinkFileError,
    PrusaLinkJobError,
    PrusaLinkOperationError,
    PrusaLinkUploadError,
    PrusaLinkValidationError,
)

logger = logging.getLogger(__name__)


class PrusaLinkClient:
    """Client for interacting with PrusaLink API."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize PrusaLink client.

        Args:
            config_path: Path to specific config file. If None, uses hierarchical config loading.
        """
        self.config = self._load_config(config_path)
        self.base_url = f"http://{self.config['host']}"

        # Support both API key and LCD password authentication
        password = self.config.get("password") or self.config.get("api_key")
        self.auth = HTTPDigestAuth(self.config["username"], password)
        self.timeout = self.config.get("timeout", 30)

    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load configuration using hierarchical config loading or specific file."""
        try:
            prusalink_config = load_prusalink_config(config_path)
        except FileNotFoundError as e:
            raise PrusaLinkConfigError(str(e))
        except KeyError as e:
            raise PrusaLinkConfigError(str(e))
        except Exception as e:
            raise PrusaLinkConfigError(f"Failed to load configuration: {e}")

        # Validate required fields
        required_fields = ["host", "username"]
        for field in required_fields:
            if field not in prusalink_config:
                raise PrusaLinkConfigError(f"Missing required field: {field}")

        # Require either password or api_key
        if "password" not in prusalink_config and "api_key" not in prusalink_config:
            raise PrusaLinkConfigError(
                "Missing required field: either 'password' (LCD password) or 'api_key'"
            )

        return prusalink_config

    def test_connection(self) -> bool:
        """Test connection to PrusaLink API.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/version", auth=self.auth, timeout=self.timeout
            )

            # Return True only for successful responses
            return response.status_code == 200

        except (
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.RequestException,
        ):
            # Return False for any connection issues
            return False

    def get_printer_info(self) -> Dict[str, Any]:
        """Get printer information.

        Returns:
            Dictionary containing printer information.

        Raises:
            PrusaLinkConnectionError: If connection fails.
            PrusaLinkAuthError: If authentication fails.
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/info", auth=self.auth, timeout=self.timeout
            )

            if response.status_code == 401:
                raise PrusaLinkAuthError(
                    "Authentication failed. Check your credentials."
                )
            elif response.status_code != 200:
                raise PrusaLinkConnectionError(
                    f"Failed to get printer info: {response.status_code}"
                )

            return response.json()

        except requests.exceptions.RequestException as e:
            raise PrusaLinkConnectionError(f"Connection failed: {e}")

    def get_storage_info(self) -> Dict[str, Any]:
        """Get available storage information.

        Returns:
            Dictionary containing storage information.
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/storage", auth=self.auth, timeout=self.timeout
            )

            if response.status_code == 401:
                raise PrusaLinkAuthError(
                    "Authentication failed. Check your credentials."
                )
            elif response.status_code != 200:
                raise PrusaLinkConnectionError(
                    f"Failed to get storage info: {response.status_code}"
                )

            return response.json()

        except requests.exceptions.RequestException as e:
            raise PrusaLinkConnectionError(f"Connection failed: {e}")

    def upload_gcode(
        self,
        gcode_path: str,
        storage: Optional[str] = None,
        remote_filename: Optional[str] = None,
        auto_start: Optional[bool] = None,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """Upload G-code file to printer.

        Args:
            gcode_path: Path to local G-code file.
            storage: Target storage ("local" or "usb"). If None, uses config default.
            remote_filename: Name for file on printer. If None, uses original filename.
            auto_start: Whether to start printing after upload. If None, uses config default.
            overwrite: Whether to overwrite existing files.

        Returns:
            Dictionary containing upload response.

        Raises:
            PrusaLinkUploadError: If upload fails.
            PrusaLinkConnectionError: If connection fails.
            PrusaLinkAuthError: If authentication fails.
        """
        gcode_file = Path(gcode_path)
        if not gcode_file.exists():
            raise PrusaLinkUploadError(f"G-code file not found: {gcode_path}")

        if storage is None:
            storage = self.config.get("default_storage", "local")

        if remote_filename is None:
            remote_filename = gcode_file.name

        if auto_start is None:
            auto_start = self.config.get("auto_start_print", False)

        # Prepare headers
        headers = {
            "Content-Type": "application/octet-stream",
            "Print-After-Upload": "?1" if auto_start else "?0",
            "Overwrite": "?1" if overwrite else "?0",
        }

        # Read file content
        try:
            with open(gcode_file, "rb") as f:
                file_content = f.read()
        except Exception as e:
            raise PrusaLinkUploadError(f"Failed to read G-code file: {e}")

        headers["Content-Length"] = str(len(file_content))

        # Upload file
        url = f"{self.base_url}/api/v1/files/{storage}/{remote_filename}"

        # Debug logging for upload details
        logger.info(f"Upload URL: {url}")
        logger.info(f"Upload headers: {headers}")
        logger.info(f"File size: {len(file_content)} bytes")
        logger.info(f"Storage: {storage}")
        logger.info(f"Remote filename: {remote_filename}")

        try:
            response = requests.put(
                url,
                data=file_content,
                headers=headers,
                auth=self.auth,
                timeout=self.timeout,
            )

            # Log response details
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            logger.info(f"Response text: {response.text}")

            if response.status_code == 401:
                raise PrusaLinkAuthError(
                    "Authentication failed. Check your credentials."
                )
            elif response.status_code == 403:
                raise PrusaLinkUploadError(
                    f"Upload forbidden (403): {response.text}. "
                    f"Check printer permissions, storage availability, or API access rights. "
                    f"URL: {url}, Storage: {storage}"
                )
            elif response.status_code == 409:
                raise PrusaLinkUploadError(
                    f"File already exists: {remote_filename}. Use overwrite=True to replace it."
                )
            elif response.status_code == 404:
                raise PrusaLinkUploadError(f"Storage not found: {storage}")
            elif response.status_code not in [201, 200]:
                raise PrusaLinkUploadError(
                    f"Upload failed with status {response.status_code}: {response.text}"
                )

            return {
                "status": "success",
                "filename": remote_filename,
                "storage": storage,
                "auto_started": auto_start,
                "response_code": response.status_code,
            }

        except requests.exceptions.RequestException as e:
            raise PrusaLinkConnectionError(f"Connection failed during upload: {e}")

    def get_printer_status(self) -> Dict[str, Any]:
        """Get printer status including readiness for printing.

        Returns:
            Dictionary containing printer status information.
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/status", auth=self.auth, timeout=self.timeout
            )

            if response.status_code == 401:
                raise PrusaLinkAuthError(
                    "Authentication failed. Check your credentials."
                )
            elif response.status_code != 200:
                raise PrusaLinkConnectionError(
                    f"Failed to get printer status: {response.status_code}"
                )

            return response.json()

        except requests.exceptions.RequestException as e:
            raise PrusaLinkConnectionError(f"Connection failed: {e}")

    def is_printer_ready(self) -> bool:
        """Check if printer is ready to start a new print job.

        Returns:
            True if printer is ready, False otherwise.
        """
        try:
            status = self.get_printer_status()
            printer_state = status.get("printer", {}).get("state", "").lower()

            # Printer is ready if it's operational and not printing
            ready_states = ["operational", "ready", "idle"]
            return any(state in printer_state for state in ready_states)

        except PrusaLinkError:
            return False

    def get_job_status(self) -> Optional[Dict[str, Any]]:
        """Get current job status.

        Returns:
            Dictionary containing job information, or None if no job running.
        """
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/job", auth=self.auth, timeout=self.timeout
            )

            if response.status_code == 204:
                return None  # No job running
            elif response.status_code == 401:
                raise PrusaLinkAuthError(
                    "Authentication failed. Check your credentials."
                )
            elif response.status_code != 200:
                raise PrusaLinkConnectionError(
                    f"Failed to get job status: {response.status_code}"
                )

            return response.json()

        except requests.exceptions.RequestException as e:
            raise PrusaLinkConnectionError(f"Connection failed: {e}")

    def stop_print(self) -> bool:
        """Stop the current print job."""
        try:
            response = self.session.delete(f"{self.base_url}/api/job")

            if response.status_code == 401:
                raise PrusaLinkAuthError(
                    "Authentication failed. Check your credentials."
                )
            elif response.status_code == 409:
                # No job running or already stopped
                return True
            elif response.status_code != 204:
                raise PrusaLinkConnectionError(
                    f"Failed to stop print: {response.status_code}"
                )

            return True

        except requests.exceptions.RequestException as e:
            raise PrusaLinkConnectionError(f"Connection failed: {e}")

    def wait_for_printer_ready(self, timeout_seconds: int = 300) -> bool:
        """Wait for printer to finish current job and become ready.

        Args:
            timeout_seconds: Maximum time to wait (default: 5 minutes)

        Returns:
            True if printer is ready, False if timeout
        """
        import time

        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            try:
                # Check printer status
                status = self.get_printer_status()
                printer_info = status.get("printer", {})
                state = printer_info.get("state", "Unknown").upper()

                # Check if printer is ready (idle)
                if state in ["IDLE", "READY", "FINISHED"]:
                    return True
                elif state in ["PRINTING", "PAUSED"]:
                    # Still busy, wait a bit
                    time.sleep(2)
                    continue
                elif state in ["ERROR", "CANCELLED"]:
                    # Error state, don't wait
                    return False
                else:
                    # Unknown state, wait a bit
                    time.sleep(2)
                    continue

            except Exception:
                # If we can't get status, wait a bit and try again
                time.sleep(2)
                continue

        # Timeout reached
        return False

    def delete_file(self, filename: str, storage: str = "local") -> bool:
        """Delete a file from printer storage.

        Args:
            filename: Name of file to delete
            storage: Storage location ("usb" or "local")

        Returns:
            True if file was deleted successfully
        """
        try:
            import requests

            url = f"{self.base_url}/api/v1/files/{storage}/{filename}"
            response = requests.delete(url, auth=self.auth, timeout=self.timeout)

            # 204 = successfully deleted, 404 = file not found (already gone)
            return response.status_code in [204, 404]

        except Exception:
            # If delete fails, don't crash - just log it
            return False

    def send_and_run_gcode(
        self,
        commands: list[str],
        wait_for_completion: bool = True,
        keep_temp_file: bool = False,
        print_to_stdout: bool = False,
        job_name: str = "temp_gcode",
    ) -> bool:
        """Send and run G-code commands via temporary file upload.

        Args:
            commands: List of G-code commands to send
            wait_for_completion: Whether to wait for completion before returning
            keep_temp_file: Whether to keep the temporary file on printer
            print_to_stdout: Whether to print the G-code to stdout
            job_name: Base name for the temporary file

        Returns:
            True if commands were executed successfully

        Raises:
            PrusaLinkConnectionError: If connection fails
        """
        try:
            import os
            import tempfile
            import time

            # First, wait for printer to be ready
            if not self.wait_for_printer_ready(timeout_seconds=300):
                raise PrusaLinkConnectionError(
                    "Printer not ready - still busy or in error state after 5 minutes"
                )

            # Create G-code content
            gcode_lines = [
                f"; Generated G-code: {job_name}",
                f"; Created: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                "",
            ]
            gcode_lines.extend(commands)
            gcode_lines.append("")  # End with newline

            gcode_content = "\n".join(gcode_lines)

            # Print to stdout if requested
            if print_to_stdout:
                print("Generated G-code:")
                print("-" * 40)
                print(gcode_content)
                print("-" * 40)

            temp_filename = f"{job_name}_{int(time.time())}.gcode"

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".gcode", delete=False
            ) as f:
                f.write(gcode_content)
                temp_file_path = f.name

            try:
                # Upload and auto-start the G-code
                result = self.upload_gcode(
                    gcode_path=temp_file_path,
                    storage="local",  # Use local storage since USB not available
                    remote_filename=temp_filename,
                    auto_start=True,
                    overwrite=True,
                )

                # Clean up local temp file
                os.unlink(temp_file_path)

                if not (result and result.get("status") == "success"):
                    raise PrusaLinkConnectionError(f"G-code upload failed: {result}")

                # If requested, wait for completion and optionally clean up remote file
                if wait_for_completion:
                    if self.wait_for_printer_ready(timeout_seconds=600):
                        if not keep_temp_file:
                            self.delete_file(temp_filename, storage="local")
                    else:
                        # Even if timeout, try to clean up (unless keeping)
                        if not keep_temp_file:
                            self.delete_file(temp_filename, storage="local")

                        # Check if printer is in error state
                        self._check_printer_error_state()

                        raise PrusaLinkConnectionError(
                            f"G-code job '{job_name}' timed out after 10 minutes"
                        )

                return True

            except Exception as e:
                # Clean up local temp file on error
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                # Try to clean up remote file too (unless keeping)
                if not keep_temp_file:
                    self.delete_file(temp_filename, storage="local")
                raise e

        except Exception as e:
            # Check if this is a critical error that requires halting operations
            if isinstance(e, PrusaLinkOperationError) and any(
                keyword in str(e).lower()
                for keyword in ["error state", "cancelled", "rejected", "clamped"]
            ):
                # This is a critical error - halt operations for safety
                self.halt_print_operations(f"Critical error in {job_name}: {e}")

            raise PrusaLinkConnectionError(
                f"Failed to execute G-code job '{job_name}': {e}"
            )

    def send_gcode(self, command: str, wait_for_completion: bool = True) -> bool:
        """Send a single G-code command to the printer via temporary file upload.

        Args:
            command: G-code command to send (e.g., "G28", "M140 S60")
            wait_for_completion: Whether to wait for command to complete before returning

        Returns:
            True if command was sent successfully, False otherwise

        Raises:
            PrusaLinkConnectionError: If connection fails
        """
        return self.send_and_run_gcode(
            commands=[command],
            wait_for_completion=wait_for_completion,
            job_name="temp_cmd",
        )

    # High-level printer operation methods
    def calibrate_printer(self, bed_leveling: bool = True, **kwargs) -> bool:
        """Perform printer calibration.

        Args:
            bed_leveling: Whether to include bed leveling (G29)
            **kwargs: Additional options for send_and_run_gcode

        Returns:
            True if calibration successful
        """
        commands = ["G28  ; Home all axes"]
        if bed_leveling:
            commands.append("G29  ; Auto bed leveling")
        commands.append("M117 Calibration complete")

        return self.send_and_run_gcode(
            commands=commands, job_name="calibration", **kwargs
        )

    def home_axes(self, axes: str = "XYZ", **kwargs) -> bool:
        """Home specified axes.

        Args:
            axes: Axes to home ("X", "Y", "Z", "XY", "XYZ", etc.)
            **kwargs: Additional options for send_and_run_gcode

        Returns:
            True if homing successful
        """
        if axes.upper() == "XYZ" or not axes:
            command = "G28  ; Home all axes"
        else:
            axis_list = " ".join(axes.upper())
            command = f"G28 {axis_list}  ; Home {axes.upper()} axes"

        return self.send_and_run_gcode(
            commands=[command], job_name="home_axes", **kwargs
        )

    def set_bed_temperature(
        self, temperature: float, wait: bool = False, **kwargs
    ) -> bool:
        """Set bed temperature.

        Args:
            temperature: Target temperature in Celsius
            wait: Whether to wait for temperature to be reached
            **kwargs: Additional options for send_and_run_gcode

        Returns:
            True if command successful

        Raises:
            PrusaLinkValidationError: If temperature is out of safe range
        """
        # Validate temperature range
        if temperature < 0:
            raise PrusaLinkValidationError(
                f"Bed temperature cannot be negative: {temperature}°C"
            )
        elif temperature > 120:  # Typical max for heated beds
            raise PrusaLinkValidationError(
                f"Bed temperature {temperature}°C exceeds safe maximum (120°C). "
                "Use --force flag if you really need this temperature."
            )

        commands = []
        if wait:
            commands.append(f"M190 S{temperature}  ; Set bed temp and wait")
        else:
            commands.append(f"M140 S{temperature}  ; Set bed temp")
        commands.append(f"M117 Bed temp set to {temperature}C")

        try:
            result = self.send_and_run_gcode(
                commands=commands, job_name="set_bed_temp", **kwargs
            )

            # Always verify the temperature was actually set by checking printer status
            if result:
                self._verify_temperature_set(temperature, "bed")

            return result

        except Exception as e:
            if isinstance(e, (PrusaLinkValidationError, PrusaLinkOperationError)):
                raise
            raise PrusaLinkOperationError(f"Failed to set bed temperature: {e}")

    def _verify_temperature_set(self, expected_temp: float, heater_type: str) -> None:
        """Verify that temperature was actually set on the printer.

        Args:
            expected_temp: Expected temperature
            heater_type: 'bed' or 'nozzle'

        Raises:
            PrusaLinkOperationError: If temperature was not set correctly
        """
        try:
            import time

            time.sleep(1)  # Give printer time to process command

            status = self.get_printer_status()
            printer_info = status.get("printer", {})

            if heater_type == "bed":
                actual_target = printer_info.get("target_bed", 0)
            else:
                actual_target = printer_info.get("target_nozzle", 0)

            # Check if temperature was clamped or rejected
            if abs(actual_target - expected_temp) > 1:  # Allow 1°C tolerance
                if actual_target == 0 and expected_temp > 0:
                    raise PrusaLinkOperationError(
                        f"Printer rejected {heater_type} temperature {expected_temp}°C "
                        "(target remains 0°C)"
                    )
                elif actual_target != expected_temp:
                    raise PrusaLinkOperationError(
                        f"Printer clamped {heater_type} temperature from {expected_temp}°C "
                        f"to {actual_target}°C (safety limit reached)"
                    )

        except Exception as e:
            if isinstance(e, PrusaLinkOperationError):
                raise
            # Don't fail the whole operation if we can't verify
            pass

    def _check_printer_error_state(self) -> None:
        """Check if printer is in an error state and raise appropriate exception.

        Raises:
            PrusaLinkOperationError: If printer is in error state
        """
        try:
            status = self.get_printer_status()
            printer_info = status.get("printer", {})
            state = printer_info.get("state", "Unknown").upper()

            if state in ["ERROR", "STOPPED", "FAULT"]:
                raise PrusaLinkOperationError(
                    f"Printer is in error state: {state}. "
                    "Check printer display and resolve issues before continuing."
                )
            elif state == "CANCELLED":
                raise PrusaLinkOperationError(
                    "Print operation was cancelled. Check printer for issues."
                )

        except Exception as e:
            if isinstance(e, PrusaLinkOperationError):
                raise
            # Don't fail if we can't check status
            pass

    def halt_print_operations(self, reason: str = "Safety halt") -> bool:
        """Halt all print operations and put printer in safe state.

        This method should be called when any critical error occurs during
        G-code operations to ensure printer safety.

        Args:
            reason: Reason for halting operations

        Returns:
            True if halt was successful
        """
        try:
            print(f"🛑 HALTING PRINT OPERATIONS: {reason}")

            # Try to stop current job
            try:
                self.stop_print()
                print("   ✓ Current job stopped")
            except Exception:
                print("   ⚠️  Could not stop current job")

            # Turn off all heaters for safety
            try:
                self.send_and_run_gcode(
                    commands=[
                        "M104 S0  ; Turn off nozzle heater",
                        "M140 S0  ; Turn off bed heater",
                        "M107     ; Turn off fans",
                        "M117 OPERATIONS HALTED",
                    ],
                    job_name="emergency_halt",
                    wait_for_completion=False,  # Don't wait, just send
                )
                print("   ✓ Heaters and fans turned off")
            except Exception:
                print("   ⚠️  Could not turn off heaters")

            # Move to safe position if possible
            try:
                self.send_and_run_gcode(
                    commands=["G28 Z  ; Home Z axis to safe position"],
                    job_name="safe_position",
                    wait_for_completion=False,
                )
                print("   ✓ Moving to safe Z position")
            except Exception:
                print("   ⚠️  Could not move to safe position")

            print("   🛑 Print operations halted - check printer before resuming")
            return True

        except Exception as e:
            print(f"   ❌ Error during halt procedure: {e}")
            return False

    def set_nozzle_temperature(
        self, temperature: float, wait: bool = False, **kwargs
    ) -> bool:
        """Set nozzle temperature.

        Args:
            temperature: Target temperature in Celsius
            wait: Whether to wait for temperature to be reached
            **kwargs: Additional options for send_and_run_gcode

        Returns:
            True if command successful

        Raises:
            PrusaLinkValidationError: If temperature is out of safe range
        """
        # Validate temperature range
        if temperature < 0:
            raise PrusaLinkValidationError(
                f"Nozzle temperature cannot be negative: {temperature}°C"
            )
        elif temperature > 300:  # Typical max for hotends
            raise PrusaLinkValidationError(
                f"Nozzle temperature {temperature}°C exceeds safe maximum (300°C). "
                "Use --force flag if you really need this temperature."
            )

        commands = []
        if wait:
            commands.append(f"M109 S{temperature}  ; Set nozzle temp and wait")
        else:
            commands.append(f"M104 S{temperature}  ; Set nozzle temp")
        commands.append(f"M117 Nozzle temp set to {temperature}C")

        try:
            result = self.send_and_run_gcode(
                commands=commands, job_name="set_nozzle_temp", **kwargs
            )

            # Always verify the temperature was actually set by checking printer status
            if result:
                self._verify_temperature_set(temperature, "nozzle")

            return result

        except Exception as e:
            if isinstance(e, (PrusaLinkValidationError, PrusaLinkOperationError)):
                raise
            raise PrusaLinkOperationError(f"Failed to set nozzle temperature: {e}")

    def turn_off_heaters(self, **kwargs) -> bool:
        """Turn off all heaters.

        Args:
            **kwargs: Additional options for send_and_run_gcode

        Returns:
            True if command successful
        """
        commands = [
            "M104 S0  ; Turn off nozzle heater",
            "M140 S0  ; Turn off bed heater",
            "M117 All heaters off",
        ]

        return self.send_and_run_gcode(
            commands=commands, job_name="turn_off_heaters", **kwargs
        )

    def move_to_position(
        self,
        x: float = None,
        y: float = None,
        z: float = None,
        feedrate: float = 3000,
        verify_movement: bool = True,
        **kwargs,
    ) -> bool:
        """Move to specified position.

        Args:
            x: X coordinate (None to keep current)
            y: Y coordinate (None to keep current)
            z: Z coordinate (None to keep current)
            feedrate: Movement speed in mm/min
            verify_movement: Whether to verify the movement actually occurred
            **kwargs: Additional options for send_and_run_gcode

        Returns:
            True if movement successful

        Raises:
            PrusaLinkValidationError: If coordinates are out of safe range
            PrusaLinkOperationError: If movement was blocked or clamped
        """
        # Validate coordinates against typical printer limits
        if x is not None and (x < -10 or x > 260):  # Typical Prusa bed size + margin
            raise PrusaLinkValidationError(
                f"X coordinate {x}mm is outside safe range (-10 to 260mm)"
            )
        if y is not None and (y < -10 or y > 220):  # Typical Prusa bed size + margin
            raise PrusaLinkValidationError(
                f"Y coordinate {y}mm is outside safe range (-10 to 220mm)"
            )
        if z is not None and (z < 0 or z > 300):  # Typical Z height limit
            raise PrusaLinkValidationError(
                f"Z coordinate {z}mm is outside safe range (0 to 300mm)"
            )

        coords = []
        if x is not None:
            coords.append(f"X{x}")
        if y is not None:
            coords.append(f"Y{y}")
        if z is not None:
            coords.append(f"Z{z}")

        if not coords:
            raise ValueError("At least one coordinate must be specified")

        # Get initial position for verification
        initial_pos = None
        if verify_movement:
            try:
                status = self.get_printer_status()
                printer_info = status.get("printer", {})
                initial_pos = {
                    "x": printer_info.get("axis_x", 0),
                    "y": printer_info.get("axis_y", 0),
                    "z": printer_info.get("axis_z", 0),
                }
            except Exception:
                verify_movement = (
                    False  # Skip verification if we can't get initial position
                )

        coord_str = " ".join(coords)
        commands = [
            "G90  ; Absolute positioning",
            f"G1 {coord_str} F{feedrate}  ; Move to position",
        ]

        try:
            result = self.send_and_run_gcode(
                commands=commands, job_name="move_to_position", **kwargs
            )

            # Verify movement if requested
            if result and verify_movement and initial_pos:
                self._verify_movement(x, y, z, initial_pos)

            return result

        except Exception as e:
            if isinstance(e, (PrusaLinkValidationError, PrusaLinkOperationError)):
                raise
            raise PrusaLinkOperationError(f"Failed to move to position: {e}")

    def _verify_movement(
        self, target_x: float, target_y: float, target_z: float, initial_pos: dict
    ) -> None:
        """Verify that movement actually occurred as expected.

        Args:
            target_x: Target X coordinate (None if not moved)
            target_y: Target Y coordinate (None if not moved)
            target_z: Target Z coordinate (None if not moved)
            initial_pos: Initial position before movement

        Raises:
            PrusaLinkOperationError: If movement was blocked or clamped
        """
        try:
            import time

            time.sleep(1)  # Give printer time to move

            status = self.get_printer_status()
            printer_info = status.get("printer", {})
            final_pos = {
                "x": printer_info.get("axis_x", 0),
                "y": printer_info.get("axis_y", 0),
                "z": printer_info.get("axis_z", 0),
            }

            tolerance = 2.0  # Allow 2mm tolerance for movement verification

            # Check each axis that was supposed to move
            if target_x is not None:
                if abs(final_pos["x"] - target_x) > tolerance:
                    raise PrusaLinkOperationError(
                        f"X movement blocked: requested {target_x}mm, "
                        f"actual {final_pos['x']:.1f}mm (difference: {abs(final_pos['x'] - target_x):.1f}mm)"
                    )

            if target_y is not None:
                if abs(final_pos["y"] - target_y) > tolerance:
                    raise PrusaLinkOperationError(
                        f"Y movement blocked: requested {target_y}mm, "
                        f"actual {final_pos['y']:.1f}mm (difference: {abs(final_pos['y'] - target_y):.1f}mm)"
                    )

            if target_z is not None:
                if abs(final_pos["z"] - target_z) > tolerance:
                    raise PrusaLinkOperationError(
                        f"Z movement blocked: requested {target_z}mm, "
                        f"actual {final_pos['z']:.1f}mm (difference: {abs(final_pos['z'] - target_z):.1f}mm)"
                    )

        except Exception as e:
            if isinstance(e, PrusaLinkOperationError):
                raise
            # Don't fail the whole operation if we can't verify
            pass

    def test_invalid_operations(self) -> dict:
        """Test various invalid operations to trigger different printer exceptions.

        Returns:
            Dictionary of test results and exceptions caught
        """
        results = {}

        print("🧪 Testing Invalid Operations for Exception Handling:")
        print("=" * 55)

        # Test 1: Extreme temperature (should be clamped)
        print("1. Testing extreme bed temperature (500°C)...")
        try:
            self.set_bed_temperature(500)
            results["extreme_temp"] = "Unexpected success"
        except Exception as e:
            results["extreme_temp"] = f"{type(e).__name__}: {e}"
            print(f"   ✅ Caught: {results['extreme_temp']}")

        # Test 2: Movement beyond limits
        print("2. Testing movement beyond printer limits...")
        try:
            self.move_to_position(x=500, y=500, z=500)
            results["extreme_movement"] = "Unexpected success"
        except Exception as e:
            results["extreme_movement"] = f"{type(e).__name__}: {e}"
            print(f"   ✅ Caught: {results['extreme_movement']}")

        # Test 3: Negative Z movement (dangerous)
        print("3. Testing dangerous negative Z movement...")
        try:
            self.move_to_position(z=-50)
            results["negative_z"] = "Unexpected success"
        except Exception as e:
            results["negative_z"] = f"{type(e).__name__}: {e}"
            print(f"   ✅ Caught: {results['negative_z']}")

        # Test 4: Invalid G-code syntax
        print("4. Testing malformed G-code command...")
        try:
            self.send_and_run_gcode(
                commands=["G1 XINVALID YNOTANUMBER"], job_name="test_malformed"
            )
            results["malformed_gcode"] = "Command ignored by printer"
        except Exception as e:
            results["malformed_gcode"] = f"{type(e).__name__}: {e}"
            print(f"   ✅ Caught: {results['malformed_gcode']}")

        return results
