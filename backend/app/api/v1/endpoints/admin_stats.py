from __future__ import annotations

from datetime import datetime, date, timedelta, time, timezone
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, desc
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.payment_webhook import PaymentWebhook
from app.models.appointment import Appointment


router = APIRouter()


@router.get("/stats", summary="Общая статистика для админ-панели")
def get_admin_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> Dict[str, Any]:
    """Агрегированная статистика для админ-панели."""
    try:
        # Даты/границы
        today: date = datetime.utcnow().date()

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
        appointments_today = (
            db.query(Appointment).filter(Appointment.appointment_date == today).count()
        )

        # Используем func.date() для извлечения даты из datetime (SQLite совместимо)
        # func.date() возвращает строку 'YYYY-MM-DD', поэтому сравниваем со строкой
        today_str = today.strftime('%Y-%m-%d')
        
        visits_today = (
            db.query(Visit)
            .filter(func.date(Visit.created_at) == today_str)
            .count()
        )

        # Ожидающие подтверждения записей
        pending_approvals = (
            db.query(Appointment).filter(Appointment.status == "pending").count()
        )

        # Новые пациенты за сегодня
        new_patients_today = (
            db.query(Patient)
            .filter(func.date(Patient.created_at) == today_str)
            .count()
        )

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


@router.get("/quick-stats", summary="Быстрая статистика для дашборда")
def get_quick_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> Dict[str, Any]:
    try:
        today: date = datetime.utcnow().date()
        today_str = today.strftime('%Y-%m-%d')

        # Используем func.date() для извлечения даты из datetime (SQLite совместимо)
        # func.date() возвращает строку 'YYYY-MM-DD', поэтому сравниваем со строкой
        today_visits = (
            db.query(Visit)
            .filter(func.date(Visit.created_at) == today_str)
            .count()
        )

        today_patients = (
            db.query(Patient)
            .filter(func.date(Patient.created_at) == today_str)
            .count()
        )

        today_revenue_rows = (
            db.query(PaymentWebhook)
            .filter(
                and_(
                    PaymentWebhook.status == "success",
                    func.date(PaymentWebhook.created_at) == today_str
                )
            )
            .all()
        )
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
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения быстрой статистики: {e}"
        )


