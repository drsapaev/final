"""HTTP/DB checks for clinical Telegram sends; the transport is never contacted."""
import secrets
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints import telegram_notifications as api
from app.models.lab import (
    LabReportInstance,
    LabReportTemplate,
    LabReportTemplateVersion,
)
from app.models.payment import Payment
from app.models.telegram_config import TelegramConfig
from app.services.lab_report_pdf_service import lab_report_pdf_service
from app.services.lab_reporting import LabReportingService
from tests.integration.test_telegram_delivery_authorization import telegram_case  # noqa: F401


@pytest.fixture
def delivery(db_session, telegram_case, monkeypatch, admin_auth_headers):
    c = telegram_case
    template = LabReportTemplate(code='SYN-' + secrets.token_hex(8), name='Synthetic', family='lab')
    db_session.add(template)
    db_session.flush()
    version = LabReportTemplateVersion(template_id=template.id, version_no=1, layout_preset='a4')
    db_session.add(version)
    db_session.flush()
    report = LabReportInstance(order_id=c.result.order_id, visit_id=c.visit.id, patient_id=c.patient.id,
                               template_id=template.id, template_version_id=version.id, status='FINALIZED')
    payment = Payment(visit_id=c.visit.id, amount=Decimal('123.45'), currency='UZS',
                      method='cash', status='paid', paid_at=datetime.now(UTC))
    db_session.add_all([report, payment])
    db_session.commit()
    bot = SimpleNamespace(active=True, _send_message=AsyncMock(return_value=True),
                          _send_document=AsyncMock(return_value=(True, 1, None)))
    monkeypatch.setattr(api, '_fresh_bot', AsyncMock(return_value=bot))
    monkeypatch.setattr(LabReportingService, 'materialize_instance', lambda *_: [])
    monkeypatch.setattr(LabReportingService, 'summarize_critical_findings', lambda *_: [])
    monkeypatch.setattr(lab_report_pdf_service, 'render_report', lambda *_: b'%PDF-synthetic')
    return SimpleNamespace(c=c, report=report, payment=payment, bot=bot, admin=admin_auth_headers)


def send(client, d, kind, *, patient_id=None, body=None):
    c = d.c
    patient_id = patient_id or c.patient.id
    if kind == 'appointment':
        return client.post('/api/v1/telegram/send-appointment-reminder', headers=c.headers,
                           params={'appointment_id': c.appointment.id})
    if kind == 'lab':
        return client.post('/api/v1/telegram/send-lab-results', headers=c.headers,
                           params={'patient_id': patient_id}, json=body or [c.result.id])
    if kind == 'pdf':
        return client.post('/api/v1/telegram/send-lab-report-instance', headers=c.headers,
                           json={'patient_id': patient_id, 'report_instance_id': d.report.id})
    return client.post('/api/v1/telegram/send-payment-confirmation', headers=d.admin,
                       params={'patient_id': patient_id},
                       json=body if body is not None else {'payment_id': d.payment.id, 'amount': 999999})


def assert_not_sent(d):
    d.bot._send_message.assert_not_awaited()
    d.bot._send_document.assert_not_awaited()


@pytest.mark.parametrize('kind', ['appointment', 'lab', 'pdf', 'payment'])
def test_delivers_only_to_linked_private_chat(client, delivery, kind):
    d = delivery
    response = send(client, d, kind)
    assert response.status_code == 200, response.text
    assert response.json()['success'] is True
    mock = d.bot._send_document if kind == 'pdf' else d.bot._send_message
    assert mock.await_args.kwargs['chat_id'] == d.c.link.chat_id
    assert str(d.c.link.chat_id) not in response.text and d.c.patient.phone not in response.text
    if kind == 'pdf':
        assert mock.await_args.kwargs['document_bytes'] == b'%PDF-synthetic'
    if kind == 'payment':
        assert '123.45' in mock.await_args.kwargs['text']
        assert '999999' not in mock.await_args.kwargs['text']


@pytest.mark.parametrize('kind', ['appointment', 'lab', 'pdf', 'payment'])
@pytest.mark.parametrize('field,value', [('chat_id', -100123456), ('chat_id', 0),
                                         ('active', False), ('blocked', True),
                                         ('notifications_enabled', False)])
