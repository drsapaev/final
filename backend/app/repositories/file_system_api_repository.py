"""Repository helpers for file_system endpoints."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session


class FileSystemApiRepository:
    """Encapsulates DB primitives used by file_system endpoint wrappers."""

    def __init__(self, db: Session):
        self.db = db

    def refresh(self, instance: Any) -> None:
        self.db.refresh(instance)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def count_files(
        self,
        *,
        file_model: Any,
        owner_id: int | None,
        file_type: str | None,
        patient_id: int | None,
        appointment_id: int | None,
        emr_id: int | None,
        folder_id: int | None,
    ) -> int:
        query = self.db.query(file_model)

        # owner_id=None означает "без фильтра по владельцу" (admin view)
        if owner_id is not None:
            query = query.filter(file_model.owner_id == owner_id)
        if file_type:
            query = query.filter(file_model.file_type == file_type)
        if patient_id:
            query = query.filter(file_model.patient_id == patient_id)
        if appointment_id:
            query = query.filter(file_model.appointment_id == appointment_id)
        if emr_id:
            query = query.filter(file_model.emr_id == emr_id)
        if folder_id:
            query = query.filter(file_model.folder_id == folder_id)

        return query.count()
