from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from app.models.online_queue import DailyQueue
from app.services.qr_full_update_queue_assignment_service import (
    QRFullUpdateCreateBranchHandoff,
    QRFullUpdateQueueAssignmentService,
)
from app.services.queue_domain_service import QueueDomainService


@pytest.mark.unit
def test_qr_create_branch_handoff_builds_boundary_compatible_kwargs() -> None:
    handoff = QRFullUpdateCreateBranchHandoff(
        service_id=17,
        service_name="Lab QR service",
        target_queue_id=22,
        target_queue_tag="lab",
        queue_day=date(2026, 3, 9),
        current_queue_time=datetime(2026, 3, 9, 12, 30, 0),
        create_entry_payload={
            "patient_id": 101,
            "patient_name": "QR Patient",
            "phone": "+998901112233",
            "birth_year": 1990,
            "address": "QR compatibility address",
            "status": "waiting",
            "source": "online",
            "discount_mode": "none",
            "visit_id": None,
            "total_amount": 50000,
            "services": json.dumps(
                [
                    {
                        "service_id": 17,
                        "name": "Lab QR service",
                        "code": "LAB-QR",
                        "quantity": 1,
                        "price": 50000,
                        "queue_time": "2026-03-09T12:30:00",
                        "cancelled": False,
                    }
                ],
                ensure_ascii=False,
            ),
            "service_codes": json.dumps(["LAB-QR"], ensure_ascii=False),
        },
    )
    service = QRFullUpdateQueueAssignmentService(db=None)  # type: ignore[arg-type]

    kwargs = service.build_create_entry_kwargs(handoff, commit=False)

    assert kwargs["queue_id"] == 22
    assert kwargs["patient_id"] == 101
    assert kwargs["birth_year"] == 1990
    assert kwargs["address"] == "QR compatibility address"
    assert kwargs["source"] == "online"
    assert kwargs["status"] == "waiting"
    assert kwargs["queue_time"] == handoff.current_queue_time
    assert json.loads(kwargs["services"])[0]["service_id"] == 17
    assert json.loads(kwargs["service_codes"]) == ["LAB-QR"]
    assert kwargs["commit"] is False


@pytest.mark.unit
def test_queue_domain_create_entry_compatibility_preserves_qr_payload_fields(
    db_session,
    test_doctor,
    test_patient,
) -> None:
    queue = DailyQueue(
        day=date.today(),
        specialist_id=test_doctor.id,
        queue_tag="lab",
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)

    queue_time = datetime(2026, 3, 9, 13, 0, 0)
    service = QueueDomainService(db_session)

    created_entry = service.allocate_ticket(
        allocation_mode="create_entry",
        queue_id=queue.id,
        number=8,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        birth_year=1990,
        address="QR compatibility address",
        source="online",
        status="waiting",
        queue_time=queue_time,
        total_amount=50000,
        services=json.dumps(
            [
                {
                    "service_id": 17,
                    "name": "Lab QR service",
                    "code": "LAB-QR",
                    "quantity": 1,
                    "price": 50000,
                    "queue_time": queue_time.isoformat(),
                    "cancelled": False,
                }
            ],
            ensure_ascii=False,
        ),
        service_codes=json.dumps(["LAB-QR"], ensure_ascii=False),
        session_id="qr-session-101",
        commit=False,
    )

    assert created_entry.queue_id == queue.id
    assert created_entry.number == 8
    assert created_entry.source == "online"
    assert created_entry.status == "waiting"
    assert created_entry.queue_time == queue_time
    assert created_entry.birth_year == 1990
    assert created_entry.address == "QR compatibility address"
    assert created_entry.session_id == "qr-session-101"
    assert json.loads(created_entry.services)[0]["service_id"] == 17
    assert json.loads(created_entry.service_codes) == ["LAB-QR"]
