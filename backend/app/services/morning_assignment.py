"""
Сервис утренней сборки для присвоения номеров в очередях
Запускается каждое утро для обработки подтвержденных визитов на текущий день
"""
from datetime import date, datetime
from typing import Dict, List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.session import SessionLocal
from app.models.visit import Visit, VisitService
from app.models.service import Service
from app.models.user import User
from app.models.patient import Patient
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.crud import online_queue as crud_queue

import logging

logger = logging.getLogger(__name__)

class MorningAssignmentService:
    """Сервис утренней сборки для присвоения номеров в очередях"""
    
    def __init__(self):
        self.db: Optional[Session] = None
        
    def __enter__(self):
        self.db = SessionLocal()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()
    
    def run_morning_assignment(self, target_date: Optional[date] = None) -> Dict[str, any]:
        """
        Основная функция утренней сборки
        Присваивает номера всем подтвержденным визитам на указанную дату
        """
        if not target_date:
            target_date = date.today()
            
        logger.info(f"🌅 Запуск утренней сборки для {target_date}")
        
        try:
            # Получаем все подтвержденные визиты на сегодня без номеров в очередях
            confirmed_visits = self._get_confirmed_visits_without_queues(target_date)
            
            if not confirmed_visits:
                logger.info(f"✅ Нет подтвержденных визитов без номеров на {target_date}")
                return {
                    "success": True,
                    "message": f"Нет визитов для обработки на {target_date}",
                    "processed_visits": 0,
                    "assigned_queues": 0,
                    "errors": []
                }
            
            logger.info(f"📋 Найдено {len(confirmed_visits)} подтвержденных визитов для обработки")
            
            processed_count = 0
            assigned_queues_count = 0
            errors = []
            
            for visit in confirmed_visits:
                try:
                    queue_assignments = self._assign_queues_for_visit(visit, target_date)
                    if queue_assignments:
                        processed_count += 1
                        assigned_queues_count += len(queue_assignments)
                        
                        # Обновляем статус визита
                        visit.status = "open"  # Готов к приему
                        
                        logger.info(f"✅ Визит {visit.id}: присвоено {len(queue_assignments)} номеров")
                    else:
                        logger.warning(f"⚠️ Визит {visit.id}: не удалось присвоить номера")
                        
                except Exception as e:
                    error_msg = f"Ошибка обработки визита {visit.id}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            # Сохраняем изменения
            self.db.commit()
            
            result = {
                "success": True,
                "message": f"Утренняя сборка завершена для {target_date}",
                "processed_visits": processed_count,
                "assigned_queues": assigned_queues_count,
                "errors": errors,
                "date": target_date.isoformat()
            }
            
            logger.info(f"🎉 Утренняя сборка завершена: {processed_count} визитов, {assigned_queues_count} номеров")
            return result
            
        except Exception as e:
            self.db.rollback()
            error_msg = f"Критическая ошибка утренней сборки: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "message": error_msg,
                "processed_visits": 0,
                "assigned_queues": 0,
                "errors": [error_msg]
            }
    
    def _get_confirmed_visits_without_queues(self, target_date: date) -> List[Visit]:
        """Получает подтвержденные визиты на указанную дату без номеров в очередях"""
        
        # Находим визиты со статусом "confirmed" на указанную дату
        confirmed_visits = self.db.query(Visit).filter(
            and_(
                Visit.visit_date == target_date,
                Visit.status == "confirmed",
                Visit.confirmed_at.isnot(None)
            )
        ).all()
        
        # Фильтруем визиты, у которых еще нет записей в очередях
        visits_without_queues = []
        
        for visit in confirmed_visits:
            # Проверяем есть ли уже записи в очередях для этого визита
            existing_queue_entries = self.db.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.patient_id == visit.patient_id
            ).join(DailyQueue).filter(
                DailyQueue.day == target_date
            ).all()
            
            # Если нет записей в очередях или они не покрывают все услуги визита
            if not existing_queue_entries:
                visits_without_queues.append(visit)
                continue
                
            # Проверяем покрывают ли существующие записи все queue_tag визита
            visit_queue_tags = self._get_visit_queue_tags(visit)
            existing_queue_tags = set()
            
            for entry in existing_queue_entries:
                queue = self.db.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).first()
                if queue and queue.queue_tag:
                    existing_queue_tags.add(queue.queue_tag)
            
            # Если не все queue_tag покрыты, добавляем визит для обработки
            if not visit_queue_tags.issubset(existing_queue_tags):
                visits_without_queues.append(visit)
        
        return visits_without_queues
    
    def _get_visit_queue_tags(self, visit: Visit) -> set:
        """Получает все queue_tag для услуг визита"""
        visit_services = self.db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
        
        queue_tags = set()
        for vs in visit_services:
            service = self.db.query(Service).filter(Service.id == vs.service_id).first()
            if service and service.queue_tag:
                queue_tags.add(service.queue_tag)
        
        return queue_tags
    
    def _assign_queues_for_visit(self, visit: Visit, target_date: date) -> List[Dict[str, any]]:
        """Присваивает номера в очередях для конкретного визита"""
        
        # Получаем уникальные queue_tag из услуг визита
        unique_queue_tags = self._get_visit_queue_tags(visit)
        
        if not unique_queue_tags:
            logger.warning(f"Визит {visit.id}: нет queue_tag в услугах")
            return []
        
        queue_assignments = []
        
        for queue_tag in unique_queue_tags:
            try:
                assignment = self._assign_single_queue(visit, queue_tag, target_date)
                if assignment:
                    queue_assignments.append(assignment)
            except Exception as e:
                logger.error(f"Ошибка присвоения очереди {queue_tag} для визита {visit.id}: {e}")
        
        return queue_assignments
    
    def _assign_single_queue(self, visit: Visit, queue_tag: str, target_date: date) -> Optional[Dict[str, any]]:
        """Присваивает номер в конкретной очереди"""
        
        # Определяем врача для очереди
        doctor_id = visit.doctor_id
        
        # Для очередей без конкретного врача используем ресурс-врачей
        if queue_tag == "ecg" and not doctor_id:
            ecg_resource = self.db.query(User).filter(
                User.username == "ecg_resource",
                User.is_active == True
            ).first()
            if ecg_resource:
                doctor_id = ecg_resource.id
            else:
                logger.warning(f"ЭКГ ресурс-врач не найден для queue_tag={queue_tag}")
                return None
                
        elif queue_tag == "lab" and not doctor_id:
            lab_resource = self.db.query(User).filter(
                User.username == "lab_resource",
                User.is_active == True
            ).first()
            if lab_resource:
                doctor_id = lab_resource.id
            else:
                logger.warning(f"Лаборатория ресурс-врач не найден для queue_tag={queue_tag}")
                return None
        
        if not doctor_id:
            logger.warning(f"Не найден врач для queue_tag={queue_tag}, visit_id={visit.id}")
            return None
        
        # Получаем или создаем дневную очередь
        daily_queue = crud_queue.get_or_create_daily_queue(self.db, target_date, doctor_id, queue_tag)
        
        # Проверяем нет ли уже записи для этого пациента в этой очереди
        existing_entry = self.db.query(OnlineQueueEntry).filter(
            and_(
                OnlineQueueEntry.queue_id == daily_queue.id,
                OnlineQueueEntry.patient_id == visit.patient_id
            )
        ).first()
        
        if existing_entry:
            logger.info(f"Пациент {visit.patient_id} уже есть в очереди {queue_tag}")
            return {
                "queue_tag": queue_tag,
                "queue_id": daily_queue.id,
                "number": existing_entry.number,
                "status": "existing"
            }
        
        # Подсчитываем текущее количество записей в очереди
        current_count = crud_queue.count_queue_entries(self.db, daily_queue.id)
        next_number = 1 + current_count  # Начинаем с 1
        
        # Создаем запись в очереди
        queue_entry = OnlineQueueEntry(
            queue_id=daily_queue.id,
            patient_id=visit.patient_id,
            number=next_number,
            status="waiting",
            source="morning_assignment",  # Источник: утренняя сборка
            visit_id=visit.id  # Связываем с визитом
        )
        self.db.add(queue_entry)
        
        logger.info(f"Присвоен номер {next_number} в очереди {queue_tag} для пациента {visit.patient_id}")
        
        return {
            "queue_tag": queue_tag,
            "queue_id": daily_queue.id,
            "number": next_number,
            "status": "assigned"
        }
    
    def get_morning_assignment_stats(self, target_date: Optional[date] = None) -> Dict[str, any]:
        """Получает статистику утренней сборки"""
        if not target_date:
            target_date = date.today()
        
        # Подтвержденные визиты на дату
        confirmed_visits = self.db.query(Visit).filter(
            and_(
                Visit.visit_date == target_date,
                Visit.status.in_(["confirmed", "open"]),
                Visit.confirmed_at.isnot(None)
            )
        ).count()
        
        # Визиты со статусом "open" (уже обработанные)
        processed_visits = self.db.query(Visit).filter(
            and_(
                Visit.visit_date == target_date,
                Visit.status == "open"
            )
        ).count()
        
        # Записи в очередях на дату
        queue_entries = self.db.query(OnlineQueueEntry).join(DailyQueue).filter(
            DailyQueue.day == target_date
        ).count()
        
        return {
            "date": target_date.isoformat(),
            "confirmed_visits": confirmed_visits,
            "processed_visits": processed_visits,
            "queue_entries": queue_entries,
            "pending_processing": confirmed_visits - processed_visits
        }


