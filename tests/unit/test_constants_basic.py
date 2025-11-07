"""Basic tests for constants module."""

from microweldr.core.constants import (
    ErrorMessages,
    WeldType,
    get_valid_weld_types,
    get_weld_type_enum,
)


class TestConstantsBasics:
    """Basic constants tests."""

    def test_weld_types_exist(self):
        """Test that weld types are defined."""
        valid_types = get_valid_weld_types()
        assert len(valid_types) > 0
        assert "normal" in valid_types

    def test_get_weld_type_enum(self):
        """Test weld type enum conversion."""
        normal_enum = get_weld_type_enum("normal")
        assert normal_enum == WeldType.NORMAL

    def test_error_messages_exist(self):
        """Test that error messages are defined."""
        assert hasattr(ErrorMessages, "INVALID_WELD_TYPE")
        assert isinstance(ErrorMessages.INVALID_WELD_TYPE, str)
