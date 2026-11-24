"""Characterization tests for the core mobile_api.py endpoints (PR-3).

Audit found that several endpoints in mobile_api.py return HTTP 500 due to
schema/model drift:

- /patients/me uses Patient.fio / Patient.birth_year / Patient.telegram_id
  which don't exist on the Patient model (real columns: first_name,
  last_name, middle_name, birth_date, and telegram_id is on User).
- /appointments/upcoming and /appointments/{id} access appointment.doctor
  relationship (doesn't exist on Appointment) and appointment.doctor.name
  (Doctor has no `name`; name is on User.full_name via doctor.user).
- /appointments/book looks up doctor via crud_user.get_user, but doctors
  are in the doctors table, not users; it also reads doctor.name / doctor.
  specialty from the User object (User has no specialty).
- /lab/results reads result.test_name / result.result / result.normal_range
  / result.unit / result.test_date / result.status / result.doctor_notes —
  verify these exist on the LabResult model.

This file asserts 200 (not 500) for each endpoint.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from app.core.security import get_password_hash
from app.crud.lab import patient_lab_results_statement
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.lab import (
    LabOrder,
    LabReportInstance,
    LabReportTemplate,
    LabReportTemplateVersion,
    LabReportValue,
    LabResult,
)
from app.models.patient import Patient
from app.models.user import User


def _suffix() -> str:
    return uuid4().hex[:10]


def _make_patient_user(db_session) -> tuple[User, Patient]:
    s = _suffix()
    user = User(
        username=f"mob_pt_{s}",
        email=f"mob-pt-{s}@test.local",
        full_name=f"Mobile Patient {s}",
        hashed_password=get_password_hash("patient123"),
        role="Patient",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    patient = Patient(
        user_id=user.id,
        first_name="Patient",
        last_name=f"Test{s}",
        phone=f"+99890{s[:7]}",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return user, patient


def _make_doctor(db_session) -> Doctor:
    s = _suffix()
    # Doctor requires a User for name lookup
    user = User(
        username=f"doc_{s}",
        email=f"doc-{s}@test.local",
        full_name=f"Dr. {s}",
        hashed_password=get_password_hash("docpass"),
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(
        user_id=user.id,
        specialty="cardiology",
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _login(client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "patient123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_get_mobile_patient_profile_returns_200(client, db_session):
    """GET /api/v1/mobile/patients/me should return 200, not 500."""
    user, _ = _make_patient_user(db_session)
    headers = _login(client, user)

    response = client.get("/api/v1/mobile/patients/me", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert "id" in body
    assert "fio" in body
    assert "phone" in body


def test_get_upcoming_appointments_returns_200(client, db_session):
    """GET /api/v1/mobile/appointments/upcoming should return 200, not 500."""
    user, patient = _make_patient_user(db_session)
    doctor = _make_doctor(db_session)
    # Seed an upcoming appointment
    appt = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=date.today() + timedelta(days=3),
        status="scheduled",
    )
    db_session.add(appt)
    db_session.commit()

    headers = _login(client, user)
    response = client.get("/api/v1/mobile/appointments/upcoming", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)


def test_get_appointment_detail_returns_200(client, db_session):
    """GET /api/v1/mobile/appointments/{id} should return 200, not 500."""
    user, patient = _make_patient_user(db_session)
    doctor = _make_doctor(db_session)
    appt = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=date.today() + timedelta(days=3),
        status="scheduled",
    )
    db_session.add(appt)
    db_session.commit()
    db_session.refresh(appt)

    headers = _login(client, user)
    response = client.get(f"/api/v1/mobile/appointments/{appt.id}", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == appt.id
    assert "doctor_name" in body


def test_get_lab_results_returns_200(client, db_session):
    """GET /api/v1/mobile/lab/results should return 200, not 500."""
    user, _ = _make_patient_user(db_session)
    headers = _login(client, user)

    response = client.get("/api/v1/mobile/lab/results", headers=headers)

    # Empty list is fine — we just need 200, not 500.
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)


def test_mobile_lab_result_uses_exact_release_snapshot_and_preserves_legacy(
    client, db_session
):
    user, patient = _make_patient_user(db_session)
    other_user, other_patient = _make_patient_user(db_session)
    original_date = datetime(2025, 1, 1, tzinfo=UTC)
    revised_date = original_date + timedelta(days=3)
    order = LabOrder(patient_id=patient.id, status="done")
    other_order = LabOrder(patient_id=other_patient.id, status="done")
    template = LabReportTemplate(
        code=f"mobile_{_suffix()}", name="Mobile parity", family="test"
    )
    version = LabReportTemplateVersion(
        template=template,
        version_no=1,
        status="PUBLISHED",
        layout_preset="standard",
    )
    db_session.add_all([order, other_order, version])
    db_session.flush()

    def create_instance(
        lab_order, *, status, finalized_at=None, supersedes_instance_id=None
    ):
        instance = LabReportInstance(
            order_id=lab_order.id,
            patient_id=lab_order.patient_id,
            template_id=template.id,
            template_version_id=version.id,
            status=status,
            finalized_at=finalized_at,
            supersedes_instance_id=supersedes_instance_id,
        )
        db_session.add(instance)
        db_session.flush()
        return instance

    original = create_instance(order, status="FINALIZED", finalized_at=original_date)
    revised = create_instance(
        order,
        status="PRINTED",
        finalized_at=revised_date,
        supersedes_instance_id=original.id,
    )
    draft = create_instance(order, status="DRAFT", supersedes_instance_id=revised.id)
    other_report = create_instance(
        other_order, status="FINALIZED", finalized_at=original_date
    )

    long_text = ("SYNTHETIC Ниҳоявий кузатув. " * 8).strip()
    values = [
        ("qualified", "<1", "not_evaluated", None),
        ("full_text", long_text, "not_evaluated", None),
        ("without_rules", "3.2", "not_applicable", None),
        ("cleared", None, "missing", None),
        ("normal", "7", "evaluated", "normal"),
        ("high", "20", "evaluated", "high"),
    ]
    db_session.add(
        LabReportValue(
            instance_id=original.id,
            field_key="qualified",
            value_text="5",
            evaluation_snapshot={
                "status": "evaluated",
                "interpretation": "normal",
                "unit": "U/L",
            },
        )
    )
    for field, raw_value, evaluation_status, interpretation in values:
        db_session.add_all(
            [
                LabReportValue(
                    instance_id=revised.id,
                    field_key=field,
                    value_text="1.0000" if field == "qualified" else raw_value,
                    value_numeric=Decimal(1) if field == "qualified" else None,
                    resolved_reference_text="1–10" if raw_value else None,
                    evaluation_snapshot={
                        "status": evaluation_status,
                        "interpretation": interpretation,
                        "unit": "mg/L",
                    },
                ),
                LabResult(
                    order_id=order.id,
                    test_code=field,
                    test_name=field,
                    value=raw_value[:128] if raw_value is not None else None,
                    unit="U/L",
                    ref_range="old range",
                    abnormal=(field == "high"),
                    source_root_instance_id=original.id,
                    source_instance_id=revised.id,
                    created_at=original_date,
                ),
            ]
        )
    db_session.add_all(
        [
            LabResult(
                order_id=order.id,
                test_code="qualified",
                test_name="legacy",
                value="10",
                abnormal=True,
                created_at=original_date,
            ),
            LabResult(
                order_id=order.id,
                test_code="old",
                test_name="no_snapshot",
                value="3",
                source_root_instance_id=original.id,
                source_instance_id=original.id,
            ),
            LabResult(
                order_id=order.id,
                test_code="draft",
                test_name="draft",
                value="40",
                source_root_instance_id=original.id,
                source_instance_id=draft.id,
            ),
            LabResult(
                order_id=order.id,
                test_code="wrong_patient",
                test_name="wrong_patient",
                value="4",
                source_root_instance_id=other_report.id,
                source_instance_id=other_report.id,
            ),
            LabResult(
                order_id=other_order.id, test_code="other", test_name="other", value="8"
            ),
        ]
    )
    db_session.commit()

    emr_observations = db_session.execute(
        patient_lab_results_statement(patient.id, include_observation=True)
    ).mappings()
    emr_values = {row["test_name"]: row for row in emr_observations}
    assert emr_values["full_text"]["value"] == long_text
    assert emr_values["full_text"]["source_instance_id"] == revised.id
    assert emr_values["qualified"]["value"] == "<1"

    response = client.get("/api/v1/mobile/lab/results", headers=_login(client, user))
    assert response.status_code == 200, response.text
    rows = {row["test_name"]: row for row in response.json()}
    assert set(rows) == {"legacy", "no_snapshot", *(field for field, *_ in values)}
    assert rows["legacy"] == {
        "id": rows["legacy"]["id"],
        "test_name": "legacy",
        "result_value": "10",
        "reference_range": "",
        "unit": "",
        "result_date": original_date.replace(tzinfo=None).isoformat(),
        "status": "abnormal",
        "notes": None,
    }
    assert rows["no_snapshot"]["status"] == "unknown"
    for field, raw_value, evaluation_status, interpretation in values:
        row = rows[field]
        assert row["result_value"] == (raw_value or "")
        assert row["reference_range"] == ("1–10" if raw_value else "")
        assert row["unit"] == "mg/L"
        assert row["evaluation_status"] == evaluation_status
        assert row["interpretation"] == interpretation
        assert row["status"] == {"normal": "normal", "high": "abnormal"}.get(
            field, evaluation_status
        )
        assert row["source_instance_id"] == revised.id
        assert row["source_root_instance_id"] == original.id
        assert row["supersedes_instance_id"] == original.id
        assert (
            datetime.fromisoformat(row["result_date"]).replace(tzinfo=UTC)
            == revised_date
        )

    other_response = client.get(
        "/api/v1/mobile/lab/results", headers=_login(client, other_user)
    )
    assert other_response.status_code == 200, other_response.text
    assert [row["test_name"] for row in other_response.json()] == ["other"]


def test_get_mobile_quick_stats_returns_200(client, db_session):
    """GET /api/v1/mobile/stats should return 200, not 500."""
    user, _ = _make_patient_user(db_session)
    headers = _login(client, user)

    response = client.get("/api/v1/mobile/stats", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert "total_appointments" in body


def test_get_mobile_notifications_returns_200(client, db_session):
    """GET /api/v1/mobile/notifications should return 200, not 500."""
    user, _ = _make_patient_user(db_session)
    headers = _login(client, user)

    response = client.get("/api/v1/mobile/notifications", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)
