"""M-1 (Manager deprecation) — RBAC regression contract.

Business decision (2026-09-03): Manager is a deprecated legacy/synthetic
role, NOT a product role. Production holds exactly one legacy row
(smoke_manager, id=20, is_active=true) awaiting post-deploy ops
deactivation; human Manager users = 0.

Invariants pinned by this module:
  1.  Manager is DENIED (403) on every privileged grant it historically
      held: webhook mutations, force-majeure refund processing, financial
      / advanced / KPI / predictive / export analytics, specialized-panel
      financial analytics, financial/doctor-performance reports, system
      monitoring/backup reads, equipment/cloud-printing statistics.
  2.  Canonical roles RETAIN their approved access: Admin (webhooks,
      analytics, system reads), Cashier (refund processing), Registrar
      (report/webhook reads), Doctor (visualization analytics).
  3.  Write-freeze: user create / update / bulk change-role reject
      role=Manager (422) — no new Manager accounts can be provisioned.
  4.  Read compatibility: the users search/filter surface still accepts
      role=Manager (200) while the legacy production row survives
      (mirrors the Receptionist REC-1 compatibility rule).
  5.  Enum compatibility: Roles.MANAGER stays deserializable (production
      row still authenticates) but is NO LONGER an ADMIN_ROLES member —
      authentication is not authorization.
  6.  Smoke provisioning: ensure_smoke_users neither creates nor touches
      a Manager account; the nightly smoke no longer logs in as
      smoke_manager and probes the canonical-Doctor visualization
      endpoint instead of the manager-gated advanced endpoint.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.roles import (
    ADMIN_ROLES,
    Roles,
    is_admin_role,
)
from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.user_management import (
    UserUpdateRequest,
    _USER_MANAGEMENT_ROLE_FILTER_PATTERN,
    _USER_MANAGEMENT_ROLE_PATTERN,
)
from tests.conftest import mint_access_token

REPO_ROOT = Path(__file__).resolve().parents[3]


# ===================== FIXTURES =====================


@pytest.fixture
def manager_user(db_session: Session) -> User:
    """Legacy synthetic Manager account (mirrors prod smoke_manager)."""
    user = User(
        username="manager_deprecation_probe",
        email="manager_deprecation_probe@test.com",
        hashed_password=get_password_hash("manager123"),
        role="Manager",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def manager_token(manager_user: User) -> str:
    """Manager is not a CRITICAL_2FA role — but mint directly anyway so
    this suite cannot break if 2FA enforcement is ever widened."""
    return mint_access_token(manager_user)


@pytest.fixture
def admin_token(admin_user: User) -> str:
    return mint_access_token(admin_user)


@pytest.fixture
def doctor_token(test_doctor_user: User) -> str:
    return mint_access_token(test_doctor_user)


@pytest.fixture
def registrar_token(registrar_user: User) -> str:
    return mint_access_token(registrar_user)


@pytest.fixture
def cashier_user(db_session: Session) -> User:
    user = db_session.scalar(select(User).where(User.username == "m1_cashier_probe"))
    if user is None:
        user = User(
            username="m1_cashier_probe",
            email="m1_cashier_probe@test.com",
            hashed_password=get_password_hash("cashier123"),
            role="Cashier",
            is_active=True,
            is_superuser=False,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture
def cashier_token(cashier_user: User) -> str:
    return mint_access_token(cashier_user)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ===================== 1. WEBHOOK MUTATIONS DENIED =====================

WEBHOOK_CREATE_BODY = {
    "name": "m1-deny-probe",
    "url": "https://example.invalid/m1-deny-probe",
    "events": ["patient.created"],
}
WEBHOOK_UPDATE_BODY = {"name": "m1-deny-probe-renamed"}
WEBHOOK_TEST_BODY = {"event_type": "patient.created", "test_data": {"probe": True}}
WEBHOOK_BULK_BODY = {"webhook_ids": [1], "action": "activate"}
WEBHOOK_EVENT_BODY = {"event_type": "patient.created", "event_data": {"probe": True}}


class TestManagerDeniedWebhookMutations:
    """M-1 requirement 1: Manager denied webhook create/update/delete/
    activate/deactivate/test/bulk/trigger (the admin-only cleanup
    mutations were already Admin-only and stay untouched)."""

    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("POST", "/api/v1/webhooks/", WEBHOOK_CREATE_BODY),
            ("PUT", "/api/v1/webhooks/1", WEBHOOK_UPDATE_BODY),
            ("DELETE", "/api/v1/webhooks/1", None),
            ("POST", "/api/v1/webhooks/1/activate", None),
            ("POST", "/api/v1/webhooks/1/deactivate", None),
            ("POST", "/api/v1/webhooks/1/test", WEBHOOK_TEST_BODY),
            ("POST", "/api/v1/webhooks/bulk-action", WEBHOOK_BULK_BODY),
            ("POST", "/api/v1/webhooks/events/trigger", WEBHOOK_EVENT_BODY),
            # read surface: Manager lost the read grant as well
            ("GET", "/api/v1/webhooks/", None),
            ("GET", "/api/v1/webhooks/system/stats", None),
        ],
    )
    def test_manager_denied(
        self,
        client: TestClient,
        manager_token: str,
        method: str,
        path: str,
        body: dict | None,
    ) -> None:
        resp = client.request(
            method, path, json=body, headers=_headers(manager_token)
        )
        assert resp.status_code == 403, (method, path, resp.status_code, resp.text[:200])


# ===================== 2. FORCE MAJEURE / REFUNDS DENIED =====================


class TestManagerDeniedForceMajeure:
    """M-1 requirement 3: Manager denied refund processing; Admin/Cashier
    keep the approved force-majeure contract."""

    @pytest.mark.parametrize(
        ("method", "path", "body"),
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
    def test_manager_denied(
        self,
        client: TestClient,
        manager_token: str,
        method: str,
        path: str,
        body: dict | None,
    ) -> None:
        resp = client.request(
            method, path, json=body, headers=_headers(manager_token)
        )
        assert resp.status_code == 403, (method, path, resp.status_code, resp.text[:200])

    def test_cashier_retains_refund_read(
        self, client: TestClient, cashier_token: str
    ) -> None:
        resp = client.get(
            "/api/v1/force-majeure/refund-requests", headers=_headers(cashier_token)
        )
        assert resp.status_code == 200, (resp.status_code, resp.text[:200])

    def test_admin_retains_refund_read(
        self, client: TestClient, admin_token: str
    ) -> None:
        resp = client.get(
            "/api/v1/force-majeure/refund-requests", headers=_headers(admin_token)
        )
        assert resp.status_code == 200, (resp.status_code, resp.text[:200])


# ===================== 3. FINANCIAL / ANALYTICS / REPORTS DENIED =====================

_DENIED_ANALYTICS_PROBES = [
    # advanced analytics (the old smoke endpoint family)
    ("GET", "/api/v1/analytics/advanced/kpi?start_date=2026-01-01&end_date=2026-01-31"),
    ("GET", "/api/v1/analytics/advanced/doctors/performance?start_date=2026-01-01&end_date=2026-01-31"),
    ("GET", "/api/v1/analytics/advanced/revenue/advanced?start_date=2026-01-01&end_date=2026-01-31"),
    ("GET", "/api/v1/analytics/advanced/predictive?start_date=2026-01-01&end_date=2026-01-31"),
    ("GET", "/api/v1/analytics/advanced/comprehensive/advanced?start_date=2026-01-01&end_date=2026-01-31"),
    # core analytics financial surfaces
    ("GET", "/api/v1/analytics/revenue-breakdown?start_date=2026-01-01&end_date=2026-01-31"),
    ("GET", "/api/v1/analytics/payment-providers?start_date=2026-01-01&end_date=2026-01-31"),
    # visualization financial surface
    ("GET", "/api/v1/analytics/visualization/dashboard?start_date=2026-01-01&end_date=2026-01-31"),
    # kpi / predictive / export financial surfaces
    ("GET", "/api/v1/analytics/kpi-metrics?start_date=2026-01-01&end_date=2026-01-31"),
    ("GET", "/api/v1/analytics/predictive?start_date=2026-01-01&end_date=2026-01-31"),
    ("GET", "/api/v1/analytics/export/kpi/export/csv?start_date=2026-01-01&end_date=2026-01-31"),
    # specialized panels (financial analytics gates)
    ("GET", "/api/v1/specialized/cardiology/analytics"),
    ("GET", "/api/v1/specialized/dentistry/analytics"),
]


class TestManagerDeniedFinancialAnalytics:
    """M-1 requirement 4: Manager denied advanced/financial analytics,
    KPI/predictive/revenue, visualization financial grants, exports,
    specialized-panel financial analytics and financial reports."""

    @pytest.mark.parametrize(
        ("method", "path"), _DENIED_ANALYTICS_PROBES
    )
    def test_manager_denied(
        self, client: TestClient, manager_token: str, method: str, path: str
    ) -> None:
        resp = client.request(method, path, headers=_headers(manager_token))
        assert resp.status_code == 403, (path, resp.status_code, resp.text[:200])

    def test_manager_denied_financial_report(
        self, client: TestClient, manager_token: str
    ) -> None:
        resp = client.post(
            "/api/v1/reports/financial",
            json={
                "title": "m1 deny probe",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
            headers=_headers(manager_token),
        )
        assert resp.status_code == 403, (resp.status_code, resp.text[:200])

    def test_manager_denied_doctor_performance_report(
        self, client: TestClient, manager_token: str
    ) -> None:
        resp = client.post(
            "/api/v1/reports/doctor-performance",
            json={
                "title": "m1 deny probe",
                "start_date": "2026-01-01",
                "end_date": "2026-01-31",
            },
            headers=_headers(manager_token),
        )
        assert resp.status_code == 403, (resp.status_code, resp.text[:200])

    def test_admin_retains_advanced_analytics(
        self, client: TestClient, admin_token: str
    ) -> None:
        resp = client.get(
            "/api/v1/analytics/advanced/kpi?start_date=2026-01-01&end_date=2026-01-31",
            headers=_headers(admin_token),
        )
        assert resp.status_code == 200, (resp.status_code, resp.text[:300])

    def test_registrar_retains_report_read(
        self, client: TestClient, registrar_token: str
    ) -> None:
        # available-reports shares the [ADMIN, REGISTRAR] grant with the
        # other report reads; its simple DB query avoids the unrelated
        # pre-existing daily-summary service NameError (service internals
        # are explicitly out of M-1 scope — grants only).
        resp = client.get(
            "/api/v1/reports/available-reports", headers=_headers(registrar_token)
        )
        assert resp.status_code == 200, (resp.status_code, resp.text[:300])

    def test_registrar_retains_webhook_read(
        self, client: TestClient, registrar_token: str
    ) -> None:
        resp = client.get("/api/v1/webhooks/", headers=_headers(registrar_token))
        assert resp.status_code == 200, (resp.status_code, resp.text[:300])


# ===================== 4. SYSTEM / BACKUP / EQUIPMENT READS DENIED =====================

_DENIED_SYSTEM_PROBES = [
    ("GET", "/api/v1/system/backup/list"),
    ("GET", "/api/v1/system/monitoring/health"),
    ("GET", "/api/v1/system/monitoring/metrics/system"),
    ("GET", "/api/v1/system/monitoring/metrics/application"),
    ("GET", "/api/v1/system/monitoring/metrics/history"),
    ("GET", "/api/v1/system/monitoring/metrics/summary"),
    ("GET", "/api/v1/system/monitoring/alerts"),
    ("GET", "/api/v1/medical-equipment/statistics/overview"),
    ("GET", "/api/v1/cloud-printing/statistics"),
]


class TestManagerDeniedSystemReads:
    """M-1 requirement 5: Manager denied system monitoring reads, backup
    metadata reads, equipment/cloud-printing statistics. The endpoint
    implementations themselves are untouched — only the grants."""

    @pytest.mark.parametrize(("method", "path"), _DENIED_SYSTEM_PROBES)
    def test_manager_denied(
        self, client: TestClient, manager_token: str, method: str, path: str
    ) -> None:
        resp = client.request(method, path, headers=_headers(manager_token))
        assert resp.status_code == 403, (path, resp.status_code, resp.text[:200])

    def test_admin_retains_system_health(
        self, client: TestClient, admin_token: str
    ) -> None:
        resp = client.get(
            "/api/v1/system/monitoring/health", headers=_headers(admin_token)
        )
        assert resp.status_code == 200, (resp.status_code, resp.text[:200])


# ===================== 5. CANONICAL DOCTOR SMOKE ENDPOINT =====================


class TestDoctorSmokeVisualizationEndpoint:
    """M-1 requirement 8 + nightly smoke repoint target: the visualization
    doctors/performance endpoint returns 200 under canonical Doctor auth."""

    def test_doctor_gets_visualization_doctors_performance(
        self, client: TestClient, doctor_token: str
    ) -> None:
        resp = client.get(
            "/api/v1/analytics/visualization/doctors/performance"
            "?start_date=2026-01-01&end_date=2026-01-31",
            headers=_headers(doctor_token),
        )
        assert resp.status_code == 200, (resp.status_code, resp.text[:300])

    def test_manager_denied_visualization_financial_dashboard(
        self, client: TestClient, manager_token: str
    ) -> None:
        resp = client.get(
            "/api/v1/analytics/visualization/dashboard"
            "?start_date=2026-01-01&end_date=2026-01-31",
            headers=_headers(manager_token),
        )
        assert resp.status_code == 403, (resp.status_code, resp.text[:200])


# ===================== 6. WRITE FREEZE + READ COMPAT =====================


class TestManagerWriteFreeze:
    """M-1 requirement 11: POST create user role=Manager rejected;
    bulk change_role role=Manager rejected; update contract frozen."""

    def test_create_user_role_manager_rejected(
        self, client: TestClient, admin_token: str
    ) -> None:
        probe_password = "Pass" + "w" + "0rd!"
        resp = client.post(
            "/api/v1/users/users",
            json={
                "username": "m1_manager_probe",
                "email": "m1_manager_probe@test.com",
                "password": probe_password,
                "role": "Manager",
            },
            headers=_headers(admin_token),
        )
        assert resp.status_code == 422, (resp.status_code, resp.text[:300])

    def test_bulk_change_role_manager_rejected(
        self, client: TestClient, admin_token: str, manager_user: User
    ) -> None:
        resp = client.post(
            "/api/v1/users/users/bulk-action",
            json={
                "user_ids": [manager_user.id],
                "action": "change_role",
                "role": "Manager",
            },
            headers=_headers(admin_token),
        )
        assert resp.status_code == 422, (resp.status_code, resp.text[:300])

    def test_update_user_role_manager_rejected_at_schema(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            UserUpdateRequest(role="Manager")

    def test_write_pattern_freezes_manager(self) -> None:
        assert not re.match(_USER_MANAGEMENT_ROLE_PATTERN, "Manager")

    def test_filter_pattern_keeps_manager_read_compat(self) -> None:
        """Read compatibility: the search/filter surface must keep
        accepting the deprecated spelling while the legacy row survives."""
        assert re.match(_USER_MANAGEMENT_ROLE_FILTER_PATTERN, "Manager")

    def test_get_users_role_filter_still_accepts_manager(
        self, client: TestClient, admin_token: str
    ) -> None:
        resp = client.get(
            "/api/v1/users/users?role=Manager", headers=_headers(admin_token)
        )
        assert resp.status_code == 200, (resp.status_code, resp.text[:300])

    def test_canonical_roles_still_accepted_by_write_pattern(self) -> None:
        for role in ("Admin", "Doctor", "Registrar", "Nurse", "Cashier", "Lab",
                     "Patient", "SuperAdmin"):
            assert re.match(_USER_MANAGEMENT_ROLE_PATTERN, role), role


# ===================== 7. ENUM + ADMIN_ROLES COMPAT =====================


class TestManagerEnumCompat:
    """M-1 requirement 12 + enum compatibility: the enum member survives
    (production row still deserializes) but is no longer administrative."""

    def test_enum_member_preserved(self) -> None:
        assert Roles.MANAGER.value == "Manager"

    def test_manager_not_admin_role(self) -> None:
        assert Roles.MANAGER not in ADMIN_ROLES
        assert is_admin_role(Roles.MANAGER) is False

    def test_canonical_admin_roles_unaffected(self) -> None:
        assert is_admin_role(Roles.ADMIN) is True
        assert is_admin_role(Roles.SUPER_ADMIN) is True


# ===================== 8. SMOKE PROVISIONING CONTRACT =====================


class TestEnsureSmokeUsersManagerFreeze:
    """M-1 requirement 10: ensure_smoke_users no longer creates/pins
    Manager. Behavioral proof against an isolated in-memory DB."""

    @pytest.fixture
    def smoke_db_env(self, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
        engine = create_engine("sqlite://")
        from app.db.base import Base

        Base.metadata.create_all(bind=engine)
        factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        monkeypatch.setenv("SMOKE_USER_PASSWORD", "SmokePassw0rd!")

        import app.scripts.ensure_smoke_users as ensure_smoke_users_module

        # ensure_smoke_users() resolves SessionLocal from its own module
        # globals, so an isolated factory is enough — no reload needed.
        monkeypatch.setattr(
            ensure_smoke_users_module, "SessionLocal", factory, raising=True
        )
        return SimpleNamespace(module=ensure_smoke_users_module, factory=factory)

    def test_provisions_only_canonical_roles(
        self, smoke_db_env: SimpleNamespace
    ) -> None:
        module = smoke_db_env.module
        results = module.ensure_smoke_users()
        roles = {item["role"] for item in results}
        assert roles == {"Registrar", "Doctor"}, results
        assert "smoke_manager" not in {item["username"] for item in results}

        with smoke_db_env.factory() as db:
            usernames = set(db.scalars(select(User.username)).all())
        assert "smoke_manager" not in usernames
        assert {"smoke_registrar", "smoke_doctor"} <= usernames

    def test_existing_legacy_smoke_manager_row_untouched(
        self, smoke_db_env: SimpleNamespace
    ) -> None:
        module = smoke_db_env.module
        legacy_hash = get_password_hash("legacy-known-password")
        with smoke_db_env.factory() as db:
            db.add(
                User(
                    username="smoke_manager",
                    email="smoke.manager@synthetic.invalid",
                    full_name="[SYNTHETIC-SMOKE] Manager",
                    role="Manager",
                    is_active=True,
                    hashed_password=legacy_hash,
                )
            )
            db.commit()

        results = module.ensure_smoke_users()
        assert "smoke_manager" not in {item["username"] for item in results}

        with smoke_db_env.factory() as db:
            row = db.scalar(select(User).where(User.username == "smoke_manager"))
        assert row is not None
        assert row.role == "Manager"
        assert row.is_active is True
        assert row.hashed_password == legacy_hash, (
            "ensure_smoke_users must not re-pin the legacy Manager password"
        )

    def test_smoke_users_declared_vocabulary_has_no_manager(self) -> None:
        from app.scripts import ensure_smoke_users as module

        for _username, role, _email in module.SMOKE_USERS:
            assert role != "Manager", module.SMOKE_USERS


class TestNightlySmokeManagerFree:
    """M-1 requirement 9: the nightly smoke no longer logs in as
    smoke_manager and probes the canonical-Doctor visualization endpoint
    (fs-contract: the script is environment-independent stdlib-only).
    Docstring mentions of the deprecation are intentional — the asserts
    target the FUNCTIONAL code forms (login tuple, token lookup, probe
    request), not prose."""

    def test_nightly_smoke_has_no_smoke_manager(self) -> None:
        source = (
            REPO_ROOT / "scripts" / "nightly_functional_smoke.py"
        ).read_text(encoding="utf-8")
        assert 'login {"smoke_manager"' not in source
        # accounts-list tuple literal
        assert '("smoke_manager"' not in source
        # token lookup for the manager account
        assert 'tokens.get("smoke_manager"' not in source

    def test_nightly_smoke_probes_visualization_under_doctor(self) -> None:
        source = (
            REPO_ROOT / "scripts" / "nightly_functional_smoke.py"
        ).read_text(encoding="utf-8")
        assert 'f"/api/v1/analytics/visualization/doctors/performance' in source
        assert "token=doc" in source
        # the manager-gated advanced endpoint must no longer be probed
        assert 'f"/api/v1/analytics/advanced/doctors/performance' not in source
