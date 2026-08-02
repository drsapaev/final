"""
Backend Sentry initialization.

Mirrors frontend/src/services/sentry.js PII scrubbing. Initializes Sentry
for FastAPI + SQLAlchemy + asyncPG. No-op if SENTRY_DSN env var is unset.

Usage (called from app/main.py):
    from app.core.sentry import init_sentry
    init_sentry()
"""

from __future__ import annotations

import logging
import os
from typing import Any

from app.core.pii_masker import mask_pii

logger = logging.getLogger(__name__)

# Same field-name list as frontend/src/services/sentry.js + backend/app/core/pii_masker.py.
# Keep all three in sync.
MEDICAL_PII_KEYS = [
    "iin", "passport_number", "passport_series", "ssn", "national_id",
    "doc_number", "doc_series",
    "phone", "phone_number", "mobile", "email",
    "diagnosis", "diagnoses", "icd10", "icd10_code", "icd10_codes",
    "complaints", "complaint", "examination",
    "prescription", "prescriptions", "medications", "medication",
    "allergies", "allergy",
    "visit_reason", "patient_name", "patient_full_name", "doctor_notes",
    "notes", "anamnesis", "anamnesis_morbida",
    "first_name", "last_name", "middle_name", "full_name", "name",
    "birth_date", "date_of_birth", "dob",
    "address", "street_address", "home_address",
]


def _scrub_pii(data: Any) -> Any:
    """Recursively redact PII keys from a dict/list structure.

    .. note::
        ``before_send`` now uses ``mask_pii()`` from ``pii_masker.py`` which
        combines key-based redaction with regex-based string scrubbing.
        ``_scrub_pii`` is retained for backward compatibility and any
        callers outside ``before_send``. Removal is deferred to a separate
        cleanup PR after this security fix is verified in production.
    """
    if data is None:
        return None
    if isinstance(data, dict):
        return {k: ("[REDACTED]" if k.lower() in MEDICAL_PII_KEYS else _scrub_pii(v)) for k, v in data.items()}
    if isinstance(data, list):
        return [_scrub_pii(item) for item in data]
    return data


# Standard Sentry contexts as documented by Sentry:
# https://docs.sentry.io/platforms/python/enriching-events/contexts/
_STANDARD_SENTRY_CONTEXTS = frozenset({
    "app",             # app version, build type
    "browser",         # browser name, version
    "device",          # device model, family, arch
    "os",              # os name, version, build
    "runtime",         # runtime name, version (CPython, etc.)
    "gpu",             # GPU name, vendor
    "trace",           # distributed tracing (trace_id, span_id)
    "response",        # HTTP response context
    "culture",         # user culture (locale, timezone)
    "cloud_resource",  # cloud provider info
})

# Diagnostic field keys within standard Sentry contexts whose names collide
# with PII field patterns (e.g. "name" is in PII_FIELD_PATTERNS). These are
# preserved as-is when they appear inside a standard context, because they
# contain runtime/OS/device metadata (e.g. {"runtime": {"name": "CPython"}}),
# not patient data.
#
# All OTHER keys within standard contexts are still scrubbed via mask_pii(),
# so PII that accidentally lands inside a standard context (e.g.
# {"device": {"name": "server-1", "phone": "+998..."}}) is still redacted.
_STANDARD_CONTEXT_DIAGNOSTIC_KEYS = frozenset({"name"})


