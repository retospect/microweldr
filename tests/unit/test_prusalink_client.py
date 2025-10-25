"""Tests for PrusaLink client functionality."""

import tempfile
from pathlib import Path

import pytest

from microweldr.prusalink.client import PrusaLinkClient
from microweldr.prusalink.exceptions import PrusaLinkConfigError, PrusaLinkError


class TestPrusaLinkClient:
    """Test PrusaLink client functionality."""

    @pytest.fixture
    def secrets_file(self):
        """Create a temporary secrets file."""
        secrets_content = """[prusalink]
host = "192.168.1.100"
username = "maker"
password = "test123"
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(secrets_content)
            f.flush()
            yield f.name
        Path(f.name).unlink()

    @pytest.fixture
    def client(self, secrets_file):
        """Create a PrusaLink client."""
        return PrusaLinkClient(secrets_file)

    def test_client_initialization(self, client):
        """Test client initialization."""
        assert client.base_url == "http://192.168.1.100"
        assert client.config["username"] == "maker"
        assert client.config["password"] == "test123"
        assert client.timeout == 30

    def test_client_initialization_missing_file(self):
        """Test client initialization with missing secrets file."""
        with pytest.raises(PrusaLinkConfigError):
            PrusaLinkClient("nonexistent.toml")

    def test_client_initialization_invalid_toml(self):
        """Test client initialization with invalid TOML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("invalid toml content [")
            f.flush()

            with pytest.raises(PrusaLinkConfigError):
                PrusaLinkClient(f.name)

            Path(f.name).unlink()

    def test_get_printer_status_success(self, requests_mock, client):
        """Test successful printer status retrieval."""
        mock_response = {
            "printer": {
                "state": "Operational",
                "temp_bed": {"actual": 25.0, "target": 0.0},
                "temp_nozzle": {"actual": 23.0, "target": 0.0},
            }
        }

        requests_mock.get("http://192.168.1.100/api/v1/status", json=mock_response)

        status = client.get_printer_status()
        assert status == mock_response
        assert status["printer"]["state"] == "Operational"

    def test_get_printer_status_error(self, requests_mock, client):
        """Test printer status retrieval with error."""
        requests_mock.get("http://192.168.1.100/api/v1/status", status_code=401)

        with pytest.raises(PrusaLinkError):
            client.get_printer_status()

    def test_upload_gcode_missing_file(self, client):
        """Test upload_gcode with missing file."""
        with pytest.raises(Exception):
            client.upload_gcode("nonexistent.gcode")

    def test_get_job_status_success(self, requests_mock, client):
        """Test successful job status retrieval."""
        mock_response = {
            "file": {"name": "test.gcode"},
            "estimatedPrintTime": 1800,
            "progress": {"completion": 45.5},
        }

        requests_mock.get("http://192.168.1.100/api/v1/job", json=mock_response)

        job_info = client.get_job_status()
        assert job_info == mock_response

    def test_get_job_status_error(self, requests_mock, client):
        """Test job status retrieval with error."""
        requests_mock.get("http://192.168.1.100/api/v1/job", status_code=500)

        with pytest.raises(PrusaLinkError):
            client.get_job_status()

    def test_test_connection_success(self, requests_mock, client):
        """Test successful connection test."""
        requests_mock.get("http://192.168.1.100/api/version", status_code=200)

        result = client.test_connection()
        assert result is True

    def test_test_connection_failure(self, requests_mock, client):
        """Test failed connection test."""
        requests_mock.get("http://192.168.1.100/api/version", status_code=500)

        result = client.test_connection()
        assert result is False

    def test_is_printer_ready(self, requests_mock, client):
        """Test printer ready check."""
        mock_response = {"printer": {"state": "Operational"}}
        requests_mock.get("http://192.168.1.100/api/v1/status", json=mock_response)

        result = client.is_printer_ready()
        assert result is True
