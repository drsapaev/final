"""
Patient Data Validation Service

✅ SECURITY: Comprehensive validation and sanitization for patient data
"""
import re
import logging
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple
from html import escape

logger = logging.getLogger(__name__)


class PatientValidationService:
    """Service for patient data validation and sanitization"""

    # Field length limits
    MAX_NAME_LENGTH = 128
    MAX_PHONE_LENGTH = 32
    MAX_DOC_NUMBER_LENGTH = 64
    MAX_ADDRESS_LENGTH = 512

    # Phone number patterns (Uzbekistan)
    PHONE_PATTERNS = [
        r"^\+998\d{9}$",  # +998XXXXXXXXX
        r"^998\d{9}$",    # 998XXXXXXXXX
        r"^\d{9}$",       # XXXXXXXXX (local)
    ]

    # Document types
    VALID_DOC_TYPES = ["passport", "id_card", "birth_certificate", "driver_license"]

    def sanitize_string(self, value: Optional[str], max_length: int = None) -> Optional[str]:
        """
        Sanitize string input
        
        Args:
            value: Input string
            max_length: Maximum allowed length
        
        Returns:
            Sanitized string or None
        """
        if not value:
            return None

        # Remove leading/trailing whitespace
        value = value.strip()

        # Remove null bytes and control characters (except newlines and tabs)
        value = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]', '', value)

        # Limit length
        if max_length and len(value) > max_length:
            value = value[:max_length]
            logger.warning(f"String truncated to {max_length} characters")

        return value if value else None

    def validate_name(self, name: Optional[str], field_name: str = "name") -> Tuple[bool, Optional[str]]:
        """
        Validate name field
        
        Returns:
            (is_valid, error_message)
        """
        if not name:
            return False, f"{field_name} is required"

        # Sanitize
        name = self.sanitize_string(name, self.MAX_NAME_LENGTH)
        if not name:
            return False, f"{field_name} cannot be empty"

        # Check length
        if len(name) < 2:
            return False, f"{field_name} must be at least 2 characters"

        if len(name) > self.MAX_NAME_LENGTH:
            return False, f"{field_name} exceeds maximum length of {self.MAX_NAME_LENGTH}"

        # Check for valid characters (letters, spaces, hyphens, apostrophes)
        # Use [\w\s\-\'] instead of \p{L} for better compatibility
        if not re.match(r'^[\w\s\-\']+$', name, re.UNICODE):
            return False, f"{field_name} contains invalid characters"

        # Check for excessive whitespace
        if re.search(r'\s{3,}', name):
            return False, f"{field_name} contains excessive whitespace"

        return True, None

    def validate_phone(self, phone: Optional[str]) -> Tuple[bool, Optional[str]]:
        """
        Validate phone number
        
        Returns:
            (is_valid, error_message)
        """
        if not phone:
            return True, None  # Phone is optional

        # Sanitize
        phone = self.sanitize_string(phone, self.MAX_PHONE_LENGTH)
        if not phone:
            return True, None  # Empty phone is valid

        # Remove common formatting characters
        phone = re.sub(r'[\s\-\(\)]', '', phone)

        # Check if matches any valid pattern
        is_valid = any(re.match(pattern, phone) for pattern in self.PHONE_PATTERNS)

        if not is_valid:
            return False, "Invalid phone number format. Expected: +998XXXXXXXXX or 998XXXXXXXXX"

        return True, None

    def validate_birth_date(self, birth_date: Optional[date]) -> Tuple[bool, Optional[str]]:
        """
        Validate birth date
        
        Returns:
            (is_valid, error_message)
        """
        if not birth_date:
            return True, None  # Birth date is optional

        today = date.today()

        # Check if date is in the future
        if birth_date > today:
            return False, "Birth date cannot be in the future"

        # Check if date is too far in the past (reasonable limit: 150 years)
        min_date = date(today.year - 150, 1, 1)
        if birth_date < min_date:
            return False, "Birth date is too far in the past"

        return True, None

    def validate_document(
        self, doc_type: Optional[str], doc_number: Optional[str]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate document information
        
        Returns:
            (is_valid, error_message)
        """
        # Both or neither must be provided
        if bool(doc_type) != bool(doc_number):
            return False, "Both document type and number must be provided together"

        if not doc_type:
            return True, None  # Documents are optional

        # Validate document type
        if doc_type.lower() not in self.VALID_DOC_TYPES:
            return False, f"Invalid document type. Valid types: {', '.join(self.VALID_DOC_TYPES)}"

        # Validate document number
        doc_number = self.sanitize_string(doc_number, self.MAX_DOC_NUMBER_LENGTH)
        if not doc_number:
            return False, "Document number cannot be empty"

        # Document number should contain alphanumeric characters
        if not re.match(r'^[A-Za-z0-9]+$', doc_number):
            return False, "Document number contains invalid characters"

        return True, None

    def validate_address(self, address: Optional[str]) -> Tuple[bool, Optional[str]]:
        """
        Validate address
        
        Returns:
            (is_valid, error_message)
        """
        if not address:
            return True, None  # Address is optional

        # Sanitize
        address = self.sanitize_string(address, self.MAX_ADDRESS_LENGTH)
        if not address:
            return True, None  # Empty address is valid

        # Check length
        if len(address) > self.MAX_ADDRESS_LENGTH:
            return False, f"Address exceeds maximum length of {self.MAX_ADDRESS_LENGTH}"

        # Check for potentially dangerous content (basic XSS prevention)
        if re.search(r'<script|javascript:|onerror=|onload=', address, re.IGNORECASE):
            return False, "Address contains potentially dangerous content"

        return True, None

    def validate_sex(self, sex: Optional[str]) -> Tuple[bool, Optional[str]]:
        """
        Validate sex/gender field
        
        Returns:
            (is_valid, error_message)
        """
        if not sex:
            return True, None  # Sex is optional

        valid_values = ["M", "F", "X", "m", "f", "x", "M", "F", "X"]
        if sex.upper() not in ["M", "F", "X"]:
            return False, "Sex must be M (Male), F (Female), or X (Other)"

        return True, None

    def validate_patient_data(self, patient_data: Dict) -> Tuple[bool, List[str]]:
        """
        Comprehensive validation of patient data
        
        Args:
            patient_data: Dictionary with patient fields
        
        Returns:
            (is_valid, list_of_errors)
        """
        errors = []

        # Validate names
        # ✅ ИСПРАВЛЕНО: Проверяем только если поле не пустое (после нормализации full_name должен быть разобран)
        last_name = patient_data.get("last_name")
        if last_name and last_name.strip():
            valid, error = self.validate_name(last_name, "Last name")
            if not valid:
                errors.append(error)

        first_name = patient_data.get("first_name")
        if first_name and first_name.strip():
            valid, error = self.validate_name(first_name, "First name")
            if not valid:
                errors.append(error)

        if "middle_name" in patient_data:
            middle_name = patient_data.get("middle_name")
            if middle_name:  # Middle name is optional
                valid, error = self.validate_name(middle_name, "Middle name")
                if not valid:
                    errors.append(error)

        # ✅ ИСПРАВЛЕНО: После нормализации full_name должен быть разобран на last_name и first_name
        # normalize_patient_name всегда возвращает last_name и first_name (даже если full_name состоит из одного слова)
        has_last_name = patient_data.get("last_name") and patient_data.get("last_name").strip()
        has_first_name = patient_data.get("first_name") and patient_data.get("first_name").strip()
        has_full_name = patient_data.get("full_name") and patient_data.get("full_name").strip()

        # Если нормализация уже произошла (что должно быть в create_patient), требуем оба поля
        # Если нормализация еще не произошла (прямой вызов валидации), разрешаем full_name
        if not has_full_name:
            # После нормализации должны быть и last_name, и first_name
            if not has_last_name:
                errors.append("Last name is required")
            if not has_first_name:
                errors.append("First name is required")
        elif not (has_last_name and has_first_name):
            # Есть full_name, но нет last_name/first_name - нормализация еще не произошла
            # Это допустимо, если валидация вызывается до нормализации
            # Но в create_patient нормализация происходит ПЕРЕД валидацией, так что это не должно происходить
            pass  # full_name достаточен до нормализации

        # Validate phone
        if "phone" in patient_data:
            valid, error = self.validate_phone(patient_data.get("phone"))
            if not valid:
                errors.append(error)

        # Validate birth date
        if "birth_date" in patient_data:
            birth_date = patient_data.get("birth_date")
            if isinstance(birth_date, str):
                try:
                    birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date()
                except ValueError:
                    errors.append("Invalid birth date format. Expected: YYYY-MM-DD")
                    birth_date = None

            if birth_date:
                valid, error = self.validate_birth_date(birth_date)
                if not valid:
                    errors.append(error)

        # Validate document
        if "doc_type" in patient_data or "doc_number" in patient_data:
            valid, error = self.validate_document(
                patient_data.get("doc_type"),
                patient_data.get("doc_number")
            )
            if not valid:
                errors.append(error)

        # Validate address
        if "address" in patient_data:
            valid, error = self.validate_address(patient_data.get("address"))
            if not valid:
                errors.append(error)

        # Validate sex
        if "sex" in patient_data or "gender" in patient_data:
            sex = patient_data.get("sex") or patient_data.get("gender")
            valid, error = self.validate_sex(sex)
            if not valid:
                errors.append(error)

        return len(errors) == 0, errors

    def sanitize_patient_data(self, patient_data: Dict) -> Dict:
        """
        Sanitize all patient data fields
        
        Args:
            patient_data: Dictionary with patient fields
        
        Returns:
            Sanitized dictionary
        """
        sanitized = {}

        # Sanitize string fields
        string_fields = ["last_name", "first_name", "middle_name", "full_name", "phone", "address", "doc_type", "doc_number"]
        for field in string_fields:
            if field in patient_data:
                if field == "phone":
                    # Special handling for phone - remove formatting
                    value = patient_data[field]
                    if value:
                        value = re.sub(r'[\s\-\(\)]', '', str(value))
                    sanitized[field] = self.sanitize_string(value, self.MAX_PHONE_LENGTH if field == "phone" else None)
                else:
                    max_len = {
                        "last_name": self.MAX_NAME_LENGTH,
                        "first_name": self.MAX_NAME_LENGTH,
                        "middle_name": self.MAX_NAME_LENGTH,
                        "full_name": self.MAX_NAME_LENGTH * 3,  # Allow for full name
                        "address": self.MAX_ADDRESS_LENGTH,
                        "doc_type": 32,
                        "doc_number": self.MAX_DOC_NUMBER_LENGTH,
                    }.get(field)
                    sanitized[field] = self.sanitize_string(patient_data[field], max_len)

        # Preserve other fields (dates, integers, etc.)
        other_fields = ["birth_date", "sex", "gender", "user_id"]
        for field in other_fields:
            if field in patient_data:
                sanitized[field] = patient_data[field]

        return sanitized

