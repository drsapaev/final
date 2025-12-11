"""
Common validation utilities with full type hints.

This module provides reusable validators for:
- Phone numbers (Uzbekistan format)
- Email addresses
- Dates and times
- Currency and amounts
"""

from __future__ import annotations

import re
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, List, Optional, Tuple, Union

# ===================== PHONE VALIDATION =====================

# Uzbekistan phone number patterns
UZBEKISTAN_PHONE_PATTERNS: List[str] = [
    r"^\+998\d{9}$",    # +998XXXXXXXXX (international)
    r"^998\d{9}$",      # 998XXXXXXXXX (without +)
    r"^\d{9}$",         # XXXXXXXXX (local only)
]


def validate_phone_uz(phone: str) -> bool:
    """
    Validate Uzbekistan phone number format.
    
    Args:
        phone: Phone number string to validate
    
    Returns:
        True if valid Uzbekistan phone format, False otherwise
    
    Example:
        >>> validate_phone_uz("+998901234567")
        True
        >>> validate_phone_uz("invalid")
        False
    """
    if not phone or not isinstance(phone, str):
        return False
    
    cleaned = phone.strip()
    return any(re.match(pattern, cleaned) for pattern in UZBEKISTAN_PHONE_PATTERNS)


def normalize_phone_uz(phone: str) -> str:
    """
    Normalize phone number to +998XXXXXXXXX format.
    
    Args:
        phone: Phone number in any valid format
    
    Returns:
        Normalized phone number with +998 prefix
    
    Example:
        >>> normalize_phone_uz("901234567")
        "+998901234567"
        >>> normalize_phone_uz("998901234567")
        "+998901234567"
    """
    if not phone:
        return phone
    
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone.strip())
    
    # Extract digits only
    digits = re.sub(r'\D', '', cleaned)
    
    # Normalize based on length
    if len(digits) == 12 and digits.startswith('998'):
        return f'+{digits}'
    elif len(digits) == 9:
        return f'+998{digits}'
    elif len(digits) == 11 and digits.startswith('8'):
        # Handle old format 8XXXXXXXXXX -> +998XXXXXXXXX
        return f'+998{digits[1:]}'
    
    # Return original if can't normalize
    return phone


def format_phone_display(phone: str) -> str:
    """
    Format phone number for display: +998 (XX) XXX-XX-XX
    
    Args:
        phone: Phone number to format
    
    Returns:
        Formatted phone string for UI display
    """
    normalized = normalize_phone_uz(phone)
    digits = re.sub(r'\D', '', normalized)
    
    if len(digits) == 12:
        return f'+{digits[:3]} ({digits[3:5]}) {digits[5:8]}-{digits[8:10]}-{digits[10:]}'
    
    return phone


# ===================== EMAIL VALIDATION =====================

EMAIL_PATTERN: str = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'


