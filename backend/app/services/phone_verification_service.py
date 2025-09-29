"""
Сервис верификации телефонных номеров
"""
import asyncio
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.core.config import settings
from app.services.sms_providers import get_sms_manager, SMSProviderType
from app.crud import user as crud_user
from app.models.user import User

logger = logging.getLogger(__name__)


class PhoneVerificationService:
    """Сервис для верификации телефонных номеров"""
    
    def __init__(self):
        self.sms_manager = get_sms_manager()
        self.verification_codes = {}  # В production использовать Redis
        self.code_length = 6
        self.code_ttl_minutes = 5
        self.max_attempts = 3
        self.rate_limit_minutes = 1  # Минимальный интервал между отправками
        
    def generate_verification_code(self) -> str:
        """Генерация кода верификации"""
        return ''.join([str(secrets.randbelow(10)) for _ in range(self.code_length)])
    
    def _get_code_key(self, phone: str, purpose: str = "verification") -> str:
        """Получение ключа для хранения кода"""
        return f"phone_verification:{purpose}:{phone}"
    
    def _is_rate_limited(self, phone: str, purpose: str = "verification") -> bool:
        """Проверка лимита частоты отправки"""
        key = self._get_code_key(phone, purpose)
        
        if key in self.verification_codes:
            last_sent = self.verification_codes[key].get('last_sent')
            if last_sent:
                time_passed = datetime.now() - last_sent
                if time_passed < timedelta(minutes=self.rate_limit_minutes):
                    return True
        
        return False
    
    def _clean_expired_codes(self):
        """Очистка истекших кодов"""
        now = datetime.now()
        expired_keys = []
        
        for key, data in self.verification_codes.items():
            if data.get('expires_at') and now > data['expires_at']:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.verification_codes[key]
    
    async def send_verification_code(
        self,
        phone: str,
        purpose: str = "verification",
        provider_type: Optional[SMSProviderType] = None,
        custom_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """Отправка кода верификации"""
        try:
            # Очищаем истекшие коды
            self._clean_expired_codes()
            
            # Проверяем лимит частоты
            if self._is_rate_limited(phone, purpose):
                return {
                    "success": False,
                    "error": f"Повторная отправка возможна через {self.rate_limit_minutes} минут",
                    "error_code": "RATE_LIMITED"
                }
            
            # Генерируем код
            code = self.generate_verification_code()
            expires_at = datetime.now() + timedelta(minutes=self.code_ttl_minutes)
            
            # Формируем сообщение
            if custom_message:
                message = custom_message.format(code=code)
            else:
                purpose_messages = {
                    "verification": f"Ваш код подтверждения: {code}. Код действителен {self.code_ttl_minutes} минут.",
                    "password_reset": f"Код для сброса пароля: {code}. Код действителен {self.code_ttl_minutes} минут.",
                    "phone_change": f"Код для смены номера телефона: {code}. Код действителен {self.code_ttl_minutes} минут.",
                    "registration": f"Код для регистрации: {code}. Код действителен {self.code_ttl_minutes} минут."
                }
                message = purpose_messages.get(purpose, f"Ваш код: {code}")
            
            # Отправляем SMS
            sms_result = await self.sms_manager.send_sms(
                phone=phone,
                message=message,
                provider_type=provider_type
            )
            
            if sms_result.success:
                # Сохраняем код
                key = self._get_code_key(phone, purpose)
                self.verification_codes[key] = {
                    "code": code,
                    "phone": phone,
                    "purpose": purpose,
                    "created_at": datetime.now(),
                    "expires_at": expires_at,
                    "last_sent": datetime.now(),
                    "attempts": 0,
                    "verified": False,
                    "message_id": sms_result.message_id,
                    "provider": sms_result.provider
                }
                
                logger.info(f"Verification code sent to {phone} for {purpose}")
                
                return {
                    "success": True,
                    "message": "Код верификации отправлен",
                    "expires_in_minutes": self.code_ttl_minutes,
                    "message_id": sms_result.message_id,
                    "provider": sms_result.provider
                }
            else:
                logger.error(f"Failed to send verification code to {phone}: {sms_result.error}")
                return {
                    "success": False,
                    "error": f"Ошибка отправки SMS: {sms_result.error}",
                    "error_code": "SMS_SEND_FAILED"
                }
                
        except Exception as e:
            logger.error(f"Error sending verification code to {phone}: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "INTERNAL_ERROR"
            }
    
    def verify_code(
        self,
        phone: str,
        code: str,
        purpose: str = "verification",
        remove_after_verification: bool = True
    ) -> Dict[str, Any]:
        """Проверка кода верификации"""
        try:
            # Очищаем истекшие коды
            self._clean_expired_codes()
            
            key = self._get_code_key(phone, purpose)
            
            if key not in self.verification_codes:
                return {
                    "success": False,
                    "error": "Код не найден или истек",
                    "error_code": "CODE_NOT_FOUND"
                }
            
            verification_data = self.verification_codes[key]
            
            # Проверяем истечение
            if datetime.now() > verification_data['expires_at']:
                del self.verification_codes[key]
                return {
                    "success": False,
                    "error": "Код истек",
                    "error_code": "CODE_EXPIRED"
                }
            
            # Проверяем количество попыток
            if verification_data['attempts'] >= self.max_attempts:
                del self.verification_codes[key]
                return {
                    "success": False,
                    "error": f"Превышено максимальное количество попыток ({self.max_attempts})",
                    "error_code": "MAX_ATTEMPTS_EXCEEDED"
                }
            
            # Увеличиваем счетчик попыток
            verification_data['attempts'] += 1
            
            # Проверяем код
            if verification_data['code'] != code:
                return {
                    "success": False,
                    "error": f"Неверный код. Осталось попыток: {self.max_attempts - verification_data['attempts']}",
                    "error_code": "INVALID_CODE",
                    "attempts_left": self.max_attempts - verification_data['attempts']
                }
            
            # Код верный
            verification_data['verified'] = True
            verification_data['verified_at'] = datetime.now()
            
            logger.info(f"Phone {phone} verified successfully for {purpose}")
            
            result = {
                "success": True,
                "message": "Номер телефона успешно подтвержден",
                "phone": phone,
                "purpose": purpose,
                "verified_at": verification_data['verified_at'].isoformat()
            }
            
            # Удаляем код после успешной верификации
            if remove_after_verification:
                del self.verification_codes[key]
            
            return result
            
        except Exception as e:
            logger.error(f"Error verifying code for {phone}: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "INTERNAL_ERROR"
            }
    
    def get_verification_status(self, phone: str, purpose: str = "verification") -> Dict[str, Any]:
        """Получение статуса верификации"""
        try:
            self._clean_expired_codes()
            
            key = self._get_code_key(phone, purpose)
            
            if key not in self.verification_codes:
                return {
                    "exists": False,
                    "verified": False
                }
            
            verification_data = self.verification_codes[key]
            
            return {
                "exists": True,
                "verified": verification_data.get('verified', False),
                "phone": verification_data['phone'],
                "purpose": verification_data['purpose'],
                "created_at": verification_data['created_at'].isoformat(),
                "expires_at": verification_data['expires_at'].isoformat(),
                "attempts": verification_data['attempts'],
                "max_attempts": self.max_attempts,
                "time_left_minutes": max(0, int((verification_data['expires_at'] - datetime.now()).total_seconds() / 60))
            }
            
        except Exception as e:
            logger.error(f"Error getting verification status for {phone}: {e}")
            return {
                "exists": False,
                "verified": False,
                "error": str(e)
            }
    
    def cancel_verification(self, phone: str, purpose: str = "verification") -> bool:
        """Отмена верификации"""
        try:
            key = self._get_code_key(phone, purpose)
            
            if key in self.verification_codes:
                del self.verification_codes[key]
                logger.info(f"Verification cancelled for {phone} ({purpose})")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error cancelling verification for {phone}: {e}")
            return False
    
    async def verify_and_update_user_phone(
        self,
        db: Session,
        user_id: int,
        phone: str,
        code: str,
        purpose: str = "phone_change"
    ) -> Dict[str, Any]:
        """Верификация и обновление номера телефона пользователя"""
        try:
            # Проверяем код
            verification_result = self.verify_code(phone, code, purpose)
            
            if not verification_result["success"]:
                return verification_result
            
            # Проверяем, не занят ли номер другим пользователем
            existing_user = crud_user.get_user_by_phone(db, phone=phone)
            if existing_user and existing_user.id != user_id:
                return {
                    "success": False,
                    "error": "Номер телефона уже используется другим пользователем",
                    "error_code": "PHONE_ALREADY_USED"
                }
            
            # Обновляем номер телефона
            user_data = {
                "phone": phone,
                "phone_verified": True,
                "phone_verified_at": datetime.now()
            }
            
            updated_user = crud_user.update_user(db, user_id=user_id, user_data=user_data)
            
            if updated_user:
                logger.info(f"Phone updated for user {user_id}: {phone}")
                return {
                    "success": True,
                    "message": "Номер телефона успешно обновлен и подтвержден",
                    "phone": phone,
                    "verified_at": user_data["phone_verified_at"].isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": "Ошибка обновления пользователя",
                    "error_code": "USER_UPDATE_FAILED"
                }
                
        except Exception as e:
            logger.error(f"Error verifying and updating user phone: {e}")
            return {
                "success": False,
                "error": str(e),
                "error_code": "INTERNAL_ERROR"
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Статистика верификаций"""
        try:
            self._clean_expired_codes()
            
            total_codes = len(self.verification_codes)
            verified_codes = sum(1 for data in self.verification_codes.values() if data.get('verified', False))
            expired_soon = sum(1 for data in self.verification_codes.values() 
                             if (data['expires_at'] - datetime.now()).total_seconds() < 60)
            
            purposes = {}
            providers = {}
            
            for data in self.verification_codes.values():
                purpose = data.get('purpose', 'unknown')
                provider = data.get('provider', 'unknown')
                
                purposes[purpose] = purposes.get(purpose, 0) + 1
                providers[provider] = providers.get(provider, 0) + 1
            
            return {
                "total_active_codes": total_codes,
                "verified_codes": verified_codes,
                "pending_codes": total_codes - verified_codes,
                "expiring_soon": expired_soon,
                "by_purpose": purposes,
                "by_provider": providers,
                "settings": {
                    "code_length": self.code_length,
                    "ttl_minutes": self.code_ttl_minutes,
                    "max_attempts": self.max_attempts,
                    "rate_limit_minutes": self.rate_limit_minutes
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting verification statistics: {e}")
            return {
                "error": str(e)
            }


# Глобальный экземпляр сервиса
phone_verification_service = PhoneVerificationService()


def get_phone_verification_service() -> PhoneVerificationService:
    """Получить экземпляр сервиса верификации телефонов"""
    return phone_verification_service


