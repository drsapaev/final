"""PR-6: Push device registry endpoints — canonical multi-device store.

Scope guard (owner directive): this surface REGISTERS credentials only.
It does NOT activate any push channel — FCM_ENABLED stays off, no VAPID
keys, Telegram/SMS untouched, no topics. Activation is a separate product
decision (Android FCM pilot) that follows the registry.

Security posture:

- Every route is scoped to ``current_user`` — a foreign device id degrades
  to 404, never to a mutation (no cross-user disable/delete).
- No token/endpoint value is ever echoed: responses carry a SHA-256
  fingerprint only, so nothing can leak into logs or Sentry.
- Device-level operations never write ``users.push_notifications_enabled``
  (the user-level master opt-out) — only registration sets it (explicit
  consent), matching the legacy /fcm/register-token semantics.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.push_devices import (
    PushDeviceListResponse,
    PushDeviceMutationResponse,
    PushDeviceOut,
    PushDeviceRegisterRequest,
    PushDeviceRegisterResponse,
)
from app.services import push_device_registry as registry

router = APIRouter()


@router.post("/register", response_model=PushDeviceRegisterResponse)
@limiter.limit(
    "30/minute"
)  # client-initiated, keyed by client IP (PR-34): clinics behind shared egress need headroom for distinct users
async def register_push_device(
    request: Request,
    payload: PushDeviceRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register/refresh a push credential for ONE device (idempotent).

    - Same credential re-sent → refresh (last_seen_at), no duplicate.
    - New token for a known device_id → rotation (old row invalidated).
    - Credential registered by another account → moves to this account.
    - provider="fcm" additionally mirrors into the DEPRECATED
      users.device_token column so every legacy sender keeps working.
    """
    try:
        device, created = registry.register_user_device(
            db,
            user=current_user,
            provider=payload.provider,
            platform=payload.platform,
            token=payload.token,
            device_id=payload.device_id,
            credential=payload.credential,
        )
        return PushDeviceRegisterResponse(
            success=True,
            created=created,
            message=(
                "Устройство зарегистрировано" if created else "Регистрация обновлена"
            ),
            device=PushDeviceOut(**registry.redact_device(device)),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("", response_model=PushDeviceListResponse)
def list_push_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the caller's own devices (including disabled/invalidated
    history rows). Credentials are never returned — fingerprints only."""
    try:
        devices = registry.list_user_devices(db, user=current_user)
        return PushDeviceListResponse(
            devices=[PushDeviceOut(**registry.redact_device(d)) for d in devices],
            total_count=len(devices),
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/{device_id}/disable", response_model=PushDeviceMutationResponse)
def disable_push_device(
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Logout ONE device: device-level ``enabled = False``. Other devices
    and the user-level master opt-out are untouched. The legacy mirror is
    cleared only when it points at exactly this credential."""
    try:
        if not registry.disable_user_device(
            db, user=current_user, device_row_id=device_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
            )
        return PushDeviceMutationResponse(success=True, message="Устройство отключено")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/{device_id}/enable", response_model=PushDeviceMutationResponse)
def enable_push_device(
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-enable ONE device. An invalidated (dead) credential cannot be
    revived — only a fresh registration returns it (409)."""
    try:
        if not registry.enable_user_device(
            db, user=current_user, device_row_id=device_id
        ):
            device_exists = registry.get_user_device(
                db, user=current_user, device_row_id=device_id
            )
            if device_exists is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Credential invalidated — register the device again",
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
            )
        return PushDeviceMutationResponse(success=True, message="Устройство включено")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete("/{device_id}", response_model=PushDeviceMutationResponse)
def delete_push_device(
    device_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Hard-delete ONE own device row (full logout with credential
    removal). Foreign device ids are 404 — never a cross-user deletion."""
    try:
        if not registry.delete_user_device(
            db, user=current_user, device_row_id=device_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
            )
        return PushDeviceMutationResponse(success=True, message="Устройство удалено")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )
