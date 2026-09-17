"""Patient portal access endpoints (Phase 0, PR-A1).

Public, unauthenticated OTP foundation: request-otp / verify-otp / login.
NO patient linking lives here (identity contract: phone is possession,
not identity — linking is PR-A2 via registrar-issued activation tokens).

Security properties (plan v3 acceptance):
- anti-enumeration on BOTH request-otp and verify-otp (uniform responses);
- canonical +998 normalization (single source: patient_otp_service);
- rate limits: IP (slowapi limiter, PR-34 convention) + normalized phone
  (Redis cooldown/hourly cap inside the service);
- OTP single-use, verification grant single-use;
- login resolver is fail-closed on ambiguous phone (never .first());
- Mock SMS forbidden outside TESTING; errors are number-neutral.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer  # noqa: F401 (docs parity, unused)
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.services.patient_otp_service import (
    ERR_LOGIN_GENERIC,
    ERR_OTP_INVALID,
    ERR_RATE_LIMITED,
    ERR_SMS_UNAVAILABLE,
    PatientOtpError,
    get_patient_otp_service,
)

router = APIRouter()

_PHONE_CLEAN_RE = re.compile(r"[^\d+]")


def _clean_phone(v: str) -> str:
    return _PHONE_CLEAN_RE.sub("", v or "")


class PatientOtpRequest(BaseModel):
    phone: str
    locale: str | None = None

    @field_validator("phone")
    @classmethod
    def _phone_format(cls, v: str) -> str:
        cleaned = _clean_phone(v)
        if not re.fullmatch(r"\+998\d{9}", cleaned):
            raise ValueError("Номер телефона должен быть в формате +998XXXXXXXXX")
        return cleaned

    @field_validator("locale")
    @classmethod
    def _locale_whitelist(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in ("ru", "uz"):
            raise ValueError("Язык должен быть 'ru' или 'uz'")
        return v


class PatientOtpVerifyRequest(BaseModel):
    phone: str
    code: str

    @field_validator("phone")
    @classmethod
    def _phone_format(cls, v: str) -> str:
        cleaned = _clean_phone(v)
        if not re.fullmatch(r"\+998\d{9}", cleaned):
            raise ValueError("Номер телефона должен быть в формате +998XXXXXXXXX")
        return cleaned

    @field_validator("code")
    @classmethod
    def _code_format(cls, v: str) -> str:
        if not re.fullmatch(r"\d{6}", v or ""):
            raise ValueError("Код должен состоять из 6 цифр")
        return v


class PatientLoginRequest(BaseModel):
    phone: str
    verification_grant: str

    @field_validator("phone")
    @classmethod
    def _phone_format(cls, v: str) -> str:
        cleaned = _clean_phone(v)
        if not re.fullmatch(r"\+998\d{9}", cleaned):
            raise ValueError("Номер телефона должен быть в формате +998XXXXXXXXX")
        return cleaned

    @field_validator("verification_grant")
    @classmethod
    def _grant_format(cls, v: str) -> str:
        if not v or not (16 <= len(v) <= 128):
            raise ValueError("Некорректный verification_grant")
        return v


@router.post("/request-otp", response_model=dict[str, Any])
@limiter.limit("5/minute")
async def request_patient_otp(request: Request, payload: PatientOtpRequest):
    """Отправить OTP для входа пациента. Ответ номер-нейтрален (anti-enum)."""
    try:
        await get_patient_otp_service().send_login_otp(payload.phone, payload.locale)
    except PatientOtpError as err:
        raise _http_error(err) from err
    return {
        "success": True,
        "message": ERR_SMS_UNAVAILABLE
        if False
        else ("Если номер обслуживается в клинике, код входа отправлен"),
        "expires_in_minutes": 5,
        "resend_after_seconds": 60,
    }


@router.post("/verify-otp", response_model=dict[str, Any])
@limiter.limit("10/minute")
async def verify_patient_otp(request: Request, payload: PatientOtpVerifyRequest):
    """Проверить OTP -> одноразовый verification_grant (единый ответ при любой неудаче)."""
    try:
        result = get_patient_otp_service().verify_login_otp(payload.phone, payload.code)
    except PatientOtpError as err:
        raise _http_error(err) from err
    return {"success": True, **result}


@router.post("/login", response_model=dict[str, Any])
@limiter.limit("10/minute")
async def patient_login(
    request: Request, payload: PatientLoginRequest, db: Session = Depends(get_db)
):
    """phone + verification_grant -> JWT канонического User(role=Patient).

    Fail-closed: 0 или >1 активных verified Patient-пользователей на номер ->
    единый generic 401 (endpoint не становится каталогом пациентов)."""
    try:
        return get_patient_otp_service().login_with_grant(
            db, payload.phone, payload.verification_grant
        )
    except PatientOtpError as err:
        raise _http_error(err) from err


def _http_error(err: PatientOtpError):
    from fastapi import HTTPException

    return HTTPException(status_code=err.status_code, detail=err.detail)


# Re-export for readability of handlers above
_ = (ERR_LOGIN_GENERIC, ERR_OTP_INVALID, ERR_RATE_LIMITED)
