"""Repository helpers for activation API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class ActivationApiRepository:
    """Shared DB session adapter for activation service."""

    def __init__(self, db: Session):
        self.db = db
