"""
API endpoints РґР»СЏ РјР°СЃС‚РµСЂР° СЂРµРіРёСЃС‚СЂР°С†РёРё СЃ РїРѕРґРґРµСЂР¶РєРѕР№ РєРѕСЂР·РёРЅС‹
Р Р°СЃС€РёСЂРµРЅРёРµ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРіРѕ registrar_integration.py
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import String, func, literal
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.crud import clinic as crud_clinic, online_queue as crud_queue
from app.models.clinic import ClinicSettings, Doctor
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.patient import Patient
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.feature_flags import is_feature_enabled
from app.services.registrar_wizard_queue_assignment_service import (
    RegistrarWizardQueueAssignmentService,
)
from app.services.notifications import notification_sender_service
from app.services.queue_service import queue_service
from app.services.queue_session import get_or_create_session_id
from app.services.service_mapping import get_service_code, normalize_service_code

logger = logging.getLogger(__name__)

router = APIRouter()

# ===================== РЎРҐР•РњР« Р”Р›РЇ РљРћР Р—РРќР« =====================


class ServiceItemRequest(BaseModel):
    service_id: int
    quantity: int = Field(default=1, ge=1)
    custom_price: Optional[Decimal] = None  # Р”Р»СЏ РІСЂР°С‡РµР±РЅРѕРіРѕ РїРµСЂРµРѕРїСЂРµРґРµР»РµРЅРёСЏ С†РµРЅС‹


class VisitRequest(BaseModel):
    doctor_id: Optional[int] = None  # РњРѕР¶РµС‚ Р±С‹С‚СЊ None РґР»СЏ Р»Р°Р±РѕСЂР°С‚РѕСЂРЅС‹С… СѓСЃР»СѓРі
    services: List[ServiceItemRequest]
    visit_date: date
    visit_time: Optional[str] = None  # HH:MM
    department: Optional[str] = None
    notes: Optional[str] = None


class CartRequest(BaseModel):
    patient_id: int
    visits: List[VisitRequest]
    discount_mode: str = Field(default="none")  # none|repeat|benefit|all_free
    payment_method: str = Field(default="cash")  # cash|card|online|click|payme
    all_free: bool = Field(default=False)  # Р§РµРєР±РѕРєСЃ "All Free"
    notes: Optional[str] = None


class CartResponse(BaseModel):
    success: bool
    message: str
    invoice_id: int
    visit_ids: List[int]
    total_amount: Decimal
    queue_numbers: Dict[
        int, List[Dict]
    ]  # visit_id -> [{"queue_tag": str, "number": int, "queue_id": int}]
    print_tickets: List[Dict[str, Any]]
    created_visits: Optional[List[Dict[str, Any]]] = (
        None  # РРЅС„РѕСЂРјР°С†РёСЏ Рѕ СЃРѕР·РґР°РЅРЅС‹С… РІРёР·РёС‚Р°С…
    )


class MarkPaidRequest(BaseModel):
    amount: Optional[Decimal] = None
    method: Optional[str] = Field(default="cash")


class RepeatEligibilityCandidate(BaseModel):
    service_id: int
    doctor_id: Optional[int] = None
    visit_date: date
    candidate_key: Optional[str] = None


class RepeatEligibilityPreviewRequest(BaseModel):
    patient_id: int
    candidates: List[RepeatEligibilityCandidate] = Field(default_factory=list)


class RepeatEligibilityPreviewItem(BaseModel):
    candidate_key: Optional[str] = None
    service_id: int
    doctor_id: Optional[int] = None
    visit_date: date
    eligible: bool
    reason: str
    repeat_window_days: int
    repeat_discount_percent: int


class RepeatEligibilityPreviewResponse(BaseModel):
    patient_id: int
    items: List[RepeatEligibilityPreviewItem]


# ===================== Р’РЎРџРћРњРћР“РђРўР•Р›Р¬РќР«Р• Р¤РЈРќРљР¦РР =====================


def _check_repeat_visit_eligibility(
    db: Session,
    patient_id: int,
    doctor_id: int,
    service_ids: List[int],
    days_window: int = 21,
) -> bool:
    """
    РџСЂРѕРІРµСЂРєР° РїСЂР°РІР° РЅР° РїРѕРІС‚РѕСЂРЅС‹Р№ РІРёР·РёС‚ (в‰¤N РґРЅРµР№ Сѓ С‚РѕРіРѕ Р¶Рµ СЃРїРµС†РёР°Р»РёСЃС‚Р°)
    """
    # РџРѕР»СѓС‡Р°РµРј РєРѕРЅСЃСѓР»СЊС‚Р°С†РёРё СЌС‚РѕРіРѕ РІСЂР°С‡Р° Р·Р° РїРѕСЃР»РµРґРЅРёРµ N РґРЅРµР№
    cutoff_date = date.today() - timedelta(days=days_window)

    recent_visits = (
        db.query(Visit)
        .filter(
            Visit.patient_id == patient_id,
            Visit.doctor_id == doctor_id,
            Visit.visit_date >= cutoff_date,
            Visit.status != "cancelled",
        )
        .all()
    )

    if not recent_visits:
        return False

    # РџСЂРѕРІРµСЂСЏРµРј, РµСЃС‚СЊ Р»Рё СЃСЂРµРґРё РІС‹Р±СЂР°РЅРЅС‹С… СѓСЃР»СѓРі РєРѕРЅСЃСѓР»СЊС‚Р°С†РёРё
    consultation_services = (
        db.query(Service)
        .filter(Service.id.in_(service_ids), Service.is_consultation == True)
        .all()
    )

    return len(consultation_services) > 0


def _resolve_effective_discount_mode(cart_data: CartRequest) -> str:
    """All Free checkbox wins over the legacy discount_mode radio."""
    if cart_data.all_free or cart_data.discount_mode == "all_free":
        return "all_free"
    return cart_data.discount_mode or "none"


def _load_registration_discount_settings(db: Session) -> Dict[str, Any]:
    """Load repeat/benefit settings with safe defaults."""
    defaults = {
        "repeat_visit_days": 21,
        "repeat_visit_discount": 0,
        "benefit_consultation_free": True,
        "all_free_auto_approve": False,
    }
    settings = defaults.copy()

    rows = (
        db.query(ClinicSettings)
        .filter(
            ClinicSettings.key.in_(
                [
                    "repeat_visit_days",
                    "repeat_visit_discount",
                    "benefit_consultation_free",
                    "all_free_auto_approve",
                ]
            )
        )
        .all()
    )

    for row in rows:
        if row.key in {"repeat_visit_days", "repeat_visit_discount"}:
            try:
                settings[row.key] = int(row.value)
            except (TypeError, ValueError):
                pass
        elif row.key in {"benefit_consultation_free", "all_free_auto_approve"}:
            settings[row.key] = bool(row.value)

    return settings


def _apply_service_discount(
    base_price: Decimal,
    discount_mode: str,
    settings: Dict[str, Any],
    is_consultation: bool,
) -> Decimal:
    """Apply deterministic service pricing rules for the registrar cart."""
    if discount_mode == "all_free":
        return Decimal("0")

    if discount_mode == "repeat" and is_consultation:
        repeat_discount = Decimal(str(settings.get("repeat_visit_discount", 0) or 0))
        repeat_discount = max(Decimal("0"), min(repeat_discount, Decimal("100")))
        return (base_price * (Decimal("100") - repeat_discount) / Decimal("100")).quantize(
            Decimal("0.01")
        )

    if discount_mode == "benefit" and is_consultation:
        if settings.get("benefit_consultation_free", True):
            return Decimal("0")

    return base_price


def _visit_has_paid_payment(db: Session, visit_id: int) -> bool:
    """Payment truth comes from the payments table, not from discount_mode."""
    try:
        from app.models.payment import Payment

        payment_row = (
            db.query(Payment)
            .filter(Payment.visit_id == visit_id)
            .order_by(Payment.created_at.desc())
            .first()
        )
        return bool(
            payment_row
            and (str(payment_row.status).lower() == "paid" or payment_row.paid_at)
        )
    except Exception:
        return False


REGISTRATION_DISCOUNT_MODES = {"none", "repeat", "benefit", "all_free"}


def _normalize_registration_discount_mode(raw_value: str | None) -> str:
    normalized = str(raw_value or "none").strip().lower()
    if normalized in REGISTRATION_DISCOUNT_MODES:
        return normalized
    return "none"


def _resolve_payment_truth(
    db: Session,
    *,
    visit_id: int | None = None,
    legacy_paid_at: datetime | None = None,
) -> tuple[str, str | None]:
    if visit_id:
        try:
            from app.models.payment import Payment

            payment_row = (
                db.query(Payment)
                .filter(Payment.visit_id == visit_id)
                .order_by(Payment.created_at.desc())
                .first()
            )
            if payment_row:
                payment_status = (
                    "paid"
                    if (
                        str(getattr(payment_row, "status", "") or "").lower() == "paid"
                        or getattr(payment_row, "paid_at", None)
                    )
                    else "pending"
                )
                return payment_status, getattr(payment_row, "method", None) or None
        except Exception:
            logger.debug(
                "registrar_wizard: failed to resolve payment truth for visit %s",
                visit_id,
                exc_info=True,
            )

    return ("paid", None) if legacy_paid_at else ("pending", None)


def _build_repeat_eligibility_preview_item(
    db: Session,
    *,
    patient_id: int,
    candidate: RepeatEligibilityCandidate,
    repeat_visit_days: int,
    repeat_discount_percent: int,
) -> RepeatEligibilityPreviewItem:
    service = db.query(Service).filter(Service.id == candidate.service_id).first()

    if not service:
        return RepeatEligibilityPreviewItem(
            candidate_key=candidate.candidate_key,
            service_id=candidate.service_id,
            doctor_id=candidate.doctor_id,
            visit_date=candidate.visit_date,
            eligible=False,
            reason="РЈСЃР»СѓРіР° РЅРµ РЅР°Р№РґРµРЅР°",
            repeat_window_days=repeat_visit_days,
            repeat_discount_percent=repeat_discount_percent,
        )

    if not service.is_consultation:
        return RepeatEligibilityPreviewItem(
            candidate_key=candidate.candidate_key,
            service_id=candidate.service_id,
            doctor_id=candidate.doctor_id,
            visit_date=candidate.visit_date,
            eligible=False,
            reason="РџРѕРІС‚РѕСЂРЅР°СЏ СЃРєРёРґРєР° РґРѕСЃС‚СѓРїРЅР° С‚РѕР»СЊРєРѕ РґР»СЏ РєРѕРЅСЃСѓР»СЊС‚Р°С†РёР№",
            repeat_window_days=repeat_visit_days,
            repeat_discount_percent=repeat_discount_percent,
        )

    if not candidate.doctor_id:
        return RepeatEligibilityPreviewItem(
            candidate_key=candidate.candidate_key,
            service_id=candidate.service_id,
            doctor_id=candidate.doctor_id,
            visit_date=candidate.visit_date,
            eligible=False,
            reason="Р’С‹Р±РµСЂРёС‚Рµ РІСЂР°С‡Р° РґР»СЏ РїСЂРѕРІРµСЂРєРё РїРѕРІС‚РѕСЂРЅРѕР№ СЃРєРёРґРєРё",
            repeat_window_days=repeat_visit_days,
            repeat_discount_percent=repeat_discount_percent,
        )

    eligible = _check_repeat_visit_eligibility(
        db,
        patient_id,
        candidate.doctor_id,
        [candidate.service_id],
        days_window=repeat_visit_days,
    )

    reason = (
        f"Р”РѕСЃС‚СѓРїРЅР° РїРѕРІС‚РѕСЂРЅР°СЏ СЃРєРёРґРєР° {repeat_discount_percent}%"
        if eligible
        else f"РќРµС‚ РєРѕРЅСЃСѓР»СЊС‚Р°С†РёРё Сѓ СЌС‚РѕРіРѕ РІСЂР°С‡Р° Р·Р° РїРѕСЃР»РµРґРЅРёРµ {repeat_visit_days} РґРЅРµР№"
    )

    return RepeatEligibilityPreviewItem(
        candidate_key=candidate.candidate_key,
        service_id=candidate.service_id,
        doctor_id=candidate.doctor_id,
        visit_date=candidate.visit_date,
        eligible=eligible,
        reason=reason,
        repeat_window_days=repeat_visit_days,
        repeat_discount_percent=repeat_discount_percent,
    )


# _calculate_visit_price() СѓРґР°Р»РµРЅР° - РёСЃРїРѕР»СЊР·СѓР№С‚Рµ billing_service.calculate_total() (SSOT)


def _create_queue_entries(
    db: Session, visits: List[Visit], queue_settings: Dict[str, Any]
) -> Dict[int, int]:
    """
    РЎРѕР·РґР°РЅРёРµ Р·Р°РїРёСЃРµР№ РІ РѕС‡РµСЂРµРґРё РґР»СЏ РІРёР·РёС‚РѕРІ РЅР° СЃРµРіРѕРґРЅСЏ
    """
    queue_numbers = {}
    today = date.today()

    for visit in visits:
        if visit.visit_date != today:
            continue

        # РћРїСЂРµРґРµР»СЏРµРј РІСЃРµ СѓРЅРёРєР°Р»СЊРЅС‹Рµ С‚РёРїС‹ РѕС‡РµСЂРµРґРµР№ РґР»СЏ СѓСЃР»СѓРі РІРёР·РёС‚Р°
        visit_services = (
            db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
        )
        service_ids = [vs.service_id for vs in visit_services]
        services = db.query(Service).filter(Service.id.in_(service_ids)).all()

        # РЎРѕР±РёСЂР°РµРј РІСЃРµ СѓРЅРёРєР°Р»СЊРЅС‹Рµ queue_tag РґР»СЏ СЃРѕР·РґР°РЅРёСЏ РѕС‚РґРµР»СЊРЅС‹С… РѕС‡РµСЂРµРґРµР№
        unique_queue_tags = set()
        for service in services:
            if service.queue_tag:
                unique_queue_tags.add(service.queue_tag)
            else:
                unique_queue_tags.add("general")  # РџРѕ СѓРјРѕР»С‡Р°РЅРёСЋ

        # РЎРѕР·РґР°С‘Рј РѕС‚РґРµР»СЊРЅСѓСЋ Р·Р°РїРёСЃСЊ РІ РѕС‡РµСЂРµРґРё РґР»СЏ РєР°Р¶РґРѕРіРѕ С‚РёРїР° СѓСЃР»СѓРі
        visit_queue_numbers = []
        try:
            for queue_tag in unique_queue_tags:
                # РћРїСЂРµРґРµР»СЏРµРј РІСЂР°С‡Р° РґР»СЏ РѕС‡РµСЂРµРґРё
                doctor_id = visit.doctor_id

                # Р”Р»СЏ РѕС‡РµСЂРµРґРµР№ Р±РµР· РєРѕРЅРєСЂРµС‚РЅРѕРіРѕ РІСЂР°С‡Р° РёСЃРїРѕР»СЊР·СѓРµРј СЂРµСЃСѓСЂСЃ-РІСЂР°С‡РµР№
                if queue_tag == "ecg" and not doctor_id:
                    # РС‰РµРј СЂРµСЃСѓСЂСЃ-РІСЂР°С‡Р° Р­РљР“
                    from app.models.user import User

                    ecg_resource = (
                        db.query(User)
                        .filter(User.username == "ecg_resource", User.is_active == True)
                        .first()
                    )
                    if ecg_resource:
                        doctor_id = ecg_resource.id
                    else:
                        logger.warning(
                            "Р­РљР“ СЂРµСЃСѓСЂСЃ-РІСЂР°С‡ РЅРµ РЅР°Р№РґРµРЅ РґР»СЏ queue_tag=%s", queue_tag
                        )
                        continue

                elif queue_tag == "lab" and not doctor_id:
                    # РС‰РµРј СЂРµСЃСѓСЂСЃ-РІСЂР°С‡Р° Р»Р°Р±РѕСЂР°С‚РѕСЂРёРё
                    from app.models.user import User

                    lab_resource = (
                        db.query(User)
                        .filter(User.username == "lab_resource", User.is_active == True)
                        .first()
                    )
                    if lab_resource:
                        # вњ… РРЎРџР РђР’Р›Р•РќРћ: РќР°С…РѕРґРёРј Doctor РїРѕ user_id РґР»СЏ РїСЂР°РІРёР»СЊРЅРѕРіРѕ specialist_id
                        lab_doctor = (
                            db.query(Doctor)
                            .filter(Doctor.user_id == lab_resource.id)
                            .first()
                        )
                        if lab_doctor:
                            doctor_id = (
                                lab_doctor.id
                            )  # РСЃРїРѕР»СЊР·СѓРµРј doctor_id, Р° РЅРµ user_id
                            logger.info(
                                f"Р”Р»СЏ queue_tag={queue_tag} РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ СЂРµСЃСѓСЂСЃ-РІСЂР°С‡: lab_resource (Doctor ID: {doctor_id})"
                            )
                        else:
                            logger.warning(
                                f"РЈ СЂРµСЃСѓСЂСЃ-РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ lab_resource (User ID: {lab_resource.id}) РЅРµС‚ Р·Р°РїРёСЃРё РІ С‚Р°Р±Р»РёС†Рµ doctors"
                            )
                            continue
                    else:
                        logger.warning(
                            "Р›Р°Р±РѕСЂР°С‚РѕСЂРёСЏ СЂРµСЃСѓСЂСЃ-РІСЂР°С‡ РЅРµ РЅР°Р№РґРµРЅ РґР»СЏ queue_tag=%s",
                            queue_tag,
                        )
                        continue

                daily_queue = crud_queue.get_or_create_daily_queue(
                    db, today, doctor_id, queue_tag
                )

                start_number = queue_settings.get("start_numbers", {}).get(queue_tag, 1)
                next_number = queue_service.get_next_queue_number(
                    db,
                    daily_queue=daily_queue,
                    queue_tag=queue_tag,
                    default_start=start_number,
                )

                queue_entry = queue_service.create_queue_entry(
                    db,
                    daily_queue=daily_queue,
                    patient_id=visit.patient_id,
                    number=next_number,
                    source="desk",
                )

                visit_queue_numbers.append(
                    {
                        "queue_tag": queue_tag,
                        "number": next_number,
                        "queue_id": daily_queue.id,
                    }
                )

            # РЎРѕС…СЂР°РЅСЏРµРј РІСЃРµ РЅРѕРјРµСЂР° РѕС‡РµСЂРµРґРµР№ РґР»СЏ РІРёР·РёС‚Р°
            queue_numbers[visit.id] = visit_queue_numbers
        except Exception as e:
            logger.warning(
                "Could not create queue entries for visit %d: %s",
                visit.id,
                e,
                exc_info=True,
            )

    return queue_numbers


# ===================== CLICK РРќРўР•Р“Р РђР¦РРЇ =====================


class InvoicePaymentRequest(BaseModel):
    invoice_id: int
    provider: str = Field(default="click")  # click|payme
    return_url: Optional[str] = None
    cancel_url: Optional[str] = None


class InvoicePaymentResponse(BaseModel):
    success: bool
    payment_url: Optional[str] = None
    provider_payment_id: Optional[str] = None
    error_message: Optional[str] = None


@router.post("/registrar/invoice/init-payment", response_model=InvoicePaymentResponse)
def init_invoice_payment(
    payment_req: InvoicePaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    РРЅРёС†РёР°С†РёСЏ РѕРїР»Р°С‚С‹ РґР»СЏ invoice С‡РµСЂРµР· Click/PayMe
    """
    try:
        # РџРѕР»СѓС‡Р°РµРј invoice
        invoice = (
            db.query(PaymentInvoice)
            .filter(PaymentInvoice.id == payment_req.invoice_id)
            .first()
        )
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice РЅРµ РЅР°Р№РґРµРЅ")

        if invoice.status != "pending":
            raise HTTPException(
                status_code=400, detail=f"Invoice СѓР¶Рµ РѕР±СЂР°Р±РѕС‚Р°РЅ: {invoice.status}"
            )

        # РРЅРёС†РёР°Р»РёР·РёСЂСѓРµРј РїСЂРѕРІР°Р№РґРµСЂ РїР»Р°С‚РµР¶РµР№
        if payment_req.provider == "click":
            from app.services.payment_providers.click import ClickProvider

            # РљРѕРЅС„РёРіСѓСЂР°С†РёСЏ Click (РІ СЂРµР°Р»СЊРЅРѕРј РїСЂРѕРµРєС‚Рµ РёР· РЅР°СЃС‚СЂРѕРµРє)
            provider_config = {
                "service_id": "test_service",
                "merchant_id": "test_merchant",
                "secret_key": "test_secret",
                "base_url": "https://api.click.uz/v2",
            }

            provider = ClickProvider(provider_config)

        elif payment_req.provider == "payme":
            from app.services.payment_providers.payme import PayMeProvider

            # РљРѕРЅС„РёРіСѓСЂР°С†РёСЏ PayMe (РІ СЂРµР°Р»СЊРЅРѕРј РїСЂРѕРµРєС‚Рµ РёР· РЅР°СЃС‚СЂРѕРµРє)
            provider_config = {
                "merchant_id": "test_merchant_payme",
                "secret_key": "test_secret_payme",
                "base_url": "https://checkout.paycom.uz",
                "api_url": "https://api.paycom.uz",
            }

            provider = PayMeProvider(provider_config)

        else:
            return InvoicePaymentResponse(
                success=False,
                error_message=f"РџСЂРѕРІР°Р№РґРµСЂ {payment_req.provider} РЅРµ РїРѕРґРґРµСЂР¶РёРІР°РµС‚СЃСЏ",
            )

        # РЎРѕР·РґР°С‘Рј РїР»Р°С‚С‘Р¶
        result = provider.create_payment(
            amount=invoice.total_amount,
            currency=invoice.currency,
            order_id=f"invoice_{invoice.id}",
            description=f"РћРїР»Р°С‚Р° РІРёР·РёС‚РѕРІ #{invoice.id}",
            return_url=payment_req.return_url,
            cancel_url=payment_req.cancel_url,
        )

        if result.success:
            # РћР±РЅРѕРІР»СЏРµРј invoice
            invoice.provider_payment_id = result.payment_id
            invoice.payment_method = payment_req.provider
            invoice.provider = payment_req.provider
            invoice.status = "processing"
            invoice.provider_data = result.provider_data
            db.commit()

            return InvoicePaymentResponse(
                success=True,
                payment_url=result.payment_url,
                provider_payment_id=result.payment_id,
            )
        else:
            return InvoicePaymentResponse(
                success=False, error_message=result.error_message
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"РћС€РёР±РєР° РёРЅРёС†РёР°С†РёРё РїР»Р°С‚РµР¶Р°: {str(e)}"
        )


