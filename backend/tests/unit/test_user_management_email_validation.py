from __future__ import annotations

from pydantic import ValidationError

from app.schemas.user_management import UserCreateRequest, UserUpdateRequest


def test_user_create_request_allows_reserved_test_domain() -> None:
    request = UserCreateRequest(
        username="qa_admin_reserved",
        email="QA_Admin@Test.Local",
        password="Admin1234",
        role="Admin",
        full_name="QA Admin Reserved",
    )

    assert request.email == "qa_admin@test.local"


def test_user_update_request_allows_reserved_test_domain() -> None:
    request = UserUpdateRequest(
        email="Updated@Test.Local",
    )

    assert request.email == "updated@test.local"


def test_user_create_request_rejects_invalid_email() -> None:
    try:
        UserCreateRequest(
            username="qa_admin_invalid",
            email="user@localhost",
            password="Admin1234",
            role="Admin",
        )
    except ValidationError as exc:
        assert "email" in str(exc).lower()
    else:
        raise AssertionError("Expected ValidationError for invalid email")
