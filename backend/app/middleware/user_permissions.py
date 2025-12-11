"""
Middleware для проверки прав пользователей
"""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.crud.user_management import user_group, user_permission, user_role
from app.db.session import get_db
from app.models.role_permission import UserGroup, UserPermissionOverride
from app.models.user import User

logger = logging.getLogger(__name__)


class UserPermissionsMiddleware:
    """Middleware для проверки прав пользователей"""

    def __init__(self):
        self.permission_cache = {}  # Кэш разрешений
        self.role_permissions = {
            "Admin": ["*"],  # Все права
            "Doctor": [
                "patients:read",
                "patients:write",
                "appointments:read",
                "appointments:write",
                "emr:read",
                "emr:write",
                "prescriptions:read",
                "prescriptions:write",
                "schedules:read",
                "schedules:write",
                "analytics:read",
            ],
            "Nurse": [
                "patients:read",
                "appointments:read",
                "emr:read",
                "schedules:read",
            ],
            "Receptionist": [
                "patients:read",
                "patients:write",
                "appointments:read",
                "appointments:write",
                "schedules:read",
                "schedules:write",
                "payments:read",
                "payments:write",
            ],
            "Patient": [
                "profile:read",
                "profile:write",
                "appointments:read",
                "payments:read",
            ],
        }

        self.endpoint_permissions = {
            # Управление пользователями
            "/api/v1/users": {
                "GET": ["users:read"],
                "POST": ["users:write"],
                "PUT": ["users:write"],
                "DELETE": ["users:delete"],
            },
            "/api/v1/users/{user_id}": {
                "GET": ["users:read"],
                "PUT": ["users:write"],
                "DELETE": ["users:delete"],
            },
            "/api/v1/users/{user_id}/profile": {
                "GET": ["users:read", "profile:read"],
                "PUT": ["users:write", "profile:write"],
            },
            "/api/v1/users/{user_id}/preferences": {
                "GET": ["users:read", "preferences:read"],
                "PUT": ["users:write", "preferences:write"],
            },
            "/api/v1/users/{user_id}/notifications": {
                "GET": ["users:read", "notifications:read"],
                "PUT": ["users:write", "notifications:write"],
            },
            "/api/v1/users/{user_id}/activity": {"GET": ["users:read", "audit:read"]},
            "/api/v1/users/stats": {"GET": ["users:read", "analytics:read"]},
            "/api/v1/users/bulk-action": {"POST": ["users:write", "users:bulk_action"]},
            "/api/v1/users/export": {"POST": ["users:read", "export:write"]},
            # Пациенты
            "/api/v1/patients": {
                "GET": ["patients:read"],
                "POST": ["patients:write"],
                "PUT": ["patients:write"],
                "DELETE": ["patients:delete"],
            },
            # Записи
            "/api/v1/appointments": {
                "GET": ["appointments:read"],
                "POST": ["appointments:write"],
                "PUT": ["appointments:write"],
                "DELETE": ["appointments:delete"],
            },
            # EMR
            "/api/v1/emr": {
                "GET": ["emr:read"],
                "POST": ["emr:write"],
                "PUT": ["emr:write"],
                "DELETE": ["emr:delete"],
            },
            # Платежи
            "/api/v1/payments": {
                "GET": ["payments:read"],
                "POST": ["payments:write"],
                "PUT": ["payments:write"],
                "DELETE": ["payments:delete"],
            },
            # Аналитика
            "/api/v1/analytics": {"GET": ["analytics:read"]},
            # Настройки
            "/api/v1/settings": {"GET": ["settings:read"], "PUT": ["settings:write"]},
        }

    def get_required_permissions(self, path: str, method: str) -> List[str]:
        """Получить требуемые разрешения для endpoint"""
        # Ищем точное совпадение
        if path in self.endpoint_permissions:
            return self.endpoint_permissions[path].get(method, [])

        # Ищем по паттерну
        for pattern, methods in self.endpoint_permissions.items():
            if self._match_pattern(pattern, path):
                return methods.get(method, [])

        return []

    def _match_pattern(self, pattern: str, path: str) -> bool:
        """Проверяет, соответствует ли путь паттерну"""
        # Простая проверка для паттернов с {param}
        if "{" in pattern and "}" in pattern:
            # Заменяем {param} на .* для regex
            import re

            regex_pattern = re.sub(r'\{[^}]+\}', '.*', pattern)
            return re.match(regex_pattern, path) is not None

        return pattern == path

    def get_user_permissions(self, db: Session, user: User) -> List[str]:
        """Получить разрешения пользователя"""
        try:
            # Проверяем кэш
            cache_key = f"user_{user.id}_permissions"
            if cache_key in self.permission_cache:
                return self.permission_cache[cache_key]

            permissions = []

            # Получаем разрешения роли
            if user.role in self.role_permissions:
                permissions.extend(self.role_permissions[user.role])

            # Если суперпользователь, добавляем все права
            if user.is_superuser:
                permissions = ["*"]

            # Получаем дополнительные разрешения из БД
            if user.user_role:
                role_permissions = user_role.get_role_permissions(db, user.user_role.id)
                for perm in role_permissions:
                    if perm.name not in permissions:
                        permissions.append(perm.name)

            # Получаем разрешения групп
            for group in user.groups:
                group_permissions = self._get_group_permissions(db, group.id)
                for perm in group_permissions:
                    if perm not in permissions:
                        permissions.append(perm)

            # Кэшируем результат
            self.permission_cache[cache_key] = permissions

            return permissions

        except Exception as e:
            logger.error(f"Error getting user permissions: {e}")
            return []

    def _get_group_permissions(self, db: Session, group_id: int) -> List[str]:
        """Получить разрешения группы"""
        try:
            # TODO: Реализовать получение разрешений группы из БД
            return []
        except Exception as e:
            logger.error(f"Error getting group permissions: {e}")
            return []

    def has_permission(
        self, user_permissions: List[str], required_permissions: List[str]
    ) -> bool:
        """Проверяет, есть ли у пользователя нужные разрешения"""
        if not required_permissions:
            return True

        # Если есть право "*", разрешаем все
        if "*" in user_permissions:
            return True

        # Проверяем каждое требуемое разрешение
        for required_perm in required_permissions:
            if required_perm not in user_permissions:
                return False

        return True

    def check_resource_access(
        self, db: Session, user: User, resource_type: str, resource_id: int
    ) -> bool:
        """Проверяет доступ к конкретному ресурсу"""
        try:
            # Для профилей - пользователь может редактировать только свой профиль
            if resource_type == "profile" and user.id != resource_id:
                return user.role == "Admin"

            # Для настроек - пользователь может редактировать только свои настройки
            if resource_type == "preferences" and user.id != resource_id:
                return user.role == "Admin"

            # Для уведомлений - пользователь может редактировать только свои настройки
            if resource_type == "notifications" and user.id != resource_id:
                return user.role == "Admin"

            # Для активности - пользователь может просматривать только свою активность
            if resource_type == "activity" and user.id != resource_id:
                return user.role == "Admin"

            # Для других ресурсов - проверяем по роли
            if resource_type == "patients":
                return user.role in ["Admin", "Doctor", "Nurse", "Receptionist"]

            if resource_type == "appointments":
                return user.role in ["Admin", "Doctor", "Nurse", "Receptionist"]

            if resource_type == "emr":
                return user.role in ["Admin", "Doctor", "Nurse"]

            if resource_type == "payments":
                return user.role in ["Admin", "Receptionist"]

            if resource_type == "analytics":
                return user.role in ["Admin", "Doctor"]

            if resource_type == "settings":
                return user.role == "Admin"

            return True

        except Exception as e:
            logger.error(f"Error checking resource access: {e}")
            return False

    def clear_permission_cache(self, user_id: int = None):
        """Очистить кэш разрешений"""
        if user_id:
            cache_key = f"user_{user_id}_permissions"
            self.permission_cache.pop(cache_key, None)
        else:
            self.permission_cache.clear()

    async def __call__(  # type: ignore[override]
        self, request: Request, call_next: Callable[[Request], Any]
    ) -> Response:
        """Основной метод middleware"""
        try:
            # Получаем пользователя из состояния запроса
            user = getattr(request.state, 'user', None)
            if not user:
                # Если нет пользователя, пропускаем проверку (возможно, это публичный endpoint)
                response = await call_next(request)
                return response

            # Получаем требуемые разрешения
            required_permissions = self.get_required_permissions(
                request.url.path, request.method
            )
            if not required_permissions:
                # Если нет требований к разрешениям, пропускаем проверку
                response = await call_next(request)
                return response

            # Получаем разрешения пользователя
            db = next(get_db())
            try:
                user_permissions = self.get_user_permissions(db, user)

                # Проверяем разрешения
                if not self.has_permission(user_permissions, required_permissions):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Недостаточно прав для доступа к ресурсу",
                    )

                # Проверяем доступ к конкретному ресурсу
                resource_id = self._extract_resource_id(request.url.path)
                if resource_id:
                    resource_type = self._get_resource_type(request.url.path)
                    if not self.check_resource_access(
                        db, user, resource_type, resource_id
                    ):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Недостаточно прав для доступа к данному ресурсу",
                        )

                # Продолжаем обработку запроса
                response = await call_next(request)
                return response

            finally:
                db.close()

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"User permissions middleware error: {e}")
            # В случае ошибки пропускаем проверку
            response = await call_next(request)
            return response

    def _extract_resource_id(self, path: str) -> Optional[int]:
        """Извлекает ID ресурса из пути"""
        try:
            # Ищем паттерн /resource/{id}
            import re

            match = re.search(r'/(\w+)/(\d+)', path)
            if match:
                return int(match.group(2))
            return None
        except (ValueError, AttributeError):
            return None

    def _get_resource_type(self, path: str) -> str:
        """Определяет тип ресурса по пути"""
        try:
            # Ищем паттерн /resource/{id}
            import re

            match = re.search(r'/(\w+)/(\d+)', path)
            if match:
                return match.group(1)
            return "unknown"
        except AttributeError:
            return "unknown"


