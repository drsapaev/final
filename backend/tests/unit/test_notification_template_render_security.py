"""Regression tests for template rendering and recipient-bound Telegram delivery.

All provider methods are mocked; no message leaves the test process.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session

from app.db.base_class import Base
from app.models.notification import NotificationHistory, NotificationTemplate
from app.models.patient import Patient
from app.models.telegram_config import TelegramUser
from app.services.notifications_pkg import NotificationSenderService
from app.services.notifications_pkg._templated import crud_notification_history


@pytest.fixture
def db_session():
    """Keep consent scenarios independent of links left in the shared test DB."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def sender():
    service = NotificationSenderService()
    service.send_sms = AsyncMock(return_value=True)
    service.send_email = AsyncMock(return_value=True)
    service.send_telegram = AsyncMock(return_value=True)
    service.platform = SimpleNamespace(record_delivery_for_user=AsyncMock())
    service._platform_service = lambda _db: service.platform
    return service


def add_template(db, channel, body, subject=None):
    db.add(NotificationTemplate(
        name=f"render-security-{channel}",
        type="appointment_reminder",
        channel=channel,
        template=body,
        subject=subject,
        is_active=True,
    ))
    db.commit()


def link_patient(db, patient, **settings):
    values = dict(active=True, blocked=False, notifications_enabled=True,
                  appointment_reminders=True)
    values.update(settings)
    db.add(TelegramUser(patient_id=patient.id, chat_id=123456789, **values))
    db.commit()


def test_direct_render_supports_html_and_plain_formats_with_sandbox(sender):
    data = {"value": "<b>SYNTHETIC</b> & x"}
    template = "{{ value }}|{{ optional }}"
    assert sender.render_template(template, data) == "&lt;b&gt;SYNTHETIC&lt;/b&gt; &amp; x|"
    assert sender.render_template(template, data, html=False) == "<b>SYNTHETIC</b> & x|"
    assert sender.render_template("{{ ''.__class__.__mro__ }}", data, html=False) is None
    assert sender.render_template("{{ ''.__class__.__mro__ }}", data, html=True) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("channel", ["sms", "email", "telegram"])
async def test_template_escaping_matches_delivery_format_and_missing_values(
    db_session, test_patient, sender, channel
):
    add_template(db_session, channel, "{{ value }}|{{ optional }}", "{{ value }}")
    if channel == "telegram":
        link_patient(db_session, test_patient)
    history = await sender.send_templated_notification(
        db=db_session,
        notification_type="appointment_reminder",
        channel=channel,
        recipient_contact="untrusted-contact",
        template_data={"value": "<b>SYNTHETIC</b> & x"},
        recipient_id=test_patient.id if channel == "telegram" else None,
    )
    expected = ("&lt;b&gt;SYNTHETIC&lt;/b&gt; &amp; x" if channel == "telegram"
                else "<b>SYNTHETIC</b> & x")
    assert history.status == "sent"
    assert history.content == expected + "|"
    if channel == "sms":
        sender.send_sms.assert_awaited_once_with("untrusted-contact", expected + "|")
    elif channel == "email":
        sender.send_email.assert_awaited_once_with("untrusted-contact", expected, expected + "|")
    else:
        sender.send_telegram.assert_awaited_once_with(expected + "|", "123456789")


