"""Authenticated, non-reserving public booking request workflow."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.clinic import ClinicSettings, Doctor, Schedule
from app.models.patient import Patient
from app.models.patient_access_audit import PatientAccessAuditLog
from app.models.public_booking_request import (
    PublicBookingRequest,
    PublicBookingRequestEvent,
)
from app.models.service import Service
from app.models.user import User
from app.services.public_booking_availability import PUBLIC_BOOKING_TIMEZONE
from app.services.public_booking_request_service import (
    PublicBookingRequestError,
    PublicBookingRequestService,
)
from tests.conftest import mint_access_token

PATIENT_REQUESTS = "/api/v1/patients/booking-requests"
STAFF_REQUESTS = "/api/v1/admin/public-booking-requests"


@pytest.fixture
def public_booking_case(db_session: Session, test_patient):
    unique = uuid4().hex[:12]
    doctor_user = User(
        username=f"public-request-doctor-{unique}",
        hashed_password="not-used-in-this-test",
        role="Doctor",
        is_active=True,
        full_name="Синтетический врач",
    )
    patient_user = User(
        username=f"public-request-patient-{unique}",
        hashed_password="not-used-in-this-test",
        role="Patient",
        is_active=True,
        full_name="Синтетический пациент",
    )
    db_session.add_all([doctor_user, patient_user])
    db_session.flush()
    test_patient.user_id = patient_user.id

    doctor = Doctor(
        user_id=doctor_user.id,
        specialty="cardiology",
        active=True,
        show_on_website=True,
        slug=f"public-request-doctor-{unique}",
        bio_ru="Врач-кардиолог",
        bio_uz="Kardiolog shifokor",
    )
    service = Service(
        name="Cardiology consultation",
        name_uz="Kardiolog maslahati",
        description_ru="Приём врача-кардиолога.",
        description_uz="Kardiolog shifokor qabuli.",
        slug=f"cardiology-consultation-{unique}",
        duration_minutes=20,
        active=True,
        show_on_website=True,
        requires_doctor=True,
    )
    db_session.add_all([doctor, service])
    db_session.flush()

    target_date = datetime.now(PUBLIC_BOOKING_TIMEZONE).date() + timedelta(days=2)
    db_session.add(
        Schedule(
            doctor_id=doctor.id,
            weekday=target_date.weekday(),
            start_time=time(9),
            end_time=time(11),
            breaks=[],
            active=True,
        )
    )
    db_session.add_all(
        [
            ClinicSettings(
                key="public_booking_settings",
                category="booking_settings",
                value={
                    "version": 1,
                    "is_enabled": True,
                    "mode": "registrar_request",
                    "booking_horizon_days": 30,
                    "service_ids": [service.id],
                    "doctor_ids": [doctor.id],
                },
                updated_by=doctor_user.id,
            ),
            ClinicSettings(
                key=f"public_booking_calendar_year_{target_date.year:04d}",
                category="booking_calendar",
                value={
                    "year": target_date.year,
                    "version": 1,
                    "is_confirmed": True,
                    "holidays": [],
                    "confirmed_at": datetime.now(UTC).isoformat(),
                    "confirmed_by": doctor_user.id,
                },
                updated_by=doctor_user.id,
            ),
        ]
    )
    db_session.flush()

    return {
        "date": target_date,
        "doctor": doctor,
        "service": service,
        "patient": test_patient,
        "patient_headers": {
            "Authorization": f"Bearer {mint_access_token(patient_user)}"
        },
        "patient_user_id": patient_user.id,
        "doctor_id": doctor.id,
    }


def _create_body(case, *, hour: str = "09:00") -> dict[str, object]:
    return {
        "service_slug": case["service"].slug,
        "doctor_slug": case["doctor"].slug,
        "appointment_date": case["date"].isoformat(),
        "appointment_time": hour,
        "expected_settings_version": 1,
    }


def _request_new_time(
    client: TestClient, request_id: str, registrar_token: str, version: int = 1
):
    return client.post(
        f"{STAFF_REQUESTS}/{request_id}/request-new-time",
        headers={"Authorization": f"Bearer {registrar_token}"},
        json={"expected_version": version},
    )


@pytest.mark.integration
def test_patient_submission_is_idempotent_and_never_creates_appointment(
    client: TestClient, db_session: Session, public_booking_case
):
    case = public_booking_case
    idempotency_key = uuid4().hex
    headers = {
        **case["patient_headers"],
        "Idempotency-Key": idempotency_key,
    }
    body = _create_body(case)

    first = client.post(PATIENT_REQUESTS, headers=headers, json=body)
    replay = client.post(PATIENT_REQUESTS, headers=headers, json=body)

    assert first.status_code == 201, first.text
    assert replay.status_code == 201, replay.text
    assert replay.json()["id"] == first.json()["id"]
    assert first.headers["cache-control"] == "no-store"
    assert first.json()["status"] == "pending"
    assert "patient_id" not in first.json()
    assert db_session.query(PublicBookingRequest).count() == 1
    assert db_session.query(PublicBookingRequestEvent).count() == 1
    assert db_session.query(Appointment).count() == 0

    # Exercise the persisted idempotency record directly as well: the HTTP
    # middleware may short-circuit a retry while its response cache is warm.
    service = PublicBookingRequestService(db_session)
    replayed = service.create_for_patient(
        patient_id=case["patient"].id,
        actor_user_id=case["patient_user_id"],
        service_slug=case["service"].slug,
        doctor_slug=case["doctor"].slug,
        appointment_date=case["date"],
        appointment_time=time(9),
        expected_settings_version=1,
        idempotency_key=idempotency_key,
        operation_scope=f"POST:{PATIENT_REQUESTS}",
    )
    assert str(replayed.id) == first.json()["id"]
    with pytest.raises(PublicBookingRequestError) as exc_info:
        service.create_for_patient(
            patient_id=case["patient"].id,
            actor_user_id=case["patient_user_id"],
            service_slug=case["service"].slug,
            doctor_slug=case["doctor"].slug,
            appointment_date=case["date"],
            appointment_time=time(9, 20),
            expected_settings_version=1,
            idempotency_key=idempotency_key,
            operation_scope=f"POST:{PATIENT_REQUESTS}",
        )
    assert exc_info.value.code == "booking_request_idempotency_conflict"

    duplicate = client.post(
        PATIENT_REQUESTS,
        headers={
            **case["patient_headers"],
            "Idempotency-Key": uuid4().hex,
        },
        json=body,
    )
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["detail"]["code"] == "booking_request_duplicate"
    assert db_session.query(PublicBookingRequest).count() == 1

    changed = client.post(
        PATIENT_REQUESTS,
        headers=headers,
        json=_create_body(case, hour="09:20"),
    )
    assert changed.status_code == 409
    assert db_session.query(PublicBookingRequest).count() == 1

    patient_list = client.get(PATIENT_REQUESTS, headers=case["patient_headers"])
    assert patient_list.status_code == 200
    assert [item["id"] for item in patient_list.json()["items"]] == [first.json()["id"]]


@pytest.mark.integration
def test_patient_request_creation_is_limited_per_patient(
    client: TestClient, db_session: Session, public_booking_case
):
    case = public_booking_case
    for minute in (0, 20, 40, 60, 80):
        hour = 9 + minute // 60
        minute_of_hour = minute % 60
        response = client.post(
            PATIENT_REQUESTS,
            headers={
                **case["patient_headers"],
                "Idempotency-Key": uuid4().hex,
            },
            json=_create_body(
                case,
                hour=f"{hour:02d}:{minute_of_hour:02d}",
            ),
        )
        assert response.status_code == 201, response.text

    limited = client.post(
        PATIENT_REQUESTS,
        headers={
            **case["patient_headers"],
            "Idempotency-Key": uuid4().hex,
        },
        json=_create_body(case, hour="10:40"),
    )

    assert limited.status_code == 429, limited.text
    assert limited.json()["detail"]["code"] == "booking_request_rate_limited"
    assert limited.headers["retry-after"] == "60"
    assert db_session.query(PublicBookingRequest).count() == 5
    assert db_session.query(Appointment).count() == 0


@pytest.mark.integration
def test_staff_can_ask_for_new_time_and_patient_resubmits_same_request(
    client: TestClient, db_session: Session, public_booking_case, registrar_user
):
    case = public_booking_case
    idempotency_key = uuid4().hex
    created = client.post(
        PATIENT_REQUESTS,
        headers={
            **case["patient_headers"],
            "Idempotency-Key": idempotency_key,
        },
        json=_create_body(case),
    )
    assert created.status_code == 201, created.text
    second_created = client.post(
        PATIENT_REQUESTS,
        headers={
            **case["patient_headers"],
            "Idempotency-Key": uuid4().hex,
        },
        json=_create_body(case, hour="10:40"),
    )
    assert second_created.status_code == 201, second_created.text

    registrar_token = mint_access_token(registrar_user)

    staff_list = client.get(
        STAFF_REQUESTS,
        headers={"Authorization": f"Bearer {registrar_token}"},
    )
    assert staff_list.status_code == 200, staff_list.text
    assert len(staff_list.json()["items"]) == 2
    request_id = created.json()["id"]
    audited = (
        db_session.query(PatientAccessAuditLog)
        .filter(
            PatientAccessAuditLog.resource_type == "public_booking_request",
            PatientAccessAuditLog.action == "view",
        )
        .all()
    )
    assert {row.resource_id for row in audited} == {
        request_id,
        second_created.json()["id"],
    }
    assert all(row.subject_patient_id == case["patient"].id for row in audited)
    needs_new_time = _request_new_time(client, request_id, registrar_token)
    assert needs_new_time.status_code == 200, needs_new_time.text
    assert needs_new_time.json()["status"] == "needs_new_time"
    assert len(needs_new_time.json()["history"]) == 2
    duplicate_while_waiting = client.post(
        PATIENT_REQUESTS,
        headers={
            **case["patient_headers"],
            "Idempotency-Key": uuid4().hex,
        },
        json=_create_body(case),
    )
    assert duplicate_while_waiting.status_code == 409
    assert (
        duplicate_while_waiting.json()["detail"]["code"] == "booking_request_duplicate"
    )

    unchanged = client.post(
        f"{PATIENT_REQUESTS}/{request_id}/resubmit",
        headers={
            **case["patient_headers"],
            "Idempotency-Key": uuid4().hex,
        },
        json={
            "expected_version": 2,
            "appointment_date": case["date"].isoformat(),
            "appointment_time": "09:00",
            "expected_settings_version": 1,
        },
    )
    assert unchanged.status_code == 409
    assert unchanged.json()["detail"]["code"] == "booking_time_unavailable"

    # Simulate the registrar finding a new conflict after the first request.
    db_session.add(
        Appointment(
            patient_id=case["patient"].id,
            doctor_id=case["doctor_id"],
            appointment_date=case["date"],
            appointment_time="09:00",
            duration_minutes_snapshot=20,
            status="scheduled",
        )
    )
    db_session.flush()

    resubmitted = client.post(
        f"{PATIENT_REQUESTS}/{request_id}/resubmit",
        headers={
            **case["patient_headers"],
            "Idempotency-Key": idempotency_key,
        },
        json={
            "expected_version": 2,
            "appointment_date": case["date"].isoformat(),
            "appointment_time": "09:20",
            "expected_settings_version": 1,
        },
    )
    assert resubmitted.status_code == 200, resubmitted.text
    assert resubmitted.json()["status"] == "pending"
    assert resubmitted.json()["appointment_time"] == "09:20:00"
    assert [item["event_type"] for item in resubmitted.json()["history"]] == [
        "submitted",
        "staff_requested_new_time",
        "resubmitted",
    ]
    assert db_session.query(PublicBookingRequest).count() == 2
    assert db_session.query(Appointment).count() == 1

    rejected = client.post(
        f"{STAFF_REQUESTS}/{request_id}/reject",
        headers={"Authorization": f"Bearer {registrar_token}"},
        json={"expected_version": 3},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert len(rejected.json()["history"]) == 4
    released_slot = client.post(
        PATIENT_REQUESTS,
        headers={
            **case["patient_headers"],
            "Idempotency-Key": uuid4().hex,
        },
        json=_create_body(case, hour="09:20"),
    )
    assert released_slot.status_code == 201, released_slot.text
    assert db_session.query(PublicBookingRequest).count() == 3


@pytest.mark.integration
def test_patient_can_withdraw_own_request_but_another_patient_cannot(
    client: TestClient,
    db_session: Session,
    public_booking_case,
):
    case = public_booking_case
    idempotency_key = uuid4().hex
    created = client.post(
        PATIENT_REQUESTS,
        headers={
            **case["patient_headers"],
            "Idempotency-Key": idempotency_key,
        },
        json=_create_body(case),
    )
    assert created.status_code == 201, created.text

    other_user = User(
        username=f"other-patient-{uuid4().hex[:12]}",
        hashed_password="not-used-in-this-test",
        role="Patient",
        is_active=True,
    )
    db_session.add(other_user)
    db_session.flush()
    other_patient = Patient(
        first_name="Синтетический",
        last_name="Пациент",
        phone=f"+9989{uuid4().int % 100000000:08d}",
    )
    db_session.add(other_patient)
    db_session.flush()
    other_patient.user_id = other_user.id
    db_session.flush()
    other_headers = {"Authorization": f"Bearer {mint_access_token(other_user)}"}

    denied = client.post(
        f"{PATIENT_REQUESTS}/{created.json()['id']}/withdraw",
        headers=other_headers,
        json={"expected_version": 1},
    )
    assert denied.status_code == 404
    assert denied.json()["detail"]["code"] == "booking_request_not_found"

    withdrawn = client.post(
        f"{PATIENT_REQUESTS}/{created.json()['id']}/withdraw",
        headers=case["patient_headers"],
        json={"expected_version": 1},
    )
    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["status"] == "withdrawn"
    assert [item["event_type"] for item in withdrawn.json()["history"]] == [
        "submitted",
        "withdrawn",
    ]


@pytest.mark.integration
def test_unlinked_patient_gets_the_declared_profile_required_response(
    client: TestClient, db_session: Session, public_booking_case
):
    user = User(
        username=f"unlinked-public-patient-{uuid4().hex[:12]}",
        hashed_password="not-used-in-this-test",
        role="Patient",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    response = client.post(
        PATIENT_REQUESTS,
        headers={
            "Authorization": f"Bearer {mint_access_token(user)}",
            "Idempotency-Key": uuid4().hex,
        },
        json=_create_body(public_booking_case),
    )

    assert response.status_code == 404
    assert response.json()["detail"]["reason"] == "patient_profile_required"


@pytest.mark.integration
def test_public_booking_request_openapi_routes_and_idempotency_contract(
    client: TestClient,
):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    create = schema["paths"][PATIENT_REQUESTS]["post"]
    resubmit = schema["paths"][f"{PATIENT_REQUESTS}/{{request_id}}/resubmit"]["post"]
    staff_list = schema["paths"][STAFF_REQUESTS]["get"]

    assert create["operationId"] == "patient_create_public_booking_request"
    assert resubmit["operationId"] == "patient_resubmit_public_booking_request"
    assert staff_list["operationId"] == "staff_list_public_booking_requests"
    assert "Idempotency-Key" in {
        parameter["name"] for parameter in create["parameters"]
    }
    assert "201" in create["responses"]
    assert "409" in create["responses"]
    assert "429" in create["responses"]
    assert create["responses"]["429"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("PublicBookingRequestErrorOut")
    not_found_schema = create["responses"]["404"]["content"]["application/json"][
        "schema"
    ]
    assert {"anyOf", "oneOf"}.intersection(not_found_schema)
    assert staff_list.get("security") or schema.get("security")
