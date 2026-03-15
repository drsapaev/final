from __future__ import annotations

import pytest

from app.models.setting import Setting


@pytest.mark.integration
def test_get_settings_endpoint_returns_only_requested_category(
    client,
    db_session,
    auth_headers,
):
    db_session.add_all(
        [
            Setting(category="printer", key="device_name", value="HP"),
            Setting(category="printer", key="paper", value="A4"),
            Setting(category="display_board", key="brand", value="Clinic"),
        ]
    )
    db_session.commit()

    response = client.get(
        "/api/v1/settings",
        params={"category": "printer"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["key"] for item in payload] == ["device_name", "paper"]
    assert {item["category"] for item in payload} == {"printer"}


@pytest.mark.integration
def test_put_settings_endpoint_upserts_setting(client, db_session, auth_headers):
    response = client.put(
        "/api/v1/settings",
        json={
            "category": "display_board",
            "key": "brand",
            "value": "AI Factory Clinic",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "category": "display_board",
        "key": "brand",
        "value": "AI Factory Clinic",
    }

    row = (
        db_session.query(Setting)
        .filter(Setting.category == "display_board", Setting.key == "brand")
        .one()
    )
    assert row.value == "AI Factory Clinic"