@router.get("/registrar/invoice/{invoice_id}/status")
def check_invoice_status(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    РџСЂРѕРІРµСЂРєР° СЃС‚Р°С‚СѓСЃР° РѕРїР»Р°С‚С‹ invoice
    """
    try:
        invoice = (
            db.query(PaymentInvoice).filter(PaymentInvoice.id == invoice_id).first()
        )
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice РЅРµ РЅР°Р№РґРµРЅ")

        # Р•СЃР»Рё СЃС‚Р°С‚СѓСЃ СѓР¶Рµ С„РёРЅР°Р»СЊРЅС‹Р№, РІРѕР·РІСЂР°С‰Р°РµРј РєР°Рє РµСЃС‚СЊ
        if invoice.status in ["paid", "failed", "cancelled"]:
            return {
                "invoice_id": invoice.id,
                "status": invoice.status,
                "total_amount": invoice.total_amount,
                "currency": invoice.currency,
                "provider_payment_id": invoice.provider_payment_id,
            }

        # РџСЂРѕРІРµСЂСЏРµРј СЃС‚Р°С‚СѓСЃ Сѓ РїСЂРѕРІР°Р№РґРµСЂР°
        if invoice.provider_payment_id and invoice.provider:
            provider = None

            if invoice.provider == "click":
                from app.services.payment_providers.click import ClickProvider

                provider_config = {
                    "service_id": "test_service",
                    "merchant_id": "test_merchant",
                    "secret_key": "test_secret",
                    "base_url": "https://api.click.uz/v2",
                }

                provider = ClickProvider(provider_config)

            elif invoice.provider == "payme":
                from app.services.payment_providers.payme import PayMeProvider

                provider_config = {
                    "merchant_id": "test_merchant_payme",
                    "secret_key": "test_secret_payme",
                    "base_url": "https://checkout.paycom.uz",
                    "api_url": "https://api.paycom.uz",
                }

                provider = PayMeProvider(provider_config)

            if provider:
                result = provider.check_payment_status(invoice.provider_payment_id)

                if result.success:
                    # РћР±РЅРѕРІР»СЏРµРј СЃС‚Р°С‚СѓСЃ invoice
                    if result.status == "completed":
                        invoice.status = "paid"
                        invoice.paid_at = datetime.utcnow()

                        # [OK] РРЎРџР РђР’Р›Р•РќРћ: РЎРѕР·РґР°РµРј РїР»Р°С‚РµР¶Рё РґР»СЏ РІСЃРµС… РІРёР·РёС‚РѕРІ С‡РµСЂРµР· SSOT
                        from app.services.billing_service import BillingService

                        billing_service = BillingService(db)

                        # РџРѕРјРµС‡Р°РµРј РІСЃРµ РІРёР·РёС‚С‹ РєР°Рє РѕРїР»Р°С‡РµРЅРЅС‹Рµ Рё СЃРѕР·РґР°РµРј РїР»Р°С‚РµР¶Рё
                        invoice_visits = (
                            db.query(PaymentInvoiceVisit)
                            .filter(PaymentInvoiceVisit.invoice_id == invoice.id)
                            .all()
                        )

                        for iv in invoice_visits:
                            visit = (
                                db.query(Visit).filter(Visit.id == iv.visit_id).first()
                            )
                            if visit:
                                # РџСЂРѕРІРµСЂСЏРµРј, РЅРµ СЃРѕР·РґР°РЅ Р»Рё СѓР¶Рµ РїР»Р°С‚РµР¶
                                from app.models.payment import Payment

                                existing_payment = (
                                    db.query(Payment)
                                    .filter(
                                        Payment.visit_id == visit.id,
                                        Payment.status == "paid",
                                    )
                                    .first()
                                )

                                if not existing_payment:
                                    # РЎРѕР·РґР°РµРј РїР»Р°С‚РµР¶ С‡РµСЂРµР· SSOT
                                    payment = billing_service.create_payment(
                                        visit_id=visit.id,
                                        amount=float(iv.visit_amount),
                                        currency=invoice.currency,
                                        method="online",  # РћРЅР»Р°Р№РЅ РѕРїР»Р°С‚Р° С‡РµСЂРµР· РїСЂРѕРІР°Р№РґРµСЂР°
                                        status="paid",
                                        provider=invoice.provider,
                                        note=f"РћРїР»Р°С‚Р° С‡РµСЂРµР· {invoice.provider} (invoice {invoice.id})",
                                    )
                                    logger.info(
                                        "check_invoice_status: РЎРѕР·РґР°РЅ РїР»Р°С‚РµР¶ ID=%d РґР»СЏ РІРёР·РёС‚Р° %d",
                                        payment.id,
                                        visit.id,
                                    )

                                visit.status = "confirmed"  # РћРїР»Р°С‡РµРЅРѕ Рё РїРѕРґС‚РІРµСЂР¶РґРµРЅРѕ

                        db.commit()
                    elif result.status in ["failed", "cancelled"]:
                        invoice.status = result.status
                        db.commit()

        return {
            "invoice_id": invoice.id,
            "status": invoice.status,
            "total_amount": invoice.total_amount,
            "currency": invoice.currency,
            "provider_payment_id": invoice.provider_payment_id,
            "paid_at": invoice.paid_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"РћС€РёР±РєР° РїСЂРѕРІРµСЂРєРё СЃС‚Р°С‚СѓСЃР°: {str(e)}"
        )


@router.post(
    "/registrar/repeat-eligibility-preview",
    response_model=RepeatEligibilityPreviewResponse,
    summary="Preview eligibility for repeat discount in registrar wizard",
)
def preview_repeat_eligibility(
    payload: RepeatEligibilityPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    _ = current_user

    patient_exists = (
        db.query(Patient.id).filter(Patient.id == payload.patient_id).first() is not None
    )
    if not patient_exists:
        raise HTTPException(status_code=404, detail="РџР°С†РёРµРЅС‚ РЅРµ РЅР°Р№РґРµРЅ")

    settings = _load_registration_discount_settings(db)
    repeat_visit_days = int(settings.get("repeat_visit_days", 21) or 21)
    repeat_discount_percent = int(settings.get("repeat_visit_discount", 0) or 0)

    items = [
        _build_repeat_eligibility_preview_item(
            db,
            patient_id=payload.patient_id,
            candidate=candidate,
            repeat_visit_days=repeat_visit_days,
            repeat_discount_percent=repeat_discount_percent,
        )
        for candidate in payload.candidates
    ]

    return RepeatEligibilityPreviewResponse(patient_id=payload.patient_id, items=items)


# ===================== РћРЎРќРћР’РќРћР™ ENDPOINT =====================


@router.post("/registrar/cart", response_model=CartResponse)
def create_cart_appointments(
    cart_data: CartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    РЎРѕР·РґР°РЅРёРµ РєРѕСЂР·РёРЅС‹ РІРёР·РёС‚РѕРІ СЃ РµРґРёРЅС‹Рј РїР»Р°С‚РµР¶РѕРј
    РџРѕРґРґРµСЂР¶РёРІР°РµС‚: РїРѕРІС‚РѕСЂРЅС‹Рµ/Р»СЊРіРѕС‚РЅС‹Рµ РІРёР·РёС‚С‹, All Free, РґРёРЅР°РјРёС‡РµСЃРєРёРµ С†РµРЅС‹, РѕС‡РµСЂРµРґРё РїРѕ queue_tag
    """
    effective_discount_mode = _resolve_effective_discount_mode(cart_data)
    logger.info(
        "REGISTRATION: РџРѕР»СѓС‡РµРЅ Р·Р°РїСЂРѕСЃ РЅР° СЃРѕР·РґР°РЅРёРµ РєРѕСЂР·РёРЅС‹. Patient ID: %s, Р’РёР·РёС‚РѕРІ: %d, Discount mode: %s, Effective discount mode: %s, All free: %s, Payment method: %s",
        cart_data.patient_id,
        len(cart_data.visits),
        cart_data.discount_mode,
        effective_discount_mode,
        cart_data.all_free,
        cart_data.payment_method,
    )

    try:
        # Р’Р°Р»РёРґР°С†РёСЏ РїР°С†РёРµРЅС‚Р°
        # (РџСЂРµРґРїРѕР»Р°РіР°РµРј, С‡С‚Рѕ РїР°С†РёРµРЅС‚ СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚, С‚Р°Рє РєР°Рє РѕРЅ РІС‹Р±СЂР°РЅ РІ РјР°СЃС‚РµСЂРµ)

        # РџРѕР»СѓС‡Р°РµРј РЅР°СЃС‚СЂРѕР№РєРё РѕС‡РµСЂРµРґРё
        queue_settings = crud_clinic.get_queue_settings(db)
        registration_settings = _load_registration_discount_settings(db)

        created_visits = []
        created_visit_amounts: Dict[int, Decimal] = {}
        total_invoice_amount = Decimal('0')

        # РЎРѕР·РґР°С‘Рј РІРёР·РёС‚С‹
        from time import sleep

        logger.info("REGISTRATION: РЎРѕР·РґР°С‘Рј %d РІРёР·РёС‚РѕРІ", len(cart_data.visits))
        for idx, visit_req in enumerate(cart_data.visits):
            logger.debug(
                "REGISTRATION: Р’РёР·РёС‚ %d: department=%s, services=%d",
                idx + 1,
                visit_req.department,
                len(visit_req.services),
            )
            # РџСЂРѕРІРµСЂСЏРµРј РїСЂР°РІРѕ РЅР° РїРѕРІС‚РѕСЂРЅС‹Р№ РІРёР·РёС‚
            if effective_discount_mode == "repeat" and visit_req.doctor_id:
                service_ids = [s.service_id for s in visit_req.services]
                repeat_visit_days = int(registration_settings["repeat_visit_days"])
                if not _check_repeat_visit_eligibility(
                    db,
                    cart_data.patient_id,
                    visit_req.doctor_id,
                    service_ids,
                    days_window=repeat_visit_days,
                ):
                    raise HTTPException(
                        status_code=400,
                        detail=f"РџРѕРІС‚РѕСЂРЅС‹Р№ РІРёР·РёС‚ РЅРµРґРѕСЃС‚СѓРїРµРЅ: РЅРµС‚ РєРѕРЅСЃСѓР»СЊС‚Р°С†РёРё Сѓ СЌС‚РѕРіРѕ РІСЂР°С‡Р° Р·Р° РїРѕСЃР»РµРґРЅРёРµ {repeat_visit_days} РґРЅРµР№",
                    )

            # [OK] РРЎРџР РђР’Р›Р•РќРћ: Р РµРіРёСЃС‚СЂР°С‚РѕСЂ РІСЃРµРіРґР° СЃРѕР·РґР°С‘С‚ РїРѕРґС‚РІРµСЂР¶РґС‘РЅРЅС‹Рµ Р·Р°РїРёСЃРё
            # Р¤РёС‡Р°-С„Р»Р°Рі "confirmation_before_queue" РїСЂРёРјРµРЅСЏРµС‚СЃСЏ С‚РѕР»СЊРєРѕ РґР»СЏ РѕРЅР»Р°Р№РЅ-Р·Р°РїРёСЃРµР№ (С‚РµР»РµРіСЂР°Рј/PWA)
            # Р—Р°РїРёСЃРё РѕС‚ СЂРµРіРёСЃС‚СЂР°С‚РѕСЂР° СЃСЂР°Р·Сѓ РїРѕРїР°РґР°СЋС‚ РІ РѕС‡РµСЂРµРґСЊ
            visit_status = "confirmed"
            confirmed_at = datetime.utcnow()
            confirmed_by = f"registrar_{current_user.id}"

            # [OK] РРЎРџР РђР’Р›Р•РќРћ: Р”РѕР±Р°РІР»СЏРµРј РјРёРєСЂРѕР·Р°РґРµСЂР¶РєСѓ РґР»СЏ СЂР°Р·РЅС‹С… created_at
            # Р­С‚Рѕ РіР°СЂР°РЅС‚РёСЂСѓРµС‚, С‡С‚Рѕ РІРёР·РёС‚С‹ РѕРґРЅРѕРіРѕ РїР°С†РёРµРЅС‚Р° Р±СѓРґСѓС‚ РёРјРµС‚СЊ СЂР°Р·РЅС‹Рµ РІСЂРµРјРµРЅРЅС‹Рµ РјРµС‚РєРё
            if idx > 0:
                sleep(0.001)  # 1 РјРёР»Р»РёСЃРµРєСѓРЅРґР° Р·Р°РґРµСЂР¶РєРё РјРµР¶РґСѓ РІРёР·РёС‚Р°РјРё

            # РџРѕРґРіРѕС‚Р°РІР»РёРІР°РµРј СѓСЃР»СѓРіРё РґР»СЏ РїРµСЂРµРґР°С‡Рё РІ create_visit
            services_data = []
            visit_amount = Decimal("0")
            for service_item in visit_req.services:
                service = (
                    db.query(Service)
                    .filter(Service.id == service_item.service_id)
                    .first()
                )
                if not service:
                    raise HTTPException(
                        status_code=404,
                        detail=f"РЈСЃР»СѓРіР° СЃ ID {service_item.service_id} РЅРµ РЅР°Р№РґРµРЅР°",
                    )

                base_price = (
                    service_item.custom_price
                    if service_item.custom_price is not None
                    else service.price or Decimal("0")
                )
                item_price = _apply_service_discount(
                    Decimal(str(base_price)),
                    effective_discount_mode,
                    registration_settings,
                    service.is_consultation,
                )
                visit_amount += item_price * Decimal(service_item.quantity)

                services_data.append(
                    {
                        "service_id": service.id,
                        # в­ђ SSOT: РёСЃРїРѕР»СЊР·СѓРµРј canonical service_code helper
                        "code": service.service_code or get_service_code(service.id, db),
                        "name": service.name,
                        "qty": service_item.quantity,
                        "price": float(item_price),
                    }
                )

            # РЎРѕР·РґР°С‘Рј РІРёР·РёС‚ РёСЃРїРѕР»СЊР·СѓСЏ РµРґРёРЅСѓСЋ С„СѓРЅРєС†РёСЋ create_visit РґР»СЏ РѕР±РµСЃРїРµС‡РµРЅРёСЏ Single Source of Truth
            from app.crud.visit import create_visit

            visit = create_visit(
                db=db,
                patient_id=cart_data.patient_id,
                doctor_id=visit_req.doctor_id,
                visit_date=visit_req.visit_date,
                visit_time=visit_req.visit_time,
                department=visit_req.department,
                notes=visit_req.notes,
                discount_mode=effective_discount_mode,
                services=services_data,
                status=visit_status,
                approval_status=(
                    "approved"
                    if effective_discount_mode != "all_free"
                    or registration_settings["all_free_auto_approve"]
                    else "pending"
                ),
                confirmed_at=confirmed_at,
                confirmed_by=confirmed_by,
                auto_status=False,  # РЎС‚Р°С‚СѓСЃ СѓР¶Рµ СѓСЃС‚Р°РЅРѕРІР»РµРЅ РІС‹С€Рµ
                notify=False,  # РЈРІРµРґРѕРјР»РµРЅРёСЏ РѕС‚РїСЂР°РІР»СЏСЋС‚СЃСЏ РѕС‚РґРµР»СЊРЅРѕ
                log=True,
            )
            logger.info("REGISTRATION: Р’РёР·РёС‚ %d СЃРѕР·РґР°РЅ С‡РµСЂРµР· create_visit()", visit.id)

            created_visits.append(visit)
            created_visit_amounts[visit.id] = visit_amount
            total_invoice_amount += visit_amount
            logger.info(
                "REGISTRATION: Р’РёР·РёС‚ %d СЃРѕР·РґР°РЅ СѓСЃРїРµС€РЅРѕ РґР»СЏ РїР°С†РёРµРЅС‚Р° %d",
                visit.id,
                cart_data.patient_id,
            )

        # РЎРѕР·РґР°С‘Рј РµРґРёРЅС‹Р№ invoice
        logger.info("REGISTRATION: РЎРѕР·РґР°С‘Рј РёРЅРІРѕР№СЃ РЅР° СЃСѓРјРјСѓ %s", total_invoice_amount)
        invoice = PaymentInvoice(
            patient_id=cart_data.patient_id,
            total_amount=total_invoice_amount,
            currency="UZS",
            status="pending",
            payment_method=cart_data.payment_method,
            notes=cart_data.notes,
        )
        db.add(invoice)
        db.flush()  # РџРѕР»СѓС‡Р°РµРј ID invoice
        logger.info("REGISTRATION: РРЅРІРѕР№СЃ %d СЃРѕР·РґР°РЅ", invoice.id)

        # РЎРІСЏР·С‹РІР°РµРј РІРёР·РёС‚С‹ СЃ invoice
        for visit in created_visits:
            visit_amount = created_visit_amounts.get(visit.id, Decimal("0"))
            invoice_visit = PaymentInvoiceVisit(
                invoice_id=invoice.id, visit_id=visit.id, visit_amount=visit_amount
            )
            db.add(invoice_visit)

        # Assign queue entries for confirmed same-day visits via extracted seam.
        queue_numbers = {}
        today = date.today()

        queue_numbers = RegistrarWizardQueueAssignmentService(db).assign_same_day_queue_numbers(
            created_visits,
            target_day=today,
            source="desk",
        )

        db.commit()
        logger.info("REGISTRATION: РўСЂР°РЅР·Р°РєС†РёСЏ Р·Р°С„РёРєСЃРёСЂРѕРІР°РЅР° РІ Р±Р°Р·Рµ РґР°РЅРЅС‹С…")

        if effective_discount_mode == "all_free":
            for visit in created_visits:
                if visit.approval_status != "pending":
                    continue
                try:
                    asyncio.run(
                        notification_sender_service.send_all_free_request_notification(
                            db=db,
                            visit=visit,
                            actor_user=current_user,
                        )
                    )
                except Exception as notification_error:
                    logger.warning(
                        "[FIX:NOTIFICATIONS] failed to publish all_free_requested after cart commit",
                        extra={
                            "visit_id": visit.id,
                            "patient_id": cart_data.patient_id,
                            "actor_id": current_user.id,
                            "error": str(notification_error),
                        },
                    )

        # Р¤РѕСЂРјРёСЂСѓРµРј С‚Р°Р»РѕРЅС‹ РґР»СЏ РІРёР·РёС‚РѕРІ СЃ РїСЂРёСЃРІРѕРµРЅРЅС‹РјРё РЅРѕРјРµСЂР°РјРё РѕС‡РµСЂРµРґРµР№
        print_tickets = []
        # Р‘Р»РѕРє С„РѕСЂРјРёСЂРѕРІР°РЅРёСЏ С‚Р°Р»РѕРЅРѕРІ РїСЂРѕРїСѓСЃРєР°РµРј, С‚Р°Рє РєР°Рє queue_numbers РїСѓСЃС‚РѕР№

        # Р¤РѕСЂРјРёСЂСѓРµРј РёРЅС„РѕСЂРјР°С†РёСЋ Рѕ СЃРѕР·РґР°РЅРЅС‹С… РІРёР·РёС‚Р°С…
        created_visits_info = []
        try:
            for visit in created_visits:
                # РџРѕР»СѓС‡Р°РµРј РґР°РЅРЅС‹Рµ РїР°С†РёРµРЅС‚Р°
                patient = (
                    db.query(Patient).filter(Patient.id == visit.patient_id).first()
                )
                patient_name = (
                    patient.short_name() if patient else "РќРµРёР·РІРµСЃС‚РЅС‹Р№ РїР°С†РёРµРЅС‚"
                )

                # РџРѕР»СѓС‡Р°РµРј РґР°РЅРЅС‹Рµ РІСЂР°С‡Р°
                doctor = (
                    db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
                    if visit.doctor_id
                    else None
                )
                # [OK] РРЎРџР РђР’Р›Р•РќРћ: User РёРјРµРµС‚ full_name, Р° РЅРµ first_name/last_name
                if doctor and doctor.user_id:
                    user = db.query(User).filter(User.id == doctor.user_id).first()
                    doctor_name = (
                        (user.full_name or user.username) if user else "Р‘РµР· РІСЂР°С‡Р°"
                    )
                else:
                    doctor_name = "Р‘РµР· РІСЂР°С‡Р°"

                # РџРѕР»СѓС‡Р°РµРј СѓСЃР»СѓРіРё РІРёР·РёС‚Р°
                visit_services = (
                    db.query(VisitService)
                    .filter(VisitService.visit_id == visit.id)
                    .all()
                )
                services_info = []
                for vs in visit_services:
                    services_info.append(
                        {
                            "name": vs.name,
                            "code": (
                                normalize_service_code(vs.code) if vs.code else None
                            ),
                            "quantity": vs.qty,
                            "price": float(vs.price) if vs.price else 0,
                        }
                    )

                created_visits_info.append(
                    {
                        "visit_id": visit.id,
                        "patient_name": patient_name,
                        "doctor_name": doctor_name,
                        "visit_date": visit.visit_date.isoformat(),
                        "visit_time": visit.visit_time,
                        "status": visit.status,
                        "department": visit.department,
                        "services": services_info,
                        "confirmation_required": visit.status == "pending_confirmation",
                        "confirmation_token": (
                            visit.confirmation_token
                            if visit.status == "pending_confirmation"
                            else None
                        ),
                    }
                )
        except Exception as e:
            logger.warning(
                "REGISTRATION: РћС€РёР±РєР° С„РѕСЂРјРёСЂРѕРІР°РЅРёСЏ РѕС‚РІРµС‚Р° (РІРёР·РёС‚С‹ СѓР¶Рµ СЃРѕС…СЂР°РЅРµРЅС‹): %s",
                str(e),
                exc_info=True,
            )
            # Р’РёР·РёС‚С‹ СѓР¶Рµ СЃРѕС…СЂР°РЅРµРЅС‹, РїРѕСЌС‚РѕРјСѓ РЅРµ РѕС‚РєР°С‚С‹РІР°РµРј С‚СЂР°РЅР·Р°РєС†РёСЋ

        # РћРїСЂРµРґРµР»СЏРµРј СЃРѕРѕР±С‰РµРЅРёРµ РІ Р·Р°РІРёСЃРёРјРѕСЃС‚Рё РѕС‚ СЂРµР·СѓР»СЊС‚Р°С‚Р°
        if queue_numbers:
            message = f"РљРѕСЂР·РёРЅР° СЃРѕР·РґР°РЅР° СѓСЃРїРµС€РЅРѕ. РџСЂРёСЃРІРѕРµРЅРѕ РЅРѕРјРµСЂРѕРІ РІ РѕС‡РµСЂРµРґСЏС…: {sum(len(assignments) for assignments in queue_numbers.values())}"
        else:
            message = "Р’РёР·РёС‚С‹ СЃРѕР·РґР°РЅС‹. РќРѕРјРµСЂР° РІ РѕС‡РµСЂРµРґСЏС… Р±СѓРґСѓС‚ РїСЂРёСЃРІРѕРµРЅС‹ РІ РґРµРЅСЊ РІРёР·РёС‚Р°."

        logger.info(
            "REGISTRATION: РљРѕСЂР·РёРЅР° СЃРѕР·РґР°РЅР° СѓСЃРїРµС€РЅРѕ. РЎРѕР·РґР°РЅРѕ РІРёР·РёС‚РѕРІ: %d, ID РІРёР·РёС‚РѕРІ: %s, Invoice ID: %d, Total amount: %s",
            len(created_visits),
            [v.id for v in created_visits],
            invoice.id,
            total_invoice_amount,
        )

        return CartResponse(
            success=True,
            message=message,
            invoice_id=invoice.id,
            visit_ids=[v.id for v in created_visits],
            total_amount=total_invoice_amount,
            queue_numbers=queue_numbers,
            print_tickets=print_tickets,
            created_visits=created_visits_info,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("REGISTRATION: РћС€РёР±РєР° СЃРѕР·РґР°РЅРёСЏ РєРѕСЂР·РёРЅС‹: %s", str(e), exc_info=True)
        import traceback

        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"РћС€РёР±РєР° СЃРѕР·РґР°РЅРёСЏ РєРѕСЂР·РёРЅС‹: {str(e)}\nTRACE: {traceback.format_exc()}",
        )


# ===================== РЈРџР РђР’Р›Р•РќРР• РР—РњР•РќР•РќРРЇРњР Р¦Р•Рќ =====================


class PriceOverrideApprovalRequest(BaseModel):
    override_id: int
    action: str = Field(..., pattern="^(approve|reject)$")  # approve РёР»Рё reject
    rejection_reason: Optional[str] = None


class PriceOverrideListResponse(BaseModel):
    id: int
    visit_id: int
    service_id: int
    service_name: str
    doctor_name: str
    doctor_specialty: str
    patient_name: Optional[str]
    original_price: Decimal
    new_price: Decimal
    reason: str
    details: Optional[str]
    status: str
    created_at: datetime


@router.get(
    "/registrar/price-overrides", summary="РџРѕР»СѓС‡РёС‚СЊ РІСЃРµ РёР·РјРµРЅРµРЅРёСЏ С†РµРЅ РґР»СЏ РѕРґРѕР±СЂРµРЅРёСЏ"
)
def get_pending_price_overrides(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
    status_filter: Optional[str] = Query(
        default="pending", pattern="^(pending|approved|rejected|all)$"
    ),
    limit: int = Query(default=50, ge=1, le=100),
) -> List[PriceOverrideListResponse]:
    """
    РџРѕР»СѓС‡РёС‚СЊ СЃРїРёСЃРѕРє РёР·РјРµРЅРµРЅРёР№ С†РµРЅ РґР»СЏ РѕРґРѕР±СЂРµРЅРёСЏ СЂРµРіРёСЃС‚СЂР°С‚СѓСЂРѕР№
    """
    try:
        query = db.query(DoctorPriceOverride).join(Service).join(Doctor)

        if status_filter != "all":
            query = query.filter(DoctorPriceOverride.status == status_filter)

        overrides = (
            query.order_by(DoctorPriceOverride.created_at.desc()).limit(limit).all()
        )

        result = []
        for override in overrides:
            # РџРѕР»СѓС‡Р°РµРј РґР°РЅРЅС‹Рµ РІРёР·РёС‚Р° Рё РїР°С†РёРµРЅС‚Р°
            visit = db.query(Visit).filter(Visit.id == override.visit_id).first()
            patient_name = None
            if visit:
                # Р—РґРµСЃСЊ РЅСѓР¶РЅРѕ РїРѕР»СѓС‡РёС‚СЊ РёРјСЏ РїР°С†РёРµРЅС‚Р° РёР· РјРѕРґРµР»Рё Patient
                # РџРѕРєР° РёСЃРїРѕР»СЊР·СѓРµРј Р·Р°РіР»СѓС€РєСѓ
                patient_name = f"РџР°С†РёРµРЅС‚ #{visit.patient_id}"

            result.append(
                PriceOverrideListResponse(
                    id=override.id,
                    visit_id=override.visit_id,
                    service_id=override.service_id,
                    service_name=override.service.name,
                    doctor_name=f"Р’СЂР°С‡ #{override.doctor.id}",  # Р—РґРµСЃСЊ РЅСѓР¶РЅРѕ РїРѕР»СѓС‡РёС‚СЊ РёРјСЏ РІСЂР°С‡Р°
                    doctor_specialty=override.doctor.specialty,
                    patient_name=patient_name,
                    original_price=override.original_price,
                    new_price=override.new_price,
                    reason=override.reason,
                    details=override.details,
                    status=override.status,
                    created_at=override.created_at,
                )
            )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ РёР·РјРµРЅРµРЅРёР№ С†РµРЅ: {str(e)}",
        )


