from __future__ import annotations

from app.models.user import User


def test_admin_user_create_accepts_reserved_test_domain(
    client,
    auth_headers,
    db_session,
):
    payload = {
        "username": "qa_admin_reserved_api",
        "email": "QA_Admin_API@Test.Local",
        "password": "Admin1234",
        "role": "Admin",
        "is_active": True,
        "full_name": "QA Admin Reserved API",
    }

    response = client.post("/api/v1/users/users", json=payload, headers=auth_headers)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["username"] == "qa_admin_reserved_api"
    assert data["email"] == "qa_admin_api@test.local"

    saved_user = (
        db_session.query(User)
        .filter(User.username == "qa_admin_reserved_api")
        .first()
    )
    assert saved_user is not None
    assert saved_user.email == "qa_admin_api@test.local"
