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
#
# Round 15 (owner codex review P1, PR #3215): the DOMAIN part was linear,
# but the LOCAL part was not — `[class][class]*@` on a long @-free input
# restarts the unbounded class run at EVERY position (greedy consume to
# end of run, backtrack, fail, retry one char later): quadratic. Measured
# on the shared 422 path (validation_exception_handler → mask_pii →
# _mask_string_inplace): 48 KB body → 1.67 s in EMAIL_REGEX alone, 192 KB
# → ~27 s of synchronous CPU inside the async handler — event-loop
# starvation reachable from ANY endpoint that can raise
# RequestValidationError. (The earlier "linear" 85ms measurement used a
# 10 KB input — too small to separate O(n) from O(n²).)
#
# Fix: negative lookbehind anchors each attempt to the START of a
# local-part run — every position is consumed by at most one attempt, so
# the scan is O(n) total. Masking results are byte-identical: with
# leftmost-first semantics the run-start attempt always succeeded first
# (any mid-run attempt requires the same '@' right after the same run
# end), so no match is gained or lost; only the wasted restarts vanish.
EMAIL_REGEX = re.compile(
    r"(?<![a-zA-Z0-9._%+-])([a-zA-Z0-9._%+-])[a-zA-Z0-9._%+-]*@"
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

# Round 14 (codex P2): gate for the percent-decoding form path — only
# strings whose DECODED form actually carries a credential-shaped field
# may be parsed/rebuilt; ordinary diagnostics ("90% complete") pass
# through untouched.
#
# Round 15 (owner codex review P1 — ReDoS): the round-14 gate was a
# regex — (?i)[\w.%-]*(?:token|web_push_subscription|vapid)[\w.%-]*\s*=\s*\S
# — driven by unanchored .search() over the FULL decoded body. On a long
# credential-free input the engine restarts the unbounded leading
# [\w.%-]* run at every position: quadratic backtracking. Measured on
# the exact HTTP path (validation_exception_handler → mask_pii → gate):
# 12 KB body → 0.34 s, 24 KB → 1.35 s, 48 KB → 5.35 s of synchronous
# CPU inside the ASYNC handler — event-loop starvation for the whole
# API, reachable from ANY endpoint that can raise RequestValidationError
# (e.g. POST /api/v1/authentication/login) with an invalid oversized
# body. Independent of FCM activation.
#
# Replacement: LINEAR gate (below). Keyword locating uses str.find — a
# C-level two-way scan with no backtracking, and successive scans from
# each hit partition the string, so total find work is O(n) per
# keyword. Tail validation after each hit runs on a bounded window with
# the exact semantics of [\w.%-]*\s*=\s*\S (wordish-run, whitespace-run,
# '=', whitespace-run, non-space), mirroring Python \w via isalnum()/_
# so unicode keys (Cyrillic etc.) behave like the old regex.
#
# Verdicts per keyword hit:
#   * a char outside [\w.%-\s] appears before '=' → definitively NOT a
#     credential field at this occurrence (identical to the old regex —
#     prose like "token: expired" or "90% complete" stays untouched);
#   * '=' found and a non-space char follows → credential field;
#   * the string ends mid-pattern (no trailing \S) → definitively NOT;
#   * the wordish or whitespace run is still running when the window
#     ends while the string continues → INCONCLUSIVE → the caller
#     fails CLOSED and redacts the whole string: an oversized
#     unsupported shape is safer to redact entirely than to let a
#     credential whose '=' sits beyond the window slip through.
_CREDENTIAL_KEYWORDS = ("token", "web_push_subscription", "vapid")
_CREDENTIAL_FIELD_WINDOW = 130  # keyword→'=' distance cap (≈6× the longest key)


def _form_gate_state(decoded: str) -> str:
    """Linear-time credential-field detector for the decoded form path.

    Returns "match" (credential-shaped field present), "clean"
    (definitively absent), or "unknown" (inconclusive — caller must
    fail closed). Total work: O(3n) for the finds + O(window) per hit;
    hits whose tail overflows the window abort the scan immediately.
    """
    n = len(decoded)
    lowered = decoded.lower()
    saw_match = False
    for kw in _CREDENTIAL_KEYWORDS:
        start = 0
        while True:
            i = lowered.find(kw, start)
            if i == -1:
                break
            state = _credential_tail_state(decoded, i + len(kw))
            if state == "unknown":
                # One inconclusive tail is enough to fail closed for the
                # whole string — regardless of any definitive match
                # elsewhere (an unknown tail may hide a SECOND credential
                # that the parse_qsl rebuild would not redact).
                return "unknown"
            if state == "match":
                saw_match = True
            start = i + 1
    return "match" if saw_match else "clean"


def _credential_tail_state(text: str, j: int) -> str:
    """Validate [\\w.%-]*\\s*=\\s*\\S at text[j:] within a bounded window."""
    n = len(text)
    limit = min(n, j + _CREDENTIAL_FIELD_WINDOW)
    k = j

    def is_wordish(ch: str) -> bool:
        # Python re \w = unicode alnum + underscore; % . - are explicit.
        return ch.isalnum() or ch in "_%.-"

    while k < limit and is_wordish(text[k]):
        k += 1
    if k == limit and k < n:
        return "unknown"  # wordish run continues beyond the window
    while k < limit and text[k].isspace():
        k += 1
    if k == limit and k < n:
        return "unknown"  # whitespace run continues beyond the window
    if k >= n or text[k] != "=":
        # Blocker char before '=' (e.g. ':' or ',' — the old regex could
        # not skip it) or string ended: no match from this occurrence.
        return "clean"
    k += 1
    while k < limit and text[k].isspace():
        k += 1
    if k >= n:
        return "clean"  # '=' at the very end — no trailing \S anywhere
    if k == limit and text[k].isspace():
        return "unknown"  # post-'=' whitespace run reaches the cut
    return "match"  # non-space char right after the (optional) spaces

# PR-6 round 13 (codex P1): Python repr forms of captured Pydantic frame
# locals — Sentry can serialize a model as
# PushDeviceRegisterRequest(token='{"endpoint": ...}') where the quoted
# value contains SPACES and the opposite quote style. The form regex
# would stop at the first whitespace, so these escape-aware patterns
# consume the whole quoted value (disjoint alternation branches — linear).
_PYREPR_SQ_CREDENTIAL_REGEX = re.compile(
    r"\b(token|previous_token|device_token|fcm_token|push_token"
    r'|web_push_subscription|vapid_private_key)=\'((?:[^\'\\]|\\.)*)\''
)
_PYREPR_DQ_CREDENTIAL_REGEX = re.compile(
    r'\b(token|previous_token|device_token|fcm_token|push_token'
    r'|web_push_subscription|vapid_private_key)="((?:[^"\\]|\\.)*)"'
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
    # PR-6 rounds 10-12: form/urlencoded credential redaction — but ONLY
    # for strings that actually look like credential-bearing form data
    # (round 14, codex P2: a bare "%" must not mangle unrelated evidence
    # like "90% complete"). The gate checks the DECODED text for a
    # credential-shaped field; parse_qsl then splits on RAW delimiters so
    # an encoded %26 inside a value cannot split it (round 12), and a pair
    # whose decoded key is a credential name is redacted WHOLE (round 11).
    # Round 15 (owner codex review P1): the gate itself is now a LINEAR
    # bounded scan (see _form_gate_state) — the previous unanchored
    # regex search was quadratic on long credential-free bodies and
    # starved the event loop from the shared 422 handler.
    if "%" in s:
        try:
            decoded = unquote_plus(s)
        except Exception:
            decoded = s
        if decoded != s:
            state = _form_gate_state(decoded)
            if state == "unknown":
                # Fail closed: a credential keyword is followed by more
                # than _CREDENTIAL_FIELD_WINDOW chars of wordish/whitespace
                # with no '=' in sight — a shape the bounded gate cannot
                # resolve. Redact the string wholesale (owner doctrine:
                # oversized/unsupported input is safer fully redacted
                # than partially processed) instead of risking a leak.
                return "[REDACTED]"
            if state == "match":
                try:
                    pairs = parse_qsl(s, keep_blank_values=True)
                except Exception:
                    pairs = []
                if pairs:
                    rebuilt = []
                    for k, v in pairs:
                        dk = unquote_plus(k).lower()
                        if (
                            dk in SECRET_FIELD_PATTERNS
                            or dk.endswith("token")
                            or "token=" in dk
                            or any(p in dk for p in SECRET_FIELD_PATTERNS)
                        ):
                            # the credential may sit in the KEY itself (e.g.
                            # "%74oken%3Dsecret") — drop the whole field
                            rebuilt.append("[REDACTED]")
                        else:
                            rebuilt.append(f"{k}={v}")
                    s = "&".join(rebuilt)
                else:
                    s = decoded
    s = PHONE_REGEX.sub(r"\1•••\2", s)
    s = EMAIL_REGEX.sub(r"\1•••@\2", s)
    s = PASSPORT_REGEX.sub(r"\1••••••", s)
    s = IIN_REGEX.sub(r"\1••••••\2", s)
    # PR-6: credential-shaped JSON keys inside raw bodies / log lines
    s = JSON_CREDENTIAL_REGEX.sub(r"\1[REDACTED]\3", s)
    # PR-6 round 13: Python repr of captured model locals (token='...')
    s = _PYREPR_SQ_CREDENTIAL_REGEX.sub(r"\1='[REDACTED]'", s)
    s = _PYREPR_DQ_CREDENTIAL_REGEX.sub(r'\1="[REDACTED]"', s)
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
