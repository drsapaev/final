"""
Сервис для двухфакторной аутентификации (2FA)
"""
import secrets
import hashlib
import hmac
import base64
import time
import qrcode
import io
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.two_factor_auth import (
    TwoFactorAuth, TwoFactorBackupCode, TwoFactorRecovery, 
    TwoFactorSession, TwoFactorDevice
)
from app.models.user import User
from app.core.config import settings
from app.core.security import verify_password
from app.services.sms_providers import get_sms_manager, SMSProviderType
from app.services.email_sms_enhanced import EmailSMSEnhancedService
import logging

logger = logging.getLogger(__name__)


class TwoFactorService:
    """Сервис для работы с 2FA"""

    def __init__(self):
        self.totp_window = 1  # Окно для проверки TOTP кодов
        self.backup_codes_count = 10  # Количество backup кодов
        self.recovery_token_length = 32  # Длина токена восстановления
        self.session_expiry_hours = 24  # Время жизни сессии
        self.recovery_expiry_hours = 1  # Время жизни токена восстановления
        self.sms_manager = get_sms_manager()
        self.email_service = EmailSMSEnhancedService()

    def generate_totp_secret(self) -> str:
        """Генерирует секретный ключ для TOTP"""
        return base64.b32encode(secrets.token_bytes(20)).decode('utf-8')

    def generate_totp_code(self, secret: str, timestamp: Optional[int] = None) -> str:
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
        offset = hmac_digest[-1] & 0x0f
        code = ((hmac_digest[offset] & 0x7f) << 24 |
                (hmac_digest[offset + 1] & 0xff) << 16 |
                (hmac_digest[offset + 2] & 0xff) << 8 |
                (hmac_digest[offset + 3] & 0xff))
        
        return str(code % 1000000).zfill(6)

    def verify_totp_code(self, secret: str, code: str, timestamp: Optional[int] = None) -> bool:
        """Проверяет TOTP код"""
        if timestamp is None:
            timestamp = int(time.time())
        
        # Проверяем код в окне времени
        for i in range(-self.totp_window, self.totp_window + 1):
            expected_code = self.generate_totp_code(secret, timestamp + i * 30)
            if hmac.compare_digest(code, expected_code):
                return True
        
        return False

    def generate_qr_code(self, secret: str, user_email: str, issuer: str = "Clinic System") -> str:
        """Генерирует QR код для настройки 2FA"""
        totp_uri = f"otpauth://totp/{issuer}:{user_email}?secret={secret}&issuer={issuer}"
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Конвертируем в base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        img_str = base64.b64encode(buffer.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"

    def generate_backup_codes(self, count: int = None) -> List[str]:
        """Генерирует backup коды"""
        if count is None:
            count = self.backup_codes_count
        
        codes = []
        for _ in range(count):
            # Генерируем 8-символьный код
            code = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(8))
            codes.append(code)
        
        return codes

    def generate_recovery_token(self) -> str:
        """Генерирует токен восстановления"""
        return secrets.token_urlsafe(self.recovery_token_length)

    def generate_device_fingerprint(self, user_agent: str, ip_address: str) -> str:
        """Генерирует отпечаток устройства"""
        data = f"{user_agent}:{ip_address}"
        return hashlib.sha256(data.encode()).hexdigest()

    def setup_two_factor_auth(
        self, 
        db: Session, 
        user_id: int, 
        recovery_email: Optional[str] = None,
        recovery_phone: Optional[str] = None
    ) -> Dict[str, Any]:
        """Настраивает 2FA для пользователя"""
        try:
            # Получаем пользователя
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")

            # Проверяем, есть ли уже 2FA
            existing_2fa = db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id).first()
            
            if existing_2fa and existing_2fa.totp_enabled:
                raise ValueError("2FA already enabled for this user")

            # Генерируем секрет
            secret = self.generate_totp_secret()
            
            # Создаем или обновляем запись 2FA
            if existing_2fa:
                existing_2fa.totp_secret = secret
                existing_2fa.totp_enabled = False
                existing_2fa.totp_verified = False
                existing_2fa.recovery_email = recovery_email
                existing_2fa.recovery_phone = recovery_phone
                two_factor_auth = existing_2fa
            else:
                two_factor_auth = TwoFactorAuth(
                    user_id=user_id,
                    totp_secret=secret,
                    totp_enabled=False,
                    totp_verified=False,
                    recovery_email=recovery_email,
                    recovery_phone=recovery_phone,
                    recovery_enabled=bool(recovery_email or recovery_phone)
                )
                db.add(two_factor_auth)

            # Генерируем backup коды
            backup_codes = self.generate_backup_codes()
            
            # Сохраняем backup коды
            for code in backup_codes:
                backup_code = TwoFactorBackupCode(
                    two_factor_auth_id=two_factor_auth.id,
                    code=code,
                    used=False
                )
                db.add(backup_code)

            # Генерируем токен восстановления
            recovery_token = self.generate_recovery_token()
            recovery_expires = datetime.utcnow() + timedelta(hours=self.recovery_expiry_hours)
            
            recovery = TwoFactorRecovery(
                two_factor_auth_id=two_factor_auth.id,
                recovery_type="email" if recovery_email else "phone",
                recovery_value=recovery_email or recovery_phone,
                recovery_token=recovery_token,
                expires_at=recovery_expires
            )
            db.add(recovery)

            db.commit()

            # Генерируем QR код
            qr_code_url = self.generate_qr_code(secret, user.email or user.username)

            return {
                "qr_code_url": qr_code_url,
                "secret_key": secret,
                "backup_codes": backup_codes,
                "recovery_token": recovery_token,
                "expires_at": recovery_expires.isoformat()
            }

        except Exception as e:
            db.rollback()
            logger.error(f"Error setting up 2FA: {e}")
            raise

    def verify_totp_setup(
        self, 
        db: Session, 
        user_id: int, 
        totp_code: str
    ) -> bool:
        """Верифицирует настройку TOTP"""
        try:
            two_factor_auth = db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id).first()
            if not two_factor_auth or not two_factor_auth.totp_secret:
                return False

            # Проверяем код
            if self.verify_totp_code(two_factor_auth.totp_secret, totp_code):
                two_factor_auth.totp_verified = True
                two_factor_auth.totp_enabled = True
                two_factor_auth.backup_codes_generated = True
                two_factor_auth.backup_codes_count = self.backup_codes_count
                two_factor_auth.last_used = datetime.utcnow()
                
                db.commit()
                return True
            
            return False

        except Exception as e:
            db.rollback()
            logger.error(f"Error verifying TOTP setup: {e}")
            return False

    def verify_two_factor(
        self, 
        db: Session, 
        user_id: int, 
        totp_code: Optional[str] = None,
        backup_code: Optional[str] = None,
        recovery_token: Optional[str] = None,
        device_fingerprint: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """Верифицирует 2FA код"""
        try:
            two_factor_auth = db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id).first()
            if not two_factor_auth or not two_factor_auth.totp_enabled:
                return False, "2FA not enabled", None

            method_used = None
            success = False

            # Проверяем TOTP код
            if totp_code and two_factor_auth.totp_secret:
                if self.verify_totp_code(two_factor_auth.totp_secret, totp_code):
                    success = True
                    method_used = "totp"

            # Проверяем backup код
            elif backup_code:
                backup_code_obj = db.query(TwoFactorBackupCode).filter(
                    and_(
                        TwoFactorBackupCode.two_factor_auth_id == two_factor_auth.id,
                        TwoFactorBackupCode.code == backup_code,
                        TwoFactorBackupCode.used == False
                    )
                ).first()
                
                if backup_code_obj:
                    backup_code_obj.used = True
                    backup_code_obj.used_at = datetime.utcnow()
                    success = True
                    method_used = "backup_code"

            # Проверяем токен восстановления
            elif recovery_token:
                recovery = db.query(TwoFactorRecovery).filter(
                    and_(
                        TwoFactorRecovery.two_factor_auth_id == two_factor_auth.id,
                        TwoFactorRecovery.recovery_token == recovery_token,
                        TwoFactorRecovery.verified == False,
                        TwoFactorRecovery.expires_at > datetime.utcnow()
                    )
                ).first()
                
                if recovery:
                    recovery.verified = True
                    recovery.verified_at = datetime.utcnow()
                    success = True
                    method_used = "recovery"

            if success:
                # Обновляем время последнего использования
                two_factor_auth.last_used = datetime.utcnow()
                
                # Создаем сессию если нужно
                session_token = None
                if device_fingerprint:
                    session_token = self.create_trusted_session(
                        db, user_id, device_fingerprint, ip_address, user_agent
                    )
                
                db.commit()
                return True, "Verification successful", session_token

            return False, "Invalid verification code", None

        except Exception as e:
            db.rollback()
            logger.error(f"Error verifying 2FA: {e}")
            return False, f"Verification error: {str(e)}", None

    def create_trusted_session(
        self, 
        db: Session, 
        user_id: int, 
        device_fingerprint: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_name: Optional[str] = None
    ) -> str:
        """Создает доверенную сессию"""
        try:
            # Генерируем токен сессии
            session_token = secrets.token_urlsafe(32)
            expires_at = datetime.utcnow() + timedelta(hours=self.session_expiry_hours)

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
                device_name=device_name
            )
            db.add(session)

            # Создаем или обновляем устройство
            device = db.query(TwoFactorDevice).filter(
                TwoFactorDevice.device_fingerprint == device_fingerprint
            ).first()

            if device:
                device.last_used = datetime.utcnow()
                device.trusted = True
                device.active = True
            else:
                device = TwoFactorDevice(
                    user_id=user_id,
                    device_name=device_name or "Unknown Device",
                    device_type="desktop",  # Можно определить по user_agent
                    device_fingerprint=device_fingerprint,
                    trusted=True,
                    active=True,
                    ip_address=ip_address,
                    user_agent=user_agent
                )
                db.add(device)

            db.commit()
            return session_token

        except Exception as e:
            db.rollback()
            logger.error(f"Error creating trusted session: {e}")
            raise

    def disable_two_factor_auth(
        self, 
        db: Session, 
        user_id: int, 
        password: str,
        totp_code: Optional[str] = None,
        backup_code: Optional[str] = None
    ) -> bool:
        """Отключает 2FA для пользователя"""
        try:
            # Получаем пользователя и проверяем пароль
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not verify_password(password, user.hashed_password):
                return False

            # Проверяем 2FA код если нужно
            if totp_code or backup_code:
                success, _, _ = self.verify_two_factor(
                    db, user_id, totp_code, backup_code
                )
                if not success:
                    return False

            # Удаляем все данные 2FA
            two_factor_auth = db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id).first()
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

            db.commit()
            return True

        except Exception as e:
            db.rollback()
            logger.error(f"Error disabling 2FA: {e}")
            return False

    def get_two_factor_status(self, db: Session, user_id: int) -> Dict[str, Any]:
        """Получает статус 2FA для пользователя"""
        try:
            two_factor_auth = db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id).first()
            
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
                    "last_used": None
                }

            # Подсчитываем оставшиеся backup коды
            remaining_backup_codes = db.query(TwoFactorBackupCode).filter(
                and_(
                    TwoFactorBackupCode.two_factor_auth_id == two_factor_auth.id,
                    TwoFactorBackupCode.used == False
                )
            ).count()

            # Подсчитываем доверенные устройства
            trusted_devices = db.query(TwoFactorDevice).filter(
                and_(
                    TwoFactorDevice.user_id == user_id,
                    TwoFactorDevice.trusted == True,
                    TwoFactorDevice.active == True
                )
            ).count()

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
                "last_used": two_factor_auth.last_used
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
                "last_used": None
            }

    def regenerate_backup_codes(self, db: Session, user_id: int) -> List[str]:
        """Перегенерирует backup коды"""
        try:
            two_factor_auth = db.query(TwoFactorAuth).filter(TwoFactorAuth.user_id == user_id).first()
            if not two_factor_auth:
                raise ValueError("2FA not found")

            # Удаляем старые коды
            db.query(TwoFactorBackupCode).filter(
                TwoFactorBackupCode.two_factor_auth_id == two_factor_auth.id
            ).delete()

            # Генерируем новые коды
            backup_codes = self.generate_backup_codes()
            
            for code in backup_codes:
                backup_code = TwoFactorBackupCode(
                    two_factor_auth_id=two_factor_auth.id,
                    code=code,
                    used=False
                )
                db.add(backup_code)

            two_factor_auth.backup_codes_generated = True
            two_factor_auth.backup_codes_count = len(backup_codes)

            db.commit()
            return backup_codes

        except Exception as e:
            db.rollback()
            logger.error(f"Error regenerating backup codes: {e}")
            raise

    async def send_sms_code(
        self, 
        phone: str, 
        code: str, 
        provider_type: Optional[SMSProviderType] = None
    ) -> Dict[str, Any]:
        """Отправить SMS код для 2FA"""
        try:
            response = await self.sms_manager.send_2fa_code(
                phone=phone,
                code=code,
                provider_type=provider_type
            )
            
            return {
                "success": response.success,
                "message_id": response.message_id,
                "error": response.error,
                "provider": response.provider
            }
            
        except Exception as e:
            logger.error(f"Error sending SMS code: {e}")
            return {
                "success": False,
                "error": str(e),
                "provider": "unknown"
            }

    async def send_email_code(
        self, 
        email: str, 
        code: str, 
        user_name: Optional[str] = None
    ) -> Dict[str, Any]:
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
                text_content=text_content
            )
            
            return {
                "success": result.get("success", False),
                "message_id": result.get("message_id"),
                "error": result.get("error"),
                "provider": "email"
            }
            
        except Exception as e:
            logger.error(f"Error sending email code: {e}")
            return {
                "success": False,
                "error": str(e),
                "provider": "email"
            }

    def generate_verification_code(self, length: int = 6) -> str:
        """Генерирует код верификации"""
        return ''.join([str(secrets.randbelow(10)) for _ in range(length)])

    async def send_verification_code(
        self,
        method: str,  # 'sms' или 'email'
        contact: str,  # номер телефона или email
        user_name: Optional[str] = None,
        provider_type: Optional[SMSProviderType] = None
    ) -> Dict[str, Any]:
        """Отправить код верификации по SMS или email"""
        try:
            code = self.generate_verification_code()
            
            if method == 'sms':
                result = await self.send_sms_code(
                    phone=contact,
                    code=code,
                    provider_type=provider_type
                )
            elif method == 'email':
                result = await self.send_email_code(
                    email=contact,
                    code=code,
                    user_name=user_name
                )
            else:
                return {
                    "success": False,
                    "error": "Invalid method. Use 'sms' or 'email'",
                    "provider": "unknown"
                }
            
            if result["success"]:
                result["code"] = code  # Возвращаем код для сохранения в сессии
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending verification code: {e}")
            return {
                "success": False,
                "error": str(e),
                "provider": "unknown"
            }


# Глобальный экземпляр сервиса
two_factor_service = TwoFactorService()

def get_two_factor_service() -> TwoFactorService:
    """Получить экземпляр сервиса 2FA"""
    return two_factor_service