def validate_email(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
    
    Returns:
        True if valid email format, False otherwise
    """
    if not email or not isinstance(email, str):
        return False
    
    return bool(re.match(EMAIL_PATTERN, email.strip().lower()))


def normalize_email(email: str) -> str:
    """
    Normalize email address (lowercase, trimmed).
    
    Args:
        email: Email address to normalize
    
    Returns:
        Normalized email string
    """
    if not email:
        return email
    return email.strip().lower()


# ===================== DATE/TIME VALIDATION =====================

def validate_date_range(
    start_date: date,
    end_date: date,
    allow_same_day: bool = True
) -> Tuple[bool, Optional[str]]:
    """
    Validate that start_date is before or equal to end_date.
    
    Args:
        start_date: Start date
        end_date: End date
        allow_same_day: Whether start and end can be the same day
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if allow_same_day:
        if start_date > end_date:
            return False, "Дата начала должна быть раньше или равна дате окончания"
    else:
        if start_date >= end_date:
            return False, "Дата начала должна быть раньше даты окончания"
    
    return True, None


def validate_future_date(
    target_date: date,
    allow_today: bool = True
) -> Tuple[bool, Optional[str]]:
    """
    Validate that date is in the future.
    
    Args:
        target_date: Date to validate
        allow_today: Whether today is allowed
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    today = date.today()
    
    if allow_today:
        if target_date < today:
            return False, "Дата должна быть сегодня или позже"
    else:
        if target_date <= today:
            return False, "Дата должна быть в будущем"
    
    return True, None


def validate_time_range(
    start_time: time,
    end_time: time
) -> Tuple[bool, Optional[str]]:
    """
    Validate that start_time is before end_time.
    
    Args:
        start_time: Start time
        end_time: End time
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if start_time >= end_time:
        return False, "Время начала должно быть раньше времени окончания"
    
    return True, None


# ===================== AMOUNT VALIDATION =====================

def validate_amount(
    amount: Union[int, float, Decimal],
    min_amount: Union[int, float, Decimal] = 0,
    max_amount: Optional[Union[int, float, Decimal]] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate monetary amount.
    
    Args:
        amount: Amount to validate
        min_amount: Minimum allowed amount (default 0)
        max_amount: Maximum allowed amount (optional)
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if amount < min_amount:
        return False, f"Сумма должна быть не менее {min_amount}"
    
    if max_amount is not None and amount > max_amount:
        return False, f"Сумма должна быть не более {max_amount}"
    
    return True, None


def format_currency_uzs(amount: Union[int, float, Decimal]) -> str:
    """
    Format amount as Uzbekistan currency (UZS).
    
    Args:
        amount: Amount to format
    
    Returns:
        Formatted currency string with space separators
    
    Example:
        >>> format_currency_uzs(1500000)
        "1 500 000 сум"
    """
    # Convert to int if whole number
    if isinstance(amount, float) and amount == int(amount):
        amount = int(amount)
    
    # Format with space separators
    formatted = f"{amount:,.0f}".replace(',', ' ')
    return f"{formatted} сум"


# ===================== STRING VALIDATION =====================

def validate_length(
    value: str,
    min_length: int = 0,
    max_length: Optional[int] = None,
    field_name: str = "Поле"
) -> Tuple[bool, Optional[str]]:
    """
    Validate string length.
    
    Args:
        value: String to validate
        min_length: Minimum length
        max_length: Maximum length (optional)
        field_name: Field name for error message
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not value:
        if min_length > 0:
            return False, f"{field_name} обязательно для заполнения"
        return True, None
    
    length = len(value)
    
    if length < min_length:
        return False, f"{field_name} должно содержать минимум {min_length} символов"
    
    if max_length is not None and length > max_length:
        return False, f"{field_name} должно содержать максимум {max_length} символов"
    
    return True, None


def sanitize_string(value: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize string by trimming whitespace and limiting length.
    
    Args:
        value: String to sanitize
        max_length: Maximum length to truncate to
    
    Returns:
        Sanitized string
    """
    if not value:
        return value
    
    result = value.strip()
    
    if max_length and len(result) > max_length:
        result = result[:max_length]
    
    return result


# ===================== ID VALIDATION =====================

def validate_id(value: Any, field_name: str = "ID") -> Tuple[bool, Optional[str]]:
    """
    Validate that value is a positive integer ID.
    
    Args:
        value: Value to validate
        field_name: Field name for error message
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if value is None:
        return False, f"{field_name} обязателен"
    
    try:
        int_value = int(value)
        if int_value <= 0:
            return False, f"{field_name} должен быть положительным числом"
        return True, None
    except (ValueError, TypeError):
        return False, f"{field_name} должен быть целым числом"


def validate_ids_list(
    values: List[Any],
    field_name: str = "IDs",
    allow_empty: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Validate list of IDs.
    
    Args:
        values: List of values to validate
        field_name: Field name for error message
        allow_empty: Whether empty list is allowed
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not values:
        if allow_empty:
            return True, None
        return False, f"{field_name} не может быть пустым"
    
    for i, val in enumerate(values):
        is_valid, error = validate_id(val, f"{field_name}[{i}]")
        if not is_valid:
            return False, error
    
    return True, None
