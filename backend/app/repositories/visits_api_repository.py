"""Repository helpers for visits endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.audit import log_critical_change
from app.crud.visit import create_visit as crud_create_visit
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

    def create_visit_via_crud(
        self,
        *,
        patient_id: int | None,
        doctor_id: int | None,
        visit_date,
        notes: str | None,
        source: str | None = None,
    ):
        return crud_create_visit(
            db=self.db,
            patient_id=patient_id,
            doctor_id=doctor_id,
            visit_date=visit_date,
            notes=notes,
            source=source or "desk",
            status="open",
            auto_status=False,
            notify=False,
            log=True,
        )

    def log_critical_change(
        self,
        *,
        user_id: int,
        action: str,
        table_name: str,
        row_id: int,
        old_data,
        new_data,
        request,
        description: str,
    ) -> None:
        log_critical_change(
            db=self.db,
            user_id=user_id,
            action=action,
            table_name=table_name,
            row_id=row_id,
            old_data=old_data,
            new_data=new_data,
            request=request,
            description=description,
        )
