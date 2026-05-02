"""Service layer for queue_reorder endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.repositories.queue_reorder_api_repository import QueueReorderApiRepository


@dataclass
class QueueReorderApiDomainError(Exception):
    status_code: int
    detail: str


class QueueReorderApiService:
    """Handles queue reorder business logic and persistence."""

    def __init__(
        self,
        db: Session,
        repository: QueueReorderApiRepository | None = None,
    ):
        self.repository = repository or QueueReorderApiRepository(db)

    @staticmethod
    def _queue_info(queue, entries: list) -> dict:
        return {
            "queue_id": queue.id,
            "day": queue.day.isoformat(),
            "specialist_name": (
                queue.specialist.user.full_name
                if (queue.specialist and queue.specialist.user)
                else "Неизвестно"
            ),
            "specialist_id": queue.specialist_id,
            "is_active": queue.active,
            "opened_at": queue.opened_at.isoformat() if queue.opened_at else None,
            "total_entries": len(entries),
            "entries": [
                {
                    "id": entry.id,
                    "number": entry.number,
                    "patient_name": entry.patient_name,
                    "phone": entry.phone,
                    "status": entry.status,
                    "source": entry.source,
                    "created_at": entry.created_at.isoformat(),
                    "called_at": (
                        entry.called_at.isoformat() if entry.called_at else None
                    ),
                }
                for entry in entries
            ],
        }

    def reorder_queue(
        self,
        *,
        queue_id: int,
        entry_orders: list[dict[str, int]],
        current_user,
    ) -> tuple[int, dict]:
        queue = self.repository.get_queue(queue_id)
        if not queue:
            raise QueueReorderApiDomainError(404, "Очередь не найдена")

        if current_user.role == "Doctor" and queue.specialist_id != current_user.id:
            raise QueueReorderApiDomainError(403, "Нет прав для изменения этой очереди")

        entries = self.repository.list_active_entries(queue_id=queue_id)
        if not entries:
            raise QueueReorderApiDomainError(404, "В очереди нет активных записей")

        entry_map = {entry.id: entry for entry in entries}
        request_entry_ids = {item["entry_id"] for item in entry_orders}
        existing_entry_ids = set(entry_map.keys())
        if not request_entry_ids.issubset(existing_entry_ids):
            missing_ids = request_entry_ids - existing_entry_ids
            raise QueueReorderApiDomainError(
                400,
                f"Записи с ID {missing_ids} не найдены в очереди",
            )

        max_position = len(entries)
        for item in entry_orders:
            if item["new_position"] > max_position:
                raise QueueReorderApiDomainError(
                    400,
                    (
                        f"Позиция {item['new_position']} превышает размер очереди "
                        f"({max_position})"
                    ),
                )

        updated_count = 0
        for item in entry_orders:
            entry = entry_map[item["entry_id"]]
            new_position = item["new_position"]
            if entry.number != new_position:
                entry.number = new_position
                updated_count += 1

        self.repository.commit()
        updated_entries = self.repository.list_active_entries(queue_id=queue_id)
        queue_info = self._queue_info(queue, updated_entries)
        return updated_count, queue_info

    def move_queue_entry(
        self,
        *,
        entry_id: int,
        new_position: int,
        current_user,
    ) -> tuple[str, int, dict]:
        entry = self.repository.get_active_entry(entry_id)
        if not entry:
            raise QueueReorderApiDomainError(404, "Запись в очереди не найдена")

        queue = self.repository.get_queue(entry.queue_id)
        if not queue:
            raise QueueReorderApiDomainError(404, "Очередь не найдена")

        if current_user.role == "Doctor" and queue.specialist_id != current_user.id:
            raise QueueReorderApiDomainError(403, "Нет прав для изменения этой очереди")

        all_entries = self.repository.list_active_entries(queue_id=entry.queue_id)
        if new_position > len(all_entries):
            raise QueueReorderApiDomainError(
                400,
                f"Позиция {new_position} превышает размер очереди ({len(all_entries)})",
            )

        old_position = entry.number
        if old_position == new_position:
            return (
                "Позиция не изменилась",
                0,
                self._queue_info(queue, all_entries),
            )

        updated_count = 0
        if old_position < new_position:
            for other_entry in all_entries:
                if other_entry.id == entry.id:
                    continue
                if old_position < other_entry.number <= new_position:
                    other_entry.number -= 1
                    updated_count += 1
        else:
            for other_entry in all_entries:
                if other_entry.id == entry.id:
                    continue
                if new_position <= other_entry.number < old_position:
                    other_entry.number += 1
                    updated_count += 1

        entry.number = new_position
        updated_count += 1
        self.repository.commit()

        updated_entries = self.repository.list_active_entries(queue_id=entry.queue_id)
        queue_info = self._queue_info(queue, updated_entries)
        return (
            f"Запись перемещена с позиции {old_position} на позицию {new_position}",
            updated_count,
            queue_info,
        )

    def get_queue_status_by_specialist(self, *, specialist_id: int, day: date) -> dict:
        queue = self.repository.get_queue_by_specialist_day(
            specialist_id=specialist_id,
            day=day,
        )
        if not queue:
            raise QueueReorderApiDomainError(404, "Очередь не найдена")

        entries = self.repository.list_active_entries(queue_id=queue.id)
        return self._queue_info(queue, entries)

    def get_queue_status(self, *, queue_id: int) -> dict:
        queue = self.repository.get_queue(queue_id)
        if not queue:
            raise QueueReorderApiDomainError(404, "Очередь не найдена")

        entries = self.repository.list_active_entries(queue_id=queue_id)
        return self._queue_info(queue, entries)

    def rollback(self) -> None:
        self.repository.rollback()
