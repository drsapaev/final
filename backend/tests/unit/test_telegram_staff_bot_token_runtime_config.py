from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1.endpoints import admin_telegram
from app.models.clinic import ClinicSettings
from app.services import telegram_bot


@pytest.mark.unit
class TestTelegramStaffBotTokenRuntimeConfig:
    def _clear_staff_bot_token_sources(self, monkeypatch):
        for env_key in admin_telegram.STAFF_BOT_TOKEN_ENV_KEYS:
            monkeypatch.delenv(env_key, raising=False)
        monkeypatch.setattr(
            admin_telegram,
            "settings",
            SimpleNamespace(model_config={}),
        )

    def test_reads_env_without_exposing_secret(self, monkeypatch, db_session):
        secret_value = "999999:staff-secret"
        self._clear_staff_bot_token_sources(monkeypatch)
        monkeypatch.setenv("TELEGRAM_STAFF_BOT_TOKEN", secret_value)

        token_status = admin_telegram._get_staff_bot_token_runtime_status(db_session)
        status = admin_telegram._build_staff_bot_status(
            webhook_set=False,
            staff_bot_token_status=token_status,
        )

        contract = status["token_contract"]
        assert contract["configured"] is True
        assert contract["runtime_read_enabled"] is True
        assert contract["source"] == "environment"
        assert contract["source_key"] == "TELEGRAM_STAFF_BOT_TOKEN"
        assert contract["token_returned_to_frontend"] is False
        assert contract["patient_bot_token_reused"] is False
        assert (
            status["role_menu_enablement_contract"][
                "pending_domain_data_command_keys"
            ][0]
            == "delivery_status"
        )
        assert status["next_slice"] == "staff_read_only_delivery_status_runtime"
        assert (
            status["command_registration_contract"]["registration_enabled"] is True
        )
        assert (
            status["command_registration_contract"]["state_changing_commands_registered"]
            is False
        )
        assert secret_value not in str(status)

    def test_reads_legacy_env_without_secret_leak(self, monkeypatch, db_session):
        secret_value = "777777:legacy-staff-secret"
        self._clear_staff_bot_token_sources(monkeypatch)
        monkeypatch.setenv("STAFF_TELEGRAM_BOT_TOKEN", secret_value)

        token_status = admin_telegram._get_staff_bot_token_runtime_status(
            db_session,
            patient_bot_token="patient-token",
        )
        status = admin_telegram._build_staff_bot_status(
            webhook_set=False,
            staff_bot_token_status=token_status,
        )

        contract = status["token_contract"]
        assert contract["configured"] is True
        assert contract["ready"] is True
        assert contract["source"] == "environment"
        assert contract["source_key"] == "STAFF_TELEGRAM_BOT_TOKEN"
        assert contract["enabled"] is True
        assert contract["runtime_blocked_by"] == []
        assert status["next_slice"] == "staff_read_only_delivery_status_runtime"
        assert (
            status["command_registration_contract"]["registration_enabled"] is True
        )
        assert secret_value not in str(status)
        assert "patient-token" not in str(status)

    def test_reads_clinic_setting_without_secret_leak(self, monkeypatch, db_session):
        secret_value = "888888:staff-setting-secret"
        self._clear_staff_bot_token_sources(monkeypatch)
        db_session.add(
            ClinicSettings(
                key="telegram_staff_bot_token",
                value=secret_value,
                category="telegram",
            )
        )
        db_session.commit()

        token_status = admin_telegram._get_staff_bot_token_runtime_status(db_session)
        status = admin_telegram._build_staff_bot_status(
            webhook_set=False,
            staff_bot_token_status=token_status,
        )

        contract = status["token_contract"]
        assert contract["configured"] is True
        assert contract["source"] == "clinic_settings"
        assert contract["source_key"] == "telegram_staff_bot_token"
        assert contract["separate_staff_bot_token_configured"] is True
        assert secret_value not in str(status)

    def test_blocks_patient_bot_token_reuse(self, monkeypatch, db_session):
        secret_value = "666666:shared-token"
        self._clear_staff_bot_token_sources(monkeypatch)
        monkeypatch.setenv("TELEGRAM_STAFF_BOT_TOKEN", secret_value)

        token_status = admin_telegram._get_staff_bot_token_runtime_status(
            db_session,
            patient_bot_token=secret_value,
        )
        status = admin_telegram._build_staff_bot_status(
            webhook_set=False,
            staff_bot_token_status=token_status,
        )

        contract = status["token_contract"]
        assert contract["configured"] is True
        assert contract["ready"] is False
        assert contract["enabled"] is False
        assert contract["separate_staff_bot_token_configured"] is False
        assert contract["patient_bot_token_reused"] is True
        assert "separate_staff_bot_token_configured" in contract["runtime_blocked_by"]
        assert status["next_slice"] == "dedicated_staff_bot_token_runtime_config"
        assert secret_value not in str(status)

    @pytest.mark.asyncio
    async def test_register_staff_commands_uses_read_only_payload_without_secret(
        self, monkeypatch, db_session
    ):
        secret_value = "999999:staff-secret"
        calls = []
        self._clear_staff_bot_token_sources(monkeypatch)
        monkeypatch.setenv("TELEGRAM_STAFF_BOT_TOKEN", secret_value)

        class FakeResponse:
            status_code = 200

            @staticmethod
            def json():
                return {"ok": True}

        def fake_post(url, json, timeout):
            calls.append({"url": url, "json": json, "timeout": timeout})
            return FakeResponse()

        monkeypatch.setattr(telegram_bot.requests, "post", fake_post)

        result = await admin_telegram.register_staff_bot_commands(
            db_session,
            SimpleNamespace(id=1),
        )

        registered = result["registered_commands"]
        assert result["success"] is True
        assert result["state_changing_commands_registered"] is False
        assert result["token_returned_to_frontend"] is False
        assert registered == [
            "staff",
            "queue",
            "schedule",
            "payments",
            "reports",
            "summary",
            "help",
        ]
        assert "refund" not in registered
        assert "call" not in registered
        assert secret_value not in str(result)
        assert calls[0]["json"]["commands"] == (
            admin_telegram._staff_bot_read_only_command_payload()
        )
