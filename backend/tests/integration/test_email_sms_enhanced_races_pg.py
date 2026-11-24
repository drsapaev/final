"""Fresh database checks between channels; all providers are mocked."""

import asyncio
import os
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.api.v1.endpoints import email_sms_enhanced as endpoint
from app.db.base_class import Base
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.user import User
from app.models.visit import Visit
from app.schemas.notifications import PaymentData
from app.services.email_sms_enhanced import EmailSMSEnhancedService

pytestmark = pytest.mark.integration


@pytest.fixture(scope='module')
def pg_engine():
    ci = os.environ.get('CI', '').lower() == 'true'
    raw = os.environ.get('DATABASE_URL', '').strip()
    if not raw or make_url(raw).get_backend_name() != 'postgresql':
        if ci:
            pytest.fail('CI requires PostgreSQL DATABASE_URL')
        pytest.skip('requires disposable PostgreSQL DATABASE_URL')
    url = make_url(raw)
    if not ci and not (url.database or '').startswith('clinic_test'):
        pytest.skip('use an explicitly disposable clinic_test database')
    schema = 'test_email_race_' + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        import app.db.base  # noqa: F401

        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


@pytest.mark.parametrize('change', ['refund', 'doctor_disabled', 'phone_changed'])
def test_rechecks_fresh_state_after_first_provider_await(
    pg_engine, monkeypatch, change
):
    marker = uuid4().hex
    with Session(pg_engine, expire_on_commit=False) as db:
        actor = User(
            username=marker,
            full_name='SYNTHETIC DOCTOR',
            hashed_password='synthetic',
            role='Doctor' if change != 'refund' else 'Admin',
            is_active=True,
        )
        patient = Patient(
            first_name='SYNTHETIC',
            last_name='PATIENT',
            email='synthetic@example.test',
            phone='+998901234567',
        )
        db.add_all([actor, patient])
        db.flush()
        doctor = Doctor(user_id=actor.id, specialty='cardiology', active=True)
        db.add(doctor)
        db.flush()
        appointment = Appointment(
            patient_id=patient.id,
            doctor_id=doctor.id,
            appointment_date=date(2030, 5, 4),
            appointment_time='10:15',
        )
        visit = Visit(patient_id=patient.id, doctor_id=doctor.id)
        db.add_all([appointment, visit])
        db.flush()
        payment = Payment(
            visit_id=visit.id,
            amount=Decimal('123.45'),
            currency='UZS',
            method='cash',
            status='paid',
        )
        db.add(payment)
        db.commit()
        ids = (patient.id, doctor.id, appointment.id, payment.id)
        sender = EmailSMSEnhancedService()

        async def first_channel(**_kwargs):
            # Commit through a separate connection after the first authorization
            # and before the service resumes dispatch to the second channel.
            with Session(pg_engine) as writer:
                if change == 'refund':
                    writer.get(Payment, ids[3]).status = 'refunded'
                elif change == 'doctor_disabled':
                    writer.get(Doctor, ids[1]).active = False
                else:
                    writer.get(Patient, ids[0]).phone = '+998909999999'
                writer.commit()
            return True, 'OK'

        sender.send_email_enhanced = AsyncMock(side_effect=first_channel)
        sender.send_sms_enhanced = AsyncMock(return_value=(True, 'OK'))
        monkeypatch.setattr(endpoint, 'get_email_sms_enhanced_service', lambda: sender)
        if change == 'refund':
            coro = endpoint.send_payment_confirmation_enhanced(
                patient_id=ids[0],
                payment_data=PaymentData(payment_id=ids[3]),
                channels=['email', 'sms'],
                template_data=None,
                background_tasks=BackgroundTasks(),
                db=db,
                current_user=actor,
            )
        else:
            coro = endpoint.send_appointment_reminder_enhanced(
                appointment_id=ids[2],
                channels=['email', 'sms'],
                template_data=None,
                background_tasks=BackgroundTasks(),
                db=db,
                current_user=actor,
            )
        result = asyncio.run(coro)
        assert result['success'] is False
        assert result['details']['channels']['email']['success'] is True
        assert result['details']['channels']['sms']['success'] is False
        sender.send_email_enhanced.assert_awaited_once()
        sender.send_sms_enhanced.assert_not_awaited()
