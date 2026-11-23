"""Actor-bound visit actions: no real Telegram traffic or production data."""

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.models.telegram_config import TelegramUser
from app.models.visit import Visit, VisitService
from app.services.visit_confirmation_service import (
    VisitConfirmationDomainError,
    VisitConfirmationService,
    build_telegram_visit_action_token,
)


@pytest.fixture
def telegram_visit(db_session, test_visit):
    # Keep the identity explicit: callback actor and chat are equal in a
    # private Telegram chat, and the database link owns this patient's visit.
    test_visit.confirmation_token = "SYNTHETIC-visit-actor-token"
    test_visit.confirmation_channel = "telegram"
    test_visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
    test_visit.status = "pending_confirmation"
    test_visit.visit_date = (datetime.now(UTC) + timedelta(days=3)).date()
    test_visit.visit_time = "10:00"
    link = TelegramUser(chat_id=740610001, patient_id=test_visit.patient_id,
                        active=True, blocked=False)
    db_session.add(link)
    db_session.commit()
    return test_visit, link


def _capability(visit, link):
    return build_telegram_visit_action_token(
        visit_id=visit.id, confirmation_token=visit.confirmation_token,
        link_id=link.id, chat_id=link.chat_id, patient_id=visit.patient_id,
        link_epoch=link.patient_link_epoch, visit_context_epoch=visit.confirmation_context_epoch,
    )


def _view_capability(visit, link):
    return build_telegram_visit_action_token(
        visit_id=visit.id, confirmation_token=visit.confirmation_token,
        link_id=link.id, chat_id=link.chat_id, patient_id=visit.patient_id,
        link_epoch=link.patient_link_epoch, visit_context_epoch=visit.confirmation_context_epoch, purpose="view",
    )


def test_view_disambiguates_visits_and_action_requires_preview(db_session, telegram_visit):
    visit, link = telegram_visit
    visit.visit_time = "09:30"
    other = Visit(patient_id=visit.patient_id, doctor_id=visit.doctor_id,
                  visit_date=visit.visit_date, visit_time="09:30",
                  status="pending_confirmation", confirmation_channel="telegram",
                  confirmation_token="SYNTHETIC-second-visit-token",
                  confirmation_expires_at=datetime.now(UTC) + timedelta(hours=1))
    db_session.add(other)
    db_session.flush()
    db_session.add_all([
        VisitService(visit_id=visit.id, service_id=1, name="УЗИ"),
        VisitService(visit_id=other.id, service_id=2, name="ЭКГ"),
    ])
    db_session.commit()
    service = VisitConfirmationService(db_session)
    view_token = _view_capability(visit, link)
    with pytest.raises(VisitConfirmationDomainError):
        service.cancel_by_telegram(token=view_token, telegram_user_id=str(link.chat_id), source_ip=None, user_agent="telegram")
    first = service.preview_by_telegram(token=view_token, telegram_user_id=str(link.chat_id))
    second = service.preview_by_telegram(token=_view_capability(other, link), telegram_user_id=str(link.chat_id))
    assert "09:30" in first["text"] and "09:30" in second["text"]
    assert f"№{visit.id}" in first["text"] and "УЗИ" in first["text"]
    assert f"№{other.id}" in second["text"] and "ЭКГ" in second["text"]
    assert first["action_token"] != second["action_token"]
    service.cancel_by_telegram(token=second["action_token"], telegram_user_id=str(link.chat_id), source_ip=None, user_agent="telegram")
    db_session.refresh(visit)
    db_session.refresh(other)
    assert visit.status == "pending_confirmation" and other.status == "canceled"


def test_preview_refuses_revoked_link_and_wrong_actor(db_session, telegram_visit):
    visit, link = telegram_visit
    token = _view_capability(visit, link)
    service = VisitConfirmationService(db_session)
    with pytest.raises(VisitConfirmationDomainError):
        service.preview_by_telegram(token=token, telegram_user_id="740610002")
    db_session.rollback()
    link.notifications_enabled = False
    db_session.commit()
    with pytest.raises(VisitConfirmationDomainError):
        service.preview_by_telegram(token=token, telegram_user_id=str(link.chat_id))


