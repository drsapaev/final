"""PR-6: push device registry endpoints — canonical multi-device store.

This surface maintains the registry ONLY. It does not activate FCM or
Web Push sending: ``FCM_ENABLED`` stays off, no VAPID keys are added,
and no sender reads the registry yet (the first consumer is the Android
FCM pilot that follows this PR). The legacy single-device column
``users.device_token`` and the legacy ``/fcm`` endpoints are untouched:
new code paths here never read or write them.

Token hygiene: request credentials are never echoed back, never logged,
never reported to Sentry. Responses carry ``token_fingerprint`` (a
non-secret SHA-256 prefix) instead of the credential.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import AfterValidator, BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limiter import RATE_LIMITS, get_client_ip, limiter
from app.db.session import get_db
from app.models.user import User
from app.services import push_device_registry as registry

router = APIRouter()


def _user_throttle_key(request: Request) -> str:
    # PR-6 round 12 (codex P2): key the registration throttle by the
    # AUTHENTICATED identity (hash of the bearer credential ≈ per user),
    # not by client IP — clinic staff/patients share one egress address,
    # and an IP-keyed limit aggregates unrelated users into one bucket.
    # The hash keeps the raw credential out of limiter keys. Requests
    # without a bearer header (they fail auth anyway) fall back to the
    # client IP, preserving an abuse bound.
    auth = request.headers.get("Authorization", "")
    if auth:
        return "push-user:" + hashlib.sha256(auth.encode()).hexdigest()[:32]
    return get_client_ip(request)


def _strip_credential(value: str) -> str:
    # PR-6 round 4 (codex P2): normalize at the request-schema boundary —
    # a whitespace-only credential passes min_length=1 but would become
    # the SHA-256 identity of a registry row. Blank after strip -> 422.
    value = value.strip()
    if not value:
        raise ValueError("credential must not be blank")
    return value


# Bounded credential string: strip + non-blank AFTER the length bounds.
# The strip also matches the service contract ("client statement is
# authoritative" applies to the stripped value).
CredentialStr = Annotated[
    str, Field(min_length=1, max_length=65536), AfterValidator(_strip_credential)
]


class PushDeviceRegisterRequest(BaseModel):
    provider: Literal["fcm", "webpush"]
    platform: Literal["android", "web"]
    token: CredentialStr
    # App-generated stable per-install identifier; optional for web.
    device_id: str | None = Field(default=None, max_length=128)
    # Explicit rotation: the credential this one replaces, if known.
    previous_token: CredentialStr | None = None


class PushDeviceRefreshRequest(BaseModel):
    token: CredentialStr


class PushDeviceUnregisterByToken(BaseModel):
    """Logout variant 1: identify the device by its credential."""

    token: CredentialStr
    # App-generated stable per-install identifier (optional in this variant).
    device_id: str | None = Field(default=None, max_length=128)


class PushDeviceUnregisterByDeviceId(BaseModel):
    """Logout variant 2: identify the device by its install identifier."""

    token: CredentialStr | None = None
    device_id: str = Field(max_length=128)


# Round 9 (codex P2): the union is expressed as two CONCRETE request models
# (a real anyOf of object schemas), so the committed OpenAPI and the
# generated TypeScript carry the at-least-one contract without an
# unconstrained base member; runtime validation returns the wrapped 422.
PushDeviceUnregisterRequest = Annotated[
    PushDeviceUnregisterByToken | PushDeviceUnregisterByDeviceId,
    Field(description="token или device_id — хотя бы одно; оба → пересечение"),
]


class PushDeviceErrorDetail(BaseModel):
    """Body of HTTPException errors on this surface: ``{"detail": ...}``."""

    detail: str


class PushDeviceRateLimitDetail(BaseModel):
    """Body of the 429 rate-limit response on this surface."""

    detail: str
    retry_after: int | None = None


class PushDeviceValidationError(BaseModel):
    """Wrapped validation-error body produced by the global handler."""

    error: str
    message: str
    detail: list[dict[str, Any]]


class PushDeviceRefreshResponse(BaseModel):
    # PR-6 round 4b (codex P2): named response models publish the actual
    # payload in OpenAPI — dict[str, bool] would expose only an index
    # signature to generated clients.
    refreshed: bool


class PushDeviceUnregisterResponse(BaseModel):
    disabled: int


class PushDeviceToggleRequest(BaseModel):
    enabled: bool


class PushDeviceOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    # PR-6 round 5 (codex P2): the DB CHECK constrains these two columns
    # to the request enums — publish the same literals in the response
    # schema instead of plain strings so generated clients keep the
    # canonical enum contract.
    provider: Literal["fcm", "webpush"]
    platform: Literal["android", "web"]
    device_id: str | None
    enabled: bool
    token_fingerprint: str
    last_seen_at: datetime | None
    invalidated_at: datetime | None
    created_at: datetime | None


class PushDeviceListResponse(BaseModel):
    devices: list[PushDeviceOut]
    total_count: int


@router.post(
    "/register",
    response_model=PushDeviceOut,
    responses={
        409: {
            "model": PushDeviceErrorDetail,
            "description": "Пер-юзер квота живых push-устройств исчерпана",
        },
        422: {
            "model": PushDeviceValidationError,
            "description": "Ошибки валидации запроса (обёртка error/message/detail)",
        },
        429: {
            "model": PushDeviceRateLimitDetail,
            "description": "Превышен лимит частоты регистраций",
            "headers": {
                "Retry-After": {
                    "description": "Секунды до повторной попытки",
                    "schema": {"type": "integer"},
                }
            },
        },
    },
)
@limiter.limit(
    RATE_LIMITS["push_register"],
    key_func=_user_throttle_key,
)  # registration writes a 64 KiB TOAST value per request — endpoint throttle per PR-6 round 6 codex P1, keyed per authenticated user so clinic shared egress does not aggregate unrelated users (round 12)
def register_push_device(
    request: Request,
    payload: PushDeviceRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register (or idempotently refresh) a push device credential."""
    try:
        device = registry.register_device(
            db,
            user_id=current_user.id,
            provider=payload.provider,
            platform=payload.platform,
            token=payload.token,
            device_id=payload.device_id,
            previous_token=payload.previous_token,
        )
    except registry.PushDeviceQuotaExceeded:
        # PR-6 round 4 (codex P1): per-user live-slot quota — the client
        # must explicitly retire a device before registering a new one.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Достигнут лимит зарегистрированных push-устройств — "
                "удалите одно из устройств перед регистрацией нового"
            ),
        )
    return device


