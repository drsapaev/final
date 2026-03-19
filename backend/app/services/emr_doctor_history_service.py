"""Service layer for EMR doctor-history endpoint."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories.emr_doctor_history_repository import EMRDoctorHistoryRepository
from app.services.emr_contract import (
    extract_diagnosis_main,
    get_emr_text_field,
    normalize_specialty,
)


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
        specialty: str,
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
            specialty=normalize_specialty(specialty),
            limit=max(limit * 5, limit),
        )

        entries: list[dict] = []
        normalized_search = (search_text or "").strip().lower()
        for record in records:
            content = get_emr_text_field(record.data, db_field)
            if not content:
                continue
            if normalized_search and len(normalized_search) >= 3:
                if normalized_search not in content.lower():
                    continue
            entries.append(
                {
                    "content": content[:500],
                    "diagnosis": (
                        extract_diagnosis_main(record.data)[:200]
                        if extract_diagnosis_main(record.data)
                        else None
                    ),
                    "created_at": record.created_at.isoformat() if record.created_at else "",
                }
            )
            if len(entries) >= limit:
                break
        return entries
