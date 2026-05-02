from __future__ import annotations

import pytest

from app.models.setting import Setting
from app.repositories.setting_api_repository import SettingApiRepository


@pytest.mark.unit
class TestSettingApiRepository:
    def test_list_by_category_returns_only_matching_rows(self, db_session):
        repository = SettingApiRepository(db_session)
        db_session.add_all(
            [
                Setting(category="printer", key="device_name", value="HP"),
                Setting(category="printer", key="paper", value="A4"),
                Setting(category="sms", key="provider", value="eskiz"),
            ]
        )
        db_session.commit()

        rows = repository.list_by_category(category="printer")

        assert {row.key for row in rows} == {"device_name", "paper"}