def test_non_private_inactive_blocked_or_unconsented_link_never_receives(client, db_session, delivery, kind, field, value):
    setattr(delivery.c.link, field, value)
    db_session.commit()
    response = send(client, delivery, kind)
    assert response.status_code in (200, 404), response.text
    if response.status_code == 200:
        assert response.json()['success'] is False
    assert_not_sent(delivery)


@pytest.mark.parametrize('kind', ['appointment', 'lab', 'pdf'])
def test_category_opt_out_prevents_delivery(client, db_session, delivery, kind):
    setattr(delivery.c.link, 'appointment_reminders' if kind == 'appointment' else 'lab_notifications', False)
    db_session.commit()
    response = send(client, delivery, kind)
    assert response.status_code in (200, 404), response.text
    if response.status_code == 200:
        assert response.json()['success'] is False
    assert_not_sent(delivery)


@pytest.mark.parametrize('kind', ['appointment', 'lab', 'pdf'])
def test_doctor_must_be_assigned_to_actual_visit_or_appointment(client, db_session, delivery, kind):
    delivery.c.appointment.doctor_id = None
    delivery.c.visit.doctor_id = None
    db_session.commit()
    response = send(client, delivery, kind)
    assert response.status_code in (403, 404), response.text
    assert_not_sent(delivery)


@pytest.mark.parametrize('kind', ['lab', 'pdf', 'payment'])
def test_other_patient_cannot_receive_resource(client, delivery, kind):
    response = send(client, delivery, kind, patient_id=delivery.c.other.id)
    assert response.status_code in (403, 404, 409), response.text
    assert_not_sent(delivery)


@pytest.mark.parametrize('kind', ['appointment', 'lab', 'pdf', 'payment'])
def test_rechecks_consent_after_awaited_bot_setup(client, db_session, delivery, monkeypatch, kind):
    d = delivery
    async def revoke(_db):
        d.c.link.notifications_enabled = False
        db_session.commit()
        return d.bot
    monkeypatch.setattr(api, '_fresh_bot', revoke)
    response = send(client, d, kind)
    assert response.status_code in (403, 404, 409), response.text
    assert_not_sent(d)


def test_payment_requires_paid_record_and_ignores_caller_fields(client, delivery):
    d = delivery
    missing = send(client, d, 'payment', body={'amount': 100, 'patient_name': 'FORGED'})
    assert missing.status_code == 400
    assert_not_sent(d)
    response = send(client, d, 'payment', body={'payment_id': d.payment.id, 'amount': 999999,
                    'patient_name': 'FORGED', 'transaction_id': 'SECRET'})
    assert response.status_code == 200, response.text
    text = d.bot._send_message.await_args.kwargs['text']
    assert all(value not in text for value in ('999999', 'FORGED', 'SECRET'))


def test_report_must_be_finalized_and_transport_failure_is_reported(client, db_session, delivery):
    d = delivery
    d.report.status = 'DRAFT'
    db_session.commit()
    response = send(client, d, 'pdf')
    assert response.status_code == 409
    assert_not_sent(d)
    d.report.status = 'FINALIZED'
    db_session.commit()
    d.bot._send_document.return_value = (False, None, 'synthetic error')
    response = send(client, d, 'pdf')
    assert response.status_code == 500
    assert 'synthetic error' not in response.text


@pytest.mark.parametrize('kind', ['appointment', 'lab', 'pdf', 'payment'])
def test_disabled_bot_configuration_blocks_even_cached_active_service(client, db_session, delivery, kind):
    db_session.add(TelegramConfig(active=False))
    db_session.commit()
    response = send(client, delivery, kind)
    assert response.status_code == 503, response.text
    assert_not_sent(delivery)


@pytest.mark.parametrize('linked', [True, False])
def test_report_authorization_precedes_link_state(client, db_session, delivery, linked):
    d = delivery
    d.c.other_link.active = linked
    db_session.commit()
    foreign = send(client, d, 'pdf', patient_id=d.c.other.id)
    missing = client.post('/api/v1/telegram/send-lab-report-instance', headers=d.c.headers,
                          json={'patient_id': d.c.other.id, 'report_instance_id': 99999999})
    assert foreign.status_code == 409, foreign.text
    assert missing.status_code == 404, missing.text
    assert_not_sent(d)


