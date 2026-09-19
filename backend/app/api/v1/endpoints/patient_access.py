"""Patient portal access endpoints (Phase 0, PR-A1 + PR-A2).

Public, unauthenticated OTP foundation: request-otp / verify-otp / login.
PR-A2 adds the registrar-issued ACTIVATION flow: activate/request-otp +
activate/confirm (User(role=Patient) + UserProfile + Patient.user_id in
ONE atomic transaction).

Security properties (plan v3 acceptance):
- anti-enumeration on BOTH request-otp and verify-otp (uniform responses);
- canonical +998 normalization (single source: patient_otp_service);
- rate limits: IP (slowapi limiter, PR-34 convention) + normalized phone
  (Redis cooldown/hourly cap inside the service);
- OTP single-use, verification grant single-use;
- login resolver is fail-closed on ambiguous phone (never .first());
- activation OTP goes ONLY to the phone captured at token issuance —
  client-supplied phone numbers are never accepted (identity contract);
- Mock SMS forbidden outside TESTING; errors are number-neutral.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer  # noqa: F401 (docs parity, unused)
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.services.patient_activation_service import (
    ActivationError,
    get_patient_activation_service,
)
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


# --- PR-A2: registrar-issued activation flow -------------------------------


class PatientActivationOtpRequest(BaseModel):
    """Токен активации — БЕЗ поля phone: OTP отправляется только на номер,
    зафиксированный в карте при выпуске токена (identity contract v3)."""

    activation_token: str = Field(min_length=16, max_length=256)
    locale: str | None = None

    @field_validator("locale")
    @classmethod
    def _locale_whitelist(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in ("ru", "uz"):
            raise ValueError("Язык должен быть 'ru' или 'uz'")
        return v


class PatientActivationConfirmRequest(BaseModel):
    activation_token: str = Field(min_length=16, max_length=256)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class PatientActivationOtpResponse(BaseModel):
    success: bool
    phone_masked: str
    expires_in_minutes: int
    resend_after_seconds: int


class PatientActivationSessionUser(BaseModel):
    id: int
    username: str
    email: str | None
    full_name: str | None
    role: str
    is_active: bool
    is_superuser: bool


class PatientActivationConfirmResponse(BaseModel):
    access_token: str
    token_type: str
    user: PatientActivationSessionUser
    patient_id: int


@router.post(
    "/activate/request-otp",
    response_model=PatientActivationOtpResponse,
)
@limiter.limit("5/minute")
async def request_activation_otp(
    request: Request,
    payload: PatientActivationOtpRequest,
    db: Session = Depends(get_db),
):
    """Отправить OTP для активации доступа.

    OTP уходит ТОЛЬКО на номер карты, привязанный к токену при выпуске.
    Ответ маскирует номер и не содержит PHI."""
    try:
        result = await get_patient_activation_service().request_activation_otp(
            db, payload.activation_token, payload.locale
        )
    except ActivationError as err:
        raise _activation_http_error(err) from err
    return {"success": True, **result}


@router.post(
    "/activate/confirm",
    response_model=PatientActivationConfirmResponse,
)
@limiter.limit("10/minute")
async def confirm_activation(
    request: Request,
    payload: PatientActivationConfirmRequest,
    db: Session = Depends(get_db),
):
    """Токен + OTP -> каноническая сессия User(role=Patient).

    Атомарно: User + UserProfile(phone, verified) + Patient.user_id в одной
    транзакции (SELECT FOR UPDATE + один commit). Все отказы — единый
    generic текст (anti-enum)."""
    try:
        return get_patient_activation_service().activate(
            db, payload.activation_token, payload.code
        )
    except ActivationError as err:
        raise _activation_http_error(err) from err


def _http_error(err: PatientOtpError):
    from fastapi import HTTPException

    return HTTPException(status_code=err.status_code, detail=err.detail)


def _activation_http_error(err: ActivationError):
    from fastapi import HTTPException

    return HTTPException(status_code=err.status_code, detail=err.detail)


# Re-export for readability of handlers above
_ = (ERR_LOGIN_GENERIC, ERR_OTP_INVALID, ERR_RATE_LIMITED)
