"""
RBAC (Role-Based Access Control) - SSOT для ролей и разрешений AI.

Единственное место для определения:
- Пользовательских ролей
- AI разрешений
- Матрицы доступа
"""

from enum import Enum
from typing import Dict, Set, Optional
from functools import wraps

from fastapi import Depends, HTTPException, status


class UserRole(str, Enum):
    """
    SSOT для ролей пользователей.
    
    Все строковые проверки ролей должны проходить через from_string().
    """
    ADMIN = "admin"
    DOCTOR = "doctor"
    REGISTRAR = "registrar"
    LAB = "lab"
    NURSE = "nurse"
    CASHIER = "cashier"
    
    # Специализации (алиасы для doctor с дополнительными permissions)
    CARDIOLOGIST = "cardio"
    DERMATOLOGIST = "derma"
    DENTIST = "dentist"
    
    @classmethod
    def from_string(cls, role_str: str) -> "UserRole":
        """
        Нормализация строковых ролей.
        
        Решает проблему разных написаний: "Doctor", "doctor", "doc", "cardio", "cardiology"
        
        Args:
            role_str: Строковое представление роли
            
        Returns:
            Нормализованный UserRole enum
            
        Raises:
            ValueError: Если роль неизвестна
        """
        role_map = {
            # Admin aliases
            "admin": cls.ADMIN,
            "administrator": cls.ADMIN,
            "Admin": cls.ADMIN,
            
            # Doctor aliases
            "doctor": cls.DOCTOR,
            "doc": cls.DOCTOR,
            "Doctor": cls.DOCTOR,
            "physician": cls.DOCTOR,
            
            # Cardiology aliases
            "cardio": cls.CARDIOLOGIST,
            "cardiology": cls.CARDIOLOGIST,
            "cardiologist": cls.CARDIOLOGIST,
            "Cardiologist": cls.CARDIOLOGIST,
            "CardioDoctor": cls.CARDIOLOGIST,
            
            # Dermatology aliases
            "derma": cls.DERMATOLOGIST,
            "dermatology": cls.DERMATOLOGIST,
            "dermatologist": cls.DERMATOLOGIST,
            "Dermatologist": cls.DERMATOLOGIST,
            
            # Dentist aliases
            "dentist": cls.DENTIST,
            "stomatology": cls.DENTIST,
            "stomatologist": cls.DENTIST,
            "Dentist": cls.DENTIST,
            
            # Registrar aliases
            "registrar": cls.REGISTRAR,
            "Registrar": cls.REGISTRAR,
            "reception": cls.REGISTRAR,
            
            # Lab aliases
            "lab": cls.LAB,
            "laboratory": cls.LAB,
            "Lab": cls.LAB,
            "laborant": cls.LAB,
            
            # Nurse aliases
            "nurse": cls.NURSE,
            "Nurse": cls.NURSE,
            
            # Cashier aliases
            "cashier": cls.CASHIER,
            "Cashier": cls.CASHIER,
        }
        
        normalized = role_str.strip()
        
        if normalized in role_map:
            return role_map[normalized]
        
        # Fallback: пробуем как enum value (lowercase)
        try:
            return cls(normalized.lower())
        except ValueError:
            raise ValueError(f"Unknown role: {role_str}. Valid roles: {[r.value for r in cls]}")
    
    def is_medical_professional(self) -> bool:
        """Является ли роль медицинским специалистом"""
        return self in {
            UserRole.DOCTOR,
            UserRole.CARDIOLOGIST,
            UserRole.DERMATOLOGIST,
            UserRole.DENTIST,
            UserRole.NURSE,
            UserRole.LAB,
        }


class AIPermission(str, Enum):
    """
    Разрешения для AI операций.
    
    Granular permissions для точного контроля доступа к AI функциям.
    """
    # Diagnostic permissions
    DIAGNOSE = "ai:diagnose"  # Диагноз, дифференциальный диагноз, лечение
    ANALYZE_LAB = "ai:analyze_lab"  # Интерпретация лабораторных анализов
    ANALYZE_IMAGE = "ai:analyze_image"  # Анализ медицинских изображений
    SUGGEST_ICD10 = "ai:suggest_icd10"  # Подсказки кодов МКБ-10
    
    # Communication permissions
    CHAT = "ai:chat"  # Базовый чат с AI
    CHAT_MEDICAL = "ai:chat_medical"  # Медицинский чат (с доступом к диагностике)
    
    # Administrative permissions
    ADMIN_AI = "ai:admin"  # Настройка AI (ключи, промпты, провайдеры)
    VIEW_STATS = "ai:view_stats"  # Просмотр статистики и аналитики AI
    VIEW_AUDIT = "ai:view_audit"  # Просмотр аудит логов AI
    
    # Document permissions
    ANALYZE_DOCUMENT = "ai:analyze_document"  # Анализ медицинских документов
    
    # Triage permissions
    SYMPTOM_CHECK = "ai:symptom_check"  # Проверка симптомов для триажа


