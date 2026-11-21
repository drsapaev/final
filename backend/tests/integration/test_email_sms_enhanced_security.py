"""Real HTTP/DB notification ownership and truthful delivery regressions.

Providers are always mocked; no email or SMS is sent.
"""

import secrets
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints import email_sms_enhanced as endpoint
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.lab import (
    LabOrder,
    LabReportInstance,
    LabReportTemplate,
    LabReportTemplateVersion,
    LabResult,
)
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.user import User
from app.models.visit import Visit
from app.services.email_sms_enhanced import EmailSMSEnhancedService
from tests.conftest import mint_access_token


@pytest.fixture
def objects(db_session):
    marker = secrets.token_hex(6)
    owner = User(
        username='SYNTHETIC_OWNER_' + marker,
        full_name='SYNTHETIC DOCTOR',
        hashed_password=secrets.token_urlsafe(24),
        role='Doctor',
        is_active=True,
    )
    other = User(
        username='SYNTHETIC_OTHER_' + marker,
        full_name='SYNTHETIC OTHER',
        hashed_password=secrets.token_urlsafe(24),
        role='Doctor',
        is_active=True,
    )
    patient = Patient(
        first_name='SYNTHETIC',
        last_name=marker,
        email=f'{marker}@example.test',
        phone='+998901234567',
    )
    db_session.add_all([owner, other, patient])
    db_session.flush()
    doctor = Doctor(
        user_id=owner.id, specialty='cardiology', active=True, cabinet='101'
    )
    other_doctor = Doctor(user_id=other.id, specialty='cardiology', active=True)
    db_session.add_all([doctor, other_doctor])
    db_session.flush()
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=date(2030, 5, 4),
        appointment_time='10:15',
    )
    visit = Visit(patient_id=patient.id, doctor_id=doctor.id)
    db_session.add_all([appointment, visit])
    db_session.flush()
    order = LabOrder(patient_id=patient.id, visit_id=visit.id, status='done')
    payment = Payment(
        visit_id=visit.id,
        amount=Decimal('123.45'),
        currency='UZS',
        method='cash',
        status='paid',
    )
    db_session.add_all([order, payment])
    db_session.flush()
    result = LabResult(order_id=order.id, test_name='SYNTHETIC TEST', abnormal=True)
    db_session.add(result)
    db_session.commit()
    return SimpleNamespace(
        owner=owner,
        other=other,
        patient=patient,
        doctor=doctor,
        appointment=appointment,
        visit=visit,
        order=order,
        result=result,
        payment=payment,
    )


@pytest.fixture
def service(monkeypatch):
    fake = SimpleNamespace(
        send_appointment_reminder_enhanced=AsyncMock(
            return_value={'success': True, 'channels': {'email': {'success': True}}}
        ),
        send_lab_results_enhanced=AsyncMock(
            return_value={'success': True, 'channels': {'email': {'success': True}}}
        ),
        send_payment_confirmation_enhanced=AsyncMock(
            return_value={'success': True, 'channels': {'email': {'success': True}}}
        ),
        send_email_enhanced=AsyncMock(return_value=(True, 'OK')),
        send_sms_enhanced=AsyncMock(return_value=(True, 'OK')),
    )
    monkeypatch.setattr(endpoint, 'get_email_sms_enhanced_service', lambda: fake)
    return fake


def auth(user):
    return {'Authorization': 'Bearer ' + mint_access_token(user)}


def test_appointment_reminder_reads_real_appointment_and_enforces_assignment(
    client, objects, service
):
    url = '/api/v1/email-sms/send-appointment-reminder-enhanced'
    params = {'appointment_id': objects.appointment.id, 'channels': 'email'}
    denied = client.post(url, params=params, headers=auth(objects.other))
    assert denied.status_code == 403, denied.text
    service.send_appointment_reminder_enhanced.assert_not_awaited()
    response = client.post(url, params=params, headers=auth(objects.owner))
    assert response.status_code == 200 and response.json()['success'] is True
    args = service.send_appointment_reminder_enhanced.await_args.kwargs
    assert args['patient_data']['id'] == objects.patient.id
    assert args['appointment_data'] == {
        'id': objects.appointment.id,
        'doctor_name': 'SYNTHETIC DOCTOR',
        'specialty': 'cardiology',
        'date': '04.05.2030',
        'time': '10:15',
        'cabinet': '101',
    }


