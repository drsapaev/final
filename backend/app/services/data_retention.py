"""
Политика хранения данных для сообщений

Реализует автоматическое удаление старых сообщений согласно требованиям
медицинского compliance и GDPR.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.message import Message

logger = logging.getLogger(__name__)


# Настройки retention по умолчанию (в днях)
DEFAULT_RETENTION_DAYS = 365 * 7  # 7 лет для медицинских записей
VOICE_MESSAGE_RETENTION_DAYS = 365 * 3  # 3 года для голосовых сообщений
DELETED_MESSAGE_RETENTION_DAYS = 90  # 90 дней для "удалённых" сообщений


class DataRetentionService:
    """Сервис для управления политикой хранения данных"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_retention_date(
        self, 
        retention_days: int = DEFAULT_RETENTION_DAYS
    ) -> datetime:
        """Получить дату, старше которой данные подлежат удалению"""
        return datetime.utcnow() - timedelta(days=retention_days)
    
    def cleanup_old_messages(
        self,
        retention_days: Optional[int] = None,
        dry_run: bool = True
    ) -> dict:
        """
        Удалить сообщения старше указанного периода.
        
        Args:
            retention_days: Количество дней хранения (по умолчанию 7 лет)
            dry_run: Если True, только посчитать без удаления
            
        Returns:
            Статистика удаления
        """
        retention_days = retention_days or DEFAULT_RETENTION_DAYS
        cutoff_date = self.get_retention_date(retention_days)
        
        # Находим старые сообщения
        old_messages = self.db.query(Message).filter(
            Message.created_at < cutoff_date
        )
        
        count = old_messages.count()
        
        stats = {
            "retention_days": retention_days,
            "cutoff_date": cutoff_date.isoformat(),
            "messages_to_delete": count,
            "dry_run": dry_run,
            "deleted": 0
        }
        
        if not dry_run and count > 0:
            # Удаляем порциями для избежания блокировок
            batch_size = 1000
            deleted = 0
            
            while True:
                batch = old_messages.limit(batch_size).all()
                if not batch:
                    break
                    
                for msg in batch:
                    # Логируем удаление для аудита
                    logger.info(
                        f"Retention cleanup: deleting message {msg.id} "
                        f"from {msg.created_at}"
                    )
                    self.db.delete(msg)
                    deleted += 1
                
                self.db.commit()
            
            stats["deleted"] = deleted
            logger.info(f"Retention cleanup completed: {deleted} messages deleted")
        
        return stats
    
    def cleanup_deleted_messages(
        self,
        retention_days: Optional[int] = None,
        dry_run: bool = True
    ) -> dict:
        """
        Физически удалить сообщения, помеченные как удалённые обоими сторонами.
        
        Args:
            retention_days: Дней после мягкого удаления до физического
            dry_run: Если True, только посчитать без удаления
            
        Returns:
            Статистика удаления
        """
        retention_days = retention_days or DELETED_MESSAGE_RETENTION_DAYS
        cutoff_date = self.get_retention_date(retention_days)
        
        # Находим сообщения удалённые обоими сторонами
        deleted_messages = self.db.query(Message).filter(
            and_(
                Message.is_deleted_by_sender == True,
                Message.is_deleted_by_recipient == True,
                Message.created_at < cutoff_date
            )
        )
        
        count = deleted_messages.count()
        
        stats = {
            "retention_days": retention_days,
            "cutoff_date": cutoff_date.isoformat(),
            "messages_to_delete": count,
            "dry_run": dry_run,
            "deleted": 0
        }
        
        if not dry_run and count > 0:
            deleted = deleted_messages.delete(synchronize_session=False)
            self.db.commit()
            stats["deleted"] = deleted
            logger.info(f"Deleted messages cleanup: {deleted} physically removed")
        
        return stats
    
    def cleanup_voice_messages(
        self,
        retention_days: Optional[int] = None,
        dry_run: bool = True
    ) -> dict:
        """
        Удалить старые голосовые сообщения (занимают много места).
        
        Args:
            retention_days: Количество дней хранения голосовых
            dry_run: Если True, только посчитать без удаления
            
        Returns:
            Статистика удаления
        """
        retention_days = retention_days or VOICE_MESSAGE_RETENTION_DAYS
        cutoff_date = self.get_retention_date(retention_days)
        
        # Находим старые голосовые сообщения
        voice_messages = self.db.query(Message).filter(
            and_(
                Message.message_type == "voice",
                Message.created_at < cutoff_date
            )
        )
        
        count = voice_messages.count()
        
        stats = {
            "retention_days": retention_days,
            "cutoff_date": cutoff_date.isoformat(),
            "voice_messages_to_delete": count,
            "dry_run": dry_run,
            "deleted": 0
        }
        
        if not dry_run and count > 0:
            # Также удаляем связанные файлы
            for msg in voice_messages.all():
                if msg.file_id:
                    # TODO: удалить физический файл
                    pass
                self.db.delete(msg)
            
            self.db.commit()
            stats["deleted"] = count
            logger.info(f"Voice messages cleanup: {count} deleted")
        
        return stats
    
    def get_retention_stats(self) -> dict:
        """Получить статистику по хранению данных"""
        total_messages = self.db.query(Message).count()
        
        # Сообщения по возрасту
        now = datetime.utcnow()
        year_ago = now - timedelta(days=365)
        three_years_ago = now - timedelta(days=365 * 3)
        seven_years_ago = now - timedelta(days=365 * 7)
        
        return {
            "total_messages": total_messages,
            "messages_last_year": self.db.query(Message).filter(
                Message.created_at >= year_ago
            ).count(),
            "messages_1_3_years": self.db.query(Message).filter(
                and_(
                    Message.created_at >= three_years_ago,
                    Message.created_at < year_ago
                )
            ).count(),
            "messages_3_7_years": self.db.query(Message).filter(
                and_(
                    Message.created_at >= seven_years_ago,
                    Message.created_at < three_years_ago
                )
            ).count(),
            "messages_over_7_years": self.db.query(Message).filter(
                Message.created_at < seven_years_ago
            ).count(),
            "voice_messages": self.db.query(Message).filter(
                Message.message_type == "voice"
            ).count(),
            "deleted_by_both": self.db.query(Message).filter(
                and_(
                    Message.is_deleted_by_sender == True,
                    Message.is_deleted_by_recipient == True
                )
            ).count(),
            "retention_policy": {
                "text_messages_days": DEFAULT_RETENTION_DAYS,
                "voice_messages_days": VOICE_MESSAGE_RETENTION_DAYS,
                "deleted_messages_days": DELETED_MESSAGE_RETENTION_DAYS
            }
        }


def run_scheduled_cleanup(db: Session) -> dict:
    """
    Запустить плановую очистку данных.
    Эту функцию можно вызывать из cron job или Celery task.
    """
    service = DataRetentionService(db)
    
    results = {
        "run_at": datetime.utcnow().isoformat(),
        "old_messages": service.cleanup_old_messages(dry_run=False),
        "deleted_messages": service.cleanup_deleted_messages(dry_run=False),
        "voice_messages": service.cleanup_voice_messages(dry_run=False)
    }
    
    logger.info(f"Scheduled cleanup completed: {results}")
    return results
