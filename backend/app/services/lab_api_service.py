"""Service layer for lab API endpoints."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories.lab_api_repository import LabApiRepository


@dataclass
class LabApiDomainError(Exception):
    status_code: int
    detail: str


class LabApiService:
    """Orchestrates lab request listing and updates."""

    def __init__(
        self,
        db: Session,
        repository: LabApiRepository | None = None,
    ):
        self.repository = repository or LabApiRepository(db)

    def list_requests(
        self,
        *,
        status: str | None,
        patient_id: int | None,
        limit: int,
        offset: int,
    ):
        return self.repository.list_orders(
            status=status,
            patient_id=patient_id,
            limit=limit,
            offset=offset,
        )

    def update_result(
        self,
        *,
        req_id: int,
        notes: str | None,
        status: str | None,
    ):
        row = self.repository.get_order(req_id)
        if not row:
            raise LabApiDomainError(status_code=404, detail="Not found")
        return self.repository.update_order_fields(row=row, notes=notes, status=status)
