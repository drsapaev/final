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
# These contain runtime/OS/device metadata rather than application
# payloads — scrubbing them corrupts diagnostic value (e.g. "name"
# key in {"runtime": {"name": "CPython"}} is masked to "C.").
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
    - ``event["contexts"]`` — custom (non-standard) contexts only;
      standard Sentry contexts (runtime, os, device, etc.) are preserved
      because they contain diagnostic metadata, not patient data
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
            # Scrub only custom (non-standard) contexts. Standard Sentry
            # contexts (runtime, os, device, app, browser, gpu, trace,
            # response, culture, cloud_resource) contain runtime/OS/device
            # metadata rather than application payloads — scrubbing them
            # corrupts diagnostic value (e.g. "name" key in
            # {"runtime": {"name": "CPython"}} is masked to "C.").
            #
            # If the application intentionally uses a standard key (runtime,
            # os, etc.) for its own data, that data will no longer pass
            # through mask_pii(). This is considered an acceptable
            # trade-off since such keys are reserved by the Sentry spec.
            event["contexts"] = {
                k: (v if k in _STANDARD_SENTRY_CONTEXTS else mask_pii(v))
                for k, v in contexts.items()
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
