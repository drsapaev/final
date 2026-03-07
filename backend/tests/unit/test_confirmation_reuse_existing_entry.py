from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.online_queue import OnlineQueueEntry
from app.models.visit import VisitService
from app.services.queue_service import queue_service
from app.services.visit_confirmation_service import (
    VisitConfirmationDomainError,
    VisitConfirmationService,
)


def _attach_visit_service(db_session, visit, service) -> None:
    db_session.add(
        VisitService(
            visit_id=visit.id,
            service_id=service.id,
            code=service.code,
            name=service.name,
            qty=1,
            price=Decimal("100000.00"),
            currency="UZS",
        )
    )
    db_session.commit()


@pytest.mark.unit
@pytest.mark.queue
@pytest.mark.confirmation
def test_assign_queue_numbers_on_confirmation_reuses_existing_entry_without_allocating(
    db_session,
    test_visit,
    test_daily_queue,
    test_service,
    test_patient,
    monkeypatch,
):
    _attach_visit_service(db_session, test_visit, test_service)
    original_queue_time = datetime.utcnow().replace(microsecond=0)

    existing_entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=5,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        source="online",
        status="waiting",
        queue_time=original_queue_time,
    )
    db_session.add(existing_entry)
    db_session.commit()

    def _unexpected_number(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("queue number allocation should not run for reuse path")

    def _unexpected_create(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("create_queue_entry should not run for reuse path")

    monkeypatch.setattr(queue_service, "get_next_queue_number", _unexpected_number)
    monkeypatch.setattr(queue_service, "create_queue_entry", _unexpected_create)

    service = VisitConfirmationService(db_session)
    queue_numbers, print_tickets = service.assign_queue_numbers_on_confirmation(
        test_visit,
        confirmation_telegram_id="123456789",
    )

    db_session.flush()
    db_session.refresh(existing_entry)

    assert queue_numbers == [
        {
            "queue_tag": "cardiology_common",
            "number": 5,
            "queue_id": test_daily_queue.id,
        }
    ]
    assert print_tickets[0]["queue_number"] == 5
    assert existing_entry.visit_id == test_visit.id
    assert existing_entry.queue_time == original_queue_time


@pytest.mark.unit
@pytest.mark.queue
@pytest.mark.confirmation
def test_assign_queue_numbers_on_confirmation_raises_explicit_error_on_ambiguity(
    db_session,
    test_visit,
    test_daily_queue,
    test_service,
    test_patient,
    monkeypatch,
):
    _attach_visit_service(db_session, test_visit, test_service)

    db_session.add(
        OnlineQueueEntry(
            queue_id=test_daily_queue.id,
            number=1,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="online",
            status="waiting",
        )
    )
    db_session.add(
        OnlineQueueEntry(
            queue_id=test_daily_queue.id,
            number=2,
            patient_id=test_patient.id,
            patient_name=test_patient.short_name(),
            phone=test_patient.phone,
            source="desk",
            status="called",
        )
    )
    db_session.commit()

    def _unexpected_number(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("queue number allocation should not run on ambiguity")

    def _unexpected_create(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("create_queue_entry should not run on ambiguity")

    monkeypatch.setattr(queue_service, "get_next_queue_number", _unexpected_number)
    monkeypatch.setattr(queue_service, "create_queue_entry", _unexpected_create)

    service = VisitConfirmationService(db_session)

    with pytest.raises(VisitConfirmationDomainError) as exc_info:
        service.assign_queue_numbers_on_confirmation(
            test_visit,
            confirmation_telegram_id="123456789",
        )

    assert exc_info.value.status_code == 409
    assert "однозначно" in exc_info.value.detail
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.visit_id == test_visit.id)
        .count()
        == 0
    )


@pytest.mark.unit
@pytest.mark.queue
@pytest.mark.confirmation
def test_assign_queue_numbers_on_confirmation_uses_domain_boundary_for_new_entry(
    db_session,
    test_visit,
    test_daily_queue,
    test_service,
    monkeypatch,
):
    _attach_visit_service(db_session, test_visit, test_service)

    boundary_calls: list[dict[str, object]] = []

    def _fake_allocate_ticket(*, allocation_mode="create_entry", **kwargs):  # type: ignore[no-untyped-def]
        boundary_calls.append(
            {
                "allocation_mode": allocation_mode,
                "kwargs": kwargs,
            }
        )
        return SimpleNamespace(
            id=999,
            queue_id=test_daily_queue.id,
            number=4,
            status="waiting",
            source="confirmation",
            queue_time=datetime.utcnow(),
        )

    def _unexpected_direct_create(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("confirmation slice should use queue facade boundary")

    monkeypatch.setattr(queue_service, "get_next_queue_number", lambda *args, **kwargs: 4)
    monkeypatch.setattr(queue_service, "create_queue_entry", _unexpected_direct_create)

    service = VisitConfirmationService(db_session)
    monkeypatch.setattr(service.queue_facade, "allocate_ticket", _fake_allocate_ticket)

    queue_numbers, print_tickets = service.assign_queue_numbers_on_confirmation(
        test_visit,
        confirmation_telegram_id="123456789",
    )

    assert boundary_calls == [
        {
            "allocation_mode": "create_entry",
            "kwargs": {
                "daily_queue": test_daily_queue,
                "patient_id": test_visit.patient_id,
                "visit_id": test_visit.id,
                "number": 4,
                "source": "confirmation",
            },
        }
    ]
    assert queue_numbers == [
        {
            "queue_tag": "cardiology_common",
            "number": 4,
            "queue_id": test_daily_queue.id,
        }
    ]
    assert print_tickets[0]["queue_number"] == 4
