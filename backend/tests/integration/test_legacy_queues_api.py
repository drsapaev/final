import pytest

from app.models.setting import Setting


@pytest.mark.integration
def test_next_ticket_requires_auth_and_does_not_mutate_counters(client, db_session):
    response = client.post(
        "/api/v1/queues/next-ticket",
        params={"department": "cardiology", "date": "2026-05-26"},
    )

    assert response.status_code == 401, response.text
    assert db_session.query(Setting).filter(Setting.category == "queue").count() == 0


@pytest.mark.integration
def test_next_ticket_allows_registrar_staff(client, registrar_auth_headers):
    response = client.post(
        "/api/v1/queues/next-ticket",
        params={"department": "cardiology", "date": "2026-05-26"},
        headers=registrar_auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ticket"] == 1
    assert body["stats"]["waiting"] == 1
