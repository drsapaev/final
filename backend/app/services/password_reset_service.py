"""
Сервис восстановления паролей
"""

import asyncio
import hashlib
import logging
import math
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import BoundedSemaphore
from typing import Any

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.pii_masker import mask_pii_text
from app.core.security import get_password_hash, verify_password
from app.crud import user as crud_user
from app.models.authentication import PasswordResetToken
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.email_sms_enhanced import EmailSMSEnhancedService
from app.services.patient_otp_service import normalize_phone
from app.services.patient_phone_scope import (
    acquire_phone_scope_lock,
    canonical_phone_identity,
    verified_phone_candidates,
)
from app.services.phone_verification_service import get_phone_verification_service
from app.services.token_blacklist_service import revoke_account_sessions_locked

logger = logging.getLogger(__name__)

# Анти-enumeration: ЕДИНАЯ форма ответа /2fa…/password-reset/initiate
# для неизвестного адреса, успешной доставки и сбоя доставки — по
# ответу нельзя отличить существующий аккаунт от несуществующего.
_EMAIL_RESET_GENERIC_MESSAGE = (
    "Если пользователь с таким email существует, ссылка для сброса отправлена"
)
_PHONE_RESET_GENERIC_MESSAGE = (
    "Если пользователь с таким номером существует, код для сброса отправлен"
)
# Срок жизни SMS-кода; синхронизирован с текстом сообщения
# ("Код действителен 5 минут") в initiate_phone_reset.
_PHONE_CODE_TTL_MINUTES = 5
_PHONE_RESET_MAX_PENDING = 128
_PHONE_RESET_TASKS: set[asyncio.Task] = set()
_EMAIL_RESET_PENDING = BoundedSemaphore(32)
_EMAIL_RESET_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="reset-email")
_ANY_EMAIL_BINDING = object()


def _dispatch_email_reset(email: str, binding: tuple[int, int] | None) -> None:
    """Run delivery off the request loop with a private, short-lived session."""
    from app.db.session import SessionLocal

    try:
        with SessionLocal() as db:
            asyncio.run(get_password_reset_service().initiate_email_reset(
                db, email, expected_binding=binding
            ))
    except Exception as exc:
        # Neither the address nor the exception message belongs in logs.
        logger.error("Password reset delivery failed: %s", type(exc).__name__)


def schedule_email_reset(email: str, binding: tuple[int, int] | None) -> bool:
    """Queue either kind of address without revealing account existence.

    Slots include queued and running workers and are released only when the
    underlying worker exits, including if the HTTP request is cancelled.
    """
    slots = _EMAIL_RESET_PENDING
    if not slots.acquire(blocking=False):
        logger.warning("Password reset delivery queue is full")
        return False
    try:
        future = _EMAIL_RESET_EXECUTOR.submit(_dispatch_email_reset, email, binding)
    except Exception as exc:
        slots.release()
        logger.error("Password reset delivery scheduling failed: %s", type(exc).__name__)
        return False
    future.add_done_callback(lambda _: slots.release())
    return True


class EmailResetUnavailable(Exception):
    """Infrastructure could not accept an email reset request."""


