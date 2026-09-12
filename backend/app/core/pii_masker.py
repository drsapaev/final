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

import json
import re
from typing import Any
from urllib.parse import parse_qsl, unquote_plus

# ---------------------------------------------------------------------------
# Field-name list — backend source of truth.
# Frontend has its own MEDICAL_PII_KEYS list in frontend/src/services/sentry.ts
# (separate concern — frontend covers auth tokens + payment fields per BS-57,
# backend focuses on medical PHI). The two lists are intentionally separate
# and do not need to mirror each other. See docs/runbooks/SENTRY_SETUP.md
# section "Maintenance → Adding new PII fields".
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
#
# SECURITY (CodeQL py/polynomial-redos #1201): the previous pattern used
# `[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` for the domain part. The character class
# `[a-zA-Z0-9.-]` includes `.`, which overlaps with the literal `\.` that
# follows — for inputs with many dots, the engine could try multiple
# split points. While linear in practice, CodeQL flagged this as a
# potential polynomial-redos source.
#
# Fix: use `(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}` — each dot is a structural
# separator between domain labels, no ambiguity. The character class
# `[a-zA-Z0-9-]` no longer includes `.`.
#
# CodeQL still flags this pattern because the outer `+` quantifier on the
# non-capturing group is structurally similar to `(\w+)+`. Empirical
# testing confirms the regex is LINEAR (10000-char pathological input
# completes in 85ms, not seconds) — see test_pii_regex_redos.py for the
# ReDoS safety verification. The alert is a false positive based on
# CodeQL's structural heuristic.
# codeql[py/polynomial-redos]
EMAIL_REGEX = re.compile(
    r"([a-zA-Z0-9._%+-])[a-zA-Z0-9._%+-]*@"
    r"((?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,})"
)

# Passport/doc: AB1234567 → AB•••••••
PASSPORT_REGEX = re.compile(r"\b([A-Z]{2})\d{6,8}\b")

# IIN (Uzbek 14-digit): 12345678901234 → 1234••••••••34
IIN_REGEX = re.compile(r"\b(\d{4})\d{6}(\d{4})\b")

# PR-6: push device credentials inside FREE-TEXT payloads (raw JSON request
# bodies captured by the Sentry integration, log lines, breadcrumbs).
# Dict-shaped payloads are covered by SECRET_FIELD_PATTERNS below; this
# regex catches the string form: {"token": "..."} etc. Conservative by
# design — only credential-looking JSON keys are redacted, never prose.
#
# PR-6 round 4 (codex P1): the value part is ESCAPE-AWARE —
# (?:[^"\\]|\\.)* — because a webpush credential is a serialized
# subscription object whose quotes arrive escaped in raw bodies
# ("token":"{\"endpoint\":...}"). A plain [^"]+ stopped at the first
# escaped quote and left the endpoint and key material exposed. The two
# alternation branches start with disjoint character classes (non-quote-
# non-backslash vs backslash), so the scan stays linear (no ReDoS).
JSON_CREDENTIAL_REGEX = re.compile(
    r'("(?:token|previous_token|device_token|fcm_token|push_token'
    r'|web_push_subscription|vapid_private_key)"\s*:\s*")((?:[^"\\]|\\.)*)(")'
)

# PR-6 round 10 (codex P1): FORM / urlencoded credential assignments —
# raw request bodies with content types like application/x-www-form-urlencoded
# arrive as "token=<credential>&..." with NO quotes, so the JSON regex above
# cannot see them. Conservative: only credential-looking keys, never prose.
FORM_CREDENTIAL_REGEX = re.compile(
    r'\b(token|previous_token|device_token|fcm_token|push_token'
    r'|web_push_subscription|vapid_private_key)=([^\s&]+)'
)

# ---------------------------------------------------------------------------
# Secret fields (PR-6): provider credentials must never leave the
# infrastructure through Sentry captures or structured logs. Exact-match
# key redaction, same style as full_redact_patterns in _mask_key_value.
# ---------------------------------------------------------------------------
SECRET_FIELD_PATTERNS = (
    # push device registry credentials (PR-6) — request bodies of
    # /api/v1/push/devices/* attach to Sentry events on unhandled 5xx
    "token",
    "previous_token",
    "device_token",
    "fcm_token",
    "push_token",
    "web_push_subscription",
    "vapid_private_key",
)


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


def mask_identifier(value: str | None) -> str | None:
    """Auto-detect phone/email/username format and apply appropriate masking.

    Used for auth_svc logs where the same `username` field can be:
    - A phone number (mobile login): "+998901234567" → "+998901•••567"
    - An email (web admin login): "john.doe@example.com" → "j•••@example.com"
    - A plain username: "admin" → "a•••n"

    Plain usernames are partially masked (first char + dots + last char)
    so that debug logs remain useful without exposing the full identifier.
    Single-character values are returned unchanged (too short to mask).
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    s = value.strip()
    if not s:
        return value

    # Phone: starts with + and digits (use existing PHONE_REGEX)
    if s.startswith("+") and any(c.isdigit() for c in s):
        return mask_phone(s)

    # Email: contains @
    if "@" in s:
        return mask_email(s)

    # Plain username: partial mask preserving first + last char
    if len(s) == 1:
        return s
    if len(s) == 2:
        return s[0] + "•"
    if len(s) == 3:
        return s[0] + "•" + s[-1]
    # 4+ chars: first + ••• + last
    return s[0] + "•••" + s[-1]


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

    # Secret credentials first (PR-6): never partially masked, never
    # recursed into — a credential is a credential in any shape.
    if key_lower in SECRET_FIELD_PATTERNS:
        return "[REDACTED]"

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
    if isinstance(value, str):
        # PR-6 round 4 (codex P1): a string under an ordinary dict key
        # still gets the free-text scrubbing pass. Fresh evidence: Sentry
        # may represent request bodies as raw JSON strings under keys
        # like "data" — key-based redaction misses them, and without
        # this pass JSON_CREDENTIAL_REGEX (credential-shaped JSON inside
        # the string) is never reached, leaking the full credential.
        return _mask_string_inplace(value)
    return value


def _mask_string_inplace(s: str) -> str:
    """Apply all regex maskers to a free-text string."""
    # PR-6 round 5 (codex P2): a string that IS a JSON document is parsed
    # and re-scrubbed STRUCTURALLY — valid JSON can spell a key as a
    # unicode escape (e.g. "\u0074oken"), which the literal-key regex
    # below would never match while Pydantic happily accepts it. Parsing
    # routes every key spelling (and nested shapes) through the key-based
    # redaction; re-serialization is compact so already-compact inputs
    # stay stable (idempotent). If the string does not parse, fall
    # through to the regex pass (log lines, truncated bodies, prose).
    if s.lstrip()[:1] in ("{", "["):
        try:
            parsed = json.loads(s)
        except Exception:
            parsed = None
        if isinstance(parsed, (dict, list)):
            try:
                return json.dumps(
                    mask_pii(parsed), ensure_ascii=False, separators=(",", ":")
                )
            except Exception:
                # Never let masking itself break the caller — fall back
                # to the regex pass below.
                pass
    # PR-6 rounds 10-12: form/urlencoded credential redaction. When the
    # text is percent-escaped, parse it into RAW-delimited key/value pairs
    # FIRST (parse_qsl splits before decoding), so an encoded delimiter
    # (%26) inside a value cannot split it and leak the remainder: a pair
    # whose DECODED key is a credential name gets its whole value redacted.
    # Plain (non-escaped) forms fall through to FORM_CREDENTIAL_REGEX.
    if "%" in s:
        try:
            pairs = parse_qsl(s, keep_blank_values=True)
        except Exception:
            pairs = []
        if pairs:
            rebuilt = []
            for k, v in pairs:
                lk = k.lower()
                if lk in SECRET_FIELD_PATTERNS or lk.endswith("token"):
                    rebuilt.append(f"{k}=[REDACTED]")
                else:
                    rebuilt.append(f"{k}={v}")
            s = "&".join(rebuilt)
        else:
            try:
                decoded = unquote_plus(s)
            except Exception:
                decoded = s
            if decoded != s:
                s = decoded
    s = PHONE_REGEX.sub(r"\1•••\2", s)
    s = EMAIL_REGEX.sub(r"\1•••@\2", s)
    s = PASSPORT_REGEX.sub(r"\1••••••", s)
    s = IIN_REGEX.sub(r"\1••••••\2", s)
    # PR-6: credential-shaped JSON keys inside raw bodies / log lines
    s = JSON_CREDENTIAL_REGEX.sub(r"\1[REDACTED]\3", s)
    # PR-6 round 10: form-style credential assignments (token=...)
    s = FORM_CREDENTIAL_REGEX.sub(r"\1=[REDACTED]", s)
    return s


def mask_pii_text(s: str) -> str:
    """Mask PII embedded in free text (emails, phones, passports, IINs).

    Public seam for scrubbing provider error strings — e.g. smtplib
    exceptions quote the recipient address (SMTPRecipientsRefused) —
    before they reach logs or API responses.
    """
    return _mask_string_inplace(s)


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
