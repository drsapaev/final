"""
CRUD операции для системы аутентификации
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, func
from datetime import datetime, timedelta

from app.models.authentication import (
    RefreshToken, UserSession, PasswordResetToken, 
    EmailVerificationToken, LoginAttempt, UserActivity, SecurityEvent
)
from app.models.user import User
from app.crud.base import CRUDBase
from app.schemas.authentication import (
    UserCreateRequest, UserUpdateRequest, UserProfileResponse,
    UserSessionResponse, LoginAttemptResponse, UserActivityResponse,
    SecurityEventResponse
)


class CRUDRefreshToken(CRUDBase[RefreshToken, None, None]):
    """CRUD операции для refresh токенов"""

    def get_by_token(self, db: Session, token: str) -> Optional[RefreshToken]:
        """Получить refresh токен по токену"""
        return db.query(RefreshToken).filter(RefreshToken.token == token).first()

    def get_by_jti(self, db: Session, jti: str) -> Optional[RefreshToken]:
        """Получить refresh токен по JTI"""
        return db.query(RefreshToken).filter(RefreshToken.jti == jti).first()

    def get_valid_token(self, db: Session, token: str) -> Optional[RefreshToken]:
        """Получить действительный refresh токен"""
        return db.query(RefreshToken).filter(
            and_(
                RefreshToken.token == token,
                RefreshToken.revoked == False,
                RefreshToken.expires_at > datetime.utcnow()
            )
        ).first()

    def get_by_user_id(self, db: Session, user_id: int) -> List[RefreshToken]:
        """Получить все refresh токены пользователя"""
        return db.query(RefreshToken).filter(RefreshToken.user_id == user_id).all()

    def get_active_tokens(self, db: Session, user_id: int) -> List[RefreshToken]:
        """Получить активные refresh токены пользователя"""
        return db.query(RefreshToken).filter(
            and_(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False,
                RefreshToken.expires_at > datetime.utcnow()
            )
        ).all()

    def revoke_token(self, db: Session, token: str) -> bool:
        """Отозвать refresh токен"""
        token_obj = self.get_by_token(db, token)
        if token_obj:
            token_obj.revoked = True
            token_obj.revoked_at = datetime.utcnow()
            db.commit()
            return True
        return False

    def revoke_all_user_tokens(self, db: Session, user_id: int) -> int:
        """Отозвать все refresh токены пользователя"""
        count = db.query(RefreshToken).filter(
            and_(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False
            )
        ).update({
            "revoked": True,
            "revoked_at": datetime.utcnow()
        })
        db.commit()
        return count

    def cleanup_expired_tokens(self, db: Session) -> int:
        """Очистить истекшие токены"""
        count = db.query(RefreshToken).filter(
            RefreshToken.expires_at < datetime.utcnow()
        ).delete()
        db.commit()
        return count


class CRUDUserSession(CRUDBase[UserSession, None, None]):
    """CRUD операции для пользовательских сессий"""

    def get_by_session_id(self, db: Session, session_id: str) -> Optional[UserSession]:
        """Получить сессию по ID"""
        return db.query(UserSession).filter(UserSession.session_id == session_id).first()

    def get_by_session_token(self, db: Session, session_token: str) -> Optional[UserSession]:
        """Получить сессию по токену"""
        return db.query(UserSession).filter(UserSession.session_token == session_token).first()

    def get_valid_session(self, db: Session, session_token: str) -> Optional[UserSession]:
        """Получить действительную сессию"""
        return db.query(UserSession).filter(
            and_(
                UserSession.session_token == session_token,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.utcnow()
            )
        ).first()

    def get_by_user_id(self, db: Session, user_id: int) -> List[UserSession]:
        """Получить все сессии пользователя"""
        return db.query(UserSession).filter(UserSession.user_id == user_id).all()

    def get_active_sessions(self, db: Session, user_id: int) -> List[UserSession]:
        """Получить активные сессии пользователя"""
        return db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.utcnow()
            )
        ).all()

    def update_activity(self, db: Session, session_id: str) -> bool:
        """Обновить активность сессии"""
        session = self.get_by_session_id(db, session_id)
        if session:
            session.last_activity = datetime.utcnow()
            db.commit()
            return True
        return False

    def deactivate_session(self, db: Session, session_id: str) -> bool:
        """Деактивировать сессию"""
        session = self.get_by_session_id(db, session_id)
        if session:
            session.is_active = False
            db.commit()
            return True
        return False

    def deactivate_all_user_sessions(self, db: Session, user_id: int) -> int:
        """Деактивировать все сессии пользователя"""
        count = db.query(UserSession).filter(
            and_(
                UserSession.user_id == user_id,
                UserSession.is_active == True
            )
        ).update({"is_active": False})
        db.commit()
        return count

    def cleanup_expired_sessions(self, db: Session) -> int:
        """Очистить истекшие сессии"""
        count = db.query(UserSession).filter(
            UserSession.expires_at < datetime.utcnow()
        ).delete()
        db.commit()
        return count


class CRUDPasswordResetToken(CRUDBase[PasswordResetToken, None, None]):
    """CRUD операции для токенов сброса пароля"""

    def get_by_token(self, db: Session, token: str) -> Optional[PasswordResetToken]:
        """Получить токен по токену"""
        return db.query(PasswordResetToken).filter(PasswordResetToken.token == token).first()

    def get_valid_token(self, db: Session, token: str) -> Optional[PasswordResetToken]:
        """Получить действительный токен"""
        return db.query(PasswordResetToken).filter(
            and_(
                PasswordResetToken.token == token,
                PasswordResetToken.used == False,
                PasswordResetToken.expires_at > datetime.utcnow()
            )
        ).first()

    def get_by_user_id(self, db: Session, user_id: int) -> List[PasswordResetToken]:
        """Получить все токены пользователя"""
        return db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user_id).all()

    def mark_as_used(self, db: Session, token: str) -> bool:
        """Отметить токен как использованный"""
        token_obj = self.get_by_token(db, token)
        if token_obj:
            token_obj.used = True
            token_obj.used_at = datetime.utcnow()
            db.commit()
            return True
        return False

    def cleanup_expired_tokens(self, db: Session) -> int:
        """Очистить истекшие токены"""
        count = db.query(PasswordResetToken).filter(
            PasswordResetToken.expires_at < datetime.utcnow()
        ).delete()
        db.commit()
        return count


class CRUDEmailVerificationToken(CRUDBase[EmailVerificationToken, None, None]):
    """CRUD операции для токенов верификации email"""

    def get_by_token(self, db: Session, token: str) -> Optional[EmailVerificationToken]:
        """Получить токен по токену"""
        return db.query(EmailVerificationToken).filter(EmailVerificationToken.token == token).first()

    def get_valid_token(self, db: Session, token: str) -> Optional[EmailVerificationToken]:
        """Получить действительный токен"""
        return db.query(EmailVerificationToken).filter(
            and_(
                EmailVerificationToken.token == token,
                EmailVerificationToken.verified == False,
                EmailVerificationToken.expires_at > datetime.utcnow()
            )
        ).first()

    def get_by_user_id(self, db: Session, user_id: int) -> List[EmailVerificationToken]:
        """Получить все токены пользователя"""
        return db.query(EmailVerificationToken).filter(EmailVerificationToken.user_id == user_id).all()

    def mark_as_verified(self, db: Session, token: str) -> bool:
        """Отметить токен как верифицированный"""
        token_obj = self.get_by_token(db, token)
        if token_obj:
            token_obj.verified = True
            token_obj.verified_at = datetime.utcnow()
            db.commit()
            return True
        return False

    def cleanup_expired_tokens(self, db: Session) -> int:
        """Очистить истекшие токены"""
        count = db.query(EmailVerificationToken).filter(
            EmailVerificationToken.expires_at < datetime.utcnow()
        ).delete()
        db.commit()
        return count


class CRUDLoginAttempt(CRUDBase[LoginAttempt, None, None]):
    """CRUD операции для попыток входа"""

    def get_by_user_id(self, db: Session, user_id: int, limit: int = 100) -> List[LoginAttempt]:
        """Получить попытки входа пользователя"""
        return db.query(LoginAttempt).filter(
            LoginAttempt.user_id == user_id
        ).order_by(desc(LoginAttempt.attempted_at)).limit(limit).all()

    def get_by_ip(self, db: Session, ip_address: str, limit: int = 100) -> List[LoginAttempt]:
        """Получить попытки входа по IP"""
        return db.query(LoginAttempt).filter(
            LoginAttempt.ip_address == ip_address
        ).order_by(desc(LoginAttempt.attempted_at)).limit(limit).all()

    def get_failed_attempts(self, db: Session, user_id: int, since: datetime = None) -> int:
        """Получить количество неудачных попыток"""
        query = db.query(LoginAttempt).filter(
            and_(
                LoginAttempt.user_id == user_id,
                LoginAttempt.success == False
            )
        )
        
        if since:
            query = query.filter(LoginAttempt.attempted_at > since)
        
        return query.count()

    def get_recent_failed_attempts(self, db: Session, ip_address: str, minutes: int = 15) -> int:
        """Получить недавние неудачные попытки по IP"""
        since = datetime.utcnow() - timedelta(minutes=minutes)
        return db.query(LoginAttempt).filter(
            and_(
                LoginAttempt.ip_address == ip_address,
                LoginAttempt.success == False,
                LoginAttempt.attempted_at > since
            )
        ).count()

    def cleanup_old_attempts(self, db: Session, days: int = 30) -> int:
        """Очистить старые попытки входа"""
        since = datetime.utcnow() - timedelta(days=days)
        count = db.query(LoginAttempt).filter(
            LoginAttempt.attempted_at < since
        ).delete()
        db.commit()
        return count


class CRUDUserActivity(CRUDBase[UserActivity, None, None]):
    """CRUD операции для активности пользователей"""

    def get_by_user_id(self, db: Session, user_id: int, limit: int = 100) -> List[UserActivity]:
        """Получить активность пользователя"""
        return db.query(UserActivity).filter(
            UserActivity.user_id == user_id
        ).order_by(desc(UserActivity.created_at)).limit(limit).all()

    def get_by_activity_type(self, db: Session, activity_type: str, limit: int = 100) -> List[UserActivity]:
        """Получить активность по типу"""
        return db.query(UserActivity).filter(
            UserActivity.activity_type == activity_type
        ).order_by(desc(UserActivity.created_at)).limit(limit).all()

    def get_recent_activity(self, db: Session, user_id: int, hours: int = 24) -> List[UserActivity]:
        """Получить недавнюю активность"""
        since = datetime.utcnow() - timedelta(hours=hours)
        return db.query(UserActivity).filter(
            and_(
                UserActivity.user_id == user_id,
                UserActivity.created_at > since
            )
        ).order_by(desc(UserActivity.created_at)).all()

    def cleanup_old_activities(self, db: Session, days: int = 90) -> int:
        """Очистить старую активность"""
        since = datetime.utcnow() - timedelta(days=days)
        count = db.query(UserActivity).filter(
            UserActivity.created_at < since
        ).delete()
        db.commit()
        return count


class CRUDSecurityEvent(CRUDBase[SecurityEvent, None, None]):
    """CRUD операции для событий безопасности"""

    def get_by_user_id(self, db: Session, user_id: int, limit: int = 100) -> List[SecurityEvent]:
        """Получить события пользователя"""
        return db.query(SecurityEvent).filter(
            SecurityEvent.user_id == user_id
        ).order_by(desc(SecurityEvent.created_at)).limit(limit).all()

    def get_by_severity(self, db: Session, severity: str, limit: int = 100) -> List[SecurityEvent]:
        """Получить события по серьезности"""
        return db.query(SecurityEvent).filter(
            SecurityEvent.severity == severity
        ).order_by(desc(SecurityEvent.created_at)).limit(limit).all()

    def get_unresolved_events(self, db: Session, limit: int = 100) -> List[SecurityEvent]:
        """Получить неразрешенные события"""
        return db.query(SecurityEvent).filter(
            SecurityEvent.resolved == False
        ).order_by(desc(SecurityEvent.created_at)).limit(limit).all()

    def get_high_severity_events(self, db: Session, limit: int = 100) -> List[SecurityEvent]:
        """Получить события высокой серьезности"""
        return db.query(SecurityEvent).filter(
            SecurityEvent.severity.in_(["high", "critical"])
        ).order_by(desc(SecurityEvent.created_at)).limit(limit).all()

    def resolve_event(self, db: Session, event_id: int, resolved_by: int, notes: str = None) -> bool:
        """Разрешить событие"""
        event = db.query(SecurityEvent).filter(SecurityEvent.id == event_id).first()
        if event:
            event.resolved = True
            event.resolved_at = datetime.utcnow()
            event.resolved_by = resolved_by
            if notes:
                event.metadata = notes
            db.commit()
            return True
        return False

    def cleanup_old_events(self, db: Session, days: int = 365) -> int:
        """Очистить старые события"""
        since = datetime.utcnow() - timedelta(days=days)
        count = db.query(SecurityEvent).filter(
            and_(
                SecurityEvent.created_at < since,
                SecurityEvent.resolved == True
            )
        ).delete()
        db.commit()
        return count


class CRUDUser(CRUDBase[User, UserCreateRequest, UserUpdateRequest]):
    """CRUD операции для пользователей с аутентификацией"""

    def get_by_username(self, db: Session, username: str) -> Optional[User]:
        """Получить пользователя по username"""
        return db.query(User).filter(User.username == username).first()

    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        """Получить пользователя по email"""
        return db.query(User).filter(User.email == email).first()

    def get_by_username_or_email(self, db: Session, username_or_email: str) -> Optional[User]:
        """Получить пользователя по username или email"""
        return db.query(User).filter(
            or_(User.username == username_or_email, User.email == username_or_email)
        ).first()

    def get_active_users(self, db: Session, skip: int = 0, limit: int = 100) -> List[User]:
        """Получить активных пользователей"""
        return db.query(User).filter(
            User.is_active == True
        ).offset(skip).limit(limit).all()

    def get_by_role(self, db: Session, role: str, skip: int = 0, limit: int = 100) -> List[User]:
        """Получить пользователей по роли"""
        return db.query(User).filter(
            User.role == role
        ).offset(skip).limit(limit).all()

    def search_users(self, db: Session, query: str, skip: int = 0, limit: int = 100) -> List[User]:
        """Поиск пользователей"""
        return db.query(User).filter(
            or_(
                User.username.ilike(f"%{query}%"),
                User.full_name.ilike(f"%{query}%"),
                User.email.ilike(f"%{query}%")
            )
        ).offset(skip).limit(limit).all()

    def get_user_stats(self, db: Session) -> Dict[str, int]:
        """Получить статистику пользователей"""
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        superusers = db.query(User).filter(User.is_superuser == True).count()
        
        # Пользователи с 2FA
        users_with_2fa = db.query(User).join(User.two_factor_auth).filter(
            User.two_factor_auth.has(totp_enabled=True)
        ).count()
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "superusers": superusers,
            "users_with_2fa": users_with_2fa
        }

    def deactivate_user(self, db: Session, user_id: int) -> bool:
        """Деактивировать пользователя"""
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.is_active = False
            db.commit()
            return True
        return False

    def activate_user(self, db: Session, user_id: int) -> bool:
        """Активировать пользователя"""
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.is_active = True
            db.commit()
            return True
        return False


# Создаем экземпляры CRUD классов
refresh_token = CRUDRefreshToken(RefreshToken)
user_session = CRUDUserSession(UserSession)
password_reset_token = CRUDPasswordResetToken(PasswordResetToken)
email_verification_token = CRUDEmailVerificationToken(EmailVerificationToken)
login_attempt = CRUDLoginAttempt(LoginAttempt)
user_activity = CRUDUserActivity(UserActivity)
security_event = CRUDSecurityEvent(SecurityEvent)
user = CRUDUser(User)
