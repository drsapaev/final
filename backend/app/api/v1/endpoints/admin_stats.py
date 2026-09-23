from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, desc, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.payment_webhook import PaymentWebhook
from app.models.user import User
from app.models.visit import Visit
from app.services.analytics import department_ids_for_filter

router = APIRouter()
logger = logging.getLogger(__name__)


def raise_admin_stats_error(action: str, public_detail: str, exc: Exception) -> NoReturn:
    logger.warning(
        "Admin stats endpoint failed action=%s error_type=%s",
        action,
        type(exc).__name__,
    )
    raise HTTPException(status_code=500, detail=public_detail)


def _as_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _daily_counts_by_date(
    db: Session,
    model: Any,
    timestamp_column: Any,
    start: datetime,
    end_exclusive: datetime,
    *filters: Any,
) -> dict[date, int]:
    day_expression = func.date(timestamp_column)
    query = db.query(day_expression, func.count(model.id)).filter(
        timestamp_column >= start,
        timestamp_column < end_exclusive,
        *filters,
    )
    return {
        _as_date(day): int(count)
        for day, count in query.group_by(day_expression).all()
    }


@router.get("/stats", summary="Общая статистика для админ-панели", response_model=dict[str, Any])
def get_admin_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> dict[str, Any]:
    """Агрегированная статистика для админ-панели."""
    try:
        # Даты/границы
        today: date = datetime.now(UTC).date()

        # Одна группировка по роли заменяет общий счётчик, подсчёт врачей
        # и восемь отдельных запросов для roleStats.
        user_counts_by_role = dict(
            db.query(User.role, func.count(User.id)).group_by(User.role).all()
        )
        total_users = sum(user_counts_by_role.values())
        doctor_roles = ("Doctor", "cardio", "derma", "dentist")
        total_doctors = sum(user_counts_by_role.get(role, 0) for role in doctor_roles)
        roles = (
            "Admin",
            "Registrar",
            "Doctor",
            "Cashier",
            "Lab",
            "cardio",
            "derma",
            "dentist",
        )
        role_stats = {
            role.lower(): int(user_counts_by_role.get(role, 0)) for role in roles
        }

        # Доход (успешные платежи; amount хранится в тийинах)
        total_revenue_cents = (
            db.query(func.coalesce(func.sum(PaymentWebhook.amount), 0))
            .filter(PaymentWebhook.status == "processed")
            .scalar()
            or 0
        )
        total_revenue = float(total_revenue_cents) / 100.0

        # Используем сравнение datetime для SQLite совместимости
        today_start = datetime.combine(today, time.min)
        today_end = datetime.combine(today, time.max)

        patient_counts = (
            db.query(
                func.count(Patient.id),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                and_(
                                    Patient.created_at >= today_start,
                                    Patient.created_at <= today_end,
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
            )
            .one()
        )
        total_patients, new_patients_today = map(int, patient_counts)

        appointments_today_count = (
            select(func.count(Appointment.id))
            .where(Appointment.appointment_date == today)
            .scalar_subquery()
        )
        pending_approvals_count = (
            select(func.count(Appointment.id))
            .where(Appointment.status == "pending")
            .scalar_subquery()
        )
        appointment_counts = db.query(
            appointments_today_count, pending_approvals_count
        ).one()
        appointments_today, pending_approvals = map(int, appointment_counts)

        visits_today = (
            db.query(Visit)
            .filter(
                and_(Visit.created_at >= today_start, Visit.created_at <= today_end)
            )
            .count()
        )

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
            "generatedAt": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        raise_admin_stats_error(
            "stats",
            "Ошибка получения статистики",
            e,
        )


@router.get("/quick-stats", summary="Быстрая статистика для дашборда", response_model=dict[str, Any])
def get_quick_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> dict[str, Any]:
    try:
        today: date = datetime.now(UTC).date()

        # Используем сравнение datetime для SQLite совместимости
        today_start = datetime.combine(today, time.min)
        today_end = datetime.combine(today, time.max)

        today_visits = (
            db.query(Visit)
            .filter(
                and_(Visit.created_at >= today_start, Visit.created_at <= today_end)
            )
            .count()
        )

        today_patients = (
            db.query(Patient)
            .filter(
                and_(Patient.created_at >= today_start, Patient.created_at <= today_end)
            )
            .count()
        )

        today_revenue_cents, today_transactions = (
            db.query(
                func.coalesce(func.sum(PaymentWebhook.amount), 0),
                func.count(PaymentWebhook.id),
            )
            .filter(
                and_(
                    PaymentWebhook.status == "processed",
                    PaymentWebhook.created_at >= today_start,
                    PaymentWebhook.created_at <= today_end,
                )
            )
            .one()
        )
        today_revenue = float(today_revenue_cents) / 100.0

        return {
            "today": {
                "visits": today_visits,
                "newPatients": today_patients,
                "revenue": today_revenue,
                "transactions": int(today_transactions),
            },
            "generatedAt": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        raise_admin_stats_error(
            "quick-stats",
            "Ошибка получения быстрой статистики",
            e,
        )


@router.get("/recent-activities", summary="Последние действия для дашборда", response_model=dict[str, Any])
def get_recent_activities(
    limit: int = Query(10, ge=1, le=50, description="Количество записей"),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> dict[str, Any]:
    """Получение последних действий: записи, платежи, регистрации пользователей."""
    try:
        activities = []
        now = datetime.now(UTC)

        # Последние записи (appointments) - фильтруем только записи с created_at
        recent_appointments = (
            db.query(Appointment)
            .filter(Appointment.created_at.isnot(None))
            .order_by(desc(Appointment.created_at))
            .limit(limit)
            .all()
        )

        # PERF: имена пациентов загружаем ОДНИМ batch-запросом. N+1 по
        # удалённому (us-east-1) пулеру стоил ~200мс на запись и разгонял
        # эндпоинт до 15.6с p95 (Sentry SLA breach 2026-09-14).
        appointment_patient_ids = sorted(
            {apt.patient_id for apt in recent_appointments if apt.patient_id is not None}
        )
        patients_by_id: dict[int, Patient] = {}
        if appointment_patient_ids:
            for patient in (
                db.query(Patient).filter(Patient.id.in_(appointment_patient_ids)).all()
            ):
                patients_by_id[patient.id] = patient

        for apt in recent_appointments:
            # Получаем имя пациента (из батча, без N+1)
            patient = patients_by_id.get(apt.patient_id) if apt.patient_id is not None else None
            patient_name = (
                patient.short_name() if patient else f"Пациент #{apt.patient_id}"
            )

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
                apt_created = apt_created.replace(tzinfo=UTC)
            else:
                apt_created = apt_created.astimezone(UTC)
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

            activities.append(
                {
                    "id": f"appointment_{apt.id}",
                    "type": (
                        "appointment_created"
                        if apt.status == "pending"
                        else "appointment_updated"
                    ),
                    "message": message,
                    "user": patient_name,
                    "time": time_str,
                    "status": status,
                    "timestamp": apt.created_at.isoformat() if apt.created_at else None,
                }
            )

        # Последние успешные платежи - фильтруем только записи с created_at
        recent_payments = (
            db.query(PaymentWebhook)
            .filter(
                and_(
                    PaymentWebhook.status == "processed",
                    PaymentWebhook.created_at.isnot(None),
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
                payment_created = payment_created.replace(tzinfo=UTC)
            else:
                payment_created = payment_created.astimezone(UTC)
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

            activities.append(
                {
                    "id": f"payment_{payment.id}",
                    "type": "payment_received",
                    "message": f"Получен платеж {amount:.2f} {payment.currency}",
                    "user": f"Транзакция #{payment.transaction_id[:8]}",
                    "time": time_str,
                    "status": "success",
                    "timestamp": (
                        payment.created_at.isoformat() if payment.created_at else None
                    ),
                }
            )

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
                user_created = user_created.replace(tzinfo=UTC)
            else:
                user_created = user_created.astimezone(UTC)
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

            activities.append(
                {
                    "id": f"user_{user.id}",
                    "type": "user_registration",
                    "message": "Новый пользователь зарегистрирован",
                    "user": user_name,
                    "time": time_str,
                    "status": "success",
                    "timestamp": (
                        user.created_at.isoformat() if user.created_at else None
                    ),
                }
            )

        # Сортируем по времени (самые новые первыми)
        activities.sort(key=lambda x: x.get("timestamp") or "", reverse=True)

        # Ограничиваем количество
        activities = activities[:limit]

        return {
            "activities": activities,
            "total": len(activities),
            "generatedAt": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        raise_admin_stats_error(
            "recent-activities",
            "Ошибка получения последних действий",
            e,
        )


@router.get("/activity-chart", summary="Данные для графика активности", response_model=dict[str, Any])
def get_activity_chart(
    days: int = Query(7, ge=1, le=30, description="Количество дней для графика"),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> dict[str, Any]:
    """Получение данных для графика активности за последние N дней."""
    try:
        end_date = datetime.now(UTC).date()
        start_date = end_date - timedelta(days=days - 1)

        start = datetime.combine(start_date, time.min)
        end_exclusive = datetime.combine(end_date + timedelta(days=1), time.min)
        appointments_by_date = _daily_counts_by_date(
            db, Appointment, Appointment.created_at, start, end_exclusive
        )
        payments_by_date = _daily_counts_by_date(
            db,
            PaymentWebhook,
            PaymentWebhook.created_at,
            start,
            end_exclusive,
            PaymentWebhook.status == "processed",
        )
        users_by_date = _daily_counts_by_date(
            db, User, User.created_at, start, end_exclusive
        )

        chart_data = []
        labels = []

        current_date = start_date
        while current_date <= end_date:
            appointments_count = appointments_by_date.get(current_date, 0)
            payments_count = payments_by_date.get(current_date, 0)
            users_count = users_by_date.get(current_date, 0)

            labels.append(current_date.strftime("%d.%m"))
            chart_data.append(
                {
                    "date": current_date.isoformat(),
                    "appointments": appointments_count,
                    "payments": payments_count,
                    "users": users_count,
                    "total": appointments_count + payments_count + users_count,
                }
            )

            current_date += timedelta(days=1)

        return {
            "labels": labels,
            "data": chart_data,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days,
            },
            "generatedAt": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        raise_admin_stats_error(
            "dashboard-chart",
            "Ошибка получения данных графика",
            e,
        )


@router.get("/analytics/overview", summary="Обзор аналитики для админ-панели", response_model=dict[str, Any])
def get_analytics_overview(
    period: str = Query(
        "week", description="Период: today, week, month, quarter, year"
    ),
    department: str | None = Query(None, description="Отделение (опционально)"),
    doctor_id: int | None = Query(None, description="ID врача (опционально)"),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> dict[str, Any]:
    """Получение обзора аналитики для админ-панели с фильтрами."""
    try:
        now = datetime.now(UTC)
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

        # Используем сравнение datetime для SQLite совместимости
        start_datetime = datetime.combine(start_date, time.min)
        end_datetime = datetime.combine(end_date, time.max)

        appointments_query = db.query(Appointment).filter(
            and_(
                Appointment.created_at >= start_datetime,
                Appointment.created_at <= end_datetime,
            )
        )

        payments_query = db.query(PaymentWebhook).filter(
            and_(
                PaymentWebhook.status == "processed",
                PaymentWebhook.created_at >= start_datetime,
                PaymentWebhook.created_at <= end_datetime,
            )
        )

        patients_query = db.query(Patient).filter(
            and_(
                Patient.created_at >= start_datetime, Patient.created_at <= end_datetime
            )
        )

        # Применяем фильтры
        if department and department != "all":
            # Round-10 (owner P2, PR #3340): the canonical KEY resolves to FK
            # ids (department_ids_for_filter) — the old
            # `Appointment.department == department` compared the ORM
            # RELATIONSHIP to the string (ArgumentError → 500 on the first
            # keyed overview). An unknown key answers an EMPTY overview
            # (exact-key semantics).
            department_ids = department_ids_for_filter(db, department)
            if department_ids is not None:
                appointments_query = appointments_query.filter(
                    Appointment.department_id.in_(department_ids)
                )

        if doctor_id and doctor_id != 0:
            appointments_query = appointments_query.filter(
                Appointment.doctor_id == doctor_id
            )

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
                apt_payments = [
                    p for p in payments if getattr(p, 'appointment_id', None) == apt.id
                ]
                if apt_payments:
                    doctor_stats[apt.doctor_id]["revenue"] += sum(
                        float(p.amount) / 100.0 for p in apt_payments
                    )
                elif apt.payment_amount:
                    doctor_stats[apt.doctor_id]["revenue"] += float(apt.payment_amount)

        # Получаем имена врачей
        top_doctors = []
        for doctor_id, stats in sorted(
            doctor_stats.items(), key=lambda x: x[1]["appointments"], reverse=True
        )[:5]:
            doctor = db.query(User).filter(User.id == doctor_id).first()
            if doctor:
                doctor_name = doctor.full_name if doctor.full_name else doctor.username
                # Получаем отделение из первого appointment этого врача
                doctor_appointments = [
                    apt for apt in appointments_all if apt.doctor_id == doctor_id
                ]
                # Round-10 (owner P2, PR #3340): the JSON contract is the
                # STRING canonical department — `doctor_appointments[0].department`
                # is the ORM RELATIONSHIP, and a Department OBJECT went into
                # the JSON payload (TypeError → 500 for every doctor whose
                # first appointment carried a non-NULL department_id). The
                # `department_key` accessor publishes the same `cardio`-style
                # string every other read surface shows.
                doctor_department = (
                    doctor_appointments[0].department_key
                    if doctor_appointments and doctor_appointments[0].department_key
                    else "Неизвестно"
                )
                top_doctors.append(
                    {
                        "name": doctor_name,
                        "department": doctor_department,
                        "patients": stats["appointments"],
                        "revenue": f"{stats['revenue']:.0f} UZS",
                    }
                )

        return {
            "period": period,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "metrics": {
                "totalAppointments": total_appointments,
                "totalRevenue": total_revenue,
                "totalPatients": total_patients,
                "averageCheck": avg_check,
            },
            "appointmentsByStatus": [
                {"status": status, "count": count}
                for status, count in status_counts.items()
            ],
            "topDoctors": top_doctors,
            "generatedAt": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        raise_admin_stats_error(
            "analytics",
            "Ошибка получения аналитики",
            e,
        )


@router.get("/analytics/charts", summary="Данные для графиков аналитики", response_model=dict[str, Any])
def get_analytics_charts(
    period: str = Query(
        "week", description="Период: today, week, month, quarter, year"
    ),
    chart_type: str = Query(
        "appointments", description="Тип графика: appointments, revenue"
    ),
    department: str | None = Query(None, description="Отделение (опционально)"),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("Admin")),
) -> dict[str, Any]:
    """Получение данных для графиков аналитики."""
    try:
        now = datetime.now(UTC)
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
            # Используем сравнение datetime для SQLite совместимости
            day_start = datetime.combine(current_date, time.min)
            day_end = datetime.combine(current_date, time.max)

            appointments_query = db.query(Appointment).filter(
                and_(
                    Appointment.created_at >= day_start,
                    Appointment.created_at <= day_end,
                )
            )
            if department and department != "all":
                # Round-10 (owner P2, PR #3340): FK-id filter, see
                # department_ids_for_filter (relationship-vs-string → 500).
                department_ids = department_ids_for_filter(db, department)
                if department_ids is not None:
                    appointments_query = appointments_query.filter(
                        Appointment.department_id.in_(department_ids)
                    )
            appointments_count = appointments_query.count()

            # Доходы за день
            payments = (
                db.query(PaymentWebhook)
                .filter(
                    and_(
                        PaymentWebhook.status == "processed",
                        PaymentWebhook.created_at >= day_start,
                        PaymentWebhook.created_at <= day_end,
                    )
                )
                .all()
            )
            revenue = sum(float(p.amount) / 100.0 for p in payments)

            labels.append(current_date.strftime("%d.%m"))
            chart_data.append(
                {
                    "date": current_date.isoformat(),
                    "appointments": appointments_count,
                    "revenue": revenue,
                }
            )

            current_date += timedelta(days=1)

        return {
            "chartType": chart_type,
            "period": period,
            "labels": labels,
            "data": chart_data,
            "generatedAt": datetime.now(UTC).isoformat(),
        }

    except Exception as e:
        raise_admin_stats_error(
            "analytics-charts",
            "Ошибка получения данных графиков",
            e,
        )
