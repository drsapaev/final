"""Durable delivery of public-booking notifications to the Registrar inbox."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.public_booking_request import (
    PublicBookingRequestNotificationOutbox,
)
from app.services.registrar_notification_service import RegistrarNotificationService

logger = logging.getLogger(__name__)

OUTBOX_BATCH_SIZE = 25
OUTBOX_LEASE = timedelta(minutes=10)
OUTBOX_BASE_RETRY_SECONDS = 60
OUTBOX_MAX_RETRY_SECONDS = 60 * 60


def retry_delay_seconds(attempt_count: int) -> int:
    """Return capped exponential backoff for a 1-based delivery attempt."""
    exponent = max(0, min(int(attempt_count) - 1, 10))
    return min(OUTBOX_BASE_RETRY_SECONDS * (2**exponent), OUTBOX_MAX_RETRY_SECONDS)


class PublicBookingRequestNotificationOutboxService:
    """Claim and retry durable internal inbox notification intents.

    Canonical notification event/delivery deduplication makes delivery
    at-least-once safe if a worker dies after persisting the inbox rows but
    before it marks the outbox item complete.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    async def process_due_batch(
        self,
        *,
        limit: int = OUTBOX_BATCH_SIZE,
        request_id: UUID | None = None,
        request_version: int | None = None,
    ) -> dict[str, int]:
        claimed_ids = self._claim_due(
            limit=limit,
            request_id=request_id,
            request_version=request_version,
        )
        result = {"claimed": len(claimed_ids), "delivered": 0, "deferred": 0}

        for outbox_id in claimed_ids:
            item = self.db.get(PublicBookingRequestNotificationOutbox, outbox_id)
            if item is None:
                continue
            try:
                delivered = await RegistrarNotificationService(
                    self.db
                ).notify_public_booking_request(
                    request_id=str(item.request_id),
                    request_version=item.request_version,
                    resubmitted=(
                        item.event_type == "public_booking_request_resubmitted"
                    ),
                )
            except Exception as exc:
                self.db.rollback()
                logger.warning(
                    "public booking notification outbox delivery raised",
                    extra={"error_type": type(exc).__name__},
                )
                delivered = False
                error_code = type(exc).__name__[:80]
            else:
                error_code = "delivery_not_recorded"

            if delivered:
                try:
                    self._mark_completed(outbox_id)
                except Exception as exc:
                    self.db.rollback()
                    logger.warning(
                        "public booking notification outbox completion deferred",
                        extra={"error_type": type(exc).__name__},
                    )
                    result["deferred"] += 1
                    continue
                result["delivered"] += 1
            else:
                try:
                    self._defer(outbox_id, error_code=error_code)
                except Exception as exc:
                    self.db.rollback()
                    logger.warning(
                        "public booking notification outbox retry scheduling failed",
                        extra={"error_type": type(exc).__name__},
                    )
                result["deferred"] += 1

        return result

    def dispatch_request_now(
        self, *, request_id: UUID, request_version: int
    ) -> dict[str, int]:
        """Attempt immediate delivery from a FastAPI worker thread.

        The request transaction has already committed its outbox row. Any
        infrastructure failure leaves that row available to the ARQ sweep
        and never changes the successful patient response.
        """
        try:
            return asyncio.run(
                self.process_due_batch(
                    limit=1,
                    request_id=request_id,
                    request_version=request_version,
                )
            )
        except Exception as exc:
            self.db.rollback()
            logger.warning(
                "public booking notification immediate attempt deferred",
                extra={"error_type": type(exc).__name__},
            )
            return {"claimed": 0, "delivered": 0, "deferred": 1}

    def _claim_due(
        self,
        *,
        limit: int,
        request_id: UUID | None,
        request_version: int | None,
    ) -> list[int]:
        if limit < 1:
            return []
        now = datetime.now(UTC)
        query = select(PublicBookingRequestNotificationOutbox.id).where(
            PublicBookingRequestNotificationOutbox.completed_at.is_(None),
            PublicBookingRequestNotificationOutbox.next_attempt_at <= now,
            or_(
                PublicBookingRequestNotificationOutbox.lease_expires_at.is_(None),
                PublicBookingRequestNotificationOutbox.lease_expires_at <= now,
            ),
        )
        if request_id is not None:
            query = query.where(
                PublicBookingRequestNotificationOutbox.request_id == request_id
            )
        if request_version is not None:
            query = query.where(
                PublicBookingRequestNotificationOutbox.request_version
                == request_version
            )
        ids = list(
            self.db.scalars(
                query.order_by(
                    PublicBookingRequestNotificationOutbox.next_attempt_at,
                    PublicBookingRequestNotificationOutbox.id,
                )
                .limit(min(limit, OUTBOX_BATCH_SIZE))
                .with_for_update(skip_locked=True)
            )
        )
        for outbox_id in ids:
            item = self.db.get(PublicBookingRequestNotificationOutbox, outbox_id)
            if item is None:
                continue
            item.attempt_count += 1
            item.lease_expires_at = now + OUTBOX_LEASE
        self.db.commit()
        return ids

    def _mark_completed(self, outbox_id: int) -> None:
        item = self.db.get(PublicBookingRequestNotificationOutbox, outbox_id)
        if item is None or item.completed_at is not None:
            return
        item.completed_at = datetime.now(UTC)
        item.lease_expires_at = None
        item.last_error_code = None
        self.db.commit()

    def _defer(self, outbox_id: int, *, error_code: str) -> None:
        item = self.db.get(PublicBookingRequestNotificationOutbox, outbox_id)
        if item is None or item.completed_at is not None:
            return
        now = datetime.now(UTC)
        item.next_attempt_at = now + timedelta(
            seconds=retry_delay_seconds(item.attempt_count)
        )
        item.lease_expires_at = None
        item.last_error_code = error_code[:80]
        self.db.commit()
