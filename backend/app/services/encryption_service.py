"""
AES-256 Encryption Service
Сервис для шифрования чувствительных данных
"""
import os
import base64
import hashlib
import logging
from typing import Optional, Tuple

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

logger = logging.getLogger(__name__)


class AES256Encryption:
    """
    AES-256 GCM шифрование для защиты чувствительных данных
    
    Использует:
    - AES-256 в режиме GCM (authenticated encryption)
    - 256-битный ключ из переменной окружения
    - 96-битный IV (генерируется случайно для каждого шифрования)
    - 128-битный authentication tag
    """
    
    # Размер ключа в байтах (256 бит = 32 байта)
    KEY_SIZE = 32
    # Размер IV (nonce) для GCM (96 бит = 12 байт)
    IV_SIZE = 12
    # Размер authentication tag
    TAG_SIZE = 16
    
    def __init__(self, key: Optional[str] = None):
        """
        Инициализация с ключом шифрования
        
        Args:
            key: 32-байтный ключ или строка для деривации ключа.
                 Если не указан, используется ENCRYPTION_KEY из env.
        """
        if key is None:
            key = os.getenv("ENCRYPTION_KEY", os.getenv("SECRET_KEY", ""))
        
        if not key:
            raise ValueError("Encryption key is required. Set ENCRYPTION_KEY env variable.")
        
        # Деривация 256-битного ключа из произвольной строки
        self.key = self._derive_key(key)
    
    def _derive_key(self, key_material: str) -> bytes:
        """
        Деривация 256-битного ключа из строки
        Использует SHA-256 для получения ключа фиксированной длины
        """
        if isinstance(key_material, bytes) and len(key_material) == self.KEY_SIZE:
            return key_material
        
        return hashlib.sha256(key_material.encode()).digest()
    
    def encrypt(self, plaintext: str) -> str:
        """
        Шифрует строку и возвращает base64-кодированный результат
        
        Args:
            plaintext: Строка для шифрования
            
        Returns:
            Base64 строка в формате: IV || ciphertext || tag
        """
        try:
            # Генерируем случайный IV
            iv = os.urandom(self.IV_SIZE)
            
            # Создаём шифр GCM
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.GCM(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            
            # Шифруем данные
            plaintext_bytes = plaintext.encode('utf-8')
            ciphertext = encryptor.update(plaintext_bytes) + encryptor.finalize()
            
            # Получаем authentication tag
            tag = encryptor.tag
            
            # Собираем результат: IV + ciphertext + tag
            encrypted_data = iv + ciphertext + tag
            
            # Кодируем в base64
            return base64.b64encode(encrypted_data).decode('ascii')
            
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Расшифровывает base64-кодированные данные
        
        Args:
            encrypted_data: Base64 строка (IV || ciphertext || tag)
            
        Returns:
            Расшифрованная строка
        """
        try:
            # Декодируем из base64
            data = base64.b64decode(encrypted_data.encode('ascii'))
            
            # Извлекаем компоненты
            iv = data[:self.IV_SIZE]
            tag = data[-self.TAG_SIZE:]
            ciphertext = data[self.IV_SIZE:-self.TAG_SIZE]
            
            # Создаём шифр GCM с tag
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.GCM(iv, tag),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            # Расшифровываем
            plaintext_bytes = decryptor.update(ciphertext) + decryptor.finalize()
            
            return plaintext_bytes.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise
    
    def encrypt_dict(self, data: dict, fields: list) -> dict:
        """
        Шифрует указанные поля в словаре
        
        Args:
            data: Исходный словарь
            fields: Список полей для шифрования
            
        Returns:
            Словарь с зашифрованными полями
        """
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                result[field] = self.encrypt(str(result[field]))
        return result
    
    def decrypt_dict(self, data: dict, fields: list) -> dict:
        """
        Расшифровывает указанные поля в словаре
        
        Args:
            data: Словарь с зашифрованными полями
            fields: Список полей для расшифровки
            
        Returns:
            Словарь с расшифрованными полями
        """
        result = data.copy()
        for field in fields:
            if field in result and result[field]:
                try:
                    result[field] = self.decrypt(str(result[field]))
                except Exception:
                    # Если расшифровка не удалась, оставляем как есть
                    pass
        return result


# Поля, которые должны быть зашифрованы в БД
SENSITIVE_FIELDS = [
    'passport_number',
    'inn',  # ИНН
    'snils',  # СНИЛС (если применимо)
    'doc_number',  # Номер документа
    'bank_account',
    'credit_card',
]

# Глобальный экземпляр (ленивая инициализация)
_encryption_instance: Optional[AES256Encryption] = None


def get_encryption() -> AES256Encryption:
    """Получить глобальный экземпляр шифрования"""
    global _encryption_instance
    if _encryption_instance is None:
        try:
            _encryption_instance = AES256Encryption()
        except ValueError as e:
            logger.warning(f"Encryption not available: {e}")
            raise
    return _encryption_instance


def encrypt_sensitive_data(data: str) -> str:
    """Шифрует чувствительные данные"""
    return get_encryption().encrypt(data)


def decrypt_sensitive_data(data: str) -> str:
    """Расшифровывает чувствительные данные"""
    return get_encryption().decrypt(data)
