"""Repository helpers for api documentation API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class ApiDocumentationApiRepository:
    """Shared DB session adapter for api documentation service."""

    def __init__(self, db: Session):
        self.db = db
