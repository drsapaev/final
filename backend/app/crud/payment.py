from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.payment import Payment  # type: ignore[attr-defined]


def list_payments(
    db: Session,
    *,
    visit_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> List[Payment]:
    """Получить список платежей с фильтрацией"""
    from datetime import datetime, date
    from sqlalchemy.orm import selectinload
    
    stmt = select(Payment).options(selectinload(Payment.payment_visits))
    
    if visit_id:
        stmt = stmt.where(Payment.visit_id == visit_id)
    
    # ✅ ИСПРАВЛЕНО: Фильтрация по датам на уровне SQL для правильной работы limit
    if date_from:
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
            stmt = stmt.where(Payment.created_at >= datetime.combine(from_date, datetime.min.time()))
        except ValueError:
            pass
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
            stmt = stmt.where(Payment.created_at <= datetime.combine(to_date, datetime.max.time()))
        except ValueError:
            pass
    
    stmt = stmt.order_by(Payment.id.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


# create_payment() удалена - используйте billing_service.create_payment() (SSOT)


def sum_paid_by_visit(db: Session, *, visit_id: int) -> float:
    q = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.visit_id == visit_id, Payment.status == "paid"
    )
    return float(db.execute(q).scalar_one() or 0.0)


# === ФУНКЦИИ ДЛЯ МОБИЛЬНОГО API ===

def get_patient_total_spent(db: Session, patient_id: int) -> float:
    """Получить общую сумму потраченную пациентом"""
    from app.models.appointment import Appointment
    
    # Получаем все визиты пациента
    visits = db.query(Appointment).filter(
        Appointment.patient_id == patient_id,
        Appointment.status.in_(["completed", "in_visit"])
    ).all()
    
    total = 0.0
    for visit in visits:
        total += sum_paid_by_visit(db, visit_id=visit.id)
    
    return total


def count_pending_payments(db: Session, patient_id: int) -> int:
    """Подсчитать количество ожидающих платежей пациента"""
    from app.models.appointment import Appointment
    
    # Получаем все визиты пациента с ожидающими платежами
    visits = db.query(Appointment).filter(
        Appointment.patient_id == patient_id,
        Appointment.status.in_(["planned", "confirmed", "paid"])
    ).all()
    
    pending_count = 0
    for visit in visits:
        # Проверяем, есть ли неоплаченные услуги
        # Здесь должна быть логика проверки неоплаченных услуг
        # Пока что просто считаем все записи как потенциально требующие оплаты
        pending_count += 1
    
    return pending_count
