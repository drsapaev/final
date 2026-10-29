"""Authenticated, non-reserving public booking request workflow."""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime, time, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import Request, Response
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.api.v1.endpoints.patient_portal as patient_portal
from app.models.appointment import Appointment
from app.models.clinic import ClinicSettings, Doctor, Schedule
from app.models.department import Department
from app.models.notification import NotificationDelivery, NotificationEvent
from app.models.patient import Patient
from app.models.patient_access_audit import PatientAccessAuditLog
from app.models.public_booking_request import (
    PublicBookingRequest,
    PublicBookingRequestEvent,
    PublicBookingRequestNotificationOutbox,
)
from app.models.service import Service
from app.models.user import User
from app.schemas.public_booking_request import (
    PublicBookingRequestCreate,
    PublicBookingRequestResubmit,
)
from app.services.public_booking_availability import PUBLIC_BOOKING_TIMEZONE
from app.services.public_booking_request_notification_outbox import (
    PublicBookingRequestNotificationOutboxService,
)
from app.services.public_booking_request_service import (
    PublicBookingRequestError,
    PublicBookingRequestService,
)
from app.services.registrar_notification_service import RegistrarNotificationService
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

    department = Department(
        key=f"public-request-{unique}",
        name_ru="Синтетическое отделение",
        name_uz="Sintetik bo'lim",
        active=True,
    )
    db_session.add(department)
    db_session.flush()

    doctor = Doctor(
        user_id=doctor_user.id,
        department_id=department.id,
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
        "department_id": department.id,
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


def _confirm_request(
    client: TestClient, request_id: str, registrar_token: str, version: int = 1
):
    return client.post(
        f"{STAFF_REQUESTS}/{request_id}/confirm",
        headers={"Authorization": f"Bearer {registrar_token}"},
        json={"expected_version": version},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create", "resubmit"])
async def test_booking_request_database_work_does_not_block_event_loop(
    operation: str, monkeypatch: pytest.MonkeyPatch
):
    request_id = uuid4()
    operation_started = threading.Event()
    release_operation = threading.Event()

    def blocking_write(*args, **kwargs):
        operation_started.set()
        if not release_operation.wait(timeout=1):
            raise AssertionError("the booking database call blocked the event loop")
        return SimpleNamespace(id=request_id, version=2)

    monkeypatch.setattr(
        patient_portal, "_require_patient_audited", lambda *args, **kwargs: 321
    )
    monkeypatch.setattr(patient_portal, "log_patient_access", lambda **kwargs: None)
    monkeypatch.setattr(
        PublicBookingRequestService, "create_for_patient", blocking_write
    )
    monkeypatch.setattr(
        PublicBookingRequestService, "resubmit_for_patient", blocking_write
    )

    monkeypatch.setattr(
        patient_portal.PublicBookingRequestNotificationOutboxService,
        "dispatch_request_now",
        lambda *args, **kwargs: {"claimed": 0, "delivered": 0, "deferred": 0},
    )

    path = (
        f"{PATIENT_REQUESTS}/{request_id}/resubmit"
        if operation == "resubmit"
        else PATIENT_REQUESTS
    )
    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 80),
            "client": ("testclient", 123),
        }
    )
    response = Response()
    current_user = SimpleNamespace(id=12)
    target_date = datetime.now(PUBLIC_BOOKING_TIMEZONE).date() + timedelta(days=2)

    async def release_after_event_loop_yields() -> bool:
        assert await asyncio.to_thread(operation_started.wait, 1)
        await asyncio.sleep(0.01)
        event_loop_remained_responsive = not release_operation.is_set()
        release_operation.set()
        return event_loop_remained_responsive

    release_task = asyncio.create_task(release_after_event_loop_yields())
    if operation == "create":
        result = await asyncio.wait_for(
            patient_portal.create_patient_public_booking_request(
                PublicBookingRequestCreate(
                    service_slug="service",
                    doctor_slug="doctor",
                    appointment_date=target_date,
                    appointment_time=time(9),
                    expected_settings_version=1,
                ),
                request,
                response,
                "event-loop-test-key",
                object(),
                current_user,
            ),
            timeout=2,
        )
    else:
        result = await asyncio.wait_for(
            patient_portal.resubmit_patient_public_booking_request(
                request_id,
                PublicBookingRequestResubmit(
                    expected_version=1,
                    appointment_date=target_date,
                    appointment_time=time(9),
                    expected_settings_version=1,
                ),
                request,
                response,
                "event-loop-test-key",
                object(),
                current_user,
            ),
            timeout=2,
        )

    assert await release_task
    assert result.id == request_id


