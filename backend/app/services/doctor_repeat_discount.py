"""Doctor repeat-visit eligibility and configured, exact-decimal pricing.

The caller must hold the current doctor's owner lock before preparing this
snapshot and lock requested Service rows in ascending order afterwards.
No helper commits: the locks and prices belong to the caller's transaction.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Context, Decimal, InvalidOperation, localcontext

from sqlalchemy.orm import Session

from app.models.clinic import ClinicSettings
from app.models.service import Service
from app.models.visit import Visit


class RepeatPolicyError(ValueError):
    """The repeat price cannot be authorized with the current policy/data."""


def repeat_candidate_ids(
    db: Session, *, patient_id: int, doctor_id: int, doctor_user_id: int,
    earliest: date, latest: date,
) -> list[int]:
    """Read candidate evidence; callers making decisions must lock and recheck it."""
    rows = (
        db.query(Visit.id)
        .filter(
            Visit.patient_id == patient_id,
            Visit.doctor_id == doctor_id,
            Visit.status.in_(("completed", "closed")),
            Visit.visit_date >= earliest,
            Visit.visit_date <= latest,
            Visit.repeat_proof_generation.is_not(None),
            Visit.repeat_proof_generation == Visit.repeat_evidence_generation,
            Visit.repeat_proof_consultation.is_(True),
            Visit.repeat_proof_doctor_user_id == doctor_user_id,
        )
        .all()
    )
    return [row.id for row in rows]


def _setting_int(value: object, *, lower: int, upper: int) -> int:
    # ClinicSettings.value is JSON. Admin configuration permits only whole
    # days/percentages; do not round malformed or out-of-range stored values.
    if isinstance(value, bool) or value is None:
        raise RepeatPolicyError("Настройки повторного визита недоступны")
    try:
        number = Decimal(str(value))
    except (ValueError, InvalidOperation):
        raise RepeatPolicyError("Настройки повторного визита недоступны") from None
    if not number.is_finite() or number != number.to_integral_value() or not lower <= number <= upper:
        raise RepeatPolicyError("Настройки повторного визита недоступны")
    return int(number)


@dataclass(frozen=True)
class RepeatDiscountSnapshot:
    percentage: Decimal
    historical_visit_ids: tuple[int, ...]
    historical_service_ids: tuple[int, ...]
    locked_visit_ids: tuple[int, ...] = ()

    def require_eligible(
        self,
        db: Session,
        locked_services: Mapping[int, Service],
        requested_service_ids: Sequence[int],
    ) -> None:
        """Check current consultation classifications under held row locks.

        Historical Visit rows must still be locked by the snapshot caller;
        requested catalog rows must be locked before entering here.
        """
        if any(service_id not in locked_services for service_id in requested_service_ids):
            raise RepeatPolicyError("Услуга повторного визита недоступна")
        requested_consultation = any(
            service_id in locked_services and locked_services[service_id].is_consultation
            for service_id in requested_service_ids
        )
        if not requested_consultation or not self.historical_visit_ids:
            raise RepeatPolicyError("Повторный визит недоступен: нет завершённой консультации у этого врача")
        # Historical service classification is frozen at completion; rereading
        # the current catalog here would let later edits manufacture a proof.

    def price(self, base_price: Decimal, is_consultation: bool) -> Decimal:
        if not is_consultation:
            return base_price
        # Prices are Numeric(12,2), and percentages are whole values 0..100.
        # Use an independent context so another caller's precision, rounding
        # mode or inexact traps cannot alter the registrar's cents contract.
        with localcontext(Context(prec=40, rounding=ROUND_HALF_EVEN)):
            return (base_price * (Decimal("100") - self.percentage) / Decimal("100")).quantize(Decimal("0.01"))


def prepare_repeat_discount(
    db: Session,
    *,
    patient_id: int,
    doctor_id: int | None,
    doctor_user_id: int | None,
    target_date: date,
    clinic_today: date,
    additional_visit_ids: Sequence[int] = (),
    exclude_visit_id: int | None = None,
) -> RepeatDiscountSnapshot:
    """Lock settings and completed clinical visits before any catalog lock.

    The window is measured backwards from the planned appointment date. A
    completed/closed visit after the current clinic day is not prior clinical
    work, even if its stored status was changed prematurely.
    """
    if doctor_id is None or doctor_user_id is None:
        raise RepeatPolicyError("Повторный визит требует назначенного врача")
    settings = {"repeat_visit_days": 21, "repeat_visit_discount": 0}
    rows = (
        db.query(ClinicSettings)
        .filter(ClinicSettings.key.in_(tuple(settings)))
        .order_by(ClinicSettings.key)
        .with_for_update(nowait=True)
        .populate_existing()
        .all()
    )
    for row in rows:
        settings[row.key] = row.value
    days = _setting_int(settings["repeat_visit_days"], lower=1, upper=365)
    percentage = _setting_int(settings["repeat_visit_discount"], lower=0, upper=100)
    earliest = target_date - timedelta(days=days)
    latest = min(target_date, clinic_today)
    # Probe without authority, then lock historical and additional access/target
    # visits as one sorted set. Missing or changed candidates are rechecked
    # after locks; a concurrent qualifying completion may safely require retry.
    candidates = repeat_candidate_ids(
        db, patient_id=patient_id, doctor_id=doctor_id, doctor_user_id=doctor_user_id,
        earliest=earliest, latest=latest,
    )
    if any(type(value) is not int or value <= 0 for value in additional_visit_ids):
        raise RepeatPolicyError("Контекст повторного визита недоступен")
    historical_ids = {visit_id for visit_id in candidates if visit_id != exclude_visit_id}
    wanted = historical_ids | set(additional_visit_ids)
    visits = (
        db.query(Visit).filter(Visit.id.in_(wanted)).order_by(Visit.id)
        .with_for_update(nowait=True).populate_existing().all()
    ) if wanted else []
    # Re-evaluate all evidence AFTER acquiring row locks. In particular, a
    # target Visit never qualifies as evidence for its own repeat discount.
    visit_ids = tuple(
        visit.id for visit in visits
        if visit.id in historical_ids
        and visit.id != exclude_visit_id
        and visit.patient_id == patient_id
        and visit.doctor_id == doctor_id
        and visit.status in ("completed", "closed")
        and visit.visit_date is not None and earliest <= visit.visit_date <= latest
        and visit.repeat_proof_generation is not None
        and visit.repeat_proof_generation == visit.repeat_evidence_generation
        and visit.repeat_proof_consultation is True
        and visit.repeat_proof_doctor_user_id == doctor_user_id
    )
    return RepeatDiscountSnapshot(Decimal(percentage), visit_ids, (), tuple(visit.id for visit in visits))
