"""
Сервис для безопасной миграции данных и обеспечения совместимости
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.visit import Visit
from app.models.appointment import Appointment
from app.models.patient import Patient
from app.core.config import settings

logger = logging.getLogger(__name__)

class MigrationService:
    """Сервис для безопасной миграции и совместимости данных"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def migrate_legacy_queue_data(self) -> Dict[str, Any]:
        """
        Мигрирует данные из старых таблиц очередей в новые
        """
        try:
            logger.info("Начинаем миграцию данных очередей...")
            
            migrated_count = 0
            errors = []
            
            # Проверяем существование старой таблицы queue_tickets
            try:
                result = self.db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='queue_tickets'"))
                if result.fetchone():
                    # Мигрируем данные из старой таблицы
                    migrated_count = self._migrate_from_queue_tickets()
                else:
                    logger.info("Старая таблица queue_tickets не найдена, миграция не требуется")
            except Exception as e:
                errors.append(f"Ошибка проверки старой таблицы: {str(e)}")
            
            # Проверяем целостность данных в новых таблицах
            integrity_result = self._check_data_integrity()
            
            return {
                "success": len(errors) == 0,
                "migrated_records": migrated_count,
                "errors": errors,
                "integrity_check": integrity_result
            }
            
        except Exception as e:
            logger.error(f"Ошибка миграции данных очередей: {e}")
            return {
                "success": False,
                "migrated_records": 0,
                "errors": [str(e)],
                "integrity_check": {"passed": False}
            }
    
    def _migrate_from_queue_tickets(self) -> int:
        """Мигрирует данные из старой таблицы queue_tickets"""
        try:
            # Получаем данные из старой таблицы
            old_tickets = self.db.execute(text("""
                SELECT 
                    ticket_number,
                    department,
                    date,
                    status,
                    patient_name,
                    phone,
                    created_at
                FROM queue_tickets 
                WHERE date >= date('now', '-30 days')
                ORDER BY created_at
            """)).fetchall()
            
            migrated_count = 0
            
            for ticket in old_tickets:
                try:
                    # Находим или создаем специалиста для отделения
                    specialist_id = self._get_specialist_for_department(ticket.department)
                    
                    if not specialist_id:
                        continue
                    
                    # Создаем или находим дневную очередь
                    daily_queue = self._get_or_create_daily_queue(
                        day=ticket.date,
                        specialist_id=specialist_id,
                        queue_tag=self._get_queue_tag_for_department(ticket.department)
                    )
                    
                    # Проверяем, не мигрирована ли уже эта запись
                    existing_entry = self.db.query(OnlineQueueEntry).filter(
                        and_(
                            OnlineQueueEntry.queue_id == daily_queue.id,
                            OnlineQueueEntry.number == ticket.ticket_number,
                            OnlineQueueEntry.phone == ticket.phone
                        )
                    ).first()
                    
                    if existing_entry:
                        continue  # Уже мигрировано
                    
                    # Создаем новую запись в очереди
                    queue_entry = OnlineQueueEntry(
                        queue_id=daily_queue.id,
                        number=ticket.ticket_number,
                        patient_name=ticket.patient_name,
                        phone=ticket.phone,
                        status=self._map_old_status_to_new(ticket.status),
                        source="migration",
                        created_at=ticket.created_at,
                        data_version="v1.0"
                    )
                    
                    self.db.add(queue_entry)
                    migrated_count += 1
                    
                except Exception as e:
                    logger.error(f"Ошибка миграции записи {ticket.ticket_number}: {e}")
                    continue
            
            self.db.commit()
            logger.info(f"Мигрировано {migrated_count} записей из старой таблицы")
            return migrated_count
            
        except Exception as e:
            logger.error(f"Ошибка миграции из queue_tickets: {e}")
            self.db.rollback()
            return 0
    
    def _get_specialist_for_department(self, department: str) -> Optional[int]:
        """Получает ID специалиста для отделения"""
        department_mapping = {
            "cardiology": "cardio",
            "dermatology": "derma", 
            "dentistry": "dentist",
            "general": "doctor"
        }
        
        role = department_mapping.get(department, "doctor")
        
        # Ищем пользователя с соответствующей ролью
        result = self.db.execute(text("""
            SELECT id FROM users 
            WHERE role = :role AND is_active = 1 
            LIMIT 1
        """), {"role": role})
        
        user = result.fetchone()
        return user.id if user else None
    
    def _get_queue_tag_for_department(self, department: str) -> str:
        """Получает тег очереди для отделения"""
        tag_mapping = {
            "cardiology": "cardiology_common",
            "dermatology": "dermatology",
            "dentistry": "stomatology",
            "general": "general"
        }
        return tag_mapping.get(department, "general")
    
    def _get_or_create_daily_queue(self, day: date, specialist_id: int, queue_tag: str) -> DailyQueue:
        """Получает или создает дневную очередь"""
        daily_queue = self.db.query(DailyQueue).filter(
            and_(
                DailyQueue.day == day,
                DailyQueue.specialist_id == specialist_id,
                DailyQueue.queue_tag == queue_tag
            )
        ).first()
        
        if not daily_queue:
            daily_queue = DailyQueue(
                day=day,
                specialist_id=specialist_id,
                queue_tag=queue_tag,
                active=True
            )
            self.db.add(daily_queue)
            self.db.flush()
        
        return daily_queue
    
    def _map_old_status_to_new(self, old_status: str) -> str:
        """Маппинг старых статусов в новые"""
        status_mapping = {
            "waiting": "waiting",
            "called": "called", 
            "served": "served",
            "completed": "served",
            "cancelled": "no_show",
            "no_show": "no_show"
        }
        return status_mapping.get(old_status, "waiting")
    
    def _check_data_integrity(self) -> Dict[str, Any]:
        """Проверяет целостность данных в новых таблицах"""
        try:
            checks = {}
            
            # 1. Проверяем уникальность номеров в очередях
            duplicate_numbers = self.db.execute(text("""
                SELECT queue_id, number, COUNT(*) as count
                FROM queue_entries 
                GROUP BY queue_id, number 
                HAVING COUNT(*) > 1
            """)).fetchall()
            
            checks["duplicate_numbers"] = {
                "passed": len(duplicate_numbers) == 0,
                "count": len(duplicate_numbers)
            }
            
            # 2. Проверяем связи с визитами
            orphaned_visits = self.db.execute(text("""
                SELECT COUNT(*) as count
                FROM queue_entries qe
                WHERE qe.visit_id IS NOT NULL 
                AND NOT EXISTS (SELECT 1 FROM visits v WHERE v.id = qe.visit_id)
            """)).fetchone()
            
            checks["orphaned_visits"] = {
                "passed": orphaned_visits.count == 0,
                "count": orphaned_visits.count
            }
            
            # 3. Проверяем связи с пациентами
            orphaned_patients = self.db.execute(text("""
                SELECT COUNT(*) as count
                FROM queue_entries qe
                WHERE qe.patient_id IS NOT NULL 
                AND NOT EXISTS (SELECT 1 FROM patients p WHERE p.id = qe.patient_id)
            """)).fetchone()
            
            checks["orphaned_patients"] = {
                "passed": orphaned_patients.count == 0,
                "count": orphaned_patients.count
            }
            
            # 4. Проверяем связи с очередями
            orphaned_queues = self.db.execute(text("""
                SELECT COUNT(*) as count
                FROM queue_entries qe
                WHERE NOT EXISTS (SELECT 1 FROM daily_queues dq WHERE dq.id = qe.queue_id)
            """)).fetchone()
            
            checks["orphaned_queues"] = {
                "passed": orphaned_queues.count == 0,
                "count": orphaned_queues.count
            }
            
            # Общий результат
            all_passed = all(check["passed"] for check in checks.values())
            
            return {
                "passed": all_passed,
                "checks": checks,
                "checked_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка проверки целостности данных: {e}")
            return {
                "passed": False,
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat()
            }
    
    def backup_queue_data(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Создает резервную копию данных очередей
        """
        try:
            if target_date is None:
                target_date = date.today()
            
            logger.info(f"Создаем резервную копию данных очередей за {target_date}")
            
            # Получаем все очереди за дату
            daily_queues = self.db.query(DailyQueue).filter(
                DailyQueue.day == target_date
            ).all()
            
            backup_data = {
                "backup_date": target_date.isoformat(),
                "created_at": datetime.utcnow().isoformat(),
                "queues": []
            }
            
            for queue in daily_queues:
                queue_data = {
                    "id": queue.id,
                    "day": queue.day.isoformat(),
                    "specialist_id": queue.specialist_id,
                    "queue_tag": queue.queue_tag,
                    "active": queue.active,
                    "opened_at": queue.opened_at.isoformat() if queue.opened_at else None,
                    "entries": []
                }
                
                # Получаем все записи в очереди
                for entry in queue.entries:
                    entry_data = {
                        "id": entry.id,
                        "number": entry.number,
                        "patient_id": entry.patient_id,
                        "patient_name": entry.patient_name,
                        "phone": entry.phone,
                        "telegram_id": entry.telegram_id,
                        "visit_id": entry.visit_id,
                        "source": entry.source,
                        "status": entry.status,
                        "created_at": entry.created_at.isoformat(),
                        "called_at": entry.called_at.isoformat() if entry.called_at else None,
                        "print_data": entry.print_data if hasattr(entry, 'print_data') else None,
                        "printed_at": entry.printed_at.isoformat() if hasattr(entry, 'printed_at') and entry.printed_at else None
                    }
                    queue_data["entries"].append(entry_data)
                
                backup_data["queues"].append(queue_data)
            
            # Сохраняем резервную копию в файл
            import json
            backup_filename = f"queue_backup_{target_date.strftime('%Y%m%d')}_{datetime.now().strftime('%H%M%S')}.json"
            backup_path = f"backups/{backup_filename}"
            
            # Создаем директорию если не существует
            import os
            os.makedirs("backups", exist_ok=True)
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            return {
                "success": True,
                "backup_file": backup_path,
                "queues_count": len(backup_data["queues"]),
                "total_entries": sum(len(q["entries"]) for q in backup_data["queues"])
            }
            
        except Exception as e:
            logger.error(f"Ошибка создания резервной копии: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def restore_queue_data(self, backup_file: str) -> Dict[str, Any]:
        """
        Восстанавливает данные очередей из резервной копии
        """
        try:
            logger.info(f"Восстанавливаем данные очередей из {backup_file}")
            
            import json
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            restored_queues = 0
            restored_entries = 0
            
            for queue_data in backup_data["queues"]:
                # Проверяем существование очереди
                existing_queue = self.db.query(DailyQueue).filter(
                    DailyQueue.id == queue_data["id"]
                ).first()
                
                if existing_queue:
                    logger.warning(f"Очередь {queue_data['id']} уже существует, пропускаем")
                    continue
                
                # Создаем очередь
                queue = DailyQueue(
                    id=queue_data["id"],
                    day=datetime.fromisoformat(queue_data["day"]).date(),
                    specialist_id=queue_data["specialist_id"],
                    queue_tag=queue_data["queue_tag"],
                    active=queue_data["active"],
                    opened_at=datetime.fromisoformat(queue_data["opened_at"]) if queue_data["opened_at"] else None
                )
                self.db.add(queue)
                self.db.flush()
                restored_queues += 1
                
                # Восстанавливаем записи в очереди
                for entry_data in queue_data["entries"]:
                    entry = OnlineQueueEntry(
                        id=entry_data["id"],
                        queue_id=queue.id,
                        number=entry_data["number"],
                        patient_id=entry_data["patient_id"],
                        patient_name=entry_data["patient_name"],
                        phone=entry_data["phone"],
                        telegram_id=entry_data["telegram_id"],
                        visit_id=entry_data["visit_id"],
                        source=entry_data["source"],
                        status=entry_data["status"],
                        created_at=datetime.fromisoformat(entry_data["created_at"]),
                        called_at=datetime.fromisoformat(entry_data["called_at"]) if entry_data["called_at"] else None
                    )
                    
                    # Добавляем новые поля если они есть
                    if "print_data" in entry_data and hasattr(entry, 'print_data'):
                        entry.print_data = entry_data["print_data"]
                    if "printed_at" in entry_data and entry_data["printed_at"] and hasattr(entry, 'printed_at'):
                        entry.printed_at = datetime.fromisoformat(entry_data["printed_at"])
                    
                    self.db.add(entry)
                    restored_entries += 1
            
            self.db.commit()
            
            return {
                "success": True,
                "restored_queues": restored_queues,
                "restored_entries": restored_entries
            }
            
        except Exception as e:
            logger.error(f"Ошибка восстановления данных: {e}")
            self.db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> Dict[str, Any]:
        """
        Очищает старые данные очередей
        """
        try:
            cutoff_date = date.today() - timedelta(days=days_to_keep)
            logger.info(f"Очищаем данные очередей старше {cutoff_date}")
            
            # Подсчитываем что будем удалять
            old_queues = self.db.query(DailyQueue).filter(
                DailyQueue.day < cutoff_date
            ).all()
            
            old_entries_count = sum(len(queue.entries) for queue in old_queues)
            
            # Удаляем старые очереди (записи удалятся каскадно)
            deleted_queues = self.db.query(DailyQueue).filter(
                DailyQueue.day < cutoff_date
            ).delete()
            
            self.db.commit()
            
            return {
                "success": True,
                "deleted_queues": deleted_queues,
                "deleted_entries": old_entries_count,
                "cutoff_date": cutoff_date.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка очистки старых данных: {e}")
            self.db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
