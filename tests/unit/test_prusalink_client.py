"""Tests for PrusaLink client functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests_mock

from microweldr.prusalink.client import PrusaLinkClient
from microweldr.prusalink.exceptions import PrusaLinkError, PrusaLinkConfigError


class TestPrusaLinkClient:
    """Test PrusaLink client functionality."""

    @pytest.fixture
    def secrets_file(self):
        """Create a temporary secrets file."""
        secrets_content = """
[prusalink]
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
            
            with pytest.raises(PrusaLinkConfigError):  # TOML parsing error
                PrusaLinkClient(f.name)
            
            Path(f.name).unlink()

    @requests_mock.Mocker()
    def test_get_status_success(self, m, client):
        """Test successful status retrieval."""
        mock_response = {
            "printer": {
                "state": "Operational",
                "temp_bed": {"actual": 25.0, "target": 0.0},
                "temp_nozzle": {"actual": 23.0, "target": 0.0}
            }
        }
        
        m.get("http://192.168.1.100/api/printer", json=mock_response)
        
        status = client.get_status()
        assert status == mock_response
        assert status["printer"]["state"] == "Operational"

    @requests_mock.Mocker()
    def test_get_status_error(self, m, client):
        """Test status retrieval with error."""
        m.get("http://192.168.1.100/api/printer", status_code=401)
        
        with pytest.raises(PrusaLinkError, match="Failed to get printer status"):
            client.get_status()

    @requests_mock.Mocker()
    def test_upload_file_success(self, m, client):
        """Test successful file upload."""
        # Create a temporary G-code file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gcode", delete=False) as f:
            f.write("G28 ; Home all axes\nG1 X10 Y10 Z1 F1000\n")
            gcode_path = f.name

        try:
            mock_response = {
                "filename": "test.gcode",
                "path": "/local/test.gcode",
                "auto_started": True
            }
            
            m.post("http://192.168.1.100/api/files/local", json=mock_response)
            
            result = client.upload_file(gcode_path, "test.gcode", auto_start=True)
            
            assert result == mock_response
            assert result["filename"] == "test.gcode"
            assert result["auto_started"] is True
            
        finally:
            Path(gcode_path).unlink()

    @requests_mock.Mocker()
    def test_upload_file_not_found(self, m, client):
        """Test file upload with missing file."""
        with pytest.raises(FileNotFoundError):
            client.upload_file("nonexistent.gcode", "test.gcode")

    @requests_mock.Mocker()
    def test_upload_file_error(self, m, client):
        """Test file upload with server error."""
        # Create a temporary G-code file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gcode", delete=False) as f:
            f.write("G28\n")
            gcode_path = f.name

        try:
            m.post("http://192.168.1.100/api/files/local", status_code=500)
            
            with pytest.raises(PrusaLinkError, match="Failed to upload file"):
                client.upload_file(gcode_path, "test.gcode")
                
        finally:
            Path(gcode_path).unlink()

    @requests_mock.Mocker()
    def test_start_print_success(self, m, client):
        """Test successful print start."""
        mock_response = {"started": True}
        m.post("http://192.168.1.100/api/job", json=mock_response)
        
        result = client.start_print("test.gcode")
        assert result == mock_response

    @requests_mock.Mocker()
    def test_start_print_error(self, m, client):
        """Test print start with error."""
        m.post("http://192.168.1.100/api/job", status_code=409)
        
        with pytest.raises(PrusaLinkError, match="Failed to start print"):
            client.start_print("test.gcode")

    @requests_mock.Mocker()
    def test_stop_print_success(self, m, client):
        """Test successful print stop."""
        mock_response = {"stopped": True}
        m.delete("http://192.168.1.100/api/job", json=mock_response)
        
        result = client.stop_print()
        assert result == mock_response

    @requests_mock.Mocker()
    def test_stop_print_error(self, m, client):
        """Test print stop with error."""
        m.delete("http://192.168.1.100/api/job", status_code=409)
        
        with pytest.raises(PrusaLinkError, match="Failed to stop print"):
            client.stop_print()

    @requests_mock.Mocker()
    def test_get_job_info_success(self, m, client):
        """Test successful job info retrieval."""
        mock_response = {
            "job": {
                "file": {"name": "test.gcode"},
                "estimatedPrintTime": 1800,
                "progress": {"completion": 45.5}
            }
        }
        
        m.get("http://192.168.1.100/api/job", json=mock_response)
        
        job_info = client.get_job_info()
        assert job_info == mock_response
        assert job_info["job"]["progress"]["completion"] == 45.5

    @requests_mock.Mocker()
    def test_get_job_info_error(self, m, client):
        """Test job info retrieval with error."""
        m.get("http://192.168.1.100/api/job", status_code=500)
        
        with pytest.raises(PrusaLinkError, match="Failed to get job info"):
            client.get_job_info()

    def test_build_url(self, client):
        """Test URL building."""
        assert client._build_url("/api/test") == "http://192.168.1.100/api/test"
        assert client._build_url("api/test") == "http://192.168.1.100/api/test"

    @requests_mock.Mocker()
    def test_request_timeout(self, m, client):
        """Test request timeout handling."""
        m.get("http://192.168.1.100/api/printer", exc=requests_mock.exceptions.ConnectTimeout)
        
        with pytest.raises(PrusaLinkError, match="Request timeout"):
            client.get_status()

    @requests_mock.Mocker()
    def test_connection_error(self, m, client):
        """Test connection error handling."""
        m.get("http://192.168.1.100/api/printer", exc=requests_mock.exceptions.ConnectionError)
        
        with pytest.raises(PrusaLinkError, match="Connection error"):
            client.get_status()

    def test_upload_file_with_storage_usb(self, client):
        """Test file upload to USB storage."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gcode", delete=False) as f:
            f.write("G28\n")
            gcode_path = f.name

        try:
            with requests_mock.Mocker() as m:
                mock_response = {"filename": "test.gcode", "path": "/usb/test.gcode"}
                m.post("http://192.168.1.100/api/files/usb", json=mock_response)
                
                result = client.upload_file(gcode_path, "test.gcode", storage="usb")
                assert result["path"] == "/usb/test.gcode"
                
        finally:
            Path(gcode_path).unlink()

    @requests_mock.Mocker()
    def test_upload_and_start_workflow(self, m, client):
        """Test complete upload and start workflow."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gcode", delete=False) as f:
            f.write("G28 ; Home\nG1 X10 Y10 Z1 F1000\n")
            gcode_path = f.name

        try:
            # Mock upload response
            upload_response = {
                "filename": "workflow_test.gcode",
                "path": "/local/workflow_test.gcode",
                "auto_started": False
            }
            m.post("http://192.168.1.100/api/files/local", json=upload_response)
            
            # Mock start print response
            start_response = {"started": True}
            m.post("http://192.168.1.100/api/job", json=start_response)
            
            # Upload file
            upload_result = client.upload_file(gcode_path, "workflow_test.gcode", auto_start=False)
            assert upload_result["auto_started"] is False
            
            # Start print
            start_result = client.start_print("workflow_test.gcode")
            assert start_result["started"] is True
            
        finally:
            Path(gcode_path).unlink()
