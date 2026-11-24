"""Persist reported birth-date precision in the caller's transaction.

Reported precision is provenance, never administrator attestation. The caller
must invoke this only for a date explicitly supplied to its trusted writer.
"""

from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.user import User


def lock_patient_audit_actor(db: Session, actor_id: int) -> None:
    """Protect the audit FK in User -> Patient order, without reauthorizing.

    PostgreSQL KEY SHARE conflicts with deletion of the actor, whose FK
    actions may otherwise wait for the Patient row held by this writer.
    Ordinary role/session updates are deliberately outside this lock's scope.
    """
    with db.no_autoflush:
        actor = (
            db.query(User.id)
            .filter(User.id == actor_id)
            .with_for_update(read=True, key_share=True)
            .first()
        )
    if actor is None:
        raise LookupError("patient audit actor unavailable")


def lock_patient_for_birth_update(db: Session, patient_id: int) -> Patient | None:
    """Serialize date updates before loading the value used by ORM change tracking."""
    if db.get_bind().dialect.name == "sqlite":
        # SQLite ignores FOR UPDATE. Reserve the writer before the read so a
        # previously loaded same-value attribute cannot mask a competing write.
        db.execute(
            text("UPDATE patients SET id=id WHERE id=:patient_id AND is_deleted=0"),
            {"patient_id": patient_id},
        )
    return (
        db.query(Patient)
        .filter(Patient.id == patient_id, Patient.is_deleted.is_(False))
        .with_for_update()
        .populate_existing()
        .first()
    )


def record_reported_birth_date(
    db: Session, patient: Patient, *, expected_date: date | None
) -> None:
    """Record a full reported date, or unknown for an explicitly cleared date.

    0110 uses an AFTER trigger on SQLite; flush and refresh before changing
    precision, then refresh again after its generation trigger. Never commit.
    """
    if expected_date is not None and type(expected_date) is not date:
        raise ValueError("reported birth date must be a date")
    db.flush()
    db.refresh(patient, attribute_names=["birth_date", "birth_date_precision", "birth_date_generation"])
    if patient.birth_date != expected_date:
        raise ValueError("reported birth date changed before provenance was recorded")
    precision = "reported_exact" if patient.birth_date is not None else "unknown"
    if patient.birth_date_precision != precision:
        patient.birth_date_precision = precision
        db.flush()
        db.refresh(patient, attribute_names=["birth_date", "birth_date_precision", "birth_date_generation"])
