"""
Сервис восстановления паролей
"""

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.pii_masker import mask_pii_text
from app.core.security import get_password_hash, verify_password
from app.crud import user as crud_user
from app.models.authentication import PasswordResetToken
from app.services.email_sms_enhanced import EmailSMSEnhancedService
from app.services.phone_verification_service import get_phone_verification_service

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


class PasswordResetService:
    """Сервис для восстановления паролей"""

    def __init__(self):
        self.phone_verification = get_phone_verification_service()
        self.email_service = EmailSMSEnhancedService()
        self.token_ttl_hours = 1  # Токены действуют 1 час

    def generate_reset_token(self) -> str:
        """Генерация токена сброса пароля"""
        return secrets.token_urlsafe(32)

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

    def _store_reset_token(self, db: Session, raw_token: str, user_id: int) -> None:
        # Opportunistic cleanup: истёкшие строки больше не нужны.
        db.query(PasswordResetToken).filter(
            PasswordResetToken.expires_at < datetime.now(UTC)
        ).delete(synchronize_session=False)
        db.add(
            PasswordResetToken(
                user_id=user_id,
                token=self._hash_token(raw_token),
                expires_at=datetime.now(UTC) + timedelta(hours=self.token_ttl_hours),
                used=False,
            )
        )
        db.commit()

    def _find_token_row(self, db: Session, raw_token: str) -> PasswordResetToken | None:
        return (
            db.query(PasswordResetToken)
            .filter(PasswordResetToken.token == self._hash_token(raw_token))
            .first()
        )

    async def initiate_phone_reset(self, db: Session, phone: str) -> dict[str, Any]:
        """Инициация сброса пароля по телефону"""
        try:
            # Проверяем, существует ли пользователь с таким номером
            user = crud_user.get_user_by_phone(db, phone=phone)
            if not user:
                # Одинаковая форма ответа для всех исходов.
                return {
                    "success": True,
                    "message": _PHONE_RESET_GENERIC_MESSAGE,
                    "expires_in_minutes": _PHONE_CODE_TTL_MINUTES,
                }

            # Отправляем код верификации
            verification_result = await self.phone_verification.send_verification_code(
                phone=phone,
                purpose="password_reset",
                custom_message="Код для сброса пароля: {code}. Код действителен 5 минут.",
            )

            if verification_result["success"]:
                # PII: номер не пишем в лог — только факт отправки.
                logger.info("Password reset code sent", extra={"has_recipient": True})
                return {
                    "success": True,
                    "message": _PHONE_RESET_GENERIC_MESSAGE,
                    "expires_in_minutes": _PHONE_CODE_TTL_MINUTES,
                }
            else:
                # Сбой доставки SMS — та же форма ответа, что и для
                # успеха (анти-enumeration); причина логируется.
                logger.warning(
                    "Password reset SMS send failed: %s",
                    mask_pii_text(str(verification_result.get("error", ""))),
                )
                return {
                    "success": True,
                    "message": _PHONE_RESET_GENERIC_MESSAGE,
                    "expires_in_minutes": _PHONE_CODE_TTL_MINUTES,
                }

        except Exception as e:
            logger.error(
                "Error initiating phone reset: %s",
                mask_pii_text(str(e)),
                extra={"has_recipient": True},
            )
            return {
                "success": False,
                "error": "Внутренняя ошибка, попробуйте позже",
                "error_code": "INTERNAL_ERROR",
            }

    async def initiate_email_reset(self, db: Session, email: str) -> dict[str, Any]:
        """Инициация сброса пароля по email"""
        try:
            # Проверяем, существует ли пользователь с таким email
            user = crud_user.get_user_by_email(db, email=email)
            if not user:
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
            self._store_reset_token(db, reset_token, user.id)

            # Формируем ссылку для сброса
            reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

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
            # Проверяем код верификации
            verification_result = self.phone_verification.verify_code(
                phone=phone, code=verification_code, purpose="password_reset"
            )

            if not verification_result["success"]:
                return verification_result

            # Проверяем, существует ли пользователь
            user = crud_user.get_user_by_phone(db, phone=phone)
            if not user:
                return {
                    "success": False,
                    "error": "Пользователь не найден",
                    "error_code": "USER_NOT_FOUND",
                }

            # Генерируем токен сброса
            reset_token = self.generate_reset_token()
            expires_at = datetime.now() + timedelta(hours=self.token_ttl_hours)

            # Сохраняем токен в БД (переживает рестарты/деплои)
            self._store_reset_token(db, reset_token, user.id)

            logger.info("Reset token generated after phone verification")

            return {
                "success": True,
                "message": "Телефон подтвержден",
                "reset_token": reset_token,
                "expires_in_hours": self.token_ttl_hours,
            }

        except Exception as e:
            logger.error(f"Error verifying phone and getting token: {e}")
            return {"success": False, "error": str(e), "error_code": "INTERNAL_ERROR"}

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

            # Проверяем пользователя
            # get_user is a ghost name (Sentry PYTHON-FASTAPI-10); the
            # crud.user module exposes get(db, id).
            user = crud_user.get(db, id=user_id)
            if not user:
                return {
                    "success": False,
                    "error": "Пользователь не найден",
                    "error_code": "USER_NOT_FOUND",
                }

            # Проверяем новый пароль
            if len(new_password) < 6:
                return {
                    "success": False,
                    "error": "Пароль должен содержать минимум 6 символов",
                    "error_code": "PASSWORD_TOO_SHORT",
                }

            # Проверяем, не совпадает ли новый пароль со старым
            if verify_password(new_password, user.hashed_password):
                return {
                    "success": False,
                    "error": "Новый пароль должен отличаться от текущего",
                    "error_code": "PASSWORD_SAME_AS_OLD",
                }

            # Пароль меняем ПРЯМО здесь: whitelist update_user не содержит
            # hashed_password/password_changed_at (и не должен — он для FCM-
            # профиля), а этот сервис — санкционированный владелец смены
            # пароля. Иначе update_user молча пропускал поля: success=True
            # при НЕИЗМЕНЁННОМ пароле.
            user.hashed_password = get_password_hash(new_password)
            user.password_changed_at = datetime.now()
            db.commit()
            db.refresh(user)

            if user.id:
                # Помечаем токен как использованный (в той же транзакции,
                # что и смена пароля)
                token_row.used = True
                token_row.used_at = datetime.now(UTC)
                db.commit()

                logger.info(f"Password reset completed for user {user.id}")

                return {
                    "success": True,
                    "message": "Пароль успешно изменен",
                    "user_id": user.id,
                }
            else:
                return {
                    "success": False,
                    "error": "Ошибка обновления пароля",
                    "error_code": "PASSWORD_UPDATE_FAILED",
                }

        except Exception as e:
            logger.error(f"Error resetting password with token: {e}")
            return {"success": False, "error": str(e), "error_code": "INTERNAL_ERROR"}

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
            logger.error(f"Error validating reset token: {e}")
            return {"valid": False, "error": str(e), "error_code": "INTERNAL_ERROR"}

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
