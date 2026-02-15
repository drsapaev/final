"""Repository helpers for cashier endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session


class CashierApiRepository:
    """Thin DB access wrapper for cashier service."""

    def __init__(self, db: Session):
        self.db = db

    def add(self, obj) -> None:
        self.db.add(obj)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)
