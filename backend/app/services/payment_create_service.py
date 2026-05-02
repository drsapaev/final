"""Service layer for cashier payment creation endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from app.models.enums import PaymentStatus
from app.repositories.payment_create_repository import PaymentCreateRepository
from app.services.billing_service import BillingService


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

        payment = self.billing_service.create_payment(
            visit_id=resolved_visit_id,
            amount=float(amount),
            currency=currency,
            method=method,
            status=PaymentStatus.PAID.value,
            note=note,
        )

        self._sync_visit_paid_state(visit_id=resolved_visit_id)
        return self._build_payment_response(payment_id=payment.id)

    def _resolve_visit_id(
        self, *, visit_id: int | None, appointment_id: int | None
    ) -> int | None:
        if visit_id:
            return visit_id

        if not appointment_id:
            return None

        appointment = self.repository.get_appointment(appointment_id)
        if not appointment:
            return None

        appointment_date = appointment.appointment_date or date.today()
        visit = self.repository.get_visit_by_patient_and_date(
            patient_id=appointment.patient_id,
            visit_date=appointment_date,
        )
        return visit.id if visit else None

    def _sync_visit_paid_state(self, *, visit_id: int) -> None:
        visit = self.repository.get_visit(visit_id)
        if not visit:
            return

        total_cost = Decimal("0")
        for vs in self.repository.get_visit_services(visit_id):
            price = Decimal(str(vs.price)) if vs.price else Decimal("0")
            qty = Decimal(vs.qty if vs.qty else 1)
            total_cost += price * qty

        total_paid = sum(
            (Decimal(str(p.amount)) for p in self.repository.list_paid_payments_for_visit(visit_id)),
            Decimal("0"),
        )

        if total_paid >= total_cost:
            visit.status = "paid"
            visit.discount_mode = "paid"
            self.repository.commit()

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
