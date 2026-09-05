"""
Система ролей пользователей
Централизованное определение ролей для системы авторизации
"""

from enum import Enum


class Roles(str, Enum):  # noqa: UP042  # manual-review: StrEnum migration needs Python 3.11+ compat check
    """Роли пользователей в системе"""

    # Основные роли
    ADMIN = "Admin"
    REGISTRAR = "Registrar"
    DOCTOR = "Doctor"
    LAB = "Lab"
    CASHIER = "Cashier"
    # M-2 (Manager vocabulary closure): MANAGER removed. The member was kept
    # through M-1 only as a read-compatibility carrier; the ops deactivation
    # of the single production row (smoke_manager, id=20, 2026-09-04) closed
    # that window. The stored tombstone row keeps role='Manager' as a RAW
    # STRING — users.role is String(20) and every read/serialization surface
    # uses plain str, so the row survives intact (audit history) with zero
    # privileges: logins are rejected at the auth layer (is_active=false)
    # and every require_roles grant list dropped the spelling in M-1D. Like
    # Receptionist (E-4) the enum no longer admits the deprecated spelling;
    # unlike Receptionist there is no canonical successor (privileges were
    # removed, not aliased).

    # Специализированные роли врачей
    CARDIO = "cardio"
    DERMA = "derma"
    DENTIST = "dentist"

    # Дополнительные роли
    # N-3 (Nurse retirement): NURSE removed — production census 2026-09-05
    # found 0 stored rows (normalized census clean); every grant list
    # (analytics/files/notifications/patients/require_staff) dropped the
    # spelling in this change. No canonical successor: the role never
    # shipped as a product surface.
    # E-4 (Receptionist alias removal): RECEPTIONIST decommissioned — the
    # legacy spelling had a canonical successor (Registrar, REC track), the
    # production table held 0 rows (SQL evidence 2026-09-02), and the last
    # read/alias surfaces were removed in E-4.
    PATIENT = "Patient"
    SUPER_ADMIN = "SuperAdmin"


# Константы для проверки ролей
CRITICAL_ROLES = {
    Roles.ADMIN,
    Roles.REGISTRAR,
    Roles.LAB,
    Roles.DOCTOR,
    Roles.CASHIER,
    Roles.CARDIO,
    Roles.DERMA,
    Roles.DENTIST,
}

# Роли с административными правами
# M-1 (Manager deprecation): Manager removed from the administrative set —
# a deprecated legacy/synthetic role (production: 1 automated row, 0 human
# users) must not be treated as administrative anywhere. Caller evidence at
# the M-1 change (exhaustive repo search, app + tests): is_admin_role()/
# ADMIN_ROLES had ZERO call sites, so the change was behavior-neutral.
# M-2 (vocabulary closure): the enum member itself is gone; this set no
# longer mentions Manager at all.
ADMIN_ROLES = {
    Roles.ADMIN,
    Roles.SUPER_ADMIN,
}

# M-2b (Codex review follow-up on #3049): spellings decommissioned from the
# RBAC vocabulary that must ALSO stay out of the DB-backed role catalog
# (public.roles / /api/v1/roles). Manager was closed by M-2 (2026-09-05,
# ops-deactivated tombstone row); Receptionist was closed by E-4;
# Nurse was closed by N-3 (2026-09-05, production census found 0 stored
# rows - the role never shipped as a product surface).
# (§4.1.27, canonical successor Registrar). The roles-catalog boundary
# (RoleCreate validation + /roles/options filtering) checks this set so a
# hand-created catalog row cannot resurrect a retired spelling into the
# user-management dropdown mirror. Case-insensitive by design (catalog
# names are free-form strings; 'manager'/'Manager' both match).
RETIRED_ROLE_SPELLINGS: frozenset[str] = frozenset({"manager", "receptionist", "nurse"})

def is_retired_role_spelling(value: object) -> bool:
    """Case-insensitive check against the retired RBAC vocabulary."""
    return normalize_role_value(value) in RETIRED_ROLE_SPELLINGS

# QD-1.1 (queue resource role cleanup, 2026-09-06): internal-only sentinel
# spelling for the synthetic queue-resource accounts provisioned by
# 0055_queue_resource_provisioning (ecg_resource/general_resource seeded
# with role='Nurse', resurrecting the spelling N-3 had just retired under
# the verified "0 stored rows" premise; migration 0056 moves the two rows
# to 'Resource' and restores the Nurse stored-count invariant).
# 'Resource' is NOT a human/product role: it never joins the Roles enum,
# the user-management write vocabulary, the roles catalog/options, or any
# grant list; the auth layer rejects logins for it (structural non-login).
# Queue machinery is deliberately role-agnostic: QD-0 resolves resource
# staff by username + is_active, never by role.
INTERNAL_ONLY_ROLE_SPELLINGS: frozenset[str] = frozenset({"resource"})


def is_internal_only_role_spelling(value: object) -> bool:
    """Case-insensitive check against the internal-only sentinel vocabulary."""
    return normalize_role_value(value) in INTERNAL_ONLY_ROLE_SPELLINGS


