from __future__ import annotations

import pytest


from tests.auth_test_credentials import (
    ADMIN_PASSWORD,
)

def _login_admin(client, admin_user):
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": admin_user.username, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.integration
def test_admin_display_settings_roundtrip(client, admin_user):
    headers = _login_admin(client, admin_user)

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
