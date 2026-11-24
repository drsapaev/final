from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.crud import clinic as crud_clinic
from app.models.clinic import ClinicSettings, Doctor
from app.models.service import Service
from app.models.visit import Visit


@pytest.fixture
def clinic_date(monkeypatch):
    today = date(2026, 11, 20)
    monkeypatch.setattr(crud_clinic, "clinic_today", lambda _db: today)
    return today


def _upsert_setting(db_session, key: str, value):
    row = db_session.query(ClinicSettings).filter(ClinicSettings.key == key).first()
    if row:
        row.value = value
    else:
        row = ClinicSettings(key=key, value=value, category="clinic")
        db_session.add(row)
    db_session.commit()


def _create_consultation_service(db_session, *, code: str, name: str):
    service = Service(
        name=name,
        code=code,
        service_code=code,
        category_code="K",
        queue_tag="cardiology",
        department_key="cardiology",
        price=Decimal("120000.00"),
        active=True,
        requires_doctor=True,
        is_consultation=True,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _create_recent_visit(db_session, *, patient_id: int, doctor_id: int, visit_date: date):
    visit = Visit(
        patient_id=patient_id,
        doctor_id=doctor_id,
        visit_date=visit_date,
        status="completed",
        repeat_evidence_generation=1,
        repeat_proof_generation=1,
        repeat_proof_consultation=True,
        repeat_proof_doctor_user_id=db_session.get(Doctor, doctor_id).user_id,
        discount_mode="none",
        approval_status="none",
        source="desk",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)
    return visit


@pytest.mark.integration
@pytest.mark.parametrize(
    "case,expected",
    [("valid", True), ("outside_target_window", False), ("open", False),
     ("stale_proof", False), ("wrong_owner", False), ("future_completed", False)],
)
def test_preview_requires_completed_same_doctor_evidence_in_target_window(
    client, db_session, registrar_auth_headers, test_patient, test_doctor, clinic_date, case, expected
):
    _upsert_setting(db_session, "repeat_visit_days", 21)
    service = _create_consultation_service(db_session, code="K94", name="SYNTHETIC repeat preview")
    today = clinic_date
    historical_date = today + timedelta(days=1) if case == "future_completed" else today - timedelta(days=2)
    prior = _create_recent_visit(db_session, patient_id=test_patient.id,
                                 doctor_id=test_doctor.id, visit_date=historical_date)
    if case == "open":
        prior.status = "open"
    elif case == "stale_proof":
        prior.repeat_evidence_generation = 2
    elif case == "wrong_owner":
        prior.repeat_proof_doctor_user_id = test_doctor.user_id + 9999
    db_session.commit()
    target = today + timedelta(days=21) if case == "outside_target_window" else today + timedelta(days=2)
    response = client.post(
        "/api/v1/registrar/repeat-eligibility-preview", headers=registrar_auth_headers,
        json={"patient_id": test_patient.id, "candidates": [{"doctor_id": test_doctor.id,
              "service_id": service.id, "visit_date": target.isoformat()}]},
    )
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["eligible"] is expected


@pytest.mark.integration
def test_repeat_preview_returns_eligible_when_recent_same_doctor_visit_exists(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
    clinic_date,
):
    _upsert_setting(db_session, "repeat_visit_days", 21)
    _upsert_setting(db_session, "repeat_visit_discount", 20)
    service = _create_consultation_service(
        db_session, code="K91", name="Консультация кардиолога (preview eligible)"
    )
    _create_recent_visit(
        db_session,
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        visit_date=clinic_date - timedelta(days=3),
    )

    response = client.post(
        "/api/v1/registrar/repeat-eligibility-preview",
        headers=registrar_auth_headers,
        json={
            "patient_id": test_patient.id,
            "candidates": [
                {
                    "candidate_key": "item-1",
                    "doctor_id": test_doctor.id,
                    "service_id": service.id,
                    "visit_date": clinic_date.isoformat(),
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["patient_id"] == test_patient.id
    assert len(payload["items"]) == 1
    item = payload["items"][0]
    assert item["candidate_key"] == "item-1"
    assert item["eligible"] is True
    assert item["repeat_window_days"] == 21
    assert item["repeat_discount_percent"] == 20
    assert "Доступна повторная скидка" in item["reason"]


@pytest.mark.integration
def test_repeat_preview_returns_ineligible_reason_when_visit_outside_window(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
    clinic_date,
):
    _upsert_setting(db_session, "repeat_visit_days", 7)
    _upsert_setting(db_session, "repeat_visit_discount", 15)
    service = _create_consultation_service(
        db_session, code="K92", name="Консультация кардиолога (preview ineligible)"
    )
    _create_recent_visit(
        db_session,
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        visit_date=clinic_date - timedelta(days=12),
    )

    response = client.post(
        "/api/v1/registrar/repeat-eligibility-preview",
        headers=registrar_auth_headers,
        json={
            "patient_id": test_patient.id,
            "candidates": [
                {
                    "candidate_key": "item-2",
                    "doctor_id": test_doctor.id,
                    "service_id": service.id,
                    "visit_date": clinic_date.isoformat(),
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["eligible"] is False
    assert item["repeat_window_days"] == 7
    assert item["repeat_discount_percent"] == 15
    assert "последние 7 дней" in item["reason"]


@pytest.mark.integration
def test_repeat_preview_reflects_current_settings_values_in_response(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
    clinic_date,
):
    _upsert_setting(db_session, "repeat_visit_days", 30)
    _upsert_setting(db_session, "repeat_visit_discount", 35)
    service = _create_consultation_service(
        db_session, code="K93", name="Консультация кардиолога (preview settings)"
    )
    _create_recent_visit(
        db_session,
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        visit_date=clinic_date - timedelta(days=10),
    )

    response = client.post(
        "/api/v1/registrar/repeat-eligibility-preview",
        headers=registrar_auth_headers,
        json={
            "patient_id": test_patient.id,
            "candidates": [
                {
                    "candidate_key": "item-3",
                    "doctor_id": test_doctor.id,
                    "service_id": service.id,
                    "visit_date": clinic_date.isoformat(),
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["eligible"] is True
    assert item["repeat_window_days"] == 30
    assert item["repeat_discount_percent"] == 35
