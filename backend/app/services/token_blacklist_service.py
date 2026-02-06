"""
Сервис для управления черным списком токенов (Token Blacklist)

Обеспечивает немедленный отзыв access токенов при:
- Logout
- Смене пароля  
- Подозрительной активности
- Блокировке пользователя
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

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
        user_id: Optional[int] = None,
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
            if expires_at < datetime.utcnow():
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
    def is_token_blacklisted(db: Session, jti: str) -> bool:
        """
        Проверить, находится ли токен в черном списке
        
        Args:
            db: Сессия базы данных
            jti: JWT ID токена
            
        Returns:
            True если токен в черном списке
        """
        try:
            entry = db.query(TokenBlacklist).filter(
                TokenBlacklist.jti == jti
            ).first()
            return entry is not None
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
            # Добавляем запись с user_id и expires_at в будущем
            # При проверке токена будем искать по user_id
            future_expiry = datetime.utcnow() + timedelta(days=30)  # На 30 дней вперёд
            
            blacklist_entry = TokenBlacklist(
                jti=f"all_user_{user_id}_{datetime.utcnow().timestamp()}",
                user_id=user_id,
                expires_at=future_expiry,
                reason=f"all_user_tokens:{reason}"
            )
            db.add(blacklist_entry)
            db.commit()
            
            logger.warning(f"All tokens for user {user_id} blacklisted (reason: {reason})")
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
                TokenBlacklist.expires_at < datetime.utcnow()
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
