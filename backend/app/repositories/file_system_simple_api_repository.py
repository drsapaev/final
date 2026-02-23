"""Repository helpers for file system simple API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class FileSystemSimpleApiRepository:
    """Shared DB session adapter for file system simple service."""

    def __init__(self, db: Session):
        self.db = db