# Глобальная функция для запуска утренней сборки
def run_morning_assignment(target_date: Optional[date] = None) -> Dict[str, any]:
    """
    Запускает утреннюю сборку для присвоения номеров в очередях
    Может быть вызвана из cron job или API эндпоинта
    """
    with MorningAssignmentService() as service:
        return service.run_morning_assignment(target_date)


def get_assignment_stats(target_date: Optional[date] = None) -> Dict[str, any]:
    """Получает статистику утренней сборки"""
    with MorningAssignmentService() as service:
        return service.get_morning_assignment_stats(target_date)


# Функция для тестирования
def test_morning_assignment():
    """Тестовая функция для проверки утренней сборки"""
    logger.info("🧪 Запуск тестирования утренней сборки")
    
    result = run_morning_assignment()
    stats = get_assignment_stats()
    
    print("📊 Результат утренней сборки:")
    print(f"  Успех: {result['success']}")
    print(f"  Обработано визитов: {result['processed_visits']}")
    print(f"  Присвоено номеров: {result['assigned_queues']}")
    print(f"  Ошибки: {len(result['errors'])}")
    
    print("\n📈 Статистика:")
    print(f"  Подтвержденные визиты: {stats['confirmed_visits']}")
    print(f"  Обработанные визиты: {stats['processed_visits']}")
    print(f"  Записи в очередях: {stats['queue_entries']}")
    print(f"  Ожидают обработки: {stats['pending_processing']}")
    
    return result, stats


if __name__ == "__main__":
    # Запуск тестирования при прямом вызове
    test_morning_assignment()
