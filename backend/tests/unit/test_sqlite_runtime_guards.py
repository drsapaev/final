from __future__ import annotations

import pytest

from app.services import backup_service, monitoring_service


@pytest.mark.parametrize(
    "module, message",
    [
        (backup_service, "backup operations"),
        (monitoring_service, "monitoring metrics"),
    ],
)
def test_active_services_reject_sqlite_database_url_without_opt_in(
    monkeypatch: pytest.MonkeyPatch, module, message: str
) -> None:
    monkeypatch.delenv("ALLOW_SQLITE_DATABASE_URL", raising=False)
    monkeypatch.delenv("TESTING", raising=False)

    with pytest.raises(RuntimeError, match=message):
        module._validate_database_url("sqlite:///clinic.db")


@pytest.mark.parametrize("module", [backup_service, monitoring_service])
def test_active_services_allow_sqlite_only_with_explicit_legacy_opt_in(
    monkeypatch: pytest.MonkeyPatch, module
) -> None:
    monkeypatch.setenv("ALLOW_SQLITE_DATABASE_URL", "1")
    monkeypatch.delenv("TESTING", raising=False)

    module._validate_database_url("sqlite:///clinic.db")
