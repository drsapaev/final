"""
Global Search API endpoint.
Aggregated search across patients, visits, and lab results.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.services.global_search_api_service import GlobalSearchApiService

router = APIRouter(tags=["search"])

GLOBAL_SEARCH_ROLES = (
    "Admin",
    "Registrar",
    "Doctor",
    "Cashier",
    "Lab",
    "Laboratory",
    "cardio",
    "cardiology",
    "Cardiologist",
    "derma",
    "Dermatologist",
    "dentist",
    "Dentist",
)


# ============== Response Schemas ==============

class PatientSearchResult(BaseModel):
    id: int
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    phone: str | None = None
    birth_date: date | None = None

    model_config = ConfigDict(from_attributes=True)


class VisitSearchResult(BaseModel):
    id: int
    patient_id: int
    patient_name: str | None = None
    status: str | None = None
    visit_date: date | None = None
    visit_time: str | None = None
    specialist_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class LabResultSearchResult(BaseModel):
    id: int
    patient_id: int | None = None
    patient_name: str | None = None
    status: str
    test_type: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class GlobalSearchResponse(BaseModel):
    patients: list[PatientSearchResult] = []
    visits: list[VisitSearchResult] = []
    labResults: list[LabResultSearchResult] = []
    query: str
    total: int = 0


# ============== API Endpoint ==============

@router.get("/global-search", response_model=GlobalSearchResponse)
async def global_search(
    q: str = Query(..., min_length=2, max_length=100, description="Search query"),
    limit: int = Query(default=5, ge=1, le=20, description="Max results per domain"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*GLOBAL_SEARCH_ROLES)),
):
    """
    Global search across patients, visits, and lab results.

    - **q**: Search query (min 2 characters)
    - **limit**: Max results per domain (default 5)

    Returns grouped results from all domains.
    """
    query = q.strip()
    search_service = GlobalSearchApiService(db)
    patients, visits, lab_results = search_service.search_all(
        query=query,
        limit=limit,
    )
    total = len(patients) + len(visits) + len(lab_results)
    search_service.log_search_query(
        user=current_user,
        query=query,
        patients=patients,
        visits=visits,
        lab_results=lab_results,
        total=total,
    )

    return GlobalSearchResponse(
        patients=patients,
        visits=visits,
        labResults=lab_results,
        query=query,
        total=total
    )


class LogClickRequest(BaseModel):
    opened_type: str  # "patient" | "visit" | "lab"
    opened_id: int
    query: str


@router.post("/global-search/log-click", response_model=dict[str, Any])
async def log_search_click(
    request: LogClickRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(*GLOBAL_SEARCH_ROLES)),
):
    """
    Log when user clicks on a search result.
    Required for audit compliance.
    """
    return GlobalSearchApiService(db).log_search_click(
        user=current_user,
        query=request.query,
        opened_type=request.opened_type,
        opened_id=request.opened_id,
    )
