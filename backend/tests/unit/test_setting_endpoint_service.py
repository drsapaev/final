from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.setting_endpoint_service import SettingDomainError, SettingService


@pytest.mark.unit
class TestSettingService:
    def test_get_settings_returns_repository_rows(self):
        expected = [SimpleNamespace(key="device_name"), SimpleNamespace(key="paper")]
        repository = SimpleNamespace(list_by_category=lambda category: expected)
        service = SettingService(db=None, repository=repository)

        result = service.get_settings(category="printer")

        assert result == expected

    def test_get_settings_wraps_repository_error(self):
        def _boom(category: str):
            raise RuntimeError("db broken")

        repository = SimpleNamespace(list_by_category=_boom)
        service = SettingService(db=None, repository=repository)

        with pytest.raises(SettingDomainError) as exc_info:
            service.get_settings(category="printer")

        assert exc_info.value.status_code == 500
        assert "db broken" in exc_info.value.detail

