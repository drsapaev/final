"""Locked persistence access for the internal all-free staging workflow."""
from __future__ import annotations

from sqlalchemy import exists, or_
from sqlalchemy.orm import Session

from app.models.all_free_request import AllFreeRequest, AllFreeRequestLine
from app.models.encounter import Encounter
from app.models.payment import Payment, PaymentVisit
from app.models.payment_invoice import PaymentInvoiceVisit
from app.models.payment_webhook import PaymentTransaction, PaymentWebhook
from app.models.visit import Visit, VisitService


class AllFreeRequestRepository:
    def __init__(self, db: Session):
        self.db = db

    def lock_visit(self, visit_id: int) -> Visit | None:
        return (self.db.query(Visit).filter(Visit.id == visit_id)
                .with_for_update().populate_existing().first())

    def lock_encounter(self, encounter_id: int) -> Encounter | None:
        return (self.db.query(Encounter).filter(Encounter.id == encounter_id)
                .with_for_update().populate_existing().first())

    def lock_lines(self, visit_id: int) -> list[VisitService]:
        # A concurrent service writer holds its child row before the 0102
        # trigger takes the Visit lock. Do not wait for that child while
        # holding Visit: the caller rolls back the whole transaction on 55P03.
        return (self.db.query(VisitService).filter(VisitService.visit_id == visit_id)
                .order_by(VisitService.id).with_for_update(nowait=True).populate_existing().all())

    def lock_request(self, request_id: int) -> AllFreeRequest | None:
        return (self.db.query(AllFreeRequest).filter(AllFreeRequest.id == request_id)
                .with_for_update().populate_existing().first())

    def request_lines(self, request_id: int) -> list[AllFreeRequestLine]:
        return (self.db.query(AllFreeRequestLine).filter(AllFreeRequestLine.request_id == request_id)
                .order_by(AllFreeRequestLine.visit_service_id_snapshot).populate_existing().all())

    def has_active_request(self, visit_id: int) -> bool:
        return (self.db.query(AllFreeRequest.id).filter(
            AllFreeRequest.visit_id == visit_id,
            AllFreeRequest.status.in_(("pending", "approved")),
        ).first() is not None)

    def has_financial_history(self, visit_id: int) -> bool:
        """Conservative temporary fence; NOT proof that provider settlement is fenced."""
        from app.models.billing import Invoice

        grouped = exists(1).where(PaymentVisit.payment_id == Payment.id, PaymentVisit.visit_id == visit_id)
        return any((
            self.db.query(Payment.id).filter(or_(Payment.visit_id == visit_id, grouped)).first() is not None,
            self.db.query(PaymentInvoiceVisit.id).filter(PaymentInvoiceVisit.visit_id == visit_id).first() is not None,
            self.db.query(Invoice.id).filter(Invoice.visit_id == visit_id).first() is not None,
            self.db.query(PaymentWebhook.id).filter(PaymentWebhook.visit_id == visit_id).first() is not None,
            self.db.query(PaymentTransaction.id).filter(PaymentTransaction.visit_id == visit_id).first() is not None,
        ))