def test_lab_result_requires_owner_patient_and_ready_visit(
    client, db_session, objects, service
):
    url = '/api/v1/email-sms/send-lab-results-enhanced'
    params = {
        'patient_id': objects.patient.id,
        'lab_results_id': objects.result.id,
        'channels': 'email',
    }
    assert (
        client.post(url, params=params, headers=auth(objects.other)).status_code == 403
    )
    service.send_lab_results_enhanced.assert_not_awaited()
    objects.order.status = 'ordered'
    db_session.commit()
    assert (
        client.post(url, params=params, headers=auth(objects.owner)).status_code == 409
    )
    service.send_lab_results_enhanced.assert_not_awaited()
    objects.order.status = 'done'
    db_session.commit()
    response = client.post(url, params=params, headers=auth(objects.owner))
    assert response.status_code == 200 and response.json()['success']
    data = service.send_lab_results_enhanced.await_args.kwargs['lab_data']
    assert data['id'] == objects.result.id and data['test_type'] == 'SYNTHETIC TEST'
    assert data['has_abnormalities'] is True


def test_lab_result_rejects_patient_mismatch_even_for_admin(
    client, db_session, admin_user, objects, service
):
    stranger = Patient(first_name='SYNTHETIC', last_name='STRANGER')
    db_session.add(stranger)
    db_session.commit()
    response = client.post(
        '/api/v1/email-sms/send-lab-results-enhanced',
        params={'patient_id': stranger.id, 'lab_results_id': objects.result.id},
        headers=auth(admin_user),
    )
    assert response.status_code == 403
    service.send_lab_results_enhanced.assert_not_awaited()


def test_unscoped_doctor_custom_destinations_fail_closed(client, objects, service):
    email = client.post(
        '/api/v1/email-sms/send-custom-email',
        headers=auth(objects.owner),
        json={
            'to_email': 'synthetic@example.com',
            'subject': 'SYNTHETIC',
            'text_content': 'SYNTHETIC',
        },
    )
    sms = client.post(
        '/api/v1/email-sms/send-custom-sms',
        headers=auth(objects.owner),
        json={'phone': '+998901234567', 'message': 'SYNTHETIC'},
    )
    assert email.status_code == sms.status_code == 403
    service.send_email_enhanced.assert_not_awaited()
    service.send_sms_enhanced.assert_not_awaited()


def test_paid_payment_is_required_and_amount_is_sourced_from_db(
    client, db_session, admin_user, objects, service
):
    url = '/api/v1/email-sms/send-payment-confirmation-enhanced'
    params = {'patient_id': objects.patient.id, 'channels': 'email'}

    def post(data):
        return client.post(
            url, params=params, headers=auth(admin_user), json={'payment_data': data}
        )

    assert post({'amount': 999999}).status_code == 400
    assert (
        post(
            {'payment_id': objects.payment.id, 'id': objects.payment.id + 1}
        ).status_code
        == 400
    )
    objects.payment.status = 'pending'
    db_session.commit()
    assert post({'payment_id': objects.payment.id}).status_code == 409
    service.send_payment_confirmation_enhanced.assert_not_awaited()
    objects.payment.status = 'paid'
    db_session.commit()
    response = post(
        {'payment_id': objects.payment.id, 'amount': 999999, 'currency': 'USD'}
    )
    assert response.status_code == 200 and response.json()['success']
    actual = service.send_payment_confirmation_enhanced.await_args.kwargs[
        'payment_data'
    ]
    assert actual['id'] == objects.payment.id and actual['amount'] == Decimal('123.45')
    assert actual['currency'] == 'UZS' and actual['payment_method'] == 'cash'


