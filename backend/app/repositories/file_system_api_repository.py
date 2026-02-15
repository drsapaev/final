"""Repository helpers for file system API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class FileSystemApiRepository:
    """Shared DB session adapter for file system service."""

    def __init__(self, db: Session):
        self.db = db