@router.post(
    "/registrar/price-override/approve", summary="РћРґРѕР±СЂРёС‚СЊ РёР»Рё РѕС‚РєР»РѕРЅРёС‚СЊ РёР·РјРµРЅРµРЅРёРµ С†РµРЅС‹"
)
def approve_price_override(
    approval_data: PriceOverrideApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
) -> Dict[str, Any]:
    """
    РћРґРѕР±СЂРёС‚СЊ РёР»Рё РѕС‚РєР»РѕРЅРёС‚СЊ РёР·РјРµРЅРµРЅРёРµ С†РµРЅС‹ РІСЂР°С‡РѕРј
    """
    try:
        # РџРѕР»СѓС‡Р°РµРј РёР·РјРµРЅРµРЅРёРµ С†РµРЅС‹
        override = (
            db.query(DoctorPriceOverride)
            .filter(DoctorPriceOverride.id == approval_data.override_id)
            .first()
        )

        if not override:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="РР·РјРµРЅРµРЅРёРµ С†РµРЅС‹ РЅРµ РЅР°Р№РґРµРЅРѕ",
            )

        if override.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"РР·РјРµРЅРµРЅРёРµ С†РµРЅС‹ СѓР¶Рµ РѕР±СЂР°Р±РѕС‚Р°РЅРѕ (СЃС‚Р°С‚СѓСЃ: {override.status})",
            )

        # РћР±РЅРѕРІР»СЏРµРј СЃС‚Р°С‚СѓСЃ
        if approval_data.action == "approve":
            override.status = "approved"
            override.approved_by = current_user.id
            override.approved_at = datetime.utcnow()

            # РћР±РЅРѕРІР»СЏРµРј С†РµРЅСѓ РІ РІРёР·РёС‚Рµ
            visit = db.query(Visit).filter(Visit.id == override.visit_id).first()
            if visit:
                # РћР±РЅРѕРІР»СЏРµРј doctor_price_override РІ JSON РїРѕР»Рµ
                if not visit.doctor_price_override:
                    visit.doctor_price_override = {}

                visit.doctor_price_override[str(override.service_id)] = {
                    "original_price": float(override.original_price),
                    "new_price": float(override.new_price),
                    "override_id": override.id,
                    "approved_at": override.approved_at.isoformat(),
                }

            message = "РР·РјРµРЅРµРЅРёРµ С†РµРЅС‹ РѕРґРѕР±СЂРµРЅРѕ"

        elif approval_data.action == "reject":
            override.status = "rejected"
            override.approved_by = current_user.id
            override.approved_at = datetime.utcnow()
            override.rejection_reason = approval_data.rejection_reason

            message = "РР·РјРµРЅРµРЅРёРµ С†РµРЅС‹ РѕС‚РєР»РѕРЅРµРЅРѕ"

        db.commit()
        db.refresh(override)

        return {
            "success": True,
            "message": message,
            "override_id": override.id,
            "new_status": override.status,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё РёР·РјРµРЅРµРЅРёСЏ С†РµРЅС‹: {str(e)}",
        )


