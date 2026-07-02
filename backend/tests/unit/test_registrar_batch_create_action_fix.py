from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue
from app.models.service import Service
from app.models.user import User
from app.services.batch_patient_service import BatchPatientService, EntryAction
from app.services.queue_domain_service import QueueDomainService
from app.services.service_mapping import normalize_service_code


def _create_batch_service(
    db_session,
    *,
    service_code: str,
    doctor_id: int | None,
    queue_tag: str = "cardiology",
) -> Service:
    service = Service(
        code=service_code,
        service_code=service_code,
        name=f"Service {service_code}",
        active=True,
        queue_tag=queue_tag,
        doctor_id=doctor_id,
        requires_doctor=doctor_id is not None,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _create_second_doctor(db_session) -> Doctor:
    user = User(
        username="test_cardio_second",
        email="cardio-second@test.com",
        full_name="Second Cardiologist",
        hashed_password="test-hash",
        role="Doctor",
        is_active=True,
        is_superuser=False,
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


def test_create_entry_routes_through_queue_domain_service_boundary(
    db_session,
    test_patient,
    test_doctor,
    monkeypatch,
):
    service = _create_batch_service(
        db_session,
        service_code="W2C-BATCH-UNIT",
        doctor_id=test_doctor.id,
        queue_tag="cardiology",
    )
    captured: dict[str, object] = {}

    def fake_allocate_ticket(self, *, allocation_mode="create_entry", **kwargs):
        captured["allocation_mode"] = allocation_mode
        captured.update(kwargs)
        return SimpleNamespace(id=77, number=11)

    monkeypatch.setattr(
        QueueDomainService,
        "allocate_ticket",
        fake_allocate_ticket,
    )

    result = BatchPatientService(db_session)._create_entry(
        patient_id=test_patient.id,
        target_date=date.today(),
        action=EntryAction(
            action="create",
            specialty="cardiology",
            service_code=service.service_code,
        ),
    )

    assert result.status == "created"
    assert result.id == 77
    assert captured["allocation_mode"] == "create_entry"
    assert captured["source"] == "batch_update"
    assert captured["status"] == "waiting"
    assert captured["service_codes"] == [normalize_service_code(service.service_code)]
    assert captured["commit"] is False
    assert captured["patient_id"] == test_patient.id
    assert captured["patient_name"] == test_patient.short_name()
    assert captured["phone"] == test_patient.phone
    assert captured["daily_queue"].specialist_id == test_doctor.id
    assert captured["daily_queue"].queue_tag == "cardiology"


def test_create_entry_returns_safe_error_when_queue_resolution_is_ambiguous(
    db_session,
    test_patient,
    test_doctor,
):
    second_doctor = _create_second_doctor(db_session)
    service = _create_batch_service(
        db_session,
        service_code="W2C-BATCH-AMB",
        doctor_id=None,
        queue_tag="cardiology",
    )

    db_session.add_all(
        [
            DailyQueue(
                day=date.today(),
                specialist_id=test_doctor.id,
                queue_tag="cardiology",
                active=True,
            ),
            DailyQueue(
                day=date.today(),
                specialist_id=second_doctor.id,
                queue_tag="cardiology",
                active=True,
            ),
        ]
    )
    db_session.commit()

    result = BatchPatientService(db_session)._create_entry(
        patient_id=test_patient.id,
        target_date=date.today(),
        action=EntryAction(
            action="create",
            specialty="cardiology",
            service_code=service.service_code,
        ),
    )

    assert result.status == "error"
    assert result.id == 0
    assert "Неоднозначная очередь" in (result.error or "")
