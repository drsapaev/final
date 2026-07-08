"""
Сервис для управления черным списком токенов (Token Blacklist)

Обеспечивает немедленный отзыв access токенов при:
- Logout
- Смене пароля
- Подозрительной активности
- Блокировке пользователя
"""
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.authentication import TokenBlacklist

logger = logging.getLogger(__name__)


class TokenBlacklistService:
    """Сервис для работы с черным списком токенов"""

    @staticmethod
    def blacklist_token(
        db: Session,
        jti: str,
        expires_at: datetime,
        user_id: int | None = None,
        reason: str = "logout"
    ) -> bool:
        """
        Добавить токен в черный список

        Args:
            db: Сессия базы данных
            jti: JWT ID токена
            expires_at: Время истечения токена
            user_id: ID пользователя (опционально)
            reason: Причина блокировки

        Returns:
            True если успешно, False если ошибка
        """
        try:
            # Проверяем, не истёк ли уже токен
            if expires_at < datetime.now(UTC):
                logger.debug(f"Token {jti} already expired, skipping blacklist")
                return True

            # Проверяем, не заблокирован ли уже
            existing = db.query(TokenBlacklist).filter(
                TokenBlacklist.jti == jti
            ).first()

            if existing:
                logger.debug(f"Token {jti} already blacklisted")
                return True

            blacklist_entry = TokenBlacklist(
                jti=jti,
                user_id=user_id,
                expires_at=expires_at,
                reason=reason
            )
            db.add(blacklist_entry)
            db.commit()

            logger.info(f"Token {jti} blacklisted (reason: {reason})")
            return True

        except Exception as e:
            logger.error(f"Error blacklisting token {jti}: {e}")
            db.rollback()
            return False

    @staticmethod
    def is_token_blacklisted(db: Session, jti: str, user_id: int | None = None) -> bool:
        """
        Проверить, находится ли токен в черном списке.

        Проверка двух типов записей:
        1. Точный jti — для индивидуально отозванных токенов (logout).
        2. "all_user_tokens" sentinel — когда был вызван
           ``blacklist_all_user_tokens(user_id)``. Все access-токены
           пользователя считаются отозванными до истечения sentinel-записи.

        Args:
            db: Сессия базы данных
            jti: JWT ID токена
            user_id: ID пользователя (опционально; передаётся deps.get_current_user)

        Returns:
            True если токен в черном списке
        """
        try:
            # 1) Точный jti
            entry = db.query(TokenBlacklist).filter(
                TokenBlacklist.jti == jti
            ).first()
            if entry is not None:
                return True

            # 2) Sentinel "отозвать все токены пользователя"
            if user_id is not None:
                from datetime import datetime as _dt
                sentinel = (
                    db.query(TokenBlacklist)
                    .filter(
                        TokenBlacklist.user_id == user_id,
                        TokenBlacklist.reason.like("all_user_tokens:%"),
                        TokenBlacklist.expires_at > _dt.utcnow(),
                    )
                    .first()
                )
                if sentinel is not None:
                    return True

            return False
        except Exception as e:
            logger.error(f"Error checking blacklist for {jti}: {e}")
            return False

    @staticmethod
    def blacklist_all_user_tokens(
        db: Session,
        user_id: int,
        reason: str = "security"
    ) -> int:
        """
        Отозвать все токены пользователя

        Используется при:
        - Смене пароля
        - Блокировке пользователя
        - Подозрительной активности

        Args:
            db: Сессия базы данных
            user_id: ID пользователя
            reason: Причина отзыва

        Returns:
            Количество отозванных токенов
        """
        # Для немедленного отзыва всех токенов пользователя
        # используем запись с user_id и временем до которого все токены недействительны
        # Это более эффективно чем искать все существующие токены

        try:
            # Sentinel-запись: одна на пользователя с уникальным стабильным jti.
            # is_token_blacklisted ищет по (user_id, reason LIKE 'all_user_tokens:%',
            # expires_at > now). jti должен быть уникален (NOT NULL UNIQUE в модели),
            # поэтому вставляем с timestamp-суффиксом; истёкшие sentinel-записи
            # удаляются в cleanup_expired_tokens.
            now = datetime.now(UTC)
            future_expiry = now + timedelta(days=30)  # Покрывает максимальный access-token TTL (30 min) с запасом

            # Удаляем предыдущие активные sentinel-записи этого пользователя
            # (idempotent — повторный вызов не накапливает дубликаты)
            db.query(TokenBlacklist).filter(
                TokenBlacklist.user_id == user_id,
                TokenBlacklist.reason.like("all_user_tokens:%"),
            ).delete(synchronize_session=False)

            blacklist_entry = TokenBlacklist(
                jti=f"all_user_{user_id}_{int(now.timestamp())}",
                user_id=user_id,
                expires_at=future_expiry,
                reason=f"all_user_tokens:{reason}",
            )
            db.add(blacklist_entry)
            db.commit()

            logger.warning(
                "All tokens for user %s blacklisted until %s (reason: %s)",
                user_id, future_expiry.isoformat(), reason,
            )
            return 1

        except Exception as e:
            logger.error(f"Error blacklisting all tokens for user {user_id}: {e}")
            db.rollback()
            return 0

    @staticmethod
    def cleanup_expired_tokens(db: Session) -> int:
        """
        Удалить истёкшие записи из черного списка

        Рекомендуется вызывать периодически (например, раз в сутки)

        Returns:
            Количество удалённых записей
        """
        try:
            deleted = db.query(TokenBlacklist).filter(
                TokenBlacklist.expires_at < datetime.now(UTC)
            ).delete()
            db.commit()

            if deleted > 0:
                logger.info(f"Cleaned up {deleted} expired blacklist entries")

            return deleted

        except Exception as e:
            logger.error(f"Error cleaning up blacklist: {e}")
            db.rollback()
            return 0


# Singleton instance
token_blacklist_service = TokenBlacklistService()
