"""Shared policy for completing visits that require a saved EMR."""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.visit import Visit

EMR_REQUIRED_SPECIALTY_KEYS = frozenset(
    {
        "cardio",
        "cardiology",
        "cardiologist",
        "derma",
        "dermatology",
        "dermatologist",
    }
)
EMR_REQUIRED_DETAIL = "Для завершения приёма сохраните ЭМК со статусом не «черновик»"


def requires_saved_emr(specialty: str | None) -> bool:
    return (specialty or "").strip().lower() in EMR_REQUIRED_SPECIALTY_KEYS


def saved_emr_pairs(
    db: Session,
    candidates: Iterable[tuple[int | None, int | None]],
) -> set[tuple[int, int]]:
    """Return active, non-draft EMRs keyed by their exact visit/patient pair."""
    candidate_pairs = {
        (visit_id, patient_id)
        for visit_id, patient_id in candidates
        if visit_id is not None and patient_id is not None
    }
    if not candidate_pairs:
        return set()

    from app.models.emr_v2 import EMRRecord

    visit_ids = {visit_id for visit_id, _ in candidate_pairs}
    rows = (
        db.query(EMRRecord.visit_id, EMRRecord.patient_id)
        .filter(
            EMRRecord.visit_id.in_(visit_ids),
            EMRRecord.is_active.is_(True),
            EMRRecord.status != "draft",
        )
        .all()
    )
    ready_pairs = {(row.visit_id, row.patient_id) for row in rows}
    return ready_pairs.intersection(candidate_pairs)


def require_saved_emr_for_visit(
    db: Session,
    visit: Visit,
    *,
    specialty_override: str | None = None,
) -> None:
    """Reject completion when the visit's specialty requires a persisted EMR."""
    doctor = getattr(visit, "doctor", None)
    specialty = (
        specialty_override
        or getattr(doctor, "specialty", None)
        or getattr(visit, "department", None)
    )
    if not requires_saved_emr(specialty):
        return

    pair = (getattr(visit, "id", None), getattr(visit, "patient_id", None))
    if pair[0] is None or pair[1] is None or pair not in saved_emr_pairs(db, {pair}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=EMR_REQUIRED_DETAIL,
        )