# ===================== РЈРџР РђР’Р›Р•РќРР• Р›Р¬Р“РћРўРђРњР ALL FREE =====================


class AllFreeApprovalRequest(BaseModel):
    visit_id: int
    action: str = Field(..., pattern="^(approve|reject)$")  # approve РёР»Рё reject
    rejection_reason: Optional[str] = None


class AllFreeVisitResponse(BaseModel):
    id: int
    patient_id: int
    patient_name: Optional[str]
    patient_phone: Optional[str]
    services: List[str]
    total_original_amount: Decimal
    doctor_name: Optional[str]
    doctor_specialty: Optional[str]
    visit_date: Optional[date]
    visit_time: Optional[str]
    notes: Optional[str]
    created_at: datetime
    approval_status: str


@router.get(
    "/admin/all-free-requests", summary="РџРѕР»СѓС‡РёС‚СЊ Р·Р°СЏРІРєРё All Free РґР»СЏ РѕРґРѕР±СЂРµРЅРёСЏ"
)
def get_all_free_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
    status_filter: Optional[str] = Query(
        default="pending", pattern="^(pending|approved|rejected|all)$"
    ),
    limit: int = Query(default=50, ge=1, le=100),
) -> List[AllFreeVisitResponse]:
    """
    РџРѕР»СѓС‡РёС‚СЊ СЃРїРёСЃРѕРє Р·Р°СЏРІРѕРє All Free РґР»СЏ РѕРґРѕР±СЂРµРЅРёСЏ Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂРѕРј
    """
    try:
        query = db.query(Visit).filter(Visit.discount_mode == "all_free")

        if status_filter != "all":
            query = query.filter(Visit.approval_status == status_filter)

        visits = query.order_by(Visit.created_at.desc()).limit(limit).all()

        result = []
        for visit in visits:
            # РџРѕР»СѓС‡Р°РµРј СѓСЃР»СѓРіРё РІРёР·РёС‚Р°
            visit_services = (
                db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
            )
            service_names = []
            total_original_amount = Decimal('0')

            for vs in visit_services:
                service = db.query(Service).filter(Service.id == vs.service_id).first()
                if service:
                    service_names.append(service.name)
                    total_original_amount += (service.price or Decimal('0')) * vs.qty

            # РџРѕР»СѓС‡Р°РµРј РґР°РЅРЅС‹Рµ РІСЂР°С‡Р°
            doctor_name = None
            doctor_specialty = None
            if visit.doctor_id:
                try:
                    doctor = (
                        db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
                    )
                    if doctor:
                        # РџРѕР»СѓС‡Р°РµРј РёРјСЏ РІСЂР°С‡Р° РёР· СЃРІСЏР·Р°РЅРЅРѕРіРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
                        # [OK] РРЎРџР РђР’Р›Р•РќРћ: РСЃРїРѕР»СЊР·СѓРµРј СЏРІРЅС‹Р№ Р·Р°РїСЂРѕСЃ РІРјРµСЃС‚Рѕ relationship, С‡С‚РѕР±С‹ РёР·Р±РµР¶Р°С‚СЊ РѕС€РёР±РѕРє
                        if doctor.user_id:
                            user = (
                                db.query(User).filter(User.id == doctor.user_id).first()
                            )
                            if user:
                                # [OK] РРЎРџР РђР’Р›Р•РќРћ: User РёРјРµРµС‚ full_name, Р° РЅРµ first_name/last_name
                                doctor_name = (
                                    (user.full_name or user.username)
                                    if user
                                    else f"Р’СЂР°С‡ #{doctor.id}"
                                )
                            else:
                                doctor_name = f"Р’СЂР°С‡ #{doctor.id}"
                        else:
                            doctor_name = f"Р’СЂР°С‡ #{doctor.id}"
                        doctor_specialty = doctor.specialty
                except Exception as e:
                    logger.warning(
                        "get_all_free_requests: РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ РґР°РЅРЅС‹С… РІСЂР°С‡Р° РґР»СЏ visit %d: %s",
                        visit.id,
                        e,
                        exc_info=True,
                    )
                    doctor_name = f"Р’СЂР°С‡ #{visit.doctor_id}"
                    doctor_specialty = None

            # [OK] РРЎРџР РђР’Р›Р•РќРћ: РџРѕР»СѓС‡Р°РµРј СЂРµР°Р»СЊРЅС‹Рµ РґР°РЅРЅС‹Рµ РїР°С†РёРµРЅС‚Р°
            patient_name = f"РџР°С†РёРµРЅС‚ #{visit.patient_id}"
            patient_phone = None
            if visit.patient_id:
                patient = (
                    db.query(Patient).filter(Patient.id == visit.patient_id).first()
                )
                if patient:
                    # Р¤РѕСЂРјРёСЂСѓРµРј Р¤РРћ РїР°С†РёРµРЅС‚Р°
                    name_parts = []
                    if patient.last_name:
                        name_parts.append(patient.last_name)
                    if patient.first_name:
                        name_parts.append(patient.first_name)
                    if patient.middle_name:
                        name_parts.append(patient.middle_name)
                    patient_name = (
                        ' '.join(name_parts)
                        if name_parts
                        else f"РџР°С†РёРµРЅС‚ #{visit.patient_id}"
                    )
                    patient_phone = patient.phone

            result.append(
                AllFreeVisitResponse(
                    id=visit.id,
                    patient_id=visit.patient_id,
                    patient_name=patient_name,
                    patient_phone=patient_phone,
                    services=service_names,
                    total_original_amount=total_original_amount,
                    doctor_name=doctor_name,
                    doctor_specialty=doctor_specialty,
                    visit_date=visit.visit_date,
                    visit_time=visit.visit_time,
                    notes=visit.notes,
                    created_at=visit.created_at,
                    approval_status=visit.approval_status,
                )
            )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ Р·Р°СЏРІРѕРє All Free: {str(e)}",
        )


@router.post(
    "/admin/all-free-approve", summary="РћРґРѕР±СЂРёС‚СЊ РёР»Рё РѕС‚РєР»РѕРЅРёС‚СЊ Р·Р°СЏРІРєСѓ All Free"
)
def approve_all_free_request(
    approval_data: AllFreeApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
) -> Dict[str, Any]:
    """
    РћРґРѕР±СЂРёС‚СЊ РёР»Рё РѕС‚РєР»РѕРЅРёС‚СЊ Р·Р°СЏРІРєСѓ All Free Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂРѕРј
    """
    try:
        # РџРѕР»СѓС‡Р°РµРј РІРёР·РёС‚
        visit = db.query(Visit).filter(Visit.id == approval_data.visit_id).first()

        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Р’РёР·РёС‚ РЅРµ РЅР°Р№РґРµРЅ"
            )

        if visit.discount_mode != "all_free":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Р­С‚Рѕ РЅРµ Р·Р°СЏРІРєР° All Free"
            )

        if visit.approval_status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Р—Р°СЏРІРєР° СѓР¶Рµ РѕР±СЂР°Р±РѕС‚Р°РЅР° (СЃС‚Р°С‚СѓСЃ: {visit.approval_status})",
            )

        # РћР±РЅРѕРІР»СЏРµРј СЃС‚Р°С‚СѓСЃ
        if approval_data.action == "approve":
            visit.approval_status = "approved"
            message = "Р—Р°СЏРІРєР° All Free РѕРґРѕР±СЂРµРЅР°"

        elif approval_data.action == "reject":
            visit.approval_status = "rejected"
            # РњРѕР¶РЅРѕ РґРѕР±Р°РІРёС‚СЊ РїРѕР»Рµ РґР»СЏ РїСЂРёС‡РёРЅС‹ РѕС‚РєР»РѕРЅРµРЅРёСЏ РІ РјРѕРґРµР»СЊ Visit
            if approval_data.rejection_reason:
                visit.notes = (
                    visit.notes or ""
                ) + f"\nРћС‚РєР»РѕРЅРµРЅРѕ: {approval_data.rejection_reason}"

            message = "Р—Р°СЏРІРєР° All Free РѕС‚РєР»РѕРЅРµРЅР°"

        db.commit()
        db.refresh(visit)

        try:
            asyncio.run(
                notification_sender_service.send_all_free_decision_notification(
                    db=db,
                    visit=visit,
                    actor_user=current_user,
                    rejection_reason=approval_data.rejection_reason,
                )
            )
        except Exception as notification_error:
            logger.warning(
                "[FIX:NOTIFICATIONS] failed to publish all_free decision notification",
                extra={
                    "visit_id": visit.id,
                    "approval_status": visit.approval_status,
                    "actor_id": current_user.id,
                    "error": str(notification_error),
                },
            )

        return {
            "success": True,
            "message": message,
            "visit_id": visit.id,
            "new_status": visit.approval_status,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё Р·Р°СЏРІРєРё All Free: {str(e)}",
        )


# ===================== РќРђРЎРўР РћР™РљР Р›Р¬Р“РћРў =====================


