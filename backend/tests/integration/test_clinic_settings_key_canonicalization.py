"""Clinic settings key canonicalization (site-plan step 1).

The setup wizard writes clinic_* keys (clinic_address, clinic_phone, ...)
while the admin settings screen historically saved the bare legacy spelling
(address, phone, ...) into the same clinic_settings category. Two spellings
for one data point break the future public read-model. Canonical keys are the
wizard's clinic_* names; batch writes normalize legacy keys to canonical;
migration 0078 copies existing legacy values over without deleting anything.
"""

import pytest
from fastapi.testclient import TestClient

LEGACY_TO_CANONICAL = {
    "address": "clinic_address",
    "phone": "clinic_phone",
    "email": "clinic_email",
    "timezone": "clinic_timezone",
    "logo_url": "clinic_logo_url",
}


def _saved_keys(db_session) -> set[str]:
    from app.models.clinic import ClinicSettings

    return {
        row.key
        for row in db_session.query(ClinicSettings).filter(
            ClinicSettings.category == "clinic"
        )
    }


@pytest.mark.integration
class TestClinicSettingsKeyCanonicalization:
    def test_batch_put_stores_canonical_keys(
        self, client: TestClient, auth_headers, db_session
    ):
        """RED-first: a legacy-key payload must land under clinic_* keys."""
        payload = {
            "address": "г. Ташкент, ул. Тестовая, 1",
            "phone": "+998 71 000-00-00",
            "email": "clinic@test.example",
            "timezone": "Asia/Tashkent",
        }
        response = client.put(
            "/api/v1/admin/clinic/settings",
            headers=auth_headers,
            json={"settings": payload},
        )
        assert response.status_code == 200, response.text

        keys = _saved_keys(db_session)
        for legacy, canonical in LEGACY_TO_CANONICAL.items():
            if legacy not in payload:
                continue
            assert (
                canonical in keys
            ), f"missing canonical key {canonical}; saved: {keys}"
            assert legacy not in keys, f"legacy key {legacy} must not be created"

    def test_canonical_wins_when_payload_carries_both(
        self, client: TestClient, auth_headers, db_session
    ):
        from app.models.clinic import ClinicSettings

        response = client.put(
            "/api/v1/admin/clinic/settings",
            headers=auth_headers,
            json={
                "settings": {
                    "phone": "legacy-value",
                    "clinic_phone": "canonical-value",
                }
            },
        )
        assert response.status_code == 200, response.text

        row = (
            db_session.query(ClinicSettings)
            .filter(ClinicSettings.key == "clinic_phone")
            .one()
        )
        assert row.value == "canonical-value"
        assert (
            db_session.query(ClinicSettings)
            .filter(ClinicSettings.key == "phone")
            .first()
            is None
        )

    def test_non_clinic_categories_are_not_normalized(
        self, client: TestClient, auth_headers, db_session
    ):
        """Normalization is scoped to category 'clinic'."""
        from app.models.clinic import ClinicSettings

        db_session.add(
            ClinicSettings(key="phone", value="keep-me", category="laboratory")
        )
        db_session.commit()

        from app.crud.clinic import update_settings_batch

        update_settings_batch(
            db_session, "laboratory", {"phone": "updated"}, user_id=None
        )

        row = (
            db_session.query(ClinicSettings)
            .filter(
                ClinicSettings.category == "laboratory",
                ClinicSettings.key == "phone",
            )
            .one()
        )
        assert row.value == "updated"

    def test_get_returns_canonical_keys_after_normalized_write(
        self, client: TestClient, auth_headers
    ):
        client.put(
            "/api/v1/admin/clinic/settings",
            headers=auth_headers,
            json={"settings": {"phone": "+998 71 000-00-00"}},
        )
        listing = client.get(
            "/api/v1/admin/clinic/settings",
            headers=auth_headers,
        )
        assert listing.status_code == 200, listing.text
        keys = {row["key"] for row in listing.json()}
        assert "clinic_phone" in keys
        assert "phone" not in keys
