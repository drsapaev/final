from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks, HTTPException

from app.api.v1.endpoints import telegram_integration


@pytest.mark.asyncio
async def test_appointment_reminder_preserves_no_id_payload(monkeypatch):
    telegram_user = SimpleNamespace(chat_id=998877, language_code="ru")
    background_tasks = BackgroundTasks()

    monkeypatch.setattr(
        telegram_integration.crud_telegram,
        "find_telegram_user_by_phone",
        lambda _db, _phone: telegram_user,
        raising=False,
    )

    response = await telegram_integration.send_appointment_reminder(
        {
            "patient_phone": "+998901234567",
            "appointment_data": {
                "patient_name": "Sensitive Patient",
                "doctor_name": "Dr Privacy",
                "date": "2026-05-31",
                "time": "09:00",
            },
        },
        background_tasks,
        db=object(),
        current_user=SimpleNamespace(role="Registrar"),
    )

    assert response["success"] is True
    assert len(background_tasks.tasks) == 1


@pytest.mark.asyncio
async def test_appointment_reminder_rejects_other_patient_appointment(
    monkeypatch,
):
    patient = SimpleNamespace(id=123, phone="+998901234567")
    appointment = SimpleNamespace(id=456, patient_id=999)
    telegram_user = SimpleNamespace(chat_id=998877, language_code="ru")
    background_tasks = BackgroundTasks()

    class FakeQuery:
        def __init__(self, result):
            self.result = result

        def filter(self, *_args, **_kwargs):
            return self

        def first(self):
            return self.result

    class FakeDb:
        def query(self, model):
            if model is telegram_integration.Appointment:
                return FakeQuery(appointment)
            raise AssertionError(f"Unexpected query model: {model}")

    monkeypatch.setattr(
        telegram_integration.crud_telegram,
        "find_telegram_user_by_phone",
        lambda _db, _phone: telegram_user,
        raising=False,
    )
    monkeypatch.setattr(
        telegram_integration.crud_patient,
        "find_patient",
        lambda _db, phone: patient,
        raising=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        await telegram_integration.send_appointment_reminder(
            {
                "patient_phone": "+998901234567",
                "appointment_data": {
                    "appointment_id": 456,
                    "patient_name": "Other Patient",
                    "date": "2026-05-31",
                    "time": "09:00",
                },
            },
            background_tasks,
            db=FakeDb(),
            current_user=SimpleNamespace(role="Registrar"),
        )

    assert exc_info.value.status_code == 403
    assert background_tasks.tasks == []
