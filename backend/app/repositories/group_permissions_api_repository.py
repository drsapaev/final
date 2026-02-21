"""Repository helpers for group permissions API."""

from __future__ import annotations

from sqlalchemy.orm import Session


class GroupPermissionsApiRepository:
    """Shared DB session adapter for group permissions service."""

    def __init__(self, db: Session):
        self.db = db


    def query(self, *entities):
        return self.db.query(*entities)

    def add(self, obj) -> None:
        self.db.add(obj)

    def delete(self, obj) -> None:
        self.db.delete(obj)

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)

    def rollback(self) -> None:
        self.db.rollback()

    def flush(self) -> None:
        self.db.flush()

    def execute(self, statement, params=None):
        if params is None:
            return self.db.execute(statement)
        return self.db.execute(statement, params)
