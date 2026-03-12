from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.service import Service
from app.models.user import User
from app.services.qr_full_update_queue_assignment_service import (
    QRFullUpdateCreateBranchHandoff,
    QRFullUpdateQueueAssignmentService,
)


def _create_doctor_with_user(
    db_session,
    *,
    username: str,
    specialty: str,
) -> Doctor:
    user = User(
        username=username,
        full_name=f"{username} full",
        email=f"{username}@example.com",
        hashed_password="test-hash",
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()

    doctor = Doctor(
        user_id=user.id,
        specialty=specialty,
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


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


def _create_service(
    db_session,
    *,
    code: str,
    queue_tag: str,
    name: str | None = None,
) -> Service:
    service = Service(
        code=code,
        service_code=code,
        name=name or code,
        price=50000,
        active=True,
        queue_tag=queue_tag,
        is_consultation=False,
        requires_doctor=False,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


@pytest.mark.unit
def test_prepare_create_branch_handoffs_builds_explicit_qr_local_handoff(
    db_session,
    test_patient,
    test_doctor,
):
    original_queue = _create_daily_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
    )
    lab_queue = _create_daily_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag="lab",
    )
    lab_service = _create_service(
        db_session,
        code="W2C-QR-LAB-SEAM",
        queue_tag="lab",
        name="Lab seam service",
    )
    original_entry = OnlineQueueEntry(
        queue_id=original_queue.id,
        number=1,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        source="online",
        status="waiting",
        queue_time=datetime.now() - timedelta(hours=1),
        discount_mode="none",
    )
    db_session.add(original_entry)
    db_session.commit()
    db_session.refresh(original_entry)

    service = QRFullUpdateQueueAssignmentService(db_session)
    handoffs = service.prepare_create_branch_handoffs(
        entry=original_entry,
        request_services=[{"service_id": lab_service.id, "quantity": 1}],
        new_service_ids=[lab_service.id],
        discount_mode="none",
        all_free=False,
        log_prefix="[test]",
    )

    assert len(handoffs) == 1
    handoff = handoffs[0]
    assert handoff.target_queue_id == lab_queue.id
    assert handoff.target_queue_tag == "lab"
    assert handoff.create_entry_payload["birth_year"] is None
    assert handoff.create_entry_payload["address"] is None
    assert handoff.create_entry_payload["source"] == "online"
    assert handoff.create_entry_payload["discount_mode"] == "none"
    assert handoff.create_entry_payload["total_amount"] == 50000

    services_payload = json.loads(handoff.create_entry_payload["services"])
    assert services_payload[0]["service_id"] == lab_service.id
    assert services_payload[0]["price"] == 50000
    assert services_payload[0]["queue_time"] == handoff.current_queue_time.isoformat()
    assert json.loads(handoff.create_entry_payload["service_codes"]) == [
        "W2C-QR-LAB-SEAM"
    ]


@dataclass
class _FakeBoundaryAllocator:
    returned_entry: OnlineQueueEntry
    calls: list[dict]

    def allocate_ticket(self, **kwargs):
        self.calls.append(kwargs)
        return self.returned_entry


@pytest.mark.unit
def test_materialize_create_branch_handoffs_uses_explicit_qr_local_handoff():
    current_queue_time = datetime(2026, 3, 9, 12, 0, 0)
    returned_entry = OnlineQueueEntry(
        queue_id=22,
        number=8,
        patient_id=101,
        patient_name="QR Patient",
        phone="+998901234567",
        birth_year=1990,
        address="QR address",
        status="waiting",
        source="online",
        discount_mode="none",
        visit_id=None,
        session_id="sess-101",
        services=json.dumps(
            [
                {
                    "service_id": 7,
                    "name": "Lab seam service",
                    "code": "LAB",
                    "quantity": 1,
                    "price": 50000,
                    "queue_time": current_queue_time.isoformat(),
                    "cancelled": False,
                }
            ],
            ensure_ascii=False,
        ),
        service_codes=json.dumps(["LAB"], ensure_ascii=False),
        total_amount=50000,
        queue_time=current_queue_time,
    )
    fake_boundary = _FakeBoundaryAllocator(returned_entry=returned_entry, calls=[])
    handoff = QRFullUpdateCreateBranchHandoff(
        service_id=7,
        service_name="Lab seam service",
        target_queue_id=22,
        target_queue_tag="lab",
        queue_day=date(2026, 3, 9),
        current_queue_time=current_queue_time,
        create_entry_payload={
            "patient_id": 101,
            "patient_name": "QR Patient",
            "phone": "+998901234567",
            "birth_year": 1990,
            "address": "QR address",
            "status": "waiting",
            "source": "online",
            "discount_mode": "none",
            "visit_id": None,
            "total_amount": 50000,
            "services": json.dumps(
                [
                    {
                        "service_id": 7,
                        "name": "Lab seam service",
                        "code": "LAB",
                        "quantity": 1,
                        "price": 50000,
                        "queue_time": current_queue_time.isoformat(),
                        "cancelled": False,
                    }
                ],
                ensure_ascii=False,
            ),
            "service_codes": json.dumps(["LAB"], ensure_ascii=False),
        },
    )
    service = QRFullUpdateQueueAssignmentService(
        db=SimpleNamespace(),
        number_allocator=lambda queue_id: 8,
        session_id_provider=lambda patient_id, queue_id, queue_day: "sess-101",
        boundary_allocator=fake_boundary,
    )

    created_entries = service.materialize_create_branch_handoffs(
        [handoff],
        log_prefix="[test]",
    )

    assert len(created_entries) == 1
    created_entry = created_entries[0]
    assert created_entry is returned_entry
    assert created_entry.queue_id == 22
    assert created_entry.number == 8
    assert created_entry.queue_time == current_queue_time
    assert created_entry.source == "online"
    assert created_entry.status == "waiting"
    assert created_entry.birth_year == 1990
    assert created_entry.address == "QR address"
    assert created_entry.session_id == "sess-101"
    assert created_entry.total_amount == 50000
    assert json.loads(created_entry.service_codes) == ["LAB"]
    assert len(fake_boundary.calls) == 1
    boundary_call = fake_boundary.calls[0]
    assert boundary_call["allocation_mode"] == "create_entry"
    assert boundary_call["queue_id"] == 22
    assert boundary_call["number"] == 8
    assert boundary_call["session_id"] == "sess-101"
    assert boundary_call["queue_time"] == current_queue_time
    assert boundary_call["source"] == "online"
    assert boundary_call["birth_year"] == 1990
    assert boundary_call["address"] == "QR address"
    assert boundary_call["commit"] is False
