"""
Global Search API endpoint.
Aggregated search across patients, visits, and lab results.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_, func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, get_db
from app.models.patient import Patient
from app.models.visit import Visit
from app.models.lab import LabOrder
from app.models.user import User
from app.models.global_search_audit import GlobalSearchAudit


router = APIRouter(tags=["search"])


def log_search_query(
    db: Session, 
    user: User, 
    query: str, 
    result_types: List[str],
    result_count: int
):
    """Log search query to audit table."""
    try:
        role = getattr(user, 'role', None) or getattr(user, 'role_name', 'unknown')
        audit = GlobalSearchAudit(
            user_id=user.id,
            role=str(role),
            query=query[:255],  # Truncate to max length
            result_types=result_types,
            result_count=result_count,
            opened_type=None,
            opened_id=None,
            created_at=datetime.utcnow()
        )
        db.add(audit)
        db.commit()
    except Exception as e:
        # Don't fail search if logging fails
        db.rollback()
        print(f"Audit logging error: {e}")


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


# ============== Search Logic ==============

def search_patients(db: Session, query: str, limit: int = 5) -> List[PatientSearchResult]:
    """Search patients by FIO, phone, or ID."""
    results = []
    
    # Try exact ID match first
    if query.isdigit():
        patient = db.query(Patient).filter(Patient.id == int(query)).first()
        if patient:
            results.append(PatientSearchResult(
                id=patient.id,
                first_name=patient.first_name,
                last_name=patient.last_name,
                middle_name=getattr(patient, 'middle_name', None),
                phone=getattr(patient, 'phone', None),
                birth_date=getattr(patient, 'birth_date', None)
            ))
    
    # Search by name/phone
    search_term = f"%{query}%"
    stmt = db.query(Patient).filter(
        or_(
            Patient.first_name.ilike(search_term),
            Patient.last_name.ilike(search_term),
            Patient.phone.ilike(search_term) if hasattr(Patient, 'phone') else False
        )
    ).limit(limit)
    
    for p in stmt.all():
        if not any(r.id == p.id for r in results):  # Avoid duplicates
            results.append(PatientSearchResult(
                id=p.id,
                first_name=p.first_name,
                last_name=p.last_name,
                middle_name=getattr(p, 'middle_name', None),
                phone=getattr(p, 'phone', None),
                birth_date=getattr(p, 'birth_date', None)
            ))
    
    return results[:limit]


def search_visits(db: Session, query: str, limit: int = 5) -> List[VisitSearchResult]:
    """Search visits by patient name, visit ID, or today's date."""
    results = []
    today = date.today()
    
    # Try exact visit ID match
    if query.isdigit():
        visit = db.query(Visit).filter(Visit.id == int(query)).first()
        if visit:
            patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
            patient_name = None
            if patient:
                patient_name = f"{patient.last_name or ''} {patient.first_name or ''}".strip()
            
            results.append(VisitSearchResult(
                id=visit.id,
                patient_id=visit.patient_id,
                patient_name=patient_name,
                status=visit.status,
                visit_date=getattr(visit, 'visit_date', None),
                visit_time=str(getattr(visit, 'visit_time', '')) if hasattr(visit, 'visit_time') else None,
                specialist_name=getattr(visit, 'specialist_name', None)
            ))
    
    # Search by patient name in recent visits
    search_term = f"%{query}%"
    stmt = (
        db.query(Visit)
        .join(Patient, Visit.patient_id == Patient.id)
        .filter(
            or_(
                Patient.first_name.ilike(search_term),
                Patient.last_name.ilike(search_term)
            ),
            Visit.created_at >= today - timedelta(days=7)  # Last 7 days
        )
        .order_by(Visit.created_at.desc())
        .limit(limit)
    )
    
    for v in stmt.all():
        if not any(r.id == v.id for r in results):
            patient = db.query(Patient).filter(Patient.id == v.patient_id).first()
            patient_name = None
            if patient:
                patient_name = f"{patient.last_name or ''} {patient.first_name or ''}".strip()
            
            results.append(VisitSearchResult(
                id=v.id,
                patient_id=v.patient_id,
                patient_name=patient_name,
                status=v.status,
                visit_date=getattr(v, 'visit_date', None),
                visit_time=str(getattr(v, 'visit_time', '')) if hasattr(v, 'visit_time') else None,
                specialist_name=getattr(v, 'specialist_name', None)
            ))
    
    return results[:limit]


def search_lab_results(db: Session, query: str, limit: int = 5) -> List[LabResultSearchResult]:
    """Search lab orders by patient name or order ID."""
    results = []
    
    # Try exact order ID match
    if query.isdigit():
        order = db.query(LabOrder).filter(LabOrder.id == int(query)).first()
        if order:
            patient = None
            if order.patient_id:
                patient = db.query(Patient).filter(Patient.id == order.patient_id).first()
            patient_name = None
            if patient:
                patient_name = f"{patient.last_name or ''} {patient.first_name or ''}".strip()
            
            results.append(LabResultSearchResult(
                id=order.id,
                patient_id=order.patient_id,
                patient_name=patient_name,
                status=order.status,
                test_type=getattr(order, 'notes', None),
                created_at=order.created_at
            ))
    
    # Search by patient name
    search_term = f"%{query}%"
    stmt = (
        db.query(LabOrder)
        .join(Patient, LabOrder.patient_id == Patient.id)
        .filter(
            or_(
                Patient.first_name.ilike(search_term),
                Patient.last_name.ilike(search_term)
            )
        )
        .order_by(LabOrder.created_at.desc())
        .limit(limit)
    )
    
    for o in stmt.all():
        if not any(r.id == o.id for r in results):
            patient = db.query(Patient).filter(Patient.id == o.patient_id).first()
            patient_name = None
            if patient:
                patient_name = f"{patient.last_name or ''} {patient.first_name or ''}".strip()
            
            results.append(LabResultSearchResult(
                id=o.id,
                patient_id=o.patient_id,
                patient_name=patient_name,
                status=o.status,
                test_type=getattr(o, 'notes', None),
                created_at=o.created_at
            ))
    
    return results[:limit]


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
    
    # Search all domains
    patients = search_patients(db, query, limit)
    visits = search_visits(db, query, limit)
    lab_results = search_lab_results(db, query, limit)
    
    total = len(patients) + len(visits) + len(lab_results)
    
    # Audit logging - log the search query
    result_types = []
    if patients:
        result_types.append("patient")
    if visits:
        result_types.append("visit")
    if lab_results:
        result_types.append("lab")
    
    log_search_query(db, current_user, query, result_types, total)
    
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
    try:
        role = getattr(current_user, 'role', None) or getattr(current_user, 'role_name', 'unknown')
        audit = GlobalSearchAudit(
            user_id=current_user.id,
            role=str(role),
            query=request.query[:255],
            result_types=None,
            result_count=None,
            opened_type=request.opened_type,
            opened_id=request.opened_id,
            created_at=datetime.utcnow()
        )
        db.add(audit)
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
