"""Create patient-scoped standalone encounter identities transactionally."""
from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models.encounter import Encounter
from app.models.patient import Patient


class EncounterCreationError(ValueError):
    """An encounter cannot be created for the supplied patient."""


_CREATED_ENCOUNTERS_KEY = "encounter_creation.current_root_transaction"


def create_standalone_encounter(db: Session, *, patient_id: int) -> Encounter:
    """Stage one new encounter without committing its owner's transaction."""
    if type(patient_id) is not int or patient_id <= 0:
        raise EncounterCreationError("Patient is required for a new encounter")
    if db.query(Patient.id).filter(Patient.id == patient_id).first() is None:
        raise EncounterCreationError("Patient is unavailable for a new encounter")
    encounter = Encounter(patient_id=patient_id, provenance="new")
    db.add(encounter)
    db.flush()
    transaction = db.get_transaction()
    marker = db.info.get(_CREATED_ENCOUNTERS_KEY)
    if marker is None or marker[0] is not transaction:
        marker = (transaction, {})
        db.info[_CREATED_ENCOUNTERS_KEY] = marker
    marker[1][encounter.id] = encounter
    return encounter


def resolve_new_encounter(
    db: Session, *, patient_id: int, encounter_id: int
) -> Encounter:
    """Use a same-patient encounter created in this root transaction only.

    This temporary server-owned capability supports composing a new cart
    atomically. Reusing an existing encounter after commit is denied until
    the group membership and benefit-version protocol has been established.
    """
    if type(patient_id) is not int or patient_id <= 0 or type(encounter_id) is not int or encounter_id <= 0:
        raise EncounterCreationError("Encounter is unavailable for this patient")
    transaction = db.get_transaction()
    marker = db.info.get(_CREATED_ENCOUNTERS_KEY)
    if transaction is None or marker is None or marker[0] is not transaction:
        raise EncounterCreationError("Encounter is unavailable for this patient")
    created = marker[1].get(encounter_id)
    if (
        created is None
        or created in db.deleted
        or inspect(created).session is not db
        or not inspect(created).persistent
    ):
        raise EncounterCreationError("Encounter is unavailable for this patient")
    # The shared session may disable autoflush. Preserve pending changes
    # before refreshing instead of silently discarding caller-owned state.
    db.flush()
    encounter = (
        db.query(Encounter)
        .filter(Encounter.id == encounter_id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if encounter is not created or encounter.patient_id != patient_id or encounter.provenance != "new":
        raise EncounterCreationError("Encounter is unavailable for this patient")
    return encounter