@pytest.mark.asyncio
@pytest.mark.parametrize("field,expression", [
    ("body", "{% if %}PRIVATE_TEMPLATE_MARKER"),
    ("subject", "{% if %}PRIVATE_TEMPLATE_MARKER"),
    ("body", "{{ ''.__class__.__mro__ }}PRIVATE_TEMPLATE_MARKER"),
])
async def test_render_error_does_not_send_or_persist_template_data(
    db_session, admin_user, test_patient, sender, caplog, field, expression
):
    test_patient.user_id = admin_user.id
    add_template(db_session, "email", expression if field == "body" else "safe",
                 expression if field == "subject" else "safe")
    history = await sender.send_templated_notification(
        db=db_session,
        notification_type="appointment_reminder",
        channel="email",
        recipient_contact="synthetic@example.test",
        template_data={"value": "PRIVATE_DATA_MARKER"},
        recipient_id=test_patient.id,
    )
    sender.send_email.assert_not_awaited()
    sender.platform.record_delivery_for_user.assert_not_awaited()
    assert history is not None
    assert history.status == "failed"
    assert not history.content
    assert not history.recipient_contact
    assert history.recipient_id is None
    assert not history.subject
    assert not history.notification_metadata
    persisted = repr((history.content, history.subject, history.error_message,
                      history.notification_metadata))
    assert "PRIVATE_TEMPLATE_MARKER" not in persisted
    assert "PRIVATE_DATA_MARKER" not in persisted
    assert "PRIVATE_TEMPLATE_MARKER" not in caplog.text
    assert "PRIVATE_DATA_MARKER" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["no_id", "wrong_type", "unlinked", "inactive", "blocked", "disabled", "event_disabled"])
async def test_telegram_requires_linked_consenting_patient(
    db_session, test_patient, sender, case
):
    if case not in {"no_id", "wrong_type", "unlinked"}:
        settings = {
            "inactive": {"active": False},
            "blocked": {"blocked": True},
            "disabled": {"notifications_enabled": False},
            "event_disabled": {"appointment_reminders": False},
        }[case]
        link_patient(db_session, test_patient, **settings)
    history = await sender.send_templated_notification(
        db=db_session,
        notification_type="appointment_reminder",
        channel="telegram",
        recipient_contact="attacker-controlled",
        template_data={"message": "SYNTHETIC"},
        recipient_type="doctor" if case == "wrong_type" else "patient",
        recipient_id=None if case == "no_id" else test_patient.id,
    )
    assert history is None
    sender.send_telegram.assert_not_awaited()
    assert db_session.query(NotificationHistory).count() == 0


def test_consent_database_does_not_inherit_an_existing_shared_link(
    test_db, db_session, test_patient
):
    # Reproduce an earlier test leaving a link with the same numeric patient ID.
    # The test's private database must still contain no link for this patient.
    with test_db.connect() as connection:
        transaction = connection.begin()
        try:
            if connection.execute(
                Patient.__table__.select().where(Patient.id == test_patient.id)
            ).first() is None:
                connection.execute(
                    Patient.__table__.insert().values(
                        id=test_patient.id, first_name="Synthetic", last_name="Patient"
                    )
                )
            max_chat_id = connection.execute(
                func.max(TelegramUser.chat_id).select()
            ).scalar_one_or_none() or 0
            connection.execute(
                TelegramUser.__table__.insert().values(
                    patient_id=test_patient.id,
                    chat_id=max_chat_id + 1,
                    active=True,
                    blocked=False,
                    notifications_enabled=True,
                    appointment_reminders=True,
                )
            )
            assert connection.execute(
                TelegramUser.__table__.select().where(
                    TelegramUser.patient_id == test_patient.id,
                    TelegramUser.chat_id == max_chat_id + 1,
                    TelegramUser.active.is_(True),
                    TelegramUser.blocked.is_(False),
                    TelegramUser.notifications_enabled.is_(True),
                )
            ).first() is not None
            assert db_session.query(TelegramUser).filter_by(
                patient_id=test_patient.id
            ).first() is None
        finally:
            transaction.rollback()


@pytest.mark.asyncio
@pytest.mark.parametrize("settings", [
    {"active": False},
    {"blocked": True},
    {"notifications_enabled": False},
])
async def test_telegram_skips_ineligible_link_when_another_link_is_consented(
    db_session, test_patient, sender, settings
):
    link_patient(db_session, test_patient)
    db_session.add(TelegramUser(
        patient_id=test_patient.id,
        chat_id=987654321,
        active=settings.get("active", True),
        blocked=settings.get("blocked", False),
        notifications_enabled=settings.get("notifications_enabled", True),
        appointment_reminders=True,
    ))
    db_session.commit()

    result = await sender.send_templated_notification(
        db=db_session,
        notification_type="appointment_reminder",
        channel="telegram",
        recipient_contact="untrusted-contact",
        template_data={"message": "SYNTHETIC"},
        recipient_id=test_patient.id,
    )

    assert result.status == "sent"
    sender.send_telegram.assert_awaited_once_with("SYNTHETIC", "123456789")