def _scrub_context(context_name: str, context_value: Any) -> Any:
    """Scrub a single Sentry context, preserving known diagnostic fields.

    For standard contexts (runtime, os, device, etc.), known diagnostic
    keys (e.g. ``name``) are passed through ``mask_pii()`` as raw values
    (not wrapped in a dict). This applies regex-based scrubbing (phone,
    email, passport, IIN) to the value without triggering key-based
    ``mask_name()`` — which would corrupt diagnostic names like
    ``"CPython"`` to ``"C."``. The result: ``device.name = "CPython"``
    is preserved, but ``device.name = "+998901234567"`` is scrubbed.

    All other keys within standard contexts are scrubbed via
    ``mask_pii({k: v})`` — wrapped in a single-key dict so ``mask_pii``
    can apply key-based redaction (e.g. ``diagnosis`` key →
    ``[REDACTED]``).

    For custom contexts, ``mask_pii()`` is applied to the entire value.
    """
    if not isinstance(context_value, dict):
        return mask_pii(context_value)
    if context_name in _STANDARD_SENTRY_CONTEXTS:
        result = {}
        for k, v in context_value.items():
            if k in _STANDARD_CONTEXT_DIAGNOSTIC_KEYS:
                # Apply mask_pii to the raw value — for strings this calls
                # _mask_string_inplace (regex only, no key-based masking).
                # Preserves "CPython" but scrubs "+998901234567".
                result[k] = mask_pii(v)
            else:
                # Wrap in single-key dict so mask_pii applies key-based
                # redaction (e.g. {"diagnosis": "Crohn"} → {"diagnosis": "[REDACTED]"})
                scrubbed = mask_pii({k: v})
                result[k] = scrubbed[k]
        return result
    return mask_pii(context_value)


def sanitize_event(event: dict[str, Any]) -> dict[str, Any]:
    """Scrub PII from a Sentry event before it is sent.

    This function is intentionally "dumb" — it does not know anything about
    regex patterns or PII field names. It delegates all masking logic to
    ``mask_pii()`` from ``pii_masker.py``, which is the single source of
    truth for PII scrubbing (also used by ``JsonLogFormatter`` and
    ``PIIMaskingFilter`` for stdout logs).

    Fields scrubbed:
    - ``event["request"]`` — request body, headers, query string
    - ``event["breadcrumbs"][*]["data"]`` — breadcrumb payloads
    - ``event["extra"]`` — extra context
    - ``event["contexts"]`` — ALL contexts are scrubbed; for standard
      Sentry contexts (runtime, os, device, etc.), known diagnostic
      fields (e.g. ``name``) are preserved while sensitive keys and
      free-text PII are still redacted
    - ``event["exception"]["values"][*]["value"]`` — ``str(exc)``, may
      contain phone/email/IIN/passport from bound SQL params
    - ``event["exception"]["values"][*]["stacktrace"]["frames"][*]["vars"]``
      — frame local variables, may contain patient objects

    Missing fields are skipped silently — this function must not raise on
    events with partial structure (e.g. ``{}`` or ``{"exception": {}}``).
    """
    if "request" in event:
        event["request"] = mask_pii(event["request"])

    if "breadcrumbs" in event:
        event["breadcrumbs"] = [
            {**b, "data": mask_pii(b.get("data", {}))}
            for b in event["breadcrumbs"]
        ]

    if "extra" in event:
        event["extra"] = mask_pii(event["extra"])

    if "contexts" in event:
        contexts = event["contexts"]
        if isinstance(contexts, dict):
            # Scrub ALL contexts — standard and custom. For standard
            # contexts, known diagnostic fields (e.g. "name") are
            # preserved via _scrub_context(); all other keys are scrubbed.
            # This ensures PII that accidentally lands inside a standard
            # context (e.g. device.phone) is still redacted.
            event["contexts"] = {
                k: _scrub_context(k, v) for k, v in contexts.items()
            }
        else:
            event["contexts"] = mask_pii(contexts)

    exception = event.get("exception")
    if isinstance(exception, dict):
        values = exception.get("values")
        if isinstance(values, list):
            for value_entry in values:
                if not isinstance(value_entry, dict):
                    continue
                # value = str(exc) — apply mask_pii (handles string via regex)
                exc_value = value_entry.get("value")
                if exc_value is not None:
                    value_entry["value"] = mask_pii(exc_value)
                # stacktrace.frames[*].vars — frame local variables
                stacktrace = value_entry.get("stacktrace")
                if isinstance(stacktrace, dict):
                    frames = stacktrace.get("frames")
                    if isinstance(frames, list):
                        for frame in frames:
                            if not isinstance(frame, dict):
                                continue
                            if "vars" in frame:
                                frame["vars"] = mask_pii(frame["vars"])

    return event


