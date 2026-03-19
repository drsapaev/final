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
        specialty: str,
        limit: int,
    ) -> list[EMRRecord]:
        query = self.db.query(EMRRecord).filter(
            EMRRecord.created_by == doctor_id,
            EMRRecord.is_active == True,
            EMRRecord.status.in_(["in_progress", "signed", "amended"]),
            EMRRecord.data["specialty"].as_string() == specialty,
        )
        return query.order_by(desc(EMRRecord.updated_at), desc(EMRRecord.created_at)).limit(limit).all()
