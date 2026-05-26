from __future__ import annotations

from datetime import date

import pytest

from app.models.online_queue import OnlineQueueEntry
from app.models.visit import Visit, VisitService


@pytest.mark.integration
def test_full_update_all_free_without_visit_id_does_not_reuse_unrelated_visit(
    client,
    db_session,
    registrar_auth_headers,
    test_daily_queue,
    test_patient,
    test_doctor,
    test_service,
):
    unrelated_visit = Visit(
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        visit_date=date.today(),
        visit_time="12:00",
        status="open",
        discount_mode="none",
        approval_status="none",
        department="cardiology",
    )
    db_session.add(unrelated_visit)
    db_session.flush()
    unrelated_service = VisitService(
        visit_id=unrelated_visit.id,
        service_id=test_service.id,
        code=test_service.code,
        name=test_service.name,
        qty=1,
        price=test_service.price,
        currency="UZS",
    )
    entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=77,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        visit_id=None,
        source="online",
        status="waiting",
    )
    db_session.add_all([unrelated_service, entry])
    db_session.commit()
    db_session.refresh(unrelated_visit)
    db_session.refresh(entry)

    response = client.put(
        f"/api/v1/queue/online-entry/{entry.id}/full-update",
        headers=registrar_auth_headers,
        json={
            "patient_data": {
                "patient_name": test_patient.short_name(),
                "phone": test_patient.phone,
                "birth_year": 1990,
                "address": test_patient.address,
            },
            "visit_type": "paid",
            "discount_mode": "none",
            "services": [{"service_id": test_service.id, "quantity": 1}],
            "all_free": True,
        },
    )

    assert response.status_code == 200, response.text

    db_session.refresh(entry)
    db_session.refresh(unrelated_visit)
    assert entry.visit_id is not None
    assert entry.visit_id != unrelated_visit.id
    assert unrelated_visit.discount_mode == "none"
    assert unrelated_visit.approval_status == "none"
    assert unrelated_visit.status == "open"
    assert (
        db_session.query(VisitService)
        .filter(VisitService.visit_id == unrelated_visit.id)
        .count()
        == 1
    )

    linked_visit = db_session.query(Visit).filter(Visit.id == entry.visit_id).one()
    assert linked_visit.discount_mode == "all_free"
    assert linked_visit.approval_status == "pending"
