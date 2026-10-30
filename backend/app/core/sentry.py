"""
Backend Sentry initialization.

Initializes Sentry for FastAPI + SQLAlchemy + asyncPG. No-op if
SENTRY_DSN env var is unset.

PII scrubbing for Sentry events is handled by ``sanitize_event()``, which
delegates to ``mask_pii()`` from ``pii_masker.py`` — the single source of
truth for backend PII patterns (``PII_FIELD_PATTERNS``). Frontend has its
own ``MEDICAL_PII_KEYS`` list in ``frontend/src/services/sentry.ts``
(separate concern, more aggressive — covers auth tokens and payment
fields per BS-57).

Usage (called from app/main.py):
    from app.core.sentry import init_sentry
    init_sentry()
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from app.core.pii_masker import mask_pii

logger = logging.getLogger(__name__)

# Standard Sentry contexts as documented by Sentry:
# https://docs.sentry.io/platforms/python/enriching-events/contexts/
_STANDARD_SENTRY_CONTEXTS = frozenset(
    {
        "app",  # app version, build type
        "browser",  # browser name, version
        "device",  # device model, family, arch
        "os",  # os name, version, build
        "runtime",  # runtime name, version (CPython, etc.)
        "gpu",  # GPU name, vendor
        "trace",  # distributed tracing (trace_id, span_id)
        "response",  # HTTP response context
        "culture",  # user culture (locale, timezone)
        "cloud_resource",  # cloud provider info
    }
)

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

# Provider payloads can contain clinical notes and tool arguments under
# generic keys that are not covered by the PII field catalog.
_AI_CONTENT_KEYS = frozenset(
    {
        "prompt",
        "prompts",
        "system_prompt",
        "systemprompt",
        "system_instructions",
        "systeminstructions",
        "user_prompt",
        "input",
        "user_input",
        "patient_input",
        "input_text",
        "output",
        "output_text",
        "provider_response",
        "providerresponse",
        "response",
        "responses",
        "content",
        "completion",
        "completions",
        "messages",
        "arguments",
        "tool_args",
        "tool_arguments",
        "toolargs",
        "toolarguments",
    }
)
_SAFE_HTTP_RESPONSE_FIELDS = frozenset({"status_code", "body_size"})
_SAFE_AI_DIAGNOSTIC_FIELDS = frozenset(
    {
        "status_code",
        "body_size",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "model",
    }
)
_SAFE_AI_DIAGNOSTIC_CODES = frozenset(
    {
        "ai_gateway_unexpected_error",
        "ai_gateway_stream_error",
        "ai_provider_failure",
    }
)


def _scrub_http_response_context(value: Any) -> Any:
    """Keep numeric response diagnostics and discard arbitrary response data."""
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in value.items()
        if str(key).lower() in _SAFE_HTTP_RESPONSE_FIELDS
        and isinstance(item, int | float)
        and not isinstance(item, bool)
    }


def _normalize_field_key(key: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", key).lower().replace("-", "_")


def _is_safe_ai_diagnostic(key: str, value: Any) -> bool:
    leaf = key.rsplit(".", 1)[-1]
    if leaf in {
        "status_code",
        "body_size",
        "input_tokens",
        "output_tokens",
        "total_tokens",
    } or leaf.endswith("_tokens"):
        return isinstance(value, int | float) and not isinstance(value, bool)
    if leaf == "model":
        return (
            isinstance(value, str)
            and re.fullmatch(r"[A-Za-z0-9_.:/-]{1,80}", value) is not None
        )
    return False


def _is_diagnostic_field(key: str) -> bool:
    leaf = key.rsplit(".", 1)[-1]
    return leaf in _SAFE_AI_DIAGNOSTIC_FIELDS or leaf.endswith("_tokens")


def _is_ai_content_key(key: str) -> bool:
    normalized = _normalize_field_key(key)
    leaf = normalized.rsplit(".", 1)[-1]
    return any(content_key in normalized for content_key in _AI_CONTENT_KEYS)


def _redact_ai_content(value: Any, parent_key: str = "") -> Any:
    """Remove AI prompt/response content wherever it appears in an event."""
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            normalized_key = _normalize_field_key(str(key))
            is_http_response_context = (
                parent_key == "contexts" and normalized_key == "response"
            )
            if is_http_response_context:
                redacted[key] = _scrub_http_response_context(item)
            elif _is_diagnostic_field(normalized_key):
                redacted[key] = (
                    item
                    if _is_safe_ai_diagnostic(normalized_key, item)
                    else "[REDACTED]"
                )
            elif _is_ai_content_key(normalized_key):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_ai_content(item, normalized_key)
        return redacted
    if isinstance(value, list):
        return [_redact_ai_content(item, parent_key) for item in value]
    return value


def _redact_unstructured_event_text(event: dict[str, Any]) -> None:
    """Drop free-form text fields that can contain clinical narratives."""
    if isinstance(event.get("message"), str):
        event["message"] = "[REDACTED]"

    request = event.get("request")
    if isinstance(request, dict) and request.get("data") is not None:
        # Request bodies can contain patient text under unknown field names.
        request["data"] = "[REDACTED]"

    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        for key in ("message", "formatted"):
            if isinstance(logentry.get(key), str):
                logentry[key] = "[REDACTED]"
        if logentry.get("params") is not None:
            logentry["params"] = []

    breadcrumbs = event.get("breadcrumbs")
    crumbs = breadcrumbs.get("values") if isinstance(breadcrumbs, dict) else breadcrumbs
    if isinstance(crumbs, list):
        for crumb in crumbs:
            if isinstance(crumb, dict) and isinstance(crumb.get("message"), str):
                crumb["message"] = "[REDACTED]"

    exception = event.get("exception")
    values = exception.get("values") if isinstance(exception, dict) else None
    if isinstance(values, list):
        for value_entry in values:
            if not isinstance(value_entry, dict):
                continue
            if value_entry.get("value") is not None:
                value_entry["value"] = "[REDACTED]"
            stacktrace = value_entry.get("stacktrace")
            frames = stacktrace.get("frames") if isinstance(stacktrace, dict) else None
            if isinstance(frames, list):
                for frame in frames:
                    if isinstance(frame, dict) and "vars" in frame:
                        frame["vars"] = {}

    # sentry-python can attach a second stack under `threads`; those locals
    # can contain the same patient objects as exception frame variables.
    threads = event.get("threads")
    thread_values = threads.get("values") if isinstance(threads, dict) else None
    if isinstance(thread_values, list):
        for thread in thread_values:
            if not isinstance(thread, dict):
                continue
            stacktrace = thread.get("stacktrace")
            frames = stacktrace.get("frames") if isinstance(stacktrace, dict) else None
            if isinstance(frames, list):
                for frame in frames:
                    if isinstance(frame, dict) and "vars" in frame:
                        frame["vars"] = {}

    transaction = event.get("transaction")
    if isinstance(transaction, str):
        event["transaction"] = mask_pii(transaction)


def _preserve_safe_ai_diagnostic_grouping(event: dict[str, Any]) -> None:
    """Keep a stable, low-cardinality fingerprint for sanitized AI log events."""
    extra = event.get("extra")
    if not isinstance(extra, dict):
        return
    diagnostic_code = extra.get("diagnostic_code")
    if diagnostic_code not in _SAFE_AI_DIAGNOSTIC_CODES:
        return

    fingerprint = ["{{ default }}", diagnostic_code]
    for field in ("provider", "error_type"):
        value = extra.get(field)
        if isinstance(value, str) and value.replace("_", "").isalnum():
            fingerprint.append(value)
    event["fingerprint"] = fingerprint


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
    - ``event["breadcrumbs"]`` — ``values[*].data`` payloads and
      ``values[*].message`` (raw formatted log lines recorded by the
      logging integration on subsequent events)
    - ``event["extra"]`` — extra context
    - ``event["contexts"]`` — ALL contexts are scrubbed; for standard
      Sentry contexts (runtime, os, device, etc.), known diagnostic
      fields (e.g. ``name``) are preserved while sensitive keys and
      free-text PII are still redacted
    - ``event["exception"]["values"][*]["value"]`` — ``str(exc)``, may
      contain phone/email/IIN/passport from bound SQL params
    - ``event["exception"]["values"][*]["stacktrace"]["frames"][*]["vars"]``
      — frame local variables, may contain patient objects
    - ``event["logentry"]`` — ``message``, ``params``, ``formatted`` from
      ``LoggingIntegration`` (ERROR-level logs). The ``PIIMaskingFilter``
      in ``logging_config.py`` is attached to the app's own stdout
      handler, NOT to the root logger, so Sentry's logging handler sees
      the raw LogRecord; this is the only scrubbing layer for logentry.

    Missing fields are skipped silently — this function must not raise on
    events with partial structure (e.g. ``{}`` or ``{"exception": {}}``).
    """
    if "request" in event:
        event["request"] = mask_pii(event["request"])

    if "breadcrumbs" in event:
        # Sentry event protocol ships breadcrumbs as {"values": [...]};
        # tolerate both that dict and a bare list, preserve the container
        # shape, and skip non-dict crumbs.
        crumbs = event["breadcrumbs"]

        def _scrumb(b: Any) -> Any:
            if not isinstance(b, dict):
                return mask_pii(b)
            scrubbed = {**b, "data": mask_pii(b.get("data", {}))}
            message = scrubbed.get("message")
            if isinstance(message, str):
                # Breadcrumb messages carry raw formatted log lines: the
                # logging integration records every log record as a
                # breadcrumb on subsequent events, so PHI logged anywhere
                # surfaces here on the next captured error.
                scrubbed["message"] = mask_pii(message)
            return scrubbed

        if isinstance(crumbs, dict):
            values = crumbs.get("values", [])
            if isinstance(values, list):
                crumbs["values"] = [_scrumb(b) for b in values]
        elif isinstance(crumbs, list):
            event["breadcrumbs"] = [_scrumb(b) for b in crumbs]
        else:
            event["breadcrumbs"] = mask_pii(crumbs)

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
            event["contexts"] = {k: _scrub_context(k, v) for k, v in contexts.items()}
        else:
            event["contexts"] = mask_pii(contexts)

    if "logentry" in event:
        logentry = event["logentry"]
        if isinstance(logentry, dict):
            # LoggingIntegration puts the raw record message/args here.
            # PIIMaskingFilter runs on the app's stdout handler only, so
            # without this block PHI in logger.error(...)/logger.exception(...)
            # arguments reaches Sentry unscrubbed.
            message = logentry.get("message")
            if isinstance(message, str):
                logentry["message"] = mask_pii(message)
            params = logentry.get("params")
            if params is not None:
                logentry["params"] = mask_pii(params)
            formatted = logentry.get("formatted")
            if isinstance(formatted, str):
                logentry["formatted"] = mask_pii(formatted)

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
    if os.getenv("TESTING", "").strip().lower() in {"1", "true", "yes", "on"}:
        # Test runs (pytest conftest) load backend/.env with the production
        # DSN; without this guard every error-level log from a local pytest
        # session shipped straight to production Sentry (e.g. PYTHON-FASTAPI-C
        # "RBAC role check denied" with url=http://testserver/...).
        logger.info("[sentry] TESTING=1 — Sentry disabled for backend tests.")
        return
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
        except Exception:
            # sentry_sdk.integrations.DidNotEnable — raised when asyncpg is
            # not installed. This app uses psycopg, so the integration is
            # optional; DidNotEnable is not an ImportError subclass and
            # previously crashed init_sentry() (and app startup) whenever
            # SENTRY_DSN was set on a psycopg-only host.
            AsyncPGIntegration = None
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

    def sanitize_for_sentry(event: dict, _hint: dict | None = None) -> dict | None:
        """Scrub PII from Sentry event before sending.

        Delegates all masking logic to ``sanitize_event()`` which uses
        ``mask_pii()`` from ``pii_masker.py`` — the single source of truth
        for PII scrubbing, shared with ``JsonLogFormatter`` and
        ``PIIMaskingFilter`` for stdout logs.

        If sanitization raises, the event is dropped. The failure is logged via
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
            _redact_unstructured_event_text(event)
            event.update(_redact_ai_content(event))
            _preserve_safe_ai_diagnostic_grouping(event)
        except Exception:
            # logger.warning (NOT logger.exception) — see docstring above
            # for the Sentry recursion risk that logger.exception creates.
            logger.warning("Sentry before_send sanitizer failed; event dropped")
            return None
        return event

    def before_send(event: dict, hint: dict) -> dict | None:
        return sanitize_for_sentry(event, hint)

    def before_send_transaction(event: dict, hint: dict) -> dict | None:
        return sanitize_for_sentry(event, hint)

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=os.getenv("APP_VERSION", "unknown"),
        traces_sample_rate=sample_rate,  # 5% perf traces; errors always captured
        send_default_pii=False,  # CRITICAL: never send PII by default
        before_send=before_send,
        before_send_transaction=before_send_transaction,
        integrations=integrations,
        # Drop errors from noisy HTTP clients / bots
        ignore_errors=[
            "fastapi.exceptions.HTTPException",  # 4xx are not errors
        ],
    )
    logger.info(
        "[sentry] initialized (env=%s, sample_rate=%s)", environment, sample_rate
    )


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
