"""
Сервис для управления QR очередями
"""

from __future__ import annotations

import base64  # noqa: F401
import io  # noqa: F401
import logging  # noqa: F401
import re  # noqa: F401
import secrets  # noqa: F401
import socket  # noqa: F401
from datetime import UTC, date, datetime, timedelta  # noqa: F401
from typing import TYPE_CHECKING, Any  # noqa: F401

import qrcode  # noqa: F401
from sqlalchemy import func  # noqa: F401
from sqlalchemy.orm import Session  # noqa: F401

from app.core.config import settings  # noqa: F401
from app.models.clinic import Doctor  # noqa: F401
from app.models.online_queue import (  # noqa: F401
    DailyQueue,
    OnlineQueueEntry,
    QueueJoinSession,
    QueueStatistics,
    QueueToken,
)
from app.models.patient import Patient  # noqa: F401
from app.models.user import User  # noqa: F401
from app.services.queue_domain_service import QueueDomainService  # noqa: F401
from app.services.queue_service import (  # noqa: F401
    QueueConflictError,
    QueueNotFoundError,
    QueueValidationError,
    queue_service,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

JOIN_SESSION_PROCESSING_STATUS = "joining"

# Round-6 (PR #3362 review, P1-1): the joined marker is VERSIONED. The
# legacy ``joined`` value is what the pre-round-5 workers replay on sight
# (their ``_replay_joined_session`` checks exactly ``status == "joined"``
# and knows nothing about the payload fingerprint) — during a rolling
# deployment that let a retry carrying payload B be served patient A's
# saved ticket (wrong-patient disclosure). New workers write
# ``joined_v2``: an old worker does NOT recognize it as replayable and
# classifies the row through its fallback (expires_at long past →
# ``join_session_expired``) — a decisive, no-business-action refusal,
# never a replay of a foreign payload. New workers accept BOTH values:
# legacy rows replay fail-closed (no fingerprint ⇒ used refusal).
JOIN_SESSION_JOINED_STATUS = "joined"
JOIN_SESSION_JOINED_STATUS_V2 = "joined_v2"

# Round-6 (PR #3362 review, P2-1): a complete attempt whose allocator
# batch produced ZERO tickets and was ALREADY rolled back is a PROVEN
# no-business-action outcome. The backend says so explicitly instead of
# masking the domain refusal behind «Internal server error» — the client
# may offer the honest start-over instead of looping on UNKNOWN until
# the session TTL expires.
JOIN_SESSION_REASON_NOT_EXECUTED = "join_session_not_executed"


class JoinSessionNotExecutedRefusal(ValueError):
    """A domain refusal AFTER a confirmed rollback of the whole batch.

    Round-6 (PR #3362 review, P2-1): raised only when the service has
    already executed ``db.rollback()`` — the transaction provably left no
    ticket behind — so the refusal is decisive evidence that nothing was
    created. ``details`` carries the per-specialist allocator errors for
    the structured 400 body.
    """

    def __init__(self, message: str, details: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.reason = JOIN_SESSION_REASON_NOT_EXECUTED
        self.details = details or []


class JoinSessionStateRefusal(ValueError):
    """A complete-time refusal that is PROVEN from the join-session row.

    Round-4 review (PR #3362, P2-1): the public complete endpoint used to
    mask every ValueError behind a generic 400 «Internal server error», so
    the patient's client could not distinguish a CONFIRMED pre-execution
    refusal (nothing was created — an explicit start-over is safe) from an
    unknown business outcome (a renewal/restart must stay forbidden).
    Carrying a machine-readable ``reason`` lets the frontend offer the
    honest recovery path for each class instead of dead-ending.
    """

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


# Round-5 (PR #3362 review, P1-3): a joined session is bound to the payload
# of its FIRST successful complete. A replay whose payload does not match
# the stored fingerprint is refused decisively — the attempt can never be
# re-served to (or executed for) a different identity.
JOIN_SESSION_REASON_PAYLOAD_MISMATCH = "join_session_payload_mismatch"


def _now(tz=None) -> datetime:
    """Return the current datetime, honoring test monkeypatches.

    Tests freeze time by patching ``app.services.qr_queue_service.datetime``
    (and ``app.services.queue_service.datetime``) with a ``FixedDateTime``
    subclass. The split modules under ``qr_queue`` import ``datetime``
    directly from the stdlib, so a plain ``datetime.now()`` would bypass the
    patch. Look the class up via the public shim module at call time so the
    patched class (if any) is used.
    """
    from app.services import qr_queue_service

    return qr_queue_service.datetime.now(tz)




class QRQueueServiceMixinBase:
    """Type-hint anchor for QRQueueService mixins."""