@router.get("/recent-activities", summary="Последние действия для дашборда")
def get_recent_activities(
    limit: int = Query(10, ge=1, le=50, description="Количество записей"),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> Dict[str, Any]:
    """Получение последних действий: записи, платежи, регистрации пользователей."""
    try:
        activities = []
        now = datetime.now(timezone.utc)

        # Последние записи (appointments) - фильтруем только записи с created_at
        recent_appointments = (
            db.query(Appointment)
            .filter(Appointment.created_at.isnot(None))
            .order_by(desc(Appointment.created_at))
            .limit(limit)
            .all()
        )

        for apt in recent_appointments:
            # Получаем имя пациента
            patient = db.query(Patient).filter(Patient.id == apt.patient_id).first()
            patient_name = patient.short_name() if patient else f"Пациент #{apt.patient_id}"

            # Определяем тип сообщения в зависимости от статуса
            if apt.status == "pending":
                message = "Создана новая запись"
                status = "info"
            elif apt.status == "paid":
                message = "Запись оплачена"
                status = "success"
            elif apt.status == "completed":
                message = "Прием завершен"
                status = "success"
            else:
                message = "Обновлена запись"
                status = "info"

            # Обработка timezone для created_at
            apt_created = apt.created_at
            if apt_created is None:
                continue
            # Приводим к UTC если есть timezone, иначе считаем что уже UTC
            if apt_created.tzinfo is None:
                apt_created = apt_created.replace(tzinfo=timezone.utc)
            else:
                apt_created = apt_created.astimezone(timezone.utc)
            time_diff = now - apt_created
            if time_diff < timedelta(minutes=1):
                time_str = "только что"
            elif time_diff < timedelta(hours=1):
                minutes = int(time_diff.total_seconds() / 60)
                time_str = f"{minutes} минут назад"
            elif time_diff < timedelta(days=1):
                hours = int(time_diff.total_seconds() / 3600)
                time_str = f"{hours} часов назад"
            else:
                days = int(time_diff.total_seconds() / 86400)
                time_str = f"{days} дней назад"

            activities.append({
                "id": f"appointment_{apt.id}",
                "type": "appointment_created" if apt.status == "pending" else "appointment_updated",
                "message": message,
                "user": patient_name,
                "time": time_str,
                "status": status,
                "timestamp": apt.created_at.isoformat() if apt.created_at else None,
            })

        # Последние успешные платежи - фильтруем только записи с created_at
        recent_payments = (
            db.query(PaymentWebhook)
            .filter(
                and_(
                    PaymentWebhook.status == "success",
                    PaymentWebhook.created_at.isnot(None)
                )
            )
            .order_by(desc(PaymentWebhook.created_at))
            .limit(limit)
            .all()
        )

        for payment in recent_payments:
            amount = float(payment.amount) / 100.0
            # Обработка timezone для created_at
            payment_created = payment.created_at
            if payment_created is None:
                continue
            # Приводим к UTC если есть timezone, иначе считаем что уже UTC
            if payment_created.tzinfo is None:
                payment_created = payment_created.replace(tzinfo=timezone.utc)
            else:
                payment_created = payment_created.astimezone(timezone.utc)
            time_diff = now - payment_created
            if time_diff < timedelta(minutes=1):
                time_str = "только что"
            elif time_diff < timedelta(hours=1):
                minutes = int(time_diff.total_seconds() / 60)
                time_str = f"{minutes} минут назад"
            elif time_diff < timedelta(days=1):
                hours = int(time_diff.total_seconds() / 3600)
                time_str = f"{hours} часов назад"
            else:
                days = int(time_diff.total_seconds() / 86400)
                time_str = f"{days} дней назад"

            activities.append({
                "id": f"payment_{payment.id}",
                "type": "payment_received",
                "message": f"Получен платеж {amount:.2f} {payment.currency}",
                "user": f"Транзакция #{payment.transaction_id[:8]}",
                "time": time_str,
                "status": "success",
                "timestamp": payment.created_at.isoformat() if payment.created_at else None,
            })

        # Новые регистрации пользователей - фильтруем только записи с created_at
        recent_users = (
            db.query(User)
            .filter(User.created_at.isnot(None))
            .order_by(desc(User.created_at))
            .limit(limit)
            .all()
        )

        for user in recent_users:
            # Обработка timezone для created_at
            user_created = user.created_at
            if user_created is None:
                continue
            # Приводим к UTC если есть timezone, иначе считаем что уже UTC
            if user_created.tzinfo is None:
                user_created = user_created.replace(tzinfo=timezone.utc)
            else:
                user_created = user_created.astimezone(timezone.utc)
            time_diff = now - user_created
            if time_diff < timedelta(minutes=1):
                time_str = "только что"
            elif time_diff < timedelta(hours=1):
                minutes = int(time_diff.total_seconds() / 60)
                time_str = f"{minutes} минут назад"
            elif time_diff < timedelta(days=1):
                hours = int(time_diff.total_seconds() / 3600)
                time_str = f"{hours} часов назад"
            else:
                days = int(time_diff.total_seconds() / 86400)
                time_str = f"{days} дней назад"

            user_name = user.full_name if user.full_name else user.username

            activities.append({
                "id": f"user_{user.id}",
                "type": "user_registration",
                "message": "Новый пользователь зарегистрирован",
                "user": user_name,
                "time": time_str,
                "status": "success",
                "timestamp": user.created_at.isoformat() if user.created_at else None,
            })

        # Сортируем по времени (самые новые первыми)
        activities.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
        
        # Ограничиваем количество
        activities = activities[:limit]

        return {
            "activities": activities,
            "total": len(activities),
            "generatedAt": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения последних действий: {e}"
        )


@router.get("/activity-chart", summary="Данные для графика активности")
def get_activity_chart(
    days: int = Query(7, ge=1, le=30, description="Количество дней для графика"),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> Dict[str, Any]:
    """Получение данных для графика активности за последние N дней."""
    try:
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days - 1)

        chart_data = []
        labels = []

        current_date = start_date
        while current_date <= end_date:
            # Используем func.date() для извлечения даты из datetime (SQLite совместимо)
            # func.date() возвращает строку 'YYYY-MM-DD', поэтому сравниваем со строкой
            date_str = current_date.strftime('%Y-%m-%d')
            
            # Подсчет записей за день
            appointments_count = (
                db.query(Appointment)
                .filter(
                    and_(
                        Appointment.created_at.isnot(None),
                        func.date(Appointment.created_at) == date_str
                    )
                )
                .count()
            )

            # Подсчет платежей за день
            payments_count = (
                db.query(PaymentWebhook)
                .filter(
                    and_(
                        PaymentWebhook.status == "success",
                        PaymentWebhook.created_at.isnot(None),
                        func.date(PaymentWebhook.created_at) == date_str
                    )
                )
                .count()
            )

            # Подсчет новых пользователей за день
            users_count = (
                db.query(User)
                .filter(
                    and_(
                        User.created_at.isnot(None),
                        func.date(User.created_at) == date_str
                    )
                )
                .count()
            )

            labels.append(current_date.strftime("%d.%m"))
            chart_data.append({
                "date": current_date.isoformat(),
                "appointments": appointments_count,
                "payments": payments_count,
                "users": users_count,
                "total": appointments_count + payments_count + users_count,
            })

            current_date += timedelta(days=1)

        return {
            "labels": labels,
            "data": chart_data,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days,
            },
            "generatedAt": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения данных графика: {e}"
        )


