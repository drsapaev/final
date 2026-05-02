"""Middleware for request metrics, trace IDs and structured request logs."""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.observability import observability_state

logger = logging.getLogger(__name__)
_TRACEPARENT_RE = re.compile(
    r"^[\da-f]{2}-(?P<trace_id>[\da-f]{32})-[\da-f]{16}-[\da-f]{2}$", re.IGNORECASE
)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Collect request SLI metrics and emit structured request logs."""

    @staticmethod
    def _extract_trace_id(request: Request) -> str:
        traceparent = request.headers.get("traceparent")
        if traceparent:
            match = _TRACEPARENT_RE.match(traceparent.strip())
            if match:
                return match.group("trace_id").lower()
        return uuid4().hex

    @staticmethod
    def _extract_client_ip(request: Request) -> str:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        if request.client:
            return request.client.host
        return "unknown"

    async def dispatch(  # type: ignore[override]
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        started_at = time.perf_counter()
        trace_id = self._extract_trace_id(request)
        request.state.trace_id = trace_id
        request_id = getattr(request.state, "request_id", None)
        if not request_id:
            request_id = str(uuid4())
            request.state.request_id = request_id

        path = request.url.path
        route = request.scope.get("route")
        route_path = getattr(route, "path", path)
        status_code = 500
        client_ip = self._extract_client_ip(request)

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            duration_ms = (time.perf_counter() - started_at) * 1000.0
            observability_state.record_request(
                method=request.method,
                path=route_path,
                status_code=status_code,
                duration_ms=duration_ms,
            )
            observability_state.evaluate_sla_alerts()
            logger.exception(
                "request.failed",
                extra={
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "method": request.method,
                    "path": route_path,
                    "status_code": status_code,
                    "duration_ms": round(duration_ms, 2),
                    "client_ip": client_ip,
                },
            )
            raise

        duration_ms = (time.perf_counter() - started_at) * 1000.0
        observability_state.record_request(
            method=request.method,
            path=route_path,
            status_code=status_code,
            duration_ms=duration_ms,
        )
        observability_state.evaluate_sla_alerts()

        response.headers["X-Trace-ID"] = trace_id
        response.headers["X-Request-ID"] = str(request_id)

        log_level = logging.ERROR if status_code >= 500 else logging.INFO
        logger.log(
            log_level,
            "request.completed",
            extra={
                "request_id": request_id,
                "trace_id": trace_id,
                "method": request.method,
                "path": route_path,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 2),
                "client_ip": client_ip,
            },
        )
        return response