class PasswordResetService:
    """Сервис для восстановления паролей"""

    def __init__(self):
        self.phone_verification = get_phone_verification_service()
        self.email_service = EmailSMSEnhancedService()
        self.token_ttl_hours = 1  # Токены действуют 1 час

    def generate_reset_token(self) -> str:
        """Генерация токена сброса пароля"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def snapshot_email_binding(db: Session, email: str) -> tuple[int, int] | None:
        """Bind dispatch to the account state observed before acknowledgement."""
        try:
            user = crud_user.get_user_by_email(db, email=email)
            return (user.id, user.auth_epoch) if user and user.is_active else None
        except Exception as exc:
            logger.error("Password reset lookup failed: %s", type(exc).__name__)
            raise EmailResetUnavailable from exc
        finally:
            try:
                db.rollback()
            except Exception as exc:
                logger.error("Password reset lookup cleanup failed: %s", type(exc).__name__)
                raise EmailResetUnavailable from exc

    # Хранение в password_reset_tokens (было: dict в памяти процесса —
    # каждый рестарт/деплой убивал все высланные ссылки, TOKEN_NOT_FOUND).
    # В БД хранится sha256-hex токена (сырой bearer-токен в БД не кладём;
    # 64 hex-символа точно вписываются в String(64)).

    @staticmethod
    def _hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _aware(dt: datetime) -> datetime:
        # SQLite round-trips tz-aware values as naive; PG keeps them aware.
        # Normalize before python-side comparisons.
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)

    @staticmethod
    def _accepted_reset_phone(raw: str) -> str | None:
        """Accept only the ASCII +998 form used by SMS/reset clients."""
        normalized = normalize_phone(raw)
        return normalized if normalized and normalized.isascii() else None

    @staticmethod
    def _unique_verified_phone_binding(db: Session, phone: str) -> tuple[int, int] | None:
        """Resolve only an unambiguous verified phone owned by an active user.

        Count verified profiles of *inactive* accounts too. Their activation
        does not necessarily acquire the phone advisory lock for staff roles;
        counting them prevents a concurrent activation from creating a second
        reset identity after this check.
        """
        candidates = verified_phone_candidates(db, phone)
        if candidates is None or len(candidates) != 1:
            return None
        user_id, epoch, active = candidates[0]
        if active is not True:
            return None
        return user_id, epoch

    def _snapshot_phone_binding(self, db: Session, phone: str) -> tuple[int, int] | None:
        """Finish the read transaction before any external SMS operation."""
        try:
            return self._unique_verified_phone_binding(db, phone)
        finally:
            db.rollback()

    async def _dispatch_phone_reset(self, phone: str | None, binding: tuple[int, int] | None) -> None:
        """Deliver after the generic response without retaining a DB session."""
        if phone is None or binding is None:
            return
        try:
            result = await self.phone_verification.send_verification_code(
                phone=phone,
                purpose="password_reset",
                custom_message="Код для сброса пароля: {code}. Код действителен 5 минут.",
                account_binding=binding,
            )
            if not result.get("success"):
                logger.warning("Password reset SMS send failed")
        except Exception as exc:
            # Providers may include the phone or code in exception text.
            logger.warning("Password reset SMS send failed: %s", type(exc).__name__)

    def _schedule_phone_reset(self, phone: str | None, binding: tuple[int, int] | None) -> None:
        """Bound retained tasks while keeping known/unknown response behavior equal."""
        if len(_PHONE_RESET_TASKS) >= _PHONE_RESET_MAX_PENDING:
            logger.warning("Password reset dispatch queue is full")
            return
        task = asyncio.create_task(self._dispatch_phone_reset(phone, binding))
        _PHONE_RESET_TASKS.add(task)
        task.add_done_callback(_PHONE_RESET_TASKS.discard)

    def _store_reset_token(
        self, db: Session, raw_token: str, user_id: int, *, expected_email: str | None = None,
        expected_epoch: int | None = None, expected_phone: str | None = None,
        proof_expires_monotonic: float | None = None,
    ) -> bool:
        # Cleanup is a separate transaction: never lock other accounts' reset
        # rows while holding this account's User lock.
        db.query(PasswordResetToken).filter(
            PasswordResetToken.expires_at < datetime.now(UTC)
        ).delete(synchronize_session=False)
        db.commit()
        user = (
            db.query(User).filter(User.id == user_id)
            .with_for_update(key_share=True).populate_existing().first()
        )
        if (not user or not user.is_active
            or (expected_email is not None and user.email != expected_email)
            or (expected_epoch is not None and user.auth_epoch != expected_epoch)):
            db.rollback()
            return False
        if expected_phone is not None:
            profile = (
                db.query(UserProfile).filter(UserProfile.user_id == user_id)
                .with_for_update().populate_existing().first()
            )
            # Every verified-phone writer shares this advisory lock. Recheck
            # ownership and uniqueness after it is held; a prior lookup or OTP
            # binding is only a hint and cannot authorize issuance by itself.
            acquire_phone_scope_lock(db, expected_phone)
            if (
                not profile
                or canonical_phone_identity(profile.phone or "") != expected_phone
                or profile.phone_verified is not True
                or self._unique_verified_phone_binding(db, expected_phone)
                != (user_id, user.auth_epoch)
                or not self._proof_live(proof_expires_monotonic)
            ):
                db.rollback()
                return False
        db.add(
            PasswordResetToken(
                user_id=user_id,
                token=self._hash_token(raw_token),
                expires_at=datetime.now(UTC) + timedelta(hours=self.token_ttl_hours),
                used=False,
            )
        )
        if expected_phone is not None:
            # Flush may itself block. Recheck after all database work and just
            # before committing the bearer credential, not just at OTP consume.
            db.flush()
            if not self._proof_live(proof_expires_monotonic):
                db.rollback()
                return False
        db.commit()
        # A delayed commit must not return a usable bearer after the proof's
        # deadline; the token hash alone cannot be used by a client.
        if expected_phone is not None and not self._proof_live(proof_expires_monotonic):
            return False
        return True

    @staticmethod
    def _proof_live(expires_at: object) -> bool:
        if type(expires_at) not in (int, float):
            return False
        try:
            return math.isfinite(expires_at) and time.monotonic() < expires_at
        except OverflowError:
            return False

    def _find_token_row(self, db: Session, raw_token: str) -> PasswordResetToken | None:
        return (
            db.query(PasswordResetToken)
            .filter(PasswordResetToken.token == self._hash_token(raw_token))
            .first()
        )

    async def initiate_phone_reset(self, db: Session, phone: str) -> dict[str, Any]:
        """Инициация сброса пароля по телефону"""
        try:
            normalized = self._accepted_reset_phone(phone)
            # The session is used sequentially, never concurrently: perform
            # the potentially large query and rollback in the worker before
            # awaiting SMS, keeping both DB locks and blocking I/O off the loop.
            binding = await run_in_threadpool(self._snapshot_phone_binding, db, normalized) if normalized else None
            self._schedule_phone_reset(normalized, binding)
        except Exception as e:
            await run_in_threadpool(db.rollback)
            logger.error("Error initiating phone reset: %s", type(e).__name__)
        return {
            "success": True,
            "message": _PHONE_RESET_GENERIC_MESSAGE,
            "expires_in_minutes": _PHONE_CODE_TTL_MINUTES,
        }

    async def initiate_email_reset(
        self, db: Session, email: str, *, expected_binding: object = _ANY_EMAIL_BINDING
    ) -> dict[str, Any]:
        """Инициация сброса пароля по email"""
        try:
            # Проверяем, существует ли пользователь с таким email
            user = crud_user.get_user_by_email(db, email=email) if expected_binding is not None else None
            if not user or (expected_binding is not _ANY_EMAIL_BINDING and (user.id, user.auth_epoch) != expected_binding):
                # Не раскрываем информацию о существовании пользователя:
                # одинаковая форма ответа для всех исходов.
                return {
                    "success": True,
                    "message": _EMAIL_RESET_GENERIC_MESSAGE,
                    "expires_in_hours": self.token_ttl_hours,
                }

            # Генерируем токен сброса
            reset_token = self.generate_reset_token()
            expires_at = datetime.now() + timedelta(hours=self.token_ttl_hours)

            # Сохраняем токен в БД (переживает рестарты/деплои)
            if not self._store_reset_token(
                db, reset_token, user.id, expected_email=email, expected_epoch=user.auth_epoch
            ):
                return {
                    "success": True,
                    "message": _EMAIL_RESET_GENERIC_MESSAGE,
                    "expires_in_hours": self.token_ttl_hours,
                }

            # Формируем ссылку для сброса
            reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password#token={reset_token}"

            # Отправляем email
            subject = "Сброс пароля"
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; color: white;">
                    <h1>🔐 Сброс пароля</h1>
                </div>

                <div style="padding: 30px; background: #f9f9f9;">
                    <h2>Здравствуйте!</h2>

                    <p>Вы запросили сброс пароля для вашего аккаунта в медицинской клинике.</p>

                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{reset_url}"
                           style="background: #667eea; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">
                            Сбросить пароль
                        </a>
                    </div>

                    <p><strong>Важно:</strong></p>
                    <ul>
                        <li>Ссылка действительна в течение {self.token_ttl_hours} часа</li>
                        <li>Если вы не запрашивали сброс пароля, проигнорируйте это письмо</li>
                        <li>Ссылка может быть использована только один раз</li>
                    </ul>

                    <p>Если кнопка не работает, скопируйте и вставьте эту ссылку в браузер:</p>
                    <p style="word-break: break-all; color: #667eea;">{reset_url}</p>
                </div>

                <div style="padding: 20px; text-align: center; color: #666; font-size: 12px;">
                    <p>© 2024 Медицинская клиника. Все права защищены.</p>
                </div>
            </body>
            </html>
            """

            text_content = f"""
            Сброс пароля

            Здравствуйте!

            Вы запросили сброс пароля для вашего аккаунта в медицинской клинике.

            Перейдите по ссылке для сброса пароля:
            {reset_url}

            Важно:
            - Ссылка действительна в течение {self.token_ttl_hours} часа
            - Если вы не запрашивали сброс пароля, проигнорируйте это письмо
            - Ссылка может быть использована только один раз

            © 2024 Медицинская клиника
            """

            send_ok, send_message = await self.email_service.send_email_enhanced(
                to_email=email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
            )

            if send_ok:
                logger.info("Password reset email sent", extra={"has_recipient": True})
                return {
                    "success": True,
                    "message": _EMAIL_RESET_GENERIC_MESSAGE,
                    "expires_in_hours": self.token_ttl_hours,
                }
            else:
                # PII: текст ошибки провайдера может содержать адрес
                # получателя — логируем замаскированным. Клиенту — та
                # же форма ответа, что и для успеха/неизвестного
                # адреса: сбой доставки не должен выдавать
                # существование аккаунта (анти-enumeration).
                logger.warning(
                    "Password reset email send failed: %s",
                    mask_pii_text(send_message),
                )
                return {
                    "success": True,
                    "message": _EMAIL_RESET_GENERIC_MESSAGE,
                    "expires_in_hours": self.token_ttl_hours,
                }

        except Exception as e:
            logger.error(
                "Error initiating email reset: %s",
                mask_pii_text(str(e)),
                extra={"has_recipient": True},
            )
            return {
                "success": False,
                "error": "Внутренняя ошибка, попробуйте позже",
                "error_code": "INTERNAL_ERROR",
            }

    async def verify_phone_and_get_token(
        self, db: Session, phone: str, verification_code: str
    ) -> dict[str, Any]:
        """Верификация телефона и получение токена сброса"""
        try:
            normalized = self._accepted_reset_phone(phone)
            if not normalized:
                return {"success": False, "error": "Код не найден или истек", "error_code": "CODE_NOT_FOUND"}
            # Проверяем код верификации
            verification_result = await run_in_threadpool(
                self.phone_verification.verify_code,
                phone=normalized, code=verification_code, purpose="password_reset",
                include_account_binding=True,
            )

            if not verification_result["success"]:
                # A missing, wrong, expired or exhausted proof must not reveal
                # whether a verification was ever issued for this number.
                return {"success": False, "error": "Код не найден или истек", "error_code": "CODE_NOT_FOUND"}

            binding = verification_result.get("account_binding")
            if (not isinstance(binding, tuple) or len(binding) != 2
                or type(binding[0]) is not int or type(binding[1]) is not int
                or not self._proof_live(verification_result.get("expires_monotonic"))):
                return {"success": False, "error": "Код не найден или истек", "error_code": "CODE_NOT_FOUND"}

            # Генерируем токен сброса
            reset_token = self.generate_reset_token()

            # Сохраняем токен в БД (переживает рестарты/деплои)
            if not await run_in_threadpool(
                self._store_reset_token, db, reset_token, binding[0],
                expected_epoch=binding[1], expected_phone=normalized,
                proof_expires_monotonic=verification_result["expires_monotonic"],
            ):
                return {
                    "success": False,
                    "error": "Код не найден или истек",
                    "error_code": "CODE_NOT_FOUND",
                }

            logger.info("Reset token generated after phone verification")

            return {
                "success": True,
                "message": "Телефон подтвержден",
                "reset_token": reset_token,
                "expires_in_hours": self.token_ttl_hours,
            }

        except Exception as e:
            await run_in_threadpool(db.rollback)
            logger.error("Error verifying phone and getting token: %s", type(e).__name__)
            return {"success": False, "error": "Внутренняя ошибка", "error_code": "INTERNAL_ERROR"}

    def reset_password_with_token(
        self, db: Session, token: str, new_password: str
    ) -> dict[str, Any]:
        """Сброс пароля с использованием токена"""
        try:
            token_row = self._find_token_row(db, token)

            if token_row is None:
                return {
                    "success": False,
                    "error": "Токен не найден или истек",
                    "error_code": "TOKEN_NOT_FOUND",
                }

            # Проверяем истечение
            if datetime.now(UTC) > self._aware(token_row.expires_at):
                return {
                    "success": False,
                    "error": "Токен истек",
                    "error_code": "TOKEN_EXPIRED",
                }

            # Проверяем, не использован ли токен
            if token_row.used:
                return {
                    "success": False,
                    "error": "Токен уже использован",
                    "error_code": "TOKEN_ALREADY_USED",
                }

            user_id = token_row.user_id

            # The first lookup is only an identity hint. Serialize with login,
            # deactivation and every other account-wide revocation first.
            user = (
                db.query(User).filter(User.id == user_id)
                .with_for_update(key_share=True).populate_existing().first()
            )
            if not user or not user.is_active:
                db.rollback()
                return {
                    "success": False,
                    "error": "Токен не найден или истек",
                    "error_code": "TOKEN_NOT_FOUND",
                }

            token_row = (
                db.query(PasswordResetToken)
                .filter(
                    PasswordResetToken.user_id == user_id,
                    PasswordResetToken.token == self._hash_token(token),
                )
                .with_for_update().populate_existing().first()
            )
            if token_row is None:
                db.rollback()
                return {"success": False, "error": "Токен не найден или истек", "error_code": "TOKEN_NOT_FOUND"}
            if token_row.used:
                db.rollback()
                return {"success": False, "error": "Токен уже использован", "error_code": "TOKEN_ALREADY_USED"}
            if datetime.now(UTC) >= self._aware(token_row.expires_at):
                db.rollback()
                return {"success": False, "error": "Токен истек", "error_code": "TOKEN_EXPIRED"}

            # Проверяем новый пароль
            if len(new_password) < 8:
                db.rollback()
                return {
                    "success": False,
                    "error": "Пароль должен содержать минимум 8 символов",
                    "error_code": "PASSWORD_TOO_SHORT",
                }

            # Проверяем, не совпадает ли новый пароль со старым
            if verify_password(new_password, user.hashed_password):
                db.rollback()
                return {
                    "success": False,
                    "error": "Новый пароль должен отличаться от текущего",
                    "error_code": "PASSWORD_SAME_AS_OLD",
                }

            # Epoch, sessions, password and token consumption commit together.
            # A stale access token or concurrent reset cannot survive rotation.
            revoke_account_sessions_locked(db, user, revoke_password_resets=True)
            if datetime.now(UTC) >= self._aware(token_row.expires_at):
                db.rollback()
                return {"success": False, "error": "Токен истек", "error_code": "TOKEN_EXPIRED"}
            new_hash = get_password_hash(new_password)
            if datetime.now(UTC) >= self._aware(token_row.expires_at):
                db.rollback()
                return {"success": False, "error": "Токен истек", "error_code": "TOKEN_EXPIRED"}
            user.hashed_password = new_hash
            user.password_changed_at = datetime.now(UTC)
            token_row.used = True
            token_row.used_at = datetime.now(UTC)
            db.commit()

            logger.info("Password reset completed")
            return {
                "success": True,
                "message": "Пароль успешно изменен",
                "user_id": user.id,
            }

        except Exception as e:
            db.rollback()
            logger.error("Error resetting password with token: %s", type(e).__name__)
            return {"success": False, "error": "Внутренняя ошибка", "error_code": "INTERNAL_ERROR"}

    def validate_reset_token(self, db: Session, token: str) -> dict[str, Any]:
        """Проверка валидности токена сброса"""
        try:
            token_row = self._find_token_row(db, token)

            if token_row is None:
                return {
                    "valid": False,
                    "error": "Токен не найден",
                    "error_code": "TOKEN_NOT_FOUND",
                }

            if datetime.now(UTC) > self._aware(token_row.expires_at):
                return {
                    "valid": False,
                    "error": "Токен истек",
                    "error_code": "TOKEN_EXPIRED",
                }

            if token_row.used:
                return {
                    "valid": False,
                    "error": "Токен уже использован",
                    "error_code": "TOKEN_ALREADY_USED",
                }

            return {
                "valid": True,
                "user_id": token_row.user_id,
                "expires_at": token_row.expires_at.isoformat(),
                "time_left_minutes": int(
                    (
                        self._aware(token_row.expires_at) - datetime.now(UTC)
                    ).total_seconds()
                    / 60
                ),
            }

        except Exception as e:
            logger.error("Error validating reset token: %s", type(e).__name__)
            return {"valid": False, "error": "Внутренняя ошибка", "error_code": "INTERNAL_ERROR"}

    def get_statistics(self, db: Session) -> dict[str, Any]:
        """Статистика сброса паролей"""
        try:
            now = datetime.now(UTC)
            base = db.query(PasswordResetToken)
            total_tokens = base.count()
            used_tokens = base.filter(PasswordResetToken.used == True).count()  # noqa: E712
            active_tokens = base.filter(
                PasswordResetToken.used == False,  # noqa: E712
                PasswordResetToken.expires_at > now,
            ).count()

            # Метод (email/phone) в строках не хранится — старый словарь в
            # памяти знал его, БД нет; потребителей поля нет (проверено).
            return {
                "total_tokens": total_tokens,
                "active_tokens": active_tokens,
                "used_tokens": used_tokens,
                "by_method": {"phone": 0, "email": 0},
                "settings": {"token_ttl_hours": self.token_ttl_hours},
            }

        except Exception as e:
            logger.error(f"Error getting password reset statistics: {e}")
            return {"error": str(e)}


# Глобальный экземпляр сервиса
password_reset_service = PasswordResetService()


def get_password_reset_service() -> PasswordResetService:
    """Получить экземпляр сервиса сброса паролей"""
    return password_reset_service
