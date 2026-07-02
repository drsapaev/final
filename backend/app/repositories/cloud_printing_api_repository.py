"""Repository helpers for cloud printing API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class CloudPrintingApiRepository:
    """Shared DB session adapter for cloud printing service."""

    def __init__(self, db: Session):
        self.db = db
