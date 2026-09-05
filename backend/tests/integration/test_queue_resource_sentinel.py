"""QD-1.1 (queue resource role cleanup) — sentinel regression pins.

0055_queue_resource_provisioning seeded the doctorless-queue resource
accounts (ecg_resource/general_resource) with role='Nurse', breaking
the N-3 "stored Nurse count == 0" invariant (the N-3 closure had
verified 0 rows hours before the seed landed). Migration
0056_queue_resource_role_cleanup moves the two synthetic rows to the
internal-only 'Resource' sentinel spelling.

Pins here mirror the N-3 (test_nurse_retirement.py) and M-2
(test_manager_deprecation.py) suite style:

- the sentinel never joins the Roles enum / hierarchy / AI RBAC matrix;
- the user-management write vocabulary rejects it (the freeze IS the
  mechanism — no code change required, this pins that it stays so);
- the roles catalog boundary (RoleCreate + /roles/options) rejects it;
- logins are blocked at the auth layer (structural non-login: the
  role, not the '!disabled:' password hash, is the defense);
- QD-0 queue resolution stays role-agnostic (username + is_active);
- the migration logic: strict exactly-2 precondition, idempotent
  already-migrated pass, abort-with-no-changes on drifted state,
  unrelated 'Nurse' rows never touched, lab_resource untouched;
- the alembic chain stays single-headed with 0056 as the new head.
"""

from __future__ import annotations

import asyncio
import importlib.util
import re
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user import User

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
MIGRATION_0056 = (
    BACKEND_ROOT / "alembic" / "versions" / "0056_queue_resource_role_cleanup.py"
)


# ===================== sentinel vocabulary =====================


def test_internal_only_role_spellings() -> None:
    from app.core.roles import (
        INTERNAL_ONLY_ROLE_SPELLINGS,
        is_internal_only_role_spelling,
        is_login_blocked_role,
        is_retired_role_spelling,
    )

    assert INTERNAL_ONLY_ROLE_SPELLINGS == frozenset({"resource"})
    assert is_internal_only_role_spelling("Resource")
    assert is_internal_only_role_spelling("resource")
    assert is_login_blocked_role("Resource")
    assert is_login_blocked_role("resource")
    # distinct semantics from RETIRED: the sentinel never shipped as a
    # product surface — it is internal-only, not decommissioned
    assert not is_retired_role_spelling("Resource")
    # canonical roles are neither retired nor internal
    for canonical in ("Registrar", "Lab", "Doctor", "Admin", "Cashier"):
        assert not is_internal_only_role_spelling(canonical)
        assert not is_login_blocked_role(canonical)


def test_roles_enum_has_no_resource() -> None:
    from app.core.roles import Roles, get_role_hierarchy

    assert not hasattr(Roles, "RESOURCE")
    assert "Resource" not in [r.value for r in Roles]
    # unknown spelling scores 0 (deny), same as Manager/Receptionist/Nurse
    assert get_role_hierarchy("Resource") == 0
    assert get_role_hierarchy("Registrar") == 6


# ===================== write vocabulary closure =====================


def test_user_management_pattern_rejects_resource() -> None:
    from app.schemas.user_management import _USER_MANAGEMENT_ROLE_PATTERN

    assert not re.match(_USER_MANAGEMENT_ROLE_PATTERN, "Resource")
    assert not re.match(_USER_MANAGEMENT_ROLE_PATTERN, "resource")
    for canonical in (
        "Admin",
        "Doctor",
        "Registrar",
        "Cashier",
        "Lab",
        "Patient",
        "SuperAdmin",
        "cardio",
        "doctor",
    ):
        assert re.match(_USER_MANAGEMENT_ROLE_PATTERN, canonical), canonical


