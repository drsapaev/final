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
    """Recursively redact PII keys from a dict/list structure."""
    if data is None:
        return None
    if isinstance(data, dict):
        return {k: ("[REDACTED]" if k.lower() in MEDICAL_PII_KEYS else _scrub_pii(v)) for k, v in data.items()}
    if isinstance(data, list):
        return [_scrub_pii(item) for item in data]
    return data


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
        """Scrub PII from request bodies, breadcrumbs, extra context before sending."""
        try:
            if "request" in event:
                event["request"] = _scrub_pii(event["request"])
            if "breadcrumbs" in event:
                event["breadcrumbs"] = [
                    {**b, "data": _scrub_pii(b.get("data", {}))}
                    for b in event["breadcrumbs"]
                ]
            if "extra" in event:
                event["extra"] = _scrub_pii(event["extra"])
        except Exception:
            # Never let scrubbing itself fail the send
            pass
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
