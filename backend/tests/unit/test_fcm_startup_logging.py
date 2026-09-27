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
  flag so that flipping ``FCM_ENABLED`` stays a restart-only operation;
* ``FCM_ENABLED=true`` + valid credentials + missing ``FCM_PROJECT_ID``
  -> exactly one WARNING with remediation (review round 3: without the
  project id the channel cannot fire — ``active`` is False and every send
  short-circuits with "FCM service not configured", so a clean
  "loaded successfully" alone was a silent misconfiguration).
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


def test_disabled_with_existing_invalid_credentials_is_info_not_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Review round 2: a STALE/corrupt credential file on disk used to hit the
    blanket ``logger.error`` even with the channel intentionally off — an
    ERROR on every valid dev startup. An off channel stays calm: INFO only,
    with an honest note that the invalid file was ignored."""
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    broken_file = tmp_path / "stale-service-account.json"
    broken_file.write_text("{ not valid json", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(broken_file))
    service = _load(monkeypatch, enabled=False)

    records = _fcm_records(caplog)
    assert service.credentials is None
    assert not [r for r in records if r.levelno >= logging.WARNING], (
        "broken file + FCM_ENABLED=false must not WARN/ERROR"
    )
    infos = [r.getMessage() for r in records if r.levelno == logging.INFO]
    assert any("FCM_ENABLED=false" in m for m in infos)
    assert any("invalid and was ignored" in m for m in infos)


def test_enabled_with_valid_credentials_but_missing_project_id_warns_once(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Review round 3: flag on + a VALID credential file + no ``FCM_PROJECT_ID``
    used to be a silent misconfiguration — startup logged only "FCM
    credentials loaded successfully" while ``service.active`` was False and
    every send short-circuited with "FCM service not configured". An enabled
    channel that cannot fire must WARN once at startup, naming the missing
    setting and attaching remediation."""
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    cred_file = tmp_path / "service-account.json"
    cred_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(cred_file))
    monkeypatch.setattr(fcm_module.settings, "FCM_PROJECT_ID", None)
    sentinel = object()

    def _fake_from_service_account_file(path: str, scopes: list[str]) -> object:
        return sentinel

    monkeypatch.setattr(
        fcm_module.service_account.Credentials,
        "from_service_account_file",
        _fake_from_service_account_file,
    )
    service = _load(monkeypatch, enabled=True)

    assert service.credentials is sentinel
    assert service.project_id is None
    assert service.active is False, (
        "missing FCM_PROJECT_ID must keep the service inactive"
    )
    records = _fcm_records(caplog)
    assert not [r for r in records if r.levelno >= logging.ERROR]
    warnings = [r for r in records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert "FCM_ENABLED=true" in message
    assert "FCM_PROJECT_ID" in message
    assert "not configured" in message or "missing" in message
    infos = [r.getMessage() for r in records if r.levelno == logging.INFO]
    assert any("FCM credentials loaded successfully" in m for m in infos)


def test_enabled_fully_configured_stays_info(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Guard rail: an enabled channel with credentials AND project id must stay
    calm — the project-id warning fires only when the setting is missing."""
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    cred_file = tmp_path / "service-account.json"
    cred_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(cred_file))
    monkeypatch.setattr(fcm_module.settings, "FCM_PROJECT_ID", "test-project")
    sentinel = object()

    def _fake_from_service_account_file(path: str, scopes: list[str]) -> object:
        return sentinel

    monkeypatch.setattr(
        fcm_module.service_account.Credentials,
        "from_service_account_file",
        _fake_from_service_account_file,
    )
    service = _load(monkeypatch, enabled=True)

    assert service.credentials is sentinel
    assert service.active is True
    assert not [r for r in _fcm_records(caplog) if r.levelno >= logging.WARNING]
    infos = [
        r.getMessage()
        for r in _fcm_records(caplog)
        if r.levelno == logging.INFO
    ]
    assert any("FCM credentials loaded successfully" in m for m in infos)


def test_enabled_with_existing_invalid_credentials_warns_with_remediation(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    """Mirror quadrant: flag on + unloadable file is a real misconfiguration
    — WARNING with remediation, never a silent INFO."""
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    broken_file = tmp_path / "stale-service-account.json"
    broken_file.write_text("{ not valid json", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(broken_file))
    service = _load(monkeypatch, enabled=True)

    records = _fcm_records(caplog)
    assert service.credentials is None
    warnings = [r for r in records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert "could not be loaded" in message
    assert "Regenerate" in message
    assert "FCM_PROJECT_ID" in message
    assert not [r for r in records if r.levelno >= logging.ERROR]
