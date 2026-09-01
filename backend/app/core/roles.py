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
    MANAGER = "Manager"

    # Специализированные роли врачей
    CARDIO = "cardio"
    DERMA = "derma"
    DENTIST = "dentist"

    # Дополнительные роли
    NURSE = "Nurse"
    RECEPTIONIST = "Receptionist"
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
ADMIN_ROLES = {
    Roles.ADMIN,
    Roles.SUPER_ADMIN,
    Roles.MANAGER,
}

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
STAFF_ROLES = {
    Roles.REGISTRAR,
    Roles.LAB,
    Roles.CASHIER,
    Roles.NURSE,
    Roles.RECEPTIONIST,
}


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
        Roles.NURSE: 2,
        Roles.RECEPTIONIST: 3,
        Roles.CASHIER: 4,
        Roles.LAB: 5,
        Roles.REGISTRAR: 6,
        Roles.DOCTOR: 7,
        Roles.CARDIO: 7,
        Roles.DERMA: 7,
        Roles.DENTIST: 7,
        Roles.MANAGER: 8,
        Roles.ADMIN: 9,
        Roles.SUPER_ADMIN: 10,
    }
    return hierarchy.get(role, 0)


def has_role_permission(user_role: str, required_role: str) -> bool:
    """Проверяет, имеет ли пользователь достаточные права для доступа"""
    return get_role_hierarchy(user_role) >= get_role_hierarchy(required_role)
