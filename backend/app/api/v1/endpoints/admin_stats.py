from __future__ import annotations

from datetime import datetime, date
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.payment_webhook import PaymentWebhook
from app.models.appointment import Appointment


router = APIRouter()


@router.get("/admin/stats", summary="Общая статистика для админ-панели")
def get_admin_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> Dict[str, Any]:
    """Агрегированная статистика для админ-панели."""
    try:
        # Даты/границы
        today: date = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        # Пользователи
        total_users = db.query(User).count()

        # Врачи (включая специализированные роли)
        total_doctors = (
            db.query(User)
            .filter(User.role.in_(["Doctor", "cardio", "derma", "dentist"]))
            .count()
        )

        # Пациенты
        total_patients = db.query(Patient).count()

        # Доход (успешные платежи; amount хранится в тийинах)
        total_revenue_cents = (
            db.query(func.coalesce(func.sum(PaymentWebhook.amount), 0))
            .filter(PaymentWebhook.status == "success")
            .scalar()
            or 0
        )
        total_revenue = float(total_revenue_cents) / 100.0

        # Записи и визиты за сегодня
        appointments_today = db.query(Appointment).filter(
            Appointment.appointment_date == today
        ).count()

        visits_today = db.query(Visit).filter(
            and_(Visit.created_at >= today_start, Visit.created_at <= today_end)
        ).count()

        # Ожидающие подтверждения записей
        pending_approvals = db.query(Appointment).filter(
            Appointment.status == "pending"
        ).count()

        # Новые пациенты за сегодня
        new_patients_today = db.query(Patient).filter(
            and_(Patient.created_at >= today_start, Patient.created_at <= today_end)
        ).count()

        # Разбивка по ролям
        role_stats: Dict[str, int] = {}
        roles = [
            "Admin",
            "Registrar",
            "Doctor",
            "Cashier",
            "Lab",
            "cardio",
            "derma",
            "dentist",
        ]
        for r in roles:
            role_stats[r.lower()] = db.query(User).filter(User.role == r).count()

        return {
            "totalUsers": total_users,
            "totalDoctors": total_doctors,
            "totalPatients": total_patients,
            "totalRevenue": total_revenue,
            "appointmentsToday": appointments_today,
            "visitsToday": visits_today,
            "pendingApprovals": pending_approvals,
            "newPatientsToday": new_patients_today,
            "roleStats": role_stats,
            "generatedAt": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {e}")


@router.get("/admin/quick-stats", summary="Быстрая статистика для дашборда")
def get_quick_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> Dict[str, Any]:
    try:
        today: date = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        today_visits = db.query(Visit).filter(
            and_(Visit.created_at >= today_start, Visit.created_at <= today_end)
        ).count()

        today_patients = db.query(Patient).filter(
            and_(Patient.created_at >= today_start, Patient.created_at <= today_end)
        ).count()

        today_revenue_rows = db.query(PaymentWebhook).filter(
            and_(
                PaymentWebhook.status == "success",
                PaymentWebhook.created_at >= today_start,
                PaymentWebhook.created_at <= today_end,
            )
        ).all()
        today_revenue = sum(float(p.amount) / 100.0 for p in today_revenue_rows)

        return {
            "today": {
                "visits": today_visits,
                "newPatients": today_patients,
                "revenue": today_revenue,
                "transactions": len(today_revenue_rows),
            },
            "generatedAt": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения быстрой статистики: {e}")


