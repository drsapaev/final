"""Fail-first regression suite: EMR v2 sign-endpoint section-template learning
(RETRO-3971-01, post-merge review of the #3969-#3996 window, group 2 archive
PR #4000).

The sign endpoint's learning block read only FLAT legacy keys, although the
canonical EMR places the code at ``diagnosis.icd10_code`` and the treatment
text at ``plan.treatment`` (the service-level path already uses the canonical
extractors — ``emr_v2_service.py`` → ``app.services.emr_contract``):

- a nested-ICD sign payload yielded ``icd10_code=None`` — the template was
  persisted unkeyed and the retrieval strategy (specific-before-general)
  never matched it again; when a nested I10 and a stale flat I20 coexisted,
  learning happened under the WRONG code;
- ``payload.data.get('medications', {}).get('text')`` raised ``AttributeError``
  on the canonical LIST-shaped ``medications`` — the whole try block failed
  and ALL section learning for that sign was silently skipped;
- the ``plan.treatment`` fallback documented in the contract extractor was
  missing on this call site.

Red-first statement: on the pre-fix source every test below fails — the
nested-ICD template is learned unkeyed (``icd10_code`` NULL), the coexistence
case learns under the stale flat code, and the list-medications payload skips
learning entirely; the flat-only control keeps passing before and after.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.section_templates import DoctorSectionTemplate
from app.models.user import User
from app.models.visit import Visit

pytestmark = pytest.mark.unit


def _mk_visit(db, label: str) -> tuple[Visit, User]:
    user = User(
        username=f"emr_learn_{label}",
        email=f"emr-learn-{label}@test.com",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
    )
    doctor = Doctor(user_id=user.id, specialty="therapy", active=True)
    patient = Patient(
        first_name="Learning",
        last_name=label,
        phone=f"+99890967{abs(hash(label)) % 10000:04d}",
        birth_date=date(1990, 1, 1),
    )
    db.add_all([user, patient])
    db.flush()
    doctor.user_id = user.id
    db.add(doctor)
    db.flush()
    visit = Visit(
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_date=date.today(),
        visit_time="09:00",
        status="open",
        department="therapy",
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit, user


def _login(client, username: str) -> dict[str, str]:
    resp = client.post(
        "/api/v1/authentication/login",
        json={"username": username, "password": "doctor123"},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _save_then_sign(client, headers, visit_id, data):
    """Create the EMR draft, then sign it with the learning payload."""
    save_resp = client.post(
        f"/api/v1/v2/emr/{visit_id}",
        headers=headers,
        json={
            "data": {"complaints": "draft", "specialty": "therapy"},
            "row_version": 0,
            "client_session_id": "sess-retro3971",
            "is_draft": True,
        },
    )
    assert save_resp.status_code == 200, save_resp.text
    row_version = save_resp.json()["row_version"]
    sign_resp = client.post(
        f"/api/v1/v2/emr/{visit_id}/sign",
        headers=headers,
        json={
            "data": data,
            "row_version": row_version,
            "client_session_id": "sess-retro3971",
        },
    )
    assert sign_resp.status_code == 200, sign_resp.text
    return sign_resp


def _learned_templates(db, user_id: int) -> list[DoctorSectionTemplate]:
    stmt = select(DoctorSectionTemplate).where(
        DoctorSectionTemplate.doctor_id == user_id
    )
    return list(db.scalars(stmt))


@pytest.fixture(autouse=True)
def _clean_user_templates(db_session):
    """Isolate each case on its own synthetic doctor (fresh user id) — no
    cross-case template bleed; nothing to clean, guard kept for clarity."""
    yield


def test_nested_diagnosis_icd10_keys_the_learned_template(client, db_session):
    """RETRO-3971-01: a canonical ``diagnosis.icd10_code`` sign payload must
    key the learned section template with 'I10', not persist it unkeyed."""
    visit, user = _mk_visit(db_session, "nested_icd")
    headers = _login(client, user.username)

    _save_then_sign(
        client,
        headers,
        visit.id,
        {
            "complaints": "Боли за грудиной",
            "anamnesis_morbi": "Anamnesis text for the nested ICD case",
            "examination": "Objective status text",
            "diagnosis": {"main": "Гипертоническая болезнь", "icd10_code": "I10"},
            "medications": {"text": "Таблетки от давления"},
            "recommendations": "Режим и наблюдение",
        },
    )

    templates = _learned_templates(db_session, user.id)
    anamnesis = [t for t in templates if t.section_type == "anamnesis"]
    assert anamnesis, "the anamnesis template must be learned at all"
    assert all(t.icd10_code == "I10" for t in anamnesis), (
        f"nested diagnosis.icd10_code must key the template; got "
        f"{[t.icd10_code for t in anamnesis]}"
    )


def test_nested_icd_wins_over_a_stale_flat_code(client, db_session):
    """RETRO-3971-01: when a nested I10 and a stale flat I20 coexist, the
    canonical nested field is the SSOT — learning must happen under I10."""
    visit, user = _mk_visit(db_session, "nested_vs_flat")
    headers = _login(client, user.username)

    _save_then_sign(
        client,
        headers,
        visit.id,
        {
            "complaints": "Жалобы",
            "anamnesis_morbi": "Anamnesis text for the coexistence case",
            "diagnosis": {"main": "Диагноз", "icd10_code": "I10"},
            # stale flat legacy key — must NOT win over the canonical nested one
            "icd_10_code": "I20",
            "medications": {"text": "Лечение"},
        },
    )

    templates = _learned_templates(db_session, user.id)
    anamnesis = [t for t in templates if t.section_type == "anamnesis"]
    assert anamnesis, "the anamnesis template must be learned"
    assert all(
        t.icd10_code == "I10" for t in anamnesis
    ), f"nested-first SSOT expected; got {[t.icd10_code for t in anamnesis]}"


def test_list_shaped_medications_do_not_skip_learning(client, db_session):
    """RETRO-3971-01: a canonical LIST-shaped ``medications`` must not raise
    inside the learning block — ALL sections still learn, and the treatment
    text falls back to ``plan.treatment``."""
    visit, user = _mk_visit(db_session, "list_meds")
    headers = _login(client, user.username)

    _save_then_sign(
        client,
        headers,
        visit.id,
        {
            "complaints": "Жалобы",
            "anamnesis_morbi": "Anamnesis text for the list-medications case",
            "examination": "Status objectivus",
            "diagnosis": {"main": "Диагноз", "icd10_code": "I20"},
            "medications": [{"name": "Aspirin", "dosage": "100 mg"}],
            "plan": {"treatment": "Терапия по плану лечения"},
            "recommendations": "Наблюдение",
        },
    )

    templates = _learned_templates(db_session, user.id)
    sections = {t.section_type for t in templates}
    # pre-fix: the AttributeError skipped ALL learning — zero rows
    assert (
        "anamnesis" in sections
    ), f"list-shaped medications must not skip anamnesis learning; got {sorted(sections)}"
    treatment_rows = [t for t in templates if t.section_type == "treatment"]
    assert treatment_rows, "plan.treatment fallback must be learned as treatment text"
    assert any(
        "Терапия по плану" in t.template_text for t in treatment_rows
    ), f"plan.treatment text expected; got {[t.template_text for t in treatment_rows]}"
    # the keyed code flows to every learned section
    assert all(t.icd10_code == "I20" for t in treatment_rows)


def test_flat_only_legacy_payload_still_learns(client, db_session):
    """Control: the legacy flat-only shape keeps learning exactly as before
    (no widening, no regression) — passes on pre-fix and post-fix source."""
    visit, user = _mk_visit(db_session, "flat_only")
    headers = _login(client, user.username)

    _save_then_sign(
        client,
        headers,
        visit.id,
        {
            "complaints": "Жалобы",
            "anamnesis_morbi": "Anamnesis text for the flat-only control",
            "icd_10_code": "I30",
            "medications": {"text": "Лечение по старой форме"},
        },
    )

    templates = _learned_templates(db_session, user.id)
    anamnesis = [t for t in templates if t.section_type == "anamnesis"]
    assert anamnesis, "the flat legacy shape must keep learning"
    assert all(t.icd10_code == "I30" for t in anamnesis)
    treatment = [t for t in templates if t.section_type == "treatment"]
    assert treatment and any(
        "Лечение по старой форме" in t.template_text for t in treatment
    )
