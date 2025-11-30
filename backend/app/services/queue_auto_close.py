"""
Сервис автозакрытия очередей по времени
"""

import logging
from datetime import date, datetime, time
from typing import Any, Dict, List

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.online_queue import DailyQueue, OnlineQueueEntry

logger = logging.getLogger(__name__)


class QueueAutoCloseService:
    """Сервис для автоматического закрытия очередей по времени"""

    def __init__(self, db: Session):
        self.db = db

    def check_and_close_expired_queues(self) -> Dict[str, Any]:
        """
        Проверяет и закрывает очереди, у которых истекло время онлайн записи

        Returns:
            Статистика закрытых очередей
        """
        today = date.today()
        current_time = datetime.now().strftime("%H:%M")

        # Находим очереди, которые нужно закрыть
        queues_to_close = (
            self.db.query(DailyQueue)
            .filter(
                and_(
                    DailyQueue.day == today,
                    DailyQueue.active == True,
                    DailyQueue.opened_at.is_(None),  # Еще не открыты вручную
                    DailyQueue.online_end_time <= current_time,  # Время истекло
                )
            )
            .all()
        )

        closed_count = 0
        closed_queues = []

        for queue in queues_to_close:
            try:
                # Помечаем очередь как открытую (автозакрытие)
                queue.opened_at = datetime.now()

                # Логируем закрытие
                logger.info(
                    f"Auto-closed queue {queue.id} for specialist {queue.specialist_id} at {current_time}"
                )

                closed_queues.append(
                    {
                        "queue_id": queue.id,
                        "specialist_id": queue.specialist_id,
                        "end_time": queue.online_end_time,
                        "entries_count": self._count_queue_entries(queue.id),
                    }
                )

                closed_count += 1

            except Exception as e:
                logger.error(f"Error closing queue {queue.id}: {e}")

        if closed_count > 0:
            self.db.commit()
            logger.info(f"Auto-closed {closed_count} queues")

        return {
            "closed_count": closed_count,
            "closed_queues": closed_queues,
            "check_time": current_time,
            "date": today.isoformat(),
        }

    def get_queues_pending_close(self) -> List[Dict[str, Any]]:
        """
        Возвращает список очередей, которые скоро будут закрыты

        Returns:
            Список очередей с информацией о времени закрытия
        """
        today = date.today()
        current_time = datetime.now().strftime("%H:%M")

        pending_queues = (
            self.db.query(DailyQueue)
            .filter(
                and_(
                    DailyQueue.day == today,
                    DailyQueue.active == True,
                    DailyQueue.opened_at.is_(None),  # Еще не открыты
                    DailyQueue.online_end_time > current_time,  # Время еще не истекло
                )
            )
            .all()
        )

        result = []
        for queue in pending_queues:
            result.append(
                {
                    "queue_id": queue.id,
                    "specialist_id": queue.specialist_id,
                    "end_time": queue.online_end_time,
                    "current_time": current_time,
                    "entries_count": self._count_queue_entries(queue.id),
                    "minutes_remaining": self._calculate_minutes_remaining(
                        current_time, queue.online_end_time
                    ),
                }
            )

        return result

    def force_close_queue(self, queue_id: int, user_id: int) -> Dict[str, Any]:
        """
        Принудительно закрывает очередь

        Args:
            queue_id: ID очереди
            user_id: ID пользователя, который закрывает

        Returns:
            Результат операции
        """
        queue = self.db.query(DailyQueue).filter(DailyQueue.id == queue_id).first()

        if not queue:
            raise ValueError("Очередь не найдена")

        if queue.opened_at:
            raise ValueError("Очередь уже закрыта")

        # Закрываем очередь
        queue.opened_at = datetime.now()

        self.db.commit()

        logger.info(f"Queue {queue_id} force-closed by user {user_id}")

        return {
            "queue_id": queue_id,
            "specialist_id": queue.specialist_id,
            "closed_at": queue.opened_at.isoformat(),
            "closed_by": user_id,
            "entries_count": self._count_queue_entries(queue_id),
        }

    def _count_queue_entries(self, queue_id: int) -> int:
        """Подсчитывает количество записей в очереди"""
        return (
            self.db.query(OnlineQueueEntry)
            .filter(
                and_(
                    OnlineQueueEntry.queue_id == queue_id,
                    OnlineQueueEntry.status.in_(["waiting", "called"]),
                )
            )
            .count()
        )

    def _calculate_minutes_remaining(self, current_time: str, end_time: str) -> int:
        """Вычисляет оставшиеся минуты до закрытия"""
        try:
            current = datetime.strptime(current_time, "%H:%M").time()
            end = datetime.strptime(end_time, "%H:%M").time()

            current_minutes = current.hour * 60 + current.minute
            end_minutes = end.hour * 60 + end.minute

            return max(0, end_minutes - current_minutes)
        except:
            return 0


def run_auto_close_check():
    """
    Функция для запуска проверки автозакрытия
    Может быть вызвана из cron job или планировщика задач
    """
    db = next(get_db())
    try:
        service = QueueAutoCloseService(db)
        result = service.check_and_close_expired_queues()

        if result["closed_count"] > 0:
            print(
                f"✅ Auto-closed {result['closed_count']} queues at {result['check_time']}"
            )
        else:
            print(f"ℹ️ No queues to close at {result['check_time']}")

        return result
    finally:
        db.close()


if __name__ == "__main__":
    # Для тестирования
    run_auto_close_check()