class BenefitSettingsRequest(BaseModel):
    repeat_visit_days: int = Field(
        default=21, ge=1, le=365
    )  # РћРєРЅРѕ РїРѕРІС‚РѕСЂРЅРѕРіРѕ РІРёР·РёС‚Р° РІ РґРЅСЏС…
    repeat_visit_discount: int = Field(
        default=0, ge=0, le=100
    )  # РЎРєРёРґРєР° РЅР° РїРѕРІС‚РѕСЂРЅС‹Р№ РІРёР·РёС‚ РІ %
    benefit_consultation_free: bool = Field(
        default=True
    )  # Р›СЊРіРѕС‚РЅС‹Рµ РєРѕРЅСЃСѓР»СЊС‚Р°С†РёРё Р±РµСЃРїР»Р°С‚РЅС‹
    all_free_auto_approve: bool = Field(default=False)  # РђРІС‚РѕРѕРґРѕР±СЂРµРЅРёРµ All Free Р·Р°СЏРІРѕРє


class BenefitSettingsResponse(BaseModel):
    repeat_visit_days: int
    repeat_visit_discount: int
    benefit_consultation_free: bool
    all_free_auto_approve: bool
    updated_at: datetime


@router.get("/admin/benefit-settings", summary="РџРѕР»СѓС‡РёС‚СЊ РЅР°СЃС‚СЂРѕР№РєРё Р»СЊРіРѕС‚")
def get_benefit_settings(
    db: Session = Depends(get_db), current_user: User = Depends(require_roles("Admin"))
) -> BenefitSettingsResponse:
    """
    РџРѕР»СѓС‡РёС‚СЊ С‚РµРєСѓС‰РёРµ РЅР°СЃС‚СЂРѕР№РєРё Р»СЊРіРѕС‚ Рё РїРѕРІС‚РѕСЂРЅС‹С… РІРёР·РёС‚РѕРІ
    """
    try:
        # РџРѕР»СѓС‡Р°РµРј РЅР°СЃС‚СЂРѕР№РєРё РёР· Р±Р°Р·С‹ РґР°РЅРЅС‹С…
        settings = {}

        # РћРєРЅРѕ РїРѕРІС‚РѕСЂРЅРѕРіРѕ РІРёР·РёС‚Р° (РґРЅРё)
        repeat_days_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == "repeat_visit_days")
            .first()
        )
        settings['repeat_visit_days'] = (
            int(repeat_days_setting.value) if repeat_days_setting else 21
        )

        # РЎРєРёРґРєР° РЅР° РїРѕРІС‚РѕСЂРЅС‹Р№ РІРёР·РёС‚ (%)
        repeat_discount_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == "repeat_visit_discount")
            .first()
        )
        settings['repeat_visit_discount'] = (
            int(repeat_discount_setting.value) if repeat_discount_setting else 0
        )

        # Р›СЊРіРѕС‚РЅС‹Рµ РєРѕРЅСЃСѓР»СЊС‚Р°С†РёРё Р±РµСЃРїР»Р°С‚РЅС‹
        benefit_free_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == "benefit_consultation_free")
            .first()
        )
        settings['benefit_consultation_free'] = (
            bool(benefit_free_setting.value) if benefit_free_setting else True
        )

        # РђРІС‚РѕРѕРґРѕР±СЂРµРЅРёРµ All Free Р·Р°СЏРІРѕРє
        auto_approve_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == "all_free_auto_approve")
            .first()
        )
        settings['all_free_auto_approve'] = (
            bool(auto_approve_setting.value) if auto_approve_setting else False
        )

        # Р’СЂРµРјСЏ РїРѕСЃР»РµРґРЅРµРіРѕ РѕР±РЅРѕРІР»РµРЅРёСЏ
        latest_update = (
            db.query(ClinicSettings)
            .filter(
                ClinicSettings.key.in_(
                    [
                        "repeat_visit_days",
                        "repeat_visit_discount",
                        "benefit_consultation_free",
                        "all_free_auto_approve",
                    ]
                )
            )
            .order_by(ClinicSettings.updated_at.desc())
            .first()
        )

        updated_at = latest_update.updated_at if latest_update else datetime.utcnow()

        return BenefitSettingsResponse(
            repeat_visit_days=settings['repeat_visit_days'],
            repeat_visit_discount=settings['repeat_visit_discount'],
            benefit_consultation_free=settings['benefit_consultation_free'],
            all_free_auto_approve=settings['all_free_auto_approve'],
            updated_at=updated_at,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ РЅР°СЃС‚СЂРѕРµРє Р»СЊРіРѕС‚: {str(e)}",
        )


@router.post("/admin/benefit-settings", summary="РћР±РЅРѕРІРёС‚СЊ РЅР°СЃС‚СЂРѕР№РєРё Р»СЊРіРѕС‚")
def update_benefit_settings(
    settings_data: BenefitSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
) -> Dict[str, Any]:
    """
    РћР±РЅРѕРІРёС‚СЊ РЅР°СЃС‚СЂРѕР№РєРё Р»СЊРіРѕС‚ Рё РїРѕРІС‚РѕСЂРЅС‹С… РІРёР·РёС‚РѕРІ
    """
    try:
        # РЎРїРёСЃРѕРє РЅР°СЃС‚СЂРѕРµРє РґР»СЏ РѕР±РЅРѕРІР»РµРЅРёСЏ
        settings_to_update = [
            {
                "key": "repeat_visit_days",
                "value": settings_data.repeat_visit_days,
                "description": "РћРєРЅРѕ РїРѕРІС‚РѕСЂРЅРѕРіРѕ РІРёР·РёС‚Р° РІ РґРЅСЏС…",
            },
            {
                "key": "repeat_visit_discount",
                "value": settings_data.repeat_visit_discount,
                "description": "РЎРєРёРґРєР° РЅР° РїРѕРІС‚РѕСЂРЅС‹Р№ РІРёР·РёС‚ РІ РїСЂРѕС†РµРЅС‚Р°С…",
            },
            {
                "key": "benefit_consultation_free",
                "value": settings_data.benefit_consultation_free,
                "description": "Р›СЊРіРѕС‚РЅС‹Рµ РєРѕРЅСЃСѓР»СЊС‚Р°С†РёРё Р±РµСЃРїР»Р°С‚РЅС‹",
            },
            {
                "key": "all_free_auto_approve",
                "value": settings_data.all_free_auto_approve,
                "description": "РђРІС‚РѕРјР°С‚РёС‡РµСЃРєРѕРµ РѕРґРѕР±СЂРµРЅРёРµ All Free Р·Р°СЏРІРѕРє",
            },
        ]

        # РћР±РЅРѕРІР»СЏРµРј РєР°Р¶РґСѓСЋ РЅР°СЃС‚СЂРѕР№РєСѓ
        for setting_data in settings_to_update:
            setting = (
                db.query(ClinicSettings)
                .filter(ClinicSettings.key == setting_data["key"])
                .first()
            )

            if setting:
                # РћР±РЅРѕРІР»СЏРµРј СЃСѓС‰РµСЃС‚РІСѓСЋС‰СѓСЋ РЅР°СЃС‚СЂРѕР№РєСѓ
                setting.value = setting_data["value"]
                setting.updated_by = current_user.id
                setting.updated_at = datetime.utcnow()
            else:
                # РЎРѕР·РґР°С‘Рј РЅРѕРІСѓСЋ РЅР°СЃС‚СЂРѕР№РєСѓ
                setting = ClinicSettings(
                    key=setting_data["key"],
                    value=setting_data["value"],
                    category="benefits",
                    description=setting_data["description"],
                    updated_by=current_user.id,
                )
                db.add(setting)

        db.commit()

        return {
            "success": True,
            "message": "РќР°СЃС‚СЂРѕР№РєРё Р»СЊРіРѕС‚ РѕР±РЅРѕРІР»РµРЅС‹ СѓСЃРїРµС€РЅРѕ",
            "settings": {
                "repeat_visit_days": settings_data.repeat_visit_days,
                "repeat_visit_discount": settings_data.repeat_visit_discount,
                "benefit_consultation_free": settings_data.benefit_consultation_free,
                "all_free_auto_approve": settings_data.all_free_auto_approve,
            },
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"РћС€РёР±РєР° РѕР±РЅРѕРІР»РµРЅРёСЏ РЅР°СЃС‚СЂРѕРµРє Р»СЊРіРѕС‚: {str(e)}",
        )


# ==================== РќРђРЎРўР РћР™РљР РњРђРЎРўР•Р Рђ Р Р•Р“РРЎРўР РђР¦РР ====================


class WizardSettingsResponse(BaseModel):
    use_new_wizard: bool
    updated_at: datetime


class WizardSettingsRequest(BaseModel):
    use_new_wizard: bool = Field(
        default=False, description="РСЃРїРѕР»СЊР·РѕРІР°С‚СЊ РЅРѕРІС‹Р№ РјР°СЃС‚РµСЂ СЂРµРіРёСЃС‚СЂР°С†РёРё"
    )


@router.get("/admin/wizard-settings", summary="РџРѕР»СѓС‡РёС‚СЊ РЅР°СЃС‚СЂРѕР№РєРё РјР°СЃС‚РµСЂР° СЂРµРіРёСЃС‚СЂР°С†РёРё")
def get_wizard_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """РџРѕР»СѓС‡РёС‚СЊ РЅР°СЃС‚СЂРѕР№РєРё РјР°СЃС‚РµСЂР° СЂРµРіРёСЃС‚СЂР°С†РёРё"""
    try:
        # РџРѕР»СѓС‡Р°РµРј РЅР°СЃС‚СЂРѕР№РєСѓ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ РЅРѕРІРѕРіРѕ РјР°СЃС‚РµСЂР°
        use_new_wizard_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == "wizard_use_new_version")
            .first()
        )

        use_new_wizard = False
        updated_at = datetime.utcnow()

        if use_new_wizard_setting:
            use_new_wizard = (
                use_new_wizard_setting.value.get("enabled", False)
                if use_new_wizard_setting.value
                else False
            )
            updated_at = use_new_wizard_setting.updated_at or updated_at

        return WizardSettingsResponse(
            use_new_wizard=use_new_wizard, updated_at=updated_at
        )

    except Exception as e:
        logger.error(f"Error getting wizard settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="РћС€РёР±РєР° РїСЂРё РїРѕР»СѓС‡РµРЅРёРё РЅР°СЃС‚СЂРѕРµРє РјР°СЃС‚РµСЂР°",
        )