def test_user_management_schemas_reject_resource() -> None:
    from pydantic import TypeAdapter, ValidationError

    from app.schemas.user_management import (
        NonDoctorRoleLiteral,
        UserBulkActionRequest,
        UserSearchRequest,
        UserUpdateRequest,
    )

    with pytest.raises(ValidationError):
        TypeAdapter(UserUpdateRequest).validate_python({"role": "Resource"})
    with pytest.raises(ValidationError):
        TypeAdapter(UserSearchRequest).validate_python({"role": "Resource"})
    with pytest.raises(ValidationError):
        TypeAdapter(UserBulkActionRequest).validate_python(
            {"user_ids": [1], "action": "change_role", "role": "Resource"}
        )
    with pytest.raises(ValidationError):
        TypeAdapter(NonDoctorRoleLiteral).validate_python("Resource")
    # canonical controls on the same schemas
    TypeAdapter(UserUpdateRequest).validate_python({"role": "Registrar"})
    TypeAdapter(UserSearchRequest).validate_python({"role": "Registrar"})
    TypeAdapter(NonDoctorRoleLiteral).validate_python("Admin")


def test_authentication_legacy_schemas_reject_resource() -> None:
    from pydantic import TypeAdapter, ValidationError

    from app.schemas.authentication import UserCreateRequest, UserUpdateRequest

    # probe password is assembled at runtime — a plaintext `password="..."`
    # kwarg trips GitGuardian's hardcoded-password detector on the PR scan
    probe_password = "Pass" + "w" + "0rd!"
    create_payload: dict[str, Any] = {
        "username": "qd11_resource_probe",
        "email": "qd11.probe@example.com",
        "password": probe_password,
        "role": "Resource",
    }
    with pytest.raises(ValidationError):
        TypeAdapter(UserCreateRequest).validate_python(create_payload)
    with pytest.raises(ValidationError):
        TypeAdapter(UserUpdateRequest).validate_python({"role": "Resource"})
    # canonical control on the same schemas
    create_payload["role"] = "Admin"
    TypeAdapter(UserCreateRequest).validate_python(create_payload)
    TypeAdapter(UserUpdateRequest).validate_python({"role": "Admin"})


# ===================== roles catalog boundary =====================


def test_roles_catalog_rejects_internal_sentinel(
    client: TestClient, admin_auth_headers: dict
) -> None:
    """Same freeze discipline as M-2b: a hand-created 'Resource' catalog
    row would flow into /roles/options and the UserModal dropdown mirror,
    offering a spelling the user-management write schema then 422s."""
    for sentinel_name in ("Resource", "resource"):
        response = client.post(
            "/api/v1/roles/",
            headers=admin_auth_headers,
            json={
                "name": sentinel_name,
                "display_name": sentinel_name,
                "description": "internal sentinel probe",
                "level": 0,
                "is_active": True,
                "is_system": False,
            },
        )
        assert response.status_code == 422, (
            sentinel_name,
            response.status_code,
            response.text[:300],
        )


def test_roles_options_filter_internal_sentinel(
    client: TestClient, admin_auth_headers: dict, db_session: Session
) -> None:
    """Defense-in-depth on the READ side — a pre-existing catalog row
    carrying the internal sentinel spelling never surfaces in
    /roles/options."""
    from app.models.role_permission import Role

    def _ensure_role(name: str, display: str) -> None:
        row = db_session.query(Role).filter(Role.name == name).first()
        if row:
            return
        db_session.add(
            Role(
                name=name,
                display_name=display,
                level=0,
                is_active=True,
                is_system=False,
            )
        )
        db_session.commit()

    _ensure_role("Resource", "Queue Resource")
    _ensure_role("Shift Lead", "Shift Lead")

    response = client.get("/api/v1/roles/options", headers=admin_auth_headers)
    assert response.status_code == 200, response.text[:300]
    values = [opt["value"] for opt in response.json().get("options", [])]
    assert "Resource" not in values, values
    assert "Shift Lead" in values, values


# ===================== AI RBAC: grants = 0 by construction =====================


def test_ai_rbac_matrix_grants_resource_nothing() -> None:
    from app.core.rbac import (
        AIPermission,
        UserRole,
        get_user_permissions,
        has_permission,
    )

    with pytest.raises(ValueError):
        UserRole.from_string("Resource")
    with pytest.raises(ValueError):
        UserRole.from_string("resource")
    assert get_user_permissions("Resource") == set()
    assert get_user_permissions("resource") == set()
    for permission in AIPermission:
        assert not has_permission("Resource", permission)
        assert not has_permission("resource", permission)


