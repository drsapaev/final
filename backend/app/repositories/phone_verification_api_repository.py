"""Repository helpers for phone verification API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class PhoneVerificationApiRepository:
    """Shared DB session adapter for phone verification service."""

    def __init__(self, db: Session):
        self.db = db
