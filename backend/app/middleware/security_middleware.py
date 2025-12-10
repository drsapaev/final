"""
Security Middleware для rate limiting, brute force protection и IP logging
"""

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.audit import log_critical_change
from app.db.session import get_db

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Middleware для защиты от:
    - Rate limiting (ограничение частоты запросов)
    - Brute force attacks (защита от перебора паролей/OTP)
    - IP logging (логирование IP адресов для аудита)
    """

    def __init__(self, app):
        super().__init__(app)
        
        # Rate limiting конфигурация
        self.rate_limits: Dict[str, Dict[str, int]] = {
            "login": {"requests": 5, "window": 300},  # 5 попыток за 5 минут
            "2fa_verify": {"requests": 10, "window": 300},  # 10 попыток за 5 минут
            "password_reset": {"requests": 3, "window": 3600},  # 3 попытки за час
            "password_change": {"requests": 5, "window": 3600},  # 5 попыток за час
            "api": {"requests": 100, "window": 3600},  # 100 запросов за час
        }
        
        # Brute force protection конфигурация
        self.brute_force_config = {
            "max_failed_attempts": 5,  # Максимум неудачных попыток
            "lockout_duration": 900,  # 15 минут блокировки
            "tracking_window": 3600,  # Окно отслеживания: 1 час
        }
        
        # In-memory хранилище (в продакшене использовать Redis)
        self.request_counts: Dict[str, list] = defaultdict(list)  # IP -> [timestamps]
        self.failed_attempts: Dict[str, Dict[str, list]] = defaultdict(
            lambda: defaultdict(list)
        )  # IP -> endpoint -> [timestamps]
        self.locked_ips: Dict[str, datetime] = {}  # IP -> lock_until
        
        # Очистка старых записей каждые 5 минут
        self.last_cleanup = datetime.utcnow()
        self.cleanup_interval = timedelta(minutes=5)

    def _get_client_ip(self, request: Request) -> str:
        """Получить IP адрес клиента"""
        # Проверяем заголовки прокси
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Берем первый IP из списка
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # Fallback на client.host
        if request.client:
            return request.client.host
        
        return "unknown"

    def _get_endpoint_type(self, path: str) -> str:
        """Определить тип эндпоинта для применения соответствующих лимитов"""
        path_lower = path.lower()
        
        # Проверяем более специфичные пути первыми
        if "/authentication/login" in path_lower or path_lower.endswith("/login"):
            return "login"
        elif "/2fa/verify" in path_lower or (path_lower.endswith("/verify") and "/2fa" in path_lower):
            return "2fa_verify"
        elif "/authentication/password-reset" in path_lower or "/password-reset" in path_lower:
            return "password_reset"
        elif "/password-change" in path_lower or "/change-password" in path_lower:
            return "password_change"
        else:
            return "api"

    def _cleanup_old_records(self):
        """Очистить старые записи из памяти"""
        now = datetime.utcnow()
        if now - self.last_cleanup < self.cleanup_interval:
            return
        
        current_timestamp = now.timestamp()
        
        # Очистка request_counts
        for key in list(self.request_counts.keys()):
            window = 3600  # 1 час по умолчанию
            self.request_counts[key] = [
                ts
                for ts in self.request_counts[key]
                if current_timestamp - ts < window
            ]
            if not self.request_counts[key]:
                del self.request_counts[key]
        
        # Очистка failed_attempts
        for ip in list(self.failed_attempts.keys()):
            for endpoint in list(self.failed_attempts[ip].keys()):
                window = self.brute_force_config["tracking_window"]
                self.failed_attempts[ip][endpoint] = [
                    ts
                    for ts in self.failed_attempts[ip][endpoint]
                    if current_timestamp - ts < window
                ]
                if not self.failed_attempts[ip][endpoint]:
                    del self.failed_attempts[ip][endpoint]
            if not self.failed_attempts[ip]:
                del self.failed_attempts[ip]
        
        # Очистка истекших блокировок
        for ip in list(self.locked_ips.keys()):
            if now > self.locked_ips[ip]:
                del self.locked_ips[ip]
        
        self.last_cleanup = now

    def _check_rate_limit(
        self, ip_address: str, endpoint_type: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Проверить rate limit
        
        Returns:
            (is_limited, error_message)
        """
        if endpoint_type not in self.rate_limits:
            return False, None
        
        limit_config = self.rate_limits[endpoint_type]
        window = limit_config["window"]
        max_requests = limit_config["requests"]
        
        key = f"{endpoint_type}:{ip_address}"
        current_timestamp = time.time()
        
        # Очищаем старые записи для этого ключа
        if key in self.request_counts:
            self.request_counts[key] = [
                ts
                for ts in self.request_counts[key]
                if current_timestamp - ts < window
            ]
        else:
            self.request_counts[key] = []
        
        # Проверяем лимит
        if len(self.request_counts[key]) >= max_requests:
            return True, f"Превышен лимит запросов: {max_requests} за {window} секунд"
        
        # Добавляем текущий запрос
        self.request_counts[key].append(current_timestamp)
        return False, None

    def _check_brute_force(self, ip_address: str, endpoint: str) -> Tuple[bool, Optional[str]]:
        """
        Проверить brute force protection
        
        Returns:
            (is_blocked, error_message)
        """
        # Проверяем, не заблокирован ли IP
        if ip_address in self.locked_ips:
            lock_until = self.locked_ips[ip_address]
            if datetime.utcnow() < lock_until:
                remaining = (lock_until - datetime.utcnow()).total_seconds()
                return True, f"IP заблокирован из-за множественных неудачных попыток. Разблокировка через {int(remaining)} секунд"
            else:
                # Блокировка истекла
                del self.locked_ips[ip_address]
        
        # Проверяем количество неудачных попыток
        failed = self.failed_attempts[ip_address][endpoint]
        current_timestamp = time.time()
        window = self.brute_force_config["tracking_window"]
        
        # Очищаем старые записи
        failed[:] = [
            ts for ts in failed if current_timestamp - ts < window
        ]
        
        max_attempts = self.brute_force_config["max_failed_attempts"]
        if len(failed) >= max_attempts:
            # Блокируем IP
            lock_duration = self.brute_force_config["lockout_duration"]
            self.locked_ips[ip_address] = datetime.utcnow() + timedelta(
                seconds=lock_duration
            )
            logger.warning(
                f"IP {ip_address} заблокирован из-за {len(failed)} неудачных попыток на {endpoint}"
            )
            return True, f"IP заблокирован из-за множественных неудачных попыток. Попробуйте позже."
        
        return False, None

    def _record_failed_attempt(self, ip_address: str, endpoint: str):
        """Записать неудачную попытку"""
        current_timestamp = time.time()
        self.failed_attempts[ip_address][endpoint].append(current_timestamp)

    def _log_ip_access(
        self, request: Request, ip_address: str, endpoint_type: str, blocked: bool = False
    ):
        """Логировать доступ IP (для аудита)"""
        # Логируем только критичные эндпоинты
        if endpoint_type in ["login", "2fa_verify", "password_reset", "password_change"]:
            logger.info(
                f"IP {ip_address} -> {request.url.path} "
                f"(type: {endpoint_type}, blocked: {blocked})"
            )

    async def dispatch(self, request: Request, call_next):
        """Основной метод middleware"""
        # Пропускаем публичные эндпоинты
        public_paths = [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/",
        ]
        
        if any(request.url.path.startswith(path) for path in public_paths):
            return await call_next(request)
        
        # Получаем IP адрес
        ip_address = self._get_client_ip(request)
        
        # Определяем тип эндпоинта
        endpoint_type = self._get_endpoint_type(request.url.path)
        
        # Очистка старых записей
        self._cleanup_old_records()
        
        # Проверка brute force protection (только для auth endpoints)
        if endpoint_type in ["login", "2fa_verify", "password_reset", "password_change"]:
            is_blocked, error_msg = self._check_brute_force(ip_address, request.url.path)
            if is_blocked:
                self._log_ip_access(request, ip_address, endpoint_type, blocked=True)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=error_msg or "Превышен лимит неудачных попыток",
                )
        
        # Проверка rate limiting
        is_limited, error_msg = self._check_rate_limit(ip_address, endpoint_type)
        if is_limited:
            self._log_ip_access(request, ip_address, endpoint_type, blocked=True)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg or "Превышен лимит запросов",
            )
        
        # Выполняем запрос
        try:
            response = await call_next(request)
            
            # Если запрос неудачный (4xx/5xx) на auth endpoint, записываем как failed attempt
            if (
                endpoint_type in ["login", "2fa_verify", "password_reset", "password_change"]
                and response.status_code >= 400
            ):
                self._record_failed_attempt(ip_address, request.url.path)
                self._log_ip_access(request, ip_address, endpoint_type, blocked=True)
            
            # Добавляем заголовки с информацией о лимитах (только для успешных запросов)
            if endpoint_type in self.rate_limits and response.status_code < 400:
                limit_config = self.rate_limits[endpoint_type]
                response.headers["X-RateLimit-Limit"] = str(limit_config["requests"])
                response.headers["X-RateLimit-Window"] = str(limit_config["window"])
                
                # Подсчитываем оставшиеся запросы
                key = f"{endpoint_type}:{ip_address}"
                if key in self.request_counts:
                    remaining = limit_config["requests"] - len(self.request_counts[key])
                    response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
            
            return response
            
        except HTTPException:
            # Перебрасываем HTTPException
            raise
        except Exception as e:
            logger.error(f"Security middleware error: {e}", exc_info=True)
            # В случае ошибки пропускаем проверку
            return await call_next(request)

