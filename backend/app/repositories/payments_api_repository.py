"""Repository helpers for payments API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class PaymentsApiRepository:
    """Shared DB session adapter for payments service."""

    def __init__(self, db: Session):
        self.db = db
