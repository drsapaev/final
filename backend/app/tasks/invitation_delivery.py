"""arq outbox delivery: durable DB state, no bearer or PHI in queue jobs."""
from __future__ import annotations

import logging
from uuid import uuid4

from app.db.session import SessionLocal
from app.models.visit_invitation_delivery import (
    VisitInvitationApprovalRecovery,
    VisitInvitationDelivery,
)
from app.services.notification_service import NotificationService
from app.services.visit_invitation_delivery import (
    InvitationRuntimeUnavailable,
    claim_visit_invitation,
    deliver_price_approval_recovery,
    deliver_registrar_invitation,
    pin_invitation_runtime,
    send_claimed_visit_invitation,
)

logger = logging.getLogger(__name__)
_CURSOR_KEY = "clinic:visit-invitation:sweep-cursor:v1"
_RECOVERY_CURSOR_KEY = "clinic:visit-invitation:recovery-cursor:v1"
_BATCH_SIZE = 100


async def run_visit_invitation_sweep(ctx) -> None:
    """Queue pending IDs; a persistent cursor prevents old pending starvation."""
    from app.tasks.worker import QUEUE_NAME

    redis = ctx["redis"]
    try:
        for model, cursor_key, argument in (
            (VisitInvitationDelivery, _CURSOR_KEY, "delivery_id"),
            (VisitInvitationApprovalRecovery, _RECOVERY_CURSOR_KEY, "recovery_id"),
        ):
            raw = await redis.get(cursor_key)
            try:
                cursor = max(0, int(raw or 0))
                if cursor > 9223372036854775807:
                    cursor = 0
            except (ValueError, TypeError, OverflowError):
                cursor = 0
            with SessionLocal() as db:
                pin_invitation_runtime(db)
                def page(after, model=model):
                    return (db.query(model.id).filter(model.state == "pending", model.id > after)
                            .order_by(model.id).limit(_BATCH_SIZE).all())
                rows = page(cursor)
                if not rows and cursor:
                    cursor = 0
                    rows = page(cursor)
                ids = [row.id for row in rows]
                db.rollback()
            for item_id in ids:
                # The database claim, not the random queue job ID, deduplicates.
                await redis.enqueue_job("deliver_visit_invitation", **{argument: item_id},
                                        _queue_name=QUEUE_NAME, _job_id=f"invitation:{uuid4()}")
                cursor = item_id
                await redis.set(cursor_key, str(cursor))
            if not ids:
                await redis.set(cursor_key, "0")
    except InvitationRuntimeUnavailable:
        logger.warning("Invitation sweep unavailable")
    except Exception as exc:
        # Exceptions from database/Redis must not include PHI or credentials.
        logger.warning("Invitation sweep failed (%s)", type(exc).__name__)


async def deliver_visit_invitation(ctx, *, delivery_id: int | None = None, recovery_id: int | None = None) -> None:
    """Process one pending attempt; UNKNOWN is never dispatched again."""
    if ((delivery_id is None) == (recovery_id is None)
        or (delivery_id is not None and (type(delivery_id) is not int or delivery_id <= 0))
        or (recovery_id is not None and (type(recovery_id) is not int or recovery_id <= 0))):
        return
    try:
        with SessionLocal() as db:
            pin_invitation_runtime(db)
            if recovery_id is not None:
                await deliver_price_approval_recovery(db, recovery_id, NotificationService(db))
                return
            row = db.query(VisitInvitationDelivery.channel, VisitInvitationDelivery.state).filter(
                VisitInvitationDelivery.id == delivery_id
            ).first()
            db.rollback()
            if row is None or row.state != "pending":
                return
            sender = NotificationService(db)
            if row.channel == "phone":
                await deliver_registrar_invitation(db, delivery_id, sender)
                return
            claimed = claim_visit_invitation(db, delivery_id)
            if claimed is not None:
                await send_claimed_visit_invitation(db, claimed, sender)
    except InvitationRuntimeUnavailable:
        logger.warning("Invitation delivery unavailable")
    except Exception as exc:
        # Durable UNKNOWN survives provider timeout/crash and blocks retries.
        logger.warning("Invitation delivery failed (%s)", type(exc).__name__)
