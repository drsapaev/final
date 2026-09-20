"""NURSE-V2 N2-2 — endpoint-level auth contract for the assignment control plane.

Review P1 (PR #3333): ``require_roles()`` authenticates the JWT but does
not enforce ``User.is_active`` — a deactivated privileged account kept
its role-scoped access until token expiry (``update_user()`` performs no
token-blacklist revoke on ``is_active -> false``). The new admin surface
for the Nurse <-> QueueResource authorization primitive is gated by
``require_active_roles("Admin")`` and must fail closed.

Mandatory regression (reviewer-specified):

    Admin token -> deactivate Admin -> create/deactivate assignment
    expected: 403
    DB changes: 0
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.nurse_workplace import NurseWorkplaceAssignment
from app.models.online_queue import QueueResource
from app.models.user import User

_BASE_PATH = "/api/v1/admin/nurse-workplace-assignments"


def _admin(db_session: Session, username: str) -> User:
    """A NON-superuser Admin — the role gate must do the work, not the bypass."""
    user = db_session.query(User).filter(User.username == username).first()
    if user:
        return user
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password="x",
        role="Admin",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _nurse(db_session: Session, username: str) -> User:
    user = db_session.query(User).filter(User.username == username).first()
    if user:
        return user
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password="x",
        role="Nurse",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _resource(db_session: Session, code: str) -> QueueResource:
    resource = (
        db_session.query(QueueResource).filter(QueueResource.code == code).first()
    )
    if resource:
        return resource
    resource = QueueResource(
        code=code,
        queue_tag=f"tag_{code}",
        display_name=f"Resource {code}",
        active=True,
        start_number_online=1,
        max_online_per_day=15,
        default_cabinet="c1",
    )
    db_session.add(resource)
    db_session.commit()
    db_session.refresh(resource)
    return resource


def _assignment_count(db_session: Session) -> int:
    return db_session.query(NurseWorkplaceAssignment).count()


@pytest.mark.integration
def test_deactivated_admin_token_gets_403_and_writes_no_assignments(
    client: TestClient, db_session: Session
) -> None:
    """Review P1 regression: unexpired JWT of a deactivated Admin is 403."""
    from tests.conftest import mint_access_token

    admin = _admin(db_session, "n2v2_admin_deactivated")
    # The token is minted WHILE the account is active — this is exactly
    # the reviewer's premise: deactivation must not rely on token expiry.
    stale_token = {"Authorization": f"Bearer {mint_access_token(admin)}"}

    # Admin B deactivates Admin A (no token-blacklist revoke exists).
    admin.is_active = False
    db_session.commit()

    # The gate must answer 403 BEFORE the handler runs, so the payload is
    # irrelevant — even ids that would 404/400 on a happy path never
    # reach the service layer.
    response = client.post(
        _BASE_PATH, json={"user_id": 1, "queue_resource_id": 1}, headers=stale_token
    )
    assert response.status_code == 403, response.text
    assert _assignment_count(db_session) == 0

    response = client.post(f"{_BASE_PATH}/1/deactivate", headers=stale_token)
    assert response.status_code == 403, response.text
    assert _assignment_count(db_session) == 0

    # The read side of the control plane is closed for the same token too.
    response = client.get(f"{_BASE_PATH}/1", headers=stale_token)
    assert response.status_code == 403, response.text
    response = client.get(_BASE_PATH, headers=stale_token)
    assert response.status_code == 403, response.text
    assert _assignment_count(db_session) == 0


@pytest.mark.integration
def test_active_admin_operates_the_control_plane(
    client: TestClient, db_session: Session
) -> None:
    """Positive control: the active-aware gate keeps the legitimate flow."""
    from tests.conftest import mint_access_token

    admin = _admin(db_session, "n2v2_admin_active")
    nurse = _nurse(db_session, "n2v2_nurse_target")
    resource = _resource(db_session, "n2v2_procedures")
    headers = {"Authorization": f"Bearer {mint_access_token(admin)}"}

    response = client.post(
        _BASE_PATH,
        json={"user_id": nurse.id, "queue_resource_id": resource.id},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    assignment_id = response.json()["id"]

    response = client.get(_BASE_PATH, headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1

    response = client.get(f"{_BASE_PATH}/{assignment_id}", headers=headers)
    assert response.status_code == 200

    response = client.post(f"{_BASE_PATH}/{assignment_id}/deactivate", headers=headers)
    assert response.status_code == 200
    assert response.json()["is_active"] is False


@pytest.mark.integration
def test_create_normalizes_blank_cabinet_override_to_null(
    client: TestClient, db_session: Session
) -> None:
    """Review P2 round 3 (PR #3333): D2's cabinet axis is NULL-coalesced.

    An empty admin form field serializes to cabinet_override="". The API
    normalizes it to NULL at the write boundary, so the stored row and the
    response report a consistent pair — override NULL, effective = the
    resource default — instead of the contradictory ""-override with
    default-effective that a D2-literal N2-3 consumer would read as a
    real cabinet.
    """
    from tests.conftest import mint_access_token

    admin = _admin(db_session, "n2v2_admin_blank")
    nurse = _nurse(db_session, "n2v2_nurse_blank")
    resource = _resource(db_session, "n2v2_procedures")  # default_cabinet "c1"
    headers = {"Authorization": f"Bearer {mint_access_token(admin)}"}

    response = client.post(
        _BASE_PATH,
        json={
            "user_id": nurse.id,
            "queue_resource_id": resource.id,
            "cabinet_override": "   ",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["cabinet_override"] is None
    assert body["effective_cabinet"] == "c1"

    row = (
        db_session.query(NurseWorkplaceAssignment)
        .filter(NurseWorkplaceAssignment.user_id == nurse.id)
        .one()
    )
    assert row.cabinet_override is None


@pytest.mark.integration
def test_nurse_role_is_403_on_the_control_plane(
    client: TestClient, db_session: Session
) -> None:
    """The role gate itself stays enforced (privilege-zero Nurse)."""
    from tests.conftest import mint_access_token

    nurse = _nurse(db_session, "n2v2_nurse_caller")
    headers = {"Authorization": f"Bearer {mint_access_token(nurse)}"}

    response = client.post(
        _BASE_PATH, json={"user_id": nurse.id, "queue_resource_id": 1}, headers=headers
    )
    assert response.status_code == 403, response.text
    assert _assignment_count(db_session) == 0


@pytest.mark.integration
def test_unauthenticated_requests_are_401(client: TestClient) -> None:
    response = client.post(_BASE_PATH, json={"user_id": 1, "queue_resource_id": 1})
    assert response.status_code == 401
    response = client.get(_BASE_PATH)
    assert response.status_code == 401