@pytest.mark.parametrize("state", ["past_day", "started_today", "missing_date", "missing_time", "bad_time"])
@pytest.mark.parametrize("operation", ["view", "confirm", "cancel"])
def test_telegram_never_operates_on_started_or_incomplete_visit(db_session, telegram_visit, state, operation):
    from app.tasks.worker import _clinic_timezone

    visit, link = telegram_visit
    now = datetime.now(UTC).astimezone(_clinic_timezone())
    if state == "past_day":
        visit.visit_date, visit.visit_time = (now - timedelta(days=1)).date(), "10:00"
    elif state == "started_today":
        past = now - timedelta(minutes=2)
        visit.visit_date, visit.visit_time = past.date(), past.strftime("%H:%M")
    elif state == "missing_date":
        visit.visit_date = None
    elif state == "missing_time":
        visit.visit_date = now.date()
        visit.visit_time = None
    else:
        visit.visit_time = "25:70"
    db_session.commit()
    service = VisitConfirmationService(db_session)
    token = _view_capability(visit, link) if operation == "view" else _capability(visit, link)
    with pytest.raises(VisitConfirmationDomainError):
        if operation == "view":
            service.preview_by_telegram(token=token, telegram_user_id=str(link.chat_id))
        else:
            getattr(service, f"{operation}_by_telegram")(
                token=token, telegram_user_id=str(link.chat_id), source_ip=None, user_agent="telegram")


def test_visit_context_epoch_change_invalidates_view_and_action(db_session, telegram_visit):
    visit, link = telegram_visit
    view, action = _view_capability(visit, link), _capability(visit, link)
    visit.confirmation_context_epoch += 1
    db_session.commit()
    service = VisitConfirmationService(db_session)
    with pytest.raises(VisitConfirmationDomainError):
        service.preview_by_telegram(token=view, telegram_user_id=str(link.chat_id))
    with pytest.raises(VisitConfirmationDomainError):
        service.confirm_by_telegram(token=action, telegram_user_id=str(link.chat_id), source_ip=None, user_agent="telegram")


@pytest.mark.parametrize("operation", ["confirm", "cancel"])
def test_public_claimed_actor_cannot_change_visit(client, db_session, telegram_visit, operation):
    visit, link = telegram_visit
    response = client.post(
        f"/api/v1/telegram/visits/{operation}",
        json={"token": _capability(visit, link), "telegram_user_id": str(link.chat_id)},
    )
    assert response.status_code == 403
    assert response.headers["cache-control"] == "private, no-store"
    assert str(visit.id) not in response.text
    db_session.refresh(visit)
    assert visit.status == "pending_confirmation"
    assert visit.confirmation_token == "SYNTHETIC-visit-actor-token"


@pytest.mark.parametrize("operation", ["confirm", "cancel"])
@pytest.mark.parametrize("failure", ["wrong_actor", "unlinked", "blocked", "inactive", "expired", "missing_expiry", "wrong_channel"])
def test_untrusted_or_stale_invitation_never_mutates_visit(db_session, telegram_visit, operation, failure):
    visit, link = telegram_visit
    actor = str(link.chat_id)
    capability = _capability(visit, link)
    if failure == "wrong_actor":
        actor = "740610002"
    elif failure == "unlinked":
        link.patient_id = None
    elif failure == "blocked":
        link.blocked = True
    elif failure == "inactive":
        link.active = False
    elif failure == "expired":
        visit.confirmation_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    elif failure == "missing_expiry":
        visit.confirmation_expires_at = None
    else:
        visit.confirmation_channel = "pwa"
    db_session.commit()
    service = VisitConfirmationService(db_session)
    with pytest.raises(VisitConfirmationDomainError) as raised:
        getattr(service, f"{operation}_by_telegram")(
            token=capability, telegram_user_id=actor,
            source_ip=None, user_agent="telegram",
        )
    assert raised.value.status_code in (400, 403, 404)
    db_session.refresh(visit)
    assert visit.status == "pending_confirmation"
    assert visit.confirmation_token == "SYNTHETIC-visit-actor-token"


@pytest.mark.parametrize("operation", ["confirm", "cancel"])
def test_trusted_linked_actor_succeeds_once(db_session, telegram_visit, operation):
    visit, link = telegram_visit
    service = VisitConfirmationService(db_session)
    result = getattr(service, f"{operation}_by_telegram")(
        token=_capability(visit, link), telegram_user_id=str(link.chat_id),
        source_ip=None, user_agent="telegram",
    )
    assert result["success"] is True
    db_session.refresh(visit)
    assert visit.status in ({"confirmed", "open"} if operation == "confirm" else {"canceled"})
    if operation == "cancel":
        assert visit.confirmation_token is None
        assert visit.confirmation_expires_at is None


