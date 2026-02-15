"""Repository helpers for file upload simple API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class FileUploadSimpleApiRepository:
    """Shared DB session adapter for file upload simple service."""

    def __init__(self, db: Session):
        self.db = db
