"""
Расширенный сервис аналитики с KPI и метриками эффективности
"""

import logging
import statistics
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, asc, desc, func, or_
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.emr import EMR
from app.models.patient import Patient
from app.models.payment import Payment

# from app.models.queue import QueueTicket  # Временно отключено
from app.models.user import User

logger = logging.getLogger(__name__)


class AdvancedAnalyticsService:
    """Расширенный сервис аналитики с KPI и метриками эффективности"""

    @staticmethod
    def get_kpi_metrics(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получить ключевые показатели эффективности (KPI)"""
        try:
            # Базовые фильтры
            filters = [
                Appointment.appointment_date >= start_date.date(),
                Appointment.appointment_date <= end_date.date(),
            ]

            if department:
                filters.append(Appointment.department == department)

            # Общее количество записей
            total_appointments = db.query(Appointment).filter(and_(*filters)).count()

            # Завершенные записи
            completed_appointments = (
                db.query(Appointment)
                .filter(and_(*filters, Appointment.status == "completed"))
                .count()
            )

            # Отмененные записи
            cancelled_appointments = (
                db.query(Appointment)
                .filter(and_(*filters, Appointment.status == "cancelled"))
                .count()
            )

            # Новые пациенты
            new_patients = (
                db.query(Patient)
                .filter(
                    Patient.created_at >= start_date, Patient.created_at <= end_date
                )
                .count()
            )

            # Общий доход
            revenue_query = (
                db.query(func.sum(Payment.amount))
                .join(Appointment)
                .filter(and_(*filters, Payment.status == "completed"))
            )
            total_revenue = revenue_query.scalar() or 0

            # Средний чек
            avg_revenue_per_visit = (
                total_revenue / completed_appointments
                if completed_appointments > 0
                else 0
            )

            # Время ожидания в очереди (среднее) - ВРЕМЕННО ОТКЛЮЧЕНО
            # queue_wait_times = db.query(QueueTicket).filter(
            #     and_(
            #         QueueTicket.created_at >= start_date,
            #         QueueTicket.created_at <= end_date,
            #         QueueTicket.served_at.isnot(None)
            #     )
            # ).all()
            queue_wait_times = []  # Временная заглушка

            avg_wait_time = 0
            if queue_wait_times:
                wait_times = []
                for ticket in queue_wait_times:
                    if ticket.served_at:
                        wait_time = (
                            ticket.served_at - ticket.created_at
                        ).total_seconds() / 60  # минуты
                        wait_times.append(wait_time)

                if wait_times:
                    avg_wait_time = statistics.mean(wait_times)

            # Процент заполненности расписания
            total_working_hours = 8 * 5 * 4  # 8 часов * 5 дней * 4 недели (примерно)
            occupied_hours = completed_appointments * 0.5  # 30 минут на прием
            schedule_utilization = (
                (occupied_hours / total_working_hours * 100)
                if total_working_hours > 0
                else 0
            )

            # Процент повторных визитов
            repeat_visits = (
                db.query(Appointment)
                .filter(and_(*filters, Appointment.status == "completed"))
                .join(Patient)
                .group_by(Patient.id)
                .having(func.count(Appointment.id) > 1)
                .count()
            )

            repeat_visit_rate = (
                (repeat_visits / completed_appointments * 100)
                if completed_appointments > 0
                else 0
            )

            # Процент отмен
            cancellation_rate = (
                (cancelled_appointments / total_appointments * 100)
                if total_appointments > 0
                else 0
            )

            # Процент завершения
            completion_rate = (
                (completed_appointments / total_appointments * 100)
                if total_appointments > 0
                else 0
            )

            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "department": department or "all",
                },
                "kpi_metrics": {
                    "total_appointments": total_appointments,
                    "completed_appointments": completed_appointments,
                    "cancelled_appointments": cancelled_appointments,
                    "new_patients": new_patients,
                    "total_revenue": round(total_revenue, 2),
                    "avg_revenue_per_visit": round(avg_revenue_per_visit, 2),
                    "avg_wait_time_minutes": round(avg_wait_time, 2),
                    "schedule_utilization_percent": round(schedule_utilization, 2),
                    "repeat_visit_rate_percent": round(repeat_visit_rate, 2),
                    "cancellation_rate_percent": round(cancellation_rate, 2),
                    "completion_rate_percent": round(completion_rate, 2),
                },
                "performance_indicators": {
                    "excellent": completion_rate >= 90 and cancellation_rate <= 5,
                    "good": completion_rate >= 80 and cancellation_rate <= 10,
                    "needs_improvement": completion_rate < 80 or cancellation_rate > 10,
                },
            }

        except Exception as e:
            logger.error(f"Ошибка получения KPI метрик: {e}")
            return {"error": str(e)}

    @staticmethod
    def get_doctor_performance(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Получить показатели эффективности врачей"""
        try:
            # Базовые фильтры
            filters = [
                Appointment.appointment_date >= start_date.date(),
                Appointment.appointment_date <= end_date.date(),
            ]

            if department:
                filters.append(Appointment.department == department)

            # Статистика по врачам
            doctor_stats = (
                db.query(
                    User.id,
                    User.fio,
                    User.specialty,
                    func.count(Appointment.id).label('total_appointments'),
                    func.sum(
                        func.case((Appointment.status == "completed", 1), else_=0)
                    ).label('completed_appointments'),
                    func.sum(
                        func.case((Appointment.status == "cancelled", 1), else_=0)
                    ).label('cancelled_appointments'),
                    func.avg(
                        func.case(
                            (
                                Appointment.status == "completed",
                                func.extract(
                                    'epoch',
                                    Appointment.updated_at - Appointment.created_at,
                                )
                                / 3600,
                            ),
                            else_=None,
                        )
                    ).label('avg_visit_duration_hours'),
                )
                .join(Appointment, User.id == Appointment.doctor_id)
                .filter(and_(*filters))
                .group_by(User.id, User.fio, User.specialty)
                .all()
            )

            doctor_performance = []
            for stat in doctor_stats:
                completion_rate = (
                    (stat.completed_appointments / stat.total_appointments * 100)
                    if stat.total_appointments > 0
                    else 0
                )
                cancellation_rate = (
                    (stat.cancelled_appointments / stat.total_appointments * 100)
                    if stat.total_appointments > 0
                    else 0
                )

                doctor_performance.append(
                    {
                        "doctor_id": stat.id,
                        "doctor_name": stat.fio,
                        "specialty": stat.specialty,
                        "total_appointments": stat.total_appointments,
                        "completed_appointments": stat.completed_appointments,
                        "cancelled_appointments": stat.cancelled_appointments,
                        "completion_rate_percent": round(completion_rate, 2),
                        "cancellation_rate_percent": round(cancellation_rate, 2),
                        "avg_visit_duration_hours": round(
                            stat.avg_visit_duration_hours or 0, 2
                        ),
                        "performance_score": completion_rate
                        - cancellation_rate,  # Простая оценка эффективности
                    }
                )

            # Сортируем по оценке эффективности
            doctor_performance.sort(key=lambda x: x["performance_score"], reverse=True)

            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "department": department or "all",
                },
                "doctor_performance": doctor_performance,
                "summary": {
                    "total_doctors": len(doctor_performance),
                    "avg_completion_rate": (
                        round(
                            sum(
                                d["completion_rate_percent"] for d in doctor_performance
                            )
                            / len(doctor_performance),
                            2,
                        )
                        if doctor_performance
                        else 0
                    ),
                    "top_performer": (
                        doctor_performance[0] if doctor_performance else None
                    ),
                },
            }

        except Exception as e:
            logger.error(f"Ошибка получения показателей врачей: {e}")
            return {"error": str(e)}

    @staticmethod
    def get_patient_analytics(
        db: Session, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Расширенная аналитика пациентов"""
        try:
            # Новые пациенты
            new_patients = (
                db.query(Patient)
                .filter(
                    Patient.created_at >= start_date, Patient.created_at <= end_date
                )
                .count()
            )

            # Активные пациенты (с записями в период)
            active_patients = (
                db.query(Patient)
                .join(Appointment)
                .filter(
                    and_(
                        Appointment.appointment_date >= start_date.date(),
                        Appointment.appointment_date <= end_date.date(),
                    )
                )
                .distinct()
                .count()
            )

            # Возрастные группы
            age_groups = (
                db.query(
                    func.case(
                        (
                            func.extract('year', func.age(Patient.birth_date)) < 18,
                            'under_18',
                        ),
                        (
                            func.extract('year', func.age(Patient.birth_date)) < 30,
                            '18_29',
                        ),
                        (
                            func.extract('year', func.age(Patient.birth_date)) < 50,
                            '30_49',
                        ),
                        (
                            func.extract('year', func.age(Patient.birth_date)) < 65,
                            '50_64',
                        ),
                        else_='65_plus',
                    ).label('age_group'),
                    func.count(Patient.id).label('count'),
                )
                .filter(
                    Patient.created_at >= start_date, Patient.created_at <= end_date
                )
                .group_by('age_group')
                .all()
            )

            # Половая структура
            gender_distribution = (
                db.query(Patient.gender, func.count(Patient.id).label('count'))
                .filter(
                    Patient.created_at >= start_date, Patient.created_at <= end_date
                )
                .group_by(Patient.gender)
                .all()
            )

            # Топ диагнозов
            top_diagnoses = (
                db.query(EMR.icd10, func.count(EMR.id).label('count'))
                .join(Appointment)
                .filter(
                    and_(
                        Appointment.appointment_date >= start_date.date(),
                        Appointment.appointment_date <= end_date.date(),
                        EMR.icd10.isnot(None),
                    )
                )
                .group_by(EMR.icd10)
                .order_by(desc('count'))
                .limit(10)
                .all()
            )

            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                "patient_metrics": {
                    "new_patients": new_patients,
                    "active_patients": active_patients,
                    "patient_retention_rate": (
                        (active_patients / new_patients * 100)
                        if new_patients > 0
                        else 0
                    ),
                },
                "age_distribution": {
                    group.age_group: group.count for group in age_groups
                },
                "gender_distribution": {
                    group.gender: group.count for group in gender_distribution
                },
                "top_diagnoses": [
                    {"icd10": diag.icd10, "count": diag.count} for diag in top_diagnoses
                ],
            }

        except Exception as e:
            logger.error(f"Ошибка получения аналитики пациентов: {e}")
            return {"error": str(e)}

    @staticmethod
    def get_revenue_analytics(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Расширенная аналитика доходов"""
        try:
            # Базовые фильтры
            filters = [
                Payment.created_at >= start_date,
                Payment.created_at <= end_date,
                Payment.status == "completed",
            ]

            if department:
                filters.append(Appointment.department == department)

            # Общий доход
            total_revenue = (
                db.query(func.sum(Payment.amount))
                .join(Appointment)
                .filter(and_(*filters))
                .scalar()
                or 0
            )

            # Доход по дням недели
            daily_revenue = (
                db.query(
                    func.extract('dow', Payment.created_at).label('day_of_week'),
                    func.sum(Payment.amount).label('revenue'),
                )
                .join(Appointment)
                .filter(and_(*filters))
                .group_by('day_of_week')
                .all()
            )

            # Доход по методам оплаты
            payment_method_revenue = (
                db.query(
                    Payment.payment_method,
                    func.sum(Payment.amount).label('revenue'),
                    func.count(Payment.id).label('transactions'),
                )
                .join(Appointment)
                .filter(and_(*filters))
                .group_by(Payment.payment_method)
                .all()
            )

            # Средний чек по дням
            avg_daily_revenue = total_revenue / ((end_date - start_date).days + 1)

            # Прогноз дохода (простая линейная экстраполяция)
            days_in_period = (end_date - start_date).days + 1
            daily_avg = total_revenue / days_in_period if days_in_period > 0 else 0
            next_week_forecast = daily_avg * 7
            next_month_forecast = daily_avg * 30

            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "department": department or "all",
                },
                "revenue_metrics": {
                    "total_revenue": round(total_revenue, 2),
                    "avg_daily_revenue": round(avg_daily_revenue, 2),
                    "days_in_period": days_in_period,
                },
                "daily_revenue": {
                    day.day_of_week: round(day.revenue, 2) for day in daily_revenue
                },
                "payment_methods": [
                    {
                        "method": method.payment_method,
                        "revenue": round(method.revenue, 2),
                        "transactions": method.transactions,
                        "avg_transaction": (
                            round(method.revenue / method.transactions, 2)
                            if method.transactions > 0
                            else 0
                        ),
                    }
                    for method in payment_method_revenue
                ],
                "forecasts": {
                    "next_week": round(next_week_forecast, 2),
                    "next_month": round(next_month_forecast, 2),
                },
            }

        except Exception as e:
            logger.error(f"Ошибка получения аналитики доходов: {e}")
            return {"error": str(e)}

    @staticmethod
    def get_predictive_analytics(db: Session, days_ahead: int = 30) -> Dict[str, Any]:
        """Предиктивная аналитика и прогнозы"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=90)  # Анализируем последние 90 дней

            # Тренды записей
            appointment_trends = (
                db.query(
                    func.date(Appointment.appointment_date).label('date'),
                    func.count(Appointment.id).label('count'),
                )
                .filter(
                    and_(
                        Appointment.appointment_date >= start_date.date(),
                        Appointment.appointment_date <= end_date.date(),
                    )
                )
                .group_by('date')
                .order_by('date')
                .all()
            )

            # Тренды доходов
            revenue_trends = (
                db.query(
                    func.date(Payment.created_at).label('date'),
                    func.sum(Payment.amount).label('revenue'),
                )
                .filter(
                    and_(
                        Payment.created_at >= start_date,
                        Payment.created_at <= end_date,
                        Payment.status == "completed",
                    )
                )
                .group_by('date')
                .order_by('date')
                .all()
            )

            # Простой прогноз на основе трендов
            if len(appointment_trends) >= 7:
                recent_appointments = [trend.count for trend in appointment_trends[-7:]]
                avg_daily_appointments = statistics.mean(recent_appointments)
                appointment_forecast = avg_daily_appointments * days_ahead
            else:
                appointment_forecast = 0

            if len(revenue_trends) >= 7:
                recent_revenue = [trend.revenue for trend in revenue_trends[-7:]]
                avg_daily_revenue = statistics.mean(recent_revenue)
                revenue_forecast = avg_daily_revenue * days_ahead
            else:
                revenue_forecast = 0

            # Сезонность (простой анализ)
            monthly_appointments = {}
            for trend in appointment_trends:
                month = trend.date.month
                if month not in monthly_appointments:
                    monthly_appointments[month] = []
                monthly_appointments[month].append(trend.count)

            seasonal_pattern = {}
            for month, counts in monthly_appointments.items():
                seasonal_pattern[month] = statistics.mean(counts)

            return {
                "forecast_period_days": days_ahead,
                "analysis_period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                "forecasts": {
                    "appointments": round(appointment_forecast, 0),
                    "revenue": round(revenue_forecast, 2),
                },
                "trends": {
                    "appointments": [
                        {"date": trend.date.isoformat(), "count": trend.count}
                        for trend in appointment_trends
                    ],
                    "revenue": [
                        {
                            "date": trend.date.isoformat(),
                            "revenue": float(trend.revenue),
                        }
                        for trend in revenue_trends
                    ],
                },
                "seasonal_patterns": seasonal_pattern,
                "confidence_level": "medium",  # Простая оценка уверенности
            }

        except Exception as e:
            logger.error(f"Ошибка получения предиктивной аналитики: {e}")
            return {"error": str(e)}


# Глобальный экземпляр сервиса
advanced_analytics_service = AdvancedAnalyticsService()


def get_advanced_analytics_service() -> AdvancedAnalyticsService:
    """Получить экземпляр расширенного сервиса аналитики"""
    return advanced_analytics_service
