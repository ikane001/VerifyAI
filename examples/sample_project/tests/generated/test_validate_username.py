import pytest
import re
from unittest.mock import patch
from user_service import validate_username, ValidationError


class TestValidateUsername:
    """Test suite for validate_username function."""

    def test_validate_username_valid_short_username_returns_true(self):
        """Test that a valid 3-character username returns True."""
        result = validate_username("abc")
        assert result is True

    def test_validate_username_valid_medium_username_returns_true(self):
        """Test that a valid medium-length username returns True."""
        result = validate_username("user123")
        assert result is True

    def test_validate_username_valid_long_username_returns_true(self):
        """Test that a valid 50-character username returns True."""
        username = "a" * 50
        result = validate_username(username)
        assert result is True

    def test_validate_username_valid_with_underscores_returns_true(self):
        """Test that a valid username with underscores returns True."""
        result = validate_username("user_name_123")
        assert result is True

    def test_validate_username_valid_with_numbers_returns_true(self):
        """Test that a valid username with numbers returns True."""
        result = validate_username("user123456")
        assert result is True

    def test_validate_username_valid_with_mixed_case_returns_true(self):
        """Test that a valid username with mixed case letters returns True."""
        result = validate_username("UserName123")
        assert result is True

    def test_validate_username_valid_all_uppercase_returns_true(self):
        """Test that a valid all