"""qr_queue — split from qr_queue_service.py.

Re-exports QRQueueService for backward compatibility.
"""
from __future__ import annotations

from app.services.qr_queue._base import QRQueueServiceMixinBase
from app.services.qr_queue._patients import PatientsMixin
from app.services.qr_queue._qr_helpers import QrHelpersMixin
from app.services.qr_queue._queue_ops import QueueOpsMixin
from app.services.qr_queue._sessions import SessionsMixin
from app.services.qr_queue._specialists import SpecialistsMixin
from app.services.qr_queue._tokens import TokensMixin
from app.services.qr_queue._visits import VisitsMixin

__all__ = ["QRQueueService"]


class QRQueueService(
    SpecialistsMixin,
    PatientsMixin,
    VisitsMixin,
    SessionsMixin,
    TokensMixin,
    QueueOpsMixin,
    QrHelpersMixin,
    QRQueueServiceMixinBase,
):
    """Сервис для управления QR очередями.

    Composed of focused mixin modules under qr_queue/.
    """

    def __init__(
        self,
        db: Session,
        queue_domain_service: QueueDomainService | None = None,
    ):
        from sqlalchemy.orm import Session  # noqa: F401

        from app.services.queue_domain_service import QueueDomainService
        self.db = db
        self.queue_domain_service = queue_domain_service or QueueDomainService(db)
