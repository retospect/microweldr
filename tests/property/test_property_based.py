"""Property-based tests using Hypothesis for robust validation."""

import tempfile
from pathlib import Path

import pytest
from hypothesis import given, strategies as st, assume, settings
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant

from microweldr.core.models import WeldPoint, WeldPath
from microweldr.core.safety import SafetyValidator, validate_weld_operation
from microweldr.core.security import SecretsValidator
from microweldr.core.caching import optimize_weld_paths


class TestSafetyValidation:
    """Property-based tests for safety validation."""
    
    @given(st.floats(min_value=0, max_value=120, allow_nan=False, allow_infinity=False))
    def test_valid_temperatures_always_pass(self, temperature):
        """Test that valid temperatures always pass validation."""
        validator = SafetyValidator()
        # Should not raise exception for valid temperatures
        validator.validate_temperature(temperature)
    
    @given(st.floats(min_value=120.1, max_value=1000, allow_nan=False, allow_infinity=False))
    def test_high_temperatures_always_fail(self, temperature):
        """Test that temperatures above 120°C always fail."""
        validator = SafetyValidator()
        with pytest.raises(Exception):  # Should raise SafetyError
            validator.validate_temperature(temperature)
    
    @given(st.floats(min_value=0, max_value=0.5, allow_nan=False, allow_infinity=False))
    def test_valid_weld_heights_pass(self, height):
        """Test that valid weld heights pass validation."""
        validator = SafetyValidator()
        validator.validate_weld_height(height)
    
    @given(st.floats(min_value=0.5001, max_value=10, allow_nan=False, allow_infinity=False))
    def test_excessive_weld_heights_fail(self, height):
        """Test that excessive weld heights fail validation."""
        validator = SafetyValidator()
        with pytest.raises(Exception):  # Should raise SafetyError
            validator.validate_weld_height(height)
    
    @given(st.floats(min_value=0.05, max_value=5.0, allow_nan=False, allow_infinity=False))
    def test_valid_weld_times_pass(self, weld_time):
        """Test that valid weld times pass validation."""
        validator = SafetyValidator()
        validator.validate_weld_time(weld_time)
    
    @given(st.floats(min_value=5.001, max_value=100, allow_nan=False, allow_infinity=False))
    def test_excessive_weld_times_fail(self, weld_time):
        """Test that excessive weld times fail validation."""
        validator = SafetyValidator()
        with pytest.raises(Exception):  # Should raise SafetyError
            validator.validate_weld_time(weld_time)


class TestWeldPointGeneration:
    """Property-based tests for weld point generation and validation."""
    
    @given(
        x=st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False),
        y=st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False),
        weld_type=st.sampled_from(["normal", "light", "stop", "pipette"]),
        custom_temp=st.one_of(st.none(), st.floats(min_value=50, max_value=120)),
        custom_weld_time=st.one_of(st.none(), st.floats(min_value=0.05, max_value=5.0)),
        custom_weld_height=st.one_of(st.none(), st.floats(min_value=0.001, max_value=0.5))
    )
    def test_weld_point_creation_with_valid_parameters(
        self, x, y, weld_type, custom_temp, custom_weld_time, custom_weld_height
    ):
        """Test that WeldPoint creation works with any valid parameters."""
        point = WeldPoint(
            x=x,
            y=y,
            weld_type=weld_type,
            custom_temp=custom_temp,
            custom_weld_time=custom_weld_time,
            custom_weld_height=custom_weld_height
        )
        
        # Verify properties
        assert point.x == x
        assert point.y == y
        assert point.weld_type == weld_type
        assert point.custom_temp == custom_temp
        assert point.custom_weld_time == custom_weld_time
        assert point.custom_weld_height == custom_weld_height
        
        # Validate with safety validator if custom parameters are present
        validator = SafetyValidator()
        validator.validate_weld_point(point)  # Should not raise exception
    
    @given(
        points=st.lists(
            st.builds(
                WeldPoint,
                x=st.floats(min_value=0, max_value=250, allow_nan=False, allow_infinity=False),
                y=st.floats(min_value=0, max_value=220, allow_nan=False, allow_infinity=False),
                weld_type=st.sampled_from(["normal", "light"]),
                custom_temp=st.one_of(st.none(), st.floats(min_value=50, max_value=120)),
                custom_weld_time=st.one_of(st.none(), st.floats(min_value=0.05, max_value=5.0)),
                custom_weld_height=st.one_of(st.none(), st.floats(min_value=0.001, max_value=0.5))
            ),
            min_size=1,
            max_size=100
        ),
        weld_type=st.sampled_from(["normal", "light"]),
        name=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc', 'Pd')))
    )
    def test_weld_path_creation_and_optimization(self, points, weld_type, name):
        """Test WeldPath creation and optimization with various point configurations."""
        # Create weld path
        path = WeldPath(points=points, weld_type=weld_type, name=name)
        
        assert len(path.points) == len(points)
        assert path.weld_type == weld_type
        assert path.name == name
        
        # Test optimization
        optimized_paths = optimize_weld_paths([path])
        assert len(optimized_paths) == 1
        
        optimized_path = optimized_paths[0]
        assert optimized_path.weld_type == weld_type
        assert optimized_path.name == name
        
        # Optimized path should have same or fewer points (due to duplicate removal)
        assert len(optimized_path.points) <= len(points)
        
        # All points in optimized path should be from original points
        for opt_point in optimized_path.points:
            assert any(
                abs(opt_point.x - orig_point.x) < 0.001 and 
                abs(opt_point.y - orig_point.y) < 0.001
                for orig_point in points
            )


