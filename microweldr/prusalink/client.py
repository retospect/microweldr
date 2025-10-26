"""PrusaLink API client for G-code submission."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import toml
from requests.auth import HTTPDigestAuth

from .exceptions import (
    PrusaLinkAuthError,
    PrusaLinkConfigError,
    PrusaLinkConnectionError,
    PrusaLinkError,
    PrusaLinkUploadError,
)


class PrusaLinkClient:
    """Client for interacting with PrusaLink API."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize PrusaLink client.

        Args:
            config_path: Path to secrets.toml file. If None, looks for secrets.toml in current directory.
        """
        self.config = self._load_config(config_path)
        self.base_url = f"http://{self.config['host']}"

        # Support both API key and LCD password authentication
        password = self.config.get("password") or self.config.get("api_key")
        self.auth = HTTPDigestAuth(self.config["username"], password)
        self.timeout = self.config.get("timeout", 30)

    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load configuration from secrets.toml file."""
        if config_path is None:
            config_path = "secrets.toml"

        if not os.path.exists(config_path):
            raise PrusaLinkConfigError(
                f"Configuration file not found: {config_path}. "
                f"Please create it based on secrets.toml.template"
            )

        try:
            with open(config_path, "r") as f:
                config = toml.load(f)
        except Exception as e:
            raise PrusaLinkConfigError(f"Failed to load configuration: {e}")

        if "prusalink" not in config:
            raise PrusaLinkConfigError("Missing [prusalink] section in configuration")

        prusalink_config = config["prusalink"]

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
            return response.status_code == 200
        except requests.exceptions.RequestException:
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

        try:
            response = requests.put(
                url,
                data=file_content,
                headers=headers,
                auth=self.auth,
                timeout=self.timeout,
            )

            if response.status_code == 401:
                raise PrusaLinkAuthError(
                    "Authentication failed. Check your credentials."
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

    def send_gcode(self, command: str) -> bool:
        """Send a single G-code command to the printer.

        Args:
            command: G-code command to send (e.g., "G28", "M140 S60")

        Returns:
            True if command was sent successfully, False otherwise

        Raises:
            PrusaLinkConnectionError: If connection fails
        """
        try:
            # PrusaLink API endpoint for sending G-code commands
            # Note: This is a simplified implementation - actual PrusaLink API
            # may require different endpoints or formatting
            response = self.session.post(
                f"{self.base_url}/api/printer/command",
                json={"command": command},
                auth=self.auth,
                timeout=self.timeout,
            )

            if response.status_code == 200:
                return True
            else:
                raise PrusaLinkConnectionError(
                    f"G-code command failed: HTTP {response.status_code}"
                )

        except requests.exceptions.RequestException as e:
            raise PrusaLinkConnectionError(f"Failed to send G-code '{command}': {e}")
