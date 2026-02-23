"""Repository helpers for EMR doctor-history endpoint."""

from __future__ import annotations

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.emr_v2 import EMRRecord


class EMRDoctorHistoryRepository:
    """Encapsulates EMRRecord lookups for doctor history context."""

    def __init__(self, db: Session):
        self.db = db

    def list_records(
        self,
        *,
        doctor_id: int,
        db_field: str,
        search_text: str | None,
        limit: int,
    ) -> list[EMRRecord]:
        query = self.db.query(EMRRecord).filter(
            EMRRecord.created_by == doctor_id,
            getattr(EMRRecord, db_field).isnot(None),
            getattr(EMRRecord, db_field) != "",
        )
        if search_text and len(search_text) >= 3:
            query = query.filter(getattr(EMRRecord, db_field).ilike(f"%{search_text[:50]}%"))
        return query.order_by(desc(EMRRecord.updated_at)).limit(limit).all()

