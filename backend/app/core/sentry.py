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
import math
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
_SAFE_AI_PROVIDERS = frozenset({"openai", "gemini", "deepseek", "grok", "mock", "none"})
_SAFE_ALERT_TYPES = frozenset(
    {
        "payment_failure",
        "database_error",
        "auth_failure",
        "queue_error",
        "high_error_rate",
        "external_service",
        "security_incident",
        "system_resource",
    }
)
_SAFE_ALERT_SEVERITIES = frozenset({"info", "warning", "error", "critical"})
_SAFE_HTTP_METHODS = frozenset(
    {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
)
_SAFE_SPAN_OPS = frozenset(
    {
        "http.client",
        "http.server",
        "db",
        "db.query",
        "db.sql.query",
        "cache.get",
        "cache.put",
        "function",
        "task",
        "queue.process",
        "ui.load",
        "ui.click",
        "navigation",
        "resource.fetch",
        "ai.completion",
        "gen_ai.request",
    }
)
_SAFE_EVENT_FIELDS = frozenset(
    {
        "event_id",
        "timestamp",
        "start_timestamp",
        "platform",
        "level",
        "environment",
        "release",
        "dist",
        "sdk",
        "type",
        "exception",
        "threads",
        "request",
        "contexts",
        "extra",
        "tags",
        "fingerprint",
        "transaction",
        "transaction_info",
        "spans",
        "measurements",
        "trace",
        "message",
        "logentry",
    }
)
_SAFE_SPAN_DATA_FIELDS = frozenset(
    {
        "http.response.status_code",
        "http.request.method",
        "http.response.body.size",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "gen_ai.usage.total_tokens",
        "db.system",
        "db.operation",
    }
)
_SAFE_DB_SYSTEMS = frozenset({"postgresql", "postgres", "redis", "mysql"})
_SAFE_DB_OPERATIONS = frozenset(
    {"SELECT", "INSERT", "UPDATE", "DELETE", "BEGIN", "COMMIT", "ROLLBACK"}
)
_SAFE_MEASUREMENTS = frozenset(
    {
        "lcp",
        "cls",
        "fcp",
        "ttfb",
        "inp",
        "fp",
        "tbt",
        "frames",
        "frames_slow",
        "frames_frozen",
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


def _bounded_number(value: Any, minimum: int, maximum: int) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        if not math.isfinite(value) or not minimum <= value <= maximum:
            return None
    except (OverflowError, TypeError, ValueError):
        return None
    return value


def _safe_token(value: Any, pattern: str, maximum_length: int = 128) -> str | None:
    if not isinstance(value, str) or len(value) > maximum_length:
        return None
    if re.fullmatch(pattern, value) is None:
        return None
    return value


def _safe_trace_context(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    for field in ("trace_id", "span_id", "parent_span_id", "segment_id"):
        candidate = value.get(field)
        if isinstance(candidate, str) and re.fullmatch(
            r"[0-9a-fA-F]{16}|[0-9a-fA-F]{32}", candidate
        ):
            safe[field] = candidate
    sampled = value.get("sampled")
    if isinstance(sampled, bool):
        safe["sampled"] = sampled
    op = value.get("op")
    if isinstance(op, str) and op in _SAFE_SPAN_OPS:
        safe["op"] = op
    status = value.get("status")
    if isinstance(status, str) and status in {"ok", "error", "cancelled"}:
        safe["status"] = status
    return safe


def _safe_contexts(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    response = value.get("response")
    if isinstance(response, dict):
        response_safe = {}
        status_code = _bounded_number(response.get("status_code"), 100, 599)
        body_size = _bounded_number(response.get("body_size"), 0, 1_000_000_000)
        if status_code is not None and int(status_code) == status_code:
            response_safe["status_code"] = int(status_code)
        if body_size is not None and int(body_size) == body_size:
            response_safe["body_size"] = int(body_size)
        if response_safe:
            safe["response"] = response_safe

    trace = _safe_trace_context(value.get("trace"))
    if trace:
        safe["trace"] = trace

    version_pattern = r"\d{1,3}(?:\.\d{1,4}){0,3}"
    context_name_allowlists = {
        "runtime": {"python", "cpython", "node", "javascript", "v8", "deno"},
        "browser": {"chrome", "chromium", "firefox", "safari", "edge", "opera"},
        "os": {
            "windows",
            "windows server",
            "linux",
            "ubuntu",
            "debian",
            "macos",
            "mac os x",
            "ios",
            "android",
            "darwin",
        },
    }
    for context_name, allowed_names in context_name_allowlists.items():
        context = value.get(context_name)
        if not isinstance(context, dict):
            continue
        context_safe = {}
        name = context.get("name")
        if isinstance(name, str) and name.casefold() in allowed_names:
            context_safe["name"] = name
        version = _safe_token(context.get("version"), version_pattern, 32)
        if version is not None:
            context_safe["version"] = version
        if context_safe:
            safe[context_name] = context_safe
    return safe


def _safe_extra(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    diagnostic_code = value.get("diagnostic_code")
    if (
        isinstance(diagnostic_code, str)
        and diagnostic_code in _SAFE_AI_DIAGNOSTIC_CODES
    ):
        safe["diagnostic_code"] = diagnostic_code
    provider = value.get("provider")
    if isinstance(provider, str) and provider in _SAFE_AI_PROVIDERS:
        safe["provider"] = provider
    error_type = _safe_token(
        value.get("error_type"), r"[A-Z][A-Za-z0-9]*(?:Error|Exception|Fault|Timeout)"
    )
    if error_type is not None:
        safe["error_type"] = error_type
    for field, minimum, maximum in (
        ("status_code", 100, 599),
        ("body_size", 0, 1_000_000_000),
        ("input_tokens", 0, 1_000_000_000),
        ("output_tokens", 0, 1_000_000_000),
        ("total_tokens", 0, 1_000_000_000),
    ):
        number = _bounded_number(value.get(field), minimum, maximum)
        if number is not None and int(number) == number:
            safe[field] = int(number)
    return safe


def _safe_tags(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, str] = {}
    alert_type = value.get("alert_type")
    if isinstance(alert_type, str) and alert_type in _SAFE_ALERT_TYPES:
        safe["alert_type"] = alert_type
    severity = value.get("severity")
    if isinstance(severity, str) and severity in _SAFE_ALERT_SEVERITIES:
        safe["severity"] = severity
    return safe


def _safe_span_data(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    for field in _SAFE_SPAN_DATA_FIELDS:
        candidate = value.get(field)
        if field in {"http.response.status_code"}:
            number = _bounded_number(candidate, 100, 599)
            if number is not None and int(number) == number:
                safe[field] = int(number)
        elif field in {
            "http.response.body.size",
            "gen_ai.usage.input_tokens",
            "gen_ai.usage.output_tokens",
            "gen_ai.usage.total_tokens",
        }:
            number = _bounded_number(candidate, 0, 1_000_000_000)
            if number is not None and int(number) == number:
                safe[field] = int(number)
        elif (
            field == "http.request.method"
            and isinstance(candidate, str)
            and candidate in _SAFE_HTTP_METHODS
        ):
            safe[field] = candidate
        elif (
            field == "db.system"
            and isinstance(candidate, str)
            and candidate in _SAFE_DB_SYSTEMS
        ):
            safe[field] = candidate
        elif (
            field == "db.operation"
            and isinstance(candidate, str)
            and candidate in _SAFE_DB_OPERATIONS
        ):
            safe[field] = candidate
    return safe


def _safe_span(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    for field in ("trace_id", "span_id", "parent_span_id"):
        candidate = value.get(field)
        if isinstance(candidate, str) and re.fullmatch(
            r"[0-9a-fA-F]{16}|[0-9a-fA-F]{32}", candidate
        ):
            safe[field] = candidate
    for field in ("start_timestamp", "timestamp"):
        number = _bounded_number(value.get(field), 0, 4_102_444_800)
        if number is not None:
            safe[field] = number
    op = value.get("op")
    if isinstance(op, str) and op in _SAFE_SPAN_OPS:
        safe["op"] = op
    status = value.get("status")
    if isinstance(status, str) and status in {"ok", "error", "cancelled"}:
        safe["status"] = status
    data = _safe_span_data(value.get("data"))
    if data:
        safe["data"] = data
    return safe


def _safe_stacktrace(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("frames"), list):
        return {}
    frames = []
    for frame in value["frames"]:
        if not isinstance(frame, dict):
            continue
        safe_frame: dict[str, Any] = {}
        for field in ("lineno", "colno"):
            number = _bounded_number(frame.get(field), 0, 10_000_000)
            if number is not None and int(number) == number:
                safe_frame[field] = int(number)
        function = _safe_token(
            frame.get("function"), r"[A-Za-z_$][A-Za-z0-9_.$<>:-]*", 128
        )
        if function is not None:
            safe_frame["function"] = function
        module = _safe_token(frame.get("module"), r"[A-Za-z_][A-Za-z0-9_.]*", 128)
        if module is not None:
            safe_frame["module"] = module
        filename = frame.get("filename")
        if isinstance(filename, str):
            basename = os.path.basename(filename.split("?", 1)[0].split("#", 1)[0])
            safe_filename = _safe_token(basename, r"[A-Za-z0-9_.-]+", 128)
            if safe_filename is not None:
                safe_frame["filename"] = safe_filename
        in_app = frame.get("in_app")
        if isinstance(in_app, bool):
            safe_frame["in_app"] = in_app
        if safe_frame:
            frames.append(safe_frame)
    return {"frames": frames} if frames else {}


def _safe_exception(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("values"), list):
        return {}
    safe_values = []
    for item in value["values"]:
        if not isinstance(item, dict):
            continue
        safe_item: dict[str, Any] = {"value": "[REDACTED]"}
        exception_type = _safe_token(
            item.get("type"), r"[A-Z][A-Za-z0-9]*(?:Error|Exception|Fault|Timeout)"
        )
        if exception_type is not None:
            safe_item["type"] = exception_type
        stacktrace = _safe_stacktrace(item.get("stacktrace"))
        if stacktrace:
            safe_item["stacktrace"] = stacktrace
        mechanism = item.get("mechanism")
        if isinstance(mechanism, dict):
            safe_mechanism: dict[str, Any] = {}
            mechanism_type = _safe_token(mechanism.get("type"), r"[A-Za-z0-9_.-]+", 64)
            if mechanism_type is not None:
                safe_mechanism["type"] = mechanism_type
            for field in ("handled", "synthetic"):
                flag = mechanism.get(field)
                if isinstance(flag, bool):
                    safe_mechanism[field] = flag
            if safe_mechanism:
                safe_item["mechanism"] = safe_mechanism
        safe_values.append(safe_item)
    return {"values": safe_values} if safe_values else {}


def _safe_threads(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not isinstance(value.get("values"), list):
        return {}
    safe_values = []
    for item in value["values"]:
        if not isinstance(item, dict):
            continue
        safe_item: dict[str, Any] = {}
        for field in ("current", "crashed"):
            flag = item.get(field)
            if isinstance(flag, bool):
                safe_item[field] = flag
        stacktrace = _safe_stacktrace(item.get("stacktrace"))
        if stacktrace:
            safe_item["stacktrace"] = stacktrace
        if safe_item:
            safe_values.append(safe_item)
    return {"values": safe_values} if safe_values else {}


def _safe_measurements(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe = {}
    for name in _SAFE_MEASUREMENTS:
        measurement = value.get(name)
        if not isinstance(measurement, dict):
            continue
        number = _bounded_number(measurement.get("value"), 0, 1_000_000_000)
        if number is None:
            continue
        safe[name] = {"value": number}
        unit = measurement.get("unit")
        if isinstance(unit, str) and unit in {
            "millisecond",
            "second",
            "none",
            "byte",
            "ratio",
            "hertz",
        }:
            safe[name]["unit"] = unit
    return safe


def _safe_sdk(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    safe: dict[str, Any] = {}
    name = _safe_token(value.get("name"), r"sentry\.[A-Za-z0-9_.-]+")
    if name is not None:
        safe["name"] = name
    version = _safe_token(
        value.get("version"), r"\d{1,3}(?:\.\d{1,4}){0,3}(?:[-+][A-Za-z0-9.-]+)?", 64
    )
    if version is not None:
        safe["version"] = version
    packages = value.get("packages")
    if isinstance(packages, list):
        safe_packages = []
        for package in packages:
            if not isinstance(package, dict):
                continue
            package_name = _safe_token(package.get("name"), r"@?sentry/[A-Za-z0-9_.-]+")
            package_version = _safe_token(
                package.get("version"),
                r"\d{1,3}(?:\.\d{1,4}){0,3}(?:[-+][A-Za-z0-9.-]+)?",
                64,
            )
            if package_name is not None and package_version is not None:
                safe_packages.append({"name": package_name, "version": package_version})
        if safe_packages:
            safe["packages"] = safe_packages
    return safe or None


def _safe_route_transaction(value: Any, source: Any) -> str | None:
    """Retain a framework-marked route template, never a raw URL/path value."""
    if source != "route" or not isinstance(value, str):
        return None
    segment = (
        r"(?:[A-Za-z0-9_.-]+|\{[A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z_][A-Za-z0-9_]*)?\})"
    )
    if re.fullmatch(rf"(?:[A-Z]+ )?/(?:{segment}(?:/{segment})*)?", value):
        return value
    return None


def sanitize_sentry_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Keep only Sentry protocol structure and explicitly safe diagnostics.

    Event callbacks are the final privacy boundary. Key-based PII masking
    cannot identify clinical text hidden under arbitrary field names, so this
    allowlist discards free text, user identity, raw URLs, breadcrumbs,
    custom contexts, and unrecognized event/span fields before transport.
    """
    safe = {key: event[key] for key in _SAFE_EVENT_FIELDS if key in event}

    if "event_id" in safe:
        event_id = _safe_token(safe["event_id"], r"[0-9a-fA-F]{32}", 32)
        if event_id is None:
            safe.pop("event_id", None)
        else:
            safe["event_id"] = event_id
    for field in ("timestamp", "start_timestamp"):
        if field in safe:
            number = _bounded_number(safe[field], 0, 4_102_444_800)
            if number is None:
                safe.pop(field, None)
            else:
                safe[field] = number

    if not isinstance(safe.get("platform"), str) or safe.get("platform") not in {
        "python",
        "javascript",
        "native",
        "other",
    }:
        safe.pop("platform", None)
    if not isinstance(safe.get("level"), str) or safe.get("level") not in {
        "fatal",
        "error",
        "warning",
        "log",
        "info",
        "debug",
    }:
        safe.pop("level", None)
    if safe.get("type") != "transaction":
        safe.pop("type", None)
    for field in ("environment", "release", "dist"):
        if field in safe:
            label = _safe_token(safe[field], r"[A-Za-z0-9_.+:-]+", 128)
            if label is None:
                safe.pop(field, None)
            else:
                safe[field] = label

    sdk = _safe_sdk(safe.get("sdk"))
    if sdk is not None:
        safe["sdk"] = sdk
    else:
        safe.pop("sdk", None)

    if "request" in safe:
        request = safe["request"]
        method = request.get("method") if isinstance(request, dict) else None
        safe["request"] = (
            {"method": method}
            if isinstance(method, str) and method in _SAFE_HTTP_METHODS
            else {}
        )
        if not safe["request"]:
            safe.pop("request")
    if "contexts" in safe:
        contexts = _safe_contexts(safe["contexts"])
        if contexts:
            safe["contexts"] = contexts
        else:
            safe.pop("contexts")
    if "trace" in safe:
        trace = _safe_trace_context(safe["trace"])
        if trace:
            safe["trace"] = trace
        else:
            safe.pop("trace")
    if "extra" in safe:
        extra = _safe_extra(safe["extra"])
        if extra:
            safe["extra"] = extra
        else:
            safe.pop("extra")
    if "tags" in safe:
        tags = _safe_tags(safe["tags"])
        if tags:
            safe["tags"] = tags
        else:
            safe.pop("tags")
    if "exception" in safe:
        exception = _safe_exception(safe["exception"])
        if exception:
            safe["exception"] = exception
        else:
            safe.pop("exception")
    if "threads" in safe:
        threads = _safe_threads(safe["threads"])
        if threads:
            safe["threads"] = threads
        else:
            safe.pop("threads")
    if "spans" in safe:
        spans = (
            [_safe_span(span) for span in safe["spans"]]
            if isinstance(safe["spans"], list)
            else []
        )
        safe["spans"] = [span for span in spans if span]
    if "measurements" in safe:
        measurements = _safe_measurements(safe["measurements"])
        if measurements:
            safe["measurements"] = measurements
        else:
            safe.pop("measurements")
    if "transaction_info" in safe:
        info = safe["transaction_info"]
        source = info.get("source") if isinstance(info, dict) else None
        if isinstance(source, str) and source in {
            "route",
            "url",
            "custom",
            "task",
            "component",
            "view",
        }:
            safe["transaction_info"] = {"source": source}
        else:
            safe.pop("transaction_info")

    if "message" in safe:
        safe["message"] = "[REDACTED]"
    if "logentry" in safe:
        safe["logentry"] = {"message": "[REDACTED]"}
    if isinstance(safe.get("transaction"), str):
        transaction_info = safe.get("transaction_info")
        source = (
            transaction_info.get("source")
            if isinstance(transaction_info, dict)
            else None
        )
        safe["transaction"] = (
            _safe_route_transaction(safe["transaction"], source)
            or "[REDACTED TRANSACTION]"
        )
    if "fingerprint" in safe:
        safe.pop("fingerprint")
    extra = safe.get("extra")
    if (
        isinstance(extra, dict)
        and isinstance(extra.get("diagnostic_code"), str)
        and extra["diagnostic_code"] in _SAFE_AI_DIAGNOSTIC_CODES
    ):
        fingerprint = ["{{ default }}", extra["diagnostic_code"]]
        for field in ("provider", "error_type"):
            value = extra.get(field)
            if isinstance(value, str):
                fingerprint.append(value)
        safe["fingerprint"] = fingerprint
    # Sentry breadcrumbs and the entire user object are intentionally not
    # copied into `safe`; both are independent payload channels.
    return safe


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
        """Scrub and minimize a Sentry event before sending.

        ``sanitize_event()`` applies the shared project PII masks. The final
        ``sanitize_sentry_payload()`` allowlist is required because key-based
        masks cannot recognize arbitrary clinical text under unknown fields.

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
            return sanitize_sentry_payload(event)
        except Exception:
            # logger.warning (NOT logger.exception) — see docstring above
            # for the Sentry recursion risk that logger.exception creates.
            logger.warning("Sentry before_send sanitizer failed; event dropped")
            return None

    def before_send(event: dict, hint: dict) -> dict | None:
        return sanitize_for_sentry(event, hint)

    def before_send_transaction(event: dict, hint: dict) -> dict | None:
        return sanitize_for_sentry(event, hint)

    def before_breadcrumb(_crumb: dict, _hint: dict | None = None) -> None:
        # Breadcrumbs can retain arbitrary log lines, URLs, and form values
        # until a later event is captured. Do not buffer them in this app.
        return None

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=os.getenv("APP_VERSION", "unknown"),
        traces_sample_rate=sample_rate,  # 5% perf traces; errors always captured
        send_default_pii=False,  # CRITICAL: never send PII by default
        before_send=before_send,
        before_send_transaction=before_send_transaction,
        before_breadcrumb=before_breadcrumb,
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
