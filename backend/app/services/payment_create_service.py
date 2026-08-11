"""Service layer for cashier payment creation endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.models.enums import PaymentStatus
from app.repositories.payment_create_repository import PaymentCreateRepository
from app.services.billing_service import BillingService
from app.services.payment_invariant_service import PaymentInvariantService
from app.services.canonical_visit_service import (
    CanonicalVisitResolutionError,
    CanonicalVisitService,
)


@dataclass
class PaymentCreateDomainError(Exception):
    status_code: int
    detail: str


class PaymentCreateService:
    """Orchestrates payment creation and visit payment-status sync."""

    def __init__(self, db):  # type: ignore[no-untyped-def]
        self.repository = PaymentCreateRepository(db)
        self.billing_service = BillingService(db)

    def create_payment(
        self,
        *,
        visit_id: int | None,
        appointment_id: int | None,
        amount: float,
        currency: str,
        method: str,
        note: str | None,
    ) -> dict[str, Any]:
        resolved_visit_id = self._resolve_visit_id(visit_id=visit_id, appointment_id=appointment_id)
        if not resolved_visit_id:
            raise PaymentCreateDomainError(
                status_code=400, detail="Не указан visit_id или appointment_id"
            )

        # Issue #06 Phase 4b B1+: This caller creates PAID payments (not
        # pending), so it uses create_payment_for_visit() (cashier path),
        # NOT create_pending_payment() (online path).
        #
        # The original BillingService.create_payment() bypassed:
        #   - with_for_update() row lock
        #   - paid_amount vs total_cost check
        #   - overpayment policy
        #   - IntegrityError defense-in-depth
        from app.services.payment_invariant_service import PaymentInvariantService
        from decimal import Decimal

        payment = PaymentInvariantService(self.billing_service.db).create_payment_for_visit(
            visit_id=resolved_visit_id,
            amount=Decimal(str(amount)),
            method=method,
            note=note,
            current_user=type("User", (), {"id": None})(),  # no user context in this service
            commit=True,  # standalone — caller owns no larger transaction
        )

        self._sync_visit_paid_state(visit_id=resolved_visit_id)
        return self._build_payment_response(payment_id=payment.id)

    def _resolve_visit_id(
        self, *, visit_id: int | None, appointment_id: int | None
    ) -> int | None:
        if visit_id and appointment_id:
            resolved_appointment_visit_id = self._resolve_visit_id(
                visit_id=None,
                appointment_id=appointment_id,
            )
            if resolved_appointment_visit_id != visit_id:
                raise PaymentCreateDomainError(
                    status_code=409,
                    detail="visit_id does not match appointment_id",
                )
            return visit_id

        if visit_id:
            return visit_id

        if not appointment_id:
            return None

        try:
            return CanonicalVisitService(self.repository.db).resolve_canonical_visit(
                appointment_id,
                create_if_missing=False,
            )
        except CanonicalVisitResolutionError as exc:
            if exc.status_code == 409:
                raise PaymentCreateDomainError(
                    status_code=exc.status_code,
                    detail=exc.detail,
                ) from exc
            return None

    def _sync_visit_paid_state(self, *, visit_id: int) -> None:
        """Sync visit's payment-derived state after a payment is created.

        Issue #06 Phase 0 (Launch Blockers Audit): the previous version
        set ``visit.status = "paid"`` and ``visit.discount_mode = "paid"``
        when ``total_paid >= total_cost``. This conflated payment state
        with visit lifecycle state — two competing state machines
        (``Visit.status`` and ``Payment.status``) that inevitably
        diverge.

        Audit confirmed 0 consumers of ``visit.status == "paid"`` in the
        codebase. The ``_preserve_cashier_visit_status()`` and
        ``_preserve_operational_status_on_payment()`` functions already
        normalize the legacy ``"paid"`` value back to ``"waiting"`` with
        docstring: "legacy visit.status='paid' becomes operational waiting".

        Payment state is the source of truth and lives in the ``Payment``
        table (``status`` field, ``amount``, ``paid_at``). The aggregate
        "fully paid" state is derivable via
        ``PaymentInvariantService.compute_paid_amount() >= total_cost``.

        This method is now a no-op — kept as a hook for future
        audit-log integration (H-5) and to preserve the call site in
        ``create_payment`` without a larger refactor. The
        ``discount_mode`` field is also no longer set to ``"paid"`` here;
        if that field needs to track payment state, it should be derived
        from the Payment table, not denormalized onto the Visit.
        """
        # Issue #06 Phase 0: visit.status = "paid" removed.
        # Payment state lives in Payment table; visit lifecycle state
        # remains independent (open, in_progress, completed, closed, canceled).
        # This method is intentionally a no-op. If you need to react to
        # "visit became fully paid", query PaymentInvariantService instead.
        return None

    def _build_payment_response(self, *, payment_id: int) -> dict[str, Any]:
        payment = self.repository.get_payment(payment_id)
        if not payment:
            raise PaymentCreateDomainError(status_code=500, detail="Платеж не найден после создания")

        patient_name = "Неизвестно"
        service_name = "Услуга"
        appointment_time = "—"

        visit = self.repository.get_visit(payment.visit_id) if payment.visit_id else None
        if visit:
            if visit.visit_time:
                appointment_time = str(visit.visit_time)[:5]
            elif visit.created_at:
                appointment_time = visit.created_at.strftime("%H:%M")

            if visit.patient_id:
                patient = self.repository.get_patient(visit.patient_id)
                if patient:
                    patient_name = (
                        patient.short_name()
                        or f"{patient.first_name or ''} {patient.last_name or ''}".strip()
                        or patient_name
                    )

            first_service = self.repository.get_first_visit_service(visit.id)
            if first_service:
                service = self.repository.get_service(first_service.service_id)
                if service and service.name:
                    service_name = service.name

        method_label = "Наличные"
        if payment.provider:
            method_label = payment.provider.capitalize()
        elif payment.method:
            method_label = payment.method.capitalize()

        return {
            "id": payment.id,
            "payment_id": payment.id,
            "time": appointment_time or "—",
            "patient": patient_name,
            "service": service_name,
            "amount": float(payment.amount),
            "method": method_label,
            "status": payment.status,
            "currency": payment.currency,
            "created_at": payment.created_at.isoformat() if payment.created_at else None,
            "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
        }
