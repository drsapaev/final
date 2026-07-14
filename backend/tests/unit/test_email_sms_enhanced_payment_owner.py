from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.api.v1.endpoints import email_sms_enhanced
from app.schemas.notifications import PaymentData


@pytest.mark.asyncio
async def test_doctor_cannot_send_appointment_reminder_enhanced_for_other_doctor(
    monkeypatch,
):
    appointment = SimpleNamespace(
        id=456,
        patient_id=123,
        doctor_id=99,
    )
    get_patient = Mock()
    get_service = Mock()

    monkeypatch.setattr(
        email_sms_enhanced.crud_appointment,
        "get_appointment",
        lambda _db, _appointment_id: appointment,
        raising=False,
    )
    monkeypatch.setattr(
        email_sms_enhanced,
        "_doctor_allowed_doctor_ids",
        lambda _db, _current_user: {42},
    )
    monkeypatch.setattr(
        email_sms_enhanced.crud_patient,
        "get_patient",
        get_patient,
        raising=False,
    )
    monkeypatch.setattr(
        email_sms_enhanced,
        "get_email_sms_enhanced_service",
        get_service,
    )

    with pytest.raises(HTTPException) as exc_info:
        await email_sms_enhanced.send_appointment_reminder_enhanced(
            appointment_id=456,
            channels=["email"],
            template_data=None,
            background_tasks=BackgroundTasks(),
            db=object(),
            current_user=SimpleNamespace(role="Doctor", is_superuser=False),
        )

    assert exc_info.value.status_code == 403
    get_patient.assert_not_called()
    get_service.assert_not_called()


@pytest.mark.asyncio
async def test_send_payment_confirmation_enhanced_preserves_no_id_payload(
    monkeypatch,
):
    patient = SimpleNamespace(
        id=123,
        phone="+998901234567",
        email="patient@example.com",
        full_name="Sensitive Patient",
    )
    service = SimpleNamespace(
        send_payment_confirmation_enhanced=AsyncMock(
            return_value={"success": True, "channels": {"email": {"success": True}}}
        )
    )

    monkeypatch.setattr(
        email_sms_enhanced.crud_patient,
        "get_patient",
        lambda _db, _patient_id: patient,
        raising=False,
    )
    monkeypatch.setattr(
        email_sms_enhanced,
        "get_email_sms_enhanced_service",
        Mock(return_value=service),
    )

    response = await email_sms_enhanced.send_payment_confirmation_enhanced(
        patient_id=123,
        payment_data=PaymentData(amount=125000),
        channels=["email"],
        template_data=None,
        background_tasks=BackgroundTasks(),
        db=object(),
        current_user=SimpleNamespace(role="Cashier"),
    )

    assert response["success"] is True
    service.send_payment_confirmation_enhanced.assert_awaited_once()


@pytest.mark.asyncio
async def test_send_payment_confirmation_enhanced_rejects_other_patient_payment(
    monkeypatch,
):
    patient = SimpleNamespace(
        id=123,
        phone="+998901234567",
        email="patient@example.com",
        full_name="Sensitive Patient",
    )
    payment = SimpleNamespace(id=456, visit_id=10)
    visit = SimpleNamespace(id=10, patient_id=999)
    get_service = Mock()

    class FakeQuery:
        def __init__(self, result):
            self.result = result

        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return self.result

    class FakeDb:
        def query(self, model):
            if model is email_sms_enhanced.Payment:
                return FakeQuery(payment)
            if model is email_sms_enhanced.Visit:
                return FakeQuery(visit)
            raise AssertionError(f"Unexpected query model: {model}")

    monkeypatch.setattr(
        email_sms_enhanced.crud_patient,
        "get_patient",
        lambda _db, _patient_id: patient,
        raising=False,
    )
    monkeypatch.setattr(
        email_sms_enhanced,
        "get_email_sms_enhanced_service",
        get_service,
    )

    with pytest.raises(HTTPException) as exc_info:
        await email_sms_enhanced.send_payment_confirmation_enhanced(
            patient_id=123,
            payment_data=PaymentData(payment_id=456, amount=125000),
            channels=["email", "sms"],
            template_data=None,
            background_tasks=BackgroundTasks(),
            db=FakeDb(),
            current_user=SimpleNamespace(role="Cashier"),
        )

    assert exc_info.value.status_code == 403
    get_service.assert_not_called()