def is_login_blocked_role(value: object) -> bool:
    """Internal-only sentinel roles are structural non-logins (QD-1.1)."""
    return is_internal_only_role_spelling(value)


# Роли врачей
DOCTOR_ROLES = {
    Roles.DOCTOR,
    Roles.CARDIO,
    Roles.DERMA,
    Roles.DENTIST,
}

def normalize_role_value(role: object) -> str:
    """Extract a role's string value and normalize case/whitespace.

    Roles are stored as raw strings in the DB and arrive either as plain
    strings or as the ``Roles`` str-enum, so the raw value must be
    extracted before any set membership test (str(Roles.X) would yield
    'Roles.X', not the value).
    """
    return str(getattr(role, "value", role)).strip().lower()


# Every doctor-role spelling accepted anywhere in the repo's IAM surfaces
# (Codex round-7/round-8): core/roles.py DOCTOR_ROLES canonical enum values,
# the user_mgmt/_core.py PR-26 doctor-role tuple, and the cardio/derma
# specialist-surface tuples (cardio.py CARDIO_ROLES, derma.py DERMA_ROLES).
# Single source of truth for role gates that must recognize doctor accounts
# regardless of the exact spelling their row carries (appointments schedule
# ownership, booking eligibility owner checks, ...).
DOCTOR_ROLE_SPELLINGS = frozenset(
    spelling.strip().lower()
    for spelling in (
        {str(getattr(r, "value", r)) for r in DOCTOR_ROLES}
        | {
            "Cardiologist",
            "cardiology",
            "cardiologist",
            "Dermatologist",
            "dermatology",
            "dermatologist",
            "Dentist",
            "dentistry",
        }
    )
)


def is_doctor_role_spelling(role: object) -> bool:
    """Case-insensitive doctor-role check against the full IAM vocabulary."""
    return normalize_role_value(role) in DOCTOR_ROLE_SPELLINGS


# require_roles gate members admitting the WHOLE doctor family
# (canonical "Doctor" + every legacy spelling listed in
# DOCTOR_ROLE_SPELLINGS). require_roles() is case-insensitive
# (app/core/security.py), so one lowercase member per spelling is enough
# - spell them straight from the SSOT frozenset so a future vocabulary
# addition is picked up here too. Spread with ``*`` into require_roles:
#     require_roles("Admin", "Registrar", *DOCTOR_FAMILY_GATE_ROLES)
# (RBAC unification D-3: visits/patients/appointment-flow used to admit
# only the exact "Doctor" spelling and 403'd legacy doctor accounts that
# EMR v2 and the specialist panels accepted - single behavior now.)
DOCTOR_FAMILY_GATE_ROLES: tuple[str, ...] = tuple(sorted(DOCTOR_ROLE_SPELLINGS))

# Роли персонала
# E-4: Roles.RECEPTIONIST removed — canonical Registrar is the front-desk
# staff role (REC track); the legacy spelling is decommissioned.
STAFF_ROLES = {
    Roles.REGISTRAR,
    Roles.LAB,
    Roles.CASHIER,
}

# NOTE (M-2): the hierarchy map covers the canonical vocabulary only — the
# legacy Manager entry (level 8) was retired with the spelling, the same
# way E-4 retired Receptionist's level 3. A stored raw 'Manager' string
# now scores 0 here; this is descriptive only: the table is consulted via
# has_role_permission(), which has zero external callers (verified by
# exhaustive search), and Manager's privileges were governed by the
# require_roles() grant lists, all of which dropped the spelling in M-1D.


def is_admin_role(role: str) -> bool:
    """Проверяет, является ли роль административной"""
    return role in ADMIN_ROLES


def is_doctor_role(role: str) -> bool:
    """Проверяет, является ли роль врачебной"""
    return role in DOCTOR_ROLES


def is_staff_role(role: str) -> bool:
    """Проверяет, является ли роль персонала"""
    return role in STAFF_ROLES


def is_critical_role(role: str) -> bool:
    """Проверяет, является ли роль критической для системы"""
    return role in CRITICAL_ROLES


def get_role_hierarchy(role: str) -> int:
    """Возвращает уровень иерархии роли (чем выше число, тем больше прав)"""
    hierarchy = {
        Roles.PATIENT: 1,
        # N-3: Roles.NURSE: 2 retired with the spelling (the level table
        # covers the canonical vocabulary only).
        # E-4: Roles.RECEPTIONIST: 3 removed — the level table covers the
        # canonical vocabulary only (level 3 retired with the spelling).
        Roles.CASHIER: 4,
        Roles.LAB: 5,
        Roles.REGISTRAR: 6,
        Roles.DOCTOR: 7,
        Roles.CARDIO: 7,
        Roles.DERMA: 7,
        Roles.DENTIST: 7,
        # M-2: Manager (8) retired with the deprecated spelling.
        Roles.ADMIN: 9,
        Roles.SUPER_ADMIN: 10,
    }
    return hierarchy.get(role, 0)


def has_role_permission(user_role: str, required_role: str) -> bool:
    """Проверяет, имеет ли пользователь достаточные права для доступа"""
    return get_role_hierarchy(user_role) >= get_role_hierarchy(required_role)
