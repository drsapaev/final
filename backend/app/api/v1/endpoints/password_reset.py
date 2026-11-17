"""
API endpoints для восстановления паролей
"""

import logging
import re
from datetime import datetime
from typing import Any, Literal, NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.api.deps import require_roles
from app.core.rate_limiter import get_client_ip, limiter
from app.db.session import get_db
from app.models.user import User
from app.services.password_reset_service import get_password_reset_service
from app.services.phone_verification_store import PhoneStoreUnavailable

router = APIRouter()
logger = logging.getLogger(__name__)


def raise_password_reset_internal_error(
    action: str, exc: Exception, *, headers: dict[str, str] | None = None
) -> NoReturn:
    logger.error(
        "Password reset endpoint failed action=%s error_type=%s",
        action,
        type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
        headers=headers,
    ) from exc


class PasswordResetInitiateRequest(BaseModel):
    """Запрос на инициацию сброса пароля"""

    phone: str | None = None
    email: str | None = None

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        phone = re.sub(r'[^\d+]', '', v)
        if not re.fullmatch(r'\+998[0-9]{9}', phone):
            raise ValueError('Номер телефона должен быть в формате +998XXXXXXXXX')
        return phone

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', v):
            raise ValueError('Неверный формат email адреса')
        return v

    @model_validator(mode='after')
    def validate_contact_provided(self):
        if not self.email and not self.phone:
            raise ValueError('Необходимо указать номер телефона или email')
        if self.email and self.phone:
            raise ValueError('Укажите только один способ связи: телефон или email')
        return self


