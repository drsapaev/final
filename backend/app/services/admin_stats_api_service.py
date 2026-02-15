"""Service layer for admin stats endpoints."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.payment_webhook import PaymentWebhook
from app.models.user import User
from app.models.visit import Visit
from app.repositories.admin_stats_api_repository import AdminStatsApiRepository


class AdminStatsApiService:
    """Builds all admin dashboard statistics payloads."""

    def __init__(
        self,
        db: Session,
        repository: AdminStatsApiRepository | None = None,
    ):
        self.repository = repository or AdminStatsApiRepository(db)

    def get_admin_stats(self) -> dict[str, Any]:
        today: date = datetime.utcnow().date()

        total_users = self.repository.query(User).count()

        total_doctors = (
            self.repository.query(User)
            .filter(User.role.in_(["Doctor", "cardio", "derma", "dentist"]))
            .count()
        )

        total_patients = self.repository.query(Patient).count()

        total_revenue_cents = (
            self.repository.query(func.coalesce(func.sum(PaymentWebhook.amount), 0))
            .filter(PaymentWebhook.status == "processed")
            .scalar()
            or 0
        )
        total_revenue = float(total_revenue_cents) / 100.0

        appointments_today = (
            self.repository.query(Appointment)
            .filter(Appointment.appointment_date == today)
            .count()
        )

        today_start = datetime.combine(today, time.min)
        today_end = datetime.combine(today, time.max)

        visits_today = (
            self.repository.query(Visit)
            .filter(and_(Visit.created_at >= today_start, Visit.created_at <= today_end))
            .count()
        )

        pending_approvals = (
            self.repository.query(Appointment).filter(Appointment.status == "pending").count()
        )

        new_patients_today = (
            self.repository.query(Patient)
            .filter(and_(Patient.created_at >= today_start, Patient.created_at <= today_end))
            .count()
        )

        role_stats: dict[str, int] = {}
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
        for role in roles:
            role_stats[role.lower()] = (
                self.repository.query(User).filter(User.role == role).count()
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
            "generatedAt": datetime.utcnow().isoformat(),
        }

    def get_quick_stats(self) -> dict[str, Any]:
        today: date = datetime.utcnow().date()
        today_start = datetime.combine(today, time.min)
        today_end = datetime.combine(today, time.max)

        today_visits = (
            self.repository.query(Visit)
            .filter(and_(Visit.created_at >= today_start, Visit.created_at <= today_end))
            .count()
        )

        today_patients = (
            self.repository.query(Patient)
            .filter(and_(Patient.created_at >= today_start, Patient.created_at <= today_end))
            .count()
        )

        today_revenue_rows = (
            self.repository.query(PaymentWebhook)
            .filter(
                and_(
                    PaymentWebhook.status == "processed",
                    PaymentWebhook.created_at >= today_start,
                    PaymentWebhook.created_at <= today_end,
                )
            )
            .all()
        )
        today_revenue = sum(float(payment.amount) / 100.0 for payment in today_revenue_rows)

        return {
            "today": {
                "visits": today_visits,
                "newPatients": today_patients,
                "revenue": today_revenue,
                "transactions": len(today_revenue_rows),
            },
            "generatedAt": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _time_ago_uz(ts: datetime, now: datetime) -> str:
        value = ts
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        time_diff = now - value
        if time_diff < timedelta(minutes=1):
            return "только что"
        if time_diff < timedelta(hours=1):
            minutes = int(time_diff.total_seconds() / 60)
            return f"{minutes} минут назад"
        if time_diff < timedelta(days=1):
            hours = int(time_diff.total_seconds() / 3600)
            return f"{hours} часов назад"
        days = int(time_diff.total_seconds() / 86400)
        return f"{days} дней назад"

    def get_recent_activities(self, *, limit: int) -> dict[str, Any]:
        activities = []
        now = datetime.now(timezone.utc)

        recent_appointments = (
            self.repository.query(Appointment)
            .filter(Appointment.created_at.isnot(None))
            .order_by(desc(Appointment.created_at))
            .limit(limit)
            .all()
        )

        for appointment in recent_appointments:
            patient = self.repository.query(Patient).filter(Patient.id == appointment.patient_id).first()
            patient_name = patient.short_name() if patient else f"Пациент #{appointment.patient_id}"

            if appointment.status == "pending":
                message = "Создана новая запись"
                status = "info"
            elif appointment.status in {"paid", "completed"}:
                message = "Запись оплачена" if appointment.status == "paid" else "Прием завершен"
                status = "success"
            else:
                message = "Обновлена запись"
                status = "info"

            created_at = appointment.created_at
            if created_at is None:
                continue
            activities.append(
                {
                    "id": f"appointment_{appointment.id}",
                    "type": (
                        "appointment_created"
                        if appointment.status == "pending"
                        else "appointment_updated"
                    ),
                    "message": message,
                    "user": patient_name,
                    "time": self._time_ago_uz(created_at, now),
                    "status": status,
                    "timestamp": created_at.isoformat(),
                }
            )

        recent_payments = (
            self.repository.query(PaymentWebhook)
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
            created_at = payment.created_at
            if created_at is None:
                continue
            amount = float(payment.amount) / 100.0
            activities.append(
                {
                    "id": f"payment_{payment.id}",
                    "type": "payment_received",
                    "message": f"Получен платеж {amount:.2f} {payment.currency}",
                    "user": f"Транзакция #{payment.transaction_id[:8]}",
                    "time": self._time_ago_uz(created_at, now),
                    "status": "success",
                    "timestamp": created_at.isoformat(),
                }
            )

        recent_users = (
            self.repository.query(User)
            .filter(User.created_at.isnot(None))
            .order_by(desc(User.created_at))
            .limit(limit)
            .all()
        )

        for user in recent_users:
            created_at = user.created_at
            if created_at is None:
                continue
            user_name = user.full_name if user.full_name else user.username
            activities.append(
                {
                    "id": f"user_{user.id}",
                    "type": "user_registration",
                    "message": "Новый пользователь зарегистрирован",
                    "user": user_name,
                    "time": self._time_ago_uz(created_at, now),
                    "status": "success",
                    "timestamp": created_at.isoformat(),
                }
            )

        activities.sort(key=lambda item: item.get("timestamp") or "", reverse=True)
        activities = activities[:limit]

        return {
            "activities": activities,
            "total": len(activities),
            "generatedAt": datetime.utcnow().isoformat(),
        }

    def get_activity_chart(self, *, days: int) -> dict[str, Any]:
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days - 1)

        chart_data = []
        labels = []

        current_date = start_date
        while current_date <= end_date:
            day_start = datetime.combine(current_date, time.min)
            day_end = datetime.combine(current_date, time.max)

            appointments_count = (
                self.repository.query(Appointment)
                .filter(
                    and_(
                        Appointment.created_at.isnot(None),
                        Appointment.created_at >= day_start,
                        Appointment.created_at <= day_end,
                    )
                )
                .count()
            )

            payments_count = (
                self.repository.query(PaymentWebhook)
                .filter(
                    and_(
                        PaymentWebhook.status == "processed",
                        PaymentWebhook.created_at.isnot(None),
                        PaymentWebhook.created_at >= day_start,
                        PaymentWebhook.created_at <= day_end,
                    )
                )
                .count()
            )

            users_count = (
                self.repository.query(User)
                .filter(
                    and_(
                        User.created_at.isnot(None),
                        User.created_at >= day_start,
                        User.created_at <= day_end,
                    )
                )
                .count()
            )

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
            "generatedAt": datetime.utcnow().isoformat(),
        }

    def get_analytics_overview(
        self,
        *,
        period: str,
        department: str | None,
        doctor_id: int | None,
    ) -> dict[str, Any]:
        now = datetime.utcnow()
        today = now.date()

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

        start_datetime = datetime.combine(start_date, time.min)
        end_datetime = datetime.combine(end_date, time.max)

        appointments_query = self.repository.query(Appointment).filter(
            and_(
                Appointment.created_at >= start_datetime,
                Appointment.created_at <= end_datetime,
            )
        )

        payments_query = self.repository.query(PaymentWebhook).filter(
            and_(
                PaymentWebhook.status == "processed",
                PaymentWebhook.created_at >= start_datetime,
                PaymentWebhook.created_at <= end_datetime,
            )
        )

        patients_query = self.repository.query(Patient).filter(
            and_(Patient.created_at >= start_datetime, Patient.created_at <= end_datetime)
        )

        if department and department != "all":
            appointments_query = appointments_query.filter(Appointment.department == department)

        if doctor_id and doctor_id != 0:
            appointments_query = appointments_query.filter(Appointment.doctor_id == doctor_id)

        total_appointments = appointments_query.count()
        payments = payments_query.all()
        total_revenue = sum(float(payment.amount) / 100.0 for payment in payments)
        avg_check = total_revenue / len(payments) if payments else 0
        total_patients = patients_query.count()

        appointments_all = appointments_query.all()
        status_counts: dict[str, int] = {}
        for appointment in appointments_all:
            status_key = appointment.status or "unknown"
            status_counts[status_key] = status_counts.get(status_key, 0) + 1

        doctor_stats = defaultdict(lambda: {"appointments": 0, "revenue": 0.0})
        for appointment in appointments_all:
            if appointment.doctor_id:
                doctor_stats[appointment.doctor_id]["appointments"] += 1
                apt_payments = [
                    payment
                    for payment in payments
                    if getattr(payment, "appointment_id", None) == appointment.id
                ]
                if apt_payments:
                    doctor_stats[appointment.doctor_id]["revenue"] += sum(
                        float(payment.amount) / 100.0 for payment in apt_payments
                    )
                elif appointment.payment_amount:
                    doctor_stats[appointment.doctor_id]["revenue"] += float(
                        appointment.payment_amount
                    )

        top_doctors = []
        for doctor_id_key, stats in sorted(
            doctor_stats.items(),
            key=lambda item: item[1]["appointments"],
            reverse=True,
        )[:5]:
            doctor = self.repository.query(User).filter(User.id == doctor_id_key).first()
            if not doctor:
                continue
            doctor_name = doctor.full_name if doctor.full_name else doctor.username
            doctor_appointments = [
                appointment
                for appointment in appointments_all
                if appointment.doctor_id == doctor_id_key
            ]
            doctor_department = (
                doctor_appointments[0].department
                if doctor_appointments and doctor_appointments[0].department
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
                {"status": status_key, "count": count}
                for status_key, count in status_counts.items()
            ],
            "topDoctors": top_doctors,
            "generatedAt": datetime.utcnow().isoformat(),
        }

    def get_analytics_charts(
        self,
        *,
        period: str,
        chart_type: str,
        department: str | None,
    ) -> dict[str, Any]:
        now = datetime.utcnow()
        today = now.date()

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
            day_start = datetime.combine(current_date, time.min)
            day_end = datetime.combine(current_date, time.max)

            appointments_query = self.repository.query(Appointment).filter(
                and_(Appointment.created_at >= day_start, Appointment.created_at <= day_end)
            )
            if department and department != "all":
                appointments_query = appointments_query.filter(
                    Appointment.department == department
                )
            appointments_count = appointments_query.count()

            payments = (
                self.repository.query(PaymentWebhook)
                .filter(
                    and_(
                        PaymentWebhook.status == "processed",
                        PaymentWebhook.created_at >= day_start,
                        PaymentWebhook.created_at <= day_end,
                    )
                )
                .all()
            )
            revenue = sum(float(payment.amount) / 100.0 for payment in payments)

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
            "generatedAt": datetime.utcnow().isoformat(),
        }
