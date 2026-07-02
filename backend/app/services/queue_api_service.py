"""Service layer for legacy queue endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.repositories.queue_api_repository import QueueApiRepository


@dataclass
class QueueApiDomainError(Exception):
    status_code: int
    detail: str


class QueueApiService:
    """Handles endpoint-level DB actions for legacy queue module."""

    def __init__(
        self,
        db: Session,
        repository: QueueApiRepository | None = None,
    ):
        self.repository = repository or QueueApiRepository(db)

    def get_doctor_user(self, specialist_id: int):
        return self.repository.get_doctor_user(specialist_id)

    def get_daily_queue(self, *, day: date, specialist_id: int):
        return self.repository.get_daily_queue(day=day, specialist_id=specialist_id)

    def get_or_create_daily_queue(self, *, day: date, specialist_id: int):
        daily_queue = self.repository.get_daily_queue(day=day, specialist_id=specialist_id)
        if daily_queue:
            return daily_queue
        return self.repository.create_daily_queue(day=day, specialist_id=specialist_id)

    def open_daily_queue(self, daily_queue) -> None:
        self.repository.set_opened_at_now(daily_queue)

    def get_doctor(self, specialist_id: int):
        return self.repository.get_doctor(specialist_id)

    def list_queue_entries(self, *, queue_id: int):
        return self.repository.list_queue_entries(queue_id=queue_id)

    def get_queue_entry(self, entry_id: int):
        return self.repository.get_queue_entry(entry_id)

    def mark_entry_called(self, entry) -> None:
        self.repository.mark_entry_called(entry)
