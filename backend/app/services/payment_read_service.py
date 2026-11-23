"""Service layer for payment read endpoints."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.models.enums import PaymentStatus
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.visit import Visit
from app.repositories.payment_read_repository import PaymentReadRepository
from app.services.billing_service import BillingService
from app.services.payment_state_checks import is_valid_payment_transition

logger = logging.getLogger(__name__)


@dataclass
class PaymentReadDomainError(Exception):
    status_code: int
    detail: str


class PaymentReadService:
    """Provides payment status and visit payment listing queries."""

    def __init__(self, db, payment_manager=None):  # type: ignore[no-untyped-def]
        self.db = db
        self.repository = PaymentReadRepository(db)
        self.billing_service = BillingService(db)
        self.payment_manager = payment_manager

    @staticmethod
    def _format_amount(value: Any) -> str:
        try:
            amount = Decimal(str(value))
            if not amount.is_finite() or amount != amount.quantize(Decimal("0.01")):
                raise ValueError("Invalid receipt amount")
        except (InvalidOperation, TypeError, ValueError):
            raise PaymentReadDomainError(status_code=409, detail="Сумма платежа требует сверки") from None
        return f"{amount:,.2f}".replace(",", " ")

    @staticmethod
    def _receipt_currency(value: Any) -> str:
        if isinstance(value, str) and len(value) == 3 and value.isascii() and value.isalpha() and value.isupper():
            return value
        return "валюта не указана"

    @staticmethod
    def _format_payment_method(method: str | None) -> str:
        mapping = {
            "cash": "Наличные",
            "card": "Банковская карта",
            "transfer": "Перевод",
            "online": "Онлайн",
            "click": "Click",
            "payme": "PayMe",
            "kaspi": "Kaspi",
        }
        normalized = (method or "").strip().lower()
        return mapping.get(normalized, method or "—")

    @staticmethod
    def _format_payment_status(status: str | None) -> str:
        mapping = {
            "paid": "Оплачено",
            "completed": "Оплачено",
            "refunded": "Возвращено",
            "cancelled": "Отменён",
            "canceled": "Отменён",
            "pending": "Ожидает оплаты",
            "processing": "В обработке",
            "failed": "Ошибка",
            "void": "Аннулирован",
        }
        normalized = (status or "").strip().lower()
        if normalized in mapping:
            return mapping[normalized]
        return status.title() if status else "—"

    @staticmethod
    def _format_patient_name(patient: Patient | None, fallback_id: int | None) -> str:
        if patient is None:
            return f"Пациент #{fallback_id}" if fallback_id else "Неизвестно"
        try:
            if hasattr(patient, "short_name") and callable(patient.short_name):
                name = patient.short_name()
                if name:
                    return name
        except Exception:
            pass

        parts = []
        for attr in ("last_name", "first_name", "middle_name"):
            value = getattr(patient, attr, None)
            if value:
                parts.append(str(value).strip())
        if parts:
            return " ".join(parts)
        return f"Пациент #{patient.id}" if getattr(patient, "id", None) else "Неизвестно"

    def _load_receipt_context(self, *, payment_id: int) -> dict[str, Any]:
        payment = self.repository.get_payment(payment_id)
        if not payment:
            raise PaymentReadDomainError(status_code=404, detail="Платеж не найден")

        visit = (
            self.repository.db.query(Visit).filter(Visit.id == payment.visit_id).first()
            if payment.visit_id
            else None
        )
        patient = None
        if visit and visit.patient_id:
            patient = (
                self.repository.db.query(Patient)
                .filter(Patient.id == visit.patient_id)
                .first()
            )

        paid_at = payment.paid_at or payment.created_at
        receipt_no = payment.receipt_no or f"PAY-{payment.id:06d}"
        patient_name = self._format_patient_name(patient, visit.patient_id if visit else payment.visit_id)

        return {
            "payment": payment,
            "visit": visit,
            "patient": patient,
            "receipt_no": receipt_no,
            "patient_name": patient_name,
            "paid_at_display": paid_at.strftime("%d.%m.%Y %H:%M"),
            "amount_display": self._format_amount(payment.amount),
            "method_display": self._format_payment_method(payment.method),
            "status_display": self._format_payment_status(payment.status),
            "refund_amount_display": self._format_amount(payment.refunded_amount)
            if payment.refunded_amount
            else None,
        }

    @staticmethod
    def _register_receipt_fonts() -> tuple[str, str]:
        try:
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
        except ImportError:
            return "Helvetica", "Helvetica-Bold"

        candidate_pairs = [
            (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
            (Path("C:/Windows/Fonts/arialuni.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
            (
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            ),
            (
                Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
                Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
            ),
        ]

        for regular_path, bold_path in candidate_pairs:
            if not regular_path.exists():
                continue

            regular_name = f"ReceiptFont-{regular_path.stem}"
            bold_name = f"{regular_name}-Bold"
            if regular_name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(regular_name, str(regular_path)))
            if bold_path.exists():
                if bold_name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(bold_name, str(bold_path)))
                return regular_name, bold_name
            return regular_name, regular_name

        return "Helvetica", "Helvetica-Bold"

    def _persist_provider_status(
        self,
        payment: Payment,
        *,
        new_status: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        payment_id = payment.id
        previous_status = payment.status
        try:
            payment = self.billing_service.update_payment_status(
                payment_id=payment_id, new_status=new_status, meta=metadata, commit=False,
            )
            self.repository.record_provider_transition(payment, previous_status=previous_status)
            # Keep the response in the authorized snapshot before commit expires the ORM row.
            status_payload = self._payment_status_payload(payment)
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            logger.error("Could not save provider status transition for payment_id=%s", payment_id)
            raise PaymentReadDomainError(
                status_code=503, detail="Обновление статуса платежа временно недоступно",
            ) from None
        return status_payload

    def get_payment_status(
        self,
        *,
        payment_id: int,
        recheck_access: Callable[[Payment], None] | None = None,
        end_read_transaction: Callable[[], None] | None = None,
    ) -> dict[str, Any]:
        payment = self.repository.get_payment(payment_id)
        if not payment:
            raise PaymentReadDomainError(status_code=404, detail="Платеж не найден")

        provider = payment.provider
        order_id = payment.provider_payment_id
        recorded_status = payment.status

        if (
            self.payment_manager
            and provider
            and order_id
            and recorded_status in (PaymentStatus.PENDING.value, PaymentStatus.PROCESSING.value)
            and not order_id.startswith("test_")
        ):
            visit_id = payment.visit_id
            recorded_payment_terms = (payment.amount, payment.currency, payment.updated_at)
            if end_read_transaction is not None:
                end_read_transaction()
            result = self.payment_manager.check_payment_status(provider, order_id)
            reported_status = result.status.lower() if isinstance(result.status, str) else ""

            can_transition = (
                result.success
                and reported_status != recorded_status
                and is_valid_payment_transition(recorded_status, reported_status)
            )
            payment = self.repository.get_payment(payment_id, for_update=can_transition, refresh=True)
            if payment is None or payment.visit_id != visit_id:
                raise PaymentReadDomainError(status_code=404, detail="Платеж не найден")
            if recheck_access is not None:
                recheck_access(payment)

            if (
                can_transition
                and payment.status == recorded_status
                and payment.provider == provider
                and payment.provider_payment_id == order_id
                and (payment.amount, payment.currency, payment.updated_at) == recorded_payment_terms
            ):
                meta = {**(payment.provider_data or {}), **(result.provider_data or {})}
                return self._persist_provider_status(payment, new_status=reported_status, metadata=meta)

        return self._payment_status_payload(payment)

    @staticmethod
    def _payment_status_payload(payment: Payment) -> dict[str, Any]:
        return {
            "payment_id": payment.id,
            "status": payment.status,
            "amount": float(payment.amount),
            "currency": payment.currency,
            "provider": payment.provider,
            "provider_payment_id": payment.provider_payment_id,
            "created_at": payment.created_at,
            "paid_at": payment.paid_at,
            "provider_data": payment.provider_data,
        }

    def get_available_providers(self) -> dict[str, Any]:
        if self.payment_manager is None:
            raise PaymentReadDomainError(
                status_code=500, detail="Менеджер платежных провайдеров не настроен"
            )

        provider_info = self.payment_manager.get_provider_info()
        providers = []
        for code, info in provider_info.items():
            providers.append(
                {
                    "name": info["name"],
                    "code": code,
                    "supported_currencies": info["supported_currencies"],
                    "is_active": True,
                    "features": info["features"],
                }
            )
        return {"providers": providers}

    def list_payments(
        self,
        *,
        visit_id: int | None,
        date_from: str | None,
        date_to: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        payment_responses = self.billing_service.get_payments_list(
            visit_id=visit_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
        return {"payments": payment_responses, "total": len(payment_responses)}

    def get_visit_payments(self, *, visit_id: int) -> dict[str, Any]:
        payments = self.repository.list_payments_by_visit(visit_id)
        payment_responses = []
        for payment in payments:
            payment_responses.append(
                {
                    "payment_id": payment.id,
                    "id": payment.id,
                    "status": payment.status,
                    "amount": float(payment.amount),
                    "currency": payment.currency,
                    "provider": payment.provider,
                    "provider_payment_id": payment.provider_payment_id,
                    "created_at": (
                        payment.created_at.isoformat() if payment.created_at else None
                    ),
                    "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
                    "provider_data": payment.provider_data,
                }
            )
        return {"payments": payment_responses, "total": len(payment_responses)}

    def generate_receipt(self, *, payment_id: int, format_type: str) -> dict[str, Any]:
        payment = self.repository.get_payment(payment_id)
        if not payment:
            raise PaymentReadDomainError(status_code=404, detail="Платеж не найден")

        receipt_data = {
            "payment_id": payment.id,
            "amount": float(payment.amount),
            "currency": payment.currency,
            "status": payment.status,
            "provider": payment.provider,
            "created_at": payment.created_at.isoformat() if payment.created_at else None,
            "description": "Оплата медицинских услуг",
        }
        return {
            "success": True,
            "receipt_data": receipt_data,
            "receipt_url": f"/api/v1/payments/{payment_id}/receipt/download",
            "format": format_type,
        }

    def build_receipt_pdf(self, *, payment_id: int) -> bytes:
        context = self._load_receipt_context(payment_id=payment_id)

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas
        except ImportError as exc:
            raise PaymentReadDomainError(
                status_code=500, detail="ReportLab не установлен"
            ) from exc

        font_regular, font_bold = self._register_receipt_fonts()
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        _, height = A4
        left = 18 * mm
        top = height - 20 * mm

        pdf.setTitle(f"receipt_{context['receipt_no']}")
        pdf.setAuthor("Clinic")
        pdf.setSubject("Payment receipt")

        pdf.setFont(font_bold, 18)
        pdf.drawString(left, top, "КВИТАНЦИЯ ОБ ОПЛАТЕ")
        y = top - 10 * mm

        lines = [
            f"Номер чека: {context['receipt_no']}",
            f"Дата: {context['paid_at_display']}",
            "",
            f"Пациент: {context['patient_name']}",
            f"Визит ID: {context['visit'].id if context['visit'] else context['payment'].visit_id or 'N/A'}",
            "",
            "ПЛАТЕЖНАЯ ИНФОРМАЦИЯ:",
            f"Сумма: {context['amount_display']} {self._receipt_currency(context['payment'].currency)}",
            f"Способ оплаты: {context['method_display']}",
            f"Статус: {context['status_display']}",
        ]

        if context["refund_amount_display"]:
            lines.extend(
                [
                    "",
                    f"Возврат: {context['refund_amount_display']} {self._receipt_currency(context['payment'].currency)}",
                ]
            )
        if context["payment"].refund_reason:
            lines.append(f"Причина возврата: {context['payment'].refund_reason}")
        if context["payment"].note:
            lines.extend(["", f"Примечание: {context['payment'].note}"])

        pdf.setFont(font_regular, 11)
        for line in lines:
            pdf.drawString(left, y, line)
            y -= 6.5 * mm
            if y < 20 * mm:
                pdf.showPage()
                pdf.setFont(font_regular, 11)
                y = height - 20 * mm

        pdf.save()
        return buffer.getvalue()

    def build_receipt_content(self, *, payment_id: int) -> str:
        context = self._load_receipt_context(payment_id=payment_id)
        payment = context["payment"]
        provider = payment.provider.title() if payment.provider else "—"
        return f"""
КВИТАНЦИЯ ОБ ОПЛАТЕ
===================

Номер платежа: {payment.id}
Дата: {context["paid_at_display"]}
Сумма: {context["amount_display"]} {self._receipt_currency(payment.currency)}
Провайдер: {provider}
Статус: {context["status_display"]}

Описание: Оплата медицинских услуг

Спасибо за использование наших услуг!
        """.strip()
