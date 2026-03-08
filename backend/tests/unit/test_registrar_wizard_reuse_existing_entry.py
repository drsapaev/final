from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.morning_assignment import (
    MorningAssignmentClaimError,
    MorningAssignmentService,
)


def _create_visit_for_queue_tag(
    db_session,
    *,
    patient_id: int,
    doctor_id: int,
    service_id: int,
    service_code: str,
    service_name: str,
) -> Visit:
    visit = Visit(
        patient_id=patient_id,
        doctor_id=doctor_id,
        visit_date=date.today(),
        visit_time="10:00",
        status="confirmed",
        discount_mode="none",
        approval_status="approved",
        department="cardiology",
        source="desk",
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)

    visit_service = VisitService(
        visit_id=visit.id,
        service_id=service_id,
        code=service_code,
        name=service_name,
        qty=1,
        price=Decimal("100000.00"),
    )
    db_session.add(visit_service)
    db_session.commit()
    db_session.refresh(visit)
    return visit


def _create_daily_queue(
    db_session,
    *,
    specialist_id: int,
    queue_tag: str,
) -> DailyQueue:
    queue = DailyQueue(
        day=date.today(),
        specialist_id=specialist_id,
        queue_tag=queue_tag,
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


def _create_doctor(
    db_session,
    *,
    username: str,
    email: str,
    full_name: str,
    specialty: str,
) -> Doctor:
    user = User(
        username=username,
        email=email,
        full_name=full_name,
        hashed_password="hashed",
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(
        user_id=user.id,
        specialty=specialty,
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _create_entry(
    db_session,
    *,
    queue_id: int,
    patient_id: int,
    number: int,
    status: str,
) -> OnlineQueueEntry:
    entry = OnlineQueueEntry(
        queue_id=queue_id,
        patient_id=patient_id,
        patient_name=f"Patient {patient_id}",
        phone="+998901234567",
        number=number,
        status=status,
        source="online",
        queue_time=datetime.now(ZoneInfo("Asia/Tashkent")).replace(microsecond=0),
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


@pytest.mark.unit
@pytest.mark.parametrize("existing_status", ["in_service", "diagnostics"])
def test_resolve_existing_queue_claim_reuses_canonical_active_entry(
    db_session,
    test_patient,
    test_doctor,
    test_service,
    existing_status,
):
    service = MorningAssignmentService(db_session)
    visit = _create_visit_for_queue_tag(
        db_session,
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        service_id=test_service.id,
        service_code=test_service.code,
        service_name=test_service.name,
    )
    daily_queue = _create_daily_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag=test_service.queue_tag,
    )
    existing_entry = _create_entry(
        db_session,
        queue_id=daily_queue.id,
        patient_id=test_patient.id,
        number=15,
        status=existing_status,
    )

    resolved_queue, resolved_entry = service._resolve_existing_queue_claim_or_raise(
        patient_id=visit.patient_id,
        target_date=date.today(),
        queue_tag=test_service.queue_tag,
    )

    assert resolved_queue.id == daily_queue.id
    assert resolved_entry.id == existing_entry.id
    assert resolved_entry.status == existing_status


@pytest.mark.unit
def test_resolve_existing_queue_claim_ignores_inactive_rows(
    db_session,
    test_patient,
    test_doctor,
    test_service,
):
    service = MorningAssignmentService(db_session)
    _create_visit_for_queue_tag(
        db_session,
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        service_id=test_service.id,
        service_code=test_service.code,
        service_name=test_service.name,
    )
    daily_queue = _create_daily_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag=test_service.queue_tag,
    )
    _create_entry(
        db_session,
        queue_id=daily_queue.id,
        patient_id=test_patient.id,
        number=18,
        status="served",
    )

    resolved_queue, resolved_entry = service._resolve_existing_queue_claim_or_raise(
        patient_id=test_patient.id,
        target_date=date.today(),
        queue_tag=test_service.queue_tag,
    )

    assert resolved_queue.id == daily_queue.id
    assert resolved_entry is None


@pytest.mark.unit
def test_resolve_existing_queue_claim_raises_on_ambiguous_active_rows(
    db_session,
    test_patient,
    test_doctor,
    test_service,
):
    service = MorningAssignmentService(db_session)
    second_doctor = _create_doctor(
        db_session,
        username="wizard_unit_ambiguous_doctor",
        email="wizard_unit_ambiguous_doctor@test.local",
        full_name="Wizard Unit Ambiguous Doctor",
        specialty="Cardiology",
    )
    _create_visit_for_queue_tag(
        db_session,
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        service_id=test_service.id,
        service_code=test_service.code,
        service_name=test_service.name,
    )
    first_queue = _create_daily_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag=test_service.queue_tag,
    )
    second_queue = _create_daily_queue(
        db_session,
        specialist_id=second_doctor.id,
        queue_tag=test_service.queue_tag,
    )
    _create_entry(
        db_session,
        queue_id=first_queue.id,
        patient_id=test_patient.id,
        number=21,
        status="waiting",
    )
    _create_entry(
        db_session,
        queue_id=second_queue.id,
        patient_id=test_patient.id,
        number=22,
        status="diagnostics",
    )

    with pytest.raises(MorningAssignmentClaimError, match="Неоднозначная активная запись очереди"):
        service._resolve_existing_queue_claim_or_raise(
            patient_id=test_patient.id,
            target_date=date.today(),
            queue_tag=test_service.queue_tag,
        )
