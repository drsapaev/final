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
from jose import jwt

from app.models.user import User
from app.models.authentication import (
    RefreshToken, UserSession, PasswordResetToken, 
    EmailVerificationToken, LoginAttempt, UserActivity, SecurityEvent
)
from app.core.config import settings
from app.core.security import verify_password, get_password_hash
import logging

logger = logging.getLogger(__name__)

# Используем функции из app.core.security


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
            print(f"DEBUG: authenticate_user called with username={username}")
            
            # Ищем пользователя по username или email
            user = db.query(User).filter(
                or_(User.username == username, User.email == username)
            ).first()

            if not user:
                print(f"DEBUG: User not found for username={username}")
                self._log_login_attempt(db, None, username, ip_address, user_agent, False, "user_not_found")
                return None, "Пользователь не найден"

            print(f"DEBUG: User found: ID={user.id}, Username={user.username}, IsActive={user.is_active}")

            if not user.is_active:
                print(f"DEBUG: User is inactive")
                self._log_login_attempt(db, user.id, username, ip_address, user_agent, False, "user_inactive")
                return None, "Пользователь деактивирован"

            print(f"DEBUG: Verifying password...")
            password_valid = verify_password(password, user.hashed_password)
            print(f"DEBUG: Password verification result: {password_valid}")
            
            if not password_valid:
                print(f"DEBUG: Invalid password")
                self._log_login_attempt(db, user.id, username, ip_address, user_agent, False, "invalid_password")
                return None, "Неверный пароль"

            # Проверяем блокировку
            if self._is_user_locked(db, user.id):
                print(f"DEBUG: User is locked")
                self._log_login_attempt(db, user.id, username, ip_address, user_agent, False, "user_locked")
                return None, "Пользователь заблокирован из-за множественных неудачных попыток входа"

            # Успешный вход
            print(f"DEBUG: Authentication successful")
            self._log_login_attempt(db, user.id, username, ip_address, user_agent, True, None)
            self._log_user_activity(db, user.id, "login", "Успешный вход в систему", ip_address, user_agent)
            
            return user, "Успешная аутентификация"

        except Exception as e:
            print(f"DEBUG: Exception in authenticate_user: {e}")
            logger.error(f"Error authenticating user: {e}")
            return None, "Ошибка аутентификации"

    def login_user(self, db: Session, username: str, password: str, ip_address: str = None, user_agent: str = None, device_fingerprint: str = None, remember_me: bool = False) -> Dict[str, Any]:
        """Выполняет вход пользователя"""
        print(f"DEBUG: login_user called with username={username}")
        
        user, message = self.authenticate_user(db, username, password, ip_address, user_agent)
        
        print(f"DEBUG: authenticate_user returned user={user is not None}, message={message}")
        
        if not user:
            print(f"DEBUG: Authentication failed, returning error")
            return {
                "success": False,
                "message": message,
                "user": None,
                "tokens": None
            }

        # Проверяем, требуется ли 2FA до выдачи токенов
        requires_2fa = False
        two_factor_method = None
        # Временно отключено из-за проблем с БД
        # if user.two_factor_auth and user.two_factor_auth.totp_enabled:
        #     requires_2fa = True
        #     two_factor_method = "totp"
        
        # Если 2FA требуется — НЕ выдаём основные токены. Создаём временный pending_2fa_token
        if requires_2fa:
            pending_2fa_token = secrets.token_urlsafe(32)
            # Храним маркер в таблице сессий как незавершённую аутентификацию
            session_expires = datetime.utcnow() + timedelta(hours=self.session_expire_hours)
            user_session = UserSession(
                user_id=user.id,
                refresh_token=pending_2fa_token,
                expires_at=session_expires,
                ip=ip_address,
                user_agent=user_agent
            )
            db.add(user_session)
            db.commit()
            return {
                "success": True,
                "message": "Требуется подтверждение 2FA",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "full_name": user.full_name,
                    "email": user.email,
                    "role": user.role,
                    "is_active": user.is_active,
                    "is_superuser": user.is_superuser
                },
                "tokens": None,
                "requires_2fa": True,
                "two_factor_method": two_factor_method,
                "pending_2fa_token": pending_2fa_token
            }

        # Иначе — обычная выдача токенов
        jti = str(uuid.uuid4())
        access_token = self.create_access_token({
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser
        })
        refresh_token = self.create_refresh_token(user.id, jti)
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
        db.commit()
        
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
                        UserSession.user_id == token_obj.user_id
                    ).update({"revoked": True})
                    
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
            
            # Проверяем 2FA (строго булево значение)
            two_factor_enabled = bool(user.two_factor_auth and getattr(user.two_factor_auth, 'totp_enabled', False))
            
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
            # Временно отключено из-за проблем с БД
            print(f"DEBUG: Would log activity: {activity_type} for user {user_id}")
            pass
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

    # ===================== УПРАВЛЕНИЕ СЕССИЯМИ =====================

    def get_current_session(self, db: Session, user_id: int, ip_address: str = None, user_agent: str = None) -> Optional[UserSession]:
        """
        Получить текущую активную сессию пользователя
        """
        try:
            query = db.query(UserSession).filter(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.revoked == False,
                    UserSession.expires_at > datetime.utcnow()
                )
            )
            
            # Если указаны IP и User-Agent, ищем точное совпадение
            if ip_address and user_agent:
                session = query.filter(
                    and_(
                        UserSession.ip == ip_address,
                        UserSession.user_agent == user_agent
                    )
                ).first()
                
                if session:
                    return session
            
            # Если точного совпадения нет, ищем любую активную сессию
            session = query.order_by(desc(UserSession.created_at)).first()
            return session
            
        except Exception as e:
            logger.error(f"Ошибка получения текущей сессии для пользователя {user_id}: {e}")
            return None

    def get_user_sessions(self, db: Session, user_id: int, active_only: bool = True) -> List[UserSession]:
        """
        Получить все сессии пользователя
        """
        try:
            query = db.query(UserSession).filter(UserSession.user_id == user_id)
            
            if active_only:
                query = query.filter(
                    and_(
                        UserSession.revoked == False,
                        UserSession.expires_at > datetime.utcnow()
                    )
                )
            
            sessions = query.order_by(desc(UserSession.created_at)).all()
            return sessions
            
        except Exception as e:
            logger.error(f"Ошибка получения сессий пользователя {user_id}: {e}")
            return []

    def create_user_session(self, db: Session, user_id: int, refresh_token: str, 
                           ip_address: str = None, user_agent: str = None, 
                           device_fingerprint: str = None) -> UserSession:
        """
        Создать новую пользовательскую сессию
        """
        try:
            # Проверяем, есть ли уже активная сессия с такими же параметрами
            existing_session = None
            if ip_address and user_agent:
                existing_session = db.query(UserSession).filter(
                    and_(
                        UserSession.user_id == user_id,
                        UserSession.ip == ip_address,
                        UserSession.user_agent == user_agent,
                        UserSession.revoked == False,
                        UserSession.expires_at > datetime.utcnow()
                    )
                ).first()
            
            if existing_session:
                # Обновляем существующую сессию
                existing_session.refresh_token = refresh_token
                existing_session.expires_at = datetime.utcnow() + timedelta(hours=self.session_expire_hours)
                existing_session.last_activity = datetime.utcnow()
                if device_fingerprint:
                    existing_session.device_fingerprint = device_fingerprint
                
                db.commit()
                db.refresh(existing_session)
                
                logger.info(f"Обновлена существующая сессия для пользователя {user_id}")
                return existing_session
            
            # Создаем новую сессию
            session = UserSession(
                user_id=user_id,
                refresh_token=refresh_token,
                expires_at=datetime.utcnow() + timedelta(hours=self.session_expire_hours),
                ip=ip_address,
                user_agent=user_agent,
                device_fingerprint=device_fingerprint,
                last_activity=datetime.utcnow()
            )
            
            db.add(session)
            db.commit()
            db.refresh(session)
            
            logger.info(f"Создана новая сессия для пользователя {user_id}")
            return session
            
        except Exception as e:
            logger.error(f"Ошибка создания сессии для пользователя {user_id}: {e}")
            db.rollback()
            raise

    def update_session_activity(self, db: Session, session_id: int) -> bool:
        """
        Обновить время последней активности сессии
        """
        try:
            session = db.query(UserSession).filter(UserSession.id == session_id).first()
            if session and not session.revoked:
                session.last_activity = datetime.utcnow()
                db.commit()
                return True
            return False
            
        except Exception as e:
            logger.error(f"Ошибка обновления активности сессии {session_id}: {e}")
            db.rollback()
            return False

    def revoke_session(self, db: Session, session_id: int, reason: str = "manual") -> bool:
        """
        Отозвать сессию
        """
        try:
            session = db.query(UserSession).filter(UserSession.id == session_id).first()
            if session and not session.revoked:
                session.revoked = True
                session.revoked_at = datetime.utcnow()
                # session.revoke_reason = reason  # Поле может не существовать в модели
                
                db.commit()
                
                # Логируем событие безопасности
                self._log_security_event(
                    db, session.user_id, "session_revoked",
                    f"Сессия отозвана: {reason}",
                    session.ip, session.user_agent, "low"
                )
                
                logger.info(f"Сессия {session_id} отозвана: {reason}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Ошибка отзыва сессии {session_id}: {e}")
            db.rollback()
            return False

    def revoke_all_user_sessions(self, db: Session, user_id: int, except_session_id: int = None, reason: str = "logout_all") -> int:
        """
        Отозвать все сессии пользователя (кроме указанной)
        """
        try:
            query = db.query(UserSession).filter(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.revoked == False
                )
            )
            
            if except_session_id:
                query = query.filter(UserSession.id != except_session_id)
            
            sessions = query.all()
            revoked_count = 0
            
            for session in sessions:
                session.revoked = True
                session.revoked_at = datetime.utcnow()
                # session.revoke_reason = reason  # Поле может не существовать в модели
                revoked_count += 1
            
            db.commit()
            
            if revoked_count > 0:
                # Логируем событие безопасности
                self._log_security_event(
                    db, user_id, "sessions_revoked",
                    f"Отозвано {revoked_count} сессий: {reason}",
                    severity="medium"
                )
                
                logger.info(f"Отозвано {revoked_count} сессий для пользователя {user_id}: {reason}")
            
            return revoked_count
            
        except Exception as e:
            logger.error(f"Ошибка отзыва сессий пользователя {user_id}: {e}")
            db.rollback()
            return 0

    def cleanup_expired_sessions(self, db: Session) -> int:
        """
        Очистить истекшие сессии
        """
        try:
            expired_sessions = db.query(UserSession).filter(
                UserSession.expires_at <= datetime.utcnow()
            ).all()
            
            count = len(expired_sessions)
            
            for session in expired_sessions:
                if not session.revoked:
                    session.revoked = True
                    session.revoked_at = datetime.utcnow()
                    # session.revoke_reason = "expired"  # Поле может не существовать в модели
            
            db.commit()
            
            if count > 0:
                logger.info(f"Очищено {count} истекших сессий")
            
            return count
            
        except Exception as e:
            logger.error(f"Ошибка очистки истекших сессий: {e}")
            db.rollback()
            return 0

    def get_session_info(self, db: Session, session_id: int) -> Optional[Dict[str, Any]]:
        """
        Получить информацию о сессии
        """
        try:
            session = db.query(UserSession).filter(UserSession.id == session_id).first()
            if not session:
                return None
            
            return {
                "id": session.id,
                "user_id": session.user_id,
                "created_at": session.created_at,
                "expires_at": session.expires_at,
                "last_activity": getattr(session, 'last_activity', None),
                "ip": session.ip,
                "user_agent": session.user_agent,
                "device_fingerprint": getattr(session, 'device_fingerprint', None),
                "revoked": session.revoked,
                "revoked_at": session.revoked_at,
                "is_active": not session.revoked and session.expires_at > datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о сессии {session_id}: {e}")
            return None

    def validate_session_token(self, db: Session, user_id: int, refresh_token: str) -> Optional[UserSession]:
        """
        Проверить валидность токена сессии
        """
        try:
            session = db.query(UserSession).filter(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.refresh_token == refresh_token,
                    UserSession.revoked == False,
                    UserSession.expires_at > datetime.utcnow()
                )
            ).first()
            
            if session:
                # Обновляем время последней активности если поле существует
                if hasattr(session, 'last_activity'):
                    session.last_activity = datetime.utcnow()
                    db.commit()
            
            return session
            
        except Exception as e:
            logger.error(f"Ошибка валидации токена сессии для пользователя {user_id}: {e}")
            return None


# Глобальный экземпляр сервиса
authentication_service = AuthenticationService()

def get_authentication_service() -> AuthenticationService:
    """Получить экземпляр сервиса аутентификации"""
    return authentication_service
