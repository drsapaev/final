"""
Middleware для автоматического аудит-логирования критичных операций.

PR-31: AuditMiddleware now logs mutating requests (POST/PUT/PATCH/DELETE)
with PII masking applied to the query string. This provides a basic audit
trail for HIPAA compliance without leaking patient phone numbers, emails,
or other PII that may appear in query parameters.
"""
import logging
from collections.abc import Callable
from contextvars import ContextVar
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.pii_masker import mask_pii  # PR-31: PII scrubber for query strings

logger = logging.getLogger(__name__)

# ContextVar для хранения Request в текущем контексте (для использования в dependencies)
_request_context: ContextVar[Request] = ContextVar("request_context", default=None)


# PR-31: HTTP methods that mutate server state and must be audit-logged.
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def get_current_request() -> Request | None:
    """Получить текущий Request из contextvar"""
    return _request_context.get()


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware для установки request_id в каждом запросе и аудит-логирования
    mutating-запросов (POST/PUT/PATCH/DELETE).

    Аудит-лог содержит:
    - HTTP method + path
    - PII-маскированную query string (телефоны/emails скрываются)
    - request_id для трассировки
    - user_id если доступен (после авторизации)

    Не логирует:
    - Тело запроса (может содержать пароли, медицинские данные)
    - GET-запросы (не изменяют состояние)
    - WebSocket-соединения
    """

    async def dispatch(  # type: ignore[override]
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        # Генерируем уникальный request_id для каждого запроса
        request_id = str(uuid4())
        request.state.request_id = request_id

        # ✅ Сохраняем Request в contextvar для использования в dependencies
        token = _request_context.set(request)

        try:
            # PR-31: Audit-log mutating requests BEFORE processing.
            # We log here (not after) so that even if the handler crashes,
            # the audit trail captures the attempt.
            method = request.method.upper()
            if method in MUTATING_METHODS:
                self._audit_log_request(request, request_id, method)

            # Добавляем request_id в заголовки ответа для отладки
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id

            return response
        finally:
            # Восстанавливаем предыдущее значение contextvar
            _request_context.reset(token)

    @staticmethod
    def _audit_log_request(request: Request, request_id: str, method: str) -> None:
        """Log a mutating request with PII masking applied to query string."""
        path = request.url.path
        # Mask PII in query string — phones/emails are common in ?param=...
        # (e.g., /mobile/patients/lookup?phone=+998901234567)
        query_string = ""
        if request.url.query:
            # Parse query params into a dict and mask recursively.
            # This catches both `phone=...` and `email=...` style params.
            try:
                from urllib.parse import parse_qs
                params = {k: v if len(v) > 1 else v[0]
                          for k, v in parse_qs(request.url.query).items()}
                masked = mask_pii(params)
                # Re-serialize as k=v pairs for compact log line
                parts = []
                for k, v in masked.items():
                    if isinstance(v, list):
                        parts.append(f"{k}={','.join(str(x) for x in v)}")
                    else:
                        parts.append(f"{k}={v}")
                query_string = "?" + "&".join(parts) if parts else ""
            except Exception:
                # If query parsing fails, log the raw string through mask_pii
                # (string mode applies regex-based phone/email masking)
                query_string = "?" + str(mask_pii(request.url.query))

        # Try to extract user_id from the JWT in Authorization header (best-effort).
        # We do NOT decode the JWT here — just check if the header is present.
        # Full user identification is the responsibility of downstream audit hooks.
        user_id = getattr(request.state, "user_id", None) or "anonymous"

        logger.info(
            "audit.mutating_request method=%s path=%s%s user_id=%s request_id=%s",
            method,
            path,
            query_string,
            user_id,
            request_id,
        )
