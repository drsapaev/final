"""Auth mixin for AuthenticationService.

Split from authentication_service.py.
"""
from __future__ import annotations

from app.services.auth_svc._base import *  # noqa: F401, F403
from app.services.auth_svc._base import AuthenticationServiceMixinBase


class AuthMixin(AuthenticationServiceMixinBase):
    """Auth methods."""

    def create_password_reset_token(
        self, db: Session, email: str, ip_address: str = None, user_agent: str = None
    ) -> dict[str, Any]:
        """Создает токен для сброса пароля"""
        try:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                return {
                    "success": False,
                    "message": "Пользователь с таким email не найден",
                }

            # Отзываем старые токены
            db.query(PasswordResetToken).filter(
                and_(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.used == False,
                )
            ).update({"used": True, "used_at": datetime.now(UTC)})

            # Создаем новый токен
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now(UTC) + timedelta(
                hours=self.password_reset_expire_hours
            )

            reset_token = PasswordResetToken(
                user_id=user.id,
                token=token,
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.add(reset_token)
            db.commit()

            self._log_user_activity(
                db,
                user.id,
                "password_reset_requested",
                "Запрос сброса пароля",
                ip_address,
                user_agent,
            )

            return {
                "success": True,
                "message": "Токен сброса пароля создан",
                "token": token,
                "expires_at": expires_at,
            }

        except Exception as e:
            logger.error(f"Error creating password reset token: {e}")
            return {"success": False, "message": "Ошибка создания токена сброса пароля"}


    def reset_password(
        self, db: Session, token: str, new_password: str
    ) -> dict[str, Any]:
        """Сбрасывает пароль пользователя"""
        try:
            # Проверяем токен
            reset_token = (
                db.query(PasswordResetToken)
                .filter(
                    and_(
                        PasswordResetToken.token == token,
                        PasswordResetToken.used == False,
                        PasswordResetToken.expires_at > datetime.now(UTC),
                    )
                )
                .first()
            )

            if not reset_token:
                return {
                    "success": False,
                    "message": "Недействительный или истекший токен",
                }

            # Обновляем пароль
            user = db.query(User).filter(User.id == reset_token.user_id).first()
            if not user:
                return {"success": False, "message": "Пользователь не найден"}

            user.hashed_password = get_password_hash(new_password)
            reset_token.used = True
            reset_token.used_at = datetime.now(UTC)

            # SECURITY: Отзываем все refresh токены пользователя ВНУТРИ транзакции
            # (раньше update шёл после commit и терялся).
            db.query(RefreshToken).filter(RefreshToken.user_id == user.id).update(
                {"revoked": True, "revoked_at": datetime.now(UTC)}
            )

            # SECURITY: Деактивируем все активные сессии пользователя
            db.query(UserSession).filter(
                UserSession.user_id == user.id,
                UserSession.revoked == False,
            ).update({"revoked": True, "revoked_at": datetime.now(UTC)})

            db.commit()

            # SECURITY: Отзываем все access-токены пользователя (sentinel-запись).
            # Должно быть ПОСЛЕ commit() — blacklist-сервис сам делает commit.
            from app.services.token_blacklist_service import token_blacklist_service
            token_blacklist_service.blacklist_all_user_tokens(
                db, user.id, reason="password_reset"
            )

            self._log_user_activity(db, user.id, "password_reset", "Пароль сброшен")
            self._log_security_event(
                db,
                user.id,
                "password_reset",
                "medium",
                "Пароль пользователя был сброшен",
            )

            return {"success": True, "message": "Пароль успешно сброшен"}

        except Exception as e:
            logger.error(f"Error resetting password: {e}")
            return {"success": False, "message": "Ошибка сброса пароля"}


    def change_password(
        self, db: Session, user_id: int, current_password: str, new_password: str
    ) -> dict[str, Any]:
        """Меняет пароль пользователя"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "message": "Пользователь не найден"}

            # Проверяем текущий пароль
            if not verify_password(current_password, user.hashed_password):
                return {"success": False, "message": "Неверный текущий пароль"}

            # Обновляем пароль и сбрасываем флаг must_change_password
            user.hashed_password = get_password_hash(new_password)
            user.must_change_password = False

            # SECURITY: Отзываем все refresh токены ВНУТРИ транзакции.
            db.query(RefreshToken).filter(RefreshToken.user_id == user.id).update(
                {"revoked": True, "revoked_at": datetime.now(UTC)}
            )

            # SECURITY: Деактивируем все активные сессии
            db.query(UserSession).filter(
                UserSession.user_id == user.id,
                UserSession.revoked == False,
            ).update({"revoked": True, "revoked_at": datetime.now(UTC)})

            db.commit()

            # SECURITY: Отзываем все access-токены (sentinel-запись, после commit).
            from app.services.token_blacklist_service import token_blacklist_service
            token_blacklist_service.blacklist_all_user_tokens(
                db, user.id, reason="password_change"
            )

            self._log_user_activity(db, user.id, "password_changed", "Пароль изменен")
            self._log_security_event(
                db,
                user.id,
                "password_changed",
                "medium",
                "Пароль пользователя был изменен",
            )

            return {"success": True, "message": "Пароль успешно изменен"}

        except Exception as e:
            logger.error(f"Error changing password: {e}")
            return {"success": False, "message": "Ошибка смены пароля"}


    def create_email_verification_token(
        self, db: Session, user_id: int, ip_address: str = None, user_agent: str = None
    ) -> dict[str, Any]:
        """Создает токен для верификации email"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"success": False, "message": "Пользователь не найден"}

            # Отзываем старые токены
            db.query(EmailVerificationToken).filter(
                and_(
                    EmailVerificationToken.user_id == user.id,
                    EmailVerificationToken.verified == False,
                )
            ).update({"verified": True, "verified_at": datetime.now(UTC)})

            # Создаем новый токен
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now(UTC) + timedelta(
                hours=self.email_verification_expire_hours
            )

            verification_token = EmailVerificationToken(
                user_id=user.id,
                token=token,
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.add(verification_token)
            db.commit()

            return {
                "success": True,
                "message": "Токен верификации email создан",
                "token": token,
                "expires_at": expires_at,
            }

        except Exception as e:
            logger.error(f"Error creating email verification token: {e}")
            return {
                "success": False,
                "message": "Ошибка создания токена верификации email",
            }


    def verify_email(self, db: Session, token: str) -> dict[str, Any]:
        """Верифицирует email пользователя"""
        try:
            # Проверяем токен
            verification_token = (
                db.query(EmailVerificationToken)
                .filter(
                    and_(
                        EmailVerificationToken.token == token,
                        EmailVerificationToken.verified == False,
                        EmailVerificationToken.expires_at > datetime.now(UTC),
                    )
                )
                .first()
            )

            if not verification_token:
                return {
                    "success": False,
                    "message": "Недействительный или истекший токен",
                }

            # Отмечаем email как верифицированный
            verification_token.verified = True
            verification_token.verified_at = datetime.now(UTC)

            db.commit()

            self._log_user_activity(
                db, verification_token.user_id, "email_verified", "Email верифицирован"
            )

            return {"success": True, "message": "Email успешно верифицирован"}

        except Exception as e:
            logger.error(f"Error verifying email: {e}")
            return {"success": False, "message": "Ошибка верификации email"}


    def get_user_profile(self, db: Session, user_id: int) -> dict[str, Any] | None:
        """Получает профиль пользователя"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return None

            profile, _, _ = get_user_management_service().ensure_user_support_records(
                db, user
            )

            # Получаем последний вход
            last_login = (
                db.query(LoginAttempt)
                .filter(
                    and_(LoginAttempt.user_id == user.id, LoginAttempt.success == True)
                )
                .order_by(desc(LoginAttempt.attempted_at))
                .first()
            )

            # Проверяем верификацию email
            token_email_verified = (
                db.query(EmailVerificationToken)
                .filter(
                    and_(
                        EmailVerificationToken.user_id == user.id,
                        EmailVerificationToken.verified == True,
                    )
                )
                .first()
                is not None
            )
            email_verified = bool(getattr(profile, "email_verified", False) or token_email_verified)

            # Проверяем 2FA (строго булево значение)
            two_factor_enabled = bool(
                user.two_factor_auth
                and getattr(user.two_factor_auth, 'totp_enabled', False)
            )

            return {
                "id": user.id,
                "username": user.username,
                "full_name": profile.full_name or user.full_name,
                "first_name": profile.first_name,
                "last_name": profile.last_name,
                "middle_name": profile.middle_name,
                "email": user.email,
                "phone": profile.phone,
                "avatar_url": profile.avatar_url,
                "bio": profile.bio,
                "website": profile.website,
                "language": profile.language,
                "timezone": profile.timezone,
                "nationality": profile.nationality,
                "date_of_birth": profile.date_of_birth,
                "gender": profile.gender,
                "role": user.role,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
                "email_verified": email_verified,
                "phone_verified": bool(getattr(profile, "phone_verified", False)),
                "created_at": user.created_at if hasattr(user, 'created_at') else None,
                "updated_at": (
                    profile.updated_at
                    if getattr(profile, "updated_at", None)
                    else getattr(user, "updated_at", None)
                ),
                "last_login": profile.last_login or (last_login.attempted_at if last_login else None),
                "two_factor_enabled": two_factor_enabled,
            }

        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return None


    def _log_login_attempt(
        self,
        db: Session,
        user_id: int | None,
        username: str,
        ip_address: str,
        user_agent: str,
        success: bool,
        failure_reason: str | None,
    ):
        """Логирует попытку входа"""
        try:
            login_attempt = LoginAttempt(
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                success=success,
                failure_reason=failure_reason,
            )
            db.add(login_attempt)
            db.commit()
        except Exception as e:
            logger.error(f"Error logging login attempt: {e}")


    def _log_user_activity(
        self,
        db: Session,
        user_id: int,
        activity_type: str,
        description: str,
        ip_address: str = None,
        user_agent: str = None,
        metadata: dict[str, Any] = None,
    ):
        """Логирует активность пользователя в БД (UserActivity table)."""
        try:
            from app.models.authentication import UserActivity
            import json as _json
            activity = UserActivity(
                user_id=user_id,
                activity_type=activity_type,
                description=description,
                ip_address=ip_address,
                user_agent=user_agent,
                extra_data=_json.dumps(metadata) if metadata else None,
            )
            db.add(activity)
            db.flush()  # Don't commit — caller controls transaction
        except Exception as e:
            # Non-blocking: log warning but don't fail the auth operation
            logger.warning("Failed to log user activity: %s (type=%s, user=%d)", e, activity_type, user_id)


    def _log_security_event(
        self,
        db: Session,
        user_id: int | None,
        event_type: str,
        severity: str,
        description: str,
        ip_address: str = None,
        user_agent: str = None,
        metadata: dict[str, Any] = None,
    ):
        """Логирует событие безопасности"""
        try:
            security_event = SecurityEvent(
                user_id=user_id,
                event_type=event_type,
                severity=severity,
                description=description,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata=str(metadata) if metadata else None,
            )
            db.add(security_event)
            db.commit()
        except Exception as e:
            logger.error(f"Error logging security event: {e}")


