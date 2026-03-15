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

    def test_upsert_creates_missing_row(self, db_session):
        repository = SettingApiRepository(db_session)

        row = repository.upsert(
            category="display_board",
            key="brand",
            value="AI Factory Clinic",
        )

        assert row.category == "display_board"
        assert row.key == "brand"
        assert row.value == "AI Factory Clinic"
        assert (
            db_session.query(Setting)
            .filter(Setting.category == "display_board", Setting.key == "brand")
            .one()
            .value
            == "AI Factory Clinic"
        )

    def test_upsert_updates_existing_row(self, db_session):
        repository = SettingApiRepository(db_session)
        existing = Setting(category="printer", key="device_name", value="HP")
        db_session.add(existing)
        db_session.commit()

        row = repository.upsert(category="printer", key="device_name", value="Canon")

        assert row.id == existing.id
        assert row.value == "Canon"