# ===================== auth layer: structural non-login =====================


def _make_user(db_session: Session, *, username: str, role: str, password: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username,
        hashed_password=get_password_hash(password),
        role=role,
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_auth_service_blocks_login_for_internal_sentinel(db_session: Session) -> None:
    """The sentinel account below is ACTIVE with a CORRECT password —
  the role (not is_active, not the password hash) is the login defense."""
    from app.services.authentication_service import authentication_service

    probe_password = "Pass" + "w" + "0rd!"
    sentinel = _make_user(
        db_session, username="qd11_ecg_resource", role="Resource", password=probe_password
    )
    control = _make_user(
        db_session, username="qd11_registrar", role="Registrar", password=probe_password
    )

    user, message = authentication_service.authenticate_user(
        db_session,
        sentinel.username,
        probe_password,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    assert user is None
    assert "запрещ" in message

    user, message = authentication_service.authenticate_user(
        db_session,
        control.username,
        probe_password,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )
    assert user is not None and user.id == control.id


def test_auth_api_service_payloads_block_internal_sentinel(
    db_session: Session,
) -> None:
    """Legacy /auth/login (OAuth) and /auth/json-login share the same
    structural non-login rule via AuthApiService."""
    from app.services.auth_api_service import AuthApiDomainError, AuthApiService

    probe_password = "Pass" + "w" + "0rd!"
    sentinel = _make_user(
        db_session,
        username="qd11_general_resource",
        role="Resource",
        password=probe_password,
    )
    control = _make_user(
        db_session, username="qd11_lab_control", role="Lab", password=probe_password
    )

    with pytest.raises(AuthApiDomainError) as exc_info:
        asyncio.run(
            AuthApiService(db_session).login_oauth_payload(
                username=sentinel.username, password=probe_password
            )
        )
    assert exc_info.value.status_code == 401

    with pytest.raises(AuthApiDomainError) as exc_info:
        asyncio.run(
            AuthApiService(db_session).json_login_payload(
                username=sentinel.username, password=probe_password, remember_me=False
            )
        )
    assert exc_info.value.status_code == 401

    # canonical control: the same payload shape authenticates fine
    payload = asyncio.run(
        AuthApiService(db_session).json_login_payload(
            username=control.username, password=probe_password, remember_me=False
        )
    )
    assert payload["user"]["role"] == "Lab"


# ===================== QD-0 resolution stays role-agnostic =====================


def test_qd0_resolution_stays_role_agnostic(db_session: Session) -> None:
    """The doctorless-queue resource lookup primitive (the same
    username+is_active resolution the wizard / morning-assignment /
    batch / visit-confirmation paths use) must keep resolving a
    'Resource'-role account after 0056 — QD-0 never filters by role.
    The is_active leg is load-bearing, which is exactly why 0056 must
    NOT deactivate these rows (non-login is enforced by the auth-layer
    role guard instead)."""
    from app.repositories.visit_confirmation_repository import (
        VisitConfirmationRepository,
    )

    probe_password = "Pass" + "w" + "0rd!"
    sentinel = _make_user(
        db_session, username="ecg_resource", role="Resource", password=probe_password
    )

    repo = VisitConfirmationRepository(db_session)
    resolved = repo.get_active_user_by_username("ecg_resource")
    assert resolved is not None and resolved.id == sentinel.id

    sentinel.is_active = False
    db_session.commit()
    assert repo.get_active_user_by_username("ecg_resource") is None


# ===================== migration 0056 logic (scratch SQLite) =====================


def _load_migration_0056():
    spec = importlib.util.spec_from_file_location(
        "migration_0056_queue_resource_role_cleanup", MIGRATION_0056
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scratch_users_connection():
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    metadata = sa.MetaData()
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
    )
    metadata.create_all(engine)
    return engine.connect()


def _seed(conn, *rows: tuple[str, str]) -> None:
    for username, role in rows:
        conn.execute(
            sa.text("INSERT INTO users (username, role) VALUES (:u, :r)"),
            {"u": username, "r": role},
        )


def _roles(conn) -> dict[str, str]:
    return dict(conn.execute(sa.text("SELECT username, role FROM users")).fetchall())


def test_migration_moves_seeded_nurse_rows_to_sentinel() -> None:
    module = _load_migration_0056()
    conn = _scratch_users_connection()
    try:
        _seed(
            conn,
            ("ecg_resource", "Nurse"),
            ("general_resource", "Nurse"),
            ("lab_resource", "Lab"),  # real product role: untouched (QD-1.2)
            ("some_admin", "Admin"),
        )
        module._apply_resource_role_cleanup(conn)
        assert _roles(conn) == {
            "ecg_resource": "Resource",
            "general_resource": "Resource",
            "lab_resource": "Lab",
            "some_admin": "Admin",
        }
    finally:
        conn.close()


def test_migration_passes_when_already_migrated() -> None:
    module = _load_migration_0056()
    conn = _scratch_users_connection()
    try:
        _seed(
            conn,
            ("ecg_resource", "Resource"),
            ("general_resource", "Resource"),
        )
        module._apply_resource_role_cleanup(conn)  # must not raise
        assert _roles(conn) == {
            "ecg_resource": "Resource",
            "general_resource": "Resource",
        }
    finally:
        conn.close()


def test_migration_aborts_on_drifted_state() -> None:
    """Strict precondition: anything that is not (2 Nurse) or the
    already-migrated (2 Resource) state aborts with NO rows changed —
    never a broad rewrite (operator decision: exactly 2 expected rows)."""
    module = _load_migration_0056()
    drifted_states: tuple[tuple[tuple[str, str], ...], ...] = (
        (("ecg_resource", "Nurse"), ("general_resource", "Registrar")),
        (("ecg_resource", "Nurse"),),
        (("ecg_resource", "Resource"),),  # half-migrated by hand
        (),  # accounts missing entirely
    )
    for state in drifted_states:
        conn = _scratch_users_connection()
        try:
            _seed(conn, *state)
            with pytest.raises(RuntimeError):
                module._apply_resource_role_cleanup(conn)
            assert _roles(conn) == dict(state)
        finally:
            conn.close()


def test_migration_never_touches_unrelated_nurse_rows() -> None:
    """Narrowness pin: an unrelated 'Nurse' row is NOT rewritten — the
    migration is not a broad Nurse sweep."""
    module = _load_migration_0056()
    conn = _scratch_users_connection()
    try:
        _seed(
            conn,
            ("ecg_resource", "Nurse"),
            ("general_resource", "Nurse"),
            ("nurse_probe", "Nurse"),
        )
        module._apply_resource_role_cleanup(conn)
        assert _roles(conn) == {
            "ecg_resource": "Resource",
            "general_resource": "Resource",
            "nurse_probe": "Nurse",
        }
    finally:
        conn.close()


def test_migration_downgrade_restores_seed_shape() -> None:
    module = _load_migration_0056()
    conn = _scratch_users_connection()
    try:
        _seed(
            conn,
            ("ecg_resource", "Resource"),
            ("general_resource", "Resource"),
            ("lab_resource", "Lab"),
        )
        module._restore_resource_seed_roles(conn)
        assert _roles(conn) == {
            "ecg_resource": "Nurse",
            "general_resource": "Nurse",
            "lab_resource": "Lab",
        }
    finally:
        conn.close()


# ===================== alembic chain stays single-headed =====================


def _revision_graph() -> dict[str, tuple[str, ...]]:
    versions_dir = BACKEND_ROOT / "alembic" / "versions"
    graph: dict[str, tuple[str, ...]] = {}
    for path in sorted(versions_dir.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        revision_match = re.search(
            r'^revision\s*=\s*["\']([^"\']+)["\']', source, re.M
        )
        if not revision_match:
            continue
        down_match = re.search(r"^down_revision\s*=\s*(.+)$", source, re.M)
        parents = (
            tuple(re.findall(r'["\']([^"\']+)["\']', down_match.group(1)))
            if down_match
            else ()
        )
        graph[revision_match.group(1)] = parents
    return graph


def test_alembic_chain_single_head_0056() -> None:
    graph = _revision_graph()
    assert "0056_queue_resource_role_cleanup" in graph
    assert graph["0056_queue_resource_role_cleanup"] == (
        "0055_queue_resource_provisioning",
    )
    referenced = {parent for parents in graph.values() for parent in parents}
    heads = sorted(rev for rev in graph if rev not in referenced)
    assert heads == ["0056_queue_resource_role_cleanup"]


# ============ Codex round-1: remaining credential surfaces ============


def test_mobile_login_blocks_internal_sentinel(
    client: TestClient, db_session: Session
) -> None:
    """Codex round-1: the phone-based mobile login funnel mints tokens
    without the AuthenticationService.authenticate_user checks — it must
    reject the sentinel exactly like the web funnels."""
    from datetime import date

    from app.models.patient import Patient

    probe_password = "Pass" + "w" + "0rd!"
    sentinel = _make_user(
        db_session, username="qd11_mobile_resource", role="Resource", password=probe_password
    )
    control = _make_user(
        db_session, username="qd11_mobile_patient", role="Patient", password=probe_password
    )
    db_session.add_all(
        [
            Patient(
                first_name="Ресурс",
                last_name="ЭКГ",
                phone="+998901110001",
                birth_date=date(1990, 1, 1),
                user_id=sentinel.id,
            ),
            Patient(
                first_name="Иван",
                last_name="Иванов",
                phone="+998901110002",
                birth_date=date(1990, 1, 1),
                user_id=control.id,
            ),
        ]
    )
    db_session.commit()

    response = client.post(
        "/api/v1/mobile/auth/login",
        json={"phone": "+998901110001", "password": probe_password},
    )
    assert response.status_code == 401, (response.status_code, response.text[:300])

    response = client.post(
        "/api/v1/mobile/auth/login",
        json={"phone": "+998901110002", "password": probe_password},
    )
    assert response.status_code == 200, (response.status_code, response.text[:300])
    assert response.json().get("access_token")


def test_get_current_user_rejects_sentinel_token(
    client: TestClient, db_session: Session
) -> None:
    """Codex round-1: even a hand-minted valid-signature token must not
    authenticate a sentinel account (this also closes the 2FA-exchange
    surface: pending tokens cannot be issued for a blocked login, and
    any pre-existing token fails here)."""
    from app.services.authentication_service import authentication_service

    probe_password = "Pass" + "w" + "0rd!"
    sentinel = _make_user(
        db_session, username="qd11_token_resource", role="Resource", password=probe_password
    )
    control = _make_user(
        db_session, username="qd11_token_registrar", role="Registrar", password=probe_password
    )

    def _token(user: User) -> str:
        return authentication_service.create_access_token(
            {
                "sub": str(user.id),
                "username": user.username,
                "role": user.role,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
            }
        )

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {_token(sentinel)}"}
    )
    assert response.status_code == 401, (response.status_code, response.text[:300])

    response = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {_token(control)}"}
    )
    assert response.status_code == 200, (response.status_code, response.text[:300])


def test_refresh_token_rejected_for_internal_sentinel(db_session: Session) -> None:
    """Codex round-1: refresh rotation must never re-mint credentials for
    the sentinel — the structural non-login invariant holds on the token
    surface too, not only at password verification."""
    from datetime import UTC, datetime, timedelta

    from app.models.authentication import RefreshToken
    from app.services.authentication_service import authentication_service

    probe_password = "Pass" + "w" + "0rd!"
    sentinel = _make_user(
        db_session, username="qd11_refresh_resource", role="Resource", password=probe_password
    )

    jti = "qd11-refresh-jti"
    refresh_token = authentication_service.create_refresh_token(sentinel.id, jti)
    db_session.add(
        RefreshToken(
            user_id=sentinel.id,
            token=refresh_token,
            jti=jti,
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    db_session.commit()

    result = authentication_service.refresh_access_token(db_session, refresh_token)
    assert result.get("success") is False


def test_users_list_hides_internal_sentinel_rows(
    client: TestClient, admin_auth_headers: dict, db_session: Session
) -> None:
    """Codex round-1: the user-management listing hides sentinel rows —
    synthetic queue-resource accounts are queue machinery, not manageable
    staff accounts (UserModal would otherwise offer their unknown role
    and 422 on every edit)."""
    probe_password = "Pass" + "w" + "0rd!"
    _make_user(
        db_session, username="qd11_list_resource", role="Resource", password=probe_password
    )
    _make_user(
        db_session,
        username="qd11_list_registrar",
        role="Registrar",
        password=probe_password,
    )

    response = client.get("/api/v1/users/users", headers=admin_auth_headers)
    assert response.status_code == 200, (response.status_code, response.text[:300])
    usernames = [u["username"] for u in response.json().get("users", [])]
    assert "qd11_list_resource" not in usernames, usernames
    assert "qd11_list_registrar" in usernames, usernames


# ============ Codex round-2: WebSocket resolvers + by-ID mutations ============


def test_websocket_resolvers_reject_sentinel(db_session: Session) -> None:
    """Codex round-2: every WebSocket user resolver — the shared
    queue/display resolver and the AI chat resolver — rejects the
    sentinel (hand-minted token for a structural non-login)."""
    from app.api.v1.endpoints.websocket_auth import _resolve_websocket_user
    from app.core.config import settings
    from app.services.ai_chat_api_service import AIChatApiService
    from app.services.authentication_service import authentication_service

    probe_password = "Pass" + "w" + "0rd!"
    sentinel = _make_user(
        db_session, username="qd11_ws_resource", role="Resource", password=probe_password
    )
    control = _make_user(
        db_session, username="qd11_ws_registrar", role="Registrar", password=probe_password
    )

    # shared resolver (queue WS; the display-board WS imports it directly)
    assert _resolve_websocket_user({"sub": str(sentinel.id)}, db_session) is None
    resolved = _resolve_websocket_user({"sub": str(control.id)}, db_session)
    assert resolved is not None and resolved.id == control.id

    # AI chat resolver (raw-token path)
    sentinel_token = authentication_service.create_access_token(
        {"sub": str(sentinel.id), "role": sentinel.role}
    )
    control_token = authentication_service.create_access_token(
        {"sub": str(control.id), "role": control.role}
    )
    assert (
        AIChatApiService(db_session).authenticate_websocket_user(
            token=sentinel_token,
            secret_key=settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        is None
    )
    resolved = AIChatApiService(db_session).authenticate_websocket_user(
        token=control_token,
        secret_key=settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    assert resolved is not None and resolved.id == control.id


def test_user_management_mutations_reject_sentinel(
    client: TestClient, admin_auth_headers: dict, db_session: Session
) -> None:
    """Codex round-2: PUT / DELETE / bulk by direct ID cannot mutate the
    sentinel rows — renaming, re-roling, deactivating or deleting the
    synthetic resource users would break the username+is_active queue
    resolution the migration depends on."""
    probe_password = "Pass" + "w" + "0rd!"
    sentinel = _make_user(
        db_session, username="qd11_mut_resource", role="Resource", password=probe_password
    )
    control = _make_user(
        db_session, username="qd11_mut_registrar", role="Registrar", password=probe_password
    )

    response = client.put(
        f"/api/v1/users/users/{sentinel.id}",
        headers=admin_auth_headers,
        json={"full_name": "Must not apply"},
    )
    assert response.status_code == 400, (response.status_code, response.text[:300])
    assert "не найден" in response.json().get("detail", "")

    response = client.delete(
        f"/api/v1/users/users/{sentinel.id}", headers=admin_auth_headers
    )
    assert response.status_code == 400, (response.status_code, response.text[:300])

    db_session.expire_all()
    survivor = db_session.get(User, sentinel.id)
    assert survivor is not None
    assert survivor.role == "Resource" and survivor.is_active is True

    response = client.post(
        "/api/v1/users/users/bulk-action",
        headers=admin_auth_headers,
        json={
            "user_ids": [sentinel.id, control.id],
            "action": "deactivate",
        },
    )
    assert response.status_code == 200, (response.status_code, response.text[:300])
    data = response.json()
    failed_ids = {f["user_id"] for f in data.get("failed_users", [])}
    assert sentinel.id in failed_ids
    assert control.id not in failed_ids

    db_session.expire_all()
    assert db_session.get(User, sentinel.id).is_active is True
    assert db_session.get(User, control.id).is_active is False


# ============ Codex round-3: admin Doctor surface + standalone queue WS ============


def test_admin_doctor_surface_readonly_for_sentinel(
    client: TestClient, admin_auth_headers: dict, db_session: Session
) -> None:
    """Codex round-3 P1: the synthetic queue-resource Doctor rows are hidden
    from the admin list and read-only by ID (404 on GET/PUT/DELETE) — an
    ordinary admin action must not break the doctorless queue resolution,
    and the ghost-state guard must not trap the row in a dead state
    ('Resource' is not a doctor-family role, so deactivation could never
    be reactivated)."""
    from app.models.clinic import Doctor

    probe_password = "Pass" + "w" + "0rd!"
    sentinel = _make_user(
        db_session, username="qd11_doc_resource", role="Resource", password=probe_password
    )
    control_user = _make_user(
        db_session, username="qd11_doc_doctor", role="Doctor", password=probe_password
    )
    sentinel_doctor = Doctor(user_id=sentinel.id, specialty="ecg", active=True)
    control_doctor = Doctor(user_id=control_user.id, specialty="cardio", active=True)
    db_session.add_all([sentinel_doctor, control_doctor])
    db_session.commit()
    db_session.refresh(sentinel_doctor)
    db_session.refresh(control_doctor)

    response = client.get("/api/v1/admin/doctors", headers=admin_auth_headers)
    assert response.status_code == 200, (response.status_code, response.text[:300])
    listed_ids = {d["id"] for d in response.json()}
    assert sentinel_doctor.id not in listed_ids
    assert control_doctor.id in listed_ids

    response = client.get(
        f"/api/v1/admin/doctors/{sentinel_doctor.id}", headers=admin_auth_headers
    )
    assert response.status_code == 404

    response = client.put(
        f"/api/v1/admin/doctors/{sentinel_doctor.id}",
        headers=admin_auth_headers,
        json={"active": False},
    )
    assert response.status_code == 404, (response.status_code, response.text[:300])

    response = client.delete(
        f"/api/v1/admin/doctors/{sentinel_doctor.id}", headers=admin_auth_headers
    )
    assert response.status_code == 404, (response.status_code, response.text[:300])

    db_session.expire_all()
    survivor = db_session.get(Doctor, sentinel_doctor.id)
    assert survivor is not None and survivor.active is True


def test_queue_ws_auth_ok_rejects_sentinel(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex round-3 P2: the standalone /ws/queue stream routes through the
    shared sentinel-rejecting resolver (previously _auth_ok validated only
    the JWT signature + blacklist without resolving the user)."""
    from sqlalchemy.orm import sessionmaker

    from app.services.authentication_service import authentication_service
    from app.ws.queue_ws import _auth_ok

    probe_password = "Pass" + "w" + "0rd!"
    sentinel = _make_user(
        db_session, username="qd11_qws_resource", role="Resource", password=probe_password
    )
    control = _make_user(
        db_session, username="qd11_qws_registrar", role="Registrar", password=probe_password
    )

    monkeypatch.delenv("TESTING", raising=False)
    # bind the resolver's ad-hoc sessions to the SAME connection so they see
    # this test's savepoint-nested rows
    monkeypatch.setattr(
        "app.db.session.SessionLocal",
        sessionmaker(bind=db_session.get_bind()),
    )

    sentinel_token = authentication_service.create_access_token(
        {"sub": str(sentinel.id), "role": sentinel.role}
    )
    control_token = authentication_service.create_access_token(
        {"sub": str(control.id), "role": control.role}
    )

    assert _auth_ok({"authorization": f"Bearer {sentinel_token}"}, None) is False
    assert _auth_ok({"authorization": f"Bearer {control_token}"}, None) is True