def test_unsuccessful_provider_result_does_not_claim_sent(client, objects, service):
    service.send_appointment_reminder_enhanced.return_value = {
        'success': False,
        'channels': {'sms': {'success': False}},
    }
    response = client.post(
        '/api/v1/email-sms/send-appointment-reminder-enhanced',
        params={'appointment_id': objects.appointment.id, 'channels': 'sms'},
        headers=auth(objects.owner),
    )
    assert response.status_code == 200 and response.json()['success'] is False
    assert response.json()['message'] != 'Напоминание отправлено'

    service.send_appointment_reminder_enhanced.return_value = {
        'success': False,
        'channels': {'email': {'success': True}, 'sms': {'success': False}},
    }
    response = client.post(
        '/api/v1/email-sms/send-appointment-reminder-enhanced',
        params={'appointment_id': objects.appointment.id, 'channels': 'sms'},
        headers=auth(objects.owner),
    )
    assert response.json()['success'] is False
    assert (
        response.json()['message']
        == 'Уведомление доставлено не по всем выбранным каналам'
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'method,payload',
    [
        ('send_appointment_reminder_enhanced', {'id': 7, 'date': 'SYNTHETIC'}),
        ('send_lab_results_enhanced', {'id': 7, 'test_type': 'SYNTHETIC'}),
        (
            'send_payment_confirmation_enhanced',
            {'id': 7, 'amount': 100, 'currency': 'UZS'},
        ),
    ],
)
async def test_delivery_reports_missing_invalid_and_mixed_channels(method, payload):
    sender = EmailSMSEnhancedService()
    sender.send_email_enhanced = AsyncMock(return_value=(True, 'OK'))
    sender.send_sms_enhanced = AsyncMock(return_value=(False, 'FAILED'))
    run = getattr(sender, method)
    patient = {'id': 1, 'email': 'synthetic@example.test', 'phone': '+998901234567'}
    result = await run(patient, payload, channels=[])
    assert not result['success'] and result['channels'] == {}
    result = await run({'id': 1}, payload, channels=['email', 'sms'])
    assert not result['success'] and all(
        not v['success'] for v in result['channels'].values()
    )
    result = await run(patient, payload, channels=['invalid'])
    assert not result['success'] and not result['channels']['invalid']['success']
    result = await run(patient, payload, channels=['email', 'sms'])
    assert (
        not result['success']
        and result['channels']['email']['success']
        and not result['channels']['sms']['success']
    )
    sender.send_sms_enhanced.assert_awaited_once()
    sender.send_sms_enhanced.return_value = (True, 'OK')
    result = await run(patient, payload, channels=['email', 'sms'])
    assert result['success'] is True
    assert all(channel['success'] for channel in result['channels'].values())


def test_inactive_doctor_cannot_send_reminders(client, db_session, objects, service):
    objects.doctor.active = False
    db_session.commit()
    response = client.post(
        '/api/v1/email-sms/send-appointment-reminder-enhanced',
        params={'appointment_id': objects.appointment.id, 'channels': 'email'},
        headers=auth(objects.owner),
    )
    assert response.status_code == 403
    service.send_appointment_reminder_enhanced.assert_not_awaited()


def test_registrar_retains_custom_send_permission(client, registrar_user, service):
    response = client.post(
        '/api/v1/email-sms/send-custom-email',
        headers=auth(registrar_user),
        json={
            'to_email': 'synthetic@example.com',
            'subject': 'SYNTHETIC',
            'text_content': 'SYNTHETIC',
        },
    )
    assert response.status_code == 200 and response.json()['success'] is True
    service.send_email_enhanced.assert_awaited_once()


def test_lab_order_visit_patient_mismatch_fails_for_admin(
    client, db_session, admin_user, objects, service
):
    stranger = Patient(first_name='SYNTHETIC', last_name='STRANGER')
    db_session.add(stranger)
    db_session.flush()
    other_visit = Visit(patient_id=stranger.id)
    db_session.add(other_visit)
    db_session.flush()
    objects.order.visit_id = other_visit.id
    db_session.commit()
    response = client.post(
        '/api/v1/email-sms/send-lab-results-enhanced',
        params={'patient_id': objects.patient.id, 'lab_results_id': objects.result.id},
        headers=auth(admin_user),
    )
    assert response.status_code == 403
    service.send_lab_results_enhanced.assert_not_awaited()


def test_lab_report_must_be_finalized_even_when_order_says_done(
    client, db_session, objects, service
):
    template = LabReportTemplate(
        code='SYNTHETIC-' + secrets.token_hex(6), name='SYNTHETIC', family='SYNTHETIC'
    )
    db_session.add(template)
    db_session.flush()
    version = LabReportTemplateVersion(
        template_id=template.id, version_no=1, layout_preset='SYNTHETIC'
    )
    db_session.add(version)
    db_session.flush()
    report = LabReportInstance(
        order_id=objects.order.id,
        visit_id=objects.visit.id,
        patient_id=objects.patient.id,
        template_id=template.id,
        template_version_id=version.id,
        status='DRAFT',
    )
    db_session.add(report)
    db_session.flush()
    objects.result.source_instance_id = report.id
    db_session.commit()
    params = {
        'patient_id': objects.patient.id,
        'lab_results_id': objects.result.id,
        'channels': 'email',
    }
    path = '/api/v1/email-sms/send-lab-results-enhanced'
    assert (
        client.post(path, params=params, headers=auth(objects.owner)).status_code == 409
    )
    service.send_lab_results_enhanced.assert_not_awaited()
    report.status = 'FINALIZED'
    # Finalized reports are authoritative even when a legacy order was not
    # separately transitioned to the legacy done status.
    objects.order.status = 'ordered'
    db_session.commit()
    response = client.post(path, params=params, headers=auth(objects.owner))
    assert response.status_code == 200 and response.json()['success']
    service.send_lab_results_enhanced.assert_awaited_once()