@router.post("/admin/wizard-settings", summary="РћР±РЅРѕРІРёС‚СЊ РЅР°СЃС‚СЂРѕР№РєРё РјР°СЃС‚РµСЂР° СЂРµРіРёСЃС‚СЂР°С†РёРё")
def update_wizard_settings(
    settings_data: WizardSettingsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """РћР±РЅРѕРІРёС‚СЊ РЅР°СЃС‚СЂРѕР№РєРё РјР°СЃС‚РµСЂР° СЂРµРіРёСЃС‚СЂР°С†РёРё"""
    try:
        # РћР±РЅРѕРІР»СЏРµРј РёР»Рё СЃРѕР·РґР°РµРј РЅР°СЃС‚СЂРѕР№РєСѓ
        use_new_wizard_setting = (
            db.query(ClinicSettings)
            .filter(ClinicSettings.key == "wizard_use_new_version")
            .first()
        )

        if not use_new_wizard_setting:
            use_new_wizard_setting = ClinicSettings(
                key="wizard_use_new_version",
                category="wizard",
                description="РСЃРїРѕР»СЊР·РѕРІР°С‚СЊ РЅРѕРІС‹Р№ РјР°СЃС‚РµСЂ СЂРµРіРёСЃС‚СЂР°С†РёРё РІРјРµСЃС‚Рѕ СЃС‚Р°СЂРѕРіРѕ",
            )
            db.add(use_new_wizard_setting)

        use_new_wizard_setting.value = {
            "enabled": settings_data.use_new_wizard,
            "updated_by": current_user.id,
        }
        use_new_wizard_setting.updated_by = current_user.id
        use_new_wizard_setting.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(use_new_wizard_setting)

        settings_response = WizardSettingsResponse(
            use_new_wizard=settings_data.use_new_wizard,
            updated_at=use_new_wizard_setting.updated_at,
        )

        return {
            "success": True,
            "message": f"РќР°СЃС‚СЂРѕР№РєРё РјР°СЃС‚РµСЂР° РѕР±РЅРѕРІР»РµРЅС‹. {'Р’РєР»СЋС‡РµРЅ РЅРѕРІС‹Р№ РјР°СЃС‚РµСЂ' if settings_data.use_new_wizard else 'Р’РєР»СЋС‡РµРЅ СЃС‚Р°СЂС‹Р№ РјР°СЃС‚РµСЂ'}",
            "settings": settings_response,
        }

    except Exception as e:
        logger.error(f"Error updating wizard settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="РћС€РёР±РєР° РїСЂРё РѕР±РЅРѕРІР»РµРЅРёРё РЅР°СЃС‚СЂРѕРµРє РјР°СЃС‚РµСЂР°",
        )


# ===================== Р­РќР”РџРћРРќРў Р”Р›РЇ РџРћР›РЈР§Р•РќРРЇ Р—РђРџРРЎР•Р™ РР— VISITS =====================


class VisitResponse(BaseModel):
    id: int
    patient_id: int
    patient_fio: Optional[str] = None
    patient_phone: Optional[str] = None
    doctor_id: Optional[int] = None
    doctor_name: Optional[str] = None
    doctor_specialty: Optional[str] = None
    department: Optional[str] = None
    visit_date: Optional[date] = None
    visit_time: Optional[str] = None
    status: str
    discount_mode: str
    approval_status: str
    services: Optional[List[str]] = None
    notes: Optional[str] = None
    created_at: datetime


@router.get("/registrar/visits", response_model=List[VisitResponse])
def get_visits(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor", "cardio", "derma", "dentist", "Cashier", "Lab")),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: Optional[int] = Query(None, description="Р¤РёР»СЊС‚СЂ РїРѕ ID РїР°С†РёРµРЅС‚Р°"),
    doctor_id: Optional[int] = Query(None, description="Р¤РёР»СЊС‚СЂ РїРѕ ID РІСЂР°С‡Р°"),
    department: Optional[str] = Query(None, description="Р¤РёР»СЊС‚СЂ РїРѕ РѕС‚РґРµР»РµРЅРёСЋ"),
    date_from: Optional[str] = Query(None, description="Р”Р°С‚Р° РЅР°С‡Р°Р»Р° (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Р”Р°С‚Р° РѕРєРѕРЅС‡Р°РЅРёСЏ (YYYY-MM-DD)"),
):
    """РџРѕР»СѓС‡РёС‚СЊ РѕР±СЉРµРґРёРЅРµРЅРЅС‹Р№ СЃРїРёСЃРѕРє Р·Р°РїРёСЃРµР№ РёР· С‚Р°Р±Р»РёС† visits (РЅРѕРІС‹Р№ РјР°СЃС‚РµСЂ) Рё appointments (СЃС‚Р°СЂС‹Р№ РјР°СЃС‚РµСЂ)"""
    try:
        from app.models.appointment import Appointment
        from app.models.clinic import Doctor
        from app.models.patient import Patient
        from app.models.service import Service
        from app.models.visit import Visit, VisitService

        result = []

        # 1. РџРћР›РЈР§РђР•Рњ Р—РђРџРРЎР РР— РЎРўРђР РћР™ РўРђР‘Р›РР¦Р« APPOINTMENTS
        try:
            appointments_query = db.query(Appointment)
            
            # Р¤РёР»СЊС‚СЂС‹ РґР»СЏ appointments
            if patient_id:
                appointments_query = appointments_query.filter(Appointment.patient_id == patient_id)
            if doctor_id:
                appointments_query = appointments_query.filter(Appointment.doctor_id == doctor_id)
            if department:
                appointments_query = appointments_query.filter(Appointment.department == department)
            if date_from:
                try:
                    from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                    appointments_query = appointments_query.filter(Appointment.appointment_date >= from_date)
                except ValueError:
                    pass
            if date_to:
                try:
                    to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                    appointments_query = appointments_query.filter(Appointment.appointment_date <= to_date)
                except ValueError:
                    pass
            
            appointments = (
                appointments_query
                .order_by(Appointment.created_at.desc())
                .limit(limit)
                .all()
            )

            # РћР±СЂР°Р±Р°С‚С‹РІР°РµРј Р·Р°РїРёСЃРё РёР· appointments
            for appointment in appointments:
                # РџРѕР»СѓС‡Р°РµРј РґР°РЅРЅС‹Рµ РїР°С†РёРµРЅС‚Р°
                patient_fio = f"РџР°С†РёРµРЅС‚ #{appointment.patient_id}"
                patient_phone = None
                try:
                    if appointment.patient_id:
                        patient = (
                            db.query(Patient)
                            .filter(Patient.id == appointment.patient_id)
                            .first()
                        )
                        if patient:
                            patient_fio = patient.short_name()
                            patient_phone = patient.phone
                except Exception:
                    pass

                result.append(
                    VisitResponse(
                        id=appointment.id
                        + 10000,  # Р”РѕР±Р°РІР»СЏРµРј СЃРјРµС‰РµРЅРёРµ С‡С‚РѕР±С‹ РёР·Р±РµР¶Р°С‚СЊ РєРѕРЅС„Р»РёРєС‚РѕРІ ID
                        patient_id=appointment.patient_id,
                        patient_fio=patient_fio,
                        patient_phone=patient_phone,
                        doctor_id=appointment.doctor_id,
                        doctor_name=None,
                        doctor_specialty=None,
                        department=appointment.department,
                        visit_date=appointment.appointment_date,
                        visit_time=appointment.appointment_time,
                        status=appointment.status,
                        discount_mode="none",
                        approval_status="approved",
                        services=appointment.services or [],
                        notes=appointment.notes,
                        created_at=appointment.created_at,
                    )
                )
        except Exception as e:
            logger.error("Error processing appointments: %s", e, exc_info=True)

        # 2. РџРћР›РЈР§РђР•Рњ Р—РђРџРРЎР РР— РќРћР’РћР™ РўРђР‘Р›РР¦Р« VISITS
        visits_query = db.query(Visit)

        # Р¤РёР»СЊС‚СЂС‹ РґР»СЏ visits
        if patient_id:
            visits_query = visits_query.filter(Visit.patient_id == patient_id)
        if doctor_id:
            visits_query = visits_query.filter(Visit.doctor_id == doctor_id)
        if department:
            visits_query = visits_query.filter(Visit.department == department)
        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                visits_query = visits_query.filter(Visit.visit_date >= from_date)
            except ValueError:
                pass
        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                visits_query = visits_query.filter(Visit.visit_date <= to_date)
            except ValueError:
                pass

        visits = visits_query.order_by(Visit.created_at.desc()).all()

        # РћР±СЂР°Р±Р°С‚С‹РІР°РµРј Р·Р°РїРёСЃРё РёР· visits
        for visit in visits:
            # РџРѕР»СѓС‡Р°РµРј СѓСЃР»СѓРіРё РІРёР·РёС‚Р°
            visit_services = (
                db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
            )
            service_names = []
            for vs in visit_services:
                if vs.name:  # РСЃРїРѕР»СЊР·СѓРµРј СЃРѕС…СЂР°РЅРµРЅРЅРѕРµ РёРјСЏ
                    service_names.append(vs.name)
                else:  # Fallback - РёС‰РµРј РІ С‚Р°Р±Р»РёС†Рµ services
                    service = (
                        db.query(Service).filter(Service.id == vs.service_id).first()
                    )
                    if service:
                        service_names.append(service.name)

            # РџРѕР»СѓС‡Р°РµРј РґР°РЅРЅС‹Рµ РІСЂР°С‡Р°
            doctor_name = None
            doctor_specialty = None
            if visit.doctor_id:
                doctor = db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
                if doctor:
                    # [OK] РРЎРџР РђР’Р›Р•РќРћ: User РёРјРµРµС‚ full_name, Р° РЅРµ first_name/last_name
                    if doctor.user_id:
                        user = db.query(User).filter(User.id == doctor.user_id).first()
                        doctor_name = (
                            (user.full_name or user.username)
                            if user
                            else f"Р’СЂР°С‡ #{doctor.id}"
                        )
                    else:
                        doctor_name = f"Р’СЂР°С‡ #{doctor.id}"
                    doctor_specialty = doctor.specialty

            # РџРѕР»СѓС‡Р°РµРј РґР°РЅРЅС‹Рµ РїР°С†РёРµРЅС‚Р°
            patient_fio = f"РџР°С†РёРµРЅС‚ #{visit.patient_id}"
            patient_phone = None
            if visit.patient_id:
                patient = (
                    db.query(Patient).filter(Patient.id == visit.patient_id).first()
                )
                if patient:
                    patient_fio = patient.short_name()
                    patient_phone = patient.phone

            result.append(
                VisitResponse(
                    id=visit.id,
                    patient_id=visit.patient_id,
                    patient_fio=patient_fio,
                    patient_phone=patient_phone,
                    doctor_id=visit.doctor_id,
                    doctor_name=doctor_name,
                    doctor_specialty=doctor_specialty,
                    department=visit.department,
                    visit_date=visit.visit_date,
                    visit_time=visit.visit_time,
                    status=visit.status,
                    discount_mode=visit.discount_mode,
                    approval_status=visit.approval_status,
                    services=service_names,
                    notes=visit.notes,
                    created_at=visit.created_at,
                )
            )

        # РЎРѕСЂС‚РёСЂСѓРµРј РѕР±СЉРµРґРёРЅРµРЅРЅС‹Р№ СЂРµР·СѓР»СЊС‚Р°С‚ РїРѕ РґР°С‚Рµ СЃРѕР·РґР°РЅРёСЏ
        result.sort(key=lambda x: x.created_at, reverse=True)

        # РџСЂРёРјРµРЅСЏРµРј РїР°РіРёРЅР°С†РёСЋ Рє РѕР±СЉРµРґРёРЅРµРЅРЅРѕРјСѓ СЂРµР·СѓР»СЊС‚Р°С‚Сѓ
        total_results = result[skip : skip + limit]

        return total_results

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ Р·Р°РїРёСЃРµР№: {str(e)}",
        )


# ===================== РџР РћРЎРўРћР™ Р­РќР”РџРћРРќРў Р”Р›РЇ РћР‘РЄР•Р”РРќР•РќРРЇ Р”РђРќРќР«РҐ =====================