class UserActivityMiddleware:
    """Middleware для отслеживания активности пользователей"""

    def __init__(self):
        self.tracked_actions = ["GET", "POST", "PUT", "DELETE", "PATCH"]
        self.excluded_paths = [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
        ]

    def should_track(self, path: str, method: str) -> bool:
        """Определяет, нужно ли отслеживать активность"""
        # Пропускаем исключенные пути
        for excluded_path in self.excluded_paths:
            if path.startswith(excluded_path):
                return False

        # Отслеживаем только определенные методы
        return method in self.tracked_actions

    async def __call__(  # type: ignore[override]
        self, request: Request, call_next: Callable[[Request], Any]
    ) -> Response:
        """Основной метод middleware"""
        try:
            # Проверяем, нужно ли отслеживать активность
            if not self.should_track(request.url.path, request.method):
                response = await call_next(request)
                return response

            # Получаем пользователя
            user = getattr(request.state, 'user', None)
            if not user:
                response = await call_next(request)
                return response

            # Выполняем запрос
            response = await call_next(request)

            # Логируем активность
            try:
                db = next(get_db())
                try:
                    from app.crud.user_management import user_profile

                    user_profile.update_last_activity(db, user.id)
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"Error logging user activity: {e}")

            return response

        except Exception as e:
            logger.error(f"User activity middleware error: {e}")
            # В случае ошибки продолжаем обработку
            response = await call_next(request)
            return response


