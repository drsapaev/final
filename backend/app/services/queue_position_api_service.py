"""Service layer for queue_position endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.repositories.queue_position_api_repository import QueuePositionApiRepository


@dataclass
class QueuePositionApiDomainError(Exception):
    status_code: int
    detail: str


class QueuePositionApiService:
    """Orchestrates queue position lookups and notification preconditions."""

    def __init__(
        self,
        db: Session,
        repository: QueuePositionApiRepository | None = None,
    ):
        self.repository = repository or QueuePositionApiRepository(db)

    def _get_entry_or_error(self, entry_id: int):
        entry = self.repository.get_entry(entry_id)
        if not entry:
            raise QueuePositionApiDomainError(404, "Запись в очереди не найдена")
        return entry

    def get_position_entry(self, *, entry_id: int):
        return self._get_entry_or_error(entry_id)

    def get_position_entry_by_number(
        self,
        *,
        queue_number: int,
        specialist_id: int,
    ):
        queue = self.repository.get_today_queue_by_specialist(
            specialist_id=specialist_id,
            day=date.today(),
        )
        if not queue:
            raise QueuePositionApiDomainError(404, "Очередь не найдена")
        entry = self.repository.get_queue_entry_by_number(
            queue_id=queue.id,
            queue_number=queue_number,
        )
        if not entry:
            raise QueuePositionApiDomainError(
                404,
                f"Номер {queue_number} не найден в очереди",
            )
        return entry

    def get_queue_or_error(self, *, queue_id: int):
        queue = self.repository.get_queue(queue_id)
        if not queue:
            raise QueuePositionApiDomainError(404, "Очередь не найдена")
        return queue

    def get_diagnostics_entry_or_error(self, *, entry_id: int):
        entry = self.repository.get_diagnostics_entry(entry_id)
        if not entry:
            raise QueuePositionApiDomainError(
                404,
                "Запись в статусе 'diagnostics' не найдена",
            )
        return entry

    def get_waiting_entry_or_error(self, *, entry_id: int):
        entry = self.repository.get_waiting_entry(entry_id)
        if not entry:
            raise QueuePositionApiDomainError(
                404,
                "Запись в статусе 'waiting' не найдена",
            )
        return entry

    def get_queue_entries_stats(self, *, queue_id: int) -> tuple[object, list]:
        queue = self.get_queue_or_error(queue_id=queue_id)
        entries = self.repository.list_position_entries(queue_id=queue_id)
        return queue, entries

