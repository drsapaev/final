"""
Система ролей пользователей
Централизованное определение ролей для системы авторизации
"""

from enum import Enum


class Roles(str, Enum):
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

