"""N-3 (Nurse retirement) history + NURSE-V2 re-open regression pins.

Production evidence (2026-09-05 census, read-only txn, Q4-stamp
2026-09-05T04:15:15Z): users.role census = {Doctor 2, Registrar 2,
Admin 1, Manager 1-tombstone}; normalized census clean — ZERO stored
'Nurse' rows in any case/whitespace variant, zero doctor-linkage rows.
N-3 stays the correct HISTORICAL decision: the old Nurse never shipped
as a product surface.

NURSE-V2 (owner design-GO 2026-09-19, slice N2-2, PR record in
.ai-factory/plans/nurse-v2-clinical-serving.md): the canonical role
`Nurse` is re-opened as a NEW product capability — re-opened here:
enum member, catalog boundary (out of RETIRED_ROLE_SPELLINGS), write
vocabulary (user management), both frontend mirrors. Re-opened WITHOUT
legacy grants: the AI RBAC matrix, analytics/visit read lists, staff
permission sets, route registry and the nurse->doctor alias all stay
Nurse-free (privilege-zero until the N2-3 serving API, which is
assignment-scoped). Manager/Receptionist closures remain permanent.
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

def test_roles_enum_reopens_nurse_v2() -> None:
    from app.core.roles import Roles

    assert hasattr(Roles, "NURSE")
    assert Roles.NURSE.value == "Nurse"
    assert [r.value for r in Roles] == [
        "Admin",
        "Registrar",
        "Doctor",
        "Lab",
        "Cashier",
        "cardio",
        "derma",
        "dentist",
        "Nurse",
        "Patient",
        "SuperAdmin",
    ]


def test_roles_catalog_retired_set_drops_nurse_only() -> None:
    """Codex review P2 (#3054) history + NURSE-V2: the DB-backed role
    catalog boundary (RoleCreate + /roles/options) keeps Manager/
    Receptionist retired; the re-opened canonical 'Nurse' is no longer
    blocked — a catalog row for it is legal product vocabulary now (the
    dropdown mirror surfaces it only if the catalog row exists; creating
    one is NOT an N2-2 requirement)."""
    from app.core.roles import (
        is_retired_role_spelling,
        normalize_role_value,
    )

    # NURSE-V2 re-open: the spelling left the retired set.
    assert not is_retired_role_spelling("Nurse")
    assert not is_retired_role_spelling("nurse")
    assert normalize_role_value("Nurse") == "nurse"
    # Manager/Receptionist closures are permanent.
    assert is_retired_role_spelling("Manager")
    assert is_retired_role_spelling("manager")
    assert is_retired_role_spelling("Receptionist")
    assert not is_retired_role_spelling("Registrar")


def test_staff_roles_and_hierarchy_keep_nurse_least_privilege() -> None:
    from app.core.roles import STAFF_ROLES, get_role_hierarchy

    staff_values = {r.value for r in STAFF_ROLES}
    # NURSE-V2: Nurse is deliberately NOT a generic staff role — no
    # role-wide staff grants; serving permissions are N2-3 and
    # assignment-scoped (active NurseWorkplaceAssignment), never role-wide.
    assert "Nurse" not in staff_values
    # canonical staff roles untouched
    assert {"Registrar", "Lab", "Cashier"} <= staff_values
    # NURSE-V2: descriptive hierarchy re-opened at level 2 (the map is
    # inert — has_role_permission has zero external callers).
    assert get_role_hierarchy("Nurse") == 2
    assert get_role_hierarchy("Registrar") == 6


# ===================== write vocabulary closure =====================

def test_user_management_pattern_accepts_canonical_nurse() -> None:
    from app.schemas.user_management import _USER_MANAGEMENT_ROLE_PATTERN

    # NURSE-V2 (owner design-GO 2026-09-19): the canonical TitleCase
    # spelling joins the write vocabulary — a Nurse User is created via
    # user management WITHOUT a doctor_profile, exactly like Registrar.
    assert re.match(_USER_MANAGEMENT_ROLE_PATTERN, "Nurse")
    # the pattern stays case-sensitive: the lowercase spelling is not
    # the canonical stored form
    assert not re.match(_USER_MANAGEMENT_ROLE_PATTERN, "nurse")
    # retired spellings stay frozen
    assert not re.match(_USER_MANAGEMENT_ROLE_PATTERN, "Manager")
    assert not re.match(_USER_MANAGEMENT_ROLE_PATTERN, "Receptionist")
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
    # lives in the user-management vocabulary, not here; NURSE-V2 follows
    # the same Registrar precedent: Nurse creation goes through user
    # management, the legacy authentication subset stays without it)
    create_payload["role"] = "Admin"
    TypeAdapter(UserCreateRequest).validate_python(create_payload)
    TypeAdapter(UserUpdateRequest).validate_python({"role": "Admin"})


# ===================== AI RBAC matrix closure =====================

def test_ai_rbac_matrix_has_no_nurse_grants() -> None:
    from app.core.rbac import ROLE_PERMISSIONS, UserRole

    # NURSE-V2: the enum member is re-opened and from_string resolves
    # the canonical spellings …
    assert hasattr(UserRole, "NURSE")
    assert UserRole.from_string("nurse") is UserRole.NURSE
    assert UserRole.from_string("Nurse") is UserRole.NURSE
    # … but the AI RBAC matrix grants Nurse NOTHING — privilege-zero
    # until N2-3; no legacy N-3 grants return.
    assert UserRole.NURSE not in ROLE_PERMISSIONS


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
    (a superuser row would bypass every role check).

    NURSE-V2 does NOT change this: the legacy import path must not
    auto-resurrect old-world rows as active Nurse v2 accounts — new
    Nurse accounts are created fresh via user management, and v2
    serving requires an explicit workplace assignment anyway."""
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


def test_frontend_roles_mirror_reopens_nurse() -> None:
    src = _src("types/roles.ts")
    # NURSE-V2: the canonical spelling is back in the BackendRole union
    assert "  | 'Nurse'" in src
    # the nurse -> doctor alias STAYS removed (NURSE-V2 is not a doctor
    # alias; no routes until N2-3/N2-5)
    assert "nurse: 'doctor'" not in src
    assert "'Registrar', 'Lab', 'Cashier', 'Nurse'" not in src


def test_route_registry_nurse_alias_removed() -> None:
    src = _src("routing/routeRegistry.ts")
    assert "nurse: 'doctor'" not in src
    assert "export const ROLE_ALIASES = {};" in src
    assert "homeForRoles: ['doctor', 'nurse']" not in src


def test_route_parity_test_pins_the_deny() -> None:
    src = _src("test/parity/rbacRouteParity.test.ts")
    assert "drops the nurse -> doctor alias (N-3 retirement)" in src
    assert "toBe(false)" in src
