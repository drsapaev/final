"""Service layer for payment invoice endpoints."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from app.models.enums import PaymentStatus
from app.models.payment_invoice import PaymentInvoice
from app.repositories.payment_invoice_repository import PaymentInvoiceRepository
from app.services.context_facades.patient_facade import (
    PatientContextFacade,
    PatientServiceContractAdapter,
)
from app.services.notifications import notification_sender_service

logger = logging.getLogger(__name__)


@dataclass
class PaymentInvoiceDomainError(Exception):
    status_code: int
    detail: str


class PaymentInvoiceService:
    """Creates and lists payment invoices."""

    def __init__(self, db):  # type: ignore[no-untyped-def]
        self.repository = PaymentInvoiceRepository(db)
        self.patient_facade = PatientContextFacade(
            PatientServiceContractAdapter(db)
        )

    def create_invoice(
        self,
        *,
        amount: float,
        currency: str,
        provider: str,
        description: str | None,
        patient_id: int,
        created_by_id: int | None,
    ) -> dict[str, Any]:
        try:
            patient_id = self._validate_patient_id(patient_id)
            if not self.patient_facade.active_patient_exists(patient_id):
                raise PaymentInvoiceDomainError(
                    status_code=404, detail="Пациент не найден"
                )

            provider_data: dict[str, Any] = {}
            if created_by_id is not None:
                provider_data["created_by_id"] = created_by_id

            invoice = PaymentInvoice(
                patient_id=patient_id,
                total_amount=amount,
                currency=currency,
                provider=provider,
                status=PaymentStatus.PENDING.value,
                payment_method=provider,
                notes=description,
                provider_data=provider_data or None,
            )

            self.repository.add(invoice)
            self.repository.commit()
            self.repository.refresh(invoice)

            self._notify_unpaid_invoice_created(invoice)

            return self._serialize_invoice(invoice)
        except PaymentInvoiceDomainError:
            raise
        except Exception as exc:
            self.repository.rollback()
            raise PaymentInvoiceDomainError(
                status_code=500, detail=f"Ошибка создания счета: {exc}"
            )

    def list_pending_invoices(self, *, limit: int = 50) -> list[dict[str, Any]]:
        try:
            invoices = self.repository.list_pending(limit=limit)
            return [self._serialize_invoice(invoice) for invoice in invoices]
        except Exception as exc:
            raise PaymentInvoiceDomainError(
                status_code=500, detail=f"Ошибка получения счетов: {exc}"
            )

    @staticmethod
    def _validate_patient_id(patient_id: int) -> int:
        if (
            isinstance(patient_id, bool)
            or not isinstance(patient_id, int)
            or patient_id <= 0
        ):
            raise PaymentInvoiceDomainError(
                status_code=400, detail="Некорректный patient_id"
            )
        return patient_id

    def _notify_unpaid_invoice_created(self, invoice: PaymentInvoice) -> None:
        patient_id = getattr(invoice, "patient_id", None)
        if not patient_id:
            return

        try:
            patient_id_int = int(patient_id)
        except (TypeError, ValueError):
            return

        if patient_id_int <= 0:
            return

        metadata = {
            "amount": invoice.total_amount,
            "currency": invoice.currency,
            "status": invoice.status,
            "provider": invoice.provider,
        }
        sender = notification_sender_service

        async def _send() -> None:
            await sender.send_patient_telegram_event_notification(
                db=self.repository.db,
                patient_id=patient_id_int,
                event_type="payment_created",
                metadata=metadata,
            )

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            async def _send_detached() -> None:
                from app.db.session import SessionLocal

                db = SessionLocal()
                try:
                    await sender.send_patient_telegram_event_notification(
                        db=db,
                        patient_id=patient_id_int,
                        event_type="payment_created",
                        metadata=metadata,
                    )
                finally:
                    db.close()

            task = loop.create_task(_send_detached())
            task.add_done_callback(
                self._log_unpaid_invoice_created_notification_result
            )
            return

        try:
            asyncio.run(_send())
        except Exception as exc:
            logger.warning(
                "Payment invoice Telegram unpaid bill notification failed",
                extra={"error_type": type(exc).__name__},
            )

    @staticmethod
    def _log_unpaid_invoice_created_notification_result(
        task: asyncio.Task[None],
    ) -> None:
        try:
            task.result()
        except Exception as exc:
            logger.warning(
                "Payment invoice Telegram unpaid bill notification failed",
                extra={"error_type": type(exc).__name__},
            )

    @staticmethod
    def _serialize_invoice(invoice: PaymentInvoice) -> dict[str, Any]:
        return {
            "invoice_id": invoice.id,
            "amount": float(invoice.total_amount),
            "currency": invoice.currency,
            "provider": invoice.provider,
            "status": invoice.status,
            "description": invoice.notes,
            "created_at": invoice.created_at,
        }
