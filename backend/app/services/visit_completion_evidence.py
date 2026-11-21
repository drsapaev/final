"""Record consultation evidence only at an authorized completion boundary.

Callers must hold the Visit lock and must have applied the completion policy.
The database invalidates the generation when identity, clinical service
association, or a transition out of the completed lifecycle changes.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.service import Service
from app.models.visit import Visit, VisitService


class RepeatEvidenceBusy(HTTPException):
    """A whole completion transaction must be retried after catalog contention."""

    def __init__(self) -> None:
        super().__init__(status_code=409, detail="Услуги изменяются, повторите завершение визита")


def reserve_sqlite_completion_writer(db: Session, visit_id: int) -> None:
    """Reserve SQLite's writer before reading data used for completion."""
    if db.get_bind().dialect.name != "sqlite":
        return
    try:
        with db.no_autoflush:
            db.execute(text("UPDATE visits SET id=id WHERE id=:visit_id"), {"visit_id": visit_id})
    except DBAPIError as exc:
        sqlite_code = getattr(exc.orig, "sqlite_errorcode", None)
        if sqlite_code is not None and sqlite_code & 0xff in {5, 6}:
            db.rollback()
            raise RepeatEvidenceBusy() from None
        raise


def capture_completion_evidence(db: Session, visit: Visit) -> None:
    """Bind the completed consultation and doctor owner to this generation.

    Do not lock child rows while holding Visit: their trigger takes the
    Visit lock after the child lock. Lock the catalog in sorted order with
    NOWAIT instead, so its consultation classification remains stable until
    completion commits without creating an ABBA wait against other writers.
    """
    def service_ids() -> set[int]:
        return {
            row[0] for row in db.query(VisitService.service_id)
            .filter(VisitService.visit_id == visit.id, VisitService.qty > 0,
                    VisitService.service_id.is_not(None)).all()
        }

    try:
        # FOR UPDATE/SHARE is a no-op on SQLite. Lifecycle callers reserve
        # before the first visit read; direct CAS callers already own a writer.
        reserve_sqlite_completion_writer(db, visit.id)
        db.flush()
        db.refresh(visit, [
            "repeat_evidence_generation",
            "repeat_assigned_doctor_user_id",
            "repeat_assigned_owner_generation",
        ])
        ids = service_ids()
        services = (
            db.query(Service).filter(Service.id.in_(ids)).order_by(Service.id)
            .with_for_update(read=True, nowait=True).populate_existing().all()
        ) if ids else []
        if {service.id for service in services} != ids or service_ids() != ids:
            db.rollback()
            raise RepeatEvidenceBusy()
    except DBAPIError as exc:
        code = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
        sqlite_code = getattr(exc.orig, "sqlite_errorcode", None)
        if code == "55P03" or (sqlite_code is not None and sqlite_code & 0xff in {5, 6}):
            db.rollback()
            raise RepeatEvidenceBusy() from None
        raise

    owner = (
        db.query(Doctor.user_id, Doctor.repeat_owner_generation)
        .filter(Doctor.id == visit.doctor_id).first()
        if visit.doctor_id is not None else None
    )
    if (
        owner is None
        or owner[0] is None
        or visit.repeat_assigned_doctor_user_id != owner[0]
        or visit.repeat_assigned_owner_generation != owner[1]
    ):
        # Legacy or a profile rebind during care is not proof of who treated
        # the patient. An administrator can review and attest it explicitly.
        visit.repeat_proof_generation = None
        visit.repeat_proof_consultation = None
        visit.repeat_proof_doctor_user_id = None
        return
    visit.repeat_proof_generation = visit.repeat_evidence_generation
    visit.repeat_proof_consultation = any(service.is_consultation for service in services)
    visit.repeat_proof_doctor_user_id = owner[0]
