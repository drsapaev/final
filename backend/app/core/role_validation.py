"""
Валидация и проверка системы ролей
Предотвращает нарушения в системе авторизации
"""

import logging
from typing import List

logger = logging.getLogger(__name__)

# Критические роли системы - НЕ ИЗМЕНЯТЬ без обновления тестов!
CRITICAL_ROLES = {
    "Admin",
    "Registrar",
    "Lab",
    "Doctor",
    "Cashier",
    "cardio",
    "derma",
    "dentist",
}

# Ожидаемые маршруты для ролей
ROLE_ROUTES = {
    "Admin": "/admin",
    "Registrar": "/registrar-panel",
    "Lab": "/lab-panel",
    "Doctor": "/doctor-panel",
    "Cashier": "/cashier-panel",
    "cardio": "/cardiologist",
    "derma": "/dermatologist",
    "dentist": "/dentist",
}

# Ожидаемые API endpoints для ролей
ROLE_API_ENDPOINTS = {
    "cardio": ["/api/v1/cardio/"],
    "derma": ["/api/v1/derma/"],
    "dentist": ["/api/v1/dental/"],
    "Lab": ["/api/v1/lab/"],
}


def validate_role_exists(role: str) -> bool:
    """Проверяет, что роль существует в системе"""
    if role not in CRITICAL_ROLES:
        logger.warning(f"Неизвестная роль: {role}")
        return False
    return True


def validate_role_route(role: str, expected_route: str) -> bool:
    """Проверяет, что роль соответствует ожидаемому маршруту"""
    if role not in ROLE_ROUTES:
        logger.error(f"Роль {role} не имеет определенного маршрута")
        return False

    expected = ROLE_ROUTES[role]
    if expected_route != expected:
        logger.error(
            f"Неправильный маршрут для роли {role}: ожидался {expected}, получен {expected_route}"
        )
        return False

    return True


def validate_role_api_access(role: str, endpoint: str) -> bool:
    """Проверяет, что роль имеет доступ к соответствующему API"""
    if role not in ROLE_API_ENDPOINTS:
        return True  # Роль не имеет специализированных endpoints

    allowed_endpoints = ROLE_API_ENDPOINTS[role]
    for allowed in allowed_endpoints:
        if endpoint.startswith(allowed):
            return True

    logger.warning(f"Роль {role} пытается получить доступ к {endpoint}")
    return False


def get_expected_roles_for_endpoint(endpoint: str) -> List[str]:
    """Возвращает ожидаемые роли для API endpoint"""
    if endpoint.startswith("/api/v1/cardio/"):
        return ["Admin", "Doctor", "cardio"]
    elif endpoint.startswith("/api/v1/derma/"):
        return ["Admin", "Doctor", "derma"]
    elif endpoint.startswith("/api/v1/dental/"):
        return ["Admin", "Doctor", "dentist"]
    elif endpoint.startswith("/api/v1/lab/"):
        return ["Admin", "Lab"]
    else:
        return ["Admin"]  # По умолчанию только админ


def log_role_access(user_role: str, endpoint: str, allowed: bool):
    """Логирует доступ роли к endpoint"""
    status = "РАЗРЕШЕН" if allowed else "ЗАПРЕЩЕН"
    logger.info(f"Доступ {status}: роль {user_role} -> {endpoint}")


def validate_critical_user_roles():
    """Проверяет, что все критические роли определены корректно"""
    issues = []

    # Проверяем, что все критические роли имеют маршруты
    for role in CRITICAL_ROLES:
        if role not in ROLE_ROUTES:
            issues.append(f"Роль {role} не имеет определенного маршрута")

    # Проверяем, что все маршруты имеют соответствующие роли
    for route_role, route in ROLE_ROUTES.items():
        if route_role not in CRITICAL_ROLES:
            issues.append(f"Маршрут {route} имеет неизвестную роль {route_role}")

    if issues:
        logger.error("Проблемы в системе ролей:")
        for issue in issues:
            logger.error(f"  - {issue}")
        return False

    logger.info("Система ролей валидна")
    return True


# Автоматическая валидация при импорте модуля
if __name__ != "__main__":
    validate_critical_user_roles()
