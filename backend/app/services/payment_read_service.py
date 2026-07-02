"""Service layer for payment read endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from app.models.patient import Patient
from app.models.visit import Visit
from app.models.enums import PaymentStatus
from app.repositories.payment_read_repository import PaymentReadRepository
from app.services.billing_service import BillingService


@dataclass
class PaymentReadDomainError(Exception):
    status_code: int
    detail: str


class PaymentReadService:
    """Provides payment status and visit payment listing queries."""

    def __init__(self, db, payment_manager=None):  # type: ignore[no-untyped-def]
        self.repository = PaymentReadRepository(db)
        self.billing_service = BillingService(db)
        self.payment_manager = payment_manager

    @staticmethod
    def _format_amount(value: Any) -> str:
        if value is None:
            return "0"
        try:
            return f"{value:,.0f}".replace(",", " ")
        except Exception:
            return f"{float(value):,.0f}".replace(",", " ")

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

    def get_payment_status(self, *, payment_id: int) -> dict[str, Any]:
        payment = self.repository.get_payment(payment_id)
        if not payment:
            raise PaymentReadDomainError(status_code=404, detail="Платеж не найден")

        provider_payment_id = payment.provider_payment_id or ""
        is_test_provider_payment = provider_payment_id.startswith("test_")

        if (
            self.payment_manager
            and payment.provider
            and payment.provider_payment_id
            and payment.status
            in [PaymentStatus.PENDING.value, PaymentStatus.PROCESSING.value]
            and not is_test_provider_payment
        ):
            result = self.payment_manager.check_payment_status(
                payment.provider, payment.provider_payment_id
            )

            if result.success and result.status and result.status != payment.status:
                meta = {**(payment.provider_data or {}), **(result.provider_data or {})}
                self.billing_service.update_payment_status(
                    payment_id=payment.id, new_status=result.status, meta=meta
                )
                payment = self.repository.get_payment(payment_id)
                if not payment:
                    raise PaymentReadDomainError(
                        status_code=500, detail="Платеж не найден после обновления статуса"
                    )

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
            f"Сумма: {context['amount_display']} {context['payment'].currency or 'UZS'}",
            f"Способ оплаты: {context['method_display']}",
            f"Статус: {context['status_display']}",
        ]

        if context["refund_amount_display"]:
            lines.extend(
                [
                    "",
                    f"Возврат: {context['refund_amount_display']} UZS",
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
Сумма: {context["amount_display"]} {payment.currency}
Провайдер: {provider}
Статус: {context["status_display"]}

Описание: Оплата медицинских услуг

Спасибо за использование наших услуг!
        """.strip()