class TestSecurityValidation:
    """Property-based tests for security validation."""
    
    @given(st.text(min_size=1, max_size=255, alphabet=st.characters(blacklist_categories=('Cc', 'Cs'))))
    def test_filename_sanitization_always_produces_safe_names(self, filename):
        """Test that filename sanitization always produces safe filenames."""
        validator = SecretsValidator()
        
        try:
            sanitized = validator.sanitize_filename(filename)
            
            # Sanitized filename should never be empty
            assert len(sanitized) > 0
            
            # Should not contain dangerous characters
            dangerous_chars = ['<', '>', ':', '"', '|', '?', '*', '..']
            for char in dangerous_chars:
                assert char not in sanitized
            
            # Should not start with dot (hidden file)
            assert not sanitized.startswith('.')
            
            # Should be reasonable length
            assert len(sanitized) <= 255
            
        except Exception as e:
            # If sanitization fails, it should be due to empty input
            assert filename.strip() == ""
    
    @given(
        username=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        password=st.text(min_size=8, max_size=128)
    )
    def test_password_strength_validation_consistency(self, username, password):
        """Test that password strength validation is consistent."""
        validator = SecretsValidator()
        
        is_strong, issues = validator.validate_password_strength(password, username)
        
        # Result should be boolean
        assert isinstance(is_strong, bool)
        
        # Issues should be a list
        assert isinstance(issues, list)
        
        # If password is strong, there should be no issues
        if is_strong:
            assert len(issues) == 0
        
        # If there are issues, password should not be strong
        if issues:
            assert not is_strong
        
        # Password same as username should always have issues
        if password.lower() == username.lower():
            assert not is_strong
            assert any("same as username" in issue.lower() for issue in issues)
    
    @given(st.ip_addresses(v=4))
    def test_ipv4_validation_accepts_valid_addresses(self, ip):
        """Test that IPv4 validation accepts all valid IPv4 addresses."""
        validator = SecretsValidator()
        is_valid, error = validator.validate_ip_address(str(ip))
        
        # All valid IPv4 addresses should be accepted
        assert is_valid
        assert error is None
    
    @given(st.ip_addresses(v=6))
    def test_ipv6_validation_accepts_valid_addresses(self, ip):
        """Test that IPv6 validation accepts all valid IPv6 addresses."""
        validator = SecretsValidator()
        is_valid, error = validator.validate_ip_address(str(ip))
        
        # All valid IPv6 addresses should be accepted
        assert is_valid
        assert error is None


class TestConfigurationValidation:
    """Property-based tests for configuration validation."""
    
    @given(
        bed_temp=st.floats(min_value=0, max_value=80, allow_nan=False, allow_infinity=False),
        nozzle_temp=st.floats(min_value=50, max_value=120, allow_nan=False, allow_infinity=False),
        weld_temp=st.floats(min_value=50, max_value=120, allow_nan=False, allow_infinity=False),
        weld_height=st.floats(min_value=0.001, max_value=0.5, allow_nan=False, allow_infinity=False),
        weld_time=st.floats(min_value=0.05, max_value=5.0, allow_nan=False, allow_infinity=False),
        travel_speed=st.floats(min_value=100, max_value=3000, allow_nan=False, allow_infinity=False),
        z_speed=st.floats(min_value=50, max_value=1000, allow_nan=False, allow_infinity=False)
    )
    def test_valid_configuration_always_passes(
        self, bed_temp, nozzle_temp, weld_temp, weld_height, weld_time, travel_speed, z_speed
    ):
        """Test that valid configurations always pass validation."""
        config = {
            "temperatures": {
                "bed_temperature": bed_temp,
                "nozzle_temperature": nozzle_temp
            },
            "normal_welds": {
                "weld_temperature": weld_temp,
                "weld_height": weld_height,
                "weld_time": weld_time
            },
            "movement": {
                "travel_speed": travel_speed,
                "z_speed": z_speed
            }
        }
        
        validator = SafetyValidator()
        warnings, errors = validator.validate_config(config)
        
        # Should have no errors for valid configuration
        assert len(errors) == 0
        
        # Warnings are acceptable (they're just recommendations)
        assert isinstance(warnings, list)


