from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.online_queue import OnlineQueueEntry
from app.models.visit import VisitService


def _attach_visit_service(db_session, visit, service) -> None:
    visit_service = VisitService(
        visit_id=visit.id,
        service_id=service.id,
        code=service.code,
        name=service.name,
        qty=1,
        price=Decimal("100000.00"),
        currency="UZS",
    )
    db_session.add(visit_service)
    db_session.commit()


def _queue_entries_for_visit(db_session, visit_id: int) -> list[OnlineQueueEntry]:
    return (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.visit_id == visit_id)
        .order_by(OnlineQueueEntry.number.asc(), OnlineQueueEntry.id.asc())
        .all()
    )


@pytest.mark.integration
@pytest.mark.queue
@pytest.mark.confirmation
def test_confirmation_split_flow_assigns_next_number_and_links_visit(
    client,
    db_session,
    test_visit,
    test_daily_queue,
    test_service,
):
    _attach_visit_service(db_session, test_visit, test_service)

    baseline_entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=1,
        patient_name="Baseline Queue Patient",
        source="online",
        status="waiting",
    )
    db_session.add(baseline_entry)
    db_session.commit()

    response = client.post(
        "/api/v1/telegram/visits/confirm",
        json={
            "token": test_visit.confirmation_token,
            "telegram_user_id": "123456789",
            "telegram_username": "characterization_user",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    entries = _queue_entries_for_visit(db_session, test_visit.id)
    assert len(entries) == 1

    created_entry = entries[0]
    assert created_entry.queue_id == test_daily_queue.id
    assert created_entry.number == 2
    assert created_entry.status == "waiting"
    assert created_entry.source == "confirmation"
    assert created_entry.patient_id == test_visit.patient_id
    assert created_entry.queue_time is not None

    assert payload["status"] == "open"
    assert payload["queue_numbers"] == [
        {
            "queue_tag": "cardiology_common",
            "number": 2,
            "queue_id": test_daily_queue.id,
        }
    ]


@pytest.mark.integration
@pytest.mark.queue
@pytest.mark.confirmation
def test_confirmation_split_flow_replay_returns_error_and_keeps_single_queue_row(
    client,
    db_session,
    test_visit,
    test_daily_queue,
    test_service,
):
    _attach_visit_service(db_session, test_visit, test_service)

    first_response = client.post(
        "/api/v1/telegram/visits/confirm",
        json={
            "token": test_visit.confirmation_token,
            "telegram_user_id": "123456789",
        },
    )
    assert first_response.status_code == 200

    second_response = client.post(
        "/api/v1/telegram/visits/confirm",
        json={
            "token": test_visit.confirmation_token,
            "telegram_user_id": "123456789",
        },
    )

    assert second_response.status_code == 400
    assert "Визит уже имеет статус" in second_response.json()["detail"]

    entries = _queue_entries_for_visit(db_session, test_visit.id)
    assert len(entries) == 1
    assert entries[0].source == "confirmation"
    assert entries[0].status == "waiting"


@pytest.mark.integration
@pytest.mark.queue
@pytest.mark.confirmation
def test_confirmation_split_flow_with_existing_active_entry_creates_second_active_row(
    client,
    db_session,
    test_visit,
    test_daily_queue,
    test_service,
    test_patient,
):
    _attach_visit_service(db_session, test_visit, test_service)

    existing_active_entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=1,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        source="online",
        status="waiting",
    )
    db_session.add(existing_active_entry)
    db_session.commit()

    response = client.post(
        "/api/v1/telegram/visits/confirm",
        json={
            "token": test_visit.confirmation_token,
            "telegram_user_id": "123456789",
        },
    )

    assert response.status_code == 200

    same_patient_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.queue_id == test_daily_queue.id,
            OnlineQueueEntry.patient_id == test_patient.id,
            OnlineQueueEntry.status == "waiting",
        )
        .order_by(OnlineQueueEntry.number.asc())
        .all()
    )

    assert [entry.number for entry in same_patient_entries] == [1, 2]
    assert [entry.source for entry in same_patient_entries] == ["online", "confirmation"]
    assert same_patient_entries[1].visit_id == test_visit.id


@pytest.mark.integration
@pytest.mark.queue
@pytest.mark.confirmation
def test_confirmation_split_flow_registrar_bridge_creates_confirmation_source_entry(
    client,
    db_session,
    test_visit,
    test_daily_queue,
    test_service,
    registrar_auth_headers,
):
    _attach_visit_service(db_session, test_visit, test_service)

    response = client.post(
        f"/api/v1/registrar/visits/{test_visit.id}/confirm",
        headers=registrar_auth_headers,
        json={
            "confirmation_method": "manual",
            "confirmed_by": "registrar_test",
            "notes": "characterization",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    entries = _queue_entries_for_visit(db_session, test_visit.id)
    assert len(entries) == 1
    assert entries[0].queue_id == test_daily_queue.id
    assert entries[0].source == "confirmation"
    assert entries[0].status == "waiting"
    assert entries[0].visit_id == test_visit.id

    assert payload["status"] == "open"
    assert payload["queue_numbers"]["cardiology_common"]["number"] == entries[0].number
