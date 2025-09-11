from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles

router = APIRouter()


@router.get("/quick-stats")
async def get_quick_stats(
    current_user=Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db),
):
    """Получение быстрой статистики"""
    try:
        # Простые подсчеты без сложных запросов
        today = datetime.now().date()
        
        # Импортируем модели здесь
        from app.models.patient import Patient
        from app.models.appointment import Appointment
        from app.models.payment_webhook import PaymentWebhook
        
        # Подсчитываем пациентов
        total_patients = db.query(Patient).count()
        
        # Подсчитываем записи на сегодня
        today_appointments = db.query(Appointment).filter(
            func.date(Appointment.appointment_date) == today
        ).count()
        
        # Подсчитываем общие записи
        total_appointments = db.query(Appointment).count()
        
        # Подсчитываем платежи
        total_payments = db.query(PaymentWebhook).count()
        
        return {
            "total_patients": total_patients,
            "today_appointments": today_appointments,
            "total_appointments": total_appointments,
            "total_payments": total_payments,
            "date": today.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")


@router.get("/dashboard")
async def get_dashboard_data(
    current_user=Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db),
):
    """Получение данных для дашборда"""
    try:
        today = datetime.now().date()
        
        # Импортируем модели
        from app.models.patient import Patient
        from app.models.appointment import Appointment
        from app.models.payment_webhook import PaymentWebhook
        
        # Базовые метрики
        total_patients = db.query(Patient).count()
        total_appointments = db.query(Appointment).count()
        total_payments = db.query(PaymentWebhook).count()
        
        # Записи на сегодня
        today_appointments = db.query(Appointment).filter(
            func.date(Appointment.appointment_date) == today
        ).count()
        
        # Записи на завтра
        tomorrow = today + timedelta(days=1)
        tomorrow_appointments = db.query(Appointment).filter(
            func.date(Appointment.appointment_date) == tomorrow
        ).count()
        
        return {
            "overview": {
                "total_patients": total_patients,
                "total_appointments": total_appointments,
                "total_payments": total_payments
            },
            "today": {
                "appointments": today_appointments,
                "date": today.isoformat()
            },
            "tomorrow": {
                "appointments": tomorrow_appointments,
                "date": tomorrow.isoformat()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения данных дашборда: {str(e)}")


@router.get("/trends")
async def get_trends_analytics(
    days: int = Query(30, ge=1, le=365, description="Количество дней для анализа"),
    current_user=Depends(require_roles(["admin", "doctor", "nurse"])),
    db: Session = Depends(get_db),
):
    """Получение трендов за последние N дней"""
    try:
        from app.models.appointment import Appointment
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Простой подсчет записей по дням
        appointments_by_day = db.query(
            func.date(Appointment.appointment_date).label('date'),
            func.count(Appointment.id).label('count')
        ).filter(
            func.date(Appointment.appointment_date) >= start_date,
            func.date(Appointment.appointment_date) <= end_date
        ).group_by(
            func.date(Appointment.appointment_date)
        ).all()
        
        trends_data = []
        for row in appointments_by_day:
            trends_data.append({
                "date": row.date.isoformat(),
                "appointments": row.count
            })
        
        return {
            "period_days": days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "trends": trends_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения трендов: {str(e)}")
