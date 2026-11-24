"""Auth mixin for AuthenticationService.

Split from authentication_service.py.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re

from app.services.auth_svc._base import *  # noqa: F401, F403
from app.services.auth_svc._base import AuthenticationServiceMixinBase


def _email_verification_mac(user: User, nonce: str) -> str:
    # The token never contains contact information. Domain separation and a
    # protocol version prevent confusing this MAC with other uses of SECRET_KEY.
    payload = json.dumps(
        ["email-verification-v1", user.id, user.auth_epoch, (user.email or "").strip().casefold(), nonce],
        ensure_ascii=True, separators=(",", ":"),
    ).encode()
    digest = hmac.new(settings.SECRET_KEY.encode(), payload, hashlib.sha256).digest()[:16]
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _matches_email_verification_token(user: User, token: str) -> bool:
    parts = token.split(".")
    return (
        len(parts) == 3 and parts[0] == "v1" and len(parts[1]) == 22
        and hmac.compare_digest(parts[2], _email_verification_mac(user, parts[1]))
    )


class AuthMixin(AuthenticationServiceMixinBase):
    """Auth methods."""

    def reset_password(
        self, db: Session, token: str, new_password: str
    ) -> dict[str, Any]:
        """Сбрасывает пароль пользователя"""
        # This legacy issuer used token_urlsafe(32): exactly 43 base64url
        # characters. Canonical rows store 64-character SHA-256 digests in
        # the same table, which must never be accepted as bearer credentials.
        if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            return {"success": False, "message": "Недействительный или истекший токен"}
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

            # Establish a common account lock before consuming a reset token
            # or touching the user's sessions. Re-read both records under lock:
            # the initial token lookup is only an untrusted identity hint.
            user = (
                db.query(User).filter(User.id == reset_token.user_id)
                .with_for_update(key_share=True).populate_existing().first()
            )
            if not user or not user.is_active:
                db.rollback()
                return {"success": False, "message": "Недействительный или истекший токен"}

            reset_token = (
                db.query(PasswordResetToken)
                .filter(
                    PasswordResetToken.token == token,
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.used.is_(False),
                    PasswordResetToken.expires_at > datetime.now(UTC),
                )
                .with_for_update().populate_existing().first()
            )
            if not reset_token:
                db.rollback()
                return {"success": False, "message": "Недействительный или истекший токен"}

            from app.services.token_blacklist_service import (
                revoke_account_sessions_locked,
            )
            revoke_account_sessions_locked(db, user, revoke_password_resets=True)
            expires_at = reset_token.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if datetime.now(UTC) >= expires_at:
                db.rollback()
                return {"success": False, "message": "Недействительный или истекший токен"}

            new_hash = get_password_hash(new_password)
            if datetime.now(UTC) >= expires_at:
                db.rollback()
                return {"success": False, "message": "Недействительный или истекший токен"}
            user.hashed_password = new_hash
            reset_token.used = True
            reset_token.used_at = datetime.now(UTC)

            db.commit()

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
            db.rollback()
            logger.error("Error resetting password: %s", type(e).__name__)
            return {"success": False, "message": "Ошибка сброса пароля"}


    def change_password(
        self, db: Session, user_id: int, current_password: str, new_password: str,
        *, bearer_context=None,
    ) -> dict[str, Any]:
        """Меняет пароль пользователя"""
        from app.services.profile_contact_security import (
            ProfileBearerInvalid,
            check_bearer_expiry,
            check_patient_scope,
            check_profile_bearer,
        )

        try:
            user = (
                db.query(User).filter(User.id == user_id)
                .with_for_update(key_share=True).populate_existing().first()
            )
            if bearer_context is not None:
                if user is None:
                    raise ProfileBearerInvalid("Bearer session unavailable")
                check_profile_bearer(db, user, bearer_context)
                check_patient_scope(db, user, bearer_context)
            if not user or not user.is_active:
                db.rollback()
                return {"success": False, "message": "Неверный текущий пароль"}

            # Проверяем текущий пароль
            if not verify_password(current_password, user.hashed_password):
                db.rollback()
                return {"success": False, "message": "Неверный текущий пароль"}

            new_hash = get_password_hash(new_password)
            if bearer_context is not None:
                check_bearer_expiry(bearer_context)

            from app.services.token_blacklist_service import (
                revoke_account_sessions_locked,
            )
            revoke_account_sessions_locked(db, user, revoke_password_resets=True)
            if bearer_context is not None:
                check_bearer_expiry(bearer_context)

            # Обновляем пароль и сбрасываем флаг must_change_password
            user.hashed_password = new_hash
            user.must_change_password = False

            db.commit()

            self._log_user_activity(db, user.id, "password_changed", "Пароль изменен")
            self._log_security_event(
                db,
                user.id,
                "password_changed",
                "medium",
                "Пароль пользователя был изменен",
            )

            return {"success": True, "message": "Пароль успешно изменен"}

        except ProfileBearerInvalid:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error("Error changing password: %s", type(e).__name__)
            return {"success": False, "message": "Ошибка смены пароля"}


    def create_email_verification_token(
        self, db: Session, user_id: int, ip_address: str = None, user_agent: str = None,
        *, expected_auth_epoch: int | None = None, expected_email: str | None = None,
    ) -> dict[str, Any]:
        """Создает токен для верификации email"""
        try:
            hint = db.query(User).filter(User.id == user_id).first()
            if not hint:
                return {"success": False, "message": "Пользователь не найден"}
            snapshot_epoch = hint.auth_epoch if expected_auth_epoch is None else expected_auth_epoch
            snapshot_email = hint.email if expected_email is None else expected_email
            user = (db.query(User).filter(User.id == user_id)
                    .with_for_update(key_share=True).populate_existing().first())
            if (not user or not user.is_active or not user.email
                or user.auth_epoch != snapshot_epoch or user.email != snapshot_email):
                db.rollback()
                return {"success": False, "message": "Пользователь не найден"}

            # Отзываем старые токены
            db.query(EmailVerificationToken).filter(
                and_(
                    EmailVerificationToken.user_id == user.id,
                    EmailVerificationToken.verified == False,
                )
            ).update({"verified": True, "verified_at": datetime.now(UTC)})

            # Создаем новый токен
            nonce = secrets.token_urlsafe(16)
            token = f"v1.{nonce}.{_email_verification_mac(user, nonce)}"
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
            db.rollback()
            logger.error("Error creating email verification token: %s", type(e).__name__)
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

            user = (db.query(User).filter(User.id == verification_token.user_id)
                    .with_for_update(key_share=True).populate_existing().first())
            if not user or not user.is_active or not user.email or not _matches_email_verification_token(user, token):
                db.rollback()
                return {"success": False, "message": "Недействительный или истекший токен"}

            from app.models.user_profile import UserProfile

            profile = (db.query(UserProfile).filter(UserProfile.user_id == user.id)
                       .with_for_update().populate_existing().first())
            if profile is None:
                profile, _, _ = get_user_management_service().ensure_user_support_records(db, user, commit=False)
            verification_token = (db.query(EmailVerificationToken).filter(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.token == token,
                EmailVerificationToken.verified.is_(False),
                EmailVerificationToken.expires_at > datetime.now(UTC),
            ).with_for_update().populate_existing().first())
            if not verification_token:
                db.rollback()
                return {"success": False, "message": "Недействительный или истекший токен"}

            # Profile is the sole current-email verification state. The token
            # records only one-time consumption, not a permanent assertion.
            profile.email_verified = True
            verification_token.verified = True
            verification_token.verified_at = datetime.now(UTC)

            db.commit()

            self._log_user_activity(
                db, verification_token.user_id, "email_verified", "Email верифицирован"
            )

            return {"success": True, "message": "Email успешно верифицирован"}

        except Exception as e:
            db.rollback()
            logger.error("Error verifying email: %s", type(e).__name__)
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

            email_verified = bool(getattr(profile, "email_verified", False))

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
            logger.error("Error getting user profile: %s", type(e).__name__)
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
            logger.error("Error logging login attempt: %s", type(e).__name__)


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
            import json as _json

            from app.models.authentication import UserActivity
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
            logger.error("Error logging security event: %s", type(e).__name__)


