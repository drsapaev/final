from app.models.setting import Setting


def test_board_state_is_stats_only_contract(client, db_session):
    department = "Reg"
    date_str = "2026-05-23"

    for name, value in {
        "last_ticket": "17",
        "waiting": "4",
        "serving": "2",
        "done": "1",
    }.items():
        db_session.add(
            Setting(
                category="queue",
                key=f"{department}::{date_str}::{name}",
                value=value,
            )
        )
    db_session.commit()

    response = client.get(
        "/api/v1/board/state",
        params={"department": department, "date": date_str},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload == {
        "department": department,
        "date_str": date_str,
        "is_open": True,
        "start_number": 1,
        "last_ticket": 17,
        "waiting": 4,
        "serving": 2,
        "done": 1,
    }
    assert "queue_entries" not in payload
    assert "current_call" not in payload
    assert "announcements" not in payload
