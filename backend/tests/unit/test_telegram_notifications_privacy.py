from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks

from app.api.v1.endpoints import telegram_notifications


class FakeTelegramTemplatesService:
    def __init__(self) -> None:
        self.template_data = None

    def get_abnormalities_text(self, has_abnormalities, language):
        return "abnormal" if has_abnormalities else "normal"

    def get_template(self, _template_key, _language, template_data):
        self.template_data = template_data
        return {"text": "Lab results are ready", "keyboard": None}


@pytest.mark.asyncio
async def test_send_lab_results_response_hides_patient_contact_metadata(monkeypatch):
    patient = SimpleNamespace(
        phone="+998901234567",
        full_name="Sensitive Patient",
    )
    telegram_user = SimpleNamespace(chat_id=998877, language_code="ru")
    lab_result = SimpleNamespace(
        test_code="CBC",
        created_at=datetime(2026, 5, 18, 9, 0, 0),
        is_abnormal=False,
        doctor_id=44,
    )
    bot_service = SimpleNamespace(
        active=True,
        initialize=AsyncMock(),
        _send_message=AsyncMock(return_value=True),
    )
    templates_service = FakeTelegramTemplatesService()

    monkeypatch.setattr(
        telegram_notifications.crud_patient,
        "get_patient",
        lambda _db, _patient_id: patient,
        raising=False,
    )
    monkeypatch.setattr(
        telegram_notifications.crud_telegram,
        "find_telegram_user_by_phone",
        lambda _db, _phone: telegram_user,
        raising=False,
    )
    monkeypatch.setattr(
        telegram_notifications.crud_lab,
        "get_lab_result",
        lambda _db, _result_id: lab_result,
        raising=False,
    )
    monkeypatch.setattr(
        telegram_notifications,
        "get_telegram_bot_service",
        AsyncMock(return_value=bot_service),
    )
    monkeypatch.setattr(
        telegram_notifications,
        "get_telegram_templates_service",
        lambda: templates_service,
    )

    response = await telegram_notifications.send_lab_results(
        patient_id=123,
        lab_result_ids=[456],
        background_tasks=BackgroundTasks(),
        db=object(),
        current_user=SimpleNamespace(role="Lab"),
    )

    assert response == {
        "success": True,
        "message": "Результаты анализов отправлены",
        "lab_results_count": 1,
    }
    assert "+998901234567" not in str(response)
    assert "Sensitive Patient" not in str(response)
    assert "998877" not in str(response)
    bot_service._send_message.assert_awaited_once_with(
        chat_id=998877,
        text="Lab results are ready",
        reply_markup=None,
    )
    assert templates_service.template_data["patient_name"] == "Sensitive Patient"


@pytest.mark.asyncio
async def test_send_lab_results_unregistered_response_hides_patient_phone(
    monkeypatch,
):
    patient = SimpleNamespace(
        phone="+998901234567",
        full_name="Sensitive Patient",
    )

    monkeypatch.setattr(
        telegram_notifications.crud_patient,
        "get_patient",
        lambda _db, _patient_id: patient,
        raising=False,
    )
    monkeypatch.setattr(
        telegram_notifications.crud_telegram,
        "find_telegram_user_by_phone",
        lambda _db, _phone: None,
        raising=False,
    )

    response = await telegram_notifications.send_lab_results(
        patient_id=123,
        lab_result_ids=[456],
        background_tasks=BackgroundTasks(),
        db=object(),
        current_user=SimpleNamespace(role="Lab"),
    )

    assert response["success"] is False
    assert "patient_phone" not in response
    assert "+998901234567" not in str(response)
    assert "Sensitive Patient" not in str(response)