class PhoneVerificationRequest(BaseModel):
    """Запрос на верификацию телефона для сброса пароля"""

    phone: str
    verification_code: str

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        phone = re.sub(r'[^\d+]', '', v)
        if not re.fullmatch(r'\+998[0-9]{9}', phone):
            raise ValueError('Номер телефона должен быть в формате +998XXXXXXXXX')
        return phone

    @field_validator('verification_code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not re.fullmatch(r'[0-9]{6}', v):
            raise ValueError('Код должен состоять из 6 цифр')
        return v


class PasswordResetConfirmRequest(BaseModel):
    """Запрос на подтверждение сброса пароля"""

    token: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Пароль должен содержать минимум 8 символов')
        return v


class PhoneResetVerificationResponse(BaseModel):
    success: Literal[True]
    message: str
    reset_token: str
    expires_in_hours: int


class PhoneResetVerificationFailure(BaseModel):
    success: Literal[False]
    error: str
    error_code: str | None = None
    attempts_left: int | None = None


class PhoneResetErrorResponse(BaseModel):
    detail: str | PhoneResetVerificationFailure


class PhoneResetValidationResponse(BaseModel):
    error: str
    message: str
    detail: list[dict[str, Any]]


class ResetTokenErrorResponse(BaseModel):
    detail: str


@router.post("/initiate", response_model=dict[str, Any])  # P1-1: rate limit deferred (request param conflict)
@limiter.limit("3/minute")  # P1-1: rate limit
async def initiate_password_reset(request: Request,
    request_data: PasswordResetInitiateRequest, db: Session = Depends(get_db)
):
    """Инициация сброса пароля"""
    try:
        password_reset_service = get_password_reset_service()

        if request_data.phone:
            result = await password_reset_service.initiate_phone_reset(
                db=db, phone=request_data.phone
            )
        else:
            result = await password_reset_service.initiate_email_reset(
                db=db, email=request_data.email
            )

        if result["success"]:
            response_data = {"success": True, "message": result["message"]}

            # Добавляем дополнительную информацию если есть
            if "expires_in_minutes" in result:
                response_data["expires_in_minutes"] = result["expires_in_minutes"]
            if "expires_in_hours" in result:
                response_data["expires_in_hours"] = result["expires_in_hours"]

            return response_data
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            if result.get("error_code") == "RATE_LIMITED":
                status_code = status.HTTP_429_TOO_MANY_REQUESTS
            elif result.get("error_code") == "EMAIL_SEND_FAILED":
                status_code = status.HTTP_502_BAD_GATEWAY

            raise HTTPException(status_code=status_code, detail=result["error"])

    except HTTPException:
        raise
    except Exception as e:
        raise_password_reset_internal_error("initiate_password_reset", e)


@router.post(
    "/verify-phone",
    response_model=PhoneResetVerificationResponse,
    responses={
        200: {"headers": {"Cache-Control": {"description": "Sensitive response is not cacheable", "schema": {"type": "string"}}}},
        **{code: {"model": PhoneResetErrorResponse, "description": "Verification rejected"}
           for code in (400, 404, 410, 429, 500, 503)},
        422: {"model": PhoneResetValidationResponse, "description": "Invalid verification request"},
    },
)
async def verify_phone_for_reset(
    request: Request, response: Response, request_data: PhoneVerificationRequest,
    db: Session = Depends(get_db)
):
    """Верификация телефона для сброса пароля"""
    try:
        password_reset_service = get_password_reset_service()

        # This shared budget is charged before looking up the supplied phone,
        # so both unknown and known numbers have the same IP-level behavior.
        try:
            allowed = await run_in_threadpool(
                password_reset_service.phone_verification.consume_ip_verify_budget,
                get_client_ip(request),
            )
        except PhoneStoreUnavailable as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Verification temporarily unavailable", headers={"Cache-Control": "no-store"}) from exc
        if not allowed:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many verification attempts", headers={"Cache-Control": "no-store"})

        result = await password_reset_service.verify_phone_and_get_token(
            db=db, phone=request_data.phone, verification_code=request_data.verification_code
        )

        if result["success"]:
            response.headers["Cache-Control"] = "no-store"
            return {
                "success": True,
                "message": result["message"],
                "reset_token": result["reset_token"],
                "expires_in_hours": result["expires_in_hours"],
            }
        else:
            status_code = status.HTTP_400_BAD_REQUEST
            if result.get("error_code") == "INTERNAL_ERROR":
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            elif result.get("error_code") == "CODE_NOT_FOUND":
                status_code = status.HTTP_404_NOT_FOUND
            elif result.get("error_code") == "CODE_EXPIRED":
                status_code = status.HTTP_410_GONE
            elif result.get("error_code") == "MAX_ATTEMPTS_EXCEEDED":
                status_code = status.HTTP_429_TOO_MANY_REQUESTS
            elif result.get("error_code") == "USER_NOT_FOUND":
                status_code = status.HTTP_404_NOT_FOUND

            response_data = {
                "success": False,
                "error": result["error"],
                "error_code": result.get("error_code"),
            }

            if "attempts_left" in result:
                response_data["attempts_left"] = result["attempts_left"]

            raise HTTPException(status_code=status_code, detail=response_data, headers={"Cache-Control": "no-store"})

    except HTTPException:
        raise
    except Exception as e:
        raise_password_reset_internal_error("verify_phone_for_reset", e, headers={"Cache-Control": "no-store"})


@router.post("/confirm", response_model=dict[str, Any])
async def confirm_password_reset(
    request_data: PasswordResetConfirmRequest, db: Session = Depends(get_db)
):
    """Подтверждение сброса пароля"""
    try:
        password_reset_service = get_password_reset_service()

        result = password_reset_service.reset_password_with_token(
            db=db, token=request_data.token, new_password=request_data.new_password
        )

        if result["success"]:
            return {"success": True, "message": result["message"]}
        else:
            status_code = status.HTTP_400_BAD_REQUEST
            if result.get("error_code") == "TOKEN_NOT_FOUND":
                status_code = status.HTTP_404_NOT_FOUND
            elif result.get("error_code") == "TOKEN_EXPIRED":
                status_code = status.HTTP_410_GONE
            elif result.get("error_code") == "TOKEN_ALREADY_USED":
                status_code = status.HTTP_409_CONFLICT
            elif result.get("error_code") == "USER_NOT_FOUND":
                status_code = status.HTTP_404_NOT_FOUND
            elif result.get("error_code") == "PASSWORD_UPDATE_FAILED":
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

            raise HTTPException(status_code=status_code, detail=result["error"])

    except HTTPException:
        raise
    except Exception as e:
        raise_password_reset_internal_error("confirm_password_reset", e)


@router.get(
    "/validate-token",
    response_model=dict[str, Any],
    responses={
        200: {"headers": {"Cache-Control": {"description": "Sensitive response is not cacheable", "schema": {"type": "string"}}}},
        400: {"model": ResetTokenErrorResponse, "description": "Missing or ambiguous token"},
        404: {"model": ResetTokenErrorResponse, "description": "Token not found"},
        409: {"model": ResetTokenErrorResponse, "description": "Token already used"},
        410: {"model": ResetTokenErrorResponse, "description": "Token expired"},
        500: {"model": ResetTokenErrorResponse, "description": "Internal server error"},
        503: {"model": ResetTokenErrorResponse, "description": "Validation temporarily unavailable"},
    },
)
async def validate_reset_token(
    request: Request,
    response: Response,
    token: str | None = Query(None, description="Legacy reset token transport", deprecated=True),
    x_reset_token: str | None = Header(None, alias="X-Reset-Token", description="Reset token"),
    db: Session = Depends(get_db),
):
    """Validate a reset token; query transport is retained for older clients."""
    no_store = {"Cache-Control": "no-store"}
    response.headers.update(no_store)
    # Reject ambiguity rather than picking an attacker-controlled duplicate or
    # silently preferring a query credential over the secure header.
    query_values = request.query_params.getlist("token")
    header_values = request.headers.getlist("x-reset-token")
    if len(query_values) + len(header_values) != 1:
        raise HTTPException(status_code=400, detail="Provide one reset token", headers=no_store)
    reset_token = x_reset_token if header_values else token
    if not reset_token:
        raise HTTPException(status_code=400, detail="Provide one reset token", headers=no_store)
    try:
        password_reset_service = get_password_reset_service()

        result = password_reset_service.validate_reset_token(db, reset_token)

        if result["valid"]:
            return {
                "valid": True,
                "expires_at": result["expires_at"],
                "time_left_minutes": result["time_left_minutes"],
            }
        else:
            status_code = status.HTTP_400_BAD_REQUEST
            if result.get("error_code") == "TOKEN_NOT_FOUND":
                status_code = status.HTTP_404_NOT_FOUND
            elif result.get("error_code") == "TOKEN_EXPIRED":
                status_code = status.HTTP_410_GONE
            elif result.get("error_code") == "TOKEN_ALREADY_USED":
                status_code = status.HTTP_409_CONFLICT
            elif result.get("error_code") == "INTERNAL_ERROR":
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE

            raise HTTPException(status_code=status_code, detail=result["error"], headers=no_store)

    except HTTPException:
        raise
    except Exception as e:
        raise_password_reset_internal_error("validate_reset_token", e, headers=no_store)


@router.get("/statistics", response_model=dict[str, Any])
async def get_password_reset_statistics(
    current_user: User = Depends(require_roles(["Admin", "SuperAdmin"])),
    db: Session = Depends(get_db),
):
    """Статистика сброса паролей (только для администраторов)"""
    try:
        password_reset_service = get_password_reset_service()

        stats = password_reset_service.get_statistics(db)

        return {"statistics": stats, "timestamp": datetime.now().isoformat()}

    except Exception as e:
        raise_password_reset_internal_error("get_password_reset_statistics", e)
