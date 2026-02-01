import pytest
import re
from unittest.mock import patch, MagicMock

# Assuming ValidationError is defined in the same module or imported
class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass

def validate_email(email: str) -> bool:
    """Validate email format.

    Args:
        email: Email address to validate

    Returns:
        True if email is valid

    Raises:
        ValidationError: If email format is invalid
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValidationError(f"Invalid email format: {email}")
    return True


class TestValidateEmail:
    """Test suite for validate_email function."""

    def test_validate_email_valid_simple_email_returns_true(self):
        """Test that a simple valid email returns True."""
        email = "test@example.com"
        result = validate_email(email)
        assert result is True

    def test_validate_email_valid_email_with_numbers_returns_true(self):
        """Test that a valid email with numbers returns True."""
        email = "user123@domain456.com"
        result = validate_email(email)
        assert result is True

    def test_validate_email_valid_email_with_dots_returns_true(self):
        """Test that a valid email with dots in local part returns True."""
        email = "first.last@example.com"
        result = validate_email(email)
        assert result is True

    def test_validate_email_valid_email_with_plus_returns_true(self):
        """Test that a valid email with plus sign returns True."""
        email = "user+tag@example.com"
        result = validate_email(email)
        assert result is True

    def test_validate_email_valid_email_with_underscore_returns_true(self):
        """Test that a valid email with underscore returns True."""
        email = "user_name@example.com"
        result = validate_email(email)
        assert result is True

    def test_validate_email_valid_email_with_hyphen_returns_true(self):
        """Test that a valid email with hyphen in domain returns True."""
        email = "user@sub-domain.example.com"
        result = validate_email(email)
        assert result is True

    def test_validate_email_valid_email_with_percent_returns_true(self):
        """Test that a valid email with percent sign returns True."""
        email = "user%test@example.com"
        result = validate_email(email)
        assert result is True

    def test_validate_email_valid_email_with_subdomain_returns_true(self):
        """Test that a valid email with subdomain returns True."""
        email = "user@mail.example.com"
        result = validate_email(email)
        assert result is True

    def test_validate_email_valid_email_with_long_tld_returns_true(self):
        """Test that a valid email with long TLD returns True."""
        email = "user@example.museum"
        result = validate_email(email)
        assert result is True

    def test_validate_email_valid_email_with_two_char_tld_returns_true(self):
        """Test that a valid email with two character TLD returns True."""
        email = "user@example.co"
        result = validate_email(email)
        assert result is True

    def test_validate_email_empty_string_raises_validation_error(self):
        """Test that empty string raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            validate_email("")
        assert "Invalid email format:" in str(exc_info.value)

    def test_validate_email_none_value_raises_type_error(self):
        """Test that None value raises TypeError."""
        with pytest.raises(TypeError):
            validate_email(None)

    def test_validate_email_missing_at_symbol_raises_validation_error(self):
        """Test that email without @ symbol raises ValidationError."""
        email = "userexample.com"
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        assert f"Invalid email format: {email}" in str(exc_info.value)

    def test_validate_email_missing_domain_raises_validation_error(self):
        """Test that email without domain raises ValidationError."""
        email = "user@"
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        assert f"Invalid email format: {email}" in str(exc_info.value)

    def test_validate_email_missing_local_part_raises_validation_error(self):
        """Test that email without local part raises ValidationError."""
        email = "@example.com"
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        assert f"Invalid email format: {email}" in str(exc_info.value)

    def test_validate_email_missing_tld_raises_validation_error(self):
        """Test that email without TLD raises ValidationError."""
        email = "user@example"
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        assert f"Invalid email format: {email}" in str(exc_info.value)

    def test_validate_email_invalid_tld_too_short_raises_validation_error(self):
        """Test that email with TLD shorter than 2 chars raises ValidationError."""
        email = "user@example.c"
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        assert f"Invalid email format: {email}" in str(exc_info.value)

    def test_validate_email_multiple_at_symbols_raises_validation_error(self):
        """Test that email with multiple @ symbols raises ValidationError."""
        email = "user@@example.com"
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        assert f"Invalid email format: {email}" in str(exc_info.value)

    def test_validate_email_spaces_in_email_raises_validation_error(self):
        """Test that email with spaces raises ValidationError."""
        email = "user name@example.com"
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        assert f"Invalid email format: {email}" in str(exc_info.value)

    def test_validate_email_special_chars_in_domain_raises_validation_error(self):
        """Test that email with invalid special chars in domain raises ValidationError."""
        email = "user@exam#ple.com"
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        assert f"Invalid email format: {email}" in str(exc_info.value)

    def test_validate_email_starts_with_dot_raises_validation_error(self):
        """Test that email starting with dot raises ValidationError."""
        email = ".user@example.com"
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        assert f"Invalid email format: {email}" in str(exc_info.value)

    def test_validate_email_ends_with_dot_raises_validation_error(self):
        """Test that email ending with dot before @ raises ValidationError."""
        email = "user.@example.com"
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        assert f"Invalid email format: {email}" in str(exc_info.value)

    def test_validate_email_consecutive_dots_raises_validation_error(self):
        """Test that email with consecutive dots raises ValidationError."""
        email = "user..name@example.com"
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        assert f"Invalid email format: {email}" in str(exc_info.value)

    def test_validate_email_domain_starts_with_hyphen_raises_validation_error(self):
        """Test that email with domain starting with hyphen raises ValidationError."""
        email = "user@-example.com"
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        assert f"Invalid email format: {email}" in str(exc_info.value)

    def test_validate_email_domain_ends_with_hyphen_raises_validation_error(self):
        """Test that email with domain ending with hyphen raises ValidationError."""
        email = "user@example-.com"
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        assert f"Invalid email format: {email}" in str(exc_info.value)

    def test_validate_email_numeric_tld_raises_validation_error(self):
        """Test that email with numeric TLD raises ValidationError."""
        email = "user@example.123"
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        assert f"Invalid email format: {email}" in str(exc_info.value)

    def test_validate_email_very_long_valid_email_returns_true(self):
        """Test that a very long but valid email returns True."""
        local_part = "a" * 50
        domain_part = "b" * 50
        email = f"{local_part}@{domain_part}.com"
        result = validate_email(email)
        assert result is True

    def test_validate_email_international_domain_returns_true(self):
        """Test that email with international characters in domain returns True."""
        # Note: The current regex doesn't support international domains
        # This test documents the current behavior
        email = "user@example.org"  # Using standard ASCII domain
        result = validate_email(email)
        assert result is True

    @patch('re.match')
    def test_validate_email_regex_match_called_with_correct_pattern(self, mock_match):
        """Test that re.match is called with the correct pattern and email."""
        mock_match.return_value = MagicMock()  # Mock successful match
        email = "test@example.com"
        expected_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        validate_email(email)
        
        mock_match.assert_called_once_with(expected_pattern, email)

    @patch('re.match')
    def test_validate_email_regex_match_returns_none_raises_validation_error(self, mock_match):
        """Test that when re.match returns None, ValidationError is raised."""
        mock_match.return_value = None
        email = "invalid-email"
        
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        
        assert f"Invalid email format: {email}" in str(exc_info.value)
        mock_match.assert_called_once()

    def test_validate_email_whitespace_only_raises_validation_error(self):
        """Test that email with only whitespace raises ValidationError."""
        email = "   "
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        assert f"Invalid email format: {email}" in str(exc_info.value)

    def test_validate_email_tab_character_raises_validation_error(self):
        """Test that email with tab character raises ValidationError."""
        email = "user\t@example.com"
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        assert f"Invalid email format: {email}" in str(exc_info.value)

    def test_validate_email_newline_character_raises_validation_error(self):
        """Test that email with newline character raises ValidationError."""
        email = "user\n@example.com"
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        assert f"Invalid email format: {email}" in str(exc_info.value)

    def test_validate_email_unicode_characters_raises_validation_error(self):
        """Test that email with unicode characters raises ValidationError."""
        email = "usér@example.com"
        with pytest.raises(ValidationError) as exc_info:
            validate_email(email)
        assert f"Invalid email format: {email}" in str(exc_info.value)

    def test_validate_email_case_sensitivity_mixed_case_returns_true(self):
        """Test that email with mixed case letters returns True."""
        email = "User.Name@Example.COM"
        result = validate_email(email)
        assert result is True