@pytest.mark.integration
def test_patient_submission_is_idempotent_and_never_creates_appointment(
    client: TestClient, db_session: Session, public_booking_case, registrar_user
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
    outbox_item = (
        db_session.query(PublicBookingRequestNotificationOutbox)
        .filter(
            PublicBookingRequestNotificationOutbox.request_id
            == UUID(first.json()["id"])
        )
        .one()
    )
    assert outbox_item.event_type == "public_booking_request_submitted"
    assert outbox_item.request_version == 1
    assert outbox_item.attempt_count == 1
    assert outbox_item.completed_at is not None
    assert db_session.query(Appointment).count() == 0
    notification = (
        db_session.query(NotificationEvent)
        .filter(
            NotificationEvent.event_type == "public_booking_request_submitted",
            NotificationEvent.entity_id == first.json()["id"],
        )
        .one()
    )
    delivery = (
        db_session.query(NotificationDelivery)
        .filter(NotificationDelivery.event_id == notification.id)
        .one()
    )
    assert delivery.recipient_id == registrar_user.id
    assert notification.entity_type == "public_booking_request"
    assert notification.deep_link == "/registrar/booking-requests"
    assert "Синтетический пациент" not in notification.message
    assert notification.payload_snapshot["metadata"] == {
        "request_id": first.json()["id"],
        "request_version": 1,
    }

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
@pytest.mark.asyncio
async def test_booking_notification_outbox_retries_without_duplicate_delivery(
    client: TestClient,
    db_session: Session,
    public_booking_case,
    registrar_user,
    monkeypatch: pytest.MonkeyPatch,
):
    case = public_booking_case
    original_notify = RegistrarNotificationService.notify_public_booking_request
    attempts = 0

    async def fail_once_then_deliver(self, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return False
        return await original_notify(self, **kwargs)

    monkeypatch.setattr(
        RegistrarNotificationService,
        "notify_public_booking_request",
        fail_once_then_deliver,
    )

    response = client.post(
        PATIENT_REQUESTS,
        headers={
            **case["patient_headers"],
            "Idempotency-Key": uuid4().hex,
        },
        json=_create_body(case),
    )

    assert response.status_code == 201, response.text
    request_id = UUID(response.json()["id"])
    outbox_item = (
        db_session.query(PublicBookingRequestNotificationOutbox)
        .filter(PublicBookingRequestNotificationOutbox.request_id == request_id)
        .one()
    )
    assert outbox_item.attempt_count == 1
    assert outbox_item.completed_at is None
    assert outbox_item.last_error_code == "delivery_not_recorded"
    assert (
        db_session.query(NotificationEvent)
        .filter(NotificationEvent.entity_id == str(request_id))
        .count()
        == 0
    )

    outbox_item.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    retry_result = await PublicBookingRequestNotificationOutboxService(
        db_session
    ).process_due_batch()

    assert retry_result == {"claimed": 1, "delivered": 1, "deferred": 0}
    db_session.refresh(outbox_item)
    assert outbox_item.attempt_count == 2
    assert outbox_item.completed_at is not None
    assert outbox_item.last_error_code is None
    assert attempts == 2

    repeated_result = await PublicBookingRequestNotificationOutboxService(
        db_session
    ).process_due_batch()
    assert repeated_result == {"claimed": 0, "delivered": 0, "deferred": 0}
    notification = (
        db_session.query(NotificationEvent)
        .filter(
            NotificationEvent.event_type == "public_booking_request_submitted",
            NotificationEvent.entity_id == str(request_id),
        )
        .one()
    )
    deliveries = (
        db_session.query(NotificationDelivery)
        .filter(NotificationDelivery.event_id == notification.id)
        .all()
    )
    assert [delivery.recipient_id for delivery in deliveries] == [registrar_user.id]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_booking_notification_outbox_recovers_after_inbox_commit_before_ack(
    client: TestClient,
    db_session: Session,
    public_booking_case,
    registrar_user,
    monkeypatch: pytest.MonkeyPatch,
):
    case = public_booking_case
    original_mark_completed = (
        PublicBookingRequestNotificationOutboxService._mark_completed
    )
    acknowledgements = 0

    def fail_first_ack(self, outbox_id: int):
        nonlocal acknowledgements
        acknowledgements += 1
        if acknowledgements == 1:
            raise RuntimeError("synthetic acknowledgement outage")
        original_mark_completed(self, outbox_id)

    monkeypatch.setattr(
        PublicBookingRequestNotificationOutboxService,
        "_mark_completed",
        fail_first_ack,
    )

    response = client.post(
        PATIENT_REQUESTS,
        headers={
            **case["patient_headers"],
            "Idempotency-Key": uuid4().hex,
        },
        json=_create_body(case),
    )

    assert response.status_code == 201, response.text
    request_id = UUID(response.json()["id"])
    outbox_item = (
        db_session.query(PublicBookingRequestNotificationOutbox)
        .filter(PublicBookingRequestNotificationOutbox.request_id == request_id)
        .one()
    )
    assert outbox_item.attempt_count == 1
    assert outbox_item.completed_at is None
    assert outbox_item.lease_expires_at is not None
    assert (
        db_session.query(NotificationEvent)
        .filter(
            NotificationEvent.event_type == "public_booking_request_submitted",
            NotificationEvent.entity_id == str(request_id),
        )
        .count()
        == 1
    )
    assert (
        db_session.query(NotificationDelivery)
        .join(NotificationEvent)
        .filter(NotificationEvent.entity_id == str(request_id))
        .count()
        == 1
    )

    # Model a worker restart after the canonical inbox transaction committed
    # but before the outbox acknowledgment could be persisted.
    outbox_item.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    outbox_item.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()

    retry_result = await PublicBookingRequestNotificationOutboxService(
        db_session
    ).process_due_batch()

    assert retry_result == {"claimed": 1, "delivered": 1, "deferred": 0}
    db_session.refresh(outbox_item)
    assert outbox_item.attempt_count == 2
    assert outbox_item.completed_at is not None
    assert acknowledgements == 2
    assert (
        db_session.query(NotificationEvent)
        .filter(
            NotificationEvent.event_type == "public_booking_request_submitted",
            NotificationEvent.entity_id == str(request_id),
        )
        .count()
        == 1
    )
    assert (
        db_session.query(NotificationDelivery)
        .join(NotificationEvent)
        .filter(NotificationEvent.entity_id == str(request_id))
        .count()
        == 1
    )


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
    request_notifications = (
        db_session.query(NotificationEvent)
        .filter(NotificationEvent.entity_id == request_id)
        .order_by(NotificationEvent.id)
        .all()
    )
    assert [event.event_type for event in request_notifications] == [
        "public_booking_request_submitted",
        "public_booking_request_resubmitted",
    ]
    assert all(
        event.entity_type == "public_booking_request"
        and event.deep_link == "/registrar/booking-requests"
        and "Синтетический пациент" not in event.message
        for event in request_notifications
    )
    request_notification_deliveries = (
        db_session.query(NotificationDelivery)
        .filter(
            NotificationDelivery.event_id.in_(
                [event.id for event in request_notifications]
            )
        )
        .all()
    )
    assert {delivery.recipient_id for delivery in request_notification_deliveries} == {
        registrar_user.id
    }
    assert len(request_notification_deliveries) == 2
    request_outbox = (
        db_session.query(PublicBookingRequestNotificationOutbox)
        .filter(PublicBookingRequestNotificationOutbox.request_id == UUID(request_id))
        .order_by(PublicBookingRequestNotificationOutbox.request_version)
        .all()
    )
    assert [item.event_type for item in request_outbox] == [
        "public_booking_request_submitted",
        "public_booking_request_resubmitted",
    ]
    assert [item.request_version for item in request_outbox] == [1, 3]
    assert all(item.completed_at is not None for item in request_outbox)

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
def test_staff_confirmation_creates_regular_appointment_after_settings_change(
    client: TestClient,
    db_session: Session,
    public_booking_case,
    registrar_user,
):
    case = public_booking_case
    created = client.post(
        PATIENT_REQUESTS,
        headers={
            **case["patient_headers"],
            "Idempotency-Key": uuid4().hex,
        },
        json=_create_body(case),
    )
    assert created.status_code == 201, created.text

    # Disabling the intake channel and changing its mode applies to new
    # submissions; it does not invalidate an already-submitted request.
    settings = (
        db_session.query(ClinicSettings)
        .filter(ClinicSettings.key == "public_booking_settings")
        .one()
    )
    settings.value = {
        **settings.value,
        "version": 2,
        "is_enabled": False,
        "mode": "confirmed_appointment",
    }
    db_session.commit()

    registrar_token = mint_access_token(registrar_user)
    patient_denied = client.post(
        f"{STAFF_REQUESTS}/{created.json()['id']}/confirm",
        headers=case["patient_headers"],
        json={"expected_version": 1},
    )
    assert patient_denied.status_code == 403

    confirmed = _confirm_request(client, created.json()["id"], registrar_token)

    assert confirmed.status_code == 200, confirmed.text
    payload = confirmed.json()
    assert payload["status"] == "confirmed"
    assert payload["appointment_id"] is not None
    assert [event["event_type"] for event in payload["history"]] == [
        "submitted",
        "confirmed",
    ]
    assert confirmed.headers["cache-control"] == "no-store"

    appointment = db_session.query(Appointment).one()
    assert appointment.id == payload["appointment_id"]
    assert appointment.patient_id == case["patient"].id
    assert appointment.doctor_id == case["doctor_id"]
    assert appointment.department_id == case["department_id"]
    assert appointment.appointment_date == case["date"]
    assert appointment.appointment_time == "09:00"
    assert appointment.duration_minutes_snapshot == 20
    assert appointment.status == "scheduled"

    patient_requests = client.get(
        PATIENT_REQUESTS,
        headers=case["patient_headers"],
    )
    assert patient_requests.status_code == 200, patient_requests.text
    patient_item = patient_requests.json()["items"][0]
    assert patient_item["status"] == "confirmed"
    assert patient_item["appointment_id"] == appointment.id

    replay = _confirm_request(client, created.json()["id"], registrar_token)
    assert replay.status_code == 409
    assert replay.json()["detail"]["code"] == "booking_request_version_conflict"
    assert db_session.query(Appointment).count() == 1

    audit = (
        db_session.query(PatientAccessAuditLog)
        .filter(
            PatientAccessAuditLog.resource_type == "public_booking_request",
            PatientAccessAuditLog.resource_id == created.json()["id"],
            PatientAccessAuditLog.action == "confirm",
        )
        .one()
    )
    assert audit.subject_patient_id == case["patient"].id


@pytest.mark.integration
def test_confirmation_moves_unavailable_time_to_needs_new_time_then_confirms(
    client: TestClient,
    db_session: Session,
    public_booking_case,
    registrar_user,
):
    case = public_booking_case
    created = client.post(
        PATIENT_REQUESTS,
        headers={
            **case["patient_headers"],
            "Idempotency-Key": uuid4().hex,
        },
        json=_create_body(case),
    )
    assert created.status_code == 201, created.text

    db_session.add(
        Appointment(
            patient_id=case["patient"].id,
            doctor_id=case["doctor_id"],
            department_id=case["department_id"],
            appointment_date=case["date"],
            appointment_time="09:00",
            duration_minutes_snapshot=20,
            status="scheduled",
        )
    )
    db_session.flush()

    registrar_token = mint_access_token(registrar_user)
    unavailable = _confirm_request(client, created.json()["id"], registrar_token)
    assert unavailable.status_code == 200, unavailable.text
    assert unavailable.json()["status"] == "needs_new_time"
    assert unavailable.json()["appointment_id"] is None
    assert unavailable.json()["history"][-1]["event_type"] == (
        "confirmation_slot_unavailable"
    )
    assert db_session.query(Appointment).count() == 1

    resubmitted = client.post(
        f"{PATIENT_REQUESTS}/{created.json()['id']}/resubmit",
        headers={
            **case["patient_headers"],
            "Idempotency-Key": uuid4().hex,
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

    confirmed = _confirm_request(
        client, created.json()["id"], registrar_token, version=3
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["appointment_time"] == "09:20:00"
    assert confirmed.json()["appointment_id"] is not None
    assert db_session.query(Appointment).count() == 2


@pytest.mark.integration
def test_confirmation_failure_rolls_back_appointment_and_request_transition(
    client: TestClient,
    db_session: Session,
    public_booking_case,
    registrar_user,
    monkeypatch,
):
    case = public_booking_case
    created = client.post(
        PATIENT_REQUESTS,
        headers={
            **case["patient_headers"],
            "Idempotency-Key": uuid4().hex,
        },
        json=_create_body(case),
    )
    assert created.status_code == 201, created.text

    service = PublicBookingRequestService(db_session)
    add_event = service._add_event

    def fail_after_appointment_flush(**kwargs):
        if kwargs["event_type"] == "confirmed":
            raise RuntimeError("synthetic confirmation rollback")
        add_event(**kwargs)

    monkeypatch.setattr(service, "_add_event", fail_after_appointment_flush)
    with pytest.raises(RuntimeError, match="synthetic confirmation rollback"):
        service.confirm_for_staff(
            request_id=UUID(created.json()["id"]),
            actor_user_id=case["patient_user_id"],
            expected_version=1,
        )

    db_session.expire_all()
    request = (
        db_session.query(PublicBookingRequest)
        .filter(PublicBookingRequest.id == UUID(created.json()["id"]))
        .one()
    )
    assert request.status == "pending"
    assert request.appointment_id is None
    assert db_session.query(Appointment).count() == 0


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
    confirm = schema["paths"][f"{STAFF_REQUESTS}/{{request_id}}/confirm"]["post"]

    assert create["operationId"] == "patient_create_public_booking_request"
    assert resubmit["operationId"] == "patient_resubmit_public_booking_request"
    assert staff_list["operationId"] == "staff_list_public_booking_requests"
    assert confirm["operationId"] == "staff_confirm_public_booking_request"
    assert "200" in confirm["responses"]
    assert "409" in confirm["responses"]
    assert "Idempotency-Key" in {
        parameter["name"] for parameter in create["parameters"]
    }
    assert "201" in create["responses"]
    assert "409" in create["responses"]
    assert "429" in create["responses"]
    assert create["responses"]["429"]["content"]["application/json"]["schema"][
        "$ref"
    ].endswith("PublicBookingRequestErrorOut")
    error_codes = set(
        schema["components"]["schemas"]["PublicBookingRequestErrorDetail"][
            "properties"
        ]["code"]["enum"]
    )
    assert {
        "booking_request_duplicate",
        "booking_request_rate_limited",
        "booking_request_unavailable",
    } <= error_codes
    not_found_schema = create["responses"]["404"]["content"]["application/json"][
        "schema"
    ]
    assert {"anyOf", "oneOf"}.intersection(not_found_schema)
    assert staff_list.get("security") or schema.get("security")
