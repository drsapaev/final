import base64
import hashlib
import io
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

import pyotp
import qrcode


class TwoFactorAuthService:
    """Сервис для двухфакторной аутентификации"""

    def __init__(self):
        self.issuer_name = "Clinic System"
        self.algorithm = "sha1"
        self.digits = 6
        self.interval = 30  # секунды

    def generate_secret(self) -> str:
        """Генерация секретного ключа для TOTP"""
        return pyotp.random_base32()

    def generate_totp_uri(
        self, secret: str, username: str, email: Optional[str] = None
    ) -> str:
        """Генерация URI для TOTP приложения"""
        totp = pyotp.TOTP(
            secret, digits=self.digits, interval=self.interval, algorithm=self.algorithm
        )

        # Формируем URI для TOTP приложения
        uri = totp.provisioning_uri(name=username, issuer_name=self.issuer_name)

        return uri

    def generate_qr_code(self, totp_uri: str) -> str:
        """Генерация QR-кода для TOTP URI"""
        # Создаём QR-код
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(totp_uri)
        qr.make(fit=True)

        # Создаём изображение
        img = qr.make_image(fill_color="black", back_color="white")

        # Конвертируем в base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_str}"

    def verify_totp(self, secret: str, token: str, window: int = 1) -> bool:
        """Проверка TOTP токена"""
        totp = pyotp.TOTP(
            secret, digits=self.digits, interval=self.interval, algorithm=self.algorithm
        )

        return totp.verify(token, valid_window=window)

    def generate_backup_codes(self, count: int = 10) -> Tuple[list, list]:
        """Генерация резервных кодов"""
        backup_codes = []
        hashed_codes = []

        for _ in range(count):
            # Генерируем код из 8 символов
            code = secrets.token_hex(4).upper()
            backup_codes.append(code)

            # Хешируем код для хранения в БД
            hashed_code = hashlib.sha256(code.encode()).hexdigest()
            hashed_codes.append(hashed_code)

        return backup_codes, hashed_codes

    def verify_backup_code(self, code: str, hashed_codes: list) -> bool:
        """Проверка резервного кода"""
        hashed_code = hashlib.sha256(code.encode()).hexdigest()
        return hashed_code in hashed_codes

    def get_current_totp(self, secret: str) -> str:
        """Получение текущего TOTP токена (для тестирования)"""
        totp = pyotp.TOTP(
            secret, digits=self.digits, interval=self.interval, algorithm=self.algorithm
        )

        return totp.now()

    def get_remaining_time(self) -> int:
        """Получение оставшегося времени до следующего токена"""
        return self.interval - (datetime.now().timestamp() % self.interval)

    def setup_2fa(self, username: str, email: Optional[str] = None) -> dict:
        """Настройка 2FA для пользователя"""
        # Генерируем секретный ключ
        secret = self.generate_secret()

        # Генерируем URI для TOTP
        totp_uri = self.generate_totp_uri(secret, username, email)

        # Генерируем QR-код
        qr_code = self.generate_qr_code(totp_uri)

        # Генерируем резервные коды
        backup_codes, hashed_codes = self.generate_backup_codes()

        return {
            "secret": secret,
            "totp_uri": totp_uri,
            "qr_code": qr_code,
            "backup_codes": backup_codes,
            "hashed_backup_codes": hashed_codes,
            "algorithm": self.algorithm,
            "digits": self.digits,
            "interval": self.interval,
            "issuer": self.issuer_name,
        }

    def verify_2fa_setup(self, secret: str, token: str) -> bool:
        """Проверка настройки 2FA"""
        return self.verify_totp(secret, token)

    def authenticate_with_2fa(
        self, secret: str, token: str, backup_codes: list, used_backup_codes: list
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Аутентификация с 2FA

        Returns:
            (success, message, used_backup_code)
        """
        # Сначала пробуем TOTP
        if self.verify_totp(secret, token):
            return True, "TOTP токен подтверждён", None

        # Если TOTP не прошёл, пробуем резервный код
        if self.verify_backup_code(token, backup_codes):
            # Проверяем, не использован ли уже этот код
            hashed_token = hashlib.sha256(token.encode()).hexdigest()
            if hashed_token not in used_backup_codes:
                return True, "Резервный код подтверждён", hashed_token

        return False, "Неверный токен или резервный код", None

    def is_2fa_enabled(self, secret: Optional[str]) -> bool:
        """Проверка, включена ли 2FA"""
        return secret is not None and secret.strip() != ""

    def get_2fa_info(self, secret: str) -> dict:
        """Получение информации о 2FA"""
        if not self.is_2fa_enabled(secret):
            return {"enabled": False}

        totp = pyotp.TOTP(
            secret, digits=self.digits, interval=self.interval, algorithm=self.algorithm
        )

        return {
            "enabled": True,
            "algorithm": self.algorithm,
            "digits": self.digits,
            "interval": self.interval,
            "issuer": self.issuer_name,
            "remaining_time": self.get_remaining_time(),
            "current_token": totp.now(),
        }


# Создаём глобальный экземпляр сервиса
two_factor_auth_service = TwoFactorAuthService()