def test_past_appointment_is_not_sent(client, db_session, delivery):
    from datetime import date
    delivery.c.appointment.appointment_date = date(2000, 1, 1)
    db_session.commit()
    response = send(client, delivery, 'appointment')
    assert response.status_code in (404, 409), response.text
    assert_not_sent(delivery)


@pytest.mark.parametrize('kind', ['appointment', 'lab', 'pdf', 'payment'])
def test_enabled_bot_config_allows_delivery(client, db_session, delivery, kind):
    db_session.add(TelegramConfig(active=True))
    db_session.commit()
    response = send(client, delivery, kind)
    assert response.status_code == 200 and response.json()['success'], response.text


@pytest.mark.parametrize('kind', ['appointment', 'lab', 'pdf', 'payment'])
def test_provider_failure_is_not_success_and_hides_error(client, delivery, kind):
    if kind == 'pdf':
        delivery.bot._send_document.return_value = (False, None, 'SYNTHETIC SECRET')
    else:
        delivery.bot._send_message.return_value = False
    response = send(client, delivery, kind)
    assert response.status_code in (500, 502), response.text
    assert 'SYNTHETIC SECRET' not in response.text
    assert delivery.c.patient.phone not in response.text


def test_lab_message_contains_no_raw_result_or_identifiers(client, delivery):
    response = send(client, delivery, 'lab')
    assert response.status_code == 200, response.text
    message = delivery.bot._send_message.await_args.kwargs['text']
    assert 'SYNTHETIC LAB' not in message
    assert delivery.c.patient.phone not in message
    assert delivery.c.patient.phone not in response.text


@pytest.mark.parametrize('linked', [True, False])
def test_unassigned_doctor_cannot_probe_report_link_state(client, db_session, delivery, linked):
    delivery.c.visit.doctor_id = None
    delivery.c.link.active = linked
    db_session.commit()
    response = send(client, delivery, 'pdf')
    assert response.status_code == 403, response.text
    assert_not_sent(delivery)


@pytest.mark.parametrize('payment_status,refunded_amount', [
    ('pending', None), ('failed', None), ('refunded', None), ('paid', Decimal('0.01')),
])
def test_payment_ineligible_state_never_sends(client, db_session, delivery, payment_status, refunded_amount):
    delivery.payment.status = payment_status
    delivery.payment.refunded_amount = refunded_amount
    db_session.commit()
    response = send(client, delivery, 'payment')
    assert response.status_code == 409, response.text
    assert_not_sent(delivery)


@pytest.mark.parametrize('payment_status', ['paid', 'completed'])
def test_paid_or_completed_payment_sends(client, db_session, delivery, payment_status):
    delivery.payment.status = payment_status
    db_session.commit()
    response = send(client, delivery, 'payment')
    assert response.status_code == 200, response.text
    assert response.json()['success'] is True
    delivery.bot._send_message.assert_awaited_once()


