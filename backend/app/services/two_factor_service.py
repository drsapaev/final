"""
Сервис для двухфакторной аутентификации (2FA)
"""

import base64
import hashlib
import hmac
import io
import logging
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import qrcode
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.pii_masker import mask_email
from app.core.security import verify_password
from app.models.authentication import UserSession
from app.models.two_factor_auth import (
    TwoFactorAuth,
    TwoFactorBackupCode,
    TwoFactorDevice,
    TwoFactorRecovery,
    TwoFactorSession,
    TwoFactorVerificationCode,
)
from app.models.user import User
from app.services.email_sms_enhanced import EmailSMSEnhancedService
from app.services.sms_providers import SMSProviderType, get_sms_manager

logger = logging.getLogger(__name__)


class EnrollmentSessionInvalid(ValueError):
    """Enrollment token is expired, revoked, or no longer belongs to the user."""


class PendingSessionInvalid(ValueError):
    """Pending 2FA challenge is expired, revoked, or no longer owned."""


class BearerSessionInvalid(ValueError):
    """The caller's bearer session was revoked before the 2FA operation."""


class TwoFactorAlreadyEnabled(ValueError):
    """The active 2FA configuration cannot be replaced by setup."""


class TwoFactorService:
    """Сервис для работы с 2FA"""

    def __init__(self):
        self.totp_window = 1  # Окно для проверки TOTP кодов
        self.backup_codes_count = 10  # Количество backup кодов
        self.recovery_token_length = 32  # Длина токена восстановления
        self.session_expiry_hours = 24  # Время жизни сессии
        self.recovery_expiry_hours = 1  # Время жизни токена восстановления
        self.recovery_rate_limit_per_hour = 3  # dispatch-запросов на аккаунт в час
        # TWOFACTOR-BE-001 (#4063): brute-force defense on the second factor.
        # The endpoint limiter is per-IP (bypassable), so the cap lives on the
        # 2FA record: N consecutive failures -> temporary lock, storage-backed
        # (two_factor_auth.failed_attempts / locked_until, alembic 0095).
        self.max_verify_attempts = 5
        self.verify_lockout_minutes = 15
        self.sms_manager = get_sms_manager()
        self.email_service = EmailSMSEnhancedService()

    def generate_totp_secret(self) -> str:
        """Генерирует секретный ключ для TOTP"""
        return base64.b32encode(secrets.token_bytes(20)).decode('utf-8')

    def generate_totp_code(self, secret: str, timestamp: int | None = None) -> str:
        """Генерирует TOTP код"""
        if timestamp is None:
            timestamp = int(time.time())

        # Конвертируем secret из base32
        try:
            key = base64.b32decode(secret)
        except Exception:
            raise ValueError("Invalid secret key")

        # Вычисляем время
        time_counter = timestamp // 30

        # Создаем HMAC
        msg = time_counter.to_bytes(8, 'big')
        hmac_digest = hmac.new(key, msg, hashlib.sha1).digest()

        # Извлекаем код
        offset = hmac_digest[-1] & 0x0F
        code = (
            (hmac_digest[offset] & 0x7F) << 24
            | (hmac_digest[offset + 1] & 0xFF) << 16
            | (hmac_digest[offset + 2] & 0xFF) << 8
            | (hmac_digest[offset + 3] & 0xFF)
        )

        return str(code % 1000000).zfill(6)

    def verify_totp_code(
        self, secret: str, code: str, timestamp: int | None = None
    ) -> bool:
        """Проверяет TOTP код"""
        if timestamp is None:
            timestamp = int(time.time())

        # Проверяем код в окне времени
        for i in range(-self.totp_window, self.totp_window + 1):
            expected_code = self.generate_totp_code(secret, timestamp + i * 30)
            if hmac.compare_digest(code, expected_code):
                return True

        return False

    def generate_qr_code(
        self, secret: str, user_email: str, issuer: str = "Clinic System"
    ) -> str:
        """Генерирует QR код для настройки 2FA"""
        totp_uri = (
            f"otpauth://totp/{issuer}:{user_email}?secret={secret}&issuer={issuer}"
        )

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Конвертируем в base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_str}"

    @staticmethod
    def _hash_backup_code(code: str) -> str:
        """Hash a backup code with SHA-256 for secure storage."""
        return hashlib.sha256(code.encode()).hexdigest()

    def generate_backup_codes(self, count: int = None) -> list[str]:
        """Генерирует backup коды"""
        if count is None:
            count = self.backup_codes_count

        codes = []
        for _ in range(count):
            # Генерируем 8-символьный код
            code = ''.join(
                secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(8)
            )
            codes.append(code)

        return codes

    def generate_recovery_token(self) -> str:
        """Генерирует токен восстановления"""
        return secrets.token_urlsafe(self.recovery_token_length)

    async def create_and_dispatch_recovery(
        self,
        db: Session,
        two_factor_auth: TwoFactorAuth,
        recovery_type: str,
        ip_address: str | None,
        user_agent: str | None,
        *,
        expected_auth_epoch: int,
        expected_jti: str | None,
        expected_exp: int | None,
        expected_patient_id: int | None,
    ) -> dict[str, Any]:
        """Создать одноразовый recovery-токен и доставить его по каналу.

        Порядок важен для консистентности: СНАЧАЛА доставка, ПОТОМ запись в
        БД — при сбое провайдера не остаётся «повисшего» токена, который
        пользователь так и не увидел. Получатель всегда берётся из
        НАСТРОЕННОГО в 2FA канала (two_factor_auth.recovery_email), а не из
        произвольного значения запроса — адрес подменить нельзя.

        Перед сохранением нового токена все прежние неотработанные токены
        этого аккаунта сжигаются (verified=True), поэтому в почте
        пользователя действует ровно один токен.
        """
        if recovery_type == "backup_code":
            return {
                "success": False,
                "error_code": "UNSUPPORTED_CHANNEL",
                "error": "Backup codes are verified directly via /2fa/verify",
            }
        if recovery_type != "email":
            return {
                "success": False,
                "error_code": "PHONE_CHANNEL_UNAVAILABLE",
                "error": "Восстановление по SMS пока недоступно, используйте email",
            }

        user_id = two_factor_auth.user_id
        two_factor_id = two_factor_auth.id
        recipient = two_factor_auth.recovery_email
        if not recipient:
            return {
                "success": False,
                "error_code": "CHANNEL_NOT_CONFIGURED",
                "error": "Recovery email не настроен для этого аккаунта",
            }

        # Rate limit по АККАУНТУ, а не по IP: весь персонал клиники
        # сидит за одним NAT — IP-бакет блокировал бы всех разом.
        # Учитываются и сгоревшие токены: каждый dispatch = письмо.
        hour_ago = datetime.now(UTC) - timedelta(hours=1)
        recent_count = (
            db.query(TwoFactorRecovery)
            .filter(
                TwoFactorRecovery.two_factor_auth_id == two_factor_auth.id,
                TwoFactorRecovery.created_at >= hour_ago,
            )
            .count()
        )
        if recent_count >= self.recovery_rate_limit_per_hour:
            return {
                "success": False,
                "error_code": "RATE_LIMITED",
                "error": "Превышен лимит запросов восстановления, попробуйте через час",
            }

        token = self.generate_recovery_token()
        expires_at = datetime.now(UTC) + timedelta(hours=self.recovery_expiry_hours)
        ttl_hours = self.recovery_expiry_hours

        # End the dependency's read transaction before network I/O. Keep only
        # immutable identifiers and the configured destination across the await.
        db.rollback()

        subject = "Восстановление двухфакторной аутентификации"
        html_content = f"""
        <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>Восстановление 2FA</h2>
        <p>Кто-то (надеемся, вы) запросил восстановление доступа к аккаунту клиники.</p>
        <p>Ваш одноразовый код восстановления:</p>
        <p style="font-family: monospace; font-size: 18px; font-weight: bold; padding: 12px; background: #f3f4f6; border-radius: 6px;">{token}</p>
        <p>Код действует <b>{ttl_hours} час</b> и может быть использован только один раз.</p>
        <p>Если вы не запрашивали восстановление — проигнорируйте это письмо и смените пароль.</p>
        </body></html>
        """
        text_content = (
            f"Восстановление 2FA.\n\n"
            f"Одноразовый код восстановления: {token}\n"
            f"Код действует {ttl_hours} час и может быть использован один раз.\n"
            f"Если вы не запрашивали восстановление — проигнорируйте письмо.\n"
        )

        send_ok, _send_message = await self.email_service.send_email_enhanced(
            to_email=recipient,
            subject=subject,
            html_content=html_content,
            text_content=text_content,
        )
        if not send_ok:
            logger.error(
                "2FA recovery email dispatch failed",
                extra={"has_recipient": True},
            )
            return {
                "success": False,
                "error_code": "EMAIL_SEND_FAILED",
                "error": "Не удалось отправить письмо восстановления, попробуйте позже",
            }

        # Revalidate after delivery under the same User -> Patient -> 2FA
        # ordering as the other sensitive operations. No SMTP call holds locks.
        def persist_recovery() -> dict[str, Any] | None:
            from app.core.roles import is_login_blocked_role

            try:
                user = (
                    db.query(User).filter(User.id == user_id)
                    .with_for_update(key_share=True).populate_existing().first()
                )
                if not user or not user.is_active or is_login_blocked_role(user.role):
                    raise BearerSessionInvalid("Bearer session unavailable")
                self._check_bearer_session(
                    db, user, expected_auth_epoch, expected_jti,
                    expected_exp, expected_patient_id,
                )
                current = (
                    db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id)
                    .with_for_update().populate_existing().first()
                )
                if (
                    not current or current.id != two_factor_id
                    or not current.totp_enabled or not current.totp_verified
                    or not current.recovery_enabled or current.recovery_email != recipient
                ):
                    db.rollback()
                    return {"success": False, "error_code": "CHANNEL_NOT_CONFIGURED",
                            "error": "Канал восстановления изменился, повторите запрос"}
                hour_ago = datetime.now(UTC) - timedelta(hours=1)
                recent = db.query(TwoFactorRecovery).filter(
                    TwoFactorRecovery.two_factor_auth_id == two_factor_id,
                    TwoFactorRecovery.created_at >= hour_ago,
                ).count()
                if recent >= self.recovery_rate_limit_per_hour:
                    db.rollback()
                    return {"success": False, "error_code": "RATE_LIMITED",
                            "error": "Превышен лимит запросов восстановления, попробуйте через час"}
                self._check_bearer_expiry(expected_auth_epoch, expected_exp)
                if datetime.now(UTC) >= expires_at:
                    db.rollback()
                    return {"success": False, "error_code": "EMAIL_SEND_FAILED",
                            "error": "Не удалось отправить письмо восстановления, попробуйте позже"}
                db.query(TwoFactorRecovery).filter(
                    TwoFactorRecovery.two_factor_auth_id == two_factor_id,
                    TwoFactorRecovery.verified.is_(False),
                ).update(
                    {"verified": True, "verified_at": datetime.now(UTC)},
                    synchronize_session=False,
                )
                db.add(TwoFactorRecovery(
                    two_factor_auth_id=two_factor_id, recovery_type="email",
                    recovery_value=recipient, recovery_token=token,
                    ip_address=ip_address, user_agent=user_agent,
                    verified=False, expires_at=expires_at,
                ))
                db.flush()
                self._check_bearer_expiry(expected_auth_epoch, expected_exp)
                if datetime.now(UTC) >= expires_at:
                    db.rollback()
                    return {"success": False, "error_code": "EMAIL_SEND_FAILED",
                            "error": "Не удалось отправить письмо восстановления, попробуйте позже"}
                db.commit()
                return None
            except Exception:
                db.rollback()
                raise

        from starlette.concurrency import run_in_threadpool

        failure = await run_in_threadpool(persist_recovery)
        if failure is not None:
            return failure
        logger.info("2FA recovery email sent", extra={"has_recipient": True})
        return {
            "success": True,
            "expires_at": expires_at,
            "message": f"Код восстановления отправлен на {mask_email(recipient)}",
        }

    def generate_device_fingerprint(self, user_agent: str, ip_address: str) -> str:
        """Генерирует отпечаток устройства"""
        data = f"{user_agent}:{ip_address}"
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def _lock_active_user_sessions(db: Session, user_id: int) -> None:
        """Lock sessions in deterministic order before 2FA or token writes."""
        (
            db.query(UserSession.id)
            .filter(UserSession.user_id == user_id, UserSession.revoked.is_(False))
            .order_by(UserSession.id)
            .with_for_update()
            .all()
        )

    @staticmethod
    def _check_bearer_session(
        db: Session, user: User, expected_auth_epoch: int | None,
        expected_jti: str | None = None, expected_exp: int | None = None,
        expected_patient_id: int | None = None,
    ) -> None:
        if expected_auth_epoch is None:
            return
        if user.auth_epoch != expected_auth_epoch or (
            expected_exp is not None and time.time() >= expected_exp
        ):
            raise BearerSessionInvalid("Bearer session unavailable")
        if expected_patient_id is not None:
            from app.core.user_token_claims import is_user_allowed_for_claims
            from app.models.patient import Patient

            if not is_user_allowed_for_claims(
                {"scope": "patient_portal"}, role=user.role,
                is_active=user.is_active, is_superuser=user.is_superuser,
            ):
                raise BearerSessionInvalid("Bearer session unavailable")
            patient = (
                db.query(Patient.id)
                .filter(
                    Patient.id == expected_patient_id,
                    Patient.user_id == user.id,
                    Patient.is_deleted.is_not(True),
                )
                .with_for_update()
                .first()
            )
            if patient is None:
                raise BearerSessionInvalid("Bearer session unavailable")
        from app.services.token_blacklist_service import token_blacklist_service

        if token_blacklist_service.is_token_blacklisted(
            db, expected_jti or "", user_id=user.id, auth_epoch=expected_auth_epoch
        ):
            raise BearerSessionInvalid("Bearer session unavailable")

    @staticmethod
    def _check_bearer_expiry(expected_auth_epoch: int | None, expected_exp: int | None) -> None:
        if expected_auth_epoch is not None and expected_exp is not None and time.time() >= expected_exp:
            raise BearerSessionInvalid("Bearer session unavailable")

    @staticmethod
    def _lock_enrollment_session(db: Session, user_id: int, token: str) -> UserSession:
        TwoFactorService._lock_active_user_sessions(db, user_id)
        session = (
            db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.refresh_token == token,
                UserSession.session_kind == "2fa_enrollment",
                UserSession.revoked.is_(False),
                UserSession.expires_at > datetime.now(UTC),
            )
            .with_for_update()
            .populate_existing()
            .first()
        )
        if session is None:
            raise EnrollmentSessionInvalid("Enrollment session unavailable")
        return session

    @staticmethod
    def _check_enrollment_not_expired(session: UserSession | None) -> None:
        if session is None:
            return
        expires = session.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if session.revoked or datetime.now(UTC) >= expires:
            raise EnrollmentSessionInvalid("Enrollment session unavailable")

    @staticmethod
    def _lock_pending_session(db: Session, user_id: int, token: str) -> UserSession:
        from app.services.two_factor_patient_pending import pending_session_kind_filter

        TwoFactorService._lock_active_user_sessions(db, user_id)
        session = (
            db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.refresh_token == token,
                UserSession.revoked.is_(False),
                UserSession.expires_at > datetime.now(UTC),
                pending_session_kind_filter(UserSession.session_kind),
            )
            .with_for_update()
            .populate_existing()
            .first()
        )
        if session is None:
            raise PendingSessionInvalid("Pending 2FA session unavailable")
        return session

    @staticmethod
    def _check_pending_not_expired(session: UserSession | None) -> None:
        if session is None:
            return
        expires = session.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if session.revoked or datetime.now(UTC) >= expires:
            raise PendingSessionInvalid("Pending 2FA session unavailable")

    def setup_two_factor_auth(
        self,
        db: Session,
        user_id: int,
        recovery_email: str | None = None,
        recovery_phone: str | None = None,
        enrollment_token: str | None = None,
        expected_auth_epoch: int | None = None,
        expected_jti: str | None = None,
        expected_exp: int | None = None,
        expected_patient_id: int | None = None,
    ) -> dict[str, Any]:
        """Настраивает 2FA для пользователя"""
        try:
            # Получаем пользователя
            # Serialize setup with disable and other sensitive operations.
            # NO KEY UPDATE permits FK KEY SHARE from trusted-session inserts.
            user = (
                db.query(User).filter(User.id == user_id)
                .with_for_update(key_share=True).populate_existing().first()
            )
            if not user or not user.is_active:
                if enrollment_token is not None:
                    raise EnrollmentSessionInvalid("Enrollment session unavailable")
                if expected_auth_epoch is not None:
                    raise BearerSessionInvalid("Bearer session unavailable")
                raise ValueError("User not found")
            self._check_bearer_session(db, user, expected_auth_epoch, expected_jti, expected_exp, expected_patient_id)

            enrollment = (
                self._lock_enrollment_session(db, user_id, enrollment_token)
                if enrollment_token is not None else None
            )

            # Проверяем, есть ли уже 2FA
            existing_2fa = (
                db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id)
                .with_for_update().populate_existing().first()
            )

            if existing_2fa and existing_2fa.totp_enabled:
                raise TwoFactorAlreadyEnabled("2FA already enabled for this user")

            # Генерируем секрет
            secret = self.generate_totp_secret()

            # Создаем или обновляем запись 2FA
            if existing_2fa:
                existing_2fa.totp_secret = secret
                existing_2fa.totp_enabled = False
                existing_2fa.totp_verified = False
                existing_2fa.last_sensitive_totp_step = None
                existing_2fa.recovery_email = recovery_email
                existing_2fa.recovery_phone = recovery_phone
                existing_2fa.recovery_enabled = bool(recovery_email or recovery_phone)
                two_factor_auth = existing_2fa
            else:
                two_factor_auth = TwoFactorAuth(
                    user_id=user_id,
                    totp_secret=secret,
                    totp_enabled=False,
                    totp_verified=False,
                    recovery_email=recovery_email,
                    recovery_phone=recovery_phone,
                    recovery_enabled=bool(recovery_email or recovery_phone),
                )
                db.add(two_factor_auth)

            db.flush()
            logger.info(
                "[FIX:2FA] Creating setup artifacts for user_id=%s two_factor_auth_id=%s",
                user_id,
                two_factor_auth.id,
            )

            # Удаляем старые backup/recovery артефакты при повторной настройке.
            db.query(TwoFactorBackupCode).filter(
                TwoFactorBackupCode.two_factor_auth_id == two_factor_auth.id
            ).delete()
            db.query(TwoFactorRecovery).filter(
                TwoFactorRecovery.two_factor_auth_id == two_factor_auth.id
            ).delete()

            # Генерируем backup коды
            backup_codes = self.generate_backup_codes()

            # Сохраняем backup коды
            for code in backup_codes:
                backup_code = TwoFactorBackupCode(
                    two_factor_auth_id=two_factor_auth.id,
                    code=self._hash_backup_code(code),
                    used=False
                )
                db.add(backup_code)

            two_factor_auth.backup_codes_generated = True
            two_factor_auth.backup_codes_count = len(backup_codes)

            recovery_token = None
            recovery_expires = None
            if recovery_email or recovery_phone:
                recovery_token = self.generate_recovery_token()
                recovery_expires = datetime.now(UTC) + timedelta(
                    hours=self.recovery_expiry_hours
                )

                recovery = TwoFactorRecovery(
                    two_factor_auth_id=two_factor_auth.id,
                    recovery_type="email" if recovery_email else "phone",
                    recovery_value=recovery_email or recovery_phone,
                    recovery_token=recovery_token,
                    expires_at=recovery_expires,
                )
                db.add(recovery)
            else:
                logger.info(
                    "[FIX:2FA] No recovery contact provided for user_id=%s; skipping recovery token",
                    user_id,
                )

            self._check_bearer_expiry(expected_auth_epoch, expected_exp)
            self._check_enrollment_not_expired(enrollment)
            db.commit()

            # Генерируем QR код
            qr_code_url = self.generate_qr_code(secret, user.email or user.username)

            return {
                "qr_code_url": qr_code_url,
                "secret_key": secret,
                "backup_codes": backup_codes,
                "recovery_token": recovery_token,
                "expires_at": recovery_expires.isoformat() if recovery_expires else None,
            }

        except Exception as e:
            db.rollback()
            logger.error("Error setting up 2FA: %s", type(e).__name__)
            raise

    def verify_totp_setup(
        self, db: Session, user_id: int, totp_code: str, *,
        enrollment_token: str | None = None, commit: bool = True,
        expected_auth_epoch: int | None = None,
        expected_jti: str | None = None, expected_exp: int | None = None,
        expected_patient_id: int | None = None,
    ) -> bool:
        """Верифицирует настройку TOTP"""
        try:
            if enrollment_token is not None and commit:
                raise ValueError("Enrollment verification requires an atomic token exchange")
            user = (
                db.query(User).filter(User.id == user_id)
                .with_for_update(key_share=True).populate_existing().first()
            )
            if not user or not user.is_active:
                if enrollment_token is not None:
                    raise EnrollmentSessionInvalid("Enrollment session unavailable")
                if expected_auth_epoch is not None:
                    raise BearerSessionInvalid("Bearer session unavailable")
                db.rollback()
                return False
            self._check_bearer_session(db, user, expected_auth_epoch, expected_jti, expected_exp, expected_patient_id)
            enrollment = (
                self._lock_enrollment_session(db, user_id, enrollment_token)
                if enrollment_token is not None else None
            )
            two_factor_auth = (
                db.query(TwoFactorAuth)
                .filter(TwoFactorAuth.user_id == user_id)
                .with_for_update()
                .populate_existing()
                .first()
            )
            if not two_factor_auth:
                db.rollback()
                return False
            if two_factor_auth.totp_enabled or not two_factor_auth.totp_secret:
                db.rollback()
                return False

            # Проверяем код
            if self.verify_totp_code(two_factor_auth.totp_secret, totp_code):
                two_factor_auth.totp_verified = True
                two_factor_auth.totp_enabled = True
                two_factor_auth.backup_codes_generated = True
                two_factor_auth.backup_codes_count = self.backup_codes_count
                two_factor_auth.last_used = datetime.now(UTC)

                self._check_bearer_expiry(expected_auth_epoch, expected_exp)
                self._check_enrollment_not_expired(enrollment)
                if commit:
                    db.commit()
                else:
                    # SessionLocal disables autoflush; the token exchange
                    # rechecks verified state in this same transaction.
                    db.flush()
                return True

            db.rollback()
            return False

        except (EnrollmentSessionInvalid, BearerSessionInvalid):
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error("Error verifying TOTP setup: %s", type(e).__name__)
            return False

    def verify_two_factor(
        self,
        db: Session,
        user_id: int,
        totp_code: str | None = None,
        backup_code: str | None = None,
        recovery_token: str | None = None,
        device_fingerprint: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        *,
        pending_token: str | None = None,
        commit: bool = True,
        expected_auth_epoch: int | None = None,
        expected_jti: str | None = None,
        expected_exp: int | None = None,
        expected_patient_id: int | None = None,
    ) -> tuple[bool, str, str | None]:
        """Верифицирует 2FA код"""
        try:
            pending_session = None
            user = (
                db.query(User).filter(User.id == user_id)
                .with_for_update(key_share=True).populate_existing().first()
            )
            if not user or not user.is_active:
                if pending_token is not None:
                    raise PendingSessionInvalid("Pending 2FA session unavailable")
                if expected_auth_epoch is not None:
                    raise BearerSessionInvalid("Bearer session unavailable")
                db.rollback()
                return False, "2FA not enabled", None
            self._check_bearer_session(db, user, expected_auth_epoch, expected_jti, expected_exp, expected_patient_id)
            if pending_token is not None:
                if commit:
                    raise ValueError("Pending verification requires atomic exchange")
                pending_session = self._lock_pending_session(db, user_id, pending_token)
                from app.services.two_factor_patient_pending import (
                    is_patient_pending_kind,
                )

                if is_patient_pending_kind(pending_session.session_kind):
                    if not (totp_code or backup_code):
                        db.rollback()
                        return False, "TOTP or backup code required", None
                    # Patient SMS/passkey sessions are access-only: do not
                    # mint an additional persistent trusted-device credential.
                    device_fingerprint = None
            elif not commit:
                # Commit-free callers may mint a login after verification.
                # Acquire session locks before 2FA in the shared global order.
                self._lock_active_user_sessions(db, user_id)
            # Serialize verification decisions on the per-user 2FA record.
            # Without this lock, concurrent failures can read the same counter
            # and overwrite one another, bypassing the account-level cap.
            two_factor_auth = (
                db.query(TwoFactorAuth)
                .filter(
                    TwoFactorAuth.user_id == user_id,
                    TwoFactorAuth.totp_enabled.is_(True),
                )
                .with_for_update()
                .populate_existing()
                .first()
            )
            self._check_pending_not_expired(pending_session)
            if not two_factor_auth or ((pending_session is not None or not commit) and not two_factor_auth.totp_verified):
                db.rollback()
                return False, "2FA not enabled", None

            # TWOFACTOR-BE-001 (#4063): service-side lockout gate — checked
            # BEFORE any code verification. After max_verify_attempts
            # consecutive failures even a correct code is rejected until
            # locked_until passes; the lock self-clears on the next verify.
            now = datetime.now(UTC)
            locked_until = two_factor_auth.locked_until
            if locked_until is not None:
                if locked_until.tzinfo is None:
                    locked_until = locked_until.replace(tzinfo=UTC)
                if now < locked_until:
                    self._check_bearer_expiry(expected_auth_epoch, expected_exp)
                    remaining_minutes = max(
                        1, int((locked_until - now).total_seconds() // 60) + 1
                    )
                    # Release the row lock before returning; the service's
                    # callers may reuse this session beyond this request.
                    db.commit()
                    return (
                        False,
                        "2FA temporarily locked after repeated failed "
                        f"attempts. Try again in ~{remaining_minutes} minute(s).",
                        None,
                    )
                two_factor_auth.locked_until = None
                two_factor_auth.failed_attempts = 0

            _method_used = None
            success = False

            # Проверяем TOTP код
            if totp_code and two_factor_auth.totp_secret:
                if self.verify_totp_code(two_factor_auth.totp_secret, totp_code):
                    success = True
                    _method_used = "totp"

            # Проверяем backup код
            elif backup_code:
                backup_code_hash = self._hash_backup_code(backup_code)
                backup_code_obj = (
                    db.query(TwoFactorBackupCode)
                    .filter(
                        and_(
                            TwoFactorBackupCode.two_factor_auth_id
                            == two_factor_auth.id,
                            TwoFactorBackupCode.code == backup_code_hash,
                            TwoFactorBackupCode.used == False,
                        )
                    )
                    .first()
                )

                if backup_code_obj:
                    backup_code_obj.used = True
                    backup_code_obj.used_at = datetime.now(UTC)
                    success = True
                    _method_used = "backup_code"

            # Проверяем токен восстановления
            elif recovery_token:
                recovery = (
                    db.query(TwoFactorRecovery)
                    .filter(
                        and_(
                            TwoFactorRecovery.two_factor_auth_id == two_factor_auth.id,
                            TwoFactorRecovery.recovery_token == recovery_token,
                            TwoFactorRecovery.verified == False,
                            TwoFactorRecovery.expires_at > datetime.now(UTC),
                        )
                    )
                    .first()
                )

                if recovery:
                    recovery.verified = True
                    recovery.verified_at = datetime.now(UTC)
                    success = True
                    _method_used = "recovery"

            if success:
                self._check_bearer_expiry(expected_auth_epoch, expected_exp)
                self._check_pending_not_expired(pending_session)
                # Обновляем время последнего использования
                two_factor_auth.last_used = datetime.now(UTC)

                # TWOFACTOR-BE-001 (#4063): a successful verification resets
                # the brute-force counter and clears any lock state.
                two_factor_auth.failed_attempts = 0
                two_factor_auth.locked_until = None

                # Создаем сессию если нужно
                session_token = None
                if device_fingerprint:
                    session_token = self.create_trusted_session(
                        db, user_id, device_fingerprint, ip_address, user_agent,
                        commit=commit,
                    )

                self._check_bearer_expiry(expected_auth_epoch, expected_exp)
                self._check_pending_not_expired(pending_session)
                if commit:
                    db.commit()
                else:
                    db.flush()
                return True, "Verification successful", session_token

            # TWOFACTOR-BE-001 (#4063): persist the failed attempt. After
            # max_verify_attempts consecutive failures, lock the second
            # factor for verify_lockout_minutes — even a correct code is
            # rejected while the lock is active (gate above).
            self._check_bearer_expiry(expected_auth_epoch, expected_exp)
            self._check_pending_not_expired(pending_session)
            two_factor_auth.failed_attempts = (
                two_factor_auth.failed_attempts or 0
            ) + 1
            if two_factor_auth.failed_attempts >= self.max_verify_attempts:
                two_factor_auth.locked_until = datetime.now(UTC) + timedelta(
                    minutes=self.verify_lockout_minutes
                )
                db.commit()
                return False, (
                    "Invalid verification code. 2FA temporarily locked after "
                    "repeated failed attempts."
                ), None
            db.commit()
            return False, "Invalid verification code", None

        except (PendingSessionInvalid, BearerSessionInvalid):
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error("Error verifying 2FA: %s", type(e).__name__)
            return False, "Verification temporarily unavailable", None

    def create_trusted_session(
        self,
        db: Session,
        user_id: int,
        device_fingerprint: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        device_name: str | None = None,
        *,
        commit: bool = True,
    ) -> str:
        """Создает доверенную сессию"""
        try:
            # Генерируем токен сессии
            session_token = secrets.token_urlsafe(32)
            expires_at = datetime.now(UTC) + timedelta(hours=self.session_expiry_hours)

            # Создаем сессию
            session = TwoFactorSession(
                user_id=user_id,
                session_token=session_token,
                device_fingerprint=device_fingerprint,
                two_factor_verified=True,
                two_factor_method="totp",
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent,
                device_name=device_name,
            )
            db.add(session)

            # Создаем или обновляем устройство
            device = (
                db.query(TwoFactorDevice)
                .filter(
                    TwoFactorDevice.device_fingerprint == device_fingerprint,
                    TwoFactorDevice.user_id == user_id,
                )
                .with_for_update()
                .first()
            )
            fingerprint_owner = (
                db.query(TwoFactorDevice.user_id)
                .filter(TwoFactorDevice.device_fingerprint == device_fingerprint)
                .first()
            )
            if fingerprint_owner and fingerprint_owner[0] != user_id:
                raise ValueError("Device fingerprint already belongs to another user")

            if device:
                device.last_used = datetime.now(UTC)
                device.trusted = True
                device.active = True
                device.trusted_until = datetime.now(UTC) + timedelta(days=30)
            else:
                device = TwoFactorDevice(
                    user_id=user_id,
                    device_name=device_name or "Unknown Device",
                    device_type="desktop",  # Можно определить по user_agent
                    device_fingerprint=device_fingerprint,
                    trusted=True,
                    active=True,
                    trusted_until=datetime.now(UTC) + timedelta(days=30),
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                db.add(device)

            if commit:
                db.commit()
            else:
                db.flush()
            return session_token

        except Exception as e:
            db.rollback()
            logger.warning(
                "2FA trusted session creation failed error_type=%s",
                type(e).__name__,
            )
            raise

    @staticmethod
    def _is_six_ascii_digits(code: str) -> bool:
        return len(code) == 6 and all("0" <= character <= "9" for character in code)

    @staticmethod
    def _hash_verification_code(user_id: int, method: str, code: str) -> str:
        """Keyed digest prevents offline guessing if the code table is exposed."""
        message = f"2fa-code:v1:{user_id}:{method}:{code}".encode()
        return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()

    @staticmethod
    def _hash_verification_contact(user_id: int, method: str, contact: str) -> str:
        """Bind a pending code to its configured destination without storing PII."""
        normalized = contact.strip().lower()
        message = f"2fa-contact:v1:{user_id}:{method}:{normalized}".encode()
        return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()

    def get_recovery_contact(
        self, db: Session, user_id: int, method: str
    ) -> str | None:
        """Return only the contact already configured for this account/method."""
        if method not in {"sms", "email"}:
            return None
        two_factor_auth = (
            db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id).first()
        )
        if not two_factor_auth or not two_factor_auth.recovery_enabled:
            return None
        contact = (
            two_factor_auth.recovery_phone
            if method == "sms"
            else two_factor_auth.recovery_email
        )
        return contact.strip() if contact and contact.strip() else None

    def save_verification_code(
        self,
        db: Session,
        user_id: int,
        method: str,
        code: str,
        contact: str,
        expires_at: datetime,
    ) -> None:
        """Persist a single-use code as a keyed hash after successful delivery."""
        if method not in {"sms", "email"} or not self._is_six_ascii_digits(code):
            raise ValueError("Invalid verification code")
        now = datetime.now(UTC)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        configured_contact = self.get_recovery_contact(db, user_id, method)
        if (
            not configured_contact
            or not hmac.compare_digest(
                self._hash_verification_contact(user_id, method, configured_contact),
                self._hash_verification_contact(user_id, method, contact),
            )
        ):
            raise ValueError("Verification contact changed before code was stored")
        if expires_at <= now or expires_at > now + timedelta(minutes=5, seconds=1):
            raise ValueError("Verification code expiry must be within five minutes")

        record = (
            db.query(TwoFactorVerificationCode)
            .filter(
                TwoFactorVerificationCode.user_id == user_id,
                TwoFactorVerificationCode.method == method,
            )
            .with_for_update()
            .first()
        )
        values = {
            "code_hash": self._hash_verification_code(user_id, method, code),
            "contact_hash": self._hash_verification_contact(
                user_id, method, contact
            ),
            "expires_at": expires_at,
            "attempts_remaining": 5,
            "created_at": now,
            "consumed_at": None,
            "verified_at": None,
        }
        if record:
            for key, value in values.items():
                setattr(record, key, value)
        else:
            db.add(
                TwoFactorVerificationCode(
                    user_id=user_id, method=method, **values
                )
            )
        db.commit()

    def verify_code(
        self, db: Session, user_id: int, method: str, code: str
    ) -> bool:
        """Consume a valid current code once, under a row lock and attempt cap."""
        if method not in {"sms", "email"} or not self._is_six_ascii_digits(code):
            return False
        try:
            record = (
                db.query(TwoFactorVerificationCode)
                .filter(
                    TwoFactorVerificationCode.user_id == user_id,
                    TwoFactorVerificationCode.method == method,
                )
                .with_for_update()
                .first()
            )
            now = datetime.now(UTC)
            contact = self.get_recovery_contact(db, user_id, method)
            if not record or not contact:
                return False
            expires_at = record.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if (
                record.consumed_at is not None
                or expires_at <= now
                or record.attempts_remaining <= 0
                or not hmac.compare_digest(
                    record.contact_hash,
                    self._hash_verification_contact(user_id, method, contact),
                )
            ):
                return False

            expected_hash = self._hash_verification_code(user_id, method, code)
            if not hmac.compare_digest(record.code_hash, expected_hash):
                record.attempts_remaining -= 1
                if record.attempts_remaining == 0:
                    record.consumed_at = now
                db.commit()
                return False

            record.consumed_at = now
            record.verified_at = now
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise

    @staticmethod
    def _as_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value

    def get_verification_status(
        self, db: Session, user_id: int, method: str
    ) -> dict[str, Any]:
        """Return non-sensitive state for the authenticated settings UI."""
        now = datetime.now(UTC)
        record = (
            db.query(TwoFactorVerificationCode)
            .filter(
                TwoFactorVerificationCode.user_id == user_id,
                TwoFactorVerificationCode.method == method,
            )
            .first()
        )
        contact = self.get_recovery_contact(db, user_id, method)
        created_at = self._as_utc(record.created_at) if record else None
        expires_at = self._as_utc(record.expires_at) if record else None
        contact_matches = bool(
            record
            and contact
            and hmac.compare_digest(
                record.contact_hash,
                self._hash_verification_contact(user_id, method, contact),
            )
        )
        active = bool(
            record
            and contact_matches
            and record.consumed_at is None
            and record.attempts_remaining > 0
            and expires_at
            and expires_at > now
        )
        resend_available_at = created_at + timedelta(seconds=60) if created_at else None
        return {
            "method": method,
            "configured": bool(contact),
            "active": active,
            "verified": bool(record and record.verified_at and contact_matches),
            "expires_at": expires_at,
            "attempts_remaining": record.attempts_remaining if record else 0,
            "resend_available_at": resend_available_at,
            "can_resend": self.can_resend_code(db, user_id, method),
        }

    def can_resend_code(self, db: Session, user_id: int, method: str) -> bool:
        if method not in {"sms", "email"}:
            return False
        contact = self.get_recovery_contact(db, user_id, method)
        if not contact:
            return False
        record = (
            db.query(TwoFactorVerificationCode)
            .filter(
                TwoFactorVerificationCode.user_id == user_id,
                TwoFactorVerificationCode.method == method,
            )
            .first()
        )
        if not record:
            return False
        current_contact_hash = self._hash_verification_contact(
            user_id, method, contact
        )
        if not hmac.compare_digest(record.contact_hash, current_contact_hash):
            return True
        if record.verified_at is not None:
            return False
        return self.can_send_code(db, user_id, method)

    def can_send_code(self, db: Session, user_id: int, method: str) -> bool:
        """Apply an account-scoped 60-second cooldown to every code dispatch."""
        if method not in {"sms", "email"}:
            return False
        contact = self.get_recovery_contact(db, user_id, method)
        if not contact:
            return False
        record = (
            db.query(TwoFactorVerificationCode)
            .filter(
                TwoFactorVerificationCode.user_id == user_id,
                TwoFactorVerificationCode.method == method,
            )
            .first()
        )
        if not record:
            return True
        if not hmac.compare_digest(
            record.contact_hash,
            self._hash_verification_contact(user_id, method, contact),
        ):
            return True
        created_at = self._as_utc(record.created_at)
        return bool(
            created_at is None
            or created_at + timedelta(seconds=60) <= datetime.now(UTC)
        )

    def add_trusted_device(
        self,
        db: Session,
        user_id: int,
        name: str | None,
        device_fingerprint: str,
        user_agent: str,
        ip_address: str,
    ) -> TwoFactorDevice:
        """Register an owner-scoped device with a maximum 30-day trust grant."""
        if not 32 <= len(device_fingerprint) <= 64:
            raise ValueError("Invalid device fingerprint")
        now = datetime.now(UTC)
        device = (
            db.query(TwoFactorDevice)
            .filter(TwoFactorDevice.device_fingerprint == device_fingerprint)
            .with_for_update()
            .first()
        )
        if device and device.user_id != user_id:
            raise ValueError("Device fingerprint already belongs to another user")
        device_type = (
            "tablet"
            if "tablet" in user_agent.lower()
            else "mobile"
            if "mobile" in user_agent.lower() or "android" in user_agent.lower()
            else "desktop"
        )
        if device:
            device.device_name = name or device.device_name
            device.device_type = device_type
            device.user_agent = user_agent
            device.ip_address = ip_address
            device.active = True
            device.trusted = True
            device.trusted_until = now + timedelta(days=30)
            device.last_used = now
        else:
            device = TwoFactorDevice(
                user_id=user_id,
                device_name=name or "Unknown Device",
                device_type=device_type,
                device_fingerprint=device_fingerprint,
                trusted=True,
                active=True,
                trusted_until=now + timedelta(days=30),
                ip_address=ip_address,
                user_agent=user_agent,
            )
            db.add(device)
        db.commit()
        db.refresh(device)
        return device

    def trust_device(
        self,
        db: Session,
        user_id: int,
        device_id: int,
        trust_until: datetime,
    ) -> bool:
        """Grant time-bounded trust to a device owned by the current user."""
        from app.crud.two_factor_auth import two_factor_device

        now = datetime.now(UTC)
        if trust_until.tzinfo is None:
            trust_until = trust_until.replace(tzinfo=UTC)
        if trust_until <= now or trust_until > now + timedelta(days=30):
            return False
        return two_factor_device.trust_device(
            db, device_id, user_id, trust_until
        )

    def _authorize_sensitive_operation(
        self,
        db: Session,
        user_id: int,
        password: str,
        totp_code: str | None,
        backup_code: str | None,
        expected_auth_epoch: int | None = None,
        expected_jti: str | None = None,
        expected_exp: int | None = None,
        expected_patient_id: int | None = None,
    ) -> TwoFactorAuth | None:
        """Authenticate under locks; success retains them for the caller's commit.

        Failed attempts commit the per-account reauthentication lockout under
        the same 2FA row lock. A backup code or TOTP timestep is consumed only
        when *both* factors are correct, and only in the caller's transaction.
        """
        user = (
            db.query(User).filter(User.id == user_id)
            .with_for_update(key_share=True).populate_existing().first()
        )
        if not user or not user.is_active:
            if expected_auth_epoch is not None:
                raise BearerSessionInvalid("Bearer session unavailable")
            db.rollback()
            return None
        self._check_bearer_session(db, user, expected_auth_epoch, expected_jti, expected_exp, expected_patient_id)
        two_factor_auth = (
            db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id)
            .with_for_update().populate_existing().first()
        )
        if (
            not two_factor_auth
            or not two_factor_auth.totp_enabled
            or not two_factor_auth.totp_verified
        ):
            db.rollback()
            return None
        now = datetime.now(UTC)
        for lock_field, count_field in (
            ("locked_until", "failed_attempts"),
            ("sensitive_locked_until", "sensitive_failed_attempts"),
        ):
            locked_until = getattr(two_factor_auth, lock_field)
            if locked_until is not None:
                if locked_until.tzinfo is None:
                    locked_until = locked_until.replace(tzinfo=UTC)
                if now < locked_until:
                    db.rollback()
                    return None
                setattr(two_factor_auth, lock_field, None)
                setattr(two_factor_auth, count_field, 0)

        password_ok = verify_password(password, user.hashed_password)
        backup = None
        matched_step = None
        if (
            totp_code
            and totp_code.isascii()
            and totp_code.isdigit()
            and two_factor_auth.totp_secret
        ):
            timestamp = int(time.time())
            # Pick the maximum matching step so a rare six-digit collision
            # across adjacent windows cannot permit reuse of the same code.
            matching_steps = [
                (timestamp + offset * 30) // 30
                for offset in range(-self.totp_window, self.totp_window + 1)
                if hmac.compare_digest(
                    totp_code,
                    self.generate_totp_code(two_factor_auth.totp_secret, timestamp + offset * 30),
                )
            ]
            if matching_steps:
                matched_step = max(matching_steps)
                last_step = two_factor_auth.last_sensitive_totp_step
                if last_step is not None and matched_step <= last_step:
                    matched_step = None
        elif not totp_code and backup_code:
            backup = (
                db.query(TwoFactorBackupCode)
                .filter(
                    TwoFactorBackupCode.two_factor_auth_id == two_factor_auth.id,
                    TwoFactorBackupCode.code == self._hash_backup_code(backup_code),
                    TwoFactorBackupCode.used.is_(False),
                )
                .first()
            )

        self._check_bearer_expiry(expected_auth_epoch, expected_exp)
        factor_ok = matched_step is not None or backup is not None
        if not password_ok or not factor_ok:
            # A normal second-factor verification can reset the login counter,
            # so sensitive reauthentication keeps a separate account counter.
            two_factor_auth.sensitive_failed_attempts = (
                two_factor_auth.sensitive_failed_attempts or 0
            ) + 1
            if two_factor_auth.sensitive_failed_attempts >= self.max_verify_attempts:
                two_factor_auth.sensitive_locked_until = now + timedelta(
                    minutes=self.verify_lockout_minutes
                )
            if not factor_ok:
                two_factor_auth.failed_attempts = (two_factor_auth.failed_attempts or 0) + 1
                if two_factor_auth.failed_attempts >= self.max_verify_attempts:
                    two_factor_auth.locked_until = now + timedelta(
                        minutes=self.verify_lockout_minutes
                    )
            db.commit()
            return None

        if backup is not None:
            backup.used = True
            backup.used_at = now
        if matched_step is not None:
            two_factor_auth.last_sensitive_totp_step = matched_step
        two_factor_auth.last_used = now
        two_factor_auth.failed_attempts = 0
        two_factor_auth.locked_until = None
        two_factor_auth.sensitive_failed_attempts = 0
        two_factor_auth.sensitive_locked_until = None
        return two_factor_auth

    def disable_two_factor_auth(
        self,
        db: Session,
        user_id: int,
        password: str,
        totp_code: str | None = None,
        backup_code: str | None = None,
        *,
        expected_auth_epoch: int | None = None,
        expected_jti: str | None = None,
        expected_exp: int | None = None,
        expected_patient_id: int | None = None,
    ) -> bool:
        """Отключает 2FA для пользователя.

        SECURITY (AUTH-REAUDIT-28): требуется ОБА фактора — пароль И валидный
        2FA-код (TOTP или backup). Раньше 2FA-код был опциональным, что
        позволяло атакующему с украденным паролем (фишинг) отключить 2FA
        без второго фактора.
        """
        try:
            two_factor_auth = self._authorize_sensitive_operation(
                db, user_id, password, totp_code, backup_code,
                expected_auth_epoch, expected_jti, expected_exp, expected_patient_id,
            )
            if not two_factor_auth:
                return False

            # Удаляем все данные 2FA
            if two_factor_auth:
                # Удаляем backup коды
                db.query(TwoFactorBackupCode).filter(
                    TwoFactorBackupCode.two_factor_auth_id == two_factor_auth.id
                ).delete()

                # Удаляем попытки восстановления
                db.query(TwoFactorRecovery).filter(
                    TwoFactorRecovery.two_factor_auth_id == two_factor_auth.id
                ).delete()

                # Удаляем сессии
                db.query(TwoFactorSession).filter(
                    TwoFactorSession.user_id == user_id
                ).delete()

                # Удаляем устройства
                db.query(TwoFactorDevice).filter(
                    TwoFactorDevice.user_id == user_id
                ).delete()

                # Удаляем основную запись
                db.delete(two_factor_auth)

            self._check_bearer_expiry(expected_auth_epoch, expected_exp)
            db.commit()
            return True

        except BearerSessionInvalid:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error("Error disabling 2FA: %s", type(e).__name__)
            return False

    def get_two_factor_status(self, db: Session, user_id: int) -> dict[str, Any]:
        """Получает статус 2FA для пользователя"""
        try:
            two_factor_auth = (
                db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id).first()
            )

            if not two_factor_auth:
                return {
                    "enabled": False,
                    "totp_enabled": False,
                    "totp_verified": False,
                    "backup_codes_generated": False,
                    "backup_codes_count": 0,
                    "recovery_enabled": False,
                    "recovery_email": None,
                    "recovery_phone": None,
                    "trusted_devices_count": 0,
                    "last_used": None,
                }

            # Подсчитываем оставшиеся backup коды
            remaining_backup_codes = (
                db.query(TwoFactorBackupCode)
                .filter(
                    and_(
                        TwoFactorBackupCode.two_factor_auth_id == two_factor_auth.id,
                        TwoFactorBackupCode.used == False,
                    )
                )
                .count()
            )

            # Подсчитываем доверенные устройства
            trusted_devices = (
                db.query(TwoFactorDevice)
                .filter(
                    and_(
                        TwoFactorDevice.user_id == user_id,
                        TwoFactorDevice.trusted == True,
                        TwoFactorDevice.active == True,
                        TwoFactorDevice.trusted_until > datetime.now(UTC),
                    )
                )
                .count()
            )

            return {
                "enabled": two_factor_auth.totp_enabled,
                "totp_enabled": two_factor_auth.totp_enabled,
                "totp_verified": two_factor_auth.totp_verified,
                "backup_codes_generated": two_factor_auth.backup_codes_generated,
                "backup_codes_count": remaining_backup_codes,
                "recovery_enabled": two_factor_auth.recovery_enabled,
                "recovery_email": two_factor_auth.recovery_email,
                "recovery_phone": two_factor_auth.recovery_phone,
                "trusted_devices_count": trusted_devices,
                "last_used": two_factor_auth.last_used,
            }

        except Exception as e:
            logger.error(f"Error getting 2FA status: {e}")
            return {
                "enabled": False,
                "totp_enabled": False,
                "totp_verified": False,
                "backup_codes_generated": False,
                "backup_codes_count": 0,
                "recovery_enabled": False,
                "recovery_email": None,
                "recovery_phone": None,
                "trusted_devices_count": 0,
                "last_used": None,
            }

    def get_security_logs(
        self, db: Session, user_id: int, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Возвращает журнал действий 2FA для UI."""
        logs: list[dict[str, Any]] = []

        sessions = (
            db.query(TwoFactorSession)
            .filter(TwoFactorSession.user_id == user_id)
            .order_by(TwoFactorSession.created_at.desc())
            .all()
        )
        for session in sessions:
            logs.append(
                {
                    "type": "success" if session.two_factor_verified else "warning",
                    "action": "Верификация 2FA",
                    "description": (
                        f"Вход подтвержден методом {session.two_factor_method or 'unknown'}"
                    ),
                    "timestamp": session.created_at,
                    "ip_address": session.ip_address or "unknown",
                    "user_agent": session.user_agent or "unknown",
                }
            )

        two_factor_auth = (
            db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id).first()
        )
        if two_factor_auth:
            recovery_attempts = (
                db.query(TwoFactorRecovery)
                .filter(TwoFactorRecovery.two_factor_auth_id == two_factor_auth.id)
                .order_by(TwoFactorRecovery.created_at.desc())
                .all()
            )
            for recovery in recovery_attempts:
                logs.append(
                    {
                        "type": "success" if recovery.verified else "warning",
                        "action": "Восстановление 2FA",
                        "description": (
                            f"Запрос через {recovery.recovery_type}"
                            if recovery.verified
                            else f"Ожидает подтверждения через {recovery.recovery_type}"
                        ),
                        "timestamp": recovery.created_at,
                        "ip_address": recovery.ip_address or "unknown",
                        "user_agent": recovery.user_agent or "unknown",
                    }
                )

        logs.sort(
            key=lambda item: item["timestamp"] or datetime.min,
            reverse=True,
        )
        return logs[offset : offset + limit]

    def get_recovery_methods(self, db: Session, user_id: int) -> list[dict[str, Any]]:
        """Возвращает методы восстановления 2FA для UI."""
        two_factor_auth = (
            db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id).first()
        )
        if not two_factor_auth:
            return []

        methods: list[dict[str, Any]] = []
        if two_factor_auth.recovery_email:
            methods.append(
                {
                    "type": "email",
                    "label": "Email",
                    "value": two_factor_auth.recovery_email,
                    "verified": bool(two_factor_auth.recovery_enabled),
                }
            )
        if two_factor_auth.recovery_phone:
            methods.append(
                {
                    "type": "phone",
                    "label": "Телефон",
                    "value": two_factor_auth.recovery_phone,
                    "verified": bool(two_factor_auth.recovery_enabled),
                }
            )
        return methods

    def get_backup_codes_count(
        self, db: Session, user_id: int, *, expected_auth_epoch: int,
        expected_jti: str | None = None, expected_exp: int | None = None,
        expected_patient_id: int | None = None,
    ) -> tuple[int, datetime | None] | None:
        """Read backup-code count only while the bearer remains current."""
        try:
            user = (
                db.query(User).filter(User.id == user_id)
                .with_for_update(key_share=True).populate_existing().first()
            )
            if not user or not user.is_active:
                raise BearerSessionInvalid("Bearer session unavailable")
            self._check_bearer_session(db, user, expected_auth_epoch, expected_jti, expected_exp, expected_patient_id)
            two_factor_auth = (
                db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id)
                .populate_existing().first()
            )
            if two_factor_auth is None:
                db.rollback()
                return None
            count = (
                db.query(TwoFactorBackupCode.id)
                .filter(
                    TwoFactorBackupCode.two_factor_auth_id == two_factor_auth.id,
                    TwoFactorBackupCode.used.is_(False),
                )
                .count()
            )
            created_at = two_factor_auth.created_at
            self._check_bearer_expiry(expected_auth_epoch, expected_exp)
            db.rollback()
            return count, created_at
        except Exception:
            db.rollback()
            raise

    def regenerate_backup_codes(
        self, db: Session, user_id: int, password: str,
        totp_code: str | None = None, backup_code: str | None = None,
        *, expected_auth_epoch: int | None = None,
        expected_jti: str | None = None, expected_exp: int | None = None,
        expected_patient_id: int | None = None,
    ) -> list[str] | None:
        """Reauthenticate and rotate backup codes in one locked transaction."""
        try:
            two_factor_auth = self._authorize_sensitive_operation(
                db, user_id, password, totp_code, backup_code,
                expected_auth_epoch, expected_jti, expected_exp, expected_patient_id,
            )
            if not two_factor_auth:
                return None

            # Удаляем старые коды
            db.query(TwoFactorBackupCode).filter(
                TwoFactorBackupCode.two_factor_auth_id == two_factor_auth.id
            ).delete()

            # Генерируем новые коды
            backup_codes = self.generate_backup_codes()

            for code in backup_codes:
                backup_code = TwoFactorBackupCode(
                    two_factor_auth_id=two_factor_auth.id,
                    code=self._hash_backup_code(code),
                    used=False
                )
                db.add(backup_code)

            two_factor_auth.backup_codes_generated = True
            two_factor_auth.backup_codes_count = len(backup_codes)

            self._check_bearer_expiry(expected_auth_epoch, expected_exp)
            db.commit()
            return backup_codes

        except Exception as e:
            db.rollback()
            logger.error("Error regenerating backup codes: %s", type(e).__name__)
            raise

    async def send_sms_code(
        self, phone: str, code: str, provider_type: SMSProviderType | None = None
    ) -> dict[str, Any]:
        """Отправить SMS код для 2FA"""
        try:
            response = await self.sms_manager.send_2fa_code(
                phone=phone, code=code, provider_type=provider_type
            )

            return {
                "success": response.success,
                "message_id": response.message_id,
                "error": response.error,
                "provider": response.provider,
            }

        except Exception as e:
            logger.warning(
                "2FA SMS dispatch failed error_type=%s", type(e).__name__
            )
            return {"success": False, "error": "provider_error", "provider": "unknown"}

    async def send_email_code(
        self, email: str, code: str, user_name: str | None = None
    ) -> dict[str, Any]:
        """Отправить email код для 2FA"""
        try:
            subject = "Код подтверждения двухфакторной аутентификации"

            # HTML шаблон для email
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #0078d4, #106ebe); padding: 20px; text-align: center;">
                    <h1 style="color: white; margin: 0;">🔐 Код подтверждения</h1>
                </div>

                <div style="padding: 30px; background: #f8fafc;">
                    <p>Здравствуйте{', ' + user_name if user_name else ''}!</p>

                    <p>Ваш код подтверждения для двухфакторной аутентификации:</p>

                    <div style="text-align: center; margin: 30px 0;">
                        <div style="display: inline-block; background: #0078d4; color: white; padding: 15px 30px; border-radius: 8px; font-size: 24px; font-weight: bold; letter-spacing: 3px;">
                            {code}
                        </div>
                    </div>

                    <p style="color: #dc2626; font-weight: bold;">⚠️ Важно:</p>
                    <ul style="color: #6b7280;">
                        <li>Код действителен в течение 5 минут</li>
                        <li>Никому не сообщайте этот код</li>
                        <li>Если вы не запрашивали код, проигнорируйте это письмо</li>
                    </ul>

                    <p style="margin-top: 30px; color: #6b7280; font-size: 14px;">
                        С уважением,<br>
                        Команда клиники
                    </p>
                </div>

                <div style="background: #e5e7eb; padding: 15px; text-align: center; color: #6b7280; font-size: 12px;">
                    Это автоматическое сообщение. Пожалуйста, не отвечайте на него.
                </div>
            </body>
            </html>
            """

            # Текстовая версия
            text_content = f"""
            Код подтверждения двухфакторной аутентификации

            Здравствуйте{', ' + user_name if user_name else ''}!

            Ваш код подтверждения: {code}

            Важно:
            - Код действителен в течение 5 минут
            - Никому не сообщайте этот код
            - Если вы не запрашивали код, проигнорируйте это письмо

            С уважением,
            Команда клиники
            """

            result = await self.email_service.send_email(
                to_email=email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
            )

            return {
                "success": result.get("success", False),
                "message_id": result.get("message_id"),
                "error": result.get("error"),
                "provider": "email",
            }

        except Exception as e:
            logger.warning(
                "2FA email dispatch failed error_type=%s", type(e).__name__
            )
            return {"success": False, "error": "provider_error", "provider": "email"}

    def generate_verification_code(self, length: int = 6) -> str:
        """Генерирует код верификации"""
        return ''.join([str(secrets.randbelow(10)) for _ in range(length)])

    async def send_verification_code(
        self,
        method: str,  # 'sms' или 'email'
        contact: str,  # номер телефона или email
        user_name: str | None = None,
        provider_type: SMSProviderType | None = None,
    ) -> dict[str, Any]:
        """Отправить код верификации по SMS или email"""
        try:
            code = self.generate_verification_code()

            if method == 'sms':
                result = await self.send_sms_code(
                    phone=contact, code=code, provider_type=provider_type
                )
            elif method == 'email':
                result = await self.send_email_code(
                    email=contact, code=code, user_name=user_name
                )
            else:
                return {
                    "success": False,
                    "error": "Invalid method. Use 'sms' or 'email'",
                    "provider": "unknown",
                }

            if result["success"]:
                result["code"] = code  # Возвращаем код для сохранения в сессии

            return result

        except Exception as e:
            logger.warning(
                "2FA verification-code dispatch failed error_type=%s",
                type(e).__name__,
            )
            return {"success": False, "error": "provider_error", "provider": "unknown"}


# Глобальный экземпляр сервиса
two_factor_service = TwoFactorService()


def get_two_factor_service() -> TwoFactorService:
    """Получить экземпляр сервиса 2FA"""
    return two_factor_service
