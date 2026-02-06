"""
Сервис безопасности для подтверждений визитов
Включает rate limiting, валидацию токенов, аудит и защиту от злоупотреблений
"""

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.patient import Patient
from app.models.visit import Visit

logger = logging.getLogger(__name__)


@dataclass
class SecurityCheckResult:
    """Результат проверки безопасности"""

    allowed: bool
    reason: str
    retry_after: Optional[int] = None
    remaining_attempts: Optional[int] = None


@dataclass
class RateLimitConfig:
    """Конфигурация rate limiting"""

    max_attempts: int
    window_minutes: int
    cooldown_minutes: int


class ConfirmationSecurityService:
    """Сервис безопасности подтверждений визитов"""

    # Конфигурация rate limiting по типам действий
    RATE_LIMITS = {
        'confirmation_attempt': RateLimitConfig(
            max_attempts=5, window_minutes=15, cooldown_minutes=30
        ),
        'token_generation': RateLimitConfig(
            max_attempts=3, window_minutes=60, cooldown_minutes=60
        ),
        'failed_confirmation': RateLimitConfig(
            max_attempts=10, window_minutes=60, cooldown_minutes=120
        ),
    }

    def __init__(self, db: Session):
        self.db = db

    def validate_confirmation_request(
        self,
        token: str,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        channel: str = "unknown",
    ) -> SecurityCheckResult:
        """
        Валидирует запрос на подтверждение визита

        Args:
            token: Токен подтверждения
            source_ip: IP адрес источника запроса
            user_agent: User-Agent браузера/приложения
            channel: Канал подтверждения (telegram, pwa, phone)

        Returns:
            SecurityCheckResult с результатом проверки
        """
        try:
            # 1. Проверяем существование и валидность токена
            visit = self._get_visit_by_token(token)
            if not visit:
                print(f"DEBUG: Visit not found for token {token}")
                self._log_security_event(
                    "invalid_token",
                    {
                        "token": self._hash_token(token),
                        "source_ip": source_ip,
                        "user_agent": user_agent,
                        "channel": channel,
                    },
                )
                return SecurityCheckResult(
                    allowed=False, reason="Недействительный токен подтверждения"
                )
            
            print(f"DEBUG: Visit found: ID={visit.id}, Status={visit.status}, Expires={visit.confirmation_expires_at}, Now={datetime.utcnow()}")

            # 2. Проверяем срок действия токена
            if (
                visit.confirmation_expires_at
                and visit.confirmation_expires_at < datetime.utcnow()
            ):
                print("DEBUG: Token expired")
                self._log_security_event(
                    "expired_token",
                    {
                        "visit_id": visit.id,
                        "token": self._hash_token(token),
                        "expired_at": visit.confirmation_expires_at.isoformat(),
                        "source_ip": source_ip,
                        "channel": channel,
                    },
                )
                return SecurityCheckResult(
                    allowed=False, reason="Срок действия токена истек"
                )

            # 3. Проверяем статус визита
            if visit.status not in ["pending_confirmation"]:
                print(f"DEBUG: Invalid status {visit.status}")
                return SecurityCheckResult(
                    allowed=False, reason=f"Визит уже имеет статус: {visit.status}"
                )

            # 4. Проверяем rate limiting по IP
            if source_ip:
                ip_check = self._check_rate_limit_by_ip(
                    source_ip, "confirmation_attempt"
                )
                if not ip_check.allowed:
                    self._log_security_event(
                        "rate_limit_ip",
                        {
                            "source_ip": source_ip,
                            "visit_id": visit.id,
                            "channel": channel,
                            "retry_after": ip_check.retry_after,
                        },
                    )
                    return ip_check

            # 5. Проверяем rate limiting по пациенту
            patient_check = self._check_rate_limit_by_patient(
                visit.patient_id, "confirmation_attempt"
            )
            if not patient_check.allowed:
                self._log_security_event(
                    "rate_limit_patient",
                    {
                        "patient_id": visit.patient_id,
                        "visit_id": visit.id,
                        "channel": channel,
                        "retry_after": patient_check.retry_after,
                    },
                )
                return patient_check

            # 6. Проверяем подозрительную активность
            suspicious_check = self._check_suspicious_activity(
                visit, source_ip, user_agent, channel
            )
            if not suspicious_check.allowed:
                return suspicious_check

            # Все проверки пройдены
            self._log_security_event(
                "validation_passed",
                {
                    "visit_id": visit.id,
                    "patient_id": visit.patient_id,
                    "source_ip": source_ip,
                    "channel": channel,
                },
            )

            return SecurityCheckResult(
                allowed=True, reason="Запрос прошел все проверки безопасности"
            )

        except Exception as e:
            logger.error(f"Ошибка валидации запроса подтверждения: {e}")
            return SecurityCheckResult(
                allowed=False, reason="Внутренняя ошибка системы безопасности"
            )

    def validate_token_generation_request(
        self,
        patient_id: int,
        source_ip: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> SecurityCheckResult:
        """
        Валидирует запрос на генерацию нового токена подтверждения
        """
        try:
            # 1. Проверяем rate limiting по пациенту
            patient_check = self._check_rate_limit_by_patient(
                patient_id, "token_generation"
            )
            if not patient_check.allowed:
                self._log_security_event(
                    "rate_limit_token_generation",
                    {
                        "patient_id": patient_id,
                        "source_ip": source_ip,
                        "user_id": user_id,
                        "retry_after": patient_check.retry_after,
                    },
                )
                return patient_check

            # 2. Проверяем rate limiting по IP
            if source_ip:
                ip_check = self._check_rate_limit_by_ip(source_ip, "token_generation")
                if not ip_check.allowed:
                    self._log_security_event(
                        "rate_limit_token_generation_ip",
                        {
                            "patient_id": patient_id,
                            "source_ip": source_ip,
                            "user_id": user_id,
                            "retry_after": ip_check.retry_after,
                        },
                    )
                    return ip_check

            return SecurityCheckResult(
                allowed=True, reason="Генерация токена разрешена"
            )

        except Exception as e:
            logger.error(f"Ошибка валидации генерации токена: {e}")
            return SecurityCheckResult(
                allowed=False, reason="Внутренняя ошибка системы безопасности"
            )

    def generate_secure_token(self, visit_id: int) -> str:
        """
        Генерирует криптографически стойкий токен подтверждения
        """
        # Используем secrets для криптографически стойкой генерации
        random_part = secrets.token_urlsafe(32)

        # Добавляем контекстную информацию для дополнительной безопасности
        context = f"{visit_id}:{datetime.utcnow().timestamp()}"
        context_hash = hashlib.sha256(context.encode()).hexdigest()[:16]

        # Комбинируем части
        token = f"{random_part}-{context_hash}"

        self._log_security_event(
            "token_generated",
            {"visit_id": visit_id, "token_hash": self._hash_token(token)},
        )

        return token

    def record_confirmation_attempt(
        self,
        visit_id: int,
        success: bool,
        source_ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        channel: str = "unknown",
        error_reason: Optional[str] = None,
    ):
        """
        Записывает попытку подтверждения для аудита и rate limiting
        """
        try:
            event_type = "confirmation_success" if success else "confirmation_failed"

            event_data = {
                "visit_id": visit_id,
                "source_ip": source_ip,
                "user_agent": user_agent,
                "channel": channel,
                "success": success,
            }

            if not success and error_reason:
                event_data["error_reason"] = error_reason

            self._log_security_event(event_type, event_data)

            # Обновляем счетчики rate limiting
            if source_ip:
                self._update_rate_limit_counter(
                    f"ip:{source_ip}", "confirmation_attempt"
                )

            visit = self.db.query(Visit).filter(Visit.id == visit_id).first()
            if visit:
                self._update_rate_limit_counter(
                    f"patient:{visit.patient_id}", "confirmation_attempt"
                )

                if not success:
                    self._update_rate_limit_counter(
                        f"patient:{visit.patient_id}", "failed_confirmation"
                    )
                    if source_ip:
                        self._update_rate_limit_counter(
                            f"ip:{source_ip}", "failed_confirmation"
                        )

        except Exception as e:
            logger.error(f"Ошибка записи попытки подтверждения: {e}")

    def cleanup_expired_tokens(self) -> int:
        """
        Очищает истекшие токены подтверждения
        Возвращает количество очищенных записей
        """
        try:
            # Находим визиты с истекшими токенами
            expired_visits = (
                self.db.query(Visit)
                .filter(
                    and_(
                        Visit.status == "pending_confirmation",
                        Visit.confirmation_expires_at < datetime.utcnow(),
                    )
                )
                .all()
            )

            count = 0
            for visit in expired_visits:
                # Обновляем статус на "expired"
                visit.status = "expired"
                visit.confirmation_token = None
                visit.confirmation_expires_at = None
                count += 1

                self._log_security_event(
                    "token_expired_cleanup",
                    {
                        "visit_id": visit.id,
                        "patient_id": visit.patient_id,
                        "original_expires_at": (
                            visit.confirmation_expires_at.isoformat()
                            if visit.confirmation_expires_at
                            else None
                        ),
                    },
                )

            if count > 0:
                self.db.commit()
                logger.info(f"Очищено {count} истекших токенов подтверждения")

            return count

        except Exception as e:
            logger.error(f"Ошибка очистки истекших токенов: {e}")
            self.db.rollback()
            return 0

    def get_security_stats(self, hours: int = 24) -> Dict[str, Any]:
        """
        Получает статистику безопасности за указанный период
        """
        try:
            since = datetime.utcnow() - timedelta(hours=hours)

            # Здесь должна быть логика получения статистики из таблицы аудита
            # Пока возвращаем заглушку
            stats = {
                "period_hours": hours,
                "since": since.isoformat(),
                "confirmation_attempts": 0,
                "successful_confirmations": 0,
                "failed_confirmations": 0,
                "rate_limit_blocks": 0,
                "suspicious_activity_blocks": 0,
                "expired_tokens_cleaned": 0,
            }

            return stats

        except Exception as e:
            logger.error(f"Ошибка получения статистики безопасности: {e}")
            return {"error": str(e)}

    # Приватные методы

    def _get_visit_by_token(self, token: str) -> Optional[Visit]:
        """Получает визит по токену подтверждения"""
        return self.db.query(Visit).filter(Visit.confirmation_token == token).first()

    def _hash_token(self, token: str) -> str:
        """Хеширует токен для логирования (безопасность)"""
        return hashlib.sha256(token.encode()).hexdigest()[:16]

    def _check_rate_limit_by_ip(self, ip: str, action: str) -> SecurityCheckResult:
        """Проверяет rate limiting по IP адресу"""
        # Здесь должна быть реальная логика проверки rate limiting
        # Пока возвращаем разрешение
        return SecurityCheckResult(allowed=True, reason="Rate limit OK")

    def _check_rate_limit_by_patient(
        self, patient_id: int, action: str
    ) -> SecurityCheckResult:
        """Проверяет rate limiting по пациенту"""
        # Здесь должна быть реальная логика проверки rate limiting
        # Пока возвращаем разрешение
        return SecurityCheckResult(allowed=True, reason="Rate limit OK")

    def _check_suspicious_activity(
        self,
        visit: Visit,
        source_ip: Optional[str],
        user_agent: Optional[str],
        channel: str,
    ) -> SecurityCheckResult:
        """Проверяет подозрительную активность"""
        try:
            # 1. Проверяем множественные попытки с разных IP
            if source_ip:
                # Логика проверки множественных IP для одного визита
                pass

            # 2. Проверяем подозрительные User-Agent
            if user_agent:
                suspicious_agents = ["bot", "crawler", "spider", "scraper"]
                if any(agent in user_agent.lower() for agent in suspicious_agents):
                    self._log_security_event(
                        "suspicious_user_agent",
                        {
                            "visit_id": visit.id,
                            "user_agent": user_agent,
                            "source_ip": source_ip,
                        },
                    )
                    return SecurityCheckResult(
                        allowed=False, reason="Подозрительный User-Agent"
                    )

            # 3. Проверяем временные аномалии
            if visit.created_at:
                time_since_creation = datetime.utcnow() - visit.created_at
                if (
                    time_since_creation.total_seconds() < 60
                ):  # Слишком быстро после создания
                    self._log_security_event(
                        "too_fast_confirmation",
                        {
                            "visit_id": visit.id,
                            "time_since_creation": time_since_creation.total_seconds(),
                            "source_ip": source_ip,
                        },
                    )
                    return SecurityCheckResult(
                        allowed=False, reason="Слишком быстрая попытка подтверждения"
                    )

            return SecurityCheckResult(
                allowed=True, reason="Подозрительная активность не обнаружена"
            )

        except Exception as e:
            logger.error(f"Ошибка проверки подозрительной активности: {e}")
            return SecurityCheckResult(
                allowed=True, reason="Ошибка проверки, разрешаем"
            )

    def _update_rate_limit_counter(self, key: str, action: str):
        """Обновляет счетчик rate limiting"""
        # Здесь должна быть логика обновления счетчиков в Redis или базе данных
        # Пока просто логируем
        logger.debug(f"Rate limit counter updated: {key}:{action}")

    def _log_security_event(self, event_type: str, data: Dict[str, Any]):
        """Логирует событие безопасности"""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "data": data,
        }

        # В продакшене здесь должна быть запись в специальную таблицу аудита
        logger.info(f"Security event: {event_type}", extra={"security_event": event})
