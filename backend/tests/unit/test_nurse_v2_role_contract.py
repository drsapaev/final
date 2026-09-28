"""NURSE-V2 N2-2 — the owner's role-contract acceptance pins (2026-09-19).

Owner's required test list (design-GO):
- Nurse is accepted by the canonical role vocabulary;
- Manager/Receptionist remain retired;
- Resource remains an internal non-login;
- Nurse does NOT join the doctor family;
- Nurse receives NONE of the existing Doctor/Registrar/Admin/staff grants
  (privilege-zero until the N2-3 serving API, which is assignment-scoped).
"""

from __future__ import annotations

from types import SimpleNamespace


def test_nurse_accepted_by_canonical_vocabularies() -> None:
    import re

    from app.core.rbac import UserRole
    from app.core.roles import Roles
    from app.schemas.user_management import (
        _NON_DOCTOR_ROLE_VALUES,
        _USER_MANAGEMENT_ROLE_PATTERN,
    )

    assert Roles.NURSE.value == "Nurse"
    assert UserRole.from_string("nurse") is UserRole.NURSE
    assert UserRole.from_string("Nurse") is UserRole.NURSE
    # user-management write vocabulary (POST /users without doctor_profile)
    assert re.match(_USER_MANAGEMENT_ROLE_PATTERN, "Nurse")
    assert "Nurse" in _NON_DOCTOR_ROLE_VALUES


def test_manager_receptionist_remain_retired() -> None:
    from app.core.roles import is_retired_role_spelling

    assert is_retired_role_spelling("Manager")
    assert is_retired_role_spelling("manager")
    assert is_retired_role_spelling("Receptionist")
    assert is_retired_role_spelling("receptionist")
    # Nurse left the retired set (NURSE-V2)
    assert not is_retired_role_spelling("Nurse")


def test_resource_remains_internal_non_login() -> None:
    from app.core.roles import (
        is_internal_only_role_spelling,
        is_login_blocked_role,
    )

    assert is_internal_only_role_spelling("Resource")
    assert is_login_blocked_role("Resource")
    # Nurse is a real login-capable product role — NOT the sentinel
    assert not is_internal_only_role_spelling("Nurse")
    assert not is_login_blocked_role("Nurse")


def test_nurse_is_not_doctor_family() -> None:
    from app.api.v1.endpoints.emr_v2 import EMR_V2_WRITE_ROLES
    from app.core.rbac import UserRole
    from app.core.roles import (
        DOCTOR_FAMILY_GATE_ROLES,
        DOCTOR_ROLE_SPELLINGS,
        DOCTOR_ROLES,
        is_doctor_role,
        is_doctor_role_spelling,
        Roles,
    )

    nurse_spellings = ("Nurse", "nurse")
    assert Roles.NURSE not in DOCTOR_ROLES
    for spelling in nurse_spellings:
        assert spelling not in DOCTOR_ROLE_SPELLINGS
        assert spelling not in DOCTOR_FAMILY_GATE_ROLES
        assert not is_doctor_role(spelling)
        assert not is_doctor_role_spelling(spelling)
    # EMR write boundary: Nurse is absent — ensure_emr_visit_access already
    # 403s any role without an active Doctor profile; the deny is free.
    for spelling in nurse_spellings:
        assert spelling not in {str(r).lower() for r in EMR_V2_WRITE_ROLES}
        assert spelling not in {
            getattr(r, "value", str(r)).lower() for r in EMR_V2_WRITE_ROLES
        }
    assert UserRole.NURSE.is_medical_professional() is False


def test_nurse_gets_no_staff_permissions() -> None:
    from app.services.authorization.staff import StaffAuthorizationService

    svc = StaffAuthorizationService.__new__(StaffAuthorizationService)
    nurse = SimpleNamespace(role="Nurse", is_superuser=False)
    assert svc._get_permissions(nurse) == frozenset()
    # sanity: the map still grants the canonical roles it always did
    registrar = SimpleNamespace(role="Registrar", is_superuser=False)
    assert svc._get_permissions(registrar) != frozenset()


def test_nurse_not_in_admin_critical_staff_sets() -> None:
    from app.core.roles import ADMIN_ROLES, CRITICAL_ROLES, Roles, STAFF_ROLES

    assert Roles.NURSE not in ADMIN_ROLES
    assert Roles.NURSE not in CRITICAL_ROLES
    assert Roles.NURSE not in STAFF_ROLES
