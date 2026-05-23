from __future__ import annotations

import pytest


@pytest.mark.integration
def test_registrar_record_action_can_cancel_online_queue_entry(
    client,
    db_session,
    registrar_auth_headers,
    test_queue_entry,
):
    response = client.post(
        "/api/v1/registrar/records/actions",
        headers=registrar_auth_headers,
        json={
            "action": "cancel",
            "records": [
                {
                    "record_kind": "online_queue",
                    "record_id": test_queue_entry.id,
                }
            ],
            "reason": "contract test",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["action"] == "cancel"
    assert payload["success"] is True
    assert payload["success_count"] == 1
    assert payload["failed_count"] == 0
    assert payload["results"][0]["record_kind"] == "online_queue"
    assert payload["results"][0]["record_id"] == test_queue_entry.id

    db_session.refresh(test_queue_entry)
    assert test_queue_entry.status == "canceled"


@pytest.mark.integration
def test_registrar_record_action_rejects_doctor_mark_paid(
    client,
    cardio_auth_headers,
    test_visit,
):
    response = client.post(
        "/api/v1/registrar/records/actions",
        headers=cardio_auth_headers,
        json={
            "action": "mark_paid",
            "record_kind": "visit",
            "record_id": test_visit.id,
        },
    )

    assert response.status_code == 403

