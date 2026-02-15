"""Repository helpers for registrar wizard API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class RegistrarWizardApiRepository:
    """Shared DB session adapter for registrar wizard service."""

    def __init__(self, db: Session):
        self.db = db
