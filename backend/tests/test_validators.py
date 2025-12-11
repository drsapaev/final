"""
Tests for validation utilities.

Run: pytest tests/test_validators.py -v
"""

import pytest
from datetime import date, time
from decimal import Decimal

from app.utils.validators import (
    validate_phone_uz,
    normalize_phone_uz,
    format_phone_display,
    validate_email,
    normalize_email,
    validate_date_range,
    validate_future_date,
    validate_time_range,
    validate_amount,
    format_currency_uzs,
    validate_length,
    sanitize_string,
    validate_id,
    validate_ids_list,
)


class TestPhoneValidation:
    """Tests for phone number validation and formatting."""
    
    def test_validate_phone_uz_international_format(self):
        """Valid international format +998XXXXXXXXX"""
        assert validate_phone_uz("+998901234567") is True
        assert validate_phone_uz("+998991234567") is True
    
    def test_validate_phone_uz_without_plus(self):
        """Valid format without plus 998XXXXXXXXX"""
        assert validate_phone_uz("998901234567") is True
    
    def test_validate_phone_uz_local_format(self):
        """Valid local format XXXXXXXXX"""
        assert validate_phone_uz("901234567") is True
    
    def test_validate_phone_uz_invalid(self):
        """Invalid phone numbers"""
        assert validate_phone_uz("") is False
        assert validate_phone_uz("invalid") is False
        assert validate_phone_uz("12345") is False
        assert validate_phone_uz("+1234567890") is False  # Not UZ
        assert validate_phone_uz(None) is False
    
    def test_normalize_phone_uz_local_to_international(self):
        """Normalize local to international format"""
        assert normalize_phone_uz("901234567") == "+998901234567"
    
    def test_normalize_phone_uz_without_plus(self):
        """Normalize 998... to +998..."""
        assert normalize_phone_uz("998901234567") == "+998901234567"
    
    def test_normalize_phone_uz_already_normalized(self):
        """Already normalized stays the same"""
        assert normalize_phone_uz("+998901234567") == "+998901234567"
    
    def test_format_phone_display(self):
        """Format phone for display"""
        result = format_phone_display("+998901234567")
        assert result == "+998 (90) 123-45-67"


class TestEmailValidation:
    """Tests for email validation."""
    
    def test_validate_email_valid(self):
        """Valid email addresses"""
        assert validate_email("user@example.com") is True
        assert validate_email("user.name@example.co.uk") is True
        assert validate_email("user+tag@example.org") is True
    
    def test_validate_email_invalid(self):
        """Invalid email addresses"""
        assert validate_email("") is False
        assert validate_email("invalid") is False
        assert validate_email("@example.com") is False
        assert validate_email("user@") is False
        assert validate_email(None) is False
    
    def test_normalize_email(self):
        """Normalize email to lowercase"""
        assert normalize_email("User@Example.COM") == "user@example.com"
        assert normalize_email("  user@example.com  ") == "user@example.com"


class TestDateValidation:
    """Tests for date validation."""
    
    def test_validate_date_range_valid(self):
        """Valid date ranges"""
        is_valid, error = validate_date_range(
            date(2024, 1, 1),
            date(2024, 12, 31)
        )
        assert is_valid is True
        assert error is None
    
    def test_validate_date_range_same_day_allowed(self):
        """Same day allowed by default"""
        is_valid, error = validate_date_range(
            date(2024, 1, 1),
            date(2024, 1, 1),
            allow_same_day=True
        )
        assert is_valid is True
    
    def test_validate_date_range_same_day_not_allowed(self):
        """Same day not allowed when disabled"""
        is_valid, error = validate_date_range(
            date(2024, 1, 1),
            date(2024, 1, 1),
            allow_same_day=False
        )
        assert is_valid is False
        assert error is not None
    
    def test_validate_date_range_invalid(self):
        """Invalid date range (start after end)"""
        is_valid, error = validate_date_range(
            date(2024, 12, 31),
            date(2024, 1, 1)
        )
        assert is_valid is False
        assert error is not None


class TestTimeValidation:
    """Tests for time validation."""
    
    def test_validate_time_range_valid(self):
        """Valid time range"""
        is_valid, error = validate_time_range(
            time(9, 0),
            time(18, 0)
        )
        assert is_valid is True
        assert error is None
    
    def test_validate_time_range_invalid(self):
        """Invalid time range"""
        is_valid, error = validate_time_range(
            time(18, 0),
            time(9, 0)
        )
        assert is_valid is False


class TestAmountValidation:
    """Tests for amount validation."""
    
    def test_validate_amount_valid(self):
        """Valid amounts"""
        is_valid, error = validate_amount(100)
        assert is_valid is True
        
        is_valid, error = validate_amount(0, min_amount=0)
        assert is_valid is True
    
    def test_validate_amount_below_min(self):
        """Amount below minimum"""
        is_valid, error = validate_amount(-1)
        assert is_valid is False
        
        is_valid, error = validate_amount(50, min_amount=100)
        assert is_valid is False
    
    def test_validate_amount_above_max(self):
        """Amount above maximum"""
        is_valid, error = validate_amount(1000, max_amount=500)
        assert is_valid is False
    
    def test_format_currency_uzs(self):
        """Format UZS currency"""
        assert format_currency_uzs(1500000) == "1 500 000 сум"
        assert format_currency_uzs(100) == "100 сум"
        assert format_currency_uzs(0) == "0 сум"


class TestStringValidation:
    """Tests for string validation."""
    
    def test_validate_length_valid(self):
        """Valid string length"""
        is_valid, error = validate_length("hello", min_length=1, max_length=10)
        assert is_valid is True
    
    def test_validate_length_too_short(self):
        """String too short"""
        is_valid, error = validate_length("hi", min_length=5)
        assert is_valid is False
    
    def test_validate_length_too_long(self):
        """String too long"""
        is_valid, error = validate_length("hello world", max_length=5)
        assert is_valid is False
    
    def test_validate_length_empty_required(self):
        """Empty when required"""
        is_valid, error = validate_length("", min_length=1)
        assert is_valid is False
    
    def test_sanitize_string(self):
        """Sanitize string"""
        assert sanitize_string("  hello  ") == "hello"
        assert sanitize_string("hello world", max_length=5) == "hello"


class TestIdValidation:
    """Tests for ID validation."""
    
    def test_validate_id_valid(self):
        """Valid IDs"""
        is_valid, error = validate_id(1)
        assert is_valid is True
        
        is_valid, error = validate_id(100)
        assert is_valid is True
        
        is_valid, error = validate_id("42")  # String that can be converted
        assert is_valid is True
    
    def test_validate_id_invalid(self):
        """Invalid IDs"""
        is_valid, error = validate_id(0)
        assert is_valid is False
        
        is_valid, error = validate_id(-1)
        assert is_valid is False
        
        is_valid, error = validate_id(None)
        assert is_valid is False
        
        is_valid, error = validate_id("invalid")
        assert is_valid is False
    
    def test_validate_ids_list_valid(self):
        """Valid list of IDs"""
        is_valid, error = validate_ids_list([1, 2, 3])
        assert is_valid is True
    
    def test_validate_ids_list_empty_not_allowed(self):
        """Empty list not allowed by default"""
        is_valid, error = validate_ids_list([])
        assert is_valid is False
    
    def test_validate_ids_list_empty_allowed(self):
        """Empty list allowed when enabled"""
        is_valid, error = validate_ids_list([], allow_empty=True)
        assert is_valid is True
    
    def test_validate_ids_list_invalid_item(self):
        """List with invalid item"""
        is_valid, error = validate_ids_list([1, -1, 3])
        assert is_valid is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
