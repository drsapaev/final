"""
Сервис для точного расчета среднего времени ожидания в аналитике
Анализирует реальные данные о времени ожидания пациентов в очередях
"""

import logging
from datetime import date, datetime, timedelta
from statistics import mean, median
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, asc, desc, func, or_, text
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.visit import Visit
from app.services.doctor_info_service import get_doctor_info_service

logger = logging.getLogger(__name__)


class WaitTimeAnalyticsService:
    """Сервис для анализа времени ожидания пациентов"""

    def __init__(self, db: Session):
        self.db = db
        self.doctor_info_service = get_doctor_info_service(db)

    # ===================== ОСНОВНЫЕ МЕТОДЫ РАСЧЕТА =====================

    def calculate_accurate_wait_times(
        self,
        start_date: date,
        end_date: date,
        department: Optional[str] = None,
        doctor_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Рассчитывает точное время ожидания за период"""
        try:
            # Получаем данные очередей за период
            queue_data = self._get_queue_entries_with_times(
                start_date, end_date, department, doctor_id
            )

            if not queue_data:
                return self._get_empty_wait_time_stats()

            # Рассчитываем различные метрики времени ожидания
            wait_times = []
            department_stats = {}
            doctor_stats = {}
            hourly_stats = {}
            daily_stats = {}

            for entry in queue_data:
                wait_time = self._calculate_entry_wait_time(entry)
                if wait_time is not None:
                    wait_times.append(wait_time)

                    # Группируем по отделениям
                    dept = entry.get('department', 'Неизвестно')
                    if dept not in department_stats:
                        department_stats[dept] = []
                    department_stats[dept].append(wait_time)

                    # Группируем по врачам
                    doctor = entry.get('doctor_name', 'Неизвестно')
                    if doctor not in doctor_stats:
                        doctor_stats[doctor] = []
                    doctor_stats[doctor].append(wait_time)

                    # Группируем по часам
                    hour = entry.get('created_at', datetime.now()).hour
                    if hour not in hourly_stats:
                        hourly_stats[hour] = []
                    hourly_stats[hour].append(wait_time)

                    # Группируем по дням
                    day = entry.get('visit_date', date.today())
                    if day not in daily_stats:
                        daily_stats[day] = []
                    daily_stats[day].append(wait_time)

            # Рассчитываем итоговые метрики
            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "total_entries": len(queue_data),
                    "analyzed_entries": len(wait_times),
                },
                "overall_stats": self._calculate_wait_time_stats(wait_times),
                "department_breakdown": {
                    dept: self._calculate_wait_time_stats(times)
                    for dept, times in department_stats.items()
                },
                "doctor_breakdown": {
                    doctor: self._calculate_wait_time_stats(times)
                    for doctor, times in doctor_stats.items()
                },
                "hourly_breakdown": {
                    f"{hour:02d}:00": self._calculate_wait_time_stats(times)
                    for hour, times in hourly_stats.items()
                },
                "daily_breakdown": {
                    day.isoformat(): self._calculate_wait_time_stats(times)
                    for day, times in daily_stats.items()
                },
                "trends": self._calculate_wait_time_trends(daily_stats),
                "recommendations": self._generate_wait_time_recommendations(
                    wait_times, department_stats, doctor_stats
                ),
            }

        except Exception as e:
            logger.error(f"Ошибка расчета времени ожидания: {e}")
            return self._get_empty_wait_time_stats()

    def get_real_time_wait_estimates(
        self, department: Optional[str] = None
    ) -> Dict[str, Any]:
        """Получает текущие оценки времени ожидания в реальном времени"""
        try:
            today = date.today()
            current_time = datetime.now()

            # Получаем активные очереди на сегодня
            query = self.db.query(DailyQueue).filter(DailyQueue.queue_date == today)
            if department:
                query = query.filter(DailyQueue.department.ilike(f"%{department}%"))

            active_queues = query.all()

            estimates = {}
            for queue in active_queues:
                # Получаем текущие записи в очереди
                current_entries = (
                    self.db.query(OnlineQueueEntry)
                    .filter(
                        and_(
                            OnlineQueueEntry.queue_id == queue.id,
                            OnlineQueueEntry.status.in_(["waiting", "confirmed"]),
                        )
                    )
                    .order_by(OnlineQueueEntry.queue_number)
                    .all()
                )

                if not current_entries:
                    continue

                # Рассчитываем оценку времени ожидания
                queue_estimate = self._estimate_current_wait_time(
                    queue, current_entries, current_time
                )

                queue_key = f"{queue.department}_{queue.doctor_name}_{queue.id}"
                estimates[queue_key] = {
                    "queue_id": queue.id,
                    "department": queue.department,
                    "doctor_name": queue.doctor_name,
                    "doctor_id": queue.doctor_id,
                    "current_queue_length": len(current_entries),
                    "estimated_wait_time_minutes": queue_estimate[
                        "estimated_wait_minutes"
                    ],
                    "confidence_level": queue_estimate["confidence"],
                    "next_available_slot": queue_estimate["next_slot"],
                    "average_service_time": queue_estimate["avg_service_time"],
                    "last_updated": current_time.isoformat(),
                }

            return {
                "timestamp": current_time.isoformat(),
                "queues": estimates,
                "summary": {
                    "total_active_queues": len(estimates),
                    "shortest_wait": (
                        min(
                            [
                                q["estimated_wait_time_minutes"]
                                for q in estimates.values()
                            ]
                        )
                        if estimates
                        else 0
                    ),
                    "longest_wait": (
                        max(
                            [
                                q["estimated_wait_time_minutes"]
                                for q in estimates.values()
                            ]
                        )
                        if estimates
                        else 0
                    ),
                    "average_wait": (
                        mean(
                            [
                                q["estimated_wait_time_minutes"]
                                for q in estimates.values()
                            ]
                        )
                        if estimates
                        else 0
                    ),
                },
            }

        except Exception as e:
            logger.error(
                f"Ошибка получения оценок времени ожидания в реальном времени: {e}"
            )
            return {
                "timestamp": datetime.now().isoformat(),
                "queues": {},
                "summary": {},
            }

    def get_wait_time_analytics_by_service(
        self,
        start_date: date,
        end_date: date,
        service_codes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Анализ времени ожидания по типам услуг"""
        try:
            # Получаем данные визитов с услугами
            from app.models.visit import VisitService

            query = (
                self.db.query(
                    VisitService.service_code,
                    VisitService.name,
                    Visit.visit_date,
                    Visit.created_at,
                    Visit.appointment_time,
                    OnlineQueueEntry.created_at.label('queue_created'),
                    OnlineQueueEntry.queue_number,
                    OnlineQueueEntry.status,
                )
                .join(Visit, VisitService.visit_id == Visit.id)
                .outerjoin(OnlineQueueEntry, OnlineQueueEntry.visit_id == Visit.id)
                .filter(
                    and_(Visit.visit_date >= start_date, Visit.visit_date <= end_date)
                )
            )

            if service_codes:
                query = query.filter(VisitService.service_code.in_(service_codes))

            results = query.all()

            service_stats = {}
            for result in results:
                service_code = result.service_code
                if service_code not in service_stats:
                    service_stats[service_code] = {
                        "service_name": result.name,
                        "wait_times": [],
                        "total_visits": 0,
                    }

                service_stats[service_code]["total_visits"] += 1

                # Рассчитываем время ожидания для этой услуги
                if result.queue_created and result.appointment_time:
                    wait_time = self._calculate_service_wait_time(result)
                    if wait_time is not None:
                        service_stats[service_code]["wait_times"].append(wait_time)

            # Формируем итоговую статистику
            analytics = {}
            for service_code, data in service_stats.items():
                wait_times = data["wait_times"]
                analytics[service_code] = {
                    "service_name": data["service_name"],
                    "total_visits": data["total_visits"],
                    "analyzed_visits": len(wait_times),
                    "wait_time_stats": (
                        self._calculate_wait_time_stats(wait_times)
                        if wait_times
                        else None
                    ),
                    "service_efficiency": self._calculate_service_efficiency(
                        wait_times, data["total_visits"]
                    ),
                }

            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                "service_analytics": analytics,
                "summary": {
                    "total_services": len(analytics),
                    "best_performing_service": self._find_best_service(analytics),
                    "worst_performing_service": self._find_worst_service(analytics),
                    "recommendations": self._generate_service_recommendations(
                        analytics
                    ),
                },
            }

        except Exception as e:
            logger.error(f"Ошибка анализа времени ожидания по услугам: {e}")
            return {"period": {}, "service_analytics": {}, "summary": {}}

    # ===================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ =====================

    def _get_queue_entries_with_times(
        self,
        start_date: date,
        end_date: date,
        department: Optional[str] = None,
        doctor_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Получает записи очередей с временными метками"""
        try:
            query = (
                self.db.query(
                    OnlineQueueEntry.id,
                    OnlineQueueEntry.queue_id,
                    OnlineQueueEntry.patient_id,
                    OnlineQueueEntry.patient_name,
                    OnlineQueueEntry.queue_number,
                    OnlineQueueEntry.status,
                    OnlineQueueEntry.created_at,
                    OnlineQueueEntry.visit_date,
                    OnlineQueueEntry.confirmed_at,
                    DailyQueue.department,
                    DailyQueue.doctor_name,
                    DailyQueue.doctor_id,
                    DailyQueue.queue_date,
                )
                .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
                .filter(
                    and_(
                        OnlineQueueEntry.visit_date >= start_date,
                        OnlineQueueEntry.visit_date <= end_date,
                    )
                )
            )

            if department:
                query = query.filter(DailyQueue.department.ilike(f"%{department}%"))

            if doctor_id:
                query = query.filter(DailyQueue.doctor_id == doctor_id)

            results = query.all()

            # Преобразуем в список словарей
            entries = []
            for result in results:
                entries.append(
                    {
                        "id": result.id,
                        "queue_id": result.queue_id,
                        "patient_id": result.patient_id,
                        "patient_name": result.patient_name,
                        "queue_number": result.queue_number,
                        "status": result.status,
                        "created_at": result.created_at,
                        "visit_date": result.visit_date,
                        "confirmed_at": result.confirmed_at,
                        "department": result.department,
                        "doctor_name": result.doctor_name,
                        "doctor_id": result.doctor_id,
                        "queue_date": result.queue_date,
                    }
                )

            return entries

        except Exception as e:
            logger.error(f"Ошибка получения записей очередей: {e}")
            return []

    def _calculate_entry_wait_time(self, entry: Dict[str, Any]) -> Optional[float]:
        """Рассчитывает время ожидания для записи в очереди (в минутах)"""
        try:
            created_at = entry.get("created_at")
            confirmed_at = entry.get("confirmed_at")
            queue_number = entry.get("queue_number")

            if not created_at:
                return None

            # Если есть время подтверждения, используем его
            if confirmed_at:
                wait_time = (confirmed_at - created_at).total_seconds() / 60
                return max(0, wait_time)  # Не может быть отрицательным

            # Если нет времени подтверждения, оцениваем по номеру в очереди
            if queue_number:
                # Предполагаем среднее время обслуживания 15 минут на пациента
                estimated_wait = queue_number * 15
                return estimated_wait

            return None

        except Exception as e:
            logger.error(f"Ошибка расчета времени ожидания для записи: {e}")
            return None

    def _calculate_wait_time_stats(self, wait_times: List[float]) -> Dict[str, Any]:
        """Рассчитывает статистические метрики времени ожидания"""
        if not wait_times:
            return {
                "count": 0,
                "average_minutes": 0,
                "median_minutes": 0,
                "min_minutes": 0,
                "max_minutes": 0,
                "std_deviation": 0,
                "percentile_75": 0,
                "percentile_90": 0,
                "percentile_95": 0,
            }

        try:
            sorted_times = sorted(wait_times)
            count = len(wait_times)

            return {
                "count": count,
                "average_minutes": round(mean(wait_times), 2),
                "median_minutes": round(median(wait_times), 2),
                "min_minutes": round(min(wait_times), 2),
                "max_minutes": round(max(wait_times), 2),
                "std_deviation": round(self._calculate_std_deviation(wait_times), 2),
                "percentile_75": (
                    round(sorted_times[int(count * 0.75)], 2) if count > 0 else 0
                ),
                "percentile_90": (
                    round(sorted_times[int(count * 0.90)], 2) if count > 0 else 0
                ),
                "percentile_95": (
                    round(sorted_times[int(count * 0.95)], 2) if count > 0 else 0
                ),
            }

        except Exception as e:
            logger.error(f"Ошибка расчета статистики времени ожидания: {e}")
            return {"count": 0, "average_minutes": 0}

    def _calculate_std_deviation(self, values: List[float]) -> float:
        """Рассчитывает стандартное отклонение"""
        if len(values) < 2:
            return 0

        avg = mean(values)
        variance = sum((x - avg) ** 2 for x in values) / (len(values) - 1)
        return variance**0.5

    def _estimate_current_wait_time(
        self,
        queue: DailyQueue,
        current_entries: List[OnlineQueueEntry],
        current_time: datetime,
    ) -> Dict[str, Any]:
        """Оценивает текущее время ожидания для очереди"""
        try:
            # Получаем историческое среднее время обслуживания для этого врача
            avg_service_time = self._get_average_service_time(queue.doctor_id)

            # Рассчитываем позицию в очереди
            current_position = len(
                [e for e in current_entries if e.status == "waiting"]
            )

            # Оценка времени ожидания
            estimated_wait = current_position * avg_service_time

            # Корректируем на основе текущего времени дня
            time_factor = self._get_time_of_day_factor(current_time.hour)
            estimated_wait *= time_factor

            # Уровень уверенности в оценке
            confidence = self._calculate_estimate_confidence(queue, current_entries)

            return {
                "estimated_wait_minutes": round(estimated_wait, 1),
                "avg_service_time": avg_service_time,
                "confidence": confidence,
                "next_slot": (
                    current_time + timedelta(minutes=estimated_wait)
                ).isoformat(),
            }

        except Exception as e:
            logger.error(f"Ошибка оценки времени ожидания: {e}")
            return {
                "estimated_wait_minutes": 30,  # Значение по умолчанию
                "avg_service_time": 15,
                "confidence": 0.5,
                "next_slot": (current_time + timedelta(minutes=30)).isoformat(),
            }

    def _get_average_service_time(self, doctor_id: Optional[int]) -> float:
        """Получает среднее время обслуживания для врача"""
        try:
            if not doctor_id:
                return 15.0  # Значение по умолчанию

            # Получаем данные за последние 30 дней
            thirty_days_ago = date.today() - timedelta(days=30)

            # Здесь можно добавить более сложную логику расчета
            # на основе реальных данных о времени приема

            # Пока возвращаем значения по умолчанию в зависимости от специализации
            doctor_info = self.doctor_info_service.get_doctor_full_info(doctor_id)
            specialization = doctor_info.get("specialization", "").lower()

            if "кардиолог" in specialization:
                return 20.0
            elif "стоматолог" in specialization:
                return 30.0
            elif "дерматолог" in specialization:
                return 15.0
            else:
                return 15.0

        except Exception as e:
            logger.error(f"Ошибка получения среднего времени обслуживания: {e}")
            return 15.0

    def _get_time_of_day_factor(self, hour: int) -> float:
        """Получает коэффициент корректировки времени в зависимости от часа дня"""
        # Утренние часы (8-10) - больше времени на прием
        if 8 <= hour <= 10:
            return 1.2
        # Обеденное время (12-14) - может быть задержка
        elif 12 <= hour <= 14:
            return 1.3
        # Вечерние часы (16-18) - ускоренный прием
        elif 16 <= hour <= 18:
            return 0.9
        else:
            return 1.0

    def _calculate_estimate_confidence(
        self, queue: DailyQueue, current_entries: List[OnlineQueueEntry]
    ) -> float:
        """Рассчитывает уровень уверенности в оценке времени ожидания"""
        try:
            # Базовый уровень уверенности
            confidence = 0.7

            # Увеличиваем уверенность, если очередь небольшая
            if len(current_entries) <= 3:
                confidence += 0.2
            elif len(current_entries) <= 5:
                confidence += 0.1

            # Уменьшаем уверенность для больших очередей
            if len(current_entries) > 10:
                confidence -= 0.2

            # Корректируем на основе времени дня
            current_hour = datetime.now().hour
            if 9 <= current_hour <= 17:  # Рабочие часы
                confidence += 0.1

            return max(0.1, min(1.0, confidence))

        except Exception as e:
            logger.error(f"Ошибка расчета уверенности оценки: {e}")
            return 0.5

    def _calculate_service_wait_time(self, result) -> Optional[float]:
        """Рассчитывает время ожидания для конкретной услуги"""
        try:
            if result.queue_created and result.appointment_time:
                # Создаем datetime объект для времени приема
                appointment_datetime = datetime.combine(
                    result.visit_date, result.appointment_time
                )
                wait_time = (
                    appointment_datetime - result.queue_created
                ).total_seconds() / 60
                return max(0, wait_time)
            return None
        except Exception as e:
            logger.error(f"Ошибка расчета времени ожидания услуги: {e}")
            return None

    def _calculate_service_efficiency(
        self, wait_times: List[float], total_visits: int
    ) -> Dict[str, Any]:
        """Рассчитывает эффективность обслуживания для услуги"""
        if not wait_times or total_visits == 0:
            return {"efficiency_score": 0, "coverage": 0}

        avg_wait = mean(wait_times)
        coverage = len(wait_times) / total_visits

        # Эффективность обратно пропорциональна времени ожидания
        efficiency_score = max(
            0, 100 - (avg_wait / 2)
        )  # 100% при 0 минут, 0% при 200+ минут

        return {
            "efficiency_score": round(efficiency_score, 1),
            "coverage": round(coverage * 100, 1),
        }

    def _calculate_wait_time_trends(
        self, daily_stats: Dict[date, List[float]]
    ) -> Dict[str, Any]:
        """Рассчитывает тренды времени ожидания"""
        try:
            if not daily_stats:
                return {"trend": "stable", "change_percent": 0}

            # Сортируем по датам
            sorted_days = sorted(daily_stats.keys())
            daily_averages = [
                mean(daily_stats[day]) for day in sorted_days if daily_stats[day]
            ]

            if len(daily_averages) < 2:
                return {"trend": "stable", "change_percent": 0}

            # Рассчитываем тренд
            first_half = daily_averages[: len(daily_averages) // 2]
            second_half = daily_averages[len(daily_averages) // 2 :]

            first_avg = mean(first_half)
            second_avg = mean(second_half)

            change_percent = (
                ((second_avg - first_avg) / first_avg) * 100 if first_avg > 0 else 0
            )

            if change_percent > 10:
                trend = "increasing"
            elif change_percent < -10:
                trend = "decreasing"
            else:
                trend = "stable"

            return {
                "trend": trend,
                "change_percent": round(change_percent, 1),
                "daily_averages": {
                    day.isoformat(): round(avg, 1)
                    for day, avg in zip(sorted_days, daily_averages)
                },
            }

        except Exception as e:
            logger.error(f"Ошибка расчета трендов: {e}")
            return {"trend": "stable", "change_percent": 0}

    def _generate_wait_time_recommendations(
        self,
        wait_times: List[float],
        department_stats: Dict[str, List[float]],
        doctor_stats: Dict[str, List[float]],
    ) -> List[str]:
        """Генерирует рекомендации по улучшению времени ожидания"""
        recommendations = []

        if not wait_times:
            return ["Недостаточно данных для анализа"]

        avg_wait = mean(wait_times)

        # Общие рекомендации
        if avg_wait > 60:
            recommendations.append(
                "Среднее время ожидания превышает 1 час. Рекомендуется увеличить количество врачей или оптимизировать расписание."
            )
        elif avg_wait > 30:
            recommendations.append(
                "Время ожидания можно улучшить за счет более точного планирования приемов."
            )

        # Рекомендации по отделениям
        if department_stats:
            worst_dept = max(
                department_stats.items(), key=lambda x: mean(x[1]) if x[1] else 0
            )
            if worst_dept[1] and mean(worst_dept[1]) > avg_wait * 1.5:
                recommendations.append(
                    f"Отделение '{worst_dept[0]}' показывает наихудшие результаты. Требуется анализ загруженности."
                )

        # Рекомендации по врачам
        if doctor_stats:
            worst_doctor = max(
                doctor_stats.items(), key=lambda x: mean(x[1]) if x[1] else 0
            )
            if worst_doctor[1] and mean(worst_doctor[1]) > avg_wait * 2:
                recommendations.append(
                    f"Врач '{worst_doctor[0]}' имеет самое долгое время ожидания. Рекомендуется пересмотр расписания."
                )

        return recommendations

    def _find_best_service(self, analytics: Dict[str, Any]) -> Optional[str]:
        """Находит услугу с лучшими показателями времени ожидания"""
        try:
            best_service = None
            best_score = float('inf')

            for service_code, data in analytics.items():
                stats = data.get("wait_time_stats")
                if stats and stats.get("average_minutes", float('inf')) < best_score:
                    best_score = stats["average_minutes"]
                    best_service = service_code

            return best_service
        except Exception:
            return None

    def _find_worst_service(self, analytics: Dict[str, Any]) -> Optional[str]:
        """Находит услугу с худшими показателями времени ожидания"""
        try:
            worst_service = None
            worst_score = 0

            for service_code, data in analytics.items():
                stats = data.get("wait_time_stats")
                if stats and stats.get("average_minutes", 0) > worst_score:
                    worst_score = stats["average_minutes"]
                    worst_service = service_code

            return worst_service
        except Exception:
            return None

    def _generate_service_recommendations(self, analytics: Dict[str, Any]) -> List[str]:
        """Генерирует рекомендации по улучшению времени ожидания для услуг"""
        recommendations = []

        if not analytics:
            return ["Недостаточно данных для анализа услуг"]

        # Анализируем каждую услугу
        for service_code, data in analytics.items():
            stats = data.get("wait_time_stats")
            if stats:
                avg_wait = stats.get("average_minutes", 0)
                if avg_wait > 45:
                    recommendations.append(
                        f"Услуга '{data['service_name']}' имеет долгое время ожидания ({avg_wait:.1f} мин). Рекомендуется оптимизация процесса."
                    )

        return (
            recommendations
            if recommendations
            else ["Все услуги показывают приемлемое время ожидания"]
        )

    def _get_empty_wait_time_stats(self) -> Dict[str, Any]:
        """Возвращает пустую структуру статистики времени ожидания"""
        return {
            "period": {
                "start_date": "",
                "end_date": "",
                "total_entries": 0,
                "analyzed_entries": 0,
            },
            "overall_stats": {"count": 0, "average_minutes": 0},
            "department_breakdown": {},
            "doctor_breakdown": {},
            "hourly_breakdown": {},
            "daily_breakdown": {},
            "trends": {"trend": "stable", "change_percent": 0},
            "recommendations": ["Нет данных для анализа"],
        }


# Глобальный экземпляр сервиса
def get_wait_time_analytics_service(db: Session) -> WaitTimeAnalyticsService:
    """Получить экземпляр сервиса аналитики времени ожидания"""
    return WaitTimeAnalyticsService(db)
