from __future__ import annotations

import pytest

from app.models.setting import Setting


@pytest.mark.integration
def test_settings_get_and_put_are_admin_contract(client, auth_headers, db_session):
    db_session.add(Setting(category="printer", key="paper", value="A4"))
    db_session.commit()

    read_response = client.get(
        "/api/v1/settings",
        params={"category": "printer"},
        headers=auth_headers,
    )

    assert read_response.status_code == 200, read_response.text
    assert read_response.json() == [
        {"category": "printer", "key": "paper", "value": "A4"}
    ]

    update_response = client.put(
        "/api/v1/settings",
        json={"category": "printer", "key": "paper", "value": "A5"},
        headers=auth_headers,
    )

    assert update_response.status_code == 200, update_response.text
    assert update_response.json() == {
        "category": "printer",
        "key": "paper",
        "value": "A5",
    }

    reread_response = client.get(
        "/api/v1/settings",
        params={"category": "printer"},
        headers=auth_headers,
    )

    assert reread_response.status_code == 200, reread_response.text
    assert reread_response.json() == [
        {"category": "printer", "key": "paper", "value": "A5"}
    ]


@pytest.mark.integration
def test_settings_put_is_admin_only(client, registrar_auth_headers):
    response = client.put(
        "/api/v1/settings",
        json={"category": "printer", "key": "paper", "value": "A5"},
        headers=registrar_auth_headers,
    )

    assert response.status_code == 403