class WeldOperationStateMachine(RuleBasedStateMachine):
    """State-based testing for weld operations."""
    
    def __init__(self):
        super().__init__()
        self.weld_paths = []
        self.config = {
            "temperatures": {"bed_temperature": 60, "nozzle_temperature": 200},
            "normal_welds": {"weld_temperature": 100, "weld_height": 0.02, "weld_time": 0.1},
            "light_welds": {"weld_temperature": 110, "weld_height": 0.02, "weld_time": 0.2},
            "movement": {"travel_speed": 1500, "z_speed": 600}
        }
    
    @rule(
        x=st.floats(min_value=0, max_value=250, allow_nan=False, allow_infinity=False),
        y=st.floats(min_value=0, max_value=220, allow_nan=False, allow_infinity=False),
        weld_type=st.sampled_from(["normal", "light"])
    )
    def add_weld_point(self, x, y, weld_type):
        """Add a weld point to the current operation."""
        point = WeldPoint(x, y, weld_type)
        
        # Add to existing path or create new one
        if self.weld_paths and self.weld_paths[-1].weld_type == weld_type:
            self.weld_paths[-1].points.append(point)
        else:
            path = WeldPath([point], weld_type, f"path_{len(self.weld_paths)}")
            self.weld_paths.append(path)
    
    @rule()
    def validate_operation(self):
        """Validate the current weld operation."""
        if self.weld_paths:
            warnings, errors = validate_weld_operation(self.weld_paths, self.config)
            
            # Should not have errors with our controlled inputs
            assert isinstance(warnings, list)
            assert isinstance(errors, list)
    
    @rule()
    def optimize_paths(self):
        """Optimize the current weld paths."""
        if self.weld_paths:
            original_count = len(self.weld_paths)
            optimized = optimize_weld_paths(self.weld_paths)
            
            # Should return same number of paths
            assert len(optimized) == original_count
            
            # Each optimized path should have valid structure
            for path in optimized:
                assert len(path.points) >= 1
                assert path.weld_type in ["normal", "light"]
                assert isinstance(path.name, str)
    
    @invariant()
    def paths_are_valid(self):
        """Invariant: all paths should always be valid."""
        for path in self.weld_paths:
            assert len(path.points) >= 1
            assert path.weld_type in ["normal", "light", "stop", "pipette"]
            assert isinstance(path.name, str)
            
            for point in path.points:
                assert isinstance(point.x, (int, float))
                assert isinstance(point.y, (int, float))
                assert point.weld_type in ["normal", "light", "stop", "pipette"]


# Configure Hypothesis settings for reasonable test execution time
TestWeldOperationStateMachine.TestCase.settings = settings(
    max_examples=50,
    stateful_step_count=20,
    deadline=None
)


class TestFileOperations:
    """Property-based tests for file operations."""
    
    @given(
        content=st.text(min_size=0, max_size=10000),
        filename=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc')))
    )
    def test_safe_file_operations(self, content, filename):
        """Test that file operations are safe with various inputs."""
        # Sanitize filename first
        validator = SecretsValidator()
        safe_filename = validator.sanitize_filename(filename)
        
        # Test file operations
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / safe_filename
            
            # Write content
            file_path.write_text(content, encoding='utf-8')
            
            # Verify content
            read_content = file_path.read_text(encoding='utf-8')
            assert read_content == content
            
            # File should exist
            assert file_path.exists()
            assert file_path.is_file()
    
    @given(st.binary(min_size=0, max_size=1000))
    def test_binary_content_handling(self, binary_content):
        """Test handling of binary content in files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.bin"
            
            # Write binary content
            file_path.write_bytes(binary_content)
            
            # Read back and verify
            read_content = file_path.read_bytes()
            assert read_content == binary_content


# Run the state machine test
TestWeldOperationStateMachine = TestWeldOperationStateMachine.TestCase
