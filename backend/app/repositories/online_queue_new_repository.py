"""Repository helpers for online_queue_new endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.online_queue import OnlineQueueEntry


class OnlineQueueNewRepository:
    """Encapsulates OnlineQueueEntry ORM operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_entry(self, entry_id: int) -> OnlineQueueEntry | None:
        return self.db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()

    def update_entry_status(self, entry: OnlineQueueEntry, *, status: str) -> OnlineQueueEntry:
        entry.status = status
        self.db.commit()
        self.db.refresh(entry)
        return entry