@pytest.mark.asyncio
async def test_sms_transport_exception_does_not_expose_provider_payload(
    monkeypatch, caplog
):
    sender = EmailSMSEnhancedService()
    sender.sms_api_key = 'SYNTHETIC-API-KEY'
    sender.sms_api_url = 'https://example.invalid'
    post = AsyncMock(side_effect=RuntimeError('SYNTHETIC-CLINICAL-CANARY'))
    monkeypatch.setattr(
        'app.services.email_sms_enhanced.httpx.AsyncClient',
        lambda: SimpleNamespace(post=post),
    )
    with caplog.at_level('ERROR'):
        ok, message = await sender.send_sms_enhanced(
            phone='+998901234567', message='SYNTHETIC'
        )
    assert ok is False and 'SYNTHETIC-CLINICAL-CANARY' not in message
    assert 'SYNTHETIC-CLINICAL-CANARY' not in caplog.text
    post.assert_awaited_once()


def test_final_report_supplies_missing_order_identity_but_conflicts_fail_closed(
    client, db_session, objects, service, admin_user
):
    template = LabReportTemplate(
        code='SYNTHETIC-' + secrets.token_hex(6), name='SYNTHETIC', family='SYNTHETIC'
    )
    db_session.add(template)
    db_session.flush()
    version = LabReportTemplateVersion(
        template_id=template.id, version_no=1, layout_preset='SYNTHETIC'
    )
    db_session.add(version)
    db_session.flush()
    report = LabReportInstance(
        order_id=objects.order.id,
        visit_id=objects.visit.id,
        patient_id=objects.patient.id,
        template_id=template.id,
        template_version_id=version.id,
        status='FINALIZED',
    )
    db_session.add(report)
    db_session.flush()
    objects.result.source_instance_id = report.id
    objects.order.patient_id = None
    objects.order.visit_id = None
    objects.order.status = 'ordered'
    db_session.commit()
    path = '/api/v1/email-sms/send-lab-results-enhanced'
    params = {
        'patient_id': objects.patient.id,
        'lab_results_id': objects.result.id,
        'channels': 'email',
    }
    response = client.post(path, params=params, headers=auth(objects.owner))
    assert response.status_code == 200 and response.json()['success']
    assert client.post(path, params=params, headers=auth(admin_user)).status_code == 200
    service.send_lab_results_enhanced.reset_mock()
    stranger = Patient(first_name='SYNTHETIC', last_name='OTHER')
    db_session.add(stranger)
    db_session.flush()
    objects.order.patient_id = stranger.id
    db_session.commit()
    assert client.post(path, params=params, headers=auth(admin_user)).status_code == 403
    service.send_lab_results_enhanced.assert_not_awaited()
    objects.order.patient_id = None
    other_visit = Visit(patient_id=objects.patient.id)
    db_session.add(other_visit)
    db_session.flush()
    objects.order.visit_id = other_visit.id
    db_session.commit()
    assert client.post(path, params=params, headers=auth(admin_user)).status_code == 403
    service.send_lab_results_enhanced.assert_not_awaited()


@pytest.fixture
def actual_sender(monkeypatch):
    """Use actual template renderers while stubbing both outbound transports."""
    sender = EmailSMSEnhancedService()
    sender.smtp_username = 'synthetic@example.test'
    sender.smtp_password = secrets.token_urlsafe(24)
    sender.sms_api_key = secrets.token_urlsafe(24)
    sender.sms_api_url = 'https://example.invalid'
    mail = []
    sender._smtp_send_message = lambda message: mail.append(message)
    response = SimpleNamespace(
        raise_for_status=lambda: None, json=lambda: {'success': True}
    )
    post = AsyncMock(return_value=response)
    monkeypatch.setattr(
        'app.services.email_sms_enhanced.httpx.AsyncClient',
        lambda: SimpleNamespace(post=post),
    )
    monkeypatch.setattr(endpoint, 'get_email_sms_enhanced_service', lambda: sender)
    return SimpleNamespace(sender=sender, post=post, mail=mail)


