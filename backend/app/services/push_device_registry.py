"""PR-6: push device registry service — the canonical multi-device store.

Contract (single and explicit):

- ``push_devices`` is the canonical registry for NEW clients (the
  Android FCM pilot and any future PWA push support).
- The legacy single-device column ``users.device_token`` is FROZEN as
  deprecated: nothing in this module reads it or writes it. Existing
  legacy endpoints and senders keep working unchanged until the final
  removal PR (after the census).
- This PR does NOT activate FCM/Web Push sending: no sender consumes
  the registry yet. :func:`list_sendable_tokens` is the documented
  future integration point, with the user-level master opt-out
  (``users.push_notifications_enabled``) winning over everything.

Invariants enforced here:

- one user -> many devices;
- the same active credential never appears twice for one user
  (upsert + DB-level UNIQUE (user_id, token_hash));
- a credential has at most ONE active owner across all users: when a
  shared installation switches accounts, register() atomically retires
  the previous owner, and the partial unique index
  ``uq_push_devices_active_credential`` enforces the invariant under
  races (the losing insert retries after the winner's retirement);
- invalidation touches ONLY the exact failed credential (provider
  feedback path) — never the user's other devices;
- a single-device logout RETIRES only the exact device row (other
  devices and users untouched) — the retired row leaves the live-slot
  quota and becomes retention-bounded history; re-registering the same
  credential re-activates it ("client statement is authoritative");
- device-level ``enabled`` is independent of the user-level master;
- per-user registry growth is BOUNDED two ways: a user holds at most
  :data:`MAX_LIVE_DEVICES_PER_USER` live (non-invalidated) rows, and
  at most :data:`MAX_INVALIDATED_ROWS_PER_USER` invalidated history
  rows (older history is hard-deleted on registration) — registration
  cannot grow the user's storage footprint beyond the sum of the two
  bounds, no matter how credentials are rotated;
  a registration beyond the live quota is rejected instead of stored.

Credential identity and size: uniqueness and lookups are keyed on
``token_hash`` (full SHA-256 hex, fixed 64 chars) — NEVER on the raw
TEXT credential, which can be arbitrarily large (a B-tree over an
incompressible 64 KiB token would exceed PostgreSQL's index-row-size
limit). The raw token is stored for future sending only.

SECURITY: provider credentials (FCM tokens / Web Push subscription
descriptors) must never reach logs or Sentry. Every log line in this
module identifies a device by ``user_id`` + ``token_fingerprint`` only.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.push_device import PushDevice
from app.models.user import User

logger = logging.getLogger(__name__)

# Bounded retry for the two unique guarantees (per-user uniqueness and
# the global one-active-owner partial index) under a concurrent race.
_REGISTER_ATTEMPTS = 3

# PR-6 round 4 (codex P1): bound per-user registry growth. Without a
# quota any authenticated user could store unbounded 64 KiB credentials
# and exhaust database storage. The cap counts LIVE rows (rows not yet
# invalidated), so provider-dead history never starves new
# registrations, and it is deliberately generous: real multi-device
# users (phones, tablets, browsers) stay far below it. Idempotent
# re-registration and same-transaction rotation never trip the quota —
# only genuinely NEW live slots do.
MAX_LIVE_DEVICES_PER_USER = 20

# PR-6 round 4b (codex P1): bound the retained ROTATION HISTORY too. A
# rotation retires the previous credential but never deletes it — and a
# hostile client can rotate 64 KiB credentials on every request while
# keeping exactly one live row, so the live quota alone cannot stop
# storage exhaustion. Registrations prune invalidated history beyond
# this retention bound (oldest first). Provider-dead history (exact-
# token invalidation) is capped by the same bound.
MAX_INVALIDATED_ROWS_PER_USER = 20


class PushDeviceQuotaExceeded(RuntimeError):
    """Raised when a registration would exceed the per-user live quota."""


def token_hash(token: str) -> str:
    """Full SHA-256 hex of the credential — the bounded uniqueness key."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_fingerprint(token: str) -> str:
    """Non-secret SHA-256 prefix identifying a credential in logs."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def _now() -> datetime:
    return datetime.now(UTC)


def register_device(
    db: Session,
    *,
    user_id: int,
    provider: str,
    platform: str,
    token: str,
    device_id: str | None = None,
    previous_token: str | None = None,
) -> PushDevice:
    """Register or refresh a device credential (idempotent upsert).

    The client statement is authoritative: an existing row for the same
    ``(user_id, token_hash)`` — including one previously invalidated by
    rotation or provider feedback — is re-activated and refreshed.

    Account switching: every OTHER user's row for the same exact
    credential that is not already invalidated is retired
    (``enabled=False`` + ``invalidated_at``) in the same transaction —
    active and merely disabled ones alike, so a former owner can never
    re-enable their way back onto an installation that has since
    switched accounts. A concurrent race against that invariant loses
    on ``uq_push_devices_active_credential`` and retries.

    ``previous_token`` (explicit rotation): when the client replaced its
    credential and knows the old one, the exact old row of THIS user is
    retired in the same transaction. Rotation is never inferred
    implicitly.
    """
    token = token.strip()
    if not token:
        # Defense in depth: the endpoint schema already returns 422 for
        # blank credentials, but the service is also a documented entry
        # point for future senders — a blank credential must never become
        # the identity of a registry row.
        raise ValueError("push credential must not be blank")
    previous_token = previous_token.strip() if previous_token else None
    credential_hash = token_hash(token)

    for _attempt in range(_REGISTER_ATTEMPTS):
        # Serialize per-user quota accounting (codex round 4b P2):
        # concurrent distinct-token registrations for the same user are
        # invisible to the UNIQUE guards (every hash differs), so a burst
        # could otherwise commit past MAX_LIVE_DEVICES_PER_USER. The row
        # lock on the user anchors all of a user's registrations — the
        # count below is serialized against them. SQLite (tests) ignores
        # FOR UPDATE; PostgreSQL enforces it.
        db.query(User).filter(User.id == user_id).with_for_update().one()
        row = (
            db.query(PushDevice)
            .filter(
                PushDevice.user_id == user_id,
                PushDevice.token_hash == credential_hash,
            )
            .one_or_none()
        )
        _enforce_live_quota(
            db,
            user_id=user_id,
            credential_hash=credential_hash,
            previous_token=previous_token if previous_token != token else None,
        )
        try:
            # Retire every other owner of this exact credential BEFORE the
            # reactivation touches the flush: both the retirement and the
            # reactivation are UPDATEs on existing rows, and SQLAlchemy
            # flushes them in primary-key order. Reactivating a lower-id
            # historical row while a higher-id previous owner is still
            # active would violate the partial unique index mid-flush and
            # fail the whole transfer (e.g. A -> B -> A). The intermediate
            # flush pins the retirement first, so the partial index never
            # sees two active owners.
            _retire_other_owners(db, token_hash=credential_hash, keep_user_id=user_id)
            db.flush()
            if row is None:
                row = PushDevice(
                    user_id=user_id,
                    provider=provider,
                    platform=platform,
                    device_id=device_id,
                    token=token,
                    token_hash=credential_hash,
                    token_fingerprint=token_fingerprint(token),
                    enabled=True,
                    last_seen_at=_now(),
                )
                db.add(row)

            # Authoritative refresh of the client statement.
            row.provider = provider
            row.platform = platform
            row.device_id = device_id
            row.enabled = True
            row.invalidated_at = None
            row.last_seen_at = _now()

            if previous_token and previous_token != token:
                stale_rows = (
                    db.query(PushDevice)
                    .filter(
                        PushDevice.user_id == user_id,
                        PushDevice.token_hash == token_hash(previous_token),
                    )
                    .all()
                )
                for stale in stale_rows:
                    stale.enabled = False
                    stale.invalidated_at = _now()

            # Retention prune: hard-delete the oldest invalidated rows
            # beyond the per-user history bound (see MAX_INVALIDATED_
            # ROWS_PER_USER). Dead rows have no readers — senders filter
            # on invalidated_at — so deletion is contract-safe. The
            # explicit flush first is REQUIRED (sessions run with
            # autoflush=False): without it the prune query would not see
            # this transaction's own retirement, and history would
            # overshoot the bound by one row per register.
            db.flush()
            _prune_invalidated_history(db, user_id=user_id)

            # PR-6 round 4 (codex P2): the reactivation path hits the
            # partial unique index on UPDATE, which surfaces on this
            # flush or on commit — not on the insert flush above. Both
            # unique guarantees are covered by ONE bounded retry here:
            # any IntegrityError in the transaction rolls it back and
            # re-queries the winner's state.
            db.flush()
            db.commit()
        except IntegrityError:
            # A concurrent register won a unique slot (same user, or
            # another user's still-active row) — drop our insert and
            # retry: the re-query adopts the winner, the re-run of
            # the retirement clears a stale previous owner.
            db.rollback()
            continue
        except OperationalError:
            # PR-6 round 11 (codex P2): database AVAILABILITY failures stay
            # mappable to the dedicated retryable-503 handler — re-raise a
            # SANITIZED OperationalError (no chained exception, no bound
            # parameters) instead of collapsing it into the generic 500.
            db.rollback()
            raise OperationalError(
                "push device registration failed: database unavailable "
                "(SQL parameters hidden)",
                None,
                None,
            ) from None
        except SQLAlchemyError:
            # PR-6 round 4b (codex P1): SQLAlchemy exception text embeds
            # the bound parameters — for the INSERT above that is the RAW
            # credential. Only IntegrityError participates in the retry;
            # any other database error is re-raised SANITIZED (no chained
            # exception, no parameters) so the credential can never reach
            # logs or Sentry through the global handlers.
            db.rollback()
            raise RuntimeError(
                "push device registration failed: database error "
                "(SQL parameters hidden); the client may retry"
            ) from None

        db.refresh(row)
        logger.info(
            "push device registered: user_id=%s device_row=%s fingerprint=%s",
            user_id,
            row.id,
            row.token_fingerprint,
        )
        return row

    raise IntegrityError(
        "push device registration kept losing the unique-slot race "
        f"after {_REGISTER_ATTEMPTS} attempts",
        params=None,
        orig=None,
    )


def _enforce_live_quota(
    db: Session,
    *,
    user_id: int,
    credential_hash: str,
    previous_token: str | None,
) -> None:
    # PR-6 round 4 (codex P1): reject a registration that would create a
    # NEW live slot beyond the per-user quota. Rows this transaction is
    # about to retire (the rotated-away ``previous_token``) or reactivate
    # (the row for ``credential_hash`` itself, incl. an invalidated one)
    # do not count — idempotent refresh and same-transaction rotation
    # must always succeed.
    query = db.query(PushDevice).filter(
        PushDevice.user_id == user_id,
        PushDevice.invalidated_at.is_(None),
        PushDevice.token_hash != credential_hash,
    )
    if previous_token:
        query = query.filter(PushDevice.token_hash != token_hash(previous_token))
    if query.count() >= MAX_LIVE_DEVICES_PER_USER:
        raise PushDeviceQuotaExceeded(
            f"push device registry limit reached "
            f"({MAX_LIVE_DEVICES_PER_USER} live devices per user)"
        )


def _prune_invalidated_history(db: Session, *, user_id: int) -> None:
    # Keep only the newest MAX_INVALIDATED_ROWS_PER_USER invalidated rows
    # of this user; hard-delete the rest (oldest first). Called inside
    # the registration transaction, so the prune commits atomically with
    # the rotation that created the newest history row.
    stale_ids = [
        row_id
        for (row_id,) in db.query(PushDevice.id)
        .filter(
            PushDevice.user_id == user_id,
            PushDevice.invalidated_at.is_not(None),
        )
        .order_by(PushDevice.invalidated_at.desc(), PushDevice.id.desc())
        .offset(MAX_INVALIDATED_ROWS_PER_USER)
        .all()
    ]
    if stale_ids:
        db.query(PushDevice).filter(PushDevice.id.in_(stale_ids)).delete(
            synchronize_session=False
        )
        logger.info(
            "push device history pruned: user_id=%s count=%s",
            user_id,
            len(stale_ids),
        )


def _retire_other_owners(db: Session, *, token_hash: str, keep_user_id: int) -> None:
    # Retire every other-user history row of this exact credential that
    # is not already invalidated — active AND merely disabled ones. A
    # disabled row whose ``invalidated_at`` is still NULL would otherwise
    # be re-enableable by its former owner's device toggle, silently
    # restoring a delivery destination for an installation that has
    # since switched accounts. Rows already invalidated (provider-dead
    # or retired by an earlier transfer) stay untouched so their
    # original invalidation timestamp is preserved.
    others = (
        db.query(PushDevice)
        .filter(
            PushDevice.token_hash == token_hash,
            PushDevice.user_id != keep_user_id,
            PushDevice.invalidated_at.is_(None),
        )
        .all()
    )
    now = _now()
    for other in others:
        other.enabled = False
        other.invalidated_at = now


def refresh_device(db: Session, *, user_id: int, token: str) -> bool:
    """Heartbeat from an already-registered device: bump last_seen_at.

    Returns False when the (user, token) pair is unknown or the
    credential was invalidated; a refresh never resurrects a device.
    """
    credential_hash = token_hash(token.strip())
    row = (
        db.query(PushDevice)
        .filter(
            PushDevice.user_id == user_id,
            PushDevice.token_hash == credential_hash,
        )
        .one_or_none()
    )
    if row is None or row.invalidated_at is not None:
        return False
    row.last_seen_at = _now()
    db.commit()
    return True


def unregister_devices(
    db: Session,
    *,
    user_id: int,
    token: str | None = None,
    device_id: str | None = None,
) -> int:
    """Retire matching rows of THIS user only (single logout).

    Both filters are optional but at least one is required; when both
    are given the intersection is retired. Rows of other users are
    never touched, even when the same physical credential is registered
    under another account. Returns the number of retired rows.

    PR-6 round 4b (codex P2): logout RETIRES the row (``enabled=False``
    + ``invalidated_at``) instead of merely disabling it — a retired row
    releases its live-slot quota (a new installation can register even
    when the cap was reached) and flows into the retention-bounded
    history pool. A returning installation re-registers the same
    credential: the idempotent upsert re-activates it. Matching rows
    that a device-level toggle had DISABLED (``enabled=False`` but not
    yet invalidated) are retired too — otherwise a disabled row would
    hold its quota slot until the user re-enabled it first.
    """
    if token is None and device_id is None:
        raise ValueError("token or device_id is required to unregister a device")

    query = db.query(PushDevice).filter(
        PushDevice.user_id == user_id,
        PushDevice.invalidated_at.is_(None),
    )
    if token is not None:
        query = query.filter(PushDevice.token_hash == token_hash(token.strip()))
    if device_id is not None:
        query = query.filter(PushDevice.device_id == device_id)

    rows = query.all()
    now = _now()
    for row in rows:
        row.enabled = False
        row.invalidated_at = now
    db.commit()
    if rows:
        logger.info(
            "push devices unregistered: user_id=%s count=%s",
            user_id,
            len(rows),
        )
    return len(rows)


def set_device_enabled(
    db: Session, *, user_id: int, device_row_id: int, enabled: bool
) -> PushDevice | None:
    """Toggle the device-level switch; other devices stay untouched."""
    row = (
        db.query(PushDevice)
        .filter(PushDevice.id == device_row_id, PushDevice.user_id == user_id)
        .one_or_none()
    )
    if row is None:
        return None
    row.enabled = enabled
    db.commit()
    db.refresh(row)
    logger.info(
        "push device toggled: user_id=%s device_row=%s enabled=%s",
        user_id,
        row.id,
        row.enabled,
    )
    return row


def invalidate_token(db: Session, *, provider: str, token: str) -> int:
    """Exact-token conditional invalidation (provider feedback path).

    Called when the provider reports a specific credential dead (e.g. an
    FCM UNREGISTERED response). ONLY rows whose credential equals
    ``token`` (and whose provider matches) are marked dead — the user's
    other devices, and rows holding different credentials, are never
    touched. The dead credential is retired for every holder, because a
    provider-dead credential is dead for everyone; no user-initiated
    action is involved here.
    """
    credential_hash = token_hash(token.strip())
    rows = (
        db.query(PushDevice)
        .filter(
            PushDevice.provider == provider,
            PushDevice.token_hash == credential_hash,
            PushDevice.invalidated_at.is_(None),
        )
        .all()
    )
    now = _now()
    for row in rows:
        row.enabled = False
        row.invalidated_at = now
    db.commit()
    if rows:
        # fingerprint only — the credential itself never enters logs
        logger.info(
            "push credentials invalidated: provider=%s count=%s fingerprint=%s",
            provider,
            len(rows),
            token_fingerprint(token),
        )
    return len(rows)


def list_devices(db: Session, *, user_id: int) -> list[PushDevice]:
    """All registry rows of the user (including disabled/invalidated)."""
    return (
        db.query(PushDevice)
        .filter(PushDevice.user_id == user_id)
        .order_by(PushDevice.id)
        .all()
    )


def list_sendable_tokens(db: Session, *, user_id: int) -> list[str]:
    """Credentials a sender may use today — the future integration point.

    Layering, in order:
    1. user-level master opt-out (``users.push_notifications_enabled``)
       wins over everything;
    2. the device must be ``enabled`` (device-level switch);
    3. the credential must not be ``invalidated_at``.

    No sender consumes this yet: activation is a separate, census-gated
    decision after this PR.
    """
    user = db.get(User, user_id)
    if user is None or not user.push_notifications_enabled:
        return []
    rows = (
        db.query(PushDevice)
        .filter(
            PushDevice.user_id == user_id,
            PushDevice.enabled.is_(True),
            PushDevice.invalidated_at.is_(None),
        )
        .all()
    )
    return [row.token for row in rows]
