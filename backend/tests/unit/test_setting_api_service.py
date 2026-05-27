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

    def test_upsert_setting_delegates_to_repository(self):
        expected = SimpleNamespace(category="printer", key="paper", value="A5")
        repository = SimpleNamespace(upsert=lambda category, key, value: expected)
        service = SettingApiService(db=None, repository=repository)

        result = service.upsert_setting(category="printer", key="paper", value="A5")

        assert result == expected

    def test_get_settings_wraps_repository_error_without_leaking_detail(self):
        def _boom(category: str):
            raise RuntimeError("db broken internal diagnostic")

        repository = SimpleNamespace(list_by_category=_boom)
        service = SettingApiService(db=None, repository=repository)

        with pytest.raises(SettingApiDomainError) as exc_info:
            service.get_settings(category="printer")

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Internal server error"

    def test_upsert_setting_wraps_repository_error_without_leaking_detail(self):
        def _boom(category: str, key: str, value: str):
            raise RuntimeError("constraint diagnostic")

        repository = SimpleNamespace(upsert=_boom)
        service = SettingApiService(db=None, repository=repository)

        with pytest.raises(SettingApiDomainError) as exc_info:
            service.upsert_setting(category="printer", key="paper", value="A5")

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Internal server error"

