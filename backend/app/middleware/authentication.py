"""
Middleware для аутентификации и авторизации
"""
import logging
from typing import Optional, List
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.authentication_service import get_authentication_service
from app.crud.authentication import user, user_session, refresh_token
from app.models.user import User
from app.schemas.authentication import TokenValidationResponse

logger = logging.getLogger(__name__)

# Схема для Bearer токенов
security = HTTPBearer(auto_error=False)


class AuthenticationMiddleware:
    """Middleware для аутентификации"""
    
    def __init__(self):
        self.auth_service = get_authentication_service()
        self.excluded_paths = [
            "/docs",
            "/redoc", 
            "/openapi.json",
            "/health",
            "/auth/login",
            "/auth/register",
            "/auth/password-reset",
            "/auth/email-verification",
            "/2fa/setup",
            "/2fa/verify-setup"
        ]
        self.public_paths = [
            "/api/v1/health",
            "/api/v1/status",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/password-reset",
            "/api/v1/auth/email-verification",
            "/api/v1/2fa/setup",
            "/api/v1/2fa/verify-setup"
        ]

    def is_public_path(self, path: str) -> bool:
        """Проверяет, является ли путь публичным"""
        return any(path.startswith(public_path) for public_path in self.public_paths)

    def extract_token(self, request: Request) -> Optional[str]:
        """Извлекает токен из заголовка Authorization"""
        authorization = request.headers.get("Authorization")
        if not authorization:
            return None
        
        scheme, token = get_authorization_scheme_param(authorization)
        if scheme.lower() != "bearer":
            return None
        
        return token

    def validate_token(self, token: str, db: Session) -> Optional[TokenValidationResponse]:
        """Валидирует JWT токен"""
        try:
            # Проверяем токен
            payload = self.auth_service.verify_token(token, "access")
            if not payload:
                return None
            
            # Получаем пользователя
            user_id = int(payload.get("sub"))
            user_obj = user.get(db, user_id)
            if not user_obj or not user_obj.is_active:
                return None
            
            return TokenValidationResponse(
                valid=True,
                user_id=user_id,
                username=user_obj.username,
                role=user_obj.role,
                is_active=user_obj.is_active,
                expires_at=datetime.fromtimestamp(payload.get("exp")),
                requires_2fa=False  # TODO: проверка 2FA
            )
            
        except Exception as e:
            logger.error(f"Error validating token: {e}")
            return None

    def check_session(self, user_id: int, request: Request, db: Session) -> bool:
        """Проверяет активность сессии пользователя"""
        try:
            # Получаем отпечаток устройства
            device_fingerprint = self.get_device_fingerprint(request)
            if not device_fingerprint:
                return True  # Если нет отпечатка, пропускаем проверку
            
            # Проверяем активную сессию
            session = user_session.get_valid_session(db, device_fingerprint)
            if not session or session.user_id != user_id:
                return False
            
            # Обновляем активность
            user_session.update_activity(db, session.session_id)
            return True
            
        except Exception as e:
            logger.error(f"Error checking session: {e}")
            return True  # В случае ошибки пропускаем проверку

    def get_device_fingerprint(self, request: Request) -> Optional[str]:
        """Получает отпечаток устройства"""
        try:
            user_agent = request.headers.get("user-agent", "")
            ip_address = request.client.host if request.client else ""
            
            if not user_agent or not ip_address:
                return None
            
            import hashlib
            data = f"{user_agent}:{ip_address}"
            return hashlib.sha256(data.encode()).hexdigest()
            
        except Exception as e:
            logger.error(f"Error getting device fingerprint: {e}")
            return None

    async def __call__(self, request: Request, call_next):
        """Основной метод middleware"""
        try:
            # Пропускаем публичные пути
            if self.is_public_path(request.url.path):
                response = await call_next(request)
                return response
            
            # Извлекаем токен
            token = self.extract_token(request)
            if not token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Токен аутентификации не предоставлен",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            # Получаем сессию БД
            db = next(get_db())
            try:
                # Валидируем токен
                token_validation = self.validate_token(token, db)
                if not token_validation or not token_validation.valid:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Недействительный токен аутентификации",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                
                # Проверяем сессию
                if not self.check_session(token_validation.user_id, request, db):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Сессия недействительна или истекла",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                
                # Добавляем информацию о пользователе в запрос
                request.state.user_id = token_validation.user_id
                request.state.username = token_validation.username
                request.state.role = token_validation.role
                request.state.is_active = token_validation.is_active
                request.state.requires_2fa = token_validation.requires_2fa
                
                # Продолжаем обработку запроса
                response = await call_next(request)
                return response
                
            finally:
                db.close()
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication middleware error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка аутентификации"
            )