@router.get("/analytics/overview", summary="Обзор аналитики для админ-панели")
def get_analytics_overview(
    period: str = Query("week", description="Период: today, week, month, quarter, year"),
    department: Optional[str] = Query(None, description="Отделение (опционально)"),
    doctor_id: Optional[int] = Query(None, description="ID врача (опционально)"),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> Dict[str, Any]:
    """Получение обзора аналитики для админ-панели с фильтрами."""
    try:
        now = datetime.utcnow()
        today = now.date()
        
        # Определяем период
        if period == "today":
            start_date = today
            end_date = today
        elif period == "week":
            start_date = today - timedelta(days=7)
            end_date = today
        elif period == "month":
            start_date = today - timedelta(days=30)
            end_date = today
        elif period == "quarter":
            start_date = today - timedelta(days=90)
            end_date = today
        elif period == "year":
            start_date = today - timedelta(days=365)
            end_date = today
        else:
            start_date = today - timedelta(days=7)
            end_date = today

        # Используем func.date() для извлечения даты из datetime (SQLite совместимо)
        # func.date() возвращает строку 'YYYY-MM-DD', поэтому сравниваем со строками
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
        
        appointments_query = db.query(Appointment).filter(
            and_(
                func.date(Appointment.created_at) >= start_date_str,
                func.date(Appointment.created_at) <= end_date_str
            )
        )
        
        payments_query = db.query(PaymentWebhook).filter(
            and_(
                PaymentWebhook.status == "success",
                func.date(PaymentWebhook.created_at) >= start_date_str,
                func.date(PaymentWebhook.created_at) <= end_date_str
            )
        )

        patients_query = db.query(Patient).filter(
            and_(
                func.date(Patient.created_at) >= start_date_str,
                func.date(Patient.created_at) <= end_date_str
            )
        )

        # Применяем фильтры
        if department and department != "all":
            appointments_query = appointments_query.filter(Appointment.department == department)
        
        if doctor_id and doctor_id != 0:
            appointments_query = appointments_query.filter(Appointment.doctor_id == doctor_id)

        # Подсчеты
        total_appointments = appointments_query.count()
        
        # Доходы
        payments = payments_query.all()
        total_revenue = sum(float(p.amount) / 100.0 for p in payments)
        
        # Средний чек
        avg_check = total_revenue / len(payments) if len(payments) > 0 else 0
        
        # Пациенты
        total_patients = patients_query.count()

        # Статистика по статусам записей
        appointments_all = appointments_query.all()
        status_counts = {}
        for apt in appointments_all:
            status = apt.status or "unknown"
            status_counts[status] = status_counts.get(status, 0) + 1

        # Топ врачи
        from collections import defaultdict
        doctor_stats = defaultdict(lambda: {"appointments": 0, "revenue": 0.0})
        
        for apt in appointments_all:
            if apt.doctor_id:
                doctor_stats[apt.doctor_id]["appointments"] += 1
                # Доход от этого appointment (если есть payment)
                apt_payments = [p for p in payments if getattr(p, 'appointment_id', None) == apt.id]
                if apt_payments:
                    doctor_stats[apt.doctor_id]["revenue"] += sum(float(p.amount) / 100.0 for p in apt_payments)
                elif apt.payment_amount:
                    doctor_stats[apt.doctor_id]["revenue"] += float(apt.payment_amount)

        # Получаем имена врачей
        top_doctors = []
        for doctor_id, stats in sorted(doctor_stats.items(), key=lambda x: x[1]["appointments"], reverse=True)[:5]:
            doctor = db.query(User).filter(User.id == doctor_id).first()
            if doctor:
                doctor_name = doctor.full_name if doctor.full_name else doctor.username
                # Получаем отделение из первого appointment этого врача
                doctor_appointments = [apt for apt in appointments_all if apt.doctor_id == doctor_id]
                department = doctor_appointments[0].department if doctor_appointments and doctor_appointments[0].department else "Неизвестно"
                top_doctors.append({
                    "name": doctor_name,
                    "department": department,
                    "patients": stats["appointments"],
                    "revenue": f"{stats['revenue']:.0f} UZS"
                })

        return {
            "period": period,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "metrics": {
                "totalAppointments": total_appointments,
                "totalRevenue": total_revenue,
                "totalPatients": total_patients,
                "averageCheck": avg_check
            },
            "appointmentsByStatus": [
                {"status": status, "count": count} 
                for status, count in status_counts.items()
            ],
            "topDoctors": top_doctors,
            "generatedAt": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения аналитики: {e}"
        )


@router.get("/analytics/charts", summary="Данные для графиков аналитики")
def get_analytics_charts(
    period: str = Query("week", description="Период: today, week, month, quarter, year"),
    chart_type: str = Query("appointments", description="Тип графика: appointments, revenue"),
    department: Optional[str] = Query(None, description="Отделение (опционально)"),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> Dict[str, Any]:
    """Получение данных для графиков аналитики."""
    try:
        now = datetime.utcnow()
        today = now.date()
        
        # Определяем период
        if period == "today":
            days = 1
        elif period == "week":
            days = 7
        elif period == "month":
            days = 30
        elif period == "quarter":
            days = 90
        elif period == "year":
            days = 365
        else:
            days = 7

        start_date = today - timedelta(days=days - 1)
        end_date = today

        chart_data = []
        labels = []

        current_date = start_date
        while current_date <= end_date:
            # Используем func.date() для извлечения даты из datetime (SQLite совместимо)
            # func.date() возвращает строку 'YYYY-MM-DD', поэтому сравниваем со строкой
            date_str = current_date.strftime('%Y-%m-%d')
            
            appointments_query = db.query(Appointment).filter(
                func.date(Appointment.created_at) == date_str
            )
            if department and department != "all":
                appointments_query = appointments_query.filter(Appointment.department == department)
            appointments_count = appointments_query.count()

            # Доходы за день
            payments = (
                db.query(PaymentWebhook)
                .filter(
                    and_(
                        PaymentWebhook.status == "success",
                        func.date(PaymentWebhook.created_at) == date_str
                    )
                )
                .all()
            )
            revenue = sum(float(p.amount) / 100.0 for p in payments)

            labels.append(current_date.strftime("%d.%m"))
            chart_data.append({
                "date": current_date.isoformat(),
                "appointments": appointments_count,
                "revenue": revenue
            })

            current_date += timedelta(days=1)

        return {
            "chartType": chart_type,
            "period": period,
            "labels": labels,
            "data": chart_data,
            "generatedAt": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка получения данных графиков: {e}"
        )
