"""PR-7: Endpoint error logging helpers.

Audit found 12+ places in mobile/FCM endpoints where ``except Exception:``
silently swallows errors into HTTP 500 without logging the stack trace.
This makes debugging production issues nearly impossible — devops sees
500 status codes in monitoring but has no stack trace to investigate.

This module provides a single helper ``log_endpoint_error`` that logs
the exception with stack trace and request context, then re-raises
(but callers use it in ``except Exception`` blocks before raising
``HTTPException(500)``).

Usage::

    from app.api.v1.endpoints._error_logging import log_endpoint_error

    try:
        ...
    except HTTPException:
        raise
    except Exception as exc:
        log_endpoint_error("GET /mobile/foo", exc, user_id=current_user.id)
        raise HTTPException(status_code=500, detail="Internal server error")
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def log_endpoint_error(
    endpoint: str,
    exc: BaseException,
    *,
    user_id: int | str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Log an endpoint exception with stack trace and request context.

    Args:
        endpoint: human-readable endpoint identifier (e.g. "GET /mobile/foo")
        exc: the exception that was caught
        user_id: optional authenticated user id for correlation
        extra: optional dict of additional context fields
    """
    context: dict[str, Any] = {
        "endpoint": endpoint,
        "error_type": type(exc).__name__,
        "error_message": str(exc),
    }
    if user_id is not None:
        context["user_id"] = user_id
    if extra:
        context.update(extra)

    logger.exception(
        "Endpoint %s failed: %s: %s | context=%s",
        endpoint,
        context["error_type"],
        context["error_message"],
        context,
        exc_info=exc,
    )
