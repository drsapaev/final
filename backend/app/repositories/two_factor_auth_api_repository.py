"""Repository helpers for two factor auth API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class TwoFactorAuthApiRepository:
    """Shared DB session adapter for two factor auth service."""

    def __init__(self, db: Session):
        self.db = db
