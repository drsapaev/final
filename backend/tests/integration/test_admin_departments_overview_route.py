from app.api.v1.endpoints import admin_departments


def test_admin_departments_overview_uses_canonical_handler(
    client,
    auth_headers,
    monkeypatch,
):
    monkeypatch.setattr(
        admin_departments,
        "_collect_department_overview",
        lambda db: {
            "departments": [{"key": "cardiology"}],
            "totals": {"departments": 1},
        },
    )

    response = client.get("/api/v1/admin/departments/overview", headers=auth_headers)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "success": True,
        "data": {
            "departments": [{"key": "cardiology"}],
            "totals": {"departments": 1},
        },
    }
