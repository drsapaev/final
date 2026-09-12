"""PR-6: DB primitives for the push device registry.

Sync-Session primitives only (the codebase's established crud style).
Business framing lives in the service layer; HTTP contracts in schemas.

Core invariants enforced here:

- ONE ACTIVE credential must not duplicate (partial unique index in the
  table; ``register_device`` is idempotent on top of it).
- Invalidation is EXACT-credential and conditional: only rows whose
  ``token`` equals the credential that REALLY failed (canonical FCM
  UNREGISTERED verdict) are marked ``invalidated_at``. A replacement
  token registered while a failing send was in flight is never wiped.
- Device-scoped operations (disable/enable/delete) are user-scoped by
  construction: every statement filters on ``user_id`` first, so
  cross-user access degrades to "not found" — never to a mutation.
- Device-level operations NEVER write ``users.push_notifications_enabled``
  (that is the user-level master opt-out, owned by explicit user intent).
"""

from __future__ import annotations

from datetime import datetime, UTC

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.push_device import PushDevice


def _now_utc() -> datetime:
    return datetime.now(UTC)


def register_device(
    db: Session,
    *,
    user_id: int,
    provider: str,
    platform: str,
    token: str,
    device_id: str | None = None,
    credential: dict | None = None,
) -> tuple[PushDevice, bool]:
    """Idempotent multi-device registration. Returns ``(row, created)``.

    Semantics:

    - Same (provider, token) already ACTIVE and owned by this user →
      refresh: bump ``last_seen_at``, re-enable (a re-registering device
      that was disabled is an explicit "push me again" intent), update
      platform/device_id/credential if provided. NOT a duplicate —
      ``(row, False)``.
    - Same (provider, token) ACTIVE but owned by ANOTHER user → the
      physical device moved to a new account (shared device, re-login):
      invalidate that exact credential row, then create a fresh row for
      the new owner. The dead shared credential must not stay active for
      the previous account (PR-5 lesson, multi-owner tokens).
    - New token for a KNOWN physical device (user_id + provider +
      device_id match) → token rotation: the device's other ACTIVE rows
      with a different token are invalidated, the rotated token is
      inserted. Rows without ``device_id`` cannot be attributed to a
      physical device and are left for the UNREGISTERED purge path.
    """
    now = _now_utc()

    # FOR UPDATE: a concurrent register of the SAME credential blocks here
    # until the first transaction commits, then takes the idempotent refresh
    # path instead of racing to INSERT (SQLite ignores FOR UPDATE — the
    # partial unique index is the hard backstop there, with the
    # IntegrityError re-select below).
    existing = (
        db.execute(
            select(PushDevice)
            .where(
                PushDevice.provider == provider,
                PushDevice.token == token,
                PushDevice.invalidated_at.is_(None),
            )
            .with_for_update()
        )
        .scalars()
        .first()
    )

    if existing is not None and existing.user_id == user_id:
        existing.last_seen_at = now
        existing.enabled = True
        existing.platform = platform
        if device_id is not None:
            existing.device_id = device_id
        if credential is not None:
            existing.credential = credential
        db.commit()
        db.refresh(existing)
        return existing, False

    if existing is not None:
        # Credential moved to a different account: free the active slot for
        # the new owner by invalidating the exact credential row first.
        existing.invalidated_at = now
        existing.enabled = False
        db.commit()

    if device_id is not None:
        # Token rotation for the same physical device.
        db.execute(
            update(PushDevice)
            .where(
                PushDevice.user_id == user_id,
                PushDevice.provider == provider,
                PushDevice.device_id == device_id,
                PushDevice.token != token,
                PushDevice.invalidated_at.is_(None),
            )
            .values(invalidated_at=now, enabled=False)
            .execution_options(synchronize_session=False)
        )
        db.commit()

    row = PushDevice(
        user_id=user_id,
        provider=provider,
        platform=platform,
        token=token,
        device_id=device_id,
        credential=credential,
        enabled=True,
        last_seen_at=now,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race against a concurrent INSERT of the same credential
        # (the partial unique index is the final arbiter). Re-run the full
        # flow: the winner's row is now visible, so this either refreshes it
        # (same owner) or moves the credential to this account (new owner).
        db.rollback()
        return register_device(
            db,
            user_id=user_id,
            provider=provider,
            platform=platform,
            token=token,
            device_id=device_id,
            credential=credential,
        )
    db.refresh(row)
    return row, True


def get_device(db: Session, *, user_id: int, device_row_id: int) -> PushDevice | None:
    """Return the user's OWN registry row by primary key (others → None)."""
    return (
        db.execute(
            select(PushDevice).where(
                PushDevice.id == device_row_id, PushDevice.user_id == user_id
            )
        )
        .scalars()
        .first()
    )


def list_devices(db: Session, *, user_id: int) -> list[PushDevice]:
    """All registry rows of the user (active, disabled and invalidated —
    the invalidated ones are honest history, visible with a timestamp)."""
    stmt = (
        select(PushDevice)
        .where(PushDevice.user_id == user_id)
        .order_by(PushDevice.created_at.desc(), PushDevice.id.desc())
    )
    return list(db.execute(stmt).scalars().all())


def get_active_devices_for_user(db: Session, *, user_id: int) -> list[PushDevice]:
    """Rows a sender may target: enabled AND not invalidated.

    The FCM pilot (post-census) will consume this instead of the legacy
    ``users.device_token`` column; nothing reads it today by design —
    PR-6 does NOT change notification business semantics.
    """
    stmt = select(PushDevice).where(
        PushDevice.user_id == user_id,
        PushDevice.enabled.is_(True),
        PushDevice.invalidated_at.is_(None),
    )
    return list(db.execute(stmt).scalars().all())


def disable_device(db: Session, *, user_id: int, device_row_id: int) -> bool:
    """Logout ONE device: ``enabled = False``. Other devices (and the
    user-level master opt-out) are untouched. Returns False if the row
    is not the user's own."""
    device = get_device(db, user_id=user_id, device_row_id=device_row_id)
    if device is None:
        return False
    device.enabled = False
    db.commit()
    return True


def enable_device(db: Session, *, user_id: int, device_row_id: int) -> bool:
    """Re-enable ONE device. An INVALIDATED row cannot be revived — its
    credential is known dead; only a fresh registration returns it."""
    device = get_device(db, user_id=user_id, device_row_id=device_row_id)
    if device is None or device.invalidated_at is not None:
        return False
    device.enabled = True
    db.commit()
    return True


def delete_device(db: Session, *, user_id: int, device_row_id: int) -> bool:
    """Hard-delete the user's OWN registry row (full logout with token
    removal). Cross-user requests are a no-op returning False."""
    device = get_device(db, user_id=user_id, device_row_id=device_row_id)
    if device is None:
        return False
    db.delete(device)
    db.commit()
    return True


def invalidate_active_credential(db: Session, *, provider: str, token: str) -> int:
    """EXACT-token conditional invalidation of ACTIVE rows.

    Marks ``invalidated_at`` on every row holding precisely this credential
    (a dead shared token is dead for ALL of its owners — PR-5 lesson).
    Never touches other tokens, never writes the user-level opt-out flag.
    Returns the number of rows invalidated.
    """
    result = db.execute(
        update(PushDevice)
        .where(
            PushDevice.provider == provider,
            PushDevice.token == token,
            PushDevice.invalidated_at.is_(None),
        )
        .values(invalidated_at=_now_utc(), enabled=False)
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return result.rowcount or 0
