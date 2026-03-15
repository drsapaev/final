from __future__ import annotations

from datetime import datetime

import pytest

from app.models.activation import Activation, ActivationStatus


@pytest.mark.integration
def test_activation_list_endpoint_uses_live_admin_contract(
    client,
    db_session,
    auth_headers,
):
    db_session.add_all(
        [
            Activation(
                key="ACTIVATION-001",
                machine_hash="machine-1",
                expiry_date=datetime(2026, 6, 1),
                status=ActivationStatus.ACTIVE,
                meta='{"env":"prod"}',
            ),
            Activation(
                key="ACTIVATION-002",
                machine_hash="machine-2",
                expiry_date=datetime(2026, 7, 1),
                status=ActivationStatus.REVOKED,
                meta='{"env":"stage"}',
            ),
        ]
    )
    db_session.commit()

    response = client.get(
        "/api/v1/activation/list",
        params={"status": ActivationStatus.ACTIVE},
        headers=auth_headers,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["key"] == "ACTIVATION-001"
    assert payload["items"][0]["status"] == ActivationStatus.ACTIVE


@pytest.mark.integration
def test_activation_revoke_and_extend_endpoints_keep_admin_behavior(
    client,
    db_session,
    auth_headers,
):
    row = Activation(
        key="ACTIVATION-123",
        machine_hash="machine-x",
        expiry_date=datetime(2026, 1, 10),
        status=ActivationStatus.EXPIRED,
    )
    db_session.add(row)
    db_session.commit()

    revoke_response = client.post(
        "/api/v1/activation/revoke",
        json={"key": row.key},
        headers=auth_headers,
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json() == {"ok": True}
    db_session.refresh(row)
    assert row.status == ActivationStatus.REVOKED

    extend_response = client.post(
        "/api/v1/activation/extend",
        json={"key": row.key, "days": 5},
        headers=auth_headers,
    )
    assert extend_response.status_code == 200
    payload = extend_response.json()
    assert payload["ok"] is True
    assert payload["status"] == ActivationStatus.REVOKED
    db_session.refresh(row)
    assert row.status == ActivationStatus.REVOKED
    assert row.expiry_date.strftime("%Y-%m-%d") == payload["expiry_date"]
