"""WS-POSTMERGE-02: department-access role family contract.

The queue/display WebSocket plane authorizes room subscriptions through
``_has_department_access``. The legacy implementation honored only the four
literal spellings ``Doctor``, ``Cardiologist``, ``Dermatologist`` and
``Dentist``; the rest of the system (``messages_api_service.py``,
``context_facades/iam_facade.py``) also uses the canonical lowercase
specialty spellings ``cardio``/``derma``/``dentist`` plus the family variants
``cardiology``/``cardiologist``/``dermatologist``. Specialists created with
those roles were closed with WS 1008 on their own departments' queue rooms.

All principals in this suite are synthetic namespaces; no database, JWT,
network or patient data is touched.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.v1.endpoints.websocket_auth import _has_department_access


def _user(role: str) -> SimpleNamespace:
    return SimpleNamespace(id=1, username=f"{role.lower()}-ws-user", role=role)


# (role, expected_access) pairs. Exact legacy spellings stay accepted; the
# canonical specialty spellings used across the codebase must also pass.
# Everything outside the staff role family (Patient, unknown strings) stays
# rejected exactly as before.
ROLE_CASES = [
    # Legacy exact spellings — unchanged behavior.
    ("Admin", True),
    ("Registrar", True),
    ("Doctor", True),
    ("Cardiologist", True),
    ("Dermatologist", True),
    ("Dentist", True),
    # Canonical lowercase specialty spellings used by the system
    # (messages_api_service, iam_facade).
    ("cardio", True),
    ("derma", True),
    ("dentist", True),
    # Family variants present in the IAM permission-role map.
    ("cardiology", True),
    ("cardiologist", True),
    ("dermatologist", True),
    # Case-insensitive legacy spellings.
    ("doctor", True),
    ("DOCTOR", True),
    ("CARDIOLOGIST", True),
    # Non-staff roles must remain rejected.
    ("Patient", False),
    ("patient", False),
    ("Nurse", False),
    ("Lab", False),
    ("laboratory", False),
    ("Cashier", False),
    ("", False),
]


@pytest.mark.parametrize(("role", "expected"), ROLE_CASES)
def test_has_department_access_role_family(role: str, expected: bool):
    assert _has_department_access(_user(role), "cardiology") is expected


def test_has_department_access_admin_any_department():
    assert _has_department_access(_user("Admin"), "stomatology") is True


def test_has_department_access_patient_rejected_every_department():
    for department in ("cardiology", "dermatology", "stomatology"):
        assert _has_department_access(_user("Patient"), department) is False


def test_doctor_family_membership_matches_staff_only():
    # Guard against accidental privilege widening: roles outside the
    # doctor family and admin/registrar must not gain queue-room access.
    for role in ("Lab", "laboratory", "Patient", "Cashier", "Guest"):
        assert _has_department_access(_user(role), "cardiology") is False
