"""
Централизованные обработчики исключений для FastAPI

Обеспечивает единообразную обработку ошибок во всем приложении.
"""

import logging
import uuid
from typing import Union

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from app.services.queue_service import (
    QueueConflictError,
    QueueError,
    QueueNotFoundError,
    QueueValidationError,
)

logger = logging.getLogger(__name__)


def _get_request_id(request: Request) -> str:
    """Получить request_id из state или сгенерировать новый"""
    return getattr(request.state, 'request_id', str(uuid.uuid4())[:8])


def register_exception_handlers(app: FastAPI) -> None:
    """
    Регистрирует все обработчики исключений в FastAPI приложении
    """

    @app.exception_handler(QueueValidationError)
    async def queue_validation_error_handler(
        request: Request, exc: QueueValidationError
    ) -> JSONResponse:
        """
        Обработка ошибок валидации очереди
        """
        logger.warning(
            "QueueValidationError: %s (path: %s)",
            str(exc),
            request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "queue_validation_error",
                "message": str(exc),
                "detail": "Ошибка валидации данных очереди",
            },
        )

    @app.exception_handler(QueueConflictError)
    async def queue_conflict_error_handler(
        request: Request, exc: QueueConflictError
    ) -> JSONResponse:
        """
        Обработка конфликтов в очереди (дубликаты, лимиты)
        """
        logger.warning(
            "QueueConflictError: %s (path: %s)",
            str(exc),
            request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "queue_conflict_error",
                "message": str(exc),
                "detail": "Конфликт в очереди (дубликат, лимит или блокировка)",
            },
        )

    @app.exception_handler(QueueNotFoundError)
    async def queue_not_found_error_handler(
        request: Request, exc: QueueNotFoundError
    ) -> JSONResponse:
        """
        Обработка ошибок "очередь не найдена"
        """
        logger.warning(
            "QueueNotFoundError: %s (path: %s)",
            str(exc),
            request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "queue_not_found_error",
                "message": str(exc),
                "detail": "Очередь или запись не найдена",
            },
        )

    @app.exception_handler(QueueError)
    async def queue_error_handler(request: Request, exc: QueueError) -> JSONResponse:
        """
        Обработка общих ошибок очереди
        """
        logger.error(
            "QueueError: %s (path: %s)",
            str(exc),
            request.url.path,
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "queue_error",
                "message": str(exc),
                "detail": "Ошибка при работе с очередью",
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(
        request: Request, exc: IntegrityError
    ) -> JSONResponse:
        """
        Обработка ошибок целостности БД (UNIQUE, FOREIGN KEY и т.д.)
        """
        logger.error(
            "IntegrityError: %s (path: %s)",
            str(exc),
            request.url.path,
            exc_info=True,
        )

        # Пытаемся извлечь понятное сообщение из ошибки
        error_msg = str(exc.orig) if hasattr(exc, 'orig') else str(exc)
        if "UNIQUE constraint" in error_msg:
            detail = "Нарушение уникальности данных"
        elif "FOREIGN KEY constraint" in error_msg:
            detail = "Нарушение ссылочной целостности"
        else:
            detail = "Ошибка целостности данных"

        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": "integrity_error",
                "message": detail,
                "detail": error_msg,
            },
        )

    @app.exception_handler(OperationalError)
    async def operational_error_handler(
        request: Request, exc: OperationalError
    ) -> JSONResponse:
        """
        Обработка операционных ошибок БД (соединение, таймауты и т.д.)
        """
        logger.error(
            "OperationalError: %s (path: %s)",
            str(exc),
            request.url.path,
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "database_operational_error",
                "message": "Ошибка подключения к базе данных",
                "detail": "Попробуйте позже",
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(
        request: Request, exc: SQLAlchemyError
    ) -> JSONResponse:
        """
        Обработка общих ошибок SQLAlchemy
        """
        logger.error(
            "SQLAlchemyError: %s (path: %s)",
            str(exc),
            request.url.path,
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "database_error",
                "message": "Ошибка базы данных",
                "detail": str(exc),
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """
        Обработка ошибок валидации значений
        """
        logger.warning(
            "ValueError: %s (path: %s)",
            str(exc),
            request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "validation_error",
                "message": str(exc),
                "detail": "Некорректное значение параметра",
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        Обработка ошибок валидации Pydantic (автоматически вызывается FastAPI)
        """
        logger.warning(
            "RequestValidationError: %s (path: %s)",
            str(exc.errors()),
            request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "validation_error",
                "message": "Ошибка валидации запроса",
                "detail": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """
        Обработка всех остальных необработанных исключений
        """
        request_id = _get_request_id(request)
        logger.error(
            "[%s] Unhandled exception: %s: %s (path: %s)",
            request_id,
            type(exc).__name__,
            str(exc),
            request.url.path,
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_server_error",
                "message": "Внутренняя ошибка сервера",
                "request_id": request_id,
                "detail": (
                    str(exc)
                    if logger.level <= logging.DEBUG
                    else "Обратитесь к администратору"
                ),
            },
        )
