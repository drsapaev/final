"""Repository helpers for derma API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class DermaApiRepository:
    """Shared DB session adapter for derma service."""

    def __init__(self, db: Session):
        self.db = db
