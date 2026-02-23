"""Repository helpers for lab API endpoints."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lab import LabOrder


class LabApiRepository:
    """Encapsulates LabOrder ORM operations for API services."""

    def __init__(self, db: Session):
        self.db = db

    def list_orders(
        self,
        *,
        status: str | None,
        patient_id: int | None,
        limit: int,
        offset: int,
    ) -> list[LabOrder]:
        stmt = select(LabOrder)
        if status:
            stmt = stmt.where(LabOrder.status == status)
        if patient_id:
            stmt = stmt.where(LabOrder.patient_id == patient_id)
        stmt = stmt.order_by(LabOrder.id.desc()).limit(limit).offset(offset)
        return self.db.execute(stmt).scalars().all()

    def get_order(self, req_id: int) -> LabOrder | None:
        return self.db.get(LabOrder, req_id)

    def update_order_fields(
        self,
        *,
        row: LabOrder,
        notes: str | None = None,
        status: str | None = None,
    ) -> LabOrder:
        if notes is not None:
            row.notes = notes
        if status is not None:
            row.status = status
        self.db.flush()
        return row