class UserRateLimitMiddleware:
    """Middleware для ограничения скорости запросов по пользователям"""

    def __init__(self):
        self.rate_limits = {
            "Admin": {"requests": 1000, "window": 3600},  # 1000 запросов в час
            "Doctor": {"requests": 500, "window": 3600},  # 500 запросов в час
            "Nurse": {"requests": 300, "window": 3600},  # 300 запросов в час
            "Receptionist": {"requests": 400, "window": 3600},  # 400 запросов в час
            "Patient": {"requests": 100, "window": 3600},  # 100 запросов в час
        }
        self.request_counts = {}  # В реальном приложении использовать Redis

    def get_rate_limit(self, user_role: str) -> Dict[str, int]:
        """Получить лимит для роли пользователя"""
        return self.rate_limits.get(user_role, {"requests": 100, "window": 3600})

    def is_rate_limited(self, user_id: int, user_role: str) -> bool:
        """Проверяет, превышен ли лимит скорости"""
        rate_limit = self.get_rate_limit(user_role)
        current_time = datetime.utcnow().timestamp()
        window = rate_limit["window"]
        max_requests = rate_limit["requests"]

        key = f"user_{user_id}"
        if key not in self.request_counts:
            self.request_counts[key] = []

        # Очищаем старые записи
        self.request_counts[key] = [
            timestamp
            for timestamp in self.request_counts[key]
            if current_time - timestamp < window
        ]

        # Проверяем лимит
        if len(self.request_counts[key]) >= max_requests:
            return True

        # Добавляем текущий запрос
        self.request_counts[key].append(current_time)
        return False

    async def __call__(  # type: ignore[override]
        self, request: Request, call_next: Callable[[Request], Any]
    ) -> Response:
        """Основной метод middleware"""
        try:
            # Получаем пользователя
            user = getattr(request.state, 'user', None)
            if not user:
                response = await call_next(request)
                return response

            # Проверяем лимит скорости
            if self.is_rate_limited(user.id, user.role):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Превышен лимит запросов для вашей роли. Попробуйте позже.",
                )

            # Продолжаем обработку запроса
            response = await call_next(request)
            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"User rate limit middleware error: {e}")
            # В случае ошибки пропускаем проверку
            response = await call_next(request)
            return response


# Создаем экземпляры middleware
user_permissions_middleware = UserPermissionsMiddleware()
user_activity_middleware = UserActivityMiddleware()
user_rate_limit_middleware = UserRateLimitMiddleware()
