"""
Сервис восстановления паролей
"""

import logging
import secrets
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.crud import user as crud_user
from app.services.email_sms_enhanced import EmailSMSEnhancedService
from app.services.phone_verification_service import get_phone_verification_service

logger = logging.getLogger(__name__)


class PasswordResetService:
    """Сервис для восстановления паролей"""

    def __init__(self):
        self.phone_verification = get_phone_verification_service()
        self.email_service = EmailSMSEnhancedService()
        self.reset_tokens = {}  # В production использовать Redis
        self.token_ttl_hours = 1  # Токены действуют 1 час

    def generate_reset_token(self) -> str:
        """Генерация токена сброса пароля"""
        return secrets.token_urlsafe(32)

    def _get_token_key(self, token: str) -> str:
        """Получение ключа для хранения токена"""
        return f"password_reset:{token}"

    def _clean_expired_tokens(self):
        """Очистка истекших токенов"""
        now = datetime.now()
        expired_keys = []

        for key, data in self.reset_tokens.items():
            if data.get('expires_at') and now > data['expires_at']:
                expired_keys.append(key)

        for key in expired_keys:
            del self.reset_tokens[key]

    async def initiate_phone_reset(self, db: Session, phone: str) -> dict[str, Any]:
        """Инициация сброса пароля по телефону"""
        try:
            # Проверяем, существует ли пользователь с таким номером
            user = crud_user.get_user_by_phone(db, phone=phone)
            if not user:
                # Не раскрываем информацию о существовании пользователя
                return {
                    "success": True,
                    "message": "Если пользователь с таким номером существует, код будет отправлен",
                }

            # Отправляем код верификации
            verification_result = await self.phone_verification.send_verification_code(
                phone=phone,
                purpose="password_reset",
                custom_message="Код для сброса пароля: {code}. Код действителен 5 минут.",
            )

            if verification_result["success"]:
                logger.info(f"Password reset code sent to phone {phone}")
                return {
                    "success": True,
                    "message": "Код для сброса пароля отправлен на ваш номер",
                    "expires_in_minutes": verification_result["expires_in_minutes"],
                }
            else:
                return {
                    "success": False,
                    "error": verification_result["error"],
                    "error_code": verification_result.get("error_code"),
                }

        except Exception as e:
            logger.error(f"Error initiating phone reset for {phone}: {e}")
            return {"success": False, "error": str(e), "error_code": "INTERNAL_ERROR"}

    async def initiate_email_reset(self, db: Session, email: str) -> dict[str, Any]:
        """Инициация сброса пароля по email"""
        try:
            # Проверяем, существует ли пользователь с таким email
            user = crud_user.get_user_by_email(db, email=email)
            if not user:
                # Не раскрываем информацию о существовании пользователя
                return {
                    "success": True,
                    "message": "Если пользователь с таким email существует, ссылка будет отправлена",
                }

            # Генерируем токен сброса
            reset_token = self.generate_reset_token()
            expires_at = datetime.now() + timedelta(hours=self.token_ttl_hours)

            # Сохраняем токен
            token_key = self._get_token_key(reset_token)
            self.reset_tokens[token_key] = {
                "user_id": user.id,
                "email": email,
                "created_at": datetime.now(),
                "expires_at": expires_at,
                "used": False,
            }

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

            email_result = await self.email_service.send_email(
                to_email=email,
                subject=subject,
                html_content=html_content,
                text_content=text_content,
            )

            if email_result.get("success"):
                logger.info(f"Password reset email sent to {email}")
                return {
                    "success": True,
                    "message": "Ссылка для сброса пароля отправлена на ваш email",
                    "expires_in_hours": self.token_ttl_hours,
                }
            else:
                return {
                    "success": False,
                    "error": f"Ошибка отправки email: {email_result.get('error')}",
                    "error_code": "EMAIL_SEND_FAILED",
                }

        except Exception as e:
            logger.error(f"Error initiating email reset for {email}: {e}")
            return {"success": False, "error": str(e), "error_code": "INTERNAL_ERROR"}

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

            # Сохраняем токен
            token_key = self._get_token_key(reset_token)
            self.reset_tokens[token_key] = {
                "user_id": user.id,
                "phone": phone,
                "created_at": datetime.now(),
                "expires_at": expires_at,
                "used": False,
            }

            logger.info(f"Reset token generated for phone {phone}")

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
            # Очищаем истекшие токены
            self._clean_expired_tokens()

            token_key = self._get_token_key(token)

            if token_key not in self.reset_tokens:
                return {
                    "success": False,
                    "error": "Токен не найден или истек",
                    "error_code": "TOKEN_NOT_FOUND",
                }

            token_data = self.reset_tokens[token_key]

            # Проверяем истечение
            if datetime.now() > token_data['expires_at']:
                del self.reset_tokens[token_key]
                return {
                    "success": False,
                    "error": "Токен истек",
                    "error_code": "TOKEN_EXPIRED",
                }

            # Проверяем, не использован ли токен
            if token_data.get('used'):
                return {
                    "success": False,
                    "error": "Токен уже использован",
                    "error_code": "TOKEN_ALREADY_USED",
                }

            # Проверяем пользователя
            user = crud_user.get_user(db, user_id=token_data['user_id'])
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

            # Обновляем пароль
            hashed_password = get_password_hash(new_password)
            user_data = {
                "hashed_password": hashed_password,
                "password_changed_at": datetime.now(),
            }

            updated_user = crud_user.update_user(
                db, user_id=user.id, user_data=user_data
            )

            if updated_user:
                # Помечаем токен как использованный
                token_data['used'] = True
                token_data['used_at'] = datetime.now()

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

    def validate_reset_token(self, token: str) -> dict[str, Any]:
        """Проверка валидности токена сброса"""
        try:
            self._clean_expired_tokens()

            token_key = self._get_token_key(token)

            if token_key not in self.reset_tokens:
                return {
                    "valid": False,
                    "error": "Токен не найден",
                    "error_code": "TOKEN_NOT_FOUND",
                }

            token_data = self.reset_tokens[token_key]

            if datetime.now() > token_data['expires_at']:
                del self.reset_tokens[token_key]
                return {
                    "valid": False,
                    "error": "Токен истек",
                    "error_code": "TOKEN_EXPIRED",
                }

            if token_data.get('used'):
                return {
                    "valid": False,
                    "error": "Токен уже использован",
                    "error_code": "TOKEN_ALREADY_USED",
                }

            return {
                "valid": True,
                "user_id": token_data['user_id'],
                "expires_at": token_data['expires_at'].isoformat(),
                "time_left_minutes": int(
                    (token_data['expires_at'] - datetime.now()).total_seconds() / 60
                ),
            }

        except Exception as e:
            logger.error(f"Error validating reset token: {e}")
            return {"valid": False, "error": str(e), "error_code": "INTERNAL_ERROR"}

    def get_statistics(self) -> dict[str, Any]:
        """Статистика сброса паролей"""
        try:
            self._clean_expired_tokens()

            total_tokens = len(self.reset_tokens)
            used_tokens = sum(
                1 for data in self.reset_tokens.values() if data.get('used', False)
            )
            active_tokens = total_tokens - used_tokens

            by_method = {"phone": 0, "email": 0}
            for data in self.reset_tokens.values():
                if 'phone' in data:
                    by_method['phone'] += 1
                elif 'email' in data:
                    by_method['email'] += 1

            return {
                "total_tokens": total_tokens,
                "active_tokens": active_tokens,
                "used_tokens": used_tokens,
                "by_method": by_method,
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
