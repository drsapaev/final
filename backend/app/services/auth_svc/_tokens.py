"""Tokens mixin for AuthenticationService.

Split from authentication_service.py.
"""
from __future__ import annotations

from app.core.pii_masker import mask_identifier  # PR-31: mask usernames in logs
from app.services.auth_svc._base import *  # noqa: F401, F403
from app.services.auth_svc._base import AuthenticationServiceMixinBase


class TokensMixin(AuthenticationServiceMixinBase):
    """Tokens methods."""

    def __init__(self):
        self.algorithm = "HS256"
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.refresh_token_expire_days = 30
        self.password_reset_expire_hours = 1
        self.email_verification_expire_hours = 24
        self.session_expire_hours = 24
        self.max_login_attempts = 5
        self.lockout_duration_minutes = 15


    def create_access_token(
        self, data: dict[str, Any], expires_delta: timedelta | None = None
    ) -> str:
        """Создает JWT access токен"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(UTC) + expires_delta
        else:
            expire = datetime.now(UTC) + timedelta(
                minutes=self.access_token_expire_minutes
            )

        to_encode.update({"exp": expire, "type": "access", "jti": str(uuid.uuid4())})
        encoded_jwt = jwt.encode(
            to_encode, settings.SECRET_KEY, algorithm=self.algorithm
        )
        return encoded_jwt


    def create_refresh_token(self, user_id: int, jti: str) -> str:
        """Создает JWT refresh токен"""
        data = {"user_id": user_id, "jti": jti, "type": "refresh"}
        expire = datetime.now(UTC) + timedelta(days=self.refresh_token_expire_days)
        data.update({"exp": expire})

        encoded_jwt = jwt.encode(data, settings.SECRET_KEY, algorithm=self.algorithm)
        return encoded_jwt


    def verify_token(
        self, token: str, token_type: str = "access"
    ) -> dict[str, Any] | None:
        """Проверяет JWT токен (без проверки blacklist)"""
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[self.algorithm]
            )
            if payload.get("type") != token_type:
                return None
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid token")
            return None


    def verify_token_with_blacklist(
        self, db: Session, token: str, token_type: str = "access"
    ) -> dict[str, Any] | None:
        """
        Проверяет JWT токен с проверкой черного списка.

        Используйте этот метод для критических операций.
        """
        payload = self.verify_token(token, token_type)
        if not payload:
            return None

        jti = payload.get("jti")
        if not jti:
            return payload  # Старые токены без jti пропускаем

        # Проверяем blacklist
        from app.services.token_blacklist_service import token_blacklist_service
        if token_blacklist_service.is_token_blacklisted(db, jti):
            logger.warning(f"Token {jti} is blacklisted")
            return None

        return payload


    def authenticate_user(
        self,
        db: Session,
        username: str,
        password: str,
        ip_address: str = None,
        user_agent: str = None,
    ) -> tuple[User | None, str]:
        """Аутентифицирует пользователя"""
        try:
            logger.debug("authenticate_user called with username=%s", mask_identifier(username))

            # Ищем пользователя по username или email
            user = (
                db.query(User)
                .filter(or_(User.username == username, User.email == username))
                .first()
            )

            if not user:
                logger.debug("User not found for username=%s", mask_identifier(username))
                self._log_login_attempt(
                    db, None, username, ip_address, user_agent, False, "user_not_found"
                )
                return None, "Пользователь не найден"

            logger.debug(
                "User found: ID=%d, Username=%s, IsActive=%s",
                user.id,
                mask_identifier(user.username),
                user.is_active,
            )

            if not user.is_active:
                logger.debug("User is inactive")
                self._log_login_attempt(
                    db,
                    user.id,
                    username,
                    ip_address,
                    user_agent,
                    False,
                    "user_inactive",
                )
                return None, "Пользователь деактивирован"

            logger.debug("Verifying password...")
            password_valid = verify_password(password, user.hashed_password)
            logger.debug("Password verification result: %s", password_valid)

            if not password_valid:
                logger.debug("Invalid password")
                self._log_login_attempt(
                    db,
                    user.id,
                    username,
                    ip_address,
                    user_agent,
                    False,
                    "invalid_password",
                )
                return None, "Неверный пароль"

            # Проверяем блокировку
            if self._is_user_locked(db, user.id):
                logger.debug("User is locked")
                self._log_login_attempt(
                    db, user.id, username, ip_address, user_agent, False, "user_locked"
                )
                return (
                    None,
                    "Пользователь заблокирован из-за множественных неудачных попыток входа",
                )

            # Успешный вход
            logger.debug("Authentication successful")
            self._log_login_attempt(
                db, user.id, username, ip_address, user_agent, True, None
            )
            self._log_user_activity(
                db, user.id, "login", "Успешный вход в систему", ip_address, user_agent
            )

            return user, "Успешная аутентификация"

        except Exception as e:
            logger.debug("Exception in authenticate_user: %s", e, exc_info=True)
            logger.error("Error authenticating user: %s", e, exc_info=True)
            return None, "Ошибка аутентификации"


    def login_user(
        self,
        db: Session,
        username: str,
        password: str,
        ip_address: str = None,
        user_agent: str = None,
        device_fingerprint: str = None,
        remember_me: bool = False,
    ) -> dict[str, Any]:
        """Выполняет вход пользователя"""
        logger.debug("login_user called with username=%s", mask_identifier(username))

        user, message = self.authenticate_user(
            db, username, password, ip_address, user_agent
        )

        logger.debug(
            "authenticate_user returned user=%s, message=%s",
            user is not None,
            message,
        )

        if not user:
            logger.debug("Authentication failed, returning error")
            return {"success": False, "message": message, "user": None, "tokens": None}

        # ✅ SECURITY: Проверяем, требуется ли 2FA до выдачи токенов
        requires_2fa = False
        two_factor_method = None

        # ✅ CERTIFICATION: Принудительное 2FA для критичных ролей (Admin, Cashier)
        # ✅ CI/TESTING: Можно отключить через переменную окружения DISABLE_2FA_REQUIREMENT=1
        import os
        disable_2fa_requirement = os.getenv("DISABLE_2FA_REQUIREMENT", "").lower() in ("1", "true", "yes")

        from app.core.roles import Roles

        CRITICAL_2FA_ROLES = {Roles.ADMIN, Roles.CASHIER}
        user_role = getattr(user, "role", None)
        is_critical_role = user_role in CRITICAL_2FA_ROLES

        # Проверяем, настроена ли 2FA у пользователя
        has_2fa_enabled = (
            user.two_factor_auth
            and user.two_factor_auth.totp_enabled
            and user.two_factor_auth.totp_verified
        )

        # Если роль критичная (Admin/Cashier), но 2FA не настроена - блокируем вход
        # КРОМЕ случая, когда DISABLE_2FA_REQUIREMENT=1 (для тестирования)
        if is_critical_role and not has_2fa_enabled and not disable_2fa_requirement:
            return {
                "success": False,
                "message": f"Для роли {user_role} требуется настройка двухфакторной аутентификации (2FA). Пожалуйста, настройте 2FA перед входом.",
                "user": None,
                "tokens": None,
                "requires_2fa": False,
                "requires_2fa_setup": True,  # ✅ Новый флаг: требуется настройка 2FA
                "two_factor_method": None,
            }

        # Если 2FA настроена, требуем верификацию
        if has_2fa_enabled:
            requires_2fa = True
            two_factor_method = "totp"

        # Если 2FA требуется — НЕ выдаём основные токены. Создаём временный pending_2fa_token
        if requires_2fa:
            pending_2fa_token = secrets.token_urlsafe(32)
            # Храним маркер в таблице сессий как незавершённую аутентификацию
            session_expires = datetime.now(UTC) + timedelta(
                hours=self.session_expire_hours
            )
            user_session = UserSession(
                user_id=user.id,
                refresh_token=pending_2fa_token,
                expires_at=session_expires,
                ip=ip_address,
                user_agent=user_agent,
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
                    "is_superuser": user.is_superuser,
                },
                "tokens": None,
                "requires_2fa": True,
                "two_factor_method": two_factor_method,
                "pending_2fa_token": pending_2fa_token,
            }

        # Иначе — обычная выдача токенов
        # M4-P0-3: Session fixation protection — revoke all existing sessions
        # before creating a new one. Prevents stolen sessions from remaining
        # valid after a fresh login.
        if getattr(settings, "REVOKE_SESSIONS_ON_NEW_LOGIN", True):
            self._revoke_all_user_sessions(db, user.id, reason="new_login")

        jti = str(uuid.uuid4())
        access_token = self.create_access_token(
            {
                "sub": str(user.id),
                "username": user.username,
                "role": user.role,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
            }
        )
        refresh_token = self.create_refresh_token(user.id, jti)
        refresh_token_obj = RefreshToken(
            user_id=user.id,
            token=refresh_token,
            jti=jti,
            expires_at=datetime.now(UTC)
            + timedelta(days=self.refresh_token_expire_days),
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
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
                "is_superuser": user.is_superuser,
            },
            "tokens": {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": self.access_token_expire_minutes * 60,
            },
            "requires_2fa": requires_2fa,
            "two_factor_method": two_factor_method,
            "must_change_password": getattr(user, 'must_change_password', False),
        }


    def refresh_access_token(self, db: Session, refresh_token: str) -> dict[str, Any]:
        """Обновляет access токен.

        SECURITY (RFC 6749 §10.4): refresh-token rotation — при каждом успешном
        обмене выдаём НОВЫЙ refresh-токен и отзываем старый. Повторное использование
        отозванного refresh-токена трактуется как кража — отзываем всю сессию-семью.
        """
        try:
            # 1) Проверяем подпись + type=refresh + blacklist.
            payload = self.verify_token_with_blacklist(refresh_token, "refresh")
            if not payload:
                return {"success": False, "message": "Недействительный refresh токен"}

            # 2) Проверяем токен в БД.
            token_obj = (
                db.query(RefreshToken)
                .filter(
                    and_(
                        RefreshToken.token == refresh_token,
                        RefreshToken.expires_at > datetime.now(UTC),
                    )
                )
                .first()
            )

            if not token_obj:
                return {
                    "success": False,
                    "message": "Refresh токен не найден или истек",
                }

            # 3) Reuse detection: токен уже был отозван — возможная кража.
            if token_obj.revoked:
                # Отзываем ВСЕ refresh-токены пользователя (session family).
                db.query(RefreshToken).filter(
                    RefreshToken.user_id == token_obj.user_id
                ).update({"revoked": True, "revoked_at": datetime.now(UTC)})
                db.query(UserSession).filter(
                    UserSession.user_id == token_obj.user_id,
                    UserSession.revoked == False,
                ).update({"revoked": True, "revoked_at": datetime.now(UTC)})
                db.commit()
                from app.services.token_blacklist_service import token_blacklist_service
                token_blacklist_service.blacklist_all_user_tokens(
                    db, token_obj.user_id, reason="refresh_token_reuse"
                )
                logger.warning(
                    "Refresh-token reuse detected for user_id=%s — all tokens revoked",
                    token_obj.user_id,
                )
                return {
                    "success": False,
                    "message": "Refresh токен недействителен",
                }

            # 4) Получаем пользователя
            user = db.query(User).filter(User.id == token_obj.user_id).first()
            if not user or not user.is_active:
                return {
                    "success": False,
                    "message": "Пользователь не найден или неактивен",
                }

            # 5) Создаём НОВЫЕ access + refresh токены (rotation).
            new_jti = str(uuid.uuid4())
            access_token = self.create_access_token(
                {
                    "sub": str(user.id),
                    "username": user.username,
                    "role": user.role,
                    "is_active": user.is_active,
                    "is_superuser": user.is_superuser,
                }
            )
            new_refresh_token = self.create_refresh_token(user.id, new_jti)

            # 6) Отзываем старый refresh-токен и записываем новый в БД.
            token_obj.revoked = True
            token_obj.revoked_at = datetime.now(UTC)

            new_token_obj = RefreshToken(
                user_id=user.id,
                token=new_refresh_token,
                jti=new_jti,
                expires_at=datetime.now(UTC)
                + timedelta(days=self.refresh_token_expire_days),
                ip_address=token_obj.ip_address,
                user_agent=token_obj.user_agent,
                device_fingerprint=token_obj.device_fingerprint,
            )
            db.add(new_token_obj)

            # Обновляем linked UserSession.refresh_token, чтобы сессия оставалась активной.
            db.query(UserSession).filter(
                UserSession.user_id == user.id,
                UserSession.refresh_token == refresh_token,
                UserSession.revoked == False,
            ).update({"refresh_token": new_refresh_token, "last_activity": datetime.now(UTC)})

            db.commit()

            return {
                "success": True,
                "access_token": access_token,
                "refresh_token": new_refresh_token,  # NEW: rotated token
                "token_type": "bearer",
                "expires_in": self.access_token_expire_minutes * 60,
            }

        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            db.rollback()
            return {"success": False, "message": "Ошибка обновления токена"}


    def logout_user(
        self,
        db: Session,
        refresh_token: str = None,
        user_id: int = None,
        logout_all: bool = False,
        access_token_jti: str | None = None,
        access_token_exp: datetime | None = None,
    ) -> dict[str, Any]:
        """Выполняет выход пользователя.

        Args:
            access_token_jti: JTI текущего access-токена (для индивидуального отзыва).
            access_token_exp: expiry access-токена (нужен для blacklist_token).
        """
        try:
            if logout_all and user_id:
                # Отзываем все refresh токены пользователя
                db.query(RefreshToken).filter(RefreshToken.user_id == user_id).update(
                    {"revoked": True, "revoked_at": datetime.now(UTC)}
                )

                # Деактивируем все сессии (модель использует `revoked`, не `is_active`)
                db.query(UserSession).filter(
                    UserSession.user_id == user_id,
                    UserSession.revoked == False,
                ).update({"revoked": True, "revoked_at": datetime.now(UTC)})

                db.commit()

                # SECURITY: Sentinel-запись — отзывает ВСЕ access-токены пользователя.
                from app.services.token_blacklist_service import token_blacklist_service
                token_blacklist_service.blacklist_all_user_tokens(
                    db, user_id, reason="logout_all"
                )

                self._log_user_activity(
                    db, user_id, "logout_all", "Выход со всех устройств"
                )

            elif refresh_token:
                # Отзываем конкретный refresh токен
                token_obj = (
                    db.query(RefreshToken)
                    .filter(RefreshToken.token == refresh_token)
                    .first()
                )
                if token_obj:
                    token_obj.revoked = True
                    token_obj.revoked_at = datetime.now(UTC)

                    # Деактивируем ТОЛЬКО связанную сессию (не все сессии пользователя).
                    db.query(UserSession).filter(
                        UserSession.user_id == token_obj.user_id,
                        UserSession.refresh_token == refresh_token,
                    ).update({"revoked": True, "revoked_at": datetime.now(UTC)})

                    db.commit()

                    # SECURITY: Отзываем текущий access-токен по jti (если передан).
                    if access_token_jti and access_token_exp:
                        from app.services.token_blacklist_service import (
                            token_blacklist_service,
                        )
                        token_blacklist_service.blacklist_token(
                            db,
                            jti=access_token_jti,
                            expires_at=access_token_exp,
                            user_id=token_obj.user_id,
                            reason="logout",
                        )

                    self._log_user_activity(
                        db, token_obj.user_id, "logout", "Выход из системы"
                    )
                else:
                    db.commit()

            else:
                db.commit()

            return {"success": True, "message": "Успешный выход"}

        except Exception as e:
            logger.error(f"Error logging out user: {e}")
            db.rollback()
            return {"success": False, "message": "Ошибка выхода"}

    def _revoke_all_user_sessions(
        self, db: Session, user_id: int, *, reason: str = "unspecified"
    ) -> int:
        """M4-P0-3: Revoke all active sessions + refresh tokens for a user.

        Used for session fixation protection on new login.
        Returns the number of sessions revoked.

        Args:
            db: SQLAlchemy session
            user_id: User whose sessions to revoke
            reason: Audit reason (e.g. 'new_login', 'security_alert')
        """
        try:
            now = datetime.now(UTC)

            # Revoke all active refresh tokens
            refresh_count = (
                db.query(RefreshToken)
                .filter(
                    RefreshToken.user_id == user_id,
                    RefreshToken.revoked == False,
                )
                .update({"revoked": True, "revoked_at": now})
            )

            # Revoke all active user sessions
            session_count = (
                db.query(UserSession)
                .filter(
                    UserSession.user_id == user_id,
                    UserSession.revoked == False,
                )
                .update({"revoked": True, "revoked_at": now})
            )

            db.commit()

            if refresh_count > 0 or session_count > 0:
                logger.info(
                    "Revoked %d sessions and %d refresh tokens for user_id (reason=%s)",
                    session_count,
                    refresh_count,
                    reason,
                )

            return session_count

        except Exception as e:
            logger.error("Error revoking user sessions: %s", e)
            db.rollback()
            return 0


