"""Service layer for online_queue_new endpoints."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories.online_queue_new_repository import OnlineQueueNewRepository


@dataclass
class OnlineQueueNewDomainError(Exception):
    status_code: int
    detail: str


class OnlineQueueNewService:
    """Orchestrates online queue entry operations for API layer."""

    def __init__(
        self,
        db: Session,
        repository: OnlineQueueNewRepository | None = None,
    ):
        self.repository = repository or OnlineQueueNewRepository(db)

    def cancel_entry(self, *, entry_id: int):
        entry = self.repository.get_entry(entry_id)
        if not entry:
            raise OnlineQueueNewDomainError(
                status_code=404,
                detail="Запись очереди не найдена",
            )
        return self.repository.update_entry_status(entry, status="canceled")

