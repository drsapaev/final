"""WS-POSTMERGE-03: queue-room ownership contract for ``_has_department_access``.

The queue WebSocket plane authorizes room subscriptions through
``_has_department_access``. The pre-POSTMERGE-03 implementation returned
``True`` for ANY staff-doctor role without looking at the requested
``department`` at all, so a ``derma`` doctor could subscribe to
``specialist_{other-doctor-id}::{date}`` rooms and receive another
physician's queue events (cross-scope authorization, P1).

The fixed contract binds the department argument to the principal's own
doctor identity, resolved through the SAME SSOT the broadcasters use
(``doctors.user_id`` unique bridge; ``queue_update_departments`` room
identities; ``Department.key`` / ``specialty_variants`` vocabulary):

- ``specialist_<id>`` rooms: the id must be the principal's own
  ``doctors.id``. Shared/bridged queues need no sibling-room access —
  the routing fan-out already broadcasts to every sibling's own room.
- Department-name rooms: the principal's own ``Department.key`` or the
  specialty family of their ``Doctor.specialty`` must match.
- A doctor-family role WITHOUT a doctor row owns nothing (fail closed).
- ``Admin`` / ``Registrar`` keep full cross-department access;
  non-staff roles stay rejected exactly as before.

All principals are synthetic namespaces; the doctor resolver is
monkeypatched, so no database, JWT, network or patient data is touched.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.api.v1.endpoints.websocket_auth as ws_auth
from app.api.v1.endpoints.websocket_auth import _has_department_access


def _user(role: str, user_id: int = 1, *, is_superuser: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        id=user_id,
        username=f"{role.lower()}-ws-user",
        role=role,
        is_superuser=is_superuser,
    )


def _department(key: str) -> SimpleNamespace:
    return SimpleNamespace(key=key)


def _doctor(
    doctor_id: int = 42,
    specialty: str = "cardio",
    department: SimpleNamespace | None = None,
    active: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=doctor_id, specialty=specialty, department=department, active=active
    )


# Any non-None object works: the resolver is monkeypatched, so the session
# is never touched by these unit tests.
_FAKE_DB = SimpleNamespace()


@pytest.fixture()
def patch_doctor(monkeypatch: pytest.MonkeyPatch):
    def _patch(doctor: SimpleNamespace | None) -> None:
        monkeypatch.setattr(
            ws_auth, "_resolve_doctor_for_user", lambda db, user: doctor
        )

    return _patch


# ---------------------------------------------------------------------------
# specialist_{id} rooms — own id only
# ---------------------------------------------------------------------------


def test_cardio_doctor_joins_own_specialist_room(patch_doctor):
    patch_doctor(_doctor(doctor_id=42, specialty="cardio"))
    assert _has_department_access(_user("cardio"), "specialist_42", _FAKE_DB) is True


def test_cardio_doctor_denied_foreign_specialist_room(patch_doctor):
    patch_doctor(_doctor(doctor_id=42, specialty="cardio"))
    assert _has_department_access(_user("cardio"), "specialist_73", _FAKE_DB) is False


def test_derma_doctor_denied_cardiology_specialist_room(patch_doctor):
    # The P1 fail-first case from the audit: a dermatology principal must
    # never join a cardiology doctor's room.
    patch_doctor(_doctor(doctor_id=73, specialty="derma"))
    assert _has_department_access(_user("derma"), "specialist_42", _FAKE_DB) is False


def test_derma_doctor_joins_own_specialist_room(patch_doctor):
    patch_doctor(_doctor(doctor_id=73, specialty="derma"))
    assert _has_department_access(_user("derma"), "specialist_73", _FAKE_DB) is True


@pytest.mark.parametrize(
    "room",
    [
        "specialist_abc",
        "specialist_-5",
        "specialist_None",
        "specialist_",
        "SPECIALIST_42",
    ],
)
def test_forged_specialist_room_names_denied_for_doctors(patch_doctor, room):
    patch_doctor(_doctor(doctor_id=42, specialty="cardio"))
    assert _has_department_access(_user("cardio"), room, _FAKE_DB) is False


def test_specialist_room_whitespace_normalized_but_zero_padding_rejected(patch_doctor):
    patch_doctor(_doctor(doctor_id=42, specialty="cardio"))
    assert _has_department_access(_user("cardio"), " specialist_42 ", _FAKE_DB) is True
    assert _has_department_access(_user("cardio"), "specialist_0042", _FAKE_DB) is False


@pytest.mark.parametrize("suffix", ["²", "0", "0042", "9" * 5000])
def test_noncanonical_or_unbounded_specialist_id_rejected(patch_doctor, suffix):
    patch_doctor(_doctor(doctor_id=42, specialty="cardio"))
    assert _has_department_access(
        _user("cardio"), f"specialist_{suffix}", _FAKE_DB
    ) is False


def test_empty_department_denied_for_doctor(patch_doctor):
    patch_doctor(_doctor(doctor_id=42, specialty="cardio"))
    assert _has_department_access(_user("cardio"), "", _FAKE_DB) is False
    assert _has_department_access(_user("cardio"), "   ", _FAKE_DB) is False


# ---------------------------------------------------------------------------
# Department-name rooms — own department key / own specialty family
# ---------------------------------------------------------------------------


def test_doctor_joins_own_department_key_room(patch_doctor):
    patch_doctor(
        _doctor(doctor_id=42, specialty="cardio", department=_department("cardiology"))
    )
    assert _has_department_access(_user("cardio"), "cardiology", _FAKE_DB) is True


def test_doctor_department_key_match_is_case_and_space_insensitive(patch_doctor):
    patch_doctor(
        _doctor(doctor_id=42, specialty="cardio", department=_department("cardiology"))
    )
    assert _has_department_access(_user("cardio"), " Cardiology ", _FAKE_DB) is True


def test_doctor_denied_foreign_department_key_room(patch_doctor):
    # The P1 fail-first matrix: derma → 'cardiology' must be denied.
    patch_doctor(
        _doctor(doctor_id=73, specialty="derma", department=_department("dermatology"))
    )
    assert _has_department_access(_user("derma"), "cardiology", _FAKE_DB) is False


def test_doctor_specialty_family_matches_department_room(patch_doctor):
    # Own specialty name (no department row): 'derma' doctor may join the
    # 'derma' room; the dental family expands through specialty_variants.
    patch_doctor(_doctor(doctor_id=73, specialty="derma", department=None))
    assert _has_department_access(_user("derma"), "derma", _FAKE_DB) is True

    patch_doctor(_doctor(doctor_id=5, specialty="dentistry", department=None))
    for dental_spelling in ("dentistry", "dental", "stomatology", "dentist"):
        assert (
            _has_department_access(_user("dentist"), dental_spelling, _FAKE_DB) is True
        )


@pytest.mark.parametrize(
    ("specialty", "department"),
    [
        ("cardio", "cardiology"),
        ("cardiology", "cardio"),
        ("cardiologist", "cardio"),
        ("derma", "dermatology"),
        ("dermatology", "derma"),
        ("dermatologist", "derma"),
    ],
)
def test_cardio_and_derma_specialty_aliases_match_department_rooms(
    patch_doctor, specialty, department
):
    patch_doctor(_doctor(specialty=specialty, department=None))
    assert _has_department_access(_user("Doctor"), department, _FAKE_DB) is True


def test_doctor_denied_department_outside_own_family(patch_doctor):
    patch_doctor(_doctor(doctor_id=73, specialty="derma", department=None))
    for foreign in ("cardiology", "dentistry", "stomatology", "laboratory"):
        assert _has_department_access(_user("derma"), foreign, _FAKE_DB) is False


def test_doctor_without_department_or_specialty_denied_department_rooms(patch_doctor):
    patch_doctor(_doctor(doctor_id=42, specialty="", department=None))
    assert _has_department_access(_user("cardio"), "cardiology", _FAKE_DB) is False


@pytest.mark.parametrize("specialty", ["", "general"])
def test_incomplete_doctor_profiles_do_not_own_department_rooms(
    monkeypatch, specialty
):
    doctor = _doctor(specialty=specialty, department=None)
    monkeypatch.setattr(
        "app.crud.clinic.get_doctor_by_user_id", lambda db, user_id: doctor
    )
    monkeypatch.setattr(
        "app.crud.queue_owner_policy.eligible_real_doctor",
        lambda db, doctor_id: bool(doctor.active and doctor.specialty.strip() not in ("", "general")),
    )
    assert _has_department_access(_user("Doctor"), "general", _FAKE_DB) is False
    assert _has_department_access(_user("Doctor"), "specialist_42", _FAKE_DB) is False


def test_inactive_doctor_profile_is_denied_while_user_remains_active(monkeypatch):
    inactive = _doctor(doctor_id=42, specialty="cardiology", active=False)
    monkeypatch.setattr(
        "app.crud.clinic.get_doctor_by_user_id", lambda db, user_id: inactive
    )
    monkeypatch.setattr(
        "app.crud.queue_owner_policy.eligible_real_doctor",
        lambda db, doctor_id: bool(inactive.active),
    )
    assert _has_department_access(_user("Doctor"), "specialist_42", _FAKE_DB) is False

    active = _doctor(doctor_id=42, specialty="cardiology", active=True)
    monkeypatch.setattr(
        "app.crud.clinic.get_doctor_by_user_id", lambda db, user_id: active
    )
    monkeypatch.setattr(
        "app.crud.queue_owner_policy.eligible_real_doctor",
        lambda db, doctor_id: bool(active.active),
    )
    assert _has_department_access(_user("Doctor"), "specialist_42", _FAKE_DB) is True


# ---------------------------------------------------------------------------
# Fail closed: doctor-family role without a doctor row
# ---------------------------------------------------------------------------


def test_doctor_role_without_doctor_row_owns_nothing(patch_doctor):
    patch_doctor(None)
    assert _has_department_access(_user("Doctor"), "specialist_42", _FAKE_DB) is False
    assert _has_department_access(_user("Doctor"), "cardiology", _FAKE_DB) is False


# ---------------------------------------------------------------------------
# Canonical administrators / Registrar keep full cross-department access
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role", ["Admin", "admin", "SuperAdmin", "superadmin", "Registrar", "registrar"]
)
def test_admin_and_registrar_variants_keep_full_access_without_doctor_row(
    patch_doctor, role
):
    patch_doctor(None)  # must not even be consulted
    assert (
        _has_department_access(_user(role), "specialist_999", _FAKE_DB) is True
    )
    assert _has_department_access(_user(role), "dermatology", _FAKE_DB) is True


def test_is_superuser_gets_the_same_cross_department_scope(patch_doctor):
    patch_doctor(None)
    assert (
        _has_department_access(
            _user("Patient", is_superuser=True), "specialist_999", _FAKE_DB
        )
        is True
    )


# ---------------------------------------------------------------------------
# Non-staff roles stay rejected exactly as before
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role", ["Patient", "patient", "Nurse", "Lab", "laboratory", "Cashier", ""]
)
def test_non_staff_roles_rejected_every_room(patch_doctor, role):
    patch_doctor(_doctor(doctor_id=42, specialty="cardio"))
    for room in ("specialist_42", "specialist_73", "cardiology", "dermatology"):
        assert _has_department_access(_user(role), room, _FAKE_DB) is False


def test_doctor_family_membership_stays_staff_only(patch_doctor):
    # WS-POSTMERGE-02 guard retained: no privilege widening beyond the
    # staff doctor family + admin/registrar.
    patch_doctor(None)
    for role in ("Lab", "laboratory", "Patient", "Cashier", "Guest"):
        assert _has_department_access(_user(role), "cardiology", _FAKE_DB) is False


@pytest.mark.parametrize("role", sorted(ws_auth._STAFF_DOCTOR_ROLES))
def test_every_canonical_doctor_role_spelling_is_recognized(patch_doctor, role):
    patch_doctor(_doctor(doctor_id=42, specialty="cardiology"))
    assert _has_department_access(_user(role), "specialist_42", _FAKE_DB) is True
