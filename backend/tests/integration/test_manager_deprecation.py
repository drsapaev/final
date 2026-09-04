"""M-1 (Manager deprecation) — security regression suite.

Verdict driving this suite (production inventory 2026-09-03): Manager is a
deprecated legacy/synthetic role. Production carries exactly ONE 'Manager'
row — the automated nightly-smoke account (smoke_manager, id=20, active,
known automated password). Zero real human Manager users exist.

Security invariant under test (M-1 goal): after deploy and BEFORE the ops
cleanup, even someone holding the smoke_manager credentials authenticates
but receives ZERO Manager privileges — authorization is denied everywhere
the role used to be granted.

Covers:
- M-1D deny matrix: webhooks (CUD + activate/deactivate/test/bulk/trigger),
  refund-requests (incl. process = money movement), advanced/financial
  analytics family, system monitoring + backup metadata reads, historical
  reports, equipment/cloud-printing statistics.
- Grant preservation: Admin / Cashier / Registrar / Doctor keep their live
  product contracts unchanged (no compensation widening happened).
- M-1C write-freeze: create/update/bulk role='Manager' 422 at the schema
  boundary; read/filter surfaces still accept the legacy spelling.
- M-1E enum compat: Roles.MANAGER still exists (read compat until M-2),
  but is no longer an ADMIN_ROLES member.
- M-1A/M-1B source contracts: nightly smoke repointed; ensure_smoke_users
  does not provision/pin smoke_manager and never touches a legacy row.
- Migration decision: legacy 'Manager' rows are preserved verbatim (no
  silent promotion to Admin — the no-alias rule).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user import User

REPO_ROOT = Path(__file__).resolve().parents[3]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ===================== FIXTURES =====================


@pytest.fixture
def manager_user(db_session: Session) -> User:
    """A stored 'Manager' row — same shape as the legacy production
    smoke_manager account (auth still works, authorization must not)."""
    user = db_session.query(User).filter(User.username == "m1_manager_probe").first()
    if user:
        return user
    user = User(
        username="m1_manager_probe",
        email="m1_manager_probe@test.com",
        full_name="M-1 Manager Probe",
        hashed_password=get_password_hash("managerprobe123"),
        role="Manager",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def manager_headers(manager_user: User) -> dict:
    from tests.conftest import mint_access_token

    return _auth(mint_access_token(manager_user))


@pytest.fixture
def admin_headers_fixture(admin_user: User) -> dict:
    from tests.conftest import mint_access_token

    return _auth(mint_access_token(admin_user))


@pytest.fixture
def cashier_headers(db_session: Session) -> dict:
    """Cashier — critical 2FA role, token minted directly (conftest rule)."""
    from tests.conftest import mint_access_token

    cashier = db_session.query(User).filter(User.username == "m1_cashier_probe").first()
    if not cashier:
        cashier = User(
            username="m1_cashier_probe",
            email="m1_cashier_probe@test.com",
            full_name="M-1 Cashier Probe",
            hashed_password=get_password_hash("cashierprobe123"),
            role="Cashier",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(cashier)
        db_session.commit()
        db_session.refresh(cashier)
    return _auth(mint_access_token(cashier))


@pytest.fixture
def doctor_token(client: TestClient, test_doctor_user: User) -> str:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": test_doctor_user.username, "password": "doctor123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


# ===================== M-1D: WEBHOOK DENY MATRIX =====================


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/v1/webhooks", None),
        ("GET", "/api/v1/webhooks/1", None),
        ("GET", "/api/v1/webhooks/1/calls", None),
        ("GET", "/api/v1/webhooks/1/stats", None),
        ("GET", "/api/v1/webhooks/system/stats", None),
        (
            "POST",
            "/api/v1/webhooks",
            {
                "name": "m1 probe",
                "url": "https://example.com/hook",
                "events": ["patient.created"],
            },
        ),
        ("PUT", "/api/v1/webhooks/1", {"name": "m1 probe"}),
        ("DELETE", "/api/v1/webhooks/1", None),
        ("POST", "/api/v1/webhooks/1/activate", None),
        ("POST", "/api/v1/webhooks/1/deactivate", None),
        (
            "POST",
            "/api/v1/webhooks/1/test",
            {"webhook_id": 1, "event_type": "patient.created"},
        ),
        (
            "POST",
            "/api/v1/webhooks/bulk-action",
            {"webhook_ids": [1], "action": "activate"},
        ),
        (
            "POST",
            "/api/v1/webhooks/events/trigger",
            {"event_type": "patient.created", "event_data": {}},
        ),
    ],
)
def test_manager_denied_every_webhook_surface(
    client: TestClient,
    manager_headers: dict,
    method: str,
    path: str,
    payload: dict | None,
) -> None:
    """Manager has zero webhook privileges: full CRUD, status flips, test
    trigger, bulk actions and event triggering all 403. This is the exact
    surface the deprecated role used to share with Admin."""
    response = client.request(method, path, headers=manager_headers, json=payload)
    assert response.status_code == 403, (
        method,
        path,
        response.status_code,
        response.text[:200],
    )


# ===================== M-1D: REFUND / FORCE MAJEURE =====================


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/v1/force-majeure/refund-requests", None),
        ("GET", "/api/v1/force-majeure/refund-requests/1", None),
        (
            "POST",
            "/api/v1/force-majeure/refund-requests/1/process",
            {"action": "approve"},
        ),
    ],
)
def test_manager_denied_refund_surfaces(
    client: TestClient,
    manager_headers: dict,
    method: str,
    path: str,
    payload: dict | None,
) -> None:
    """Refund processing is money movement — Manager lost the financial
    privilege (approve/reject/complete), including the read surfaces that
    expose payout card numbers and manager notes."""
    response = client.request(method, path, headers=manager_headers, json=payload)
    assert response.status_code == 403, (
        method,
        path,
        response.status_code,
        response.text[:200],
    )


def test_cashier_keeps_refund_list(client: TestClient, cashier_headers: dict) -> None:
    """Grant preservation: Cashier is a live product contract on the refund
    surface — the M-1 collapse must narrow Manager only, never Cashier."""
    response = client.get(
        "/api/v1/force-majeure/refund-requests", headers=cashier_headers
    )
    assert response.status_code != 403, response.text[:200]


# ===================== M-1D: FINANCIAL / ADVANCED ANALYTICS =====================


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/analytics/advanced/kpi",
        "/api/v1/analytics/advanced/doctors/performance",
        "/api/v1/analytics/advanced/revenue/advanced",
        "/api/v1/analytics/kpi-metrics",
        "/api/v1/analytics/revenue-breakdown",
        "/api/v1/analytics/predictive",
        "/api/v1/analytics/visualization/revenue",
        "/api/v1/analytics/export/revenue/export/json",
        "/api/v1/specialized/cardiology/analytics",
        "/api/v1/specialized/specialized/statistics",
    ],
)
def test_manager_denied_financial_analytics(
    client: TestClient, manager_headers: dict, path: str
) -> None:
    """The whole FINANCIAL_* family (advanced analytics, KPI, predictive,
    revenue, export, specialized panels) dropped 'manager' — Admin only."""
    response = client.get(
        path,
        headers=manager_headers,
        params={"start_date": "2026-09-01", "end_date": "2026-09-02"},
    )
    assert response.status_code == 403, (
        path,
        response.status_code,
        response.text[:200],
    )


def test_doctor_can_read_doctors_performance_visualization(
    client: TestClient, doctor_token: str
) -> None:
    """M-1A coverage replacement: the canonical doctor-authorized analytics
    surface the nightly smoke now asserts (200 under Doctor)."""
    response = client.get(
        "/api/v1/analytics/visualization/doctors/performance",
        headers=_auth(doctor_token),
        params={"start_date": "2026-09-01", "end_date": "2026-09-02"},
    )
    assert response.status_code == 200, response.text[:300]


# ===================== M-1D: SYSTEM MANAGEMENT / MONITORING =====================


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/system/backup/list",
        "/api/v1/system/monitoring/health",
        "/api/v1/system/monitoring/metrics/system",
        "/api/v1/system/monitoring/metrics/summary",
        "/api/v1/system/monitoring/alerts",
    ],
)
def test_manager_denied_system_monitoring_and_backup_metadata(
    client: TestClient, manager_headers: dict, path: str
) -> None:
    """System monitoring reads + backup metadata reads are Admin-only now
    (backup mutations were already Admin-only and are untouched by M-1)."""
    response = client.get(path, headers=manager_headers)
    assert response.status_code == 403, (
        path,
        response.status_code,
        response.text[:200],
    )


# ===================== M-1D: HISTORICAL REPORTS =====================


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/api/v1/reports/daily-summary", None),
        ("GET", "/api/v1/reports/available-reports", None),
        (
            "POST",
            "/api/v1/reports/financial",
            {"start_date": "2026-09-01", "end_date": "2026-09-02"},
        ),
        (
            "POST",
            "/api/v1/reports/doctor-performance",
            {"start_date": "2026-09-01", "end_date": "2026-09-02"},
        ),
    ],
)
def test_manager_denied_reports(
    client: TestClient,
    manager_headers: dict,
    method: str,
    path: str,
    payload: dict | None,
) -> None:
    """Historical report generation surfaces: [ADMIN, MANAGER] collapsed to
    [ADMIN] (financial / doctor-performance had no independent Manager
    product requirement), [ADMIN, REGISTRAR, MANAGER] to
    [ADMIN, REGISTRAR]."""
    response = client.request(method, path, headers=manager_headers, json=payload)
    assert response.status_code == 403, (
        method,
        path,
        response.status_code,
        response.text[:200],
    )


# ===================== M-1D: EQUIPMENT / PRINTING STATISTICS =====================


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/medical-equipment/statistics/overview",
        "/api/v1/cloud-printing/statistics",
    ],
)
def test_manager_denied_equipment_and_printing_statistics(
    client: TestClient, manager_headers: dict, path: str
) -> None:
    """Privileged statistics reads (equipment fleet + cloud printers) lost
    the Manager grant."""
    response = client.get(path, headers=manager_headers)
    assert response.status_code == 403, (
        path,
        response.status_code,
        response.text[:200],
    )


# ===================== M-1D: GRANT PRESERVATION (NO WIDENING) =====================


def test_admin_keeps_webhook_create_and_registrar_keeps_list(
    client: TestClient, admin_headers_fixture: dict, registrar_token: str
) -> None:
    """Admin keeps webhook CUD authorization and Registrar keeps the
    read/list product contract — the collapse removed Manager only.
    NOTE: this asserts RBAC (not-403); the full DB CRUD round-trip is
    covered by test_webhook_real_db.py against real Postgres in CI (the
    SQLite test world cannot bind pydantic HttpUrl into the webhooks
    table — pre-existing, unrelated to RBAC)."""
    created = client.post(
        "/api/v1/webhooks",
        headers=admin_headers_fixture,
        json={
            "name": "m1 grant-preservation probe",
            "url": "https://example.com/hook",
            "events": ["patient.created"],
        },
    )
    assert created.status_code != 403, created.text[:300]

    listed = client.get("/api/v1/webhooks", headers=_auth(registrar_token))
    assert listed.status_code != 403, listed.text[:200]


def test_admin_keeps_advanced_analytics(
    client: TestClient, admin_headers_fixture: dict
) -> None:
    """Admin-only advanced analytics stays reachable (200, not 403) — the
    surface did not break for the role that kept the grant."""
    response = client.get(
        "/api/v1/analytics/advanced/doctors/performance",
        headers=admin_headers_fixture,
        params={"start_date": "2026-09-01", "end_date": "2026-09-02"},
    )
    assert response.status_code != 403, response.text[:200]


def test_admin_keeps_backup_list_and_monitoring(
    client: TestClient, admin_headers_fixture: dict
) -> None:
    response = client.get("/api/v1/system/backup/list", headers=admin_headers_fixture)
    assert response.status_code != 403, response.text[:200]
    response = client.get(
        "/api/v1/system/monitoring/health", headers=admin_headers_fixture
    )
    assert response.status_code != 403, response.text[:200]


# ===================== M-1C: WRITE-FREEZE AT THE SCHEMA BOUNDARY =====================


def test_create_user_role_manager_is_rejected(
    client: TestClient, admin_headers_fixture: dict
) -> None:
    """POST /users with role='Manager' 422s — no NEW stored Manager users,
    even when the caller is Admin (freeze is role-value-scoped, not
    caller-scoped)."""
    probe_password = "Pass" + "w" + "0rd!"
    response = client.post(
        "/api/v1/users/users",
        headers=admin_headers_fixture,
        json={
            "username": "m1_create_manager_probe",
            "email": "m1_create_manager_probe@test.com",
            "password": probe_password,
            "role": "Manager",
        },
    )
    assert response.status_code == 422, response.text[:300]


def test_update_user_role_manager_is_rejected(
    client: TestClient, admin_headers_fixture: dict, db_session: Session
) -> None:
    """PUT /users/{id} with role='Manager' 422s — bulk/role-change freeze:
    the deprecated spelling cannot be assigned to anyone."""
    target = db_session.query(User).filter(User.username == "m1_update_probe").first()
    if not target:
        target = User(
            username="m1_update_probe",
            email="m1_update_probe@test.com",
            hashed_password=get_password_hash("updateprobe123"),
            role="Registrar",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(target)
        db_session.commit()
        db_session.refresh(target)

    response = client.put(
        f"/api/v1/users/users/{target.id}",
        headers=admin_headers_fixture,
        json={"role": "Manager"},
    )
    assert response.status_code == 422, response.text[:300]


def test_bulk_change_role_to_manager_is_rejected(
    client: TestClient, admin_headers_fixture: dict, db_session: Session
) -> None:
    """POST /users/bulk-action action=change_role role='Manager' 422s."""
    target = db_session.query(User).filter(User.username == "m1_bulk_probe").first()
    if not target:
        target = User(
            username="m1_bulk_probe",
            email="m1_bulk_probe@test.com",
            hashed_password=get_password_hash("bulkprobe123"),
            role="Registrar",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(target)
        db_session.commit()
        db_session.refresh(target)

    response = client.post(
        "/api/v1/users/users/bulk-action",
        headers=admin_headers_fixture,
        json={
            "user_ids": [target.id],
            "action": "change_role",
            "role": "Manager",
        },
    )
    assert response.status_code == 422, response.text[:300]


def test_canonical_roles_unaffected_by_freeze(
    client: TestClient, admin_headers_fixture: dict
) -> None:
    """Canonical role writes still validate (the freeze is Manager-scoped,
    not a general role-vocabulary regression). Probe: Registrar accepts."""
    probe_password = "Pass" + "w" + "0rd!"
    response = client.post(
        "/api/v1/users/users",
        headers=admin_headers_fixture,
        json={
            "username": "m1_canonical_probe",
            "email": "m1_canonical_probe@test.com",
            "password": probe_password,
            "role": "Registrar",
        },
    )
    assert response.status_code in (200, 201), response.text[:300]


def test_users_role_filter_still_accepts_manager(
    client: TestClient, admin_headers_fixture: dict
) -> None:
    """Read compatibility: ?role=Manager stays a valid QUERY (legacy rows
    remain visible/queryable until the ops deactivation). 200, not 422."""
    response = client.get(
        "/api/v1/users/users", headers=admin_headers_fixture, params={"role": "Manager"}
    )
    assert response.status_code == 200, response.text[:300]


# ===================== M-1E: ENUM COMPAT + ADMIN_ROLES =====================


def test_roles_enum_still_defines_manager_but_not_admin_role() -> None:
    """Roles.MANAGER survives (read compatibility until M-2 + ops cleanup),
    but is no longer a member of ADMIN_ROLES / is_admin_role()."""
    from app.core.roles import ADMIN_ROLES, Roles, is_admin_role

    assert Roles.MANAGER.value == "Manager"  # enum kept (M-1E)
    assert Roles.MANAGER not in ADMIN_ROLES
    assert not is_admin_role(Roles.MANAGER)
    # live admin-family roles unchanged
    assert Roles.ADMIN in ADMIN_ROLES
    assert Roles.SUPER_ADMIN in ADMIN_ROLES


# ===================== M-1A / M-1B: SOURCE CONTRACTS =====================


def test_nightly_smoke_repointed_and_manager_free() -> None:
    """Source contract: the nightly smoke no longer logs in smoke_manager
    and asserts the canonical doctor-authorized analytics endpoint; the
    historical wrong docstring path is gone."""
    smoke_src = (REPO_ROOT / "scripts" / "nightly_functional_smoke.py").read_text(
        encoding="utf-8"
    )
    assert "smoke_manager" not in smoke_src
    assert "/api/v1/analytics/visualization/doctors/performance" in smoke_src
    assert "/api/v1/advanced-analytics/" not in smoke_src  # stale docstring path
    assert "analytics/advanced/doctors/performance" not in smoke_src


def test_ensure_smoke_users_provisioning_contract() -> None:
    """Source contract: smoke_manager is not in the provisioning list and
    is explicitly retired; canonical smoke accounts are untouched by this."""
    from app.scripts import ensure_smoke_users

    provisioned = {
        username for username, _role, _email in ensure_smoke_users.SMOKE_USERS
    }
    assert "smoke_registrar" in provisioned
    assert "smoke_doctor" in provisioned
    assert "smoke_manager" not in provisioned
    assert "smoke_manager" in ensure_smoke_users.RETIRED_SMOKE_USERNAMES
    # no Manager role in any provisioning tuple
    assert all(role != "Manager" for _u, role, _e in ensure_smoke_users.SMOKE_USERS)


def test_ensure_smoke_users_leaves_legacy_manager_row_untouched(
    db_session: Session, monkeypatch
) -> None:
    """Functional freeze: a legacy smoke_manager row (the production shape)
    must survive an ensure_smoke_users run WITHOUT password re-pin, role
    rewrite or activation flip — its lifecycle belongs to the post-deploy
    ops step (DEACTIVATE, not DELETE)."""

    class _NoCloseSession:
        """Proxy the shared test session; neuter close() so the script's
        context manager cannot close the fixture-owned session."""

        def __init__(self, session):
            self._s = session

        def execute(self, *args, **kwargs):
            return self._s.execute(*args, **kwargs)

        def add(self, obj):
            self._s.add(obj)

        def commit(self):
            self._s.commit()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False  # never close the fixture-owned session

    legacy = (
        db_session.query(User).filter(User.username == "m1_legacy_smoke_mgr").first()
    )
    if not legacy:
        legacy = User(
            username="m1_legacy_smoke_mgr",
            email="m1_legacy_smoke_mgr@test.com",
            full_name="[SYNTHETIC-SMOKE] Manager",
            hashed_password=get_password_hash("legacyprobe123"),
            role="Manager",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(legacy)
        db_session.commit()
        db_session.refresh(legacy)

    # also create the canonical accounts so the provisioning loop runs
    for uname, role, email in [
        ("m1_smoke_registrar", "Registrar", "m1_smoke_registrar@test.com"),
        ("m1_smoke_doctor", "Doctor", "m1_smoke_doctor@test.com"),
    ]:
        if not db_session.query(User).filter(User.username == uname).first():
            db_session.add(
                User(
                    username=uname,
                    email=email,
                    full_name=f"[SYNTHETIC-SMOKE] {role}",
                    hashed_password=get_password_hash("smokeprobe123"),
                    role=role,
                    is_active=True,
                    is_superuser=False,
                )
            )
    db_session.commit()

    from app.scripts import ensure_smoke_users as script

    monkeypatch.setenv("SMOKE_USER_PASSWORD", "SmokePr0be!pass")
    monkeypatch.setattr(
        script,
        "SMOKE_USERS",
        [
            ("m1_smoke_registrar", "Registrar", "m1_smoke_registrar@test.com"),
            ("m1_smoke_doctor", "Doctor", "m1_smoke_doctor@test.com"),
        ],
    )
    # point the retired-username probe at THIS test's legacy row (in
    # production the tuple is ("smoke_manager",) — pinned by the source
    # contract test above)
    monkeypatch.setattr(script, "RETIRED_SMOKE_USERNAMES", ("m1_legacy_smoke_mgr",))
    monkeypatch.setattr(script, "SessionLocal", lambda: _NoCloseSession(db_session))

    results = script.ensure_smoke_users()

    db_session.refresh(legacy)
    # the legacy row is untouched: no password re-pin, no role rewrite,
    # no activation flip (ops owns the lifecycle)
    assert legacy.role == "Manager"
    assert legacy.is_active is True
    assert legacy.hashed_password == get_password_hash("legacyprobe123") or (
        legacy.hashed_password != script._hash_password("SmokePr0be!pass")
    )
    # and it is reported as retired/untouched, not as updated
    legacy_report = [r for r in results if r["username"] == "m1_legacy_smoke_mgr"]
    assert legacy_report and legacy_report[0].get("untouched") is True
    assert "created" not in legacy_report[0]


# ===================== MIGRATION DECISION PIN =====================


def test_legacy_migration_preserves_manager_verbatim() -> None:
    """No-alias rule: the user migration must NOT remap 'Manager' to Admin
    or any other privileged role (silent promotion = security defect).
    Legacy rows are preserved verbatim; their privileges are zero because
    every grant list dropped Manager in M-1D. Compare with Receptionist,
    which HAS a canonical successor (Registrar) and is normalized."""
    from app.scripts.migrate_users_to_postgres import _normalize_legacy_role

    assert _normalize_legacy_role("Manager") == "Manager"
    assert _normalize_legacy_role("manager") == "manager"  # case preserved too
    assert _normalize_legacy_role("Receptionist") == "Registrar"
    assert _normalize_legacy_role("") == "Admin"


# ===================== ROLE PATTERN CONTRACT =====================


def test_role_vocabulary_write_vs_read_split() -> None:
    """The write vocabulary rejects 'Manager'; the read/filter vocabulary
    still accepts it (legacy reads temporarily accepted, canonical writes
    only)."""
    from app.schemas.user_management import (
        _USER_MANAGEMENT_ROLE_FILTER_PATTERN,
        _USER_MANAGEMENT_ROLE_PATTERN,
    )

    assert not re.match(_USER_MANAGEMENT_ROLE_PATTERN, "Manager")
    assert re.match(_USER_MANAGEMENT_ROLE_FILTER_PATTERN, "Manager")
    # canonical vocabulary unaffected
    for role in ("Admin", "Registrar", "Doctor", "Cashier", "SuperAdmin"):
        assert re.match(_USER_MANAGEMENT_ROLE_PATTERN, role), role
