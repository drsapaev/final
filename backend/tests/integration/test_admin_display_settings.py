from __future__ import annotations

import pytest


def _login_admin(client, admin_user, admin_password):
    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(admin_user)}"}


@pytest.mark.integration
def test_admin_display_settings_roundtrip(client, admin_user, admin_password):
    headers = _login_admin(client, admin_user, admin_password)

    boards_response = client.get("/api/v1/admin/display/boards", headers=headers)
    assert boards_response.status_code == 200, boards_response.text
    boards = boards_response.json()
    assert boards, "Expected seeded display boards"
    board = boards[0]
    board_id = board["id"]

    original_location = board["location"]
    original_queue_count = board["queue_display_count"]
    original_show_videos = board["show_videos"]

    update_response = client.put(
        f"/api/v1/admin/display/boards/{board_id}",
        json={
            "location": "QA display room",
            "queue_display_count": 7,
            "show_videos": True,
        },
        headers=headers,
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["success"] is True
    assert updated["board"]["location"] == "QA display room"
    assert updated["board"]["queue_display_count"] == 7
    assert updated["board"]["show_videos"] is True

    reread_response = client.get(
        f"/api/v1/admin/display/boards/{board_id}",
        headers=headers,
    )
    assert reread_response.status_code == 200, reread_response.text
    reread = reread_response.json()
    assert reread["location"] == "QA display room"
    assert reread["queue_display_count"] == 7
    assert reread["show_videos"] is True

    themes_response = client.get("/api/v1/admin/display/themes", headers=headers)
    assert themes_response.status_code == 200, themes_response.text
    themes = themes_response.json()
    assert {theme["name"] for theme in themes} >= {"light", "dark", "medical"}

    stats_response = client.get("/api/v1/admin/display/stats", headers=headers)
    assert stats_response.status_code == 200, stats_response.text
    stats = stats_response.json()
    assert stats["total_boards"] >= 1
    assert stats["active_boards"] >= 1
    assert board["name"] in stats["by_board"]
    assert stats["total_calls_today"] is None
    assert stats["uptime_percentage"] is None
    assert stats["by_board"][board["name"]]["calls"] is None
    assert stats["by_board"][board["name"]]["uptime"] is None

    cleanup_response = client.put(
        f"/api/v1/admin/display/boards/{board_id}",
        json={
            "location": original_location,
            "queue_display_count": original_queue_count,
            "show_videos": original_show_videos,
        },
        headers=headers,
    )
    assert cleanup_response.status_code == 200, cleanup_response.text


def test_display_diagnostics_require_an_active_device_of_the_chosen_board(
    client, admin_user, admin_password, db_session, monkeypatch
):
    from uuid import uuid4

    from app.api.v1.endpoints import admin_display
    from app.models.display_config import DisplayBoard
    from app.models.online_queue import OnlineQueueEntry
    from app.schemas.misc_endpoints import DisplayTestResponse
    from app.services.display_device_credentials import create_display_board_device

    headers = _login_admin(client, admin_user, admin_password)
    board = DisplayBoard(name="synthetic-test-board", display_name="Synthetic test")
    other = DisplayBoard(name="synthetic-other-board", display_name="Synthetic other")
    db_session.add_all([board, other])
    db_session.flush()
    device, _ = create_display_board_device(
        db_session, board=board, device_name="Synthetic TV", created_by=admin_user.id
    )
    count_before = db_session.query(OnlineQueueEntry).count()
    result_id = uuid4()
    attempts = []

    class DiagnosticManager:
        async def test_device(self, board_id, device_id, test_type):
            attempts.append((board_id, device_id, test_type))
            return DisplayTestResponse(test_id=result_id, status="unconfirmed")

    monkeypatch.setattr(admin_display, "get_display_manager", DiagnosticManager)
    path = f"/api/v1/admin/display/boards/{board.id}/test"
    request = {"device_id": device.id, "test_type": "announcement"}
    assert client.post(path, headers=headers, json={"test_type": "call"}).status_code == 422
    assert client.post(path, headers=headers, json={**request, "test_type": "banner"}).status_code == 422
    assert client.post(
        f"/api/v1/admin/display/boards/{other.id}/test", headers=headers, json=request
    ).status_code == 404

    response = client.post(path, headers=headers, json=request)
    assert response.status_code == 200
    assert response.json() == {"test_id": str(result_id), "status": "unconfirmed", "audio_status": None}
    assert attempts == [(board.name, device.id, "announcement")]
    assert db_session.query(OnlineQueueEntry).count() == count_before

    device.status = "revoked"
    db_session.add(device)
    db_session.commit()
    assert client.post(path, headers=headers, json=request).status_code == 409
    assert len(attempts) == 1
