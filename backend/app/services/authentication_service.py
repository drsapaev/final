"""
Сервис для аутентификации с JWT токенами
"""
import secrets
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
import jwt
from passlib.context import CryptContext

from app.models.user import User
from app.models.authentication import (
    RefreshToken, UserSession, PasswordResetToken, 
    EmailVerificationToken, LoginAttempt, UserActivity, SecurityEvent
)
from app.core.config import settings
from app.core.security import verify_password, get_password_hash
import logging

logger = logging.getLogger(__name__)

# Контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthenticationService:
    """Сервис для работы с аутентификацией"""

    def __init__(self):
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 30
        self.password_reset_expire_hours = 1
        self.email_verification_expire_hours = 24
        self.session_expire_hours = 24
        self.max_login_attempts = 5
        self.lockout_duration_minutes = 15

    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Создает JWT access токен"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=self.algorithm)
        return encoded_jwt

    def create_refresh_token(self, user_id: int, jti: str) -> str:
        """Создает JWT refresh токен"""
        data = {
            "user_id": user_id,
            "jti": jti,
            "type": "refresh"
        }
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        data.update({"exp": expire})
        
        encoded_jwt = jwt.encode(data, settings.SECRET_KEY, algorithm=self.algorithm)
        return encoded_jwt

    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """Проверяет JWT токен"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[self.algorithm])
            if payload.get("type") != token_type:
                return None
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid token")
            return None

    def authenticate_user(self, db: Session, username: str, password: str, ip_address: str = None, user_agent: str = None) -> Tuple[Optional[User], str]:
        """Аутентифицирует пользователя"""
        try:
            # Ищем пользователя по username или email
            user = db.query(User).filter(
                or_(User.username == username, User.email == username)
            ).first()

            if not user:
                self._log_login_attempt(db, None, username, ip_address, user_agent, False, "user_not_found")
                return None, "Пользователь не найден"

            if not user.is_active:
                self._log_login_attempt(db, user.id, username, ip_address, user_agent, False, "user_inactive")
                return None, "Пользователь деактивирован"

            if not verify_password(password, user.hashed_password):
                self._log_login_attempt(db, user.id, username, ip_address, user_agent, False, "invalid_password")
                return None, "Неверный пароль"

            # Проверяем блокировку
            if self._is_user_locked(db, user.id):
                self._log_login_attempt(db, user.id, username, ip_address, user_agent, False, "user_locked")
                return None, "Пользователь заблокирован из-за множественных неудачных попыток входа"

            # Успешный вход
            self._log_login_attempt(db, user.id, username, ip_address, user_agent, True, None)
            self._log_user_activity(db, user.id, "login", "Успешный вход в систему", ip_address, user_agent)
            
            return user, "Успешная аутентификация"

        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            return None, "Ошибка аутентификации"

    def login_user(self, db: Session, username: str, password: str, ip_address: str = None, user_agent: str = None, device_fingerprint: str = None, remember_me: bool = False) -> Dict[str, Any]:
        """Выполняет вход пользователя"""
        user, message = self.authenticate_user(db, username, password, ip_address, user_agent)
        
        if not user:
            return {
                "success": False,
                "message": message,
                "user": None,
                "tokens": None
            }

        # Создаем JTI для refresh токена
        jti = str(uuid.uuid4())
        
        # Создаем токены
        access_token = self.create_access_token({
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser
        })
        
        refresh_token = self.create_refresh_token(user.id, jti)
        
        # Сохраняем refresh токен в БД
        refresh_token_obj = RefreshToken(
            user_id=user.id,
            token=refresh_token,
            jti=jti,
            expires_at=datetime.utcnow() + timedelta(days=self.refresh_token_expire_days),
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint
        )
        db.add(refresh_token_obj)
        
        # Создаем сессию
        session_id = str(uuid.uuid4())
        session_token = secrets.token_urlsafe(32)
        session_expires = datetime.utcnow() + timedelta(hours=self.session_expire_hours)
        
        user_session = UserSession(
            user_id=user.id,
            session_id=session_id,
            session_token=session_token,
            expires_at=session_expires,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint
        )
        db.add(user_session)
        
        db.commit()
        
        # Проверяем, требуется ли 2FA
        requires_2fa = False
        two_factor_method = None
        if user.two_factor_auth and user.two_factor_auth.totp_enabled:
            requires_2fa = True
            two_factor_method = "totp"
        
        return {
            "success": True,
            "message": "Успешный вход",
            "user": {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser
            },
            "tokens": {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": self.access_token_expire_minutes * 60
            },
            "requires_2fa": requires_2fa,
            "two_factor_method": two_factor_method
        }

    def refresh_access_token(self, db: Session, refresh_token: str) -> Dict[str, Any]:
        """Обновляет access токен"""
        try:
            # Проверяем refresh токен
            payload = self.verify_token(refresh_token, "refresh")
            if not payload:
                return {"success": False, "message": "Недействительный refresh токен"}
            
            # Проверяем токен в БД
            token_obj = db.query(RefreshToken).filter(
                and_(
                    RefreshToken.token == refresh_token,
                    RefreshToken.revoked == False,
                    RefreshToken.expires_at > datetime.utcnow()
                )
            ).first()
            
            if not token_obj:
                return {"success": False, "message": "Refresh токен не найден или истек"}
            
            # Получаем пользователя
            user = db.query(User).filter(User.id == token_obj.user_id).first()
            if not user or not user.is_active:
                return {"success": False, "message": "Пользователь не найден или неактивен"}
            
            # Создаем новый access токен
            access_token = self.create_access_token({
                "sub": str(user.id),
                "username": user.username,
                "role": user.role,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser
            })
            
            return {
                "success": True,
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": self.access_token_expire_minutes * 60
            }
            
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return {"success": False, "message": "Ошибка обновления токена"}

    def logout_user(self, db: Session, refresh_token: str = None, user_id: int = None, logout_all: bool = False) -> Dict[str, Any]:
        """Выполняет выход пользователя"""
        try:
            if logout_all and user_id:
                # Отзываем все refresh токены пользователя
                db.query(RefreshToken).filter(RefreshToken.user_id == user_id).update({
                    "revoked": True,
                    "revoked_at": datetime.utcnow()
                })
                
                # Деактивируем все сессии
                db.query(UserSession).filter(UserSession.user_id == user_id).update({
                    "is_active": False
                })
                
                self._log_user_activity(db, user_id, "logout_all", "Выход со всех устройств")
                
            elif refresh_token:
                # Отзываем конкретный refresh токен
                token_obj = db.query(RefreshToken).filter(RefreshToken.token == refresh_token).first()
                if token_obj:
                    token_obj.revoked = True
                    token_obj.revoked_at = datetime.utcnow()
                    
                    # Деактивируем связанную сессию
                    db.query(UserSession).filter(
                        UserSession.user_id == token_obj.user_id,
                        UserSession.device_fingerprint == token_obj.device_fingerprint
                    ).update({"is_active": False})
                    
                    self._log_user_activity(db, token_obj.user_id, "logout", "Выход из системы")
            
            db.commit()
            return {"success": True, "message": "Успешный выход"}
            
        except Exception as e:
            logger.error(f"Error logging out user: {e}")
            return {"success": False, "message": "Ошибка выхода"}

    def create_password_reset_token(self, db: Session, email: str, ip_address: str = None, user_agent: str = None) -> Dict[str, Any]:
        """Создает токен для сброса пароля"""
        try:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                return {"success": False, "message": "Пользователь с таким email не найден"}
            
            # Отзываем старые токены
            db.query(PasswordResetToken).filter(
                and_(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.used == False
                )
            ).update({"used": True, "used_at": datetime.utcnow()})
            
            # Создаем новый токен
            token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(hours=self.password_reset_expire_hours)
            
            reset_token = PasswordResetToken(
                user_id=user.id,
                token=token,
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent
            )
            db.add(reset_token)
            db.commit()
            
            self._log_user_activity(db, user.id, "password_reset_requested", "Запрос сброса пароля", ip_address, user_agent)
            
            return {
                "success": True,
                "message": "Токен сброса пароля создан",
                "token": token,
                "expires_at": expires_at
            }
            
        except Exception as e:
            logger.error(f"Error creating password reset token: {e}")
            return {"success": False, "message": "Ошибка создания токена сброса пароля"}

    def reset_password(self, db: Session, token: str, new_password: str) -> Dict[str, Any]:
        """Сбрасывает пароль пользователя"""
        try:
            # Проверяем токен
            reset_token = db.query(PasswordResetToken).filter(
                and_(
                    PasswordResetToken.token == token,
                    PasswordResetToken.used == False,
                    PasswordResetToken.expires_at > datetime.utcnow()
                )
            ).first()
            
            if not reset_token:
                return {"success": False, "message": "Недействительный или истекший токен"}
            
            # Обновляем пароль
            user = db.query(User).filter(User.id == reset_token.user_id).first()
            if not user:
                return {"success": False, "message": "Пользователь не найден"}
            
            user.hashed_password = get_password_hash(new_password)
            reset_token.used = True
            reset_token.used_at = datetime.utcnow()
            
            db.commit()
            
            # Отзываем все refresh токены пользователя
            db.query(RefreshToken).filter(RefreshToken.user_id == user.id).update({
                "revoked": True,
                "revoked_at": datetime.utcnow()
            })
            
            self._log_user_activity(db, user.id, "password_reset", "Пароль сброшен")
            self._log_security_event(db, user.id, "password_reset", "medium", "Пароль пользователя был сброшен")
            
            return {"success": True, "message": "Пароль успешно сброшен"}
            
        except Exception as e:
            logger.error(f"Error resetting password: {e}")
            return {"success": False, "message": "Ошибка сброса пароля"}

    def change_password(self, db: Session, user_id: int, current_password: str, new_password: str) -> Dict[str, Any]:
        """Меняет пароль пользователя"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "message": "Пользователь не найден"}
            
            # Проверяем текущий пароль
            if not verify_password(current_password, user.hashed_password):
                return {"success": False, "message": "Неверный текущий пароль"}
            
            # Обновляем пароль
            user.hashed_password = get_password_hash(new_password)
            db.commit()
            
            # Отзываем все refresh токены пользователя
            db.query(RefreshToken).filter(RefreshToken.user_id == user.id).update({
                "revoked": True,
                "revoked_at": datetime.utcnow()
            })
            
            self._log_user_activity(db, user.id, "password_changed", "Пароль изменен")
            self._log_security_event(db, user.id, "password_changed", "medium", "Пароль пользователя был изменен")
            
            return {"success": True, "message": "Пароль успешно изменен"}
            
        except Exception as e:
            logger.error(f"Error changing password: {e}")
            return {"success": False, "message": "Ошибка смены пароля"}

    def create_email_verification_token(self, db: Session, user_id: int, ip_address: str = None, user_agent: str = None) -> Dict[str, Any]:
        """Создает токен для верификации email"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "message": "Пользователь не найден"}
            
            # Отзываем старые токены
            db.query(EmailVerificationToken).filter(
                and_(
                    EmailVerificationToken.user_id == user.id,
                    EmailVerificationToken.verified == False
                )
            ).update({"verified": True, "verified_at": datetime.utcnow()})
            
            # Создаем новый токен
            token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(hours=self.email_verification_expire_hours)
            
            verification_token = EmailVerificationToken(
                user_id=user.id,
                token=token,
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent
            )
            db.add(verification_token)
            db.commit()
            
            return {
                "success": True,
                "message": "Токен верификации email создан",
                "token": token,
                "expires_at": expires_at
            }
            
        except Exception as e:
            logger.error(f"Error creating email verification token: {e}")
            return {"success": False, "message": "Ошибка создания токена верификации email"}

    def verify_email(self, db: Session, token: str) -> Dict[str, Any]:
        """Верифицирует email пользователя"""
        try:
            # Проверяем токен
            verification_token = db.query(EmailVerificationToken).filter(
                and_(
                    EmailVerificationToken.token == token,
                    EmailVerificationToken.verified == False,
                    EmailVerificationToken.expires_at > datetime.utcnow()
                )
            ).first()
            
            if not verification_token:
                return {"success": False, "message": "Недействительный или истекший токен"}
            
            # Отмечаем email как верифицированный
            verification_token.verified = True
            verification_token.verified_at = datetime.utcnow()
            
            db.commit()
            
            self._log_user_activity(db, verification_token.user_id, "email_verified", "Email верифицирован")
            
            return {"success": True, "message": "Email успешно верифицирован"}
            
        except Exception as e:
            logger.error(f"Error verifying email: {e}")
            return {"success": False, "message": "Ошибка верификации email"}

    def get_user_profile(self, db: Session, user_id: int) -> Optional[Dict[str, Any]]:
        """Получает профиль пользователя"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return None
            
            # Получаем последний вход
            last_login = db.query(LoginAttempt).filter(
                and_(
                    LoginAttempt.user_id == user.id,
                    LoginAttempt.success == True
                )
            ).order_by(desc(LoginAttempt.attempted_at)).first()
            
            # Проверяем верификацию email
            email_verified = db.query(EmailVerificationToken).filter(
                and_(
                    EmailVerificationToken.user_id == user.id,
                    EmailVerificationToken.verified == True
                )
            ).first() is not None
            
            # Проверяем 2FA
            two_factor_enabled = user.two_factor_auth and user.two_factor_auth.totp_enabled
            
            return {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
                "email_verified": email_verified,
                "phone_verified": False,  # TODO: реализовать верификацию телефона
                "created_at": user.created_at if hasattr(user, 'created_at') else None,
                "last_login": last_login.attempted_at if last_login else None,
                "two_factor_enabled": two_factor_enabled
            }
            
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None

    def _log_login_attempt(self, db: Session, user_id: Optional[int], username: str, ip_address: str, user_agent: str, success: bool, failure_reason: Optional[str]):
        """Логирует попытку входа"""
        try:
            login_attempt = LoginAttempt(
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                success=success,
                failure_reason=failure_reason
            )
            db.add(login_attempt)
            db.commit()
        except Exception as e:
            logger.error(f"Error logging login attempt: {e}")

    def _log_user_activity(self, db: Session, user_id: int, activity_type: str, description: str, ip_address: str = None, user_agent: str = None, metadata: Dict[str, Any] = None):
        """Логирует активность пользователя"""
        try:
            activity = UserActivity(
                user_id=user_id,
                activity_type=activity_type,
                description=description,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata=str(metadata) if metadata else None
            )
            db.add(activity)
            db.commit()
        except Exception as e:
            logger.error(f"Error logging user activity: {e}")

    def _log_security_event(self, db: Session, user_id: Optional[int], event_type: str, severity: str, description: str, ip_address: str = None, user_agent: str = None, metadata: Dict[str, Any] = None):
        """Логирует событие безопасности"""
        try:
            security_event = SecurityEvent(
                user_id=user_id,
                event_type=event_type,
                severity=severity,
                description=description,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata=str(metadata) if metadata else None
            )
            db.add(security_event)
            db.commit()
        except Exception as e:
            logger.error(f"Error logging security event: {e}")

    def _is_user_locked(self, db: Session, user_id: int) -> bool:
        """Проверяет, заблокирован ли пользователь"""
        try:
            # Подсчитываем неудачные попытки за последние 15 минут
            lockout_time = datetime.utcnow() - timedelta(minutes=self.lockout_duration_minutes)
            failed_attempts = db.query(LoginAttempt).filter(
                and_(
                    LoginAttempt.user_id == user_id,
                    LoginAttempt.success == False,
                    LoginAttempt.attempted_at > lockout_time
                )
            ).count()
            
            return failed_attempts >= self.max_login_attempts
        except Exception as e:
            logger.error(f"Error checking user lock: {e}")
            return False


# Глобальный экземпляр сервиса
authentication_service = AuthenticationService()

def get_authentication_service() -> AuthenticationService:
    """Получить экземпляр сервиса аутентификации"""
    return authentication_service
