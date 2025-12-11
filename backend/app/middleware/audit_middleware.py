"""
Middleware для автоматического аудит-логирования критичных операций.
"""
import logging
from contextvars import ContextVar
from typing import Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# ContextVar для хранения Request в текущем контексте (для использования в dependencies)
_request_context: ContextVar[Request] = ContextVar("request_context", default=None)


def get_current_request() -> Request | None:
    """Получить текущий Request из contextvar"""
    return _request_context.get()


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware для установки request_id в каждом запросе.
    Это позволяет трассировать все операции в рамках одного запроса.
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
            # Добавляем request_id в заголовки ответа для отладки
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            
            return response
        finally:
            # Восстанавливаем предыдущее значение contextvar
            _request_context.reset(token)

