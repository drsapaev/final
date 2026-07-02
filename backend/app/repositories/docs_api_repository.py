"""Repository helpers for docs API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class DocsApiRepository:
    """Shared DB session adapter for docs service."""

    def __init__(self, db: Session):
        self.db = db
