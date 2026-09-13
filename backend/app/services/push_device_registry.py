"""PR-6: Push device registry service — multi-device truth + legacy mirror.

Transitional contract (ONE, explicit — chosen per owner's directive):

- The REGISTRY (``push_devices``) is the canonical multi-device store.
- The legacy single-device column ``users.device_token`` is KEPT and acts
  as a MIRROR: every FCM registration writes the credential there too, so
  every existing sender (notifications facade, mobile_service_enhanced,
  admin broadcasts, queue position pushes) continues to work unchanged —
  "last FCM registration wins" in the legacy world, full multi-device
  truth in the registry.
- The mirror is marked DEPRECATED at the write sites: the Android FCM
  pilot (after census) switches senders to the registry, and the
  destructive legacy-column migration is a SEPARATE next PR.
- Web Push registrations (provider="webpush") NEVER touch the legacy FCM
  column — a subscription is not squeezed into the FCM-token format.

Security posture: no token/endpoint value is ever logged, returned in a
response, or propagated to error trackers. Responses carry only a short
SHA-256 fingerprint (not reversible).
"""

from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app.crud import push_device as crud_push_device, user as crud_user
from app.models.push_device import PushDevice
from app.models.user import User

# Bound for the SHA-256 prefix used to distinguish devices without
# revealing credentials.
FINGERPRINT_LENGTH = 12


def fingerprint(token: str) -> str:
    """Short non-reversible fingerprint of a credential (for UI lists)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:FINGERPRINT_LENGTH]


def register_user_device(
    db: Session,
    *,
    user: User,
    provider: str,
    platform: str,
    token: str,
    device_id: str | None = None,
    credential: dict | None = None,
) -> tuple[PushDevice, bool]:
    """Register a device in the canonical registry + maintain the mirror.

    Registering a device is an explicit push consent on the user level —
    it sets ``push_notifications_enabled = True`` (same opt-in semantics
    as the legacy /fcm/register-token endpoint). Disabling/removing ONE
    device NEVER flips that flag back: the master opt-out belongs to
    explicit user intent, not to device lifecycle.
    """
    device, created = crud_push_device.register_device(
        db,
        user_id=user.id,
        provider=provider,
        platform=platform,
        token=token,
        device_id=device_id,
        credential=credential,
    )

    if provider == "fcm":
        # DEPRECATED mirror (see module docstring): keeps every legacy
        # sender working until the pilot moves them onto the registry.
        crud_user.update_user(
            db,
            user_id=user.id,
            user_data={
                "device_token": token,
                "device_type": platform,
                "push_notifications_enabled": True,
            },
        )

    return device, created


def _clear_legacy_mirror_if_matched(db: Session, *, user: User, token: str) -> None:
    """Clear users.device_token ONLY if it still holds ``token``.

    Device-scoped mirror maintenance for disable/delete: the legacy column
    must not keep pointing at a muted/removed credential. This is a
    MIRROR-ONLY clear — the registry row keeps its state (a disabled device
    is NOT a dead credential), and the user-level
    ``push_notifications_enabled`` flag is deliberately NOT reset (master
    opt-out belongs to explicit user intent, not device lifecycle).
    """
    crud_user.clear_legacy_device_mirror(db, user_id=user.id, expected_token=token)


def disable_user_device(db: Session, *, user: User, device_row_id: int) -> bool:
    """Logout ONE device (device-level switch). Legacy mirror cleared only
    when it points at exactly this credential."""
    device = crud_push_device.get_device(
        db, user_id=user.id, device_row_id=device_row_id
    )
    if device is None:
        return False
    disabled = crud_push_device.disable_device(
        db, user_id=user.id, device_row_id=device_row_id
    )
    if disabled:
        _clear_legacy_mirror_if_matched(db, user=user, token=device.token)
    return disabled


def enable_user_device(db: Session, *, user: User, device_row_id: int) -> bool:
    return crud_push_device.enable_device(
        db, user_id=user.id, device_row_id=device_row_id
    )


def list_user_devices(db: Session, *, user: User) -> list[PushDevice]:
    """All own registry rows incl. disabled/invalidated history."""
    return crud_push_device.list_devices(db, user_id=user.id)


def get_user_device(
    db: Session, *, user: User, device_row_id: int
) -> PushDevice | None:
    """Own-device lookup passthrough (foreign ids → None → HTTP 404)."""
    return crud_push_device.get_device(db, user_id=user.id, device_row_id=device_row_id)


def delete_user_device(db: Session, *, user: User, device_row_id: int) -> bool:
    """Hard-remove ONE device row (full logout with credential removal)."""
    device = crud_push_device.get_device(
        db, user_id=user.id, device_row_id=device_row_id
    )
    if device is None:
        return False
    deleted = crud_push_device.delete_device(
        db, user_id=user.id, device_row_id=device_row_id
    )
    if deleted:
        _clear_legacy_mirror_if_matched(db, user=user, token=device.token)
    return deleted


def redact_device(device: PushDevice) -> dict:
    """API-safe projection: NEVER includes the token or raw credential."""
    return {
        "id": device.id,
        "provider": device.provider,
        "platform": device.platform,
        "device_id": device.device_id,
        "enabled": device.enabled,
        "active": device.invalidated_at is None,
        "last_seen_at": (
            device.last_seen_at.isoformat() if device.last_seen_at else None
        ),
        "invalidated_at": (
            device.invalidated_at.isoformat() if device.invalidated_at else None
        ),
        "created_at": device.created_at.isoformat() if device.created_at else None,
        "token_fingerprint": fingerprint(device.token),
    }
