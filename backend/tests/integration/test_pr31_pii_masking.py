"""
PR-31 — Sprint 3 PII masking (High-8).

Tests for:
1. New mask_identifier() helper that detects phone/email/username format
2. auth_svc/_tokens.py no longer logs raw usernames (must use mask_identifier)
3. AuditMiddleware logs mutating requests with PII masking
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
PII_MASKER_PY = BACKEND_DIR / "app" / "core" / "pii_masker.py"
TOKENS_PY = BACKEND_DIR / "app" / "services" / "auth_svc" / "_tokens.py"
AUDIT_MIDDLEWARE_PY = BACKEND_DIR / "app" / "middleware" / "audit_middleware.py"


# ---------- 1. mask_identifier helper ----------

def test_mask_identifier_function_exists():
    """A new mask_identifier() helper must be exported from pii_masker.py.

    It auto-detects phone (+998901234567), email (foo@bar.com), or username
    format and applies the appropriate masking. This is needed because
    auth_svc logs 'username=%s' where the value can be a phone (mobile login)
    or an email (web admin login) — both are PII.
    """
    src = PII_MASKER_PY.read_text(encoding="utf-8")
    assert re.search(r"^def\s+mask_identifier\s*\(", src, re.MULTILINE), (
        "mask_identifier() function not found in pii_masker.py"
    )


def test_mask_identifier_masks_phone():
    """+998901234567 → +998901•••567"""
    from app.core.pii_masker import mask_identifier
    assert mask_identifier("+998901234567") == "+998901•••567"


def test_mask_identifier_masks_email():
    """john.doe@example.com → j•••@example.com"""
    from app.core.pii_masker import mask_identifier
    assert mask_identifier("john.doe@example.com") == "j•••@example.com"


def test_mask_identifier_masks_plain_username_partially():
    """Plain usernames (not phone, not email) are partially masked.

    'admin' → 'a•••n' (first char + dots + last char, min 4 chars displayed).
    'a'     → 'a' (single char unchanged — too short to mask).
    None    → None.
    """
    from app.core.pii_masker import mask_identifier
    assert mask_identifier("admin") == "a•••n"
    assert mask_identifier("a") == "a"
    assert mask_identifier(None) is None
    assert mask_identifier("") == ""


def test_mask_identifier_handles_short_usernames():
    """Short usernames (2-3 chars) get partial masking."""
    from app.core.pii_masker import mask_identifier
    # 2 chars: ab → a•
    assert mask_identifier("ab") == "a•"
    # 3 chars: abc → a•c
    assert mask_identifier("abc") == "a•c"


# ---------- 2. auth_svc/_tokens.py masks usernames ----------

def test_auth_tokens_does_not_log_raw_username():
    """auth_svc/_tokens.py must NOT log raw username values.

    Previously:
        logger.debug("authenticate_user called with username=%s", username)
        logger.debug("User not found for username=%s", username)
        logger.debug("User found: ID=%d, Username=%s, IsActive=%s", ...)
        logger.debug("login_user called with username=%s", username)

    These leak PII because usernames can be phone numbers (mobile login) or
    emails (web admin login). Fix: wrap username in mask_identifier() or
    log only the user ID once resolved.
    """
    src = TOKENS_PY.read_text(encoding="utf-8")
    # Find any log statement that interpolates a raw `username` variable
    # (not wrapped in mask_identifier).
    # Pattern: logger.<level>("...%s...", username)  — NOT mask_identifier(username)
    bad_patterns = [
        r'username=%s",\s*username\b',
        r'Username=%s",\s*user\.username\b',
        r'username=%s",\s*user\.username\b',
        r'Username=%s",\s*username\b',
    ]
    for pat in bad_patterns:
        matches = re.findall(pat, src)
        assert not matches, (
            f"_tokens.py still logs raw username (pattern: {pat!r}) — "
            f"found {len(matches)} match(es). Wrap with mask_identifier()."
        )


def test_auth_tokens_imports_mask_identifier():
    """_tokens.py must import mask_identifier from pii_masker."""
    src = TOKENS_PY.read_text(encoding="utf-8")
    assert "mask_identifier" in src, (
        "mask_identifier not imported/used in _tokens.py"
    )


# ---------- 3. AuditMiddleware logs mutating requests ----------

def test_audit_middleware_logs_mutating_requests():
    """AuditMiddleware must log POST/PUT/PATCH/DELETE requests with PII masking.

    Currently it only sets request_id — no actual audit logging.
    Fix: log method + path + user_id (if available) for mutating requests,
    with PII masking applied to query string and any logged payload summary.
    """
    src = AUDIT_MIDDLEWARE_PY.read_text(encoding="utf-8")
    # The middleware must have an explicit check for mutating methods.
    assert re.search(
        r'(POST|PUT|PATCH|DELETE)',
        src,
    ), "AuditMiddleware must check for mutating HTTP methods (POST/PUT/PATCH/DELETE)"
    # Must log via logger (audit log entry).
    assert re.search(
        r'logger\.(info|warning|audit)\s*\([^)]*method',
        src,
        re.DOTALL,
    ), "AuditMiddleware must call logger with method info for mutating requests"


def test_audit_middleware_masks_query_string():
    """Query string in audit log must be PII-masked.

    Phone numbers and emails in ?param=... are PII and must not appear
    in the audit log in plaintext.
    """
    src = AUDIT_MIDDLEWARE_PY.read_text(encoding="utf-8")
    # Must import or reference mask_pii / mask_identifier
    assert "mask_pii" in src or "mask_identifier" in src, (
        "AuditMiddleware must use mask_pii or mask_identifier to scrub query strings"
    )
