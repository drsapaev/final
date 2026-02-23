"""Service layer for file_system endpoints."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.audit import extract_model_changes, log_critical_change
from app.repositories.file_system_api_repository import FileSystemApiRepository


class FileSystemApiService:
    """Handles endpoint-level audit/commit wrappers for file operations."""

    def __init__(
        self,
        db: Session,
        repository: FileSystemApiRepository | None = None,
    ):
        self.repository = repository or FileSystemApiRepository(db)

    def finalize_file_create_audit(self, *, request, user_id: int, uploaded_file: Any) -> None:
        self.repository.refresh(uploaded_file)
        _, new_data = extract_model_changes(None, uploaded_file)
        log_critical_change(
            db=self.repository.db,
            user_id=user_id,
            action="CREATE",
            table_name="files",
            row_id=uploaded_file.id,
            old_data=None,
            new_data=new_data,
            request=request,
            description=(
                f"Загружен файл: {uploaded_file.filename} "
                f"(ID={uploaded_file.id})"
            ),
        )
        self.repository.commit()

    def finalize_file_update_audit(
        self,
        *,
        request,
        user_id: int,
        file_id: int,
        old_data: dict | None,
        updated_file: Any,
        description: str,
    ) -> None:
        self.repository.refresh(updated_file)
        _, new_data = extract_model_changes(None, updated_file)
        log_critical_change(
            db=self.repository.db,
            user_id=user_id,
            action="UPDATE",
            table_name="files",
            row_id=file_id,
            old_data=old_data,
            new_data=new_data,
            request=request,
            description=description,
        )
        self.repository.commit()

    def finalize_file_delete_audit(
        self,
        *,
        request,
        user_id: int,
        file_id: int,
        old_data: dict | None,
        filename: str,
    ) -> None:
        log_critical_change(
            db=self.repository.db,
            user_id=user_id,
            action="DELETE",
            table_name="files",
            row_id=file_id,
            old_data=old_data,
            new_data=None,
            request=request,
            description=f"Удален файл ID={file_id}: {filename}",
        )
        self.repository.commit()

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
        return self.repository.count_files(
            file_model=file_model,
            owner_id=owner_id,
            file_type=file_type,
            patient_id=patient_id,
            appointment_id=appointment_id,
            emr_id=emr_id,
            folder_id=folder_id,
        )

    def rollback(self) -> None:
        self.repository.rollback()