@pytest.mark.parametrize("operation", ["confirm", "cancel"])
def test_internal_errors_do_not_expose_or_audit_exception(
    db_session, telegram_visit, monkeypatch, caplog, operation
):
    visit, link = telegram_visit
    service = VisitConfirmationService(db_session)
    record = Mock(wraps=service.security_service.record_confirmation_attempt)
    monkeypatch.setattr(service.security_service, "record_confirmation_attempt", record)

    def failure(*args, **kwargs):
        raise RuntimeError("SYNTHETIC-SECRET-AND-CLINICAL-MARKER")

    if operation == "confirm":
        monkeypatch.setattr(service, "_confirm_visit", failure)
    else:
        monkeypatch.setattr("app.services.visit_lifecycle_service.VisitLifecycleService.cancel_visit", failure)
    with pytest.raises(VisitConfirmationDomainError) as raised:
        getattr(service, f"{operation}_by_telegram")(
            token=_capability(visit, link), telegram_user_id=str(link.chat_id),
            source_ip=None, user_agent="telegram",
        )
    assert raised.value.status_code == 500
    assert "SYNTHETIC-SECRET-AND-CLINICAL-MARKER" not in raised.value.detail
    assert "SYNTHETIC-SECRET-AND-CLINICAL-MARKER" not in caplog.text
    assert "SYNTHETIC-SECRET-AND-CLINICAL-MARKER" not in repr(record.call_args_list)


def test_telegram_capability_is_distinct_from_pwa_bearer(client, db_session, telegram_visit):
    visit, link = telegram_visit
    visit.confirmation_channel = "auto"
    db_session.commit()
    raw_pwa_token = visit.confirmation_token
    capability = _capability(visit, link)
    assert capability != raw_pwa_token
    assert raw_pwa_token not in capability
    assert len(f"confirm_visit:{capability}".encode()) <= 64
    info = client.post("/api/v1/visits/info", json={"token": capability})
    confirm = client.post("/api/v1/patient/visits/confirm", json={"token": capability})
    assert info.status_code == 404
    assert confirm.status_code == 404
    assert client.post("/api/v1/visits/info", json={"token": raw_pwa_token}).status_code == 200
    db_session.refresh(visit)
    assert visit.status == "pending_confirmation"


def test_real_patient_phone_update_revokes_pwa_link(client, db_session, auth_headers, telegram_visit):
    """Exercise the actual 0102 phone trigger through the public patient API."""
    from sqlalchemy import text

    path = Path(__file__).resolve().parents[2] / "alembic/versions/0102_visit_confirmation_context.py"
    spec = importlib.util.spec_from_file_location("test_phone_http_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    class PhoneTriggerOnly:
        def add_column(self, *args, **kwargs):
            pass
        def get_context(self):
            return SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
        def execute(self, sql):
            if "CREATE TRIGGER trg_patient_phone_confirmation_context" in str(sql):
                db_session.execute(text(str(sql)))

    migration.op = PhoneTriggerOnly()
    migration.upgrade()
    try:
        visit, _ = telegram_visit
        patient = visit.patient
        patient.phone = "+998900000001"
        db_session.commit()
        # Phone update has fenced any prior token; issue a fresh one.
        visit.confirmation_channel = "auto"
        visit.confirmation_token = "SYNTHETIC-phone-http-bearer"
        visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
        db_session.commit()
        raw_token = visit.confirmation_token
        assert client.post("/api/v1/visits/info", json={"token": raw_token}).status_code == 200
        response = client.put(f"/api/v1/patients/{patient.id}", headers=auth_headers,
                              json={"phone": "+998900000002"})
        assert response.status_code == 200, response.text
        assert client.post("/api/v1/visits/info", json={"token": raw_token}).status_code == 404
        db_session.expire_all()
        assert db_session.get(Visit, visit.id).confirmation_token is None
    finally:
        db_session.execute(text("DROP TRIGGER IF EXISTS trg_patient_phone_confirmation_context"))


@pytest.mark.parametrize("operation", ["confirm", "cancel"])
def test_capability_cannot_move_between_two_linked_chats(db_session, telegram_visit, operation):
    visit, link = telegram_visit
    other = TelegramUser(chat_id=740610003, patient_id=visit.patient_id,
                         active=True, blocked=False)
    db_session.add(other)
    db_session.commit()
    capability = _capability(visit, link)
    with pytest.raises(VisitConfirmationDomainError):
        getattr(VisitConfirmationService(db_session), f"{operation}_by_telegram")(
            token=capability, telegram_user_id=str(other.chat_id),
            source_ip=None, user_agent="telegram",
        )
    db_session.refresh(visit)
    assert visit.status == "pending_confirmation"


@pytest.mark.parametrize("field", ["active", "blocked", "notifications_enabled", "appointment_reminders", "patient_id"])
def test_revoked_then_restored_link_never_revives_old_capability(db_session, telegram_visit, field):
    visit, link = telegram_visit
    capability = _capability(visit, link)
    old_value = getattr(link, field)
    setattr(link, field, None if field == "patient_id" else not old_value)
    db_session.commit()
    setattr(link, field, old_value)
    db_session.commit()
    with pytest.raises(VisitConfirmationDomainError):
        VisitConfirmationService(db_session).cancel_by_telegram(
            token=capability, telegram_user_id=str(link.chat_id),
            source_ip=None, user_agent="telegram",
        )
    db_session.refresh(visit)
    assert visit.status == "pending_confirmation"