def init_sentry() -> None:
    """Initialize Sentry for the FastAPI backend. No-op if SENTRY_DSN is unset."""
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        logger.info("[sentry] SENTRY_DSN not set — Sentry disabled for backend.")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.redis import RedisIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        try:
            from sentry_sdk.integrations.asyncpg import AsyncPGIntegration
        except ImportError:
            AsyncPGIntegration = None  # older sentry-sdk
    except ImportError:
        logger.warning(
            "[sentry] sentry-sdk not installed. "
            "Run: pip install -r backend/requirements-monitoring.txt"
        )
        return

    environment = os.getenv("SENTRY_ENV", os.getenv("ENV", "development")).lower()
    sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.05"))

    integrations = [
        FastApiIntegration(),
        SqlalchemyIntegration(),
        RedisIntegration(),
    ]
    if AsyncPGIntegration is not None:
        integrations.append(AsyncPGIntegration())

    def before_send(event: dict, hint: dict) -> dict | None:
        """Scrub PII from Sentry event before sending.

        Delegates all masking logic to ``sanitize_event()`` which uses
        ``mask_pii()`` from ``pii_masker.py`` — the single source of truth
        for PII scrubbing, shared with ``JsonLogFormatter`` and
        ``PIIMaskingFilter`` for stdout logs.

        If ``sanitize_event`` raises, the event is still returned (unscrubbed)
        so error tracking is not lost. The failure is logged via
        ``logger.warning`` (NOT ``logger.exception``) to avoid Sentry
        recursion: ``LoggingIntegration`` auto-registers with
        ``DEFAULT_EVENT_LEVEL=ERROR``, so ``logger.exception`` (level=ERROR)
        would trigger a new Sentry event → re-enter ``before_send`` →
        infinite recursion until ``RecursionError``. ``logger.warning``
        (level=WARNING < ERROR) does not trigger event capture, breaking
        the cycle while still recording the failure in stdout logs.
        """
        try:
            sanitize_event(event)
        except Exception:
            # logger.warning (NOT logger.exception) — see docstring above
            # for the Sentry recursion risk that logger.exception creates.
            logger.warning(
                "Sentry before_send sanitizer failed — "
                "event sent unscrubbed (event_id=%s error_type=%s)",
                event.get("event_id", "unknown"),
                type(hint.get("exception") or hint.get("exc_info") or Exception()).__name__
                if hint else "unknown",
            )
        return event

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=os.getenv("APP_VERSION", "unknown"),
        traces_sample_rate=sample_rate,  # 5% perf traces; errors always captured
        send_default_pii=False,  # CRITICAL: never send PII by default
        before_send=before_send,
        integrations=integrations,
        # Drop errors from noisy HTTP clients / bots
        ignore_errors=[
            "fastapi.exceptions.HTTPException",  # 4xx are not errors
        ],
    )
    logger.info("[sentry] initialized (env=%s, sample_rate=%s)", environment, sample_rate)


def capture_exception(exc: Exception, **context: Any) -> None:
    """Capture an exception with optional context. No-op if Sentry not initialized."""
    try:
        import sentry_sdk
        if context:
            with sentry_sdk.push_scope() as scope:
                for k, v in context.items():
                    scope.set_extra(k, v)
                sentry_sdk.capture_exception(exc)
        else:
            sentry_sdk.capture_exception(exc)
    except ImportError:
        pass
    except Exception:
        # Never let Sentry itself crash the app
        pass


def capture_message(msg: str, level: str = "info") -> None:
    """Capture a message. No-op if Sentry not initialized."""
    try:
        import sentry_sdk
        sentry_sdk.capture_message(msg, level=level)
    except ImportError:
        pass
    except Exception:
        pass