@pytest.mark.asyncio
async def test_telegram_selected_link_category_opt_out_does_not_fallback(
    db_session, test_patient, sender
):
    link_patient(db_session, test_patient)
    db_session.add(TelegramUser(
        patient_id=test_patient.id, chat_id=987654321,
        active=True, blocked=False, notifications_enabled=True,
        appointment_reminders=False,
    ))
    db_session.commit()

    result = await sender.send_templated_notification(
        db=db_session,
        notification_type="appointment_reminder",
        channel="telegram",
        recipient_contact="untrusted-contact",
        template_data={"message": "SYNTHETIC"},
        recipient_id=test_patient.id,
    )

    assert result is None
    sender.send_telegram.assert_not_awaited()


@pytest.mark.asyncio
async def test_telegram_fallback_escapes_data_and_uses_only_bound_chat(
    db_session, test_patient, sender
):
    link_patient(db_session, test_patient)
    history = await sender.send_templated_notification(
        db=db_session,
        notification_type="appointment_reminder",
        channel="telegram",
        recipient_contact="attacker-controlled",
        template_data={"message": "<b>SYNTHETIC</b> & <tag>"},
        recipient_id=test_patient.id,
    )
    assert history.status == "sent"
    sender.send_telegram.assert_awaited_once_with(
        "&lt;b&gt;SYNTHETIC&lt;/b&gt; &amp; &lt;tag&gt;", "123456789"
    )


@pytest.mark.asyncio
async def test_render_failure_is_committed_once_as_failed_without_private_data(
    db_session, sender, monkeypatch
):
    add_template(db_session, "email", "{% if %}PRIVATE_TEMPLATE_MARKER")
    create = Mock(wraps=crud_notification_history.create)
    update_status = Mock(wraps=crud_notification_history.update_status)
    commit = Mock(wraps=db_session.commit)
    monkeypatch.setattr(crud_notification_history, "create", create)
    monkeypatch.setattr(crud_notification_history, "update_status", update_status)
    monkeypatch.setattr(db_session, "commit", commit)

    history = await sender.send_templated_notification(
        db=db_session,
        notification_type="appointment_reminder",
        channel="email",
        recipient_contact="synthetic@example.test",
        template_data={"private": "PRIVATE_DATA_MARKER"},
    )

    create.assert_called_once()
    update_status.assert_not_called()
    commit.assert_called_once()
    created = create.call_args.kwargs["obj_in"]
    assert created.status == history.status == "failed"
    assert created.error_message == history.error_message == "Notification template rendering failed"
    assert created.recipient_contact == ""
    assert created.recipient_id is None
    assert not created.subject and not created.content and not created.notification_metadata
    assert "PRIVATE_TEMPLATE_MARKER" not in repr(created)
    assert "PRIVATE_DATA_MARKER" not in repr(created)
    sender.send_email.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_channel_uses_safe_html_rendering_and_is_not_delivered(
    db_session, sender
):
    add_template(db_session, "future", "{{ value }}")
    history = await sender.send_templated_notification(
        db=db_session,
        notification_type="appointment_reminder",
        channel="future",
        recipient_contact="synthetic",
        template_data={"value": "<b>SYNTHETIC</b> & x"},
    )
    assert history.status == "failed"
    assert history.content == "&lt;b&gt;SYNTHETIC&lt;/b&gt; &amp; x"
    sender.send_sms.assert_not_awaited()
    sender.send_email.assert_not_awaited()
    sender.send_telegram.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type,disabled_field", [
    ("lab_results", "lab_notifications"),
    ("lab_results_ready", "lab_notifications"),
    ("result_ready", "lab_notifications"),
    ("lab_result_ready", "lab_notifications"),
    ("labresultready", "lab_notifications"),
    ("lab_critical_result", "lab_notifications"),
    ("lab_critical", "lab_notifications"),
    ("lab_new_study", "lab_notifications"),
    ("lab_new_assignment", "lab_notifications"),
    ("lab_critical_finding", "lab_notifications"),
    ("lab_result_sent_confirmation", "lab_notifications"),
    ("lab_result_sent", "lab_notifications"),
    ("prescription_ready", "lab_notifications"),
    ("queue_update", "appointment_reminders"),
    ("queue_changed", "appointment_reminders"),
    ("queue_call", "appointment_reminders"),
    ("queue_position", "appointment_reminders"),
    ("queue_reminder", "appointment_reminders"),
    ("queue_ticket_issued", "appointment_reminders"),
    ("queueticketissued", "appointment_reminders"),
    ("queue_status_changed", "appointment_reminders"),
    ("queue_status", "appointment_reminders"),
    ("queuestatuschanged", "appointment_reminders"),
    ("patient_called", "appointment_reminders"),
    ("patientcalled", "appointment_reminders"),
    ("new_appointment", "appointment_reminders"),
    ("appointment_confirmation_task", "appointment_reminders"),
    ("appointment_cancellation", "appointment_reminders"),
    ("appointment_cancelled", "appointment_reminders"),
    ("appointment_rescheduled", "appointment_reminders"),
    ("diagnostics_return_needed", "lab_notifications"),
    ("diagnostics_return_needed", "appointment_reminders"),
    ("diagnostics_return", "lab_notifications"),
    ("diagnostics_return", "appointment_reminders"),
    ("unknown_future_event", "lab_notifications"),
    ("unknown_future_event", "appointment_reminders"),
])
async def test_telegram_event_categories_respect_opt_out(
    db_session, test_patient, sender, event_type, disabled_field
):
    link_patient(db_session, test_patient, **{disabled_field: False})
    result = await sender.send_templated_notification(
        db=db_session,
        notification_type=event_type,
        channel="telegram",
        recipient_contact="untrusted-contact",
        template_data={"message": "SYNTHETIC"},
        recipient_id=test_patient.id,
    )
    assert result is None
    sender.send_telegram.assert_not_awaited()
    assert db_session.query(NotificationHistory).count() == 0


