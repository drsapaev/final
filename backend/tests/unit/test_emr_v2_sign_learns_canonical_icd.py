"""
Fail-first regression suite: signing an EMR learns the treatment template
under the CANONICAL ICD-10 code (audit 3886, round 29 — EMRLEARN-FE-001).

Pre-fix source: `_learn_treatment_pattern` read only the legacy flat
``data["icd10_code"]`` key and returned early when it was absent — a signed
record with the canonical nested ``diagnosis.icd10_code`` (the shape the
backend's own ``extract_icd10_code`` materializes) was NEVER learned, and a
record carrying both a nested I10 and a stale flat I20 learned the text
under the WRONG code. The canonical extractors
(``extract_icd10_code`` / ``get_emr_text_field``) already exist in
``emr_contract.py`` and are the SSOT for both reads.

Red-first statement: on the pre-fix source the first two tests fail (no
template is learned for a nested-ICD sign; the wrong flat code wins) and
the legacy/control test passes both before and after the fix.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.doctor_templates import DoctorTreatmentTemplate
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit
from app.services.emr_v2_service import emr_v2_service

pytestmark = pytest.mark.unit


def _mk_visit(db, label: str) -> tuple[Visit, User]:
    user = User(
        username=f"emr_learn_{label}",
        email=f"emr-learn-{label}@test.com",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
    )
    db.add(user)
    db.flush()
    doctor = Doctor(user_id=user.id, specialty="therapy", active=True)
    db.add(doctor)
    patient = Patient(
        first_name="Learn",
        last_name=label,
        phone=f"+99890977{abs(hash(label)) % 10000:04d}",
        birth_date=date(1985, 5, 5),
    )
    db.add(patient)
    db.flush()
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=date.today(),
        visit_time="10:00",
        status="open",
        department="therapy",
    )
    db.add(visit)
    db.commit()
    return visit, user


def _templates(db, user_id: int):
    return (
        db.query(DoctorTreatmentTemplate)
        .filter(
            DoctorTreatmentTemplate.doctor_id == user_id,
            DoctorTreatmentTemplate.is_deleted.is_(False),
        )
        .all()
    )


def test_sign_with_nested_canonical_icd_learns_template(db_session):
    """EMRLEARN-FE-001: the canonical nested diagnosis.icd10_code drives
    the learned template (pre-fix: nothing was learned at all)."""
    visit, user = _mk_visit(db_session, "nested")

    emr = emr_v2_service.save(
        db_session,
        visit.id,
        {
            "complaints": "Головная боль",
            "specialty": "therapy",
            "diagnosis": {"main": "Гипертоническая болезнь", "icd10_code": "I10"},
            "medications": {"text": "Амлодипин 5 мг 1 раз в день"},
        },
        user.id,
    )
    emr_v2_service.sign(
        db_session,
        visit.id,
        {
            "complaints": "Головная боль",
            "specialty": "therapy",
            "diagnosis": {"main": "Гипертоническая болезнь", "icd10_code": "I10"},
            "medications": {"text": "Амлодипин 5 мг 1 раз в день"},
        },
        user.id,
        emr.row_version,
    )

    templates = _templates(db_session, user.id)
    assert len(templates) == 1, (
        "signing a canonical nested-ICD EMR must learn one treatment template"
    )
    assert templates[0].icd10_code == "I10"
    assert templates[0].treatment_text == "Амлодипин 5 мг 1 раз в день"


def test_nested_canonical_icd_wins_over_stale_flat_code(db_session):
    """EMRLEARN-FE-001: when a nested I10 and a legacy flat I20 coexist,
    the canonical SSOT rule applies — the template is learned under I10,
    never under the stale flat code (pre-fix: learned under I20)."""
    visit, user = _mk_visit(db_session, "conflict")

    payload = {
        "complaints": "Боль за грудиной",
        "specialty": "therapy",
        "diagnosis": {"main": "Гипертоническая болезнь", "icd10_code": "I10"},
        # legacy stale flat code that must NOT win
        "icd10_code": "I20",
        "medications": {"text": "Нитроглицерин по требованию"},
    }
    emr = emr_v2_service.save(db_session, visit.id, payload, user.id)
    emr_v2_service.sign(db_session, visit.id, payload, user.id, emr.row_version)

    templates = _templates(db_session, user.id)
    assert len(templates) == 1
    assert templates[0].icd10_code == "I10", (
        "the canonical nested ICD must win over the stale flat code"
    )


def test_legacy_flat_icd_still_learns_and_treatment_chain_falls_back(db_session):
    """Control (green before AND after): the legacy flat icd10_code keeps
    working, and the treatment text is read through the canonical chain
    (treatment first, then medications.text)."""
    visit, user = _mk_visit(db_session, "legacy")

    payload = {
        "complaints": "Кашель",
        "specialty": "therapy",
        "icd10_code": "J06.9",
        "treatment": "Питьевой режим, покой",
    }
    emr = emr_v2_service.save(db_session, visit.id, payload, user.id)
    emr_v2_service.sign(db_session, visit.id, payload, user.id, emr.row_version)

    templates = _templates(db_session, user.id)
    assert len(templates) == 1
    assert templates[0].icd10_code == "J06.9"
    assert templates[0].treatment_text == "Питьевой режим, покой"


def test_sign_without_any_icd_learns_nothing(db_session):
    """Control: no ICD code anywhere — signing proceeds, nothing is
    learned (both before and after the fix)."""
    visit, user = _mk_visit(db_session, "noicd")

    payload = {
        "complaints": "Осмотр",
        "specialty": "therapy",
        "medications": {"text": "Рекомендации даны"},
    }
    emr = emr_v2_service.save(db_session, visit.id, payload, user.id)
    emr_v2_service.sign(db_session, visit.id, payload, user.id, emr.row_version)

    assert _templates(db_session, user.id) == []