@router.get("/registrar/all-appointments")
def get_all_appointments(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Registrar",
            "Doctor",
            "cardio",
            "cardiology",
            "derma",
            "dentist",
            "Lab",
        )
    ),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    date_from: Optional[str] = Query(None, description="Р”Р°С‚Р° РЅР°С‡Р°Р»Р° (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Р”Р°С‚Р° РѕРєРѕРЅС‡Р°РЅРёСЏ (YYYY-MM-DD)"),
    search: Optional[str] = Query(
        None, description="РџРѕРёСЃРє РїРѕ Р¤РРћ, С‚РµР»РµС„РѕРЅСѓ РёР»Рё СѓСЃР»СѓРіР°Рј"
    ),
):
    """РџСЂРѕСЃС‚РѕРµ РѕР±СЉРµРґРёРЅРµРЅРёРµ appointments + visits РґР»СЏ С„СЂРѕРЅС‚РµРЅРґР°"""
    try:
        from datetime import datetime

        from sqlalchemy import func, or_

        from app.models.appointment import Appointment
        from app.models.patient import Patient
        from app.models.visit import Visit

        result = []

        # 1. РџРѕР»СѓС‡Р°РµРј СЃС‚Р°СЂС‹Рµ appointments СЃ С„РёР»СЊС‚СЂР°С†РёРµР№
        appointments_query = db.query(Appointment)

        # РџСЂРёРјРµРЅСЏРµРј С„РёР»СЊС‚СЂС‹ РїРѕ РґР°С‚Рµ
        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                appointments_query = appointments_query.filter(
                    Appointment.appointment_date >= from_date
                )
            except ValueError:
                pass
        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                appointments_query = appointments_query.filter(
                    Appointment.appointment_date <= to_date
                )
            except ValueError:
                pass

        patient_search_name = func.trim(
            func.coalesce(Patient.last_name, "")
            + literal(" ")
            + func.coalesce(Patient.first_name, "")
            + literal(" ")
            + func.coalesce(Patient.middle_name, "")
        )

        # РџСЂРёРјРµРЅСЏРµРј РїРѕРёСЃРє
        if search:
            # Р”Р»СЏ РїРѕРёСЃРєР° РїРѕ С‚РµР»РµС„РѕРЅСѓ РёР·РІР»РµРєР°РµРј С‚РѕР»СЊРєРѕ С†РёС„СЂС‹
            search_digits = ''.join(filter(str.isdigit, search))

            if search_digits:
                # РџРѕРёСЃРє РїРѕ Р¤РРћ, С‚РµР»РµС„РѕРЅСѓ Рё ID Р·Р°РїРёСЃРё (РІРєР»СЋС‡Р°СЏ С‚РѕР»СЊРєРѕ С†РёС„СЂС‹)
                appointments_query = appointments_query.join(
                    Patient, Appointment.patient_id == Patient.id
                ).filter(
                    or_(
                        patient_search_name.ilike(f"%{search}%"),
                        Patient.phone.ilike(f"%{search}%"),
                        func.regexp_replace(Patient.phone, r'[^\d]', '', 'g').ilike(
                            f"%{search_digits}%"
                        ),
                        Appointment.id.cast(String).ilike(f"%{search_digits}%"),
                    )
                )
            else:
                # Р•СЃР»Рё РЅРµС‚ С†РёС„СЂ, РёС‰РµРј С‚РѕР»СЊРєРѕ РїРѕ Р¤РРћ
                appointments_query = appointments_query.join(
                    Patient, Appointment.patient_id == Patient.id
                ).filter(patient_search_name.ilike(f"%{search}%"))

        appointments = (
            appointments_query.order_by(Appointment.created_at.desc())
            .limit(limit // 2)
            .all()
        )
        for apt in appointments:
            related_visit = None
            # РџРѕР»СѓС‡Р°РµРј РёРјСЏ РїР°С†РёРµРЅС‚Р°
            patient_fio = None
            if apt.patient_id:
                patient = db.query(Patient).filter(Patient.id == apt.patient_id).first()
                if patient:
                    patient_fio = patient.short_name()

            # РџСЂРµРѕР±СЂР°Р·СѓРµРј ID СѓСЃР»СѓРі РІ РЅР°Р·РІР°РЅРёСЏ РґР»СЏ appointments
            service_names = []
            service_codes = []
            total_amount = 0

            if apt.services and isinstance(apt.services, list):
                from app.models.service import Service

                for service_id in apt.services:
                    try:
                        service_id_int = int(service_id)
                        service = (
                            db.query(Service)
                            .filter(Service.id == service_id_int)
                            .first()
                        )
                        if service:
                            service_names.append(service.name)
                            service_code = service.service_code or get_service_code(
                                service.id, db
                            )
                            if service_code:
                                service_codes.append(service_code)
                            if service.price:
                                total_amount += float(service.price)
                    except (ValueError, TypeError):
                        # Р•СЃР»Рё service_id РЅРµ С‡РёСЃР»Рѕ, РІРѕР·РјРѕР¶РЅРѕ СЌС‚Рѕ СѓР¶Рµ РЅР°Р·РІР°РЅРёРµ
                        service_names.append(str(service_id))

            # РћРїСЂРµРґРµР»СЏРµРј payment_status РґР»СЏ Appointment РїРѕ Payment table.
            try:
                from sqlalchemy import and_

                related_visit = (
                    db.query(Visit)
                    .filter(
                        and_(
                            Visit.patient_id == apt.patient_id,
                            Visit.visit_date == apt.appointment_date,
                            Visit.doctor_id == apt.doctor_id,
                        )
                    )
                    .first()
                )
            except Exception:
                related_visit = None

            visit_type = _normalize_registration_discount_mode(
                getattr(apt, 'visit_type', None)
            )
            appointment_payment_processed_at = getattr(apt, 'payment_processed_at', None)
            payment_status, payment_type = _resolve_payment_truth(
                db,
                visit_id=related_visit.id if related_visit else None,
                legacy_paid_at=appointment_payment_processed_at,
            )

            result.append(
                {
                    'id': apt.id,
                    'appointment_id': apt.id,
                    'visit_id': related_visit.id if related_visit else None,
                    'patient_id': apt.patient_id,
                    'patient_fio': patient_fio,
                    'doctor_id': apt.doctor_id,
                    'department': apt.department,
                    'appointment_date': apt.appointment_date,
                    'appointment_time': apt.appointment_time,
                    'status': _preserve_operational_status_on_payment(apt.status),
                    'services': service_names,  # РџСЂРµРѕР±СЂР°Р·РѕРІР°РЅРЅС‹Рµ РЅР°Р·РІР°РЅРёСЏ СѓСЃР»СѓРі
                    'service_codes': service_codes,  # РљРѕРґС‹ СѓСЃР»СѓРі РґР»СЏ С„РёР»СЊС‚СЂР°С†РёРё
                    'total_amount': total_amount,  # РћР±С‰Р°СЏ СЃСѓРјРјР° СѓСЃР»СѓРі
                    'payment_status': payment_status,  # [OK] Р”РћР‘РђР’Р›Р•РќРћ: РЎС‚Р°С‚СѓСЃ РѕРїР»Р°С‚С‹
                    'payment_type': payment_type,
                    'visit_type': visit_type,  # РўРёРї РІРёР·РёС‚Р° РґР»СЏ СЃРѕРІРјРµСЃС‚РёРјРѕСЃС‚Рё
                    'notes': apt.notes,
                    'created_at': apt.created_at,
                    'source': 'appointments',
                    'queue_numbers': [],  # РЎС‚Р°СЂС‹Рµ appointments РЅРµ РёРјРµСЋС‚ РЅРѕРјРµСЂРѕРІ РІ РЅРѕРІС‹С… РѕС‡РµСЂРµРґСЏС…
                    'confirmation_status': 'none',  # РЎС‚Р°СЂС‹Рµ appointments РЅРµ С‚СЂРµР±СѓСЋС‚ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ
                    'confirmed_at': None,
                    'confirmed_by': None,
                }
            )

        # 2. РџРѕР»СѓС‡Р°РµРј РЅРѕРІС‹Рµ visits СЃ С„РёР»СЊС‚СЂР°С†РёРµР№
        visits_query = db.query(Visit)

        # РџСЂРёРјРµРЅСЏРµРј С„РёР»СЊС‚СЂС‹ РїРѕ РґР°С‚Рµ
        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                visits_query = visits_query.filter(Visit.visit_date >= from_date)
            except ValueError:
                pass
        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                visits_query = visits_query.filter(Visit.visit_date <= to_date)
            except ValueError:
                pass

        # РџСЂРёРјРµРЅСЏРµРј РїРѕРёСЃРє
        if search:
            # Р”Р»СЏ РїРѕРёСЃРєР° РїРѕ С‚РµР»РµС„РѕРЅСѓ РёР·РІР»РµРєР°РµРј С‚РѕР»СЊРєРѕ С†РёС„СЂС‹
            search_digits = ''.join(filter(str.isdigit, search))

            if search_digits:
                # РџРѕРёСЃРє РїРѕ Р¤РРћ, С‚РµР»РµС„РѕРЅСѓ Рё ID Р·Р°РїРёСЃРё (РІРєР»СЋС‡Р°СЏ С‚РѕР»СЊРєРѕ С†РёС„СЂС‹)
                visits_query = visits_query.join(
                    Patient, Visit.patient_id == Patient.id
                ).filter(
                    or_(
                        Patient.full_name.ilike(f"%{search}%"),
                        Patient.phone.ilike(f"%{search}%"),
                        func.regexp_replace(Patient.phone, r'[^\d]', '', 'g').ilike(
                            f"%{search_digits}%"
                        ),
                        Visit.id.cast(String).ilike(f"%{search_digits}%"),
                    )
                )
            else:
                # Р•СЃР»Рё РЅРµС‚ С†РёС„СЂ, РёС‰РµРј С‚РѕР»СЊРєРѕ РїРѕ Р¤РРћ
                visits_query = visits_query.join(
                    Patient, Visit.patient_id == Patient.id
                ).filter(Patient.full_name.ilike(f"%{search}%"))

        visits = visits_query.order_by(Visit.created_at.desc()).limit(limit // 2).all()
        for visit in visits:
            # РџРѕР»СѓС‡Р°РµРј РёРјСЏ РїР°С†РёРµРЅС‚Р°
            patient_fio = None
            if visit.patient_id:
                patient = (
                    db.query(Patient).filter(Patient.id == visit.patient_id).first()
                )
                if patient:
                    patient_fio = patient.short_name()

            # РџРѕР»СѓС‡Р°РµРј СѓСЃР»СѓРіРё РІРёР·РёС‚Р°
            from app.models.service import Service
            from app.models.visit import VisitService

            visit_services = (
                db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
            )
            service_names = []
            service_codes = []
            total_amount = 0

            for vs in visit_services:
                service_price = 0
                if vs.price is not None:  # РСЃРїРѕР»СЊР·СѓРµРј СЃРѕС…СЂР°РЅРµРЅРЅСѓСЋ С†РµРЅСѓ (РІРєР»СЋС‡Р°СЏ 0)
                    service_price = float(vs.price)
                elif vs.service_id:  # Fallback - РёС‰РµРј С†РµРЅСѓ РІ С‚Р°Р±Р»РёС†Рµ services
                    service = (
                        db.query(Service).filter(Service.id == vs.service_id).first()
                    )
                    if service and service.price:
                        service_price = float(service.price)

                total_amount += service_price * (vs.qty or 1)

                if vs.name:  # РСЃРїРѕР»СЊР·СѓРµРј СЃРѕС…СЂР°РЅРµРЅРЅРѕРµ РёРјСЏ
                    service_names.append(vs.name)
                    if vs.code:
                        service_codes.append(normalize_service_code(vs.code))
                else:  # Fallback - РёС‰РµРј РІ С‚Р°Р±Р»РёС†Рµ services
                    service = (
                        db.query(Service).filter(Service.id == vs.service_id).first()
                    )
                    if service:
                        service_names.append(service.name)
                        service_code = service.service_code or get_service_code(
                            service.id, db
                        )
                        if service_code:
                            service_codes.append(service_code)

            # РџРѕР»СѓС‡Р°РµРј РёРЅС„РѕСЂРјР°С†РёСЋ Рѕ РЅРѕРјРµСЂР°С… РІ РѕС‡РµСЂРµРґСЏС… РґР»СЏ РІРёР·РёС‚Р°
            queue_numbers = []
            confirmation_status = None

            if visit.visit_date == date.today():
                # РС‰РµРј Р·Р°РїРёСЃРё РІ РѕС‡РµСЂРµРґСЏС… РґР»СЏ СЌС‚РѕРіРѕ РІРёР·РёС‚Р°
                from app.models.online_queue import DailyQueue, OnlineQueueEntry

                queue_entries = (
                    db.query(OnlineQueueEntry)
                    .filter(OnlineQueueEntry.visit_id == visit.id)
                    .all()
                )

                for entry in queue_entries:
                    queue = (
                        db.query(DailyQueue)
                        .filter(DailyQueue.id == entry.queue_id)
                        .first()
                    )
                    if queue:
                        queue_names = {
                            "ecg": "Р­РљР“",
                            "cardiology_common": "РљР°СЂРґРёРѕР»РѕРі",
                            "dermatology": "Р”РµСЂРјР°С‚РѕР»РѕРі",
                            "stomatology": "РЎС‚РѕРјР°С‚РѕР»РѕРі",
                            "cosmetology": "РљРѕСЃРјРµС‚РѕР»РѕРі",
                            "lab": "Р›Р°Р±РѕСЂР°С‚РѕСЂРёСЏ",
                            "general": "РћР±С‰Р°СЏ РѕС‡РµСЂРµРґСЊ",
                        }

                        queue_numbers.append(
                            {
                                "queue_tag": queue.queue_tag or "general",
                                "queue_name": queue_names.get(
                                    queue.queue_tag or "general",
                                    queue.queue_tag or "РћР±С‰Р°СЏ",
                                ),
                                "number": entry.number,
                                "status": entry.status,
                            }
                        )

            # РћРїСЂРµРґРµР»СЏРµРј СЃС‚Р°С‚СѓСЃ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ
            if visit.status == "pending_confirmation":
                confirmation_status = "pending"
            elif visit.confirmed_at:
                confirmation_status = "confirmed"
            else:
                confirmation_status = "none"

            payment_status, payment_type = _resolve_payment_truth(
                db,
                visit_id=visit.id,
                legacy_paid_at=getattr(visit, 'payment_processed_at', None),
            )
            discount_mode = _normalize_registration_discount_mode(
                getattr(visit, 'discount_mode', None)
            )

            result.append(
                {
                    'id': visit.id + 20000,  # РЎРјРµС‰РµРЅРёРµ РґР»СЏ РёР·Р±РµР¶Р°РЅРёСЏ РєРѕРЅС„Р»РёРєС‚РѕРІ
                    'appointment_id': None,
                    'visit_id': visit.id,
                    'patient_id': visit.patient_id,
                    'patient_fio': patient_fio,
                    'doctor_id': visit.doctor_id,
                    'department': visit.department,
                    'appointment_date': visit.visit_date,
                    'appointment_time': visit.visit_time,
                    'status': _preserve_operational_status_on_payment(visit.status),
                    'services': service_names,  # Р РµР°Р»СЊРЅС‹Рµ РЅР°Р·РІР°РЅРёСЏ СѓСЃР»СѓРі
                    'service_codes': service_codes,  # РљРѕРґС‹ СѓСЃР»СѓРі РґР»СЏ С„РёР»СЊС‚СЂР°С†РёРё
                    'total_amount': total_amount,  # РћР±С‰Р°СЏ СЃСѓРјРјР° СѓСЃР»СѓРі
                    'payment_status': payment_status,  # [OK] Р”РћР‘РђР’Р›Р•РќРћ: РЎС‚Р°С‚СѓСЃ РѕРїР»Р°С‚С‹
                    'payment_type': payment_type,
                    'discount_mode': discount_mode,  # РўРёРї РІРёР·РёС‚Р° РґР»СЏ РѕС‚РѕР±СЂР°Р¶РµРЅРёСЏ
                    'approval_status': visit.approval_status,  # [OK] Р”РћР‘РђР’Р›Р•РќРћ: РЎС‚Р°С‚СѓСЃ РѕРґРѕР±СЂРµРЅРёСЏ РґР»СЏ all_free
                    'notes': visit.notes,
                    'created_at': visit.created_at,
                    'source': 'visits',
                    'queue_numbers': queue_numbers,  # РќРѕРјРµСЂР° РІ РѕС‡РµСЂРµРґСЏС…
                    'confirmation_status': confirmation_status,  # РЎС‚Р°С‚СѓСЃ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ
                    'confirmed_at': (
                        visit.confirmed_at.isoformat() if visit.confirmed_at else None
                    ),
                    'confirmed_by': visit.confirmed_by,
                }
            )

        # РЎРѕСЂС‚РёСЂСѓРµРј РїРѕ РґР°С‚Рµ СЃРѕР·РґР°РЅРёСЏ
        result.sort(key=lambda x: x['created_at'], reverse=True)

        # РџСЂРёРјРµРЅСЏРµРј РїР°РіРёРЅР°С†РёСЋ
        paginated_result = result[offset : offset + limit]

        return {
            "data": paginated_result,
            "total": len(result),
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < len(result),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"РћС€РёР±РєР° РїРѕР»СѓС‡РµРЅРёСЏ Р·Р°РїРёСЃРµР№: {str(e)}",
        )


# ===================== Р­РќР”РџРћРРќРў Р”Р›РЇ РћРўРњР•РўРљР Р—РђРџРРЎР•Р™ РР— VISITS РљРђРљ РћРџР›РђР§Р•РќРќР«РҐ =====================


def _preserve_operational_status_on_payment(raw_status: str | None) -> str:
    """Payment is stored separately; old status='paid' data stays in the queue as waiting."""
    if not raw_status or raw_status == "paid":
        return "waiting"
    return raw_status


@router.post("/registrar/visits/{visit_id}/mark-paid")
def mark_visit_as_paid(
    visit_id: int,
    payment_req: Optional[MarkPaidRequest] = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Registrar", "Cashier", "Receptionist", "Doctor")
    ),
):
    """РћС‚РјРµС‚РёС‚СЊ Р·Р°РїРёСЃСЊ РёР· С‚Р°Р±Р»РёС†С‹ visits РєР°Рє РѕРїР»Р°С‡РµРЅРЅСѓСЋ Рё СЃРѕР·РґР°С‚СЊ РїР»Р°С‚РµР¶ (SSOT)"""
    try:
        from app.models.visit import Visit
        from app.services.billing_service import BillingService

        # Р›РѕРіРёСЂРѕРІР°РЅРёРµ РґР»СЏ РґРёР°РіРЅРѕСЃС‚РёРєРё
        logger.info(
            "mark_visit_as_paid: User: %s, Role: %s, Visit ID: %d",
            current_user.username,
            current_user.role,
            visit_id,
        )

        # РќР°С…РѕРґРёРј Р·Р°РїРёСЃСЊ
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Р—Р°РїРёСЃСЊ РЅРµ РЅР°Р№РґРµРЅР°"
            )

        # [OK] РРЎРџР РђР’Р›Р•РќРћ: РџСЂРѕРІРµСЂСЏРµРј, РЅРµ СЃРѕР·РґР°РЅ Р»Рё СѓР¶Рµ РїР»Р°С‚РµР¶ РґР»СЏ СЌС‚РѕРіРѕ РІРёР·РёС‚Р°
        from app.models.payment import Payment

        existing_payment = (
            db.query(Payment)
            .filter(Payment.visit_id == visit_id, Payment.status == "paid")
            .first()
        )

        requested_method = (
            str(payment_req.method).strip().lower()
            if payment_req and payment_req.method
            else "cash"
        )

        if not existing_payment:
            # [OK] РРЎРџР РђР’Р›Р•РќРћ: РЎРѕР·РґР°РµРј РїР»Р°С‚РµР¶ С‡РµСЂРµР· SSOT РїРµСЂРµРґ РїРѕРјРµС‚РєРѕР№ РІРёР·РёС‚Р° РєР°Рє РѕРїР»Р°С‡РµРЅРЅРѕРіРѕ
            billing_service = BillingService(db)

            # Р Р°СЃСЃС‡РёС‚С‹РІР°РµРј СЃСѓРјРјСѓ РІРёР·РёС‚Р° С‡РµСЂРµР· SSOT
            total_info = billing_service.calculate_total(
                visit_id=visit_id, discount_mode=visit.discount_mode or "none"
            )
            payment_amount = float(total_info["total"])

            # [OK] РРЎРџР РђР’Р›Р•РќРћ: РСЃРїРѕР»СЊР·СѓРµРј РїСЂСЏРјРѕР№ SQL РґР»СЏ СЃРѕР·РґР°РЅРёСЏ РїР»Р°С‚РµР¶Р°, С‡С‚РѕР±С‹ РѕР±РѕР№С‚Рё РєРѕРЅС„Р»РёРєС‚ РјРѕРґРµР»РµР№
            # (BillingPayment Рё Payment РёСЃРїРѕР»СЊР·СѓСЋС‚ РѕРґРЅСѓ С‚Р°Р±Р»РёС†Сѓ, С‡С‚Рѕ РІС‹Р·С‹РІР°РµС‚ РїСЂРѕР±Р»РµРјС‹)
            from datetime import datetime, timezone

            from sqlalchemy import text

            currency = total_info.get("currency", "UZS")
            note = f"РћРїР»Р°С‚Р° РІРёР·РёС‚Р° {visit_id} С‡РµСЂРµР· РїР°РЅРµР»СЊ РєР°СЃСЃРёСЂР°"
            paid_at = datetime.now(timezone.utc)

            # РЎРѕР·РґР°РµРј РїР»Р°С‚РµР¶ С‡РµСЂРµР· РїСЂСЏРјРѕР№ SQL
            result = db.execute(
                text(
                    """
                    INSERT INTO payments 
                    (visit_id, amount, currency, method, status, note, paid_at, created_at)
                    VALUES (:visit_id, :amount, :currency, :method, :status, :note, :paid_at, :created_at)
                """
                ),
                {
                    "visit_id": visit_id,
                    "amount": payment_amount,
                    "currency": currency,
                    "method": requested_method,
                    "status": "paid",
                    "note": note,
                    "paid_at": paid_at,
                    "created_at": paid_at,
                },
            )
            db.commit()

            # РџРѕР»СѓС‡Р°РµРј СЃРѕР·РґР°РЅРЅС‹Р№ РїР»Р°С‚РµР¶
            payment = (
                db.query(Payment)
                .filter(Payment.visit_id == visit_id)
                .order_by(Payment.created_at.desc())
                .first()
            )

            logger.info(
                "mark_visit_as_paid: РЎРѕР·РґР°РЅ РїР»Р°С‚РµР¶ ID=%d РґР»СЏ РІРёР·РёС‚Р° %d, СЃСѓРјРјР°=%s, method=%s",
                payment.id,
                visit_id,
                payment_amount,
                requested_method,
            )
        else:
            logger.warning(
                "mark_visit_as_paid: РџР»Р°С‚РµР¶ СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚ РґР»СЏ РІРёР·РёС‚Р° %d, ID=%d",
                visit_id,
                existing_payment.id,
            )

        # [FIX:PAYMENT_STATUS] Payment must not overwrite the operational visit/queue status.
        visit.status = _preserve_operational_status_on_payment(visit.status)
        logger.info(
            "[FIX:PAYMENT_STATUS] Visit marked paid without changing operational status: visit_id=%d, status=%s",
            visit.id,
            visit.status,
        )
        db.commit()
        db.refresh(visit)

        return {
            "id": visit.id,
            "status": visit.status,
            "payment_status": "paid",
            "payment_type": (
                existing_payment.method
                if existing_payment and getattr(existing_payment, "method", None)
                else requested_method
            ),
            "amount": (
                float(existing_payment.amount)
                if existing_payment and getattr(existing_payment, "amount", None) is not None
                else payment_amount
            ),
            "message": "Р—Р°РїРёСЃСЊ РѕС‚РјРµС‡РµРЅР° РєР°Рє РѕРїР»Р°С‡РµРЅРЅР°СЏ",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("mark_visit_as_paid: Error: %s", str(e), exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"РћС€РёР±РєР° РѕР±РЅРѕРІР»РµРЅРёСЏ Р·Р°РїРёСЃРё: {str(e)}",
        )


# ===================== Р­РќР”РџРћРРќРў Р”Р›РЇ РћРўРњР•РўРљР Р—РђРџРРЎР•Р™ РћРќР›РђР™Рќ-РћР§Р•Р Р•Р”Р РљРђРљ РћРџР›РђР§Р•РќРќР«РҐ =====================


@router.post("/registrar/queue/entry/{entry_id}/mark-paid")
def mark_queue_entry_as_paid(
    entry_id: int,
    payment_req: Optional[MarkPaidRequest] = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Registrar", "Cashier", "Receptionist", "Doctor")
    ),
):
    """
    РћС‚РјРµС‚РёС‚СЊ Р·Р°РїРёСЃСЊ OnlineQueueEntry РєР°Рє РѕРїР»Р°С‡РµРЅРЅСѓСЋ.
    
    РќР°С…РѕРґРёС‚ СЃРІСЏР·Р°РЅРЅС‹Р№ Visit С‡РµСЂРµР· visit_id Рё РѕРїР»Р°С‡РёРІР°РµС‚ РµРіРѕ.
    Р•СЃР»Рё visit_id РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚, РїС‹С‚Р°РµС‚СЃСЏ РЅР°Р№С‚Рё Visit РїРѕ patient_id Рё РґР°С‚Рµ.
    """
    try:
        from app.models.online_queue import OnlineQueueEntry
        from app.models.visit import Visit
        from app.services.billing_service import BillingService

        logger.info(
            "mark_queue_entry_as_paid: User: %s, Role: %s, Entry ID: %d",
            current_user.username,
            current_user.role,
            entry_id,
        )

        # РќР°С…РѕРґРёРј Р·Р°РїРёСЃСЊ РІ РѕС‡РµСЂРµРґРё
        entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"Р—Р°РїРёСЃСЊ РѕС‡РµСЂРµРґРё СЃ ID {entry_id} РЅРµ РЅР°Р№РґРµРЅР°"
            )

        # РџС‹С‚Р°РµРјСЃСЏ РЅР°Р№С‚Рё СЃРІСЏР·Р°РЅРЅС‹Р№ Visit
        visit = None
        
        # 1. Р§РµСЂРµР· visit_id
        if entry.visit_id:
            visit = db.query(Visit).filter(Visit.id == entry.visit_id).first()
            logger.info(f"mark_queue_entry_as_paid: РќР°Р№РґРµРЅ Visit {entry.visit_id} С‡РµСЂРµР· entry.visit_id")
        
        # 2. Р•СЃР»Рё visit_id РЅРµС‚, РёС‰РµРј РїРѕ patient_id Рё РґР°С‚Рµ
        if not visit and entry.patient_id:
            from datetime import date
            today = date.today()
            visit = (
                db.query(Visit)
                .filter(
                    Visit.patient_id == entry.patient_id,
                    Visit.visit_date == today,
                )
                .order_by(Visit.created_at.desc())
                .first()
            )
            if visit:
                logger.info(f"mark_queue_entry_as_paid: РќР°Р№РґРµРЅ Visit {visit.id} С‡РµСЂРµР· patient_id Рё РґР°С‚Сѓ")

        requested_method = (
            str(payment_req.method).strip().lower()
            if payment_req and payment_req.method
            else "cash"
        )

        if not visit:
            # Legacy fallback: Р±РµР· Visit РЅРµР»СЊР·СЏ СЃРѕР·РґР°С‚СЊ Payment SSOT, РїРѕСЌС‚РѕРјСѓ РѕСЃС‚Р°РІР»СЏРµРј queue marker.
            logger.warning(
                f"mark_queue_entry_as_paid: Visit РЅРµ РЅР°Р№РґРµРЅ РґР»СЏ entry {entry_id}. "
                f"РћР±РЅРѕРІР»СЏРµРј С‚РѕР»СЊРєРѕ РїР»Р°С‚РµР¶РЅС‹Р№ СЃС‚Р°С‚СѓСЃ."
            )
            entry.status = _preserve_operational_status_on_payment(entry.status)
            entry.discount_mode = "paid"
            logger.info(
                "[FIX:PAYMENT_STATUS] Queue entry marked paid without Visit: entry_id=%d, status=%s",
                entry.id,
                entry.status,
            )
            db.commit()
            db.refresh(entry)
            
            return {
                "id": entry.id,
                "status": entry.status,
                "payment_status": "paid",
                "payment_type": requested_method,
                "message": "Р—Р°РїРёСЃСЊ РІ РѕС‡РµСЂРµРґРё РѕС‚РјРµС‡РµРЅР° РєР°Рє РѕРїР»Р°С‡РµРЅРЅР°СЏ (Visit РЅРµ РЅР°Р№РґРµРЅ)",
            }

        # РџСЂРѕРІРµСЂСЏРµРј, РЅРµ СЃРѕР·РґР°РЅ Р»Рё СѓР¶Рµ РїР»Р°С‚РµР¶ РґР»СЏ СЌС‚РѕРіРѕ РІРёР·РёС‚Р°
        from app.models.payment import Payment

        existing_payment = (
            db.query(Payment)
            .filter(Payment.visit_id == visit.id, Payment.status == "paid")
            .first()
        )

        if not existing_payment:
            # РЎРѕР·РґР°РµРј РїР»Р°С‚РµР¶ С‡РµСЂРµР· SSOT
            billing_service = BillingService(db)
            total_info = billing_service.calculate_total(
                visit_id=visit.id, discount_mode=visit.discount_mode or "none"
            )
            payment_amount = float(total_info["total"])

            from datetime import datetime, timezone
            from sqlalchemy import text

            currency = total_info.get("currency", "UZS")
            note = f"РћРїР»Р°С‚Р° РІРёР·РёС‚Р° {visit.id} С‡РµСЂРµР· Р·Р°РїРёСЃСЊ РѕС‡РµСЂРµРґРё {entry_id}"
            paid_at = datetime.now(timezone.utc)

            result = db.execute(
                text(
                    """
                    INSERT INTO payments 
                    (visit_id, amount, currency, method, status, note, paid_at, created_at)
                    VALUES (:visit_id, :amount, :currency, :method, :status, :note, :paid_at, :created_at)
                """
                ),
                {
                    "visit_id": visit.id,
                    "amount": payment_amount,
                    "currency": currency,
                    "method": requested_method,
                    "status": "paid",
                    "note": note,
                    "paid_at": paid_at,
                    "created_at": paid_at,
                },
            )
            db.commit()

            payment = (
                db.query(Payment)
                .filter(Payment.visit_id == visit.id)
                .order_by(Payment.created_at.desc())
                .first()
            )

            logger.info(
                "mark_queue_entry_as_paid: РЎРѕР·РґР°РЅ РїР»Р°С‚РµР¶ ID=%d РґР»СЏ РІРёР·РёС‚Р° %d (С‡РµСЂРµР· entry %d), СЃСѓРјРјР°=%s, method=%s",
                payment.id,
                visit.id,
                entry_id,
                payment_amount,
                requested_method,
            )
        else:
            logger.info(
                "mark_queue_entry_as_paid: РџР»Р°С‚РµР¶ СѓР¶Рµ СЃСѓС‰РµСЃС‚РІСѓРµС‚ РґР»СЏ РІРёР·РёС‚Р° %d, ID=%d",
                visit.id,
                existing_payment.id,
            )

        # [FIX:PAYMENT_STATUS] Payment is stored separately; queue operational status stays intact.
        visit.status = _preserve_operational_status_on_payment(visit.status)
        
        entry.status = _preserve_operational_status_on_payment(entry.status)
        logger.info(
            "[FIX:PAYMENT_STATUS] Queue entry marked paid without changing operational status: entry_id=%d, visit_id=%d, entry_status=%s, visit_status=%s",
            entry.id,
            visit.id,
            entry.status,
            visit.status,
        )
        
        db.commit()
        db.refresh(visit)
        db.refresh(entry)

        return {
            "id": entry.id,
            "visit_id": visit.id,
            "status": visit.status,
            "payment_status": "paid",
            "payment_type": (
                existing_payment.method
                if existing_payment and getattr(existing_payment, "method", None)
                else requested_method
            ),
            "amount": (
                float(existing_payment.amount)
                if existing_payment and getattr(existing_payment, "amount", None) is not None
                else payment_amount
            ),
            "message": "Р—Р°РїРёСЃСЊ РѕС‚РјРµС‡РµРЅР° РєР°Рє РѕРїР»Р°С‡РµРЅРЅР°СЏ",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("mark_queue_entry_as_paid: Error: %s", str(e), exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"РћС€РёР±РєР° РѕР±РЅРѕРІР»РµРЅРёСЏ Р·Р°РїРёСЃРё: {str(e)}",
        )

@router.post("/registrar/visits/{visit_id}/complete")
def complete_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Registrar", "Cashier", "Receptionist", "Doctor")
    ),
):
    """Р—Р°РІРµСЂС€РёС‚СЊ Р·Р°РїРёСЃСЊ РёР· С‚Р°Р±Р»РёС†С‹ visits"""
    try:
        from app.models.visit import Visit

        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Р—Р°РїРёСЃСЊ РЅРµ РЅР°Р№РґРµРЅР°"
            )

        visit.status = "completed"
        db.commit()
        db.refresh(visit)

        return {"id": visit.id, "status": visit.status, "message": "Р—Р°РїРёСЃСЊ Р·Р°РІРµСЂС€РµРЅР°"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"РћС€РёР±РєР° РѕР±РЅРѕРІР»РµРЅРёСЏ Р·Р°РїРёСЃРё: {str(e)}",
        )