# RBAC Matrix: Роль -> Набор разрешений
ROLE_PERMISSIONS: Dict[UserRole, Set[AIPermission]] = {
    UserRole.ADMIN: {
        AIPermission.ADMIN_AI,
        AIPermission.VIEW_STATS,
        AIPermission.VIEW_AUDIT,
        AIPermission.CHAT,
    },
    
    UserRole.DOCTOR: {
        AIPermission.DIAGNOSE,
        AIPermission.ANALYZE_LAB,
        AIPermission.ANALYZE_IMAGE,
        AIPermission.SUGGEST_ICD10,
        AIPermission.CHAT,
        AIPermission.CHAT_MEDICAL,
        AIPermission.ANALYZE_DOCUMENT,
    },
    
    UserRole.CARDIOLOGIST: {
        AIPermission.DIAGNOSE,
        AIPermission.ANALYZE_LAB,
        AIPermission.ANALYZE_IMAGE,  # ECG interpretation
        AIPermission.SUGGEST_ICD10,
        AIPermission.CHAT,
        AIPermission.CHAT_MEDICAL,
        AIPermission.ANALYZE_DOCUMENT,
    },
    
    UserRole.DERMATOLOGIST: {
        AIPermission.DIAGNOSE,
        AIPermission.ANALYZE_IMAGE,  # Skin/dermoscopy analysis - ключевое!
        AIPermission.SUGGEST_ICD10,
        AIPermission.CHAT,
        AIPermission.CHAT_MEDICAL,
        AIPermission.ANALYZE_DOCUMENT,
    },
    
    UserRole.DENTIST: {
        AIPermission.DIAGNOSE,
        AIPermission.ANALYZE_IMAGE,  # Dental X-rays
        AIPermission.SUGGEST_ICD10,
        AIPermission.CHAT,
        AIPermission.CHAT_MEDICAL,
    },
    
    UserRole.REGISTRAR: {
        AIPermission.CHAT,  # Только базовый чат, БЕЗ диагнозов!
        AIPermission.SYMPTOM_CHECK,  # Для триажа
    },
    
    UserRole.LAB: {
        AIPermission.ANALYZE_LAB,  # Ключевое для лаборанта
        AIPermission.CHAT,
    },
    
    UserRole.NURSE: {
        AIPermission.CHAT,
        AIPermission.SYMPTOM_CHECK,
    },
    
    UserRole.CASHIER: {
        # Cashier не имеет AI разрешений
    },
}


def has_permission(user_role: str, permission: AIPermission) -> bool:
    """
    Проверка наличия разрешения у пользователя.
    
    Args:
        user_role: Роль пользователя (строка)
        permission: Требуемое разрешение
        
    Returns:
        True если разрешение есть, False иначе
    """
    try:
        role = UserRole.from_string(user_role)
        return permission in ROLE_PERMISSIONS.get(role, set())
    except ValueError:
        return False


def get_user_permissions(user_role: str) -> Set[AIPermission]:
    """
    Получить все разрешения пользователя.
    
    Args:
        user_role: Роль пользователя (строка)
        
    Returns:
        Набор разрешений
    """
    try:
        role = UserRole.from_string(user_role)
        return ROLE_PERMISSIONS.get(role, set())
    except ValueError:
        return set()


def require_ai_permission(permission: AIPermission):
    """
    FastAPI Dependency для проверки AI разрешений.
    
    Usage:
        @router.post("/diagnose")
        async def diagnose(
            current_user: User = Depends(require_ai_permission(AIPermission.DIAGNOSE))
        ):
            ...
    
    Args:
        permission: Требуемое разрешение
        
    Returns:
        Dependency function
    """
    from app.api.deps import get_current_user
    from app.models.user import User
    
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if not has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Permission denied",
                    "required_permission": permission.value,
                    "user_role": current_user.role,
                    "hint": f"Role '{current_user.role}' does not have '{permission.value}' permission"
                }
            )
        return current_user
    
    return dependency


def require_any_ai_permission(*permissions: AIPermission):
    """
    FastAPI Dependency для проверки ЛЮБОГО из указанных разрешений.
    
    Usage:
        @router.post("/analyze")
        async def analyze(
            current_user: User = Depends(require_any_ai_permission(
                AIPermission.DIAGNOSE, AIPermission.ANALYZE_LAB
            ))
        ):
            ...
    """
    from app.api.deps import get_current_user
    from app.models.user import User
    
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        user_permissions = get_user_permissions(current_user.role)
        
        if not any(perm in user_permissions for perm in permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Permission denied",
                    "required_permissions": [p.value for p in permissions],
                    "user_role": current_user.role,
                    "hint": f"Role '{current_user.role}' requires at least one of: {[p.value for p in permissions]}"
                }
            )
        return current_user
    
    return dependency


def require_all_ai_permissions(*permissions: AIPermission):
    """
    FastAPI Dependency для проверки ВСЕХ указанных разрешений.
    """
    from app.api.deps import get_current_user
    from app.models.user import User
    
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        user_permissions = get_user_permissions(current_user.role)
        
        missing = [p for p in permissions if p not in user_permissions]
        
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Permission denied",
                    "missing_permissions": [p.value for p in missing],
                    "user_role": current_user.role,
                }
            )
        return current_user
    
    return dependency
