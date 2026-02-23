"""Repository helpers for file upload json API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class FileUploadJsonApiRepository:
    """Shared DB session adapter for file upload json service."""

    def __init__(self, db: Session):
        self.db = db