@pytest.mark.asyncio
async def test_unknown_telegram_event_is_delivered_when_all_preferences_allow(
    db_session, test_patient, sender
):
    link_patient(db_session, test_patient, lab_notifications=True)
    result = await sender.send_templated_notification(
        db=db_session,
        notification_type="unknown_future_event",
        channel="telegram",
        recipient_contact="untrusted-contact",
        template_data={"message": "SYNTHETIC"},
        recipient_id=test_patient.id,
    )
    assert result.status == "sent"
    sender.send_telegram.assert_awaited_once_with("SYNTHETIC", "123456789")


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", ["payment_created", "paymentpaid", "payment_success"])
async def test_payment_telegram_uses_global_consent_not_unrelated_categories(
    db_session, test_patient, sender, event_type
):
    link_patient(db_session, test_patient, appointment_reminders=False,
                 lab_notifications=False)
    result = await sender.send_templated_notification(
        db=db_session,
        notification_type=event_type,
        channel="telegram",
        recipient_contact="untrusted-contact",
        template_data={"message": "SYNTHETIC"},
        recipient_id=test_patient.id,
    )
    assert result.status == "sent"
    sender.send_telegram.assert_awaited_once_with("SYNTHETIC", "123456789")


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type,disabled_field", [
    ("lab_new_assignment", "lab_notifications"),
    ("unknown_future_event", "lab_notifications"),
    ("unknown_future_event", "appointment_reminders"),
])
async def test_linked_user_dispatch_respects_event_category_preferences(
    db_session, admin_user, test_patient, sender, event_type, disabled_field
):
    test_patient.user_id = admin_user.id
    link_patient(db_session, test_patient, **{disabled_field: False})
    result = await sender.send_linked_user_telegram_notification(
        db=db_session,
        user_id=admin_user.id,
        event_type=event_type,
        message="SYNTHETIC",
    )
    assert result is False
    sender.send_telegram.assert_not_awaited()
