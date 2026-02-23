"""Repository helpers for two factor devices API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class TwoFactorDevicesApiRepository:
    """Shared DB session adapter for two factor devices service."""

    def __init__(self, db: Session):
        self.db = db