class AuthorizationMiddleware:
    """Middleware для авторизации"""
    
    def __init__(self):
        self.role_permissions = {
            "Admin": ["*"],  # Все права
            "Doctor": [
                "patients:read", "patients:write",
                "appointments:read", "appointments:write",
                "emr:read", "emr:write",
                "prescriptions:read", "prescriptions:write"
            ],
            "Nurse": [
                "patients:read",
                "appointments:read",
                "emr:read"
            ],
            "Receptionist": [
                "patients:read", "patients:write",
                "appointments:read", "appointments:write",
                "schedules:read", "schedules:write"
            ],
            "Patient": [
                "profile:read", "profile:write",
                "appointments:read"
            ]
        }
        
        self.path_permissions = {
            "/api/v1/users": ["Admin"],
            "/api/v1/auth/admin": ["Admin"],
            "/api/v1/patients": ["Admin", "Doctor", "Nurse", "Receptionist"],
            "/api/v1/appointments": ["Admin", "Doctor", "Nurse", "Receptionist"],
            "/api/v1/emr": ["Admin", "Doctor", "Nurse"],
            "/api/v1/prescriptions": ["Admin", "Doctor"],
            "/api/v1/schedules": ["Admin", "Receptionist"],
            "/api/v1/analytics": ["Admin", "Doctor"],
            "/api/v1/reports": ["Admin", "Doctor"],
            "/api/v1/settings": ["Admin"]
        }

    def get_required_permissions(self, path: str) -> List[str]:
        """Получает требуемые разрешения для пути"""
        for path_prefix, roles in self.path_permissions.items():
            if path.startswith(path_prefix):
                return roles
        return []

    def has_permission(self, user_role: str, required_roles: List[str]) -> bool:
        """Проверяет, есть ли у пользователя нужные разрешения"""
        if not required_roles:
            return True
        
        return user_role in required_roles

    async def __call__(self, request: Request, call_next):
        """Основной метод middleware"""
        try:
            # Получаем роль пользователя из состояния запроса
            user_role = getattr(request.state, 'role', None)
            if not user_role:
                # Если нет роли, пропускаем проверку (возможно, это публичный путь)
                response = await call_next(request)
                return response
            
            # Получаем требуемые разрешения для пути
            required_roles = self.get_required_permissions(request.url.path)
            if not required_roles:
                # Если нет требований к разрешениям, пропускаем проверку
                response = await call_next(request)
                return response
            
            # Проверяем разрешения
            if not self.has_permission(user_role, required_roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Недостаточно прав для доступа к ресурсу"
                )
            
            # Продолжаем обработку запроса
            response = await call_next(request)
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authorization middleware error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка авторизации"
            )


class RateLimitMiddleware:
    """Middleware для ограничения скорости запросов"""
    
    def __init__(self):
        self.rate_limits = {
            "login": {"requests": 5, "window": 300},  # 5 попыток за 5 минут
            "password_reset": {"requests": 3, "window": 3600},  # 3 попытки за час
            "api": {"requests": 100, "window": 3600},  # 100 запросов за час
        }
        self.request_counts = {}  # В реальном приложении использовать Redis

    def get_rate_limit_key(self, request: Request, limit_type: str = "api") -> str:
        """Получает ключ для ограничения скорости"""
        ip_address = request.client.host if request.client else "unknown"
        return f"{limit_type}:{ip_address}"

    def is_rate_limited(self, key: str, limit_type: str) -> bool:
        """Проверяет, превышен ли лимит скорости"""
        # Упрощенная реализация - в реальном приложении использовать Redis
        current_time = datetime.utcnow().timestamp()
        window = self.rate_limits[limit_type]["window"]
        max_requests = self.rate_limits[limit_type]["requests"]
        
        if key not in self.request_counts:
            self.request_counts[key] = []
        
        # Очищаем старые записи
        self.request_counts[key] = [
            timestamp for timestamp in self.request_counts[key]
            if current_time - timestamp < window
        ]
        
        # Проверяем лимит
        if len(self.request_counts[key]) >= max_requests:
            return True
        
        # Добавляем текущий запрос
        self.request_counts[key].append(current_time)
        return False

    async def __call__(self, request: Request, call_next):
        """Основной метод middleware"""
        try:
            # Определяем тип ограничения
            limit_type = "api"
            if request.url.path.endswith("/login"):
                limit_type = "login"
            elif request.url.path.endswith("/password-reset"):
                limit_type = "password_reset"
            
            # Получаем ключ ограничения
            key = self.get_rate_limit_key(request, limit_type)
            
            # Проверяем лимит
            if self.is_rate_limited(key, limit_type):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Превышен лимит запросов. Попробуйте позже."
                )
            
            # Продолжаем обработку запроса
            response = await call_next(request)
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rate limit middleware error: {e}")
            # В случае ошибки пропускаем проверку
            response = await call_next(request)
            return response


# Создаем экземпляры middleware
authentication_middleware = AuthenticationMiddleware()
authorization_middleware = AuthorizationMiddleware()
rate_limit_middleware = RateLimitMiddleware()
