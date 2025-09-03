import calendar
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.payment_webhook import PaymentWebhook
from app.models.service import Service
from app.models.visit import Visit


class AnalyticsService:
    """Сервис для аналитики и статистики клиники"""

    @staticmethod
    def get_visit_statistics(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получение статистики визитов"""
        query = db.query(Visit).filter(
            and_(Visit.date >= start_date, Visit.date <= end_date)
        )

        if department:
            query = query.filter(Visit.department == department)

        visits = query.all()

        # Общая статистика
        total_visits = len(visits)
        completed_visits = len([v for v in visits if v.status == "completed"])
        cancelled_visits = len([v for v in visits if v.status == "cancelled"])
        no_show_visits = len([v for v in visits if v.status == "no_show"])

        # Статистика по дням недели
        day_stats = {}
        for visit in visits:
            day_name = calendar.day_name[visit.date.weekday()]
            day_stats[day_name] = day_stats.get(day_name, 0) + 1

        # Статистика по часам
        hour_stats = {}
        for visit in visits:
            hour = visit.date.hour
            hour_stats[hour] = hour_stats.get(hour, 0) + 1

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "total_visits": total_visits,
            "completed_visits": completed_visits,
            "cancelled_visits": cancelled_visits,
            "no_show_visits": no_show_visits,
            "completion_rate": (
                (completed_visits / total_visits * 100) if total_visits > 0 else 0
            ),
            "by_day_of_week": day_stats,
            "by_hour": hour_stats,
        }

    @staticmethod
    def get_patient_statistics(
        db: Session, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Получение статистики пациентов"""
        # Новые пациенты за период
        new_patients = (
            db.query(Patient)
            .filter(
                and_(Patient.created_at >= start_date, Patient.created_at <= end_date)
            )
            .count()
        )

        # Активные пациенты (с визитами за период)
        active_patients = (
            db.query(Visit.patient_id)
            .filter(and_(Visit.date >= start_date, Visit.date <= end_date))
            .distinct()
            .count()
        )

        # Возвращающиеся пациенты
        returning_patients = (
            db.query(Visit.patient_id)
            .filter(and_(Visit.date >= start_date, Visit.date <= end_date))
            .group_by(Visit.patient_id)
            .having(func.count(Visit.id) > 1)
            .count()
        )

        # Статистика по возрастным группам
        patients = (
            db.query(Patient)
            .filter(
                and_(Patient.created_at >= start_date, Patient.created_at <= end_date)
            )
            .all()
        )

        age_groups = {"0-17": 0, "18-30": 0, "31-50": 0, "51-70": 0, "70+": 0}

        current_year = datetime.now().year
        for patient in patients:
            if patient.birth_date:
                age = current_year - patient.birth_date.year
                if age <= 17:
                    age_groups["0-17"] += 1
                elif age <= 30:
                    age_groups["18-30"] += 1
                elif age <= 50:
                    age_groups["31-50"] += 1
                elif age <= 70:
                    age_groups["51-70"] += 1
                else:
                    age_groups["70+"] += 1

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "new_patients": new_patients,
            "active_patients": active_patients,
            "returning_patients": returning_patients,
            "retention_rate": (
                (returning_patients / active_patients * 100)
                if active_patients > 0
                else 0
            ),
            "age_distribution": age_groups,
        }

    @staticmethod
    def get_revenue_statistics(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получение статистики доходов"""
        # Получаем успешные платежи за период
        payments = (
            db.query(PaymentWebhook)
            .filter(
                and_(
                    PaymentWebhook.status == "success",
                    PaymentWebhook.created_at >= start_date,
                    PaymentWebhook.created_at <= end_date,
                )
            )
            .all()
        )

        total_revenue = sum(
            float(p.amount) / 100 for p in payments
        )  # Конвертируем из тийинов

        # Доходы по дням
        daily_revenue = {}
        for payment in payments:
            date_str = payment.created_at.strftime("%Y-%m-%d")
            daily_revenue[date_str] = (
                daily_revenue.get(date_str, 0) + float(payment.amount) / 100
            )

        # Доходы по провайдерам
        provider_revenue = {}
        for payment in payments:
            provider = payment.provider or "unknown"
            provider_revenue[provider] = (
                provider_revenue.get(provider, 0) + float(payment.amount) / 100
            )

        # Средний чек
        avg_check = total_revenue / len(payments) if payments else 0

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "total_revenue": total_revenue,
            "total_transactions": len(payments),
            "average_check": avg_check,
            "daily_revenue": daily_revenue,
            "by_provider": provider_revenue,
        }

    @staticmethod
    def get_service_statistics(
        db: Session, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Получение статистики услуг"""
        # Получаем все услуги
        services = db.query(Service).all()

        service_stats = {}
        for service in services:
            # Подсчитываем количество визитов с этой услугой
            visit_count = (
                db.query(Visit)
                .filter(and_(Visit.date >= start_date, Visit.date <= end_date))
                .join(Visit.services)
                .filter(Service.id == service.id)
                .count()
            )

            service_stats[service.name] = {
                "id": service.id,
                "name": service.name,
                "price": float(service.price) if service.price else 0,
                "visit_count": visit_count,
                "total_revenue": (
                    visit_count * float(service.price) if service.price else 0
                ),
            }

        # Сортируем по популярности
        sorted_services = sorted(
            service_stats.values(), key=lambda x: x["visit_count"], reverse=True
        )

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "total_services": len(services),
            "services": sorted_services,
            "top_services": sorted_services[:5],  # Топ-5 услуг
        }

    @staticmethod
    def get_queue_statistics(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получение статистики очередей"""
        # Импортируем здесь, чтобы избежать циклических импортов
        from app.models.online_queue import DailyQueue

        # Получаем статистику очередей
        queue_query = db.query(DailyQueue).filter(
            and_(
                DailyQueue.date >= start_date.date(), DailyQueue.date <= end_date.date()
            )
        )

        if department:
            queue_query = queue_query.filter(DailyQueue.department == department)

        queues = queue_query.all()

        total_queues = len(queues)
        total_entries = sum(q.total_entries for q in queues)
        total_served = sum(q.served for q in queues)
        total_waiting = sum(q.waiting for q in queues)

        # Среднее время ожидания (примерно)
        avg_wait_time = "15-30 минут"  # TODO: реализовать точный расчёт

        # Статистика по отделениям
        department_stats = {}
        for queue in queues:
            dept = queue.department
            if dept not in department_stats:
                department_stats[dept] = {"total_entries": 0, "served": 0, "waiting": 0}

            department_stats[dept]["total_entries"] += queue.total_entries
            department_stats[dept]["served"] += queue.served
            department_stats[dept]["waiting"] += queue.waiting

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "total_queues": total_queues,
            "total_entries": total_entries,
            "total_served": total_served,
            "total_waiting": total_waiting,
            "service_rate": (
                (total_served / total_entries * 100) if total_entries > 0 else 0
            ),
            "average_wait_time": avg_wait_time,
            "by_department": department_stats,
        }

    @staticmethod
    def get_comprehensive_report(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получение комплексного отчёта"""
        return {
            "report_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "generated_at": datetime.utcnow().isoformat(),
            },
            "visits": AnalyticsService.get_visit_statistics(
                db, start_date, end_date, department
            ),
            "patients": AnalyticsService.get_patient_statistics(
                db, start_date, end_date
            ),
            "revenue": AnalyticsService.get_revenue_statistics(
                db, start_date, end_date, department
            ),
            "services": AnalyticsService.get_service_statistics(
                db, start_date, end_date
            ),
            "queues": AnalyticsService.get_queue_statistics(
                db, start_date, end_date, department
            ),
        }

    @staticmethod
    def get_trends(db: Session, days: int = 30) -> Dict[str, Any]:
        """Получение трендов за последние N дней"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Тренд визитов
        visit_trend = []
        for i in range(days):
            date = start_date + timedelta(days=i)
            next_date = date + timedelta(days=1)

            visit_count = (
                db.query(Visit)
                .filter(and_(Visit.date >= date, Visit.date < next_date))
                .count()
            )

            visit_trend.append(
                {"date": date.strftime("%Y-%m-%d"), "visits": visit_count}
            )

        # Тренд доходов
        revenue_trend = []
        for i in range(days):
            date = start_date + timedelta(days=i)
            next_date = date + timedelta(days=1)

            daily_revenue = (
                db.query(PaymentWebhook)
                .filter(
                    and_(
                        PaymentWebhook.status == "success",
                        PaymentWebhook.created_at >= date,
                        PaymentWebhook.created_at < next_date,
                    )
                )
                .all()
            )

            total = sum(float(p.amount) / 100 for p in daily_revenue)

            revenue_trend.append({"date": date.strftime("%Y-%m-%d"), "revenue": total})

        return {
            "period_days": days,
            "visit_trend": visit_trend,
            "revenue_trend": revenue_trend,
        }

    @staticmethod
    def get_payment_provider_analytics(
        db: Session, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Аналитика по провайдерам платежей"""
        from app.models.payment_webhook import PaymentProvider, PaymentTransaction

        # Статистика по провайдерам
        providers = db.query(PaymentProvider).all()
        provider_stats = {}

        for provider in providers:
            # Количество транзакций
            transaction_count = (
                db.query(PaymentTransaction)
                .filter(
                    and_(
                        PaymentTransaction.provider == provider.code,
                        PaymentTransaction.created_at >= start_date,
                        PaymentTransaction.created_at <= end_date,
                    )
                )
                .count()
            )

            # Успешные транзакции
            successful_count = (
                db.query(PaymentTransaction)
                .filter(
                    and_(
                        PaymentTransaction.provider == provider.code,
                        PaymentTransaction.status == "success",
                        PaymentTransaction.created_at >= start_date,
                        PaymentTransaction.created_at <= end_date,
                    )
                )
                .count()
            )

            # Общая сумма
            total_amount = (
                db.query(func.sum(PaymentTransaction.amount))
                .filter(
                    and_(
                        PaymentTransaction.provider == provider.code,
                        PaymentTransaction.status == "success",
                        PaymentTransaction.created_at >= start_date,
                        PaymentTransaction.created_at <= end_date,
                    )
                )
                .scalar()
                or 0
            )

            # Средняя сумма транзакции
            avg_amount = total_amount / successful_count if successful_count > 0 else 0

            provider_stats[provider.code] = {
                "name": provider.name,
                "is_active": provider.is_active,
                "total_transactions": transaction_count,
                "successful_transactions": successful_count,
                "failed_transactions": transaction_count - successful_count,
                "success_rate": (
                    (successful_count / transaction_count * 100)
                    if transaction_count > 0
                    else 0
                ),
                "total_amount": total_amount,
                "average_amount": avg_amount,
                "commission_earned": (
                    total_amount * (provider.commission_percent / 100)
                    if provider.commission_percent
                    else 0
                ),
            }

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "providers": provider_stats,
            "summary": {
                "total_providers": len(providers),
                "active_providers": len([p for p in providers if p.is_active]),
                "total_transactions": sum(
                    stats["total_transactions"] for stats in provider_stats.values()
                ),
                "total_revenue": sum(
                    stats["total_amount"] for stats in provider_stats.values()
                ),
                "total_commission": sum(
                    stats["commission_earned"] for stats in provider_stats.values()
                ),
            },
        }

    @staticmethod
    def get_appointment_flow_analytics(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Аналитика потока записей (appointments)"""

        query = db.query(Appointment).filter(
            and_(
                Appointment.appointment_date >= start_date.date(),
                Appointment.appointment_date <= end_date.date(),
            )
        )

        if department:
            query = query.filter(Appointment.department == department)

        appointments = query.all()

        # Статистика по статусам
        status_stats = {}
        for appointment in appointments:
            status = appointment.status
            if status not in status_stats:
                status_stats[status] = 0
            status_stats[status] += 1

        # Статистика по отделениям
        department_stats = {}
        for appointment in appointments:
            dept = appointment.department or "Не указано"
            if dept not in department_stats:
                department_stats[dept] = {"total": 0, "paid": 0, "completed": 0}
            department_stats[dept]["total"] += 1

            if appointment.status == "paid":
                department_stats[dept]["paid"] += 1
            elif appointment.status == "completed":
                department_stats[dept]["completed"] += 1

        # Статистика по дням недели
        day_stats = {}
        for appointment in appointments:
            day_name = calendar.day_name[appointment.appointment_date.weekday()]
            if day_name not in day_stats:
                day_stats[day_name] = 0
            day_stats[day_name] += 1

        # Конверсия по воронке
        total_appointments = len(appointments)
        paid_appointments = len([a for a in appointments if a.status == "paid"])
        completed_appointments = len(
            [a for a in appointments if a.status == "completed"]
        )

        conversion_rates = {
            "pending_to_paid": (
                (paid_appointments / total_appointments * 100)
                if total_appointments > 0
                else 0
            ),
            "paid_to_completed": (
                (completed_appointments / paid_appointments * 100)
                if paid_appointments > 0
                else 0
            ),
            "overall_conversion": (
                (completed_appointments / total_appointments * 100)
                if total_appointments > 0
                else 0
            ),
        }

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "summary": {
                "total_appointments": total_appointments,
                "paid_appointments": paid_appointments,
                "completed_appointments": completed_appointments,
                "cancelled_appointments": len(
                    [a for a in appointments if a.status == "cancelled"]
                ),
                "no_show_appointments": len(
                    [a for a in appointments if a.status == "no_show"]
                ),
            },
            "status_distribution": status_stats,
            "department_performance": department_stats,
            "day_of_week_distribution": day_stats,
            "conversion_rates": conversion_rates,
        }

    @staticmethod
    def get_revenue_breakdown_analytics(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Детальная аналитика доходов"""
        from app.models.payment_webhook import PaymentTransaction
        from app.models.visit import Visit

        # Доходы по провайдерам
        provider_revenue = {}
        transactions = (
            db.query(PaymentTransaction)
            .filter(
                and_(
                    PaymentTransaction.status == "success",
                    PaymentTransaction.created_at >= start_date,
                    PaymentTransaction.created_at <= end_date,
                )
            )
            .all()
        )

        for transaction in transactions:
            provider = transaction.provider
            if provider not in provider_revenue:
                provider_revenue[provider] = {
                    "count": 0,
                    "total_amount": 0,
                    "average_amount": 0,
                }
            provider_revenue[provider]["count"] += 1
            provider_revenue[provider]["total_amount"] += transaction.amount

        # Вычисляем средние суммы
        for provider, stats in provider_revenue.items():
            stats["average_amount"] = (
                stats["total_amount"] / stats["count"] if stats["count"] > 0 else 0
            )

        # Доходы по отделениям (через визиты)
        department_revenue = {}
        visits = (
            db.query(Visit)
            .filter(and_(Visit.created_at >= start_date, Visit.created_at <= end_date))
            .all()
        )

        for visit in visits:
            dept = "Общее"  # У модели Visit нет поля department
            if dept not in department_revenue:
                department_revenue[dept] = {"visits": 0, "total_revenue": 0}
            department_revenue[dept]["visits"] += 1
            # Используем payment_amount вместо total_price
            if hasattr(visit, "payment_amount") and visit.payment_amount:
                department_revenue[dept]["total_revenue"] += float(visit.payment_amount)

        # Ежедневные доходы
        daily_revenue = {}
        for transaction in transactions:
            date_str = transaction.created_at.strftime("%Y-%m-%d")
            if date_str not in daily_revenue:
                daily_revenue[date_str] = 0
            daily_revenue[date_str] += transaction.amount

        # Сортируем по дате
        daily_revenue_list = [
            {"date": date, "amount": amount}
            for date, amount in sorted(daily_revenue.items())
        ]

        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "total_revenue": sum(t.amount for t in transactions),
            "total_transactions": len(transactions),
            "average_transaction": (
                sum(t.amount for t in transactions) / len(transactions)
                if transactions
                else 0
            ),
            "provider_breakdown": provider_revenue,
            "department_breakdown": department_revenue,
            "daily_revenue": daily_revenue_list,
        }


# Создаём глобальный экземпляр сервиса
analytics_service = AnalyticsService()
