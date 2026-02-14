from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.setting_api_service import SettingApiDomainError, SettingApiService


@pytest.mark.unit
class TestSettingApiService:
    def test_get_settings_returns_repository_rows(self):
        expected = [SimpleNamespace(key="device_name"), SimpleNamespace(key="paper")]
        repository = SimpleNamespace(list_by_category=lambda category: expected)
        service = SettingApiService(db=None, repository=repository)

        result = service.get_settings(category="printer")

        assert result == expected

    def test_get_settings_wraps_repository_error(self):
        def _boom(category: str):
            raise RuntimeError("db broken")

        repository = SimpleNamespace(list_by_category=_boom)
        service = SettingApiService(db=None, repository=repository)

        with pytest.raises(SettingApiDomainError) as exc_info:
            service.get_settings(category="printer")

        assert exc_info.value.status_code == 500
        assert "db broken" in exc_info.value.detail

