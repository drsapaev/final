"""
Utility modules for the Clinic Management System.

Provides common helpers for:
- Validation (phone, email, dates, amounts)
- Formatting (currency, phone display)
- Sanitization
"""

from app.utils.validators import (
    # Phone
    validate_phone_uz,
    normalize_phone_uz,
    format_phone_display,
    # Email
    validate_email,
    normalize_email,
    # Date/Time
    validate_date_range,
    validate_future_date,
    validate_time_range,
    # Amount
    validate_amount,
    format_currency_uzs,
    # String
    validate_length,
    sanitize_string,
    # ID
    validate_id,
    validate_ids_list,
)

__all__ = [
    # Phone
    "validate_phone_uz",
    "normalize_phone_uz",
    "format_phone_display",
    # Email
    "validate_email",
    "normalize_email",
    # Date/Time
    "validate_date_range",
    "validate_future_date",
    "validate_time_range",
    # Amount
    "validate_amount",
    "format_currency_uzs",
    # String
    "validate_length",
    "sanitize_string",
    # ID
    "validate_id",
    "validate_ids_list",
]
