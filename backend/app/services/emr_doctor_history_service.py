"""Service layer for EMR doctor-history endpoint."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories.emr_doctor_history_repository import EMRDoctorHistoryRepository


@dataclass
class EMRDoctorHistoryDomainError(Exception):
    status_code: int
    detail: str


class EMRDoctorHistoryService:
    """Builds doctor history payload for EMR AI context."""

    FIELD_MAP = {
        "complaints": "complaints",
        "anamnesis_morbi": "anamnesis_morbi",
        "anamnesis_vitae": "anamnesis_vitae",
        "examination": "examination",
        "diagnosis": "diagnosis",
        "treatment": "treatment",
        "recommendations": "recommendations",
    }

    def __init__(
        self,
        db: Session,
        repository: EMRDoctorHistoryRepository | None = None,
    ):
        self.repository = repository or EMRDoctorHistoryRepository(db)

    def get_history_entries(
        self,
        *,
        doctor_id: int,
        field_name: str,
        search_text: str | None,
        limit: int,
    ) -> list[dict]:
        db_field = self.FIELD_MAP.get(field_name)
        if not db_field:
            raise EMRDoctorHistoryDomainError(
                status_code=400,
                detail=f"Invalid field name: {field_name}",
            )

        records = self.repository.list_records(
            doctor_id=doctor_id,
            db_field=db_field,
            search_text=search_text,
            limit=limit,
        )

        entries: list[dict] = []
        for record in records:
            content = getattr(record, db_field, "")
            if not content:
                continue
            entries.append(
                {
                    "content": content[:500],
                    "diagnosis": record.diagnosis[:200] if record.diagnosis else None,
                    "created_at": record.created_at.isoformat() if record.created_at else "",
                }
            )
        return entries