def test_real_sms_templates_use_db_data_not_caller_message(
    client, objects, admin_user, actual_sender
):
    malicious = {
        'message': 'FORGED-TEXT',
        'formatted_amount': '999999 USD',
        'doctor_name': 'FORGED-DOCTOR',
        'test_type': 'FORGED-LAB',
    }
    base = '/api/v1/email-sms/'
    responses = [
        client.post(
            base + 'send-appointment-reminder-enhanced',
            params={'appointment_id': objects.appointment.id, 'channels': 'sms'},
            headers=auth(objects.owner),
            json=malicious,
        ),
        client.post(
            base + 'send-lab-results-enhanced',
            params={
                'patient_id': objects.patient.id,
                'lab_results_id': objects.result.id,
                'channels': 'sms',
            },
            headers=auth(objects.owner),
            json=malicious,
        ),
        client.post(
            base + 'send-payment-confirmation-enhanced',
            params={'patient_id': objects.patient.id, 'channels': 'sms'},
            headers=auth(admin_user),
            json={
                'payment_data': {
                    'payment_id': objects.payment.id,
                    'amount': 999999,
                    'currency': 'USD',
                },
                'template_data': malicious,
            },
        ),
    ]
    assert all(
        response.status_code == 200 and response.json()['success']
        for response in responses
    )
    calls = actual_sender.post.await_args_list
    assert len(calls) == 3
    messages = [call.kwargs['json']['message'].strip() for call in calls]
    from app.services.email_sms_enhanced import _protected_frontend_url

    assert messages[0] == (
        'Programma Clinic: Напоминание о записи к SYNTHETIC DOCTOR на 04.05.2030 в 10:15. '
        'Кабинет: 101. Приходите за 10 мин. до приема. Тел: +998 71 123-45-67'
    )
    assert messages[1] == (
        f'Programma Clinic: Результаты SYNTHETIC TEST готовы! Скачать: '
        f'{_protected_frontend_url("/patient/lab-results")}. '
        '⚠️ Есть отклонения - обратитесь к врачу. Тел: +998 71 123-45-67'
    )
    assert messages[2] == (
        f'Programma Clinic: Платеж 123.45 UZS получен! ID: . '
        f'Чек: {_protected_frontend_url("/patient/payments")}. Спасибо! Тел: +998 71 123-45-67'
    )
    assert all(
        'FORGED' not in message and '999999' not in message for message in messages
    )


def test_real_payment_email_uses_paid_at_and_preserves_decimal(
    client, db_session, objects, admin_user, actual_sender
):
    from datetime import UTC, datetime

    objects.payment.status = 'completed'
    objects.payment.created_at = datetime(2030, 1, 1, 8, 10, tzinfo=UTC)
    objects.payment.paid_at = datetime(2030, 1, 3, 9, 45, tzinfo=UTC)
    db_session.commit()
    response = client.post(
        '/api/v1/email-sms/send-payment-confirmation-enhanced',
        params={'patient_id': objects.patient.id, 'channels': 'email'},
        headers=auth(admin_user),
        json={
            'payment_data': {'payment_id': objects.payment.id, 'amount': 999999},
            'template_data': {'message': 'FORGED-TEXT', 'payment_date': 'FORGED-DATE'},
        },
    )
    assert response.status_code == 200 and response.json()['success']
    assert len(actual_sender.mail) == 1
    msg = actual_sender.mail[0]
    body_parts = [
        part.get_payload(decode=True).decode('utf-8')
        for part in msg.walk()
        if part.get_content_type() in {'text/plain', 'text/html'}
    ]
    assert len(body_parts) == 2
    for body in body_parts:
        assert '123.45 UZS' in body and '03.01.2030 09:45' in body
        assert '01.01.2030 08:10' not in body
        assert 'FORGED' not in body and '999999' not in body


@pytest.mark.parametrize('kind', ['appointment', 'lab', 'payment'])
def test_missing_resource_template_fails_closed_without_delivery(
    kind, client, objects, admin_user, actual_sender
):
    from jinja2 import DictLoader

    actual_sender.sender.sms_template_env.loader = DictLoader({})
    base = '/api/v1/email-sms/'
    malicious = {'message': 'FORGED-TEXT'}
    if kind == 'appointment':
        url = base + 'send-appointment-reminder-enhanced'
        params = {'appointment_id': objects.appointment.id, 'channels': 'sms'}
        body, user = malicious, objects.owner
    elif kind == 'lab':
        url = base + 'send-lab-results-enhanced'
        params = {
            'patient_id': objects.patient.id,
            'lab_results_id': objects.result.id,
            'channels': 'sms',
        }
        body, user = malicious, objects.owner
    else:
        url = base + 'send-payment-confirmation-enhanced'
        params = {'patient_id': objects.patient.id, 'channels': 'sms'}
        body, user = {
            'payment_data': {'payment_id': objects.payment.id},
            'template_data': malicious,
        }, admin_user
    response = client.post(url, params=params, headers=auth(user), json=body)
    assert response.status_code == 200 and response.json()['success'] is False
    assert 'FORGED-TEXT' not in response.text
    actual_sender.post.assert_not_awaited()
    assert not actual_sender.mail
