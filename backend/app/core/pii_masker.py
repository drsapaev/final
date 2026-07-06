"""
PII masker for backend Python logging.

Mirrors the frontend Sentry scrubbing in frontend/src/services/sentry.js.
Use this in any log statement that might include patient data:

    from app.core.pii_masker import mask_pii, mask_phone, mask_email

    log.info("Visit created: %s", mask_pii(visit_dict))
    log.debug("Patient phone: %s", mask_phone(patient.phone))

DO NOT send unmasked PII to:
- External log sinks (Datadog, CloudWatch, Sentry)
- AI provider prompts (use pii_anonymizer.py instead)
- Audit log payload column (mask except for explicit audit need)
- Error messages returned to the client
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Field-name list — same set as frontend/src/services/sentry.js
# Keep these in sync. If you add a field here, add it there too.
# ---------------------------------------------------------------------------

PII_FIELD_PATTERNS = [
    # Patient identifiers
    "iin", "passport_number", "passport_series", "ssn", "national_id",
    "doc_number", "doc_series",
    # Contact info
    "phone", "phone_number", "mobile", "email",
    # Medical
    "diagnosis", "diagnoses", "icd10", "icd10_code", "icd10_codes",
    "complaints", "complaint", "examination", "prescription", "prescriptions",
    "medications", "medication", "allergies", "allergy",
    # Visit
    "visit_reason", "patient_name", "patient_full_name", "doctor_notes",
    "notes", "anamnesis", "anamnesis_morbida",
    # Names
    "first_name", "last_name", "middle_name", "full_name", "name",
    "birth_date", "date_of_birth", "dob",
    # Address
    "address", "street_address", "home_address",
]

PII_KEY_REGEX = re.compile(
    r"(" + "|".join(re.escape(p) for p in PII_FIELD_PATTERNS) + r")",
    re.IGNORECASE,
)

# Phone: +998901234567 → +998901•••567
PHONE_REGEX = re.compile(r"(\+\d{6})\d{3}(\d{3})")

# Email: john.doe@example.com → j•••@example.com
EMAIL_REGEX = re.compile(r"([a-zA-Z0-9._%+-])[a-zA-Z0-9._%+-]*@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")

# Passport/doc: AB1234567 → AB•••••••
PASSPORT_REGEX = re.compile(r"\b([A-Z]{2})\d{6,8}\b")

# IIN (Uzbek 14-digit): 12345678901234 → 1234••••••••34
IIN_REGEX = re.compile(r"\b(\d{4})\d{6}(\d{4})\b")


# ---------------------------------------------------------------------------
# Per-field maskers
# ---------------------------------------------------------------------------

def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return phone
    return PHONE_REGEX.sub(r"\1•••\2", phone)


def mask_email(email: str | None) -> str | None:
    if not email:
        return email
    return EMAIL_REGEX.sub(r"\1•••@\2", email)


def mask_passport(value: str | None) -> str | None:
    if not value:
        return value
    return PASSPORT_REGEX.sub(r"\1••••••", value)


def mask_iin(value: str | None) -> str | None:
    if not value:
        return value
    return IIN_REGEX.sub(r"\1••••••\2", value)


def mask_name(name: str | None) -> str | None:
    """Иван Иванов → И.И."""
    if not name:
        return name
    parts = [p for p in name.split() if p]
    if not parts:
        return name
    return ".".join(p[0].upper() for p in parts[:3]) + "."


def mask_birth_date(d: Any) -> str | None:
    """date(1985, 6, 15) → '1985-••-••'"""
    if d is None:
        return None
    if hasattr(d, "year"):
        return f"{d.year}-••-••"
    s = str(d)
    # ISO date: 1985-06-15 → 1985-••-••
    return re.sub(r"^(\d{4})-\d{2}-\d{2}", r"\1-••-••", s)


# ---------------------------------------------------------------------------
# Recursive object masker
# ---------------------------------------------------------------------------

def mask_pii(obj: Any) -> Any:
    """Recursively mask PII fields in a dict/list structure.

    Keys matching PII_FIELD_PATTERNS are replaced with '[REDACTED]' (or with
    a partially-masked value for phone/email/name/birth_date, which preserve
    enough structure to be useful for debugging).

    For free-text strings (not in a dict key), regex-based maskers run on
    phone numbers, emails, passports, IINs found anywhere in the string.
    """
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _mask_key_value(k, v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [mask_pii(item) for item in obj]
    if isinstance(obj, str):
        return _mask_string_inplace(obj)
    return obj


def _mask_key_value(key: str, value: Any) -> Any:
    if value is None:
        return None
    key_lower = key.lower()

    # Full-redact fields (identifiers, medical content)
    full_redact_patterns = {
        "iin", "passport_number", "passport_series", "ssn", "national_id",
        "doc_number", "doc_series",
        "diagnosis", "diagnoses", "icd10", "icd10_code", "icd10_codes",
        "complaints", "complaint", "examination", "prescription", "prescriptions",
        "medications", "medication", "allergies", "allergy",
        "visit_reason", "doctor_notes", "notes", "anamnesis", "anamnesis_morbida",
        "address", "street_address", "home_address",
    }
    if key_lower in full_redact_patterns:
        return "[REDACTED]"

    # Partial-mask fields (preserve structure for debug)
    if key_lower in ("phone", "phone_number", "mobile"):
        return mask_phone(value) if isinstance(value, str) else "[REDACTED]"
    if key_lower in ("email",):
        return mask_email(value) if isinstance(value, str) else "[REDACTED]"
    if key_lower in ("first_name", "last_name", "middle_name", "full_name", "name", "patient_name", "patient_full_name"):
        return mask_name(value) if isinstance(value, str) else "[REDACTED]"
    if key_lower in ("birth_date", "date_of_birth", "dob"):
        return mask_birth_date(value)

    # Recurse into nested structures
    if isinstance(value, (dict, list)):
        return mask_pii(value)
    return value


def _mask_string_inplace(s: str) -> str:
    """Apply all regex maskers to a free-text string."""
    s = PHONE_REGEX.sub(r"\1•••\2", s)
    s = EMAIL_REGEX.sub(r"\1•••@\2", s)
    s = PASSPORT_REGEX.sub(r"\1••••••", s)
    s = IIN_REGEX.sub(r"\1••••••\2", s)
    return s


# ---------------------------------------------------------------------------
# Convenience: structured logging filter
# ---------------------------------------------------------------------------

class PIIMaskingFilter:
    """logging.Filter that masks PII in record.msg and record.args.

    Usage:
        handler = logging.StreamHandler()
        handler.addFilter(PIIMaskingFilter())
        logger.addHandler(handler)

    Or, to apply globally:
        logging.getLogger().addFilter(PIIMaskingFilter())
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003 - logging API
        # Mask PII embedded directly in the message string.
        try:
            if isinstance(record.msg, str):
                record.msg = _mask_string_inplace(record.msg)
        except Exception:
            # Never let masking itself break logging
            pass
        # Mask PII in args. Note: logging.LogRecord unwraps a single-element
        # tuple whose only item is a Mapping into the Mapping itself, so we
        # must handle both shapes.
        if record.args:
            try:
                if isinstance(record.args, (dict, list)):
                    record.args = (mask_pii(record.args),)
                else:
                    record.args = tuple(
                        mask_pii(a) if isinstance(a, (dict, list, str)) else a
                        for a in record.args
                    )
            except Exception:
                # Never let masking itself break logging
                pass
        return True


# Late import to avoid circulars
import logging  # noqa: E402 - intentional late import
