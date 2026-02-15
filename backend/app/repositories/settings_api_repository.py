"""Repository helpers for settings API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class SettingsApiRepository:
    """Shared DB session adapter for settings service."""

    def __init__(self, db: Session):
        self.db = db
