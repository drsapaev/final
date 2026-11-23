from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.api.v1.endpoints.admin_telegram import _settings as admin_telegram_settings
from app.api.v1.endpoints.telegram_webhook import _helpers as telegram_helpers


def _integration_status(
    monkeypatch: pytest.MonkeyPatch,
    *,
    bot_token: str | None,
    frontend_url: str | None,
    staff_ready: bool = True,
) -> dict[str, Any]:
    monkeypatch.setattr(
        admin_telegram_settings.crud_telegram,
        "get_telegram_config",
        lambda _db: SimpleNamespace(active=True, webhook_url=None),
    )
    monkeypatch.setattr(
        admin_telegram_settings.crud_telegram,
        "get_telegram_users",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        admin_telegram_settings,
        "_get_configured_bot_token",
        lambda _db: bot_token,
    )
    monkeypatch.setattr(
        admin_telegram_settings,
        "_get_configured_bot_username",
        lambda _db: "clinic_bot" if bot_token else None,
    )
    monkeypatch.setattr(
        admin_telegram_settings,
        "_get_staff_bot_token_runtime_status",
        lambda _db, **_kwargs: {"ready": staff_ready},
    )
    monkeypatch.setattr(
        admin_telegram_settings,
        "_fetch_telegram_webhook_info",
        lambda _token: {"url": "https://api.example.test/api/v1/telegram/webhook"},
    )
    monkeypatch.setattr(
        admin_telegram_settings.settings,
        "FRONTEND_URL",
        frontend_url,
    )

    return admin_telegram_settings.get_telegram_integration_status(
        db=None,
        current_user=SimpleNamespace(role="Admin"),
    )


@pytest.mark.unit
def test_patient_mini_app_features_require_bot_token_and_frontend_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ready = _integration_status(
        monkeypatch,
        bot_token="test-bot-token",
        frontend_url="https://clinic.example",
    )
    ready_features = {
        feature["key"]: feature["enabled"]
        for feature in ready["patient_bot"]["features"]
    }
    for key in (
        "patient_booking_entrypoint",
        "patient_payments_mini_app_entry",
        "patient_forms_entrypoint",
        "doctor_schedule_entrypoint",
        "patient_cabinet_entrypoint",
    ):
        assert ready_features[key] is True
    assert ready_features["patient_documents_placeholder"] is False
    assert ready_features["staff_entrypoint"] is True

    monkeypatch.setattr(
        admin_telegram_settings.settings,
        "FRONTEND_URL",
        "",
    )
    without_frontend = admin_telegram_settings.get_telegram_integration_status(
        db=None,
        current_user=SimpleNamespace(role="Admin"),
    )
    without_frontend_features = {
        feature["key"]: feature["enabled"]
        for feature in without_frontend["patient_bot"]["features"]
    }
    for key in (
        "patient_booking_entrypoint",
        "patient_payments_mini_app_entry",
        "patient_forms_entrypoint",
        "doctor_schedule_entrypoint",
        "patient_cabinet_entrypoint",
    ):
        assert without_frontend_features[key] is False
    assert without_frontend_features["patient_mini_app_manifest"] is True
    assert without_frontend_features["patient_documents_placeholder"] is False


@pytest.mark.unit
def test_patient_mini_app_features_stay_disabled_without_bot_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status = _integration_status(
        monkeypatch,
        bot_token=None,
        frontend_url="https://clinic.example",
        staff_ready=False,
    )
    features = {
        feature["key"]: feature["enabled"]
        for feature in status["patient_bot"]["features"]
    }

    assert features["patient_booking_entrypoint"] is False
    assert features["patient_forms_entrypoint"] is False
    assert features["patient_mini_app_manifest"] is False
    assert features["staff_entrypoint"] is False
    assert features["patient_documents_placeholder"] is False


@pytest.mark.unit
@pytest.mark.parametrize(
    (
        "language",
        "protected_word",
        "chat_warning",
        "archive_text",
        "booking_confirmation",
        "missing_button_guidance",
    ),
    [
        (
            "ru",
            "защищ",
            "telegram",
            "полный архив документов и чеков",
            "регистратура подтвердит запись",
            "обратитесь в регистратуру",
        ),
        (
            "uz-Latn",
            "himoyalangan",
            "chat",
            "to'liq arxivi",
            "registratura yozilishni tasdiqlaydi",
            "registraturaga murojaat qiling",
        ),
    ],
)
def test_patient_entry_copy_matches_protected_mini_app_flows(
    language: str,
    protected_word: str,
    chat_warning: str,
    archive_text: str,
    booking_confirmation: str,
    missing_button_guidance: str,
) -> None:
    forms = telegram_helpers._localized_text("patient_forms", language).casefold()
    results = telegram_helpers._localized_text("patient_documents", language).casefold()
    booking = telegram_helpers._localized_text("doctor_schedule", language).casefold()
    cabinet = telegram_helpers._localized_text("patient_cabinet", language).casefold()

    for message in (forms, results, booking, cabinet):
        assert protected_word in message
        assert missing_button_guidance in message
    assert chat_warning in forms
    assert "не подключ" not in forms
    assert "не подключ" not in booking
    assert "hali yoqilmagan" not in cabinet
    assert archive_text in results
    assert booking_confirmation in booking
