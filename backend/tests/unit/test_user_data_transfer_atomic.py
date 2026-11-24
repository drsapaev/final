"""The legacy transfer must not mutate data before ownership is fenced."""

from unittest.mock import Mock

from app.api.v1.endpoints import user_data_transfer
from tests.conftest import mint_access_token


def test_unsafe_transfer_and_unimplemented_consent_are_not_started(client, admin_user, monkeypatch):
    legacy = Mock(side_effect=AssertionError("legacy transfer must not run"))
    monkeypatch.setattr(user_data_transfer, "get_user_data_transfer_service", legacy)
    headers = {"Authorization": f"Bearer {mint_access_token(admin_user)}"}
    payload = {"source_user_id": 1, "target_user_id": 2}
    for path in ("transfer", "transfer/request-confirmation"):
        response = client.post(f"/api/v1/admin/user-data/{path}", headers=headers, json=payload)
        assert response.status_code == 409, response.text
    response = client.post(
        "/api/v1/admin/user-data/transfer/validate?source_user_id=1&target_user_id=2",
        headers=headers,
    )
    assert response.status_code == 409, response.text
    legacy.assert_not_called()
