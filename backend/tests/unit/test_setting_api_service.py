from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.setting_api_service import SettingApiDomainError, SettingApiService


@pytest.mark.unit
class TestSettingApiService:
    def test_get_settings_returns_repository_rows(self):
        expected = [SimpleNamespace(key="device_name"), SimpleNamespace(key="paper")]
        repository = SimpleNamespace(
            list_by_category=lambda **kwargs: expected,
        )
        service = SettingApiService(db=None, repository=repository)

        result = service.get_settings(category="printer")

        assert result == expected

    def test_get_settings_wraps_repository_error(self):
        def _boom(**kwargs):
            raise RuntimeError("db broken")

        repository = SimpleNamespace(list_by_category=_boom)
        service = SettingApiService(db=None, repository=repository)

        with pytest.raises(SettingApiDomainError) as exc_info:
            service.get_settings(category="printer")

        assert exc_info.value.status_code == 500
        assert "db broken" in exc_info.value.detail

    def test_update_setting_returns_repository_row(self):
        expected = SimpleNamespace(category="display_board", key="brand", value="Clinic")
        repository = SimpleNamespace(upsert=lambda **kwargs: expected)
        service = SettingApiService(db=None, repository=repository)

        result = service.update_setting(
            category="display_board",
            key="brand",
            value="Clinic",
        )

        assert result == expected

    def test_update_setting_wraps_repository_error(self):
        def _boom(**kwargs):
            raise RuntimeError("write failed")

        repository = SimpleNamespace(upsert=_boom)
        service = SettingApiService(db=None, repository=repository)

        with pytest.raises(SettingApiDomainError) as exc_info:
            service.update_setting(category="printer", key="device_name", value="HP")

        assert exc_info.value.status_code == 500
        assert "write failed" in exc_info.value.detail
