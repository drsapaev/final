"""
Централизованные обработчики исключений для FastAPI

Обеспечивает единообразную обработку ошибок во всем приложении.
"""

import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from app.core.pii_masker import (
    SECRET_FIELD_PATTERNS,
    is_sensitive_verification_path,
    mask_pii,
)
from app.services.emr_v2_service import EMRPatientContextMismatch
from app.services.queue_service import (
    QueueConflictError,
    QueueError,
    QueueNotFoundError,
    QueueValidationError,
)

logger = logging.getLogger(__name__)

# Bound the echoed "input" value of validation errors: the raw input can
# be arbitrarily large (e.g. a 64 KiB push credential) and used to be
# echoed verbatim into logs AND the 422 response.
_VALIDATION_INPUT_PREVIEW_LEN = 256


def _sanitize_validation_errors(
    errors: list,
    *,
    sensitive_verification: bool = False,
    sensitive_lab: bool = False,
) -> list:
    """Scrub rejected raw inputs out of RequestValidationError details.

    Pydantic v2 embeds the offending value under the "input" key of each
    error - a credential field (loc tail in SECRET_FIELD_PATTERNS) would
    leak its plaintext into logs and the 422 response, which no masker
    covers because the key is "input", not "token". Secret-tail inputs
    are fully redacted; other oversized inputs are truncated to a bounded
    preview; nested dict/list inputs go through mask_pii as usual.
    """
    sanitized: list = []
    for err in errors:
        if not isinstance(err, dict):
            sanitized.append(err)
            continue
        item = dict(err)
        if sensitive_verification:
            # These bodies carry one-time proofs or arbitrary SMS content.
            # A Pydantic error may attach a whole body or validator text.
            if "input" in item:
                item["input"] = "[REDACTED]"
            item["msg"] = "Invalid verification request"
            item.pop("ctx", None)
            sanitized.append(item)
            continue
        loc = item.get("loc") or ()
        if sensitive_lab:
            # Lab bodies carry free-text reasons and measurements. A
            # validation error must never echo the rejected specimen or
            # result, including an arbitrary key or custom error message.
            item.pop("input", None)
            item.pop("ctx", None)
            if item.get("type") in {
                "extra_forbidden", "value_error", "assertion_error", "invalid_key",
            }:
                item["loc"] = loc[:1]
                item["msg"] = "Invalid laboratory request"
            sanitized.append(item)
            continue
        loc_tail = str(loc[-1]).lower().replace("-", "_") if loc else ""
        if loc_tail in SECRET_FIELD_PATTERNS:
            if "input" in item:
                item["input"] = "[REDACTED]"
            item["msg"] = "Invalid sensitive value"
            item.pop("ctx", None)
            sanitized.append(item)
            continue
        if "input" in item:
            value = item["input"]
            if isinstance(value, (bytes, bytearray)):
                # PR-6 round 10 (codex P1): non-JSON content types hand
                # Pydantic the raw body as BYTES - decode it and let it
                # flow through the same scrub-and-bound string path, so a
                # form-encoded credential cannot reach the 422 response or
                # the warning log.
                value = bytes(value).decode("utf-8", errors="replace")
            if isinstance(value, str):
                # PR-6 round 9 (codex P2): scrub EVERY string input
                # before any length bound - a double-serialized body
                # arrives as a SHORT string whose embedded credential
                # would otherwise be echoed verbatim in the 422 (the
                # retained prefix of a long input could too).
                value = mask_pii(value)
                if len(value) > _VALIDATION_INPUT_PREVIEW_LEN:
                    item["input"] = (
                        value[:_VALIDATION_INPUT_PREVIEW_LEN] + "...[TRUNCATED]"
                    )
                else:
                    item["input"] = value
            elif isinstance(value, (dict, list)):
                item["input"] = mask_pii(value)
        sanitized.append(item)
    return sanitized


def _get_request_id(request: Request) -> str:
    """Получить request_id из state или сгенерировать новый"""
    return getattr(request.state, 'request_id', str(uuid.uuid4())[:8])


def register_exception_handlers(app: FastAPI) -> None:
    """
    Регистрирует все обработчики исключений в FastAPI приложении
    """

    @app.exception_handler(EMRPatientContextMismatch)
    async def emr_patient_context_mismatch(
        _request: Request, _exc: EMRPatientContextMismatch
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": {"code": "PATIENT_CONTEXT_CHANGED"}},
        )

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
        # Database exceptions may contain SQL, bind values, and driver details.
        logger.error("IntegrityError")

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
                "detail": detail,
            },
        )

    @app.exception_handler(OperationalError)
    async def operational_error_handler(
        request: Request, exc: OperationalError
    ) -> JSONResponse:
        """
        Обработка операционных ошибок БД (соединение, таймауты и т.д.)
        """
        # Database exceptions may contain SQL, bind values, and driver details.
        logger.error("OperationalError")
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
        # Database exceptions may contain SQL, bind values, and driver details.
        logger.error("SQLAlchemyError")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "database_error",
                "message": "Ошибка базы данных",
                "detail": "Ошибка базы данных",
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

        SECURITY (PR-6 round 2): exc.errors() embeds the rejected raw
        value under "input" - a credential field would leak its plaintext
        into logs and the 422 response. Sanitized before both uses.
        """
        safe_errors = _sanitize_validation_errors(
            exc.errors(),
            sensitive_verification=is_sensitive_verification_path(request.url.path),
            sensitive_lab=request.url.path.startswith("/api/v1/lab/"),
        )
        logger.warning(
            "RequestValidationError: %s (path: %s)",
            str(safe_errors),
            request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "validation_error",
                "message": "Ошибка валидации запроса",
                # exc.errors() can carry non-JSON-serializable objects in ctx
                # (e.g. the ValueError raised by a custom validator) - passing
                # it raw made JSONResponse itself raise, surfacing as a 500
                # from the security-middleware catch-all instead of a 422.
                "detail": jsonable_encoder(safe_errors),
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """
        Обработка всех остальных необработанных исключений

        SECURITY (CodeQL py/stack-trace-exposure #1175, #1176, and ~26
        downstream false-positive alerts): the previous implementation included
        `str(exc)` in the response body when `logger.level <= logging.DEBUG`.
        This created an info-leak vector: setting `LOG_LEVEL=DEBUG` (e.g. for
        troubleshooting) would cause ALL unhandled exceptions to surface their
        message to the client, including stack-trace fragments from
        SQLAlchemy, pg_dump, Jinja2, etc.

        Fix: never include exception details in the HTTP response, regardless
        of log level. The full exception (with stack trace) is logged
        server-side via `exc_info=True`; the client receives only a generic
        message and a `request_id` for cross-referencing with server logs.
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
                "detail": "Обратитесь к администратору",
            },
        )
