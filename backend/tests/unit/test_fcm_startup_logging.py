"""FCM startup logging hygiene tests.

Regression for the noisy-startup report: ``_load_credentials`` used to emit
``WARNING "GOOGLE_APPLICATION_CREDENTIALS not found or invalid. FCM disabled."``
on EVERY process start, including the default, perfectly valid configuration
where the push channel is intentionally off (``FCM_ENABLED=false``).

Contract after the fix:
* ``FCM_ENABLED=false`` (default) + no credentials  -> INFO, no WARNING
  (an intentional off is not a misconfiguration);
* ``FCM_ENABLED=true``  + missing/unloadable path   -> WARNING with the full
  remediation checklist (a real misconfiguration: sends short-circuit with
  "FCM service not configured", so pushes silently never fire);
* valid credential file                             -> INFO "FCM credentials
  loaded successfully" (unchanged), and credentials load regardless of the
  flag so that flipping ``FCM_ENABLED`` stays a restart-only operation.
"""
from __future__ import annotations

import logging
from pathlib import Path

import pytest

from app.services import fcm_service as fcm_module
from app.services.fcm_service import FCMService

LOGGER_NAME = "app.services.fcm_service"


def _fcm_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOGGER_NAME]


def _load(monkeypatch: pytest.MonkeyPatch, *, enabled: bool) -> FCMService:
    monkeypatch.setattr(fcm_module.settings, "FCM_ENABLED", enabled)
    return FCMService()


@pytest.fixture(autouse=True)
def _no_credentials_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)


def test_disabled_by_config_logs_info_not_warning(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Default local/dev startup (flag off, no credentials) must be calm."""
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    service = _load(monkeypatch, enabled=False)

    records = _fcm_records(caplog)
    assert service.credentials is None
    assert not [r for r in records if r.levelno >= logging.WARNING]
    info = [r for r in records if r.levelno == logging.INFO]
    assert info, "expected an INFO line explaining the intentional off"
    assert "FCM_ENABLED=false" in info[-1].getMessage()


def test_enabled_without_credentials_warns_with_remediation(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Flag on + credentials missing = real misconfiguration -> WARNING."""
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    service = _load(monkeypatch, enabled=True)

    records = _fcm_records(caplog)
    assert service.credentials is None
    warnings = [r for r in records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert "FCM_ENABLED=true" in message
    assert "GOOGLE_APPLICATION_CREDENTIALS" in message
    assert "FCM_PROJECT_ID" in message


def test_enabled_with_missing_file_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """A path that no longer exists is the same misconfiguration."""
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    monkeypatch.setenv(
        "GOOGLE_APPLICATION_CREDENTIALS", str(tmp_path / "absent-service-account.json")
    )
    service = _load(monkeypatch, enabled=True)

    assert service.credentials is None
    warnings = [
        r
        for r in _fcm_records(caplog)
        if r.levelno == logging.WARNING
    ]
    assert len(warnings) == 1
    assert "GOOGLE_APPLICATION_CREDENTIALS" in warnings[0].getMessage()


def test_valid_credentials_load_even_when_disabled(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Credentials still load with the flag off: enabling push later stays a
    restart-only operation, and /fcm/status can honestly report what loaded."""
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    cred_file = tmp_path / "service-account.json"
    cred_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(cred_file))
    sentinel = object()
    loaded_paths: list[str] = []

    def _fake_from_service_account_file(path: str, scopes: list[str]) -> object:
        loaded_paths.append(path)
        assert scopes == ["https://www.googleapis.com/auth/firebase.messaging"]
        return sentinel

    monkeypatch.setattr(
        fcm_module.service_account.Credentials,
        "from_service_account_file",
        _fake_from_service_account_file,
    )
    service = _load(monkeypatch, enabled=False)

    assert service.credentials is sentinel
    assert loaded_paths == [str(cred_file)]
    infos = [
        r.getMessage()
        for r in _fcm_records(caplog)
        if r.levelno == logging.INFO
    ]
    assert any("FCM credentials loaded successfully" in m for m in infos)
    assert not [r for r in _fcm_records(caplog) if r.levelno >= logging.WARNING]
