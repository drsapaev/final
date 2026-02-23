"""
Global Search API endpoint.
Aggregated search across patients, visits, and lab results.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.global_search_api_service import GlobalSearchApiService


router = APIRouter(tags=["search"])


# ============== Response Schemas ==============

class PatientSearchResult(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    middle_name: Optional[str] = None
    phone: Optional[str] = None
    birth_date: Optional[date] = None
    
    class Config:
        from_attributes = True


class VisitSearchResult(BaseModel):
    id: int
    patient_id: int
    patient_name: Optional[str] = None
    status: Optional[str] = None
    visit_date: Optional[date] = None
    visit_time: Optional[str] = None
    specialist_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class LabResultSearchResult(BaseModel):
    id: int
    patient_id: Optional[int] = None
    patient_name: Optional[str] = None
    status: str
    test_type: Optional[str] = None
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class GlobalSearchResponse(BaseModel):
    patients: List[PatientSearchResult] = []
    visits: List[VisitSearchResult] = []
    labResults: List[LabResultSearchResult] = []
    query: str
    total: int = 0


# ============== API Endpoint ==============

@router.get("/global-search", response_model=GlobalSearchResponse)
async def global_search(
    q: str = Query(..., min_length=2, max_length=100, description="Search query"),
    limit: int = Query(default=5, ge=1, le=20, description="Max results per domain"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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


@router.post("/global-search/log-click")
async def log_search_click(
    request: LogClickRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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