@router.post("/registrar/visits/{visit_id}/start-visit")
def start_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """РќР°С‡Р°С‚СЊ РїСЂРёРµРј (РІ РєР°Р±РёРЅРµС‚Рµ) РґР»СЏ Р·Р°РїРёСЃРё РёР· С‚Р°Р±Р»РёС†С‹ visits"""
    try:
        from app.models.visit import Visit

        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Р—Р°РїРёСЃСЊ РЅРµ РЅР°Р№РґРµРЅР°"
            )

        visit.status = "in_progress"
        db.commit()
        db.refresh(visit)

        return {"id": visit.id, "status": visit.status, "message": "РџСЂРёРµРј РЅР°С‡Р°С‚"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"РћС€РёР±РєР° РѕР±РЅРѕРІР»РµРЅРёСЏ Р·Р°РїРёСЃРё: {str(e)}",
        )


"""
Р­РЅРґРїРѕРёРЅС‚С‹ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ РІРёР·РёС‚РѕРІ
Р’СЂРµРјРµРЅРЅС‹Р№ С„Р°Р№Р» РґР»СЏ РґРѕР±Р°РІР»РµРЅРёСЏ РІ registrar_wizard.py
"""

# ===================== РџРћР”РўР’Р•Р Р–Р”Р•РќРР• Р’РР—РРўРћР’ =====================


class ConfirmVisitRequest(BaseModel):
    confirmation_method: str = Field(default="phone", pattern="^(phone|manual)$")
    confirmed_by: Optional[str] = None  # РќРѕРјРµСЂ С‚РµР»РµС„РѕРЅР° РёР»Рё ID СЃРѕС‚СЂСѓРґРЅРёРєР°
    notes: Optional[str] = None


class ConfirmVisitResponse(BaseModel):
    success: bool
    message: str
    visit_id: int
    status: str
    queue_numbers: Optional[Dict[str, Any]] = None
    print_tickets: Optional[List[Dict[str, Any]]] = None


@router.post(
    "/registrar/visits/{visit_id}/confirm", response_model=ConfirmVisitResponse
)
def confirm_visit_by_registrar(
    visit_id: int,
    request: ConfirmVisitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    РџРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ РІРёР·РёС‚Р° СЂРµРіРёСЃС‚СЂР°С‚РѕСЂРѕРј (РїРѕ С‚РµР»РµС„РѕРЅСѓ)
    РџСЂРёСЃРІР°РёРІР°РµС‚ РЅРѕРјРµСЂР° РІ РѕС‡РµСЂРµРґСЏС… РµСЃР»Рё РІРёР·РёС‚ РЅР° СЃРµРіРѕРґРЅСЏ
    """
    try:
        # РќР°С…РѕРґРёРј РІРёР·РёС‚
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Р’РёР·РёС‚ РЅРµ РЅР°Р№РґРµРЅ"
            )

        # РџСЂРѕРІРµСЂСЏРµРј С‡С‚Рѕ РІРёР·РёС‚ РѕР¶РёРґР°РµС‚ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ
        if visit.status != "pending_confirmation":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Р’РёР·РёС‚ СѓР¶Рµ РёРјРµРµС‚ СЃС‚Р°С‚СѓСЃ: {visit.status}",
            )

        # РџСЂРѕРІРµСЂСЏРµРј С‡С‚Рѕ С‚РѕРєРµРЅ РЅРµ РёСЃС‚РµРє
        if (
            visit.confirmation_expires_at
            and visit.confirmation_expires_at < datetime.utcnow()
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="РЎСЂРѕРє РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ РёСЃС‚РµРє",
            )

        # РџРѕРґС‚РІРµСЂР¶РґР°РµРј РІРёР·РёС‚
        visit.confirmed_at = datetime.utcnow()
        visit.confirmed_by = request.confirmed_by or f"registrar_{current_user.id}"
        visit.status = "confirmed"

        queue_numbers = {}
        print_tickets = []

        # Р•СЃР»Рё РІРёР·РёС‚ РЅР° СЃРµРіРѕРґРЅСЏ - РїСЂРёСЃРІР°РёРІР°РµРј РЅРѕРјРµСЂР° РІ РѕС‡РµСЂРµРґСЏС…
        if visit.visit_date == date.today():
            from app.services.visit_confirmation_service import (
                VisitConfirmationDomainError,
            )

            try:
                queue_numbers, print_tickets = _assign_queue_numbers_on_confirmation(
                    db, visit
                )
            except VisitConfirmationDomainError as exc:
                raise HTTPException(status_code=exc.status_code, detail=exc.detail)
            visit.status = "open"  # Ready for appointment

        db.commit()
        db.refresh(visit)

        return ConfirmVisitResponse(
            success=True,
            message=f"Р’РёР·РёС‚ РїРѕРґС‚РІРµСЂР¶РґРµРЅ. {'РќРѕРјРµСЂР° РІ РѕС‡РµСЂРµРґСЏС… РїСЂРёСЃРІРѕРµРЅС‹.' if queue_numbers else 'РќРѕРјРµСЂР° Р±СѓРґСѓС‚ РїСЂРёСЃРІРѕРµРЅС‹ СѓС‚СЂРѕРј РІ РґРµРЅСЊ РІРёР·РёС‚Р°.'}",
            visit_id=visit.id,
            status=visit.status,
            queue_numbers=queue_numbers,
            print_tickets=print_tickets,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"РћС€РёР±РєР° РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ РІРёР·РёС‚Р°: {str(e)}",
        )


def _assign_queue_numbers_on_confirmation(
    db: Session, visit: Visit
) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Assign or reuse queue numbers through VisitConfirmationService."""
    from app.services.visit_confirmation_service import VisitConfirmationService

    service = VisitConfirmationService(db)
    queue_numbers_list, print_tickets = service.assign_queue_numbers_on_confirmation(
        visit
    )
    queue_numbers = {item["queue_tag"]: item for item in queue_numbers_list}
    return queue_numbers, print_tickets
