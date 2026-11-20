from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.api.v1.endpoints.registrar_wizard._visits import _clinic_today
from app.models.online_queue import OnlineQueueEntry
from app.models.telegram_config import TelegramUser
from app.models.visit import VisitService
from app.services.visit_confirmation_service import (
    VisitConfirmationDomainError,
    VisitConfirmationService,
    build_telegram_visit_action_token,
)


@pytest.fixture(autouse=True)
def _future_telegram_start(monkeypatch):
    # These queue tests pin the clinic's current day; the time policy has
    # dedicated tests and must not make the fixture depend on wall clock.
    monkeypatch.setattr("app.tasks.worker._appointment_start_utc", lambda visit: datetime.now(UTC) + timedelta(days=1))


def _capability(visit, link, token=None):
    return build_telegram_visit_action_token(
        visit_id=visit.id, confirmation_token=token or visit.confirmation_token,
        link_id=link.id, chat_id=link.chat_id, patient_id=visit.patient_id,
        link_epoch=link.patient_link_epoch, visit_context_epoch=visit.confirmation_context_epoch,
    )


def _linked_confirmation(db_session, visit):
    """Exercise the service using the actor supplied by a trusted callback."""
    link = db_session.query(TelegramUser).filter_by(chat_id=123456789).first()
    if link is None:
        link = TelegramUser(chat_id=123456789)
        db_session.add(link)
    link.patient_id = visit.patient_id
    link.active = True
    link.blocked = False
    link.notifications_enabled = True
    link.appointment_reminders = True
    visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
    db_session.commit()
    return VisitConfirmationService(db_session).confirm_by_telegram(
        token=_capability(visit, link),
        telegram_user_id="123456789",
        source_ip=None,
        user_agent="telegram",
    )


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

    # SSOT: приводим дату визита и очереди к дню КЛИНИКИ (не host-UTC),
    # иначе при confirm в окне 19:00-24:00 UTC активация не сработает
    clinic_day = _clinic_today(db_session)
    test_visit.visit_date = clinic_day
    test_daily_queue.day = clinic_day
    db_session.add_all([test_visit, test_daily_queue])
    db_session.commit()

    baseline_entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=1,
        patient_name="Baseline Queue Patient",
        source="online",
        status="waiting",
    )
    db_session.add(baseline_entry)
    db_session.commit()

    payload = _linked_confirmation(db_session, test_visit)

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

    # SSOT: приводим дату визита и очереди к дню КЛИНИКИ (не host-UTC),
    # иначе при confirm в окне 19:00-24:00 UTC активация не сработает
    clinic_day = _clinic_today(db_session)
    test_visit.visit_date = clinic_day
    test_daily_queue.day = clinic_day
    db_session.add_all([test_visit, test_daily_queue])
    db_session.commit()

    token = test_visit.confirmation_token
    assert _linked_confirmation(db_session, test_visit)["success"] is True
    link = db_session.query(TelegramUser).filter_by(chat_id=123456789).one()
    capability = _capability(test_visit, link, token)
    with pytest.raises(VisitConfirmationDomainError) as exc:
        VisitConfirmationService(db_session).confirm_by_telegram(
            token=capability, telegram_user_id="123456789",
            source_ip=None, user_agent="telegram",
        )
    assert 400 <= exc.value.status_code < 500

    entries = _queue_entries_for_visit(db_session, test_visit.id)
    assert len(entries) == 1
    assert entries[0].source == "confirmation"
    assert entries[0].status == "waiting"


@pytest.mark.integration
@pytest.mark.queue
@pytest.mark.confirmation
def test_confirmation_split_flow_with_existing_active_entry_reuses_active_row(
    client,
    db_session,
    test_visit,
    test_daily_queue,
    test_service,
    test_patient,
):
    _attach_visit_service(db_session, test_visit, test_service)

    # SSOT: приводим дату визита и очереди к дню КЛИНИКИ (не host-UTC),
    # иначе при confirm в окне 19:00-24:00 UTC активация не сработает
    clinic_day = _clinic_today(db_session)
    test_visit.visit_date = clinic_day
    test_daily_queue.day = clinic_day
    db_session.add_all([test_visit, test_daily_queue])
    db_session.commit()

    original_queue_time = datetime.utcnow().replace(microsecond=0)

    existing_active_entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=3,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        source="online",
        status="waiting",
        queue_time=original_queue_time,
    )
    db_session.add(existing_active_entry)
    db_session.commit()

    payload = _linked_confirmation(db_session, test_visit)

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

    db_session.refresh(existing_active_entry)
    assert len(same_patient_entries) == 1
    assert same_patient_entries[0].id == existing_active_entry.id
    assert same_patient_entries[0].number == 3
    assert same_patient_entries[0].visit_id == test_visit.id
    assert same_patient_entries[0].queue_time == original_queue_time
    assert payload["queue_numbers"][0]["number"] == 3


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

    # SSOT: приводим дату визита и очереди к дню КЛИНИКИ (не host-UTC),
    # иначе при confirm в окне 19:00-24:00 UTC активация не сработает
    clinic_day = _clinic_today(db_session)
    test_visit.visit_date = clinic_day
    test_daily_queue.day = clinic_day
    db_session.add_all([test_visit, test_daily_queue])
    db_session.commit()

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
