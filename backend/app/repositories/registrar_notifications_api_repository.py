"""Repository helpers for registrar notifications API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class RegistrarNotificationsApiRepository:
    """Shared DB session adapter for registrar notifications service."""

    def __init__(self, db: Session):
        self.db = db
