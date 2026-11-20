"""Transaction and protected-field behavior independent of HTTP."""

from datetime import date

from app.crud.patient import patient as patient_crud
from app.crud.patient import update_patient
from app.models.patient import Patient
from app.schemas.patient import PatientCreate


def test_patient_crud_can_flush_without_committing(db_session):
    patient = patient_crud.create(
        db_session,
        obj_in=PatientCreate(first_name="Synthetic", last_name="Uncommitted"),
        commit=False,
    )
    patient_id = patient.id
    assert patient_id is not None
    db_session.rollback()
    assert db_session.get(Patient, patient_id) is None


def test_mobile_cannot_set_internal_birth_metadata(db_session, test_patient):
    db_session.refresh(test_patient)
    before = (test_patient.birth_date, test_patient.birth_date_precision, test_patient.birth_date_generation)
    result = update_patient(
        db_session,
        patient_id=test_patient.id,
        update_data={"address": "Synthetic", "birth_date_precision": "reported_exact", "birth_date_generation": 1234},
    )
    assert result.address == "Synthetic"
    assert (result.birth_date, result.birth_date_precision, result.birth_date_generation) == before


def test_mobile_explicit_null_sets_unknown(db_session, test_patient):
    test_patient.birth_date = date(2000, 1, 1)
    test_patient.birth_date_precision = "reported_exact"
    db_session.commit()
    result = update_patient(db_session, patient_id=test_patient.id, update_data={"birth_date": None})
    assert result.birth_date is None
    assert result.birth_date_precision == "unknown"