def test_selected_report_and_template_are_rendered_and_delivered(client, db_session, delivery, monkeypatch):
    d = delivery
    other_template = LabReportTemplate(code='SYN-' + secrets.token_hex(8), name='Selected template', family='lab')
    db_session.add(other_template)
    db_session.flush()
    other_version = LabReportTemplateVersion(template_id=other_template.id, version_no=1,
                                             layout_preset='selected-layout', page_settings={'size': 'A4'})
    db_session.add(other_version)
    db_session.flush()
    selected = LabReportInstance(order_id=d.c.result.order_id, visit_id=d.c.visit.id,
        patient_id=d.c.patient.id, template_id=other_template.id, template_version_id=other_version.id,
        patient_snapshot={'name': 'SYNTHETIC SELECTED'}, status='FINALIZED')
    assert d.report.patient_snapshot != selected.patient_snapshot
    db_session.add(selected)
    db_session.commit()
    rendered = []
    materialized = []
    def materialize(_service, instance):
        materialized.append(instance.id)
        return [{'key': 'selected-section' if instance.id == selected.id else 'other-section'}]
    def render(payload):
        rendered.append(payload)
        return b'%PDF-selected' if payload['template_name'] == 'Selected template' else b'%PDF-other'
    monkeypatch.setattr(LabReportingService, 'materialize_instance', materialize)
    monkeypatch.setattr(lab_report_pdf_service, 'render_report', render)
    response = client.post('/api/v1/telegram/send-lab-report-instance', headers=d.c.headers,
        json={'patient_id': d.c.patient.id, 'report_instance_id': selected.id})
    assert response.status_code == 200 and response.json()['success'], response.text
    assert materialized == [selected.id]
    assert len(rendered) == 1
    assert rendered[0]['template_name'] == 'Selected template'
    assert rendered[0]['layout_preset'] == 'selected-layout'
    assert rendered[0]['page_settings'] == {'size': 'A4'}
    assert rendered[0]['patient'] == {'name': 'SYNTHETIC SELECTED'}
    assert rendered[0]['sections'] == [{'key': 'selected-section'}]
    sent = d.bot._send_document.await_args.kwargs
    assert sent['filename'] == f'lab-report-{selected.id}.pdf'
    assert sent['document_bytes'] == b'%PDF-selected'
    assert sent['chat_id'] == d.c.link.chat_id


def test_lab_text_and_markup_do_not_disclose_resource_or_actor_ids(client, db_session, delivery):
    from app.models.clinic import Doctor
    from app.models.lab import LabOrder, LabResult
    from app.models.patient import Patient
    from app.models.telegram_config import TelegramUser
    from app.models.user import User
    from app.models.visit import Visit
    from tests.conftest import mint_access_token

    patient = Patient(id=782341, first_name='SYNTHETIC', last_name='SCOPED', phone='+998900001111')
    user = User(id=654321, username='synthetic-lab-scope', hashed_password='synthetic',
                role='Doctor', is_active=True, is_superuser=False)
    db_session.add_all([patient, user])
    db_session.flush()
    doctor = Doctor(id=398721, user_id=user.id, specialty='cardiology', active=True)
    db_session.add(doctor)
    db_session.flush()
    visit = Visit(patient_id=patient.id, doctor_id=doctor.id)
    link = TelegramUser(patient_id=patient.id, chat_id=892345600, active=True, blocked=False,
                        notifications_enabled=True, appointment_reminders=True, lab_notifications=True)
    db_session.add_all([visit, link])
    db_session.flush()
    order = LabOrder(patient_id=patient.id, visit_id=visit.id, status='done')
    db_session.add(order)
    db_session.flush()
    result = LabResult(id=913572, order_id=order.id, test_name='SYNTHETIC PRIVATE RESULT')
    db_session.add(result)
    db_session.commit()
    response = client.post('/api/v1/telegram/send-lab-results',
        headers={'Authorization': f'Bearer {mint_access_token(user)}'},
        params={'patient_id': patient.id}, json=[result.id])
    assert response.status_code == 200 and response.json()['success'], response.text
    sent = delivery.bot._send_message.await_args.kwargs
    payload = repr((sent['text'], sent.get('reply_markup')))
    assert all(str(value) not in payload for value in (patient.id, result.id, doctor.id, user.id))
    assert 'SYNTHETIC PRIVATE RESULT' not in payload
    assert sent['chat_id'] == link.chat_id


@pytest.mark.parametrize('kind', ['lab', 'pdf'])
@pytest.mark.parametrize('state', ['unlinked', 'category_optout', 'global_optout'])
def test_lab_delivery_unavailable_is_200_false(client, db_session, delivery, kind, state):
    if state == 'unlinked':
        db_session.delete(delivery.c.link)
    elif state == 'category_optout':
        delivery.c.link.lab_notifications = False
    else:
        delivery.c.link.notifications_enabled = False
    db_session.commit()
    response = send(client, delivery, kind)
    assert response.status_code == 200, response.text
    assert response.json()['success'] is False
    assert_not_sent(delivery)


def test_appointment_unlinked_has_404_contract(client, db_session, delivery):
    db_session.delete(delivery.c.link)
    db_session.commit()
    response = send(client, delivery, 'appointment')
    assert response.status_code == 404, response.text
    assert_not_sent(delivery)
