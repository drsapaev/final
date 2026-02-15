"""Repository helpers for visits endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.visit import Visit


class VisitsApiRepository:
    """Encapsulates ORM/SQL execution for visits API."""

    def __init__(self, db: Session):
        self.db = db

    def execute(self, statement, params=None):
        if params is None:
            return self.db.execute(statement)
        return self.db.execute(statement, params)

    def query_visit(self, visit_id: int):
        return self.db.query(Visit).filter(Visit.id == visit_id).first()

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)

    def get_bind(self):
        return self.db.get_bind()