@router.post(
    "/refresh",
    response_model=PushDeviceRefreshResponse,
    responses={
        404: {
            "model": PushDeviceErrorDetail,
            "description": "Устройство не найдено или credential инвалидирован",
        },
        422: {
            "model": PushDeviceValidationError,
            "description": "Ошибки валидации запроса (обёртка error/message/detail)",
        },
    },
)
def refresh_push_device(
    request: Request,
    payload: PushDeviceRefreshRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Heartbeat from an already-registered device (bumps last_seen_at)."""
    ok = registry.refresh_device(db, user_id=current_user.id, token=payload.token)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Устройство не найдено или токен недействителен",
        )
    return {"refreshed": True}


@router.post(
    "/unregister",
    response_model=PushDeviceUnregisterResponse,
    responses={
        422: {
            "model": PushDeviceValidationError,
            "description": "Ошибки валидации запроса (обёртка error/message/detail)",
        },
    },
)
def unregister_push_device(
    request: Request,
    payload: PushDeviceUnregisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retire the matching device(s) of the current user (single logout)."""
    disabled = registry.unregister_devices(
        db,
        user_id=current_user.id,
        token=payload.token,
        device_id=payload.device_id,
    )
    return {"disabled": disabled}


@router.get("", response_model=PushDeviceListResponse)
def list_push_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the current user's registered push devices (no credentials)."""
    devices = registry.list_devices(db, user_id=current_user.id)
    return {
        "devices": [PushDeviceOut.model_validate(d) for d in devices],
        "total_count": len(devices),
    }


@router.post(
    "/{device_row_id}/toggle",
    response_model=PushDeviceOut,
    responses={
        404: {
            "model": PushDeviceErrorDetail,
            "description": "Устройство не найдено (или принадлежит другому пользователю)",
        },
        422: {
            "model": PushDeviceValidationError,
            "description": "Ошибки валидации запроса (обёртка error/message/detail)",
        },
    },
)
def toggle_push_device(
    request: Request,
    device_row_id: int,
    payload: PushDeviceToggleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle the device-level switch; other devices stay untouched."""
    device = registry.set_device_enabled(
        db,
        user_id=current_user.id,
        device_row_id=device_row_id,
        enabled=payload.enabled,
    )
    if device is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Устройство не найдено",
        )
    return device
