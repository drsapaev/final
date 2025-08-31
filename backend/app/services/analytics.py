from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract
import calendar

from app.models.visit import Visit
from app.models.patient import Patient
from app.models.service import Service
from app.models.payment_webhook import PaymentWebhook
from app.models.appointment import Appointment

class AnalyticsService:
    """Сервис для аналитики и статистики клиники"""
    
    @staticmethod
    def get_visit_statistics(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: Optional[str] = None
    ) -> Dict[str, Any]:
        """Получение статистики визитов"""
        query = db.query(Visit).filter(
            and_(
                Visit.date >= start_date,
                Visit.date <= end_date
            )
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
                "end_date": end_date.isoformat()
            },
            "total_visits": total_visits,
            "completed_visits": completed_visits,
            "cancelled_visits": cancelled_visits,
            "no_show_visits": no_show_visits,
            "completion_rate": (completed_visits / total_visits * 100) if total_visits > 0 else 0,
            "by_day_of_week": day_stats,
            "by_hour": hour_stats
        }
    
    @staticmethod
    def get_patient_statistics(
        db: Session,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Получение статистики пациентов"""
        # Новые пациенты за период
        new_patients = db.query(Patient).filter(
            and_(
                Patient.created_at >= start_date,
                Patient.created_at <= end_date
            )
        ).count()
        
        # Активные пациенты (с визитами за период)
        active_patients = db.query(Visit.patient_id).filter(
            and_(
                Visit.date >= start_date,
                Visit.date <= end_date
            )
        ).distinct().count()
        
        # Возвращающиеся пациенты
        returning_patients = db.query(Visit.patient_id).filter(
            and_(
                Visit.date >= start_date,
                Visit.date <= end_date
            )
        ).group_by(Visit.patient_id).having(func.count(Visit.id) > 1).count()
        
        # Статистика по возрастным группам
        patients = db.query(Patient).filter(
            and_(
                Patient.created_at >= start_date,
                Patient.created_at <= end_date
            )
        ).all()
        
        age_groups = {
            "0-17": 0,
            "18-30": 0,
            "31-50": 0,
            "51-70": 0,
            "70+": 0
        }
        
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
                "end_date": end_date.isoformat()
            },
            "new_patients": new_patients,
            "active_patients": active_patients,
            "returning_patients": returning_patients,
            "retention_rate": (returning_patients / active_patients * 100) if active_patients > 0 else 0,
            "age_distribution": age_groups
        }
    
    @staticmethod
    def get_revenue_statistics(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: Optional[str] = None
    ) -> Dict[str, Any]:
        """Получение статистики доходов"""
        # Получаем успешные платежи за период
        payments = db.query(PaymentWebhook).filter(
            and_(
                PaymentWebhook.status == "success",
                PaymentWebhook.created_at >= start_date,
                PaymentWebhook.created_at <= end_date
            )
        ).all()
        
        total_revenue = sum(float(p.amount) / 100 for p in payments)  # Конвертируем из тийинов
        
        # Доходы по дням
        daily_revenue = {}
        for payment in payments:
            date_str = payment.created_at.strftime("%Y-%m-%d")
            daily_revenue[date_str] = daily_revenue.get(date_str, 0) + float(payment.amount) / 100
        
        # Доходы по провайдерам
        provider_revenue = {}
        for payment in payments:
            provider = payment.provider or "unknown"
            provider_revenue[provider] = provider_revenue.get(provider, 0) + float(payment.amount) / 100
        
        # Средний чек
        avg_check = total_revenue / len(payments) if payments else 0
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "total_revenue": total_revenue,
            "total_transactions": len(payments),
            "average_check": avg_check,
            "daily_revenue": daily_revenue,
            "by_provider": provider_revenue
        }
    
    @staticmethod
    def get_service_statistics(
        db: Session,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Получение статистики услуг"""
        # Получаем все услуги
        services = db.query(Service).all()
        
        service_stats = {}
        for service in services:
            # Подсчитываем количество визитов с этой услугой
            visit_count = db.query(Visit).filter(
                and_(
                    Visit.date >= start_date,
                    Visit.date <= end_date
                )
            ).join(Visit.services).filter(Service.id == service.id).count()
            
            service_stats[service.name] = {
                "id": service.id,
                "name": service.name,
                "price": float(service.price) if service.price else 0,
                "visit_count": visit_count,
                "total_revenue": visit_count * float(service.price) if service.price else 0
            }
        
        # Сортируем по популярности
        sorted_services = sorted(
            service_stats.values(),
            key=lambda x: x["visit_count"],
            reverse=True
        )
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "total_services": len(services),
            "services": sorted_services,
            "top_services": sorted_services[:5]  # Топ-5 услуг
        }
    
    @staticmethod
    def get_queue_statistics(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: Optional[str] = None
    ) -> Dict[str, Any]:
        """Получение статистики очередей"""
        # Импортируем здесь, чтобы избежать циклических импортов
        from app.models.online_queue import DailyQueue, QueueEntry
        
        # Получаем статистику очередей
        queue_query = db.query(DailyQueue).filter(
            and_(
                DailyQueue.date >= start_date.date(),
                DailyQueue.date <= end_date.date()
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
                department_stats[dept] = {
                    "total_entries": 0,
                    "served": 0,
                    "waiting": 0
                }
            
            department_stats[dept]["total_entries"] += queue.total_entries
            department_stats[dept]["served"] += queue.served
            department_stats[dept]["waiting"] += queue.waiting
        
        return {
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "total_queues": total_queues,
            "total_entries": total_entries,
            "total_served": total_served,
            "total_waiting": total_waiting,
            "service_rate": (total_served / total_entries * 100) if total_entries > 0 else 0,
            "average_wait_time": avg_wait_time,
            "by_department": department_stats
        }
    
    @staticmethod
    def get_comprehensive_report(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        department: Optional[str] = None
    ) -> Dict[str, Any]:
        """Получение комплексного отчёта"""
        return {
            "report_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "generated_at": datetime.utcnow().isoformat()
            },
            "visits": AnalyticsService.get_visit_statistics(db, start_date, end_date, department),
            "patients": AnalyticsService.get_patient_statistics(db, start_date, end_date),
            "revenue": AnalyticsService.get_revenue_statistics(db, start_date, end_date, department),
            "services": AnalyticsService.get_service_statistics(db, start_date, end_date),
            "queues": AnalyticsService.get_queue_statistics(db, start_date, end_date, department)
        }
    
    @staticmethod
    def get_trends(
        db: Session,
        days: int = 30
    ) -> Dict[str, Any]:
        """Получение трендов за последние N дней"""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Тренд визитов
        visit_trend = []
        for i in range(days):
            date = start_date + timedelta(days=i)
            next_date = date + timedelta(days=1)
            
            visit_count = db.query(Visit).filter(
                and_(
                    Visit.date >= date,
                    Visit.date < next_date
                )
            ).count()
            
            visit_trend.append({
                "date": date.strftime("%Y-%m-%d"),
                "visits": visit_count
            })
        
        # Тренд доходов
        revenue_trend = []
        for i in range(days):
            date = start_date + timedelta(days=i)
            next_date = date + timedelta(days=1)
            
            daily_revenue = db.query(PaymentWebhook).filter(
                and_(
                    PaymentWebhook.status == "success",
                    PaymentWebhook.created_at >= date,
                    PaymentWebhook.created_at < next_date
                )
            ).all()
            
            total = sum(float(p.amount) / 100 for p in daily_revenue)
            
            revenue_trend.append({
                "date": date.strftime("%Y-%m-%d"),
                "revenue": total
            })
        
        return {
            "period_days": days,
            "visit_trend": visit_trend,
            "revenue_trend": revenue_trend
        }

# Создаём глобальный экземпляр сервиса
analytics_service = AnalyticsService()

