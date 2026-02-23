"""Repository helpers for file test API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class FileTestApiRepository:
    """Shared DB session adapter for file test service."""

    def __init__(self, db: Session):
        self.db = db
