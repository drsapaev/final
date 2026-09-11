"""Service layer for payment invoice endpoints."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.models.enums import PaymentStatus
from app.models.payment_invoice import PaymentInvoice
from app.repositories.payment_invoice_repository import PaymentInvoiceRepository
from app.services.context_facades.patient_facade import (
    PatientContextFacade,
    PatientServiceContractAdapter,
)
from app.services.notifications import notification_sender_service
from app.services.payment_invariant_service import PaymentInvariantService
from app.services.payment_provider_manager_factory import get_payment_manager

logger = logging.getLogger(__name__)

_HOSTED_PAYMENT_METHODS = frozenset({"click", "payme", "kaspi"})


@dataclass
class PaymentInvoiceDomainError(Exception):
    status_code: int
    detail: str


class PaymentInvoiceService:
    """Creates and lists payment invoices."""

    def __init__(self, db, payment_manager=None):  # type: ignore[no-untyped-def]
        self.repository = PaymentInvoiceRepository(db)
        self.patient_facade = PatientContextFacade(
            PatientServiceContractAdapter(db)
        )
        self.payment_invariant_service = PaymentInvariantService(db)
        self.payment_manager = payment_manager or get_payment_manager()

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

    def list_pending_invoices(
        self,
        *,
        limit: int = 50,
        actor_role: str | None = None,
    ) -> list[dict[str, Any]]:
        try:
            invoices = self.repository.list_pending(limit=limit)
            linked_visits = {
                link.visit.id: link.visit
                for invoice in invoices
                for link in invoice.visits
                if link.visit is not None
                and Decimal(str(link.visit_amount or 0)) > Decimal("0")
            }
            processing_visit_ids = self.repository.processing_visit_ids(
                set(linked_visits)
            )
            balances_by_visit_id = {}
            if linked_visits:
                summary = self.payment_invariant_service.summarize_visits(
                    list(linked_visits.values())
                )
                balances_by_visit_id = {
                    row["visit_id"]: row for row in summary["visits"]
                }
            return [
                self._serialize_invoice(
                    invoice,
                    balances_by_visit_id=balances_by_visit_id,
                    actor_role=actor_role,
                    processing_visit_ids=processing_visit_ids,
                )
                for invoice in invoices
            ]
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

    def _serialize_invoice(
        self,
        invoice: PaymentInvoice,
        *,
        balances_by_visit_id: dict[int, dict[str, Any]] | None = None,
        actor_role: str | None = None,
        processing_visit_ids: set[int] | None = None,
    ) -> dict[str, Any]:
        positive_links = [
            link
            for link in invoice.visits
            if Decimal(str(link.visit_amount or 0)) > Decimal("0")
        ]
        linked_visits = {
            link.visit.id: link.visit
            for link in positive_links
            if link.visit is not None
        }
        linked_amount = sum(
            (Decimal(str(link.visit_amount)) for link in positive_links),
            Decimal("0"),
        )
        if linked_visits:
            if balances_by_visit_id is None:
                balance = self.payment_invariant_service.summarize_visits(
                    list(linked_visits.values())
                )
                balance_rows = balance["visits"]
            else:
                balance_rows = [
                    balances_by_visit_id[visit_id]
                    for visit_id in linked_visits
                ]
            ledger_remaining_amount = sum(
                (Decimal(str(row["remaining_amount"])) for row in balance_rows),
                Decimal("0"),
            )
            invoice_total = Decimal(str(invoice.total_amount or 0))
            remaining_amount = min(invoice_total, ledger_remaining_amount)
            paid_amount = max(invoice_total - remaining_amount, Decimal("0"))
        else:
            paid_amount = Decimal("0")
            remaining_amount = Decimal(str(invoice.total_amount or 0))
            ledger_remaining_amount = remaining_amount

        available_actions, block_reason = self.resolve_online_payment_actions(
            invoice=invoice,
            has_linked_visits=bool(linked_visits),
            paid_amount=paid_amount,
            remaining_amount=remaining_amount,
            ledger_remaining_amount=ledger_remaining_amount,
            linked_amount=linked_amount,
            actor_role=actor_role,
            has_processing_reservation=bool(
                set(linked_visits) & (processing_visit_ids or set())
            ),
        )
        return {
            "invoice_id": invoice.id,
            "amount": float(invoice.total_amount),
            "currency": invoice.currency,
            "provider": invoice.provider,
            "payment_method": invoice.payment_method,
            "status": invoice.status,
            "paid_amount": float(paid_amount),
            "remaining_amount": float(remaining_amount),
            "available_actions": available_actions,
            "online_payment_block_reason": block_reason,
            "description": invoice.notes,
            "created_at": invoice.created_at,
        }

    def resolve_online_payment_actions(
        self,
        *,
        invoice: PaymentInvoice,
        has_linked_visits: bool,
        paid_amount: Decimal,
        remaining_amount: Decimal,
        ledger_remaining_amount: Decimal,
        linked_amount: Decimal,
        actor_role: str | None,
        has_processing_reservation: bool,
    ) -> tuple[list[dict[str, str]], str | None]:
        """Return hosted-payment commands that are safe for this invoice state.

        The existing hosted-payment command charges ``invoice.total_amount``.
        Until that command records an immutable settlement amount and allocates it
        against the current ledger balance, a partially paid invoice must not be
        offered here: doing so could collect or record the same debt twice.
        """
        if invoice.status != PaymentStatus.PENDING.value:
            return [], "invoice_not_pending"
        if not has_linked_visits:
            return [], "invoice_not_linked"
        if remaining_amount <= Decimal("0"):
            return [], "invoice_settled"
        if has_processing_reservation:
            return [], "invoice_payment_in_progress"
        normalized_role = str(
            getattr(actor_role, "value", actor_role) or ""
        ).strip().lower()
        if normalized_role not in {"admin", "registrar"}:
            return [], "role_not_allowed"
        invoice_total = Decimal(str(invoice.total_amount or 0))
        if linked_amount != invoice_total:
            return [], "invoice_allocation_mismatch"
        if ledger_remaining_amount < invoice_total or paid_amount > Decimal("0"):
            return [], "partial_online_payment_not_supported"
        if ledger_remaining_amount != invoice_total:
            return [], "invoice_amount_mismatch"

        provider_info = self.payment_manager.get_provider_info()
        requested_provider = str(invoice.provider or "").strip().lower() or None
        if requested_provider is None:
            method = str(invoice.payment_method or "").strip().lower()
            if method in _HOSTED_PAYMENT_METHODS:
                requested_provider = method

        actions = []
        for provider_code, info in provider_info.items():
            normalized_code = provider_code.lower()
            if requested_provider is not None and normalized_code != requested_provider:
                continue
            supported_currencies = {
                str(currency).upper()
                for currency in info.get("supported_currencies", [])
            }
            if str(invoice.currency).upper() not in supported_currencies:
                continue
            if not self.payment_manager.supports_registrar_invoice_payment(
                normalized_code
            ):
                continue
            actions.append(
                {"action": "start_online_payment", "provider": normalized_code}
            )

        if not actions:
            return [], "provider_unavailable"
        return actions, None
