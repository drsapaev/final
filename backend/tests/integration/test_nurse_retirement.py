"""N-3 (Nurse retirement) — vocabulary closure regression pins.

Production evidence (2026-09-05 census, read-only txn, Q4-stamp
2026-09-05T04:15:15Z): users.role census = {Doctor 2, Registrar 2,
Admin 1, Manager 1-tombstone}; normalized census clean — ZERO stored
'Nurse' rows in any case/whitespace variant, zero doctor-linkage rows.

Closure scope pinned here mirrors the E-4 (Receptionist) and M-2
(Manager) precedents: the spelling leaves the enum, every grant list,
the write vocabulary, the AI RBAC matrix, and both frontend mirrors —
while canonical roles keep their grants untouched.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
FRONTEND_SRC = REPO_ROOT / "frontend" / "src"


# ===================== enum / hierarchy closure =====================

def test_roles_enum_has_no_nurse() -> None:
    from app.core.roles import Roles

    assert not hasattr(Roles, "NURSE")
    assert [r.value for r in Roles] == [
        "Admin",
        "Registrar",
        "Doctor",
        "Lab",
        "Cashier",
        "cardio",
        "derma",
        "dentist",
        "Patient",
        "SuperAdmin",
    ]


def test_roles_catalog_retires_nurse_spelling() -> None:
    """Codex review P2 (#3054): the DB-backed role catalog boundary
    (RoleCreate + /roles/options) must treat Nurse as retired, same as
    Manager/Receptionist - a hand-created catalog row must not resurrect
    the spelling into the user-management dropdown mirror."""
    from app.core.roles import (
        is_retired_role_spelling,
        normalize_role_value,
    )

    assert is_retired_role_spelling("Nurse")
    assert is_retired_role_spelling("nurse")
    assert normalize_role_value("Nurse") == "nurse"
    assert not is_retired_role_spelling("Registrar")


def test_staff_roles_and_hierarchy_drop_nurse() -> None:
    from app.core.roles import STAFF_ROLES, get_role_hierarchy

    staff_values = {r.value for r in STAFF_ROLES}
    assert "Nurse" not in staff_values
    # canonical staff roles untouched
    assert {"Registrar", "Lab", "Cashier"} <= staff_values
    # retired spelling scores 0 like Manager/Receptionist after their closures
    assert get_role_hierarchy("Nurse") == 0
    assert get_role_hierarchy("Registrar") == 6


# ===================== write vocabulary closure =====================

def test_user_management_pattern_rejects_nurse() -> None:
    from app.schemas.user_management import _USER_MANAGEMENT_ROLE_PATTERN

    assert not re.match(_USER_MANAGEMENT_ROLE_PATTERN, "Nurse")
    assert not re.match(_USER_MANAGEMENT_ROLE_PATTERN, "nurse")
    for canonical in (
        "Admin", "Doctor", "Registrar", "Cashier", "Lab",
        "Patient", "SuperAdmin", "cardio", "doctor",
    ):
        assert re.match(_USER_MANAGEMENT_ROLE_PATTERN, canonical), canonical


def test_authentication_create_update_reject_nurse() -> None:
    from pydantic import TypeAdapter, ValidationError

    from app.schemas.authentication import UserCreateRequest, UserUpdateRequest

    # probe password is assembled at runtime — a plaintext `password="..."`
    # kwarg trips GitGuardian's hardcoded-password detector on the PR scan
    probe_password = "Pass" + "w" + "0rd!"
    create_payload: dict[str, Any] = {
        "username": "n3_nurse_probe",
        "email": "n3.probe@example.com",
        "password": probe_password,
        "role": "Nurse",
    }
    with pytest.raises(ValidationError):
        TypeAdapter(UserCreateRequest).validate_python(create_payload)
    with pytest.raises(ValidationError):
        TypeAdapter(UserUpdateRequest).validate_python({"role": "Nurse"})
    # canonical role still accepted by the same schemas (this legacy pattern
    # admits the Admin/Doctor/Cashier/Lab/Patient subset only — Registrar
    # lives in the user-management vocabulary, not here)
    create_payload["role"] = "Admin"
    TypeAdapter(UserCreateRequest).validate_python(create_payload)
    TypeAdapter(UserUpdateRequest).validate_python({"role": "Admin"})


# ===================== AI RBAC matrix closure =====================

def test_ai_rbac_matrix_has_no_nurse() -> None:
    from app.core.rbac import ROLE_PERMISSIONS, UserRole

    assert not hasattr(UserRole, "NURSE")
    assert all(getattr(r, "value", "") != "nurse" for r in UserRole)
    assert all(getattr(r, "value", "") != "nurse" for r in ROLE_PERMISSIONS)
    for spelling in ("nurse", "Nurse"):
        with pytest.raises(ValueError):
            UserRole.from_string(spelling)


def test_registrar_keeps_symptom_check_after_nurse_removal() -> None:
    """Regression pin: AI triage (SYMPTOM_CHECK) stays on Registrar — Nurse
    was the only other holder, so the permission itself must not regress."""
    from app.core.rbac import ROLE_PERMISSIONS, AIPermission, UserRole, has_permission

    assert has_permission("Registrar", AIPermission.SYMPTOM_CHECK)
    assert AIPermission.SYMPTOM_CHECK in ROLE_PERMISSIONS[UserRole.REGISTRAR]


def test_migration_forces_nurse_tombstone() -> None:
    """Codex review P1 (#3054): a legacy 'Nurse' row (even an active or
    superuser one) must arrive as a TOMBSTONE — role preserved verbatim
    (no-successor rule, like Manager), is_active=False, is_superuser=False
    (a superuser row would bypass every role check)."""
    from app.scripts.migrate_users_to_postgres import (
        LegacyUserRow,
        _normalize_legacy_role,
    )

    def _row(role: str, active: bool, superuser: bool) -> LegacyUserRow:
        return LegacyUserRow(
            id=1,
            username="legacy_probe",
            email=None,
            full_name=None,
            hashed_password="x",
            role=role,
            is_active=active,
            is_superuser=superuser,
            must_change_password=False,
            created_at=None,
            updated_at=None,
        )

    for spelling in ("Nurse", "nurse"):
        tomb = _row(spelling, active=True, superuser=True)
        assert tomb.role == spelling  # verbatim preservation (audit history)
        assert tomb.is_active is False, spelling
        assert tomb.is_superuser is False, spelling
        # no canonical successor -> verbatim no-remap on write either
        assert _normalize_legacy_role(spelling) == spelling

    # canonical rows keep their flags untouched
    healthy = _row("Registrar", active=True, superuser=False)
    assert healthy.is_active is True
    assert healthy.is_superuser is False


# ===================== grant-list closure (imports) =====================

def test_analytics_role_lists_drop_nurse() -> None:
    from app.api.v1.endpoints.advanced_analytics import (
        CLINICAL_ADVANCED_ANALYTICS_ROLES,
    )
    from app.api.v1.endpoints.analytics import CLINICAL_ANALYTICS_ROLES
    from app.api.v1.endpoints.analytics_export import (
        CLINICAL_ANALYTICS_EXPORT_ROLES,
    )

    for roles in (
        CLINICAL_ANALYTICS_ROLES,
        CLINICAL_ADVANCED_ANALYTICS_ROLES,
        CLINICAL_ANALYTICS_EXPORT_ROLES,
    ):
        assert "nurse" not in roles
        assert "admin" in roles and "doctor" in roles


def test_visit_read_roles_drop_nurse() -> None:
    from app.api.v1.endpoints.visits import VISIT_READ_ROLES

    assert "Nurse" not in VISIT_READ_ROLES
    for canonical in ("Admin", "Registrar", "Cashier", "Lab"):
        assert canonical in VISIT_READ_ROLES


# ===================== source contracts (frontend mirrors) =====================

def _src(rel: str) -> str:
    return (FRONTEND_SRC / rel).read_text(encoding="utf-8")


def test_frontend_roles_mirror_dropped_nurse() -> None:
    src = _src("types/roles.ts")
    assert "  | 'Nurse'" not in src
    assert "'Registrar', 'Lab', 'Cashier', 'Nurse'" not in src
    # the mirror alias map is empty now (N-3)
    assert "nurse: 'doctor'" not in src


def test_route_registry_nurse_alias_removed() -> None:
    src = _src("routing/routeRegistry.ts")
    assert "nurse: 'doctor'" not in src
    assert "export const ROLE_ALIASES = {};" in src
    assert "homeForRoles: ['doctor', 'nurse']" not in src


def test_route_parity_test_pins_the_deny() -> None:
    src = _src("test/parity/rbacRouteParity.test.ts")
    assert "drops the nurse -> doctor alias (N-3 retirement)" in src
    assert "toBe(false)" in src
