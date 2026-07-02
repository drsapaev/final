"""Repository helpers for print templates API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class PrintTemplatesApiRepository:
    """Shared DB session adapter for print templates service."""

    def __init__(self, db: Session):
        self.db = db
