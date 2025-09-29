"""
SMS провайдеры для отправки SMS сообщений
Поддержка Eskiz, PlayMobile и других провайдеров
"""
import asyncio
import logging
import aiohttp
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from app.core.config import settings

logger = logging.getLogger(__name__)


class SMSProviderType(str, Enum):
    """Типы SMS провайдеров"""
    ESKIZ = "eskiz"
    PLAYMOBILE = "playmobile"
    MOCK = "mock"


@dataclass
class SMSMessage:
    """Структура SMS сообщения"""
    phone: str
    text: str
    sender: Optional[str] = None
    callback_url: Optional[str] = None


@dataclass
class SMSResponse:
    """Ответ от SMS провайдера"""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    provider: Optional[str] = None
    cost: Optional[float] = None
    status: Optional[str] = None


class BaseSMSProvider(ABC):
    """Базовый класс для SMS провайдеров"""
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None, **kwargs):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = kwargs.get('base_url', '')
        self.sender = kwargs.get('sender', 'Clinic')
        self.timeout = kwargs.get('timeout', 30)
        
    @abstractmethod
    async def send_sms(self, message: SMSMessage) -> SMSResponse:
        """Отправить SMS сообщение"""
        pass
    
    @abstractmethod
    async def get_balance(self) -> Dict[str, Any]:
        """Получить баланс аккаунта"""
        pass
    
    @abstractmethod
    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        """Получить статус сообщения"""
        pass


class EskizSMSProvider(BaseSMSProvider):
    """SMS провайдер Eskiz (Узбекистан)"""
    
    def __init__(self, api_key: str, api_secret: str, **kwargs):
        super().__init__(api_key, api_secret, **kwargs)
        self.base_url = "https://notify.eskiz.uz/api"
        self.auth_token = None
        self.token_expires = None
        
    async def _get_auth_token(self) -> str:
        """Получить токен авторизации"""
        if self.auth_token and self.token_expires and datetime.now() < self.token_expires:
            return self.auth_token
            
        async with aiohttp.ClientSession() as session:
            auth_data = {
                "email": self.api_key,
                "password": self.api_secret
            }
            
            async with session.post(
                f"{self.base_url}/auth/login",
                json=auth_data,
                timeout=self.timeout
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    self.auth_token = data.get("data", {}).get("token")
                    # Токен действует 30 дней
                    self.token_expires = datetime.now() + timedelta(days=29)
                    return self.auth_token
                else:
                    error_text = await response.text()
                    raise Exception(f"Eskiz auth failed: {error_text}")
    
    async def send_sms(self, message: SMSMessage) -> SMSResponse:
        """Отправить SMS через Eskiz"""
        try:
            token = await self._get_auth_token()
            
            # Форматируем номер телефона (убираем + и пробелы)
            phone = message.phone.replace('+', '').replace(' ', '').replace('-', '')
            
            sms_data = {
                "mobile_phone": phone,
                "message": message.text,
                "from": message.sender or self.sender,
                "callback_url": message.callback_url
            }
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/message/sms/send",
                    json=sms_data,
                    headers=headers,
                    timeout=self.timeout
                ) as response:
                    data = await response.json()
                    
                    if response.status == 200 and data.get("status") == "success":
                        return SMSResponse(
                            success=True,
                            message_id=str(data.get("data", {}).get("id")),
                            provider="eskiz",
                            status="sent"
                        )
                    else:
                        return SMSResponse(
                            success=False,
                            error=data.get("message", "Unknown error"),
                            provider="eskiz"
                        )
                        
        except Exception as e:
            logger.error(f"Eskiz SMS error: {str(e)}")
            return SMSResponse(
                success=False,
                error=str(e),
                provider="eskiz"
            )
    
    async def get_balance(self) -> Dict[str, Any]:
        """Получить баланс Eskiz"""
        try:
            token = await self._get_auth_token()
            
            headers = {
                "Authorization": f"Bearer {token}"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/user/get-limit",
                    headers=headers,
                    timeout=self.timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "success": True,
                            "balance": data.get("data", {}).get("sms_count", 0),
                            "currency": "SMS",
                            "provider": "eskiz"
                        }
                    else:
                        return {
                            "success": False,
                            "error": "Failed to get balance",
                            "provider": "eskiz"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "provider": "eskiz"
            }
    
    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        """Получить статус сообщения Eskiz"""
        try:
            token = await self._get_auth_token()
            
            headers = {
                "Authorization": f"Bearer {token}"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/message/sms/status/{message_id}",
                    headers=headers,
                    timeout=self.timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "success": True,
                            "status": data.get("data", {}).get("status"),
                            "provider": "eskiz"
                        }
                    else:
                        return {
                            "success": False,
                            "error": "Failed to get status",
                            "provider": "eskiz"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "provider": "eskiz"
            }


class PlayMobileSMSProvider(BaseSMSProvider):
    """SMS провайдер PlayMobile (Узбекистан)"""
    
    def __init__(self, api_key: str, api_secret: str, **kwargs):
        super().__init__(api_key, api_secret, **kwargs)
        self.base_url = "https://send.playmobile.uz/api"
        
    async def send_sms(self, message: SMSMessage) -> SMSResponse:
        """Отправить SMS через PlayMobile"""
        try:
            # Форматируем номер телефона
            phone = message.phone.replace('+', '').replace(' ', '').replace('-', '')
            
            sms_data = {
                "messages": [{
                    "recipient": phone,
                    "message-id": f"msg_{datetime.now().timestamp()}",
                    "sms": {
                        "originator": message.sender or self.sender,
                        "content": {
                            "text": message.text
                        }
                    }
                }]
            }
            
            headers = {
                "Authorization": f"Basic {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/v1/send-sms",
                    json=sms_data,
                    headers=headers,
                    timeout=self.timeout
                ) as response:
                    data = await response.json()
                    
                    if response.status == 200:
                        results = data.get("results", [])
                        if results and results[0].get("status") == "0":
                            return SMSResponse(
                                success=True,
                                message_id=results[0].get("message-id"),
                                provider="playmobile",
                                status="sent"
                            )
                    
                    return SMSResponse(
                        success=False,
                        error=data.get("error", "Unknown error"),
                        provider="playmobile"
                    )
                        
        except Exception as e:
            logger.error(f"PlayMobile SMS error: {str(e)}")
            return SMSResponse(
                success=False,
                error=str(e),
                provider="playmobile"
            )
    
    async def get_balance(self) -> Dict[str, Any]:
        """Получить баланс PlayMobile"""
        try:
            headers = {
                "Authorization": f"Basic {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/v1/balance",
                    headers=headers,
                    timeout=self.timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "success": True,
                            "balance": data.get("balance", 0),
                            "currency": data.get("currency", "UZS"),
                            "provider": "playmobile"
                        }
                    else:
                        return {
                            "success": False,
                            "error": "Failed to get balance",
                            "provider": "playmobile"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "provider": "playmobile"
            }
    
    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        """Получить статус сообщения PlayMobile"""
        try:
            headers = {
                "Authorization": f"Basic {self.api_key}",
                "Content-Type": "application/json"
            }
            
            params = {
                "message-id": message_id
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/v1/message-status",
                    headers=headers,
                    params=params,
                    timeout=self.timeout
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "success": True,
                            "status": data.get("status"),
                            "provider": "playmobile"
                        }
                    else:
                        return {
                            "success": False,
                            "error": "Failed to get status",
                            "provider": "playmobile"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "provider": "playmobile"
            }


class MockSMSProvider(BaseSMSProvider):
    """Mock SMS провайдер для тестирования"""
    
    def __init__(self, api_key: str = "mock", **kwargs):
        super().__init__(api_key, **kwargs)
        
    async def send_sms(self, message: SMSMessage) -> SMSResponse:
        """Имитация отправки SMS"""
        await asyncio.sleep(0.5)  # Имитация задержки
        
        # Имитируем успешную отправку
        return SMSResponse(
            success=True,
            message_id=f"mock_{datetime.now().timestamp()}",
            provider="mock",
            status="sent"
        )
    
    async def get_balance(self) -> Dict[str, Any]:
        """Имитация получения баланса"""
        return {
            "success": True,
            "balance": 1000,
            "currency": "SMS",
            "provider": "mock"
        }
    
    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        """Имитация получения статуса"""
        return {
            "success": True,
            "status": "delivered",
            "provider": "mock"
        }


class SMSManager:
    """Менеджер для работы с SMS провайдерами"""
    
    def __init__(self):
        self.providers: Dict[SMSProviderType, BaseSMSProvider] = {}
        self.default_provider: Optional[SMSProviderType] = None
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Инициализация доступных провайдеров"""
        # Eskiz провайдер
        eskiz_email = getattr(settings, "ESKIZ_EMAIL", None)
        eskiz_password = getattr(settings, "ESKIZ_PASSWORD", None)
        if eskiz_email and eskiz_password:
            try:
                self.providers[SMSProviderType.ESKIZ] = EskizSMSProvider(
                    api_key=eskiz_email,
                    api_secret=eskiz_password,
                    sender=getattr(settings, "SMS_SENDER", "Clinic")
                )
                if not self.default_provider:
                    self.default_provider = SMSProviderType.ESKIZ
                logger.info("Initialized Eskiz SMS provider")
            except Exception as e:
                logger.error(f"Failed to initialize Eskiz provider: {str(e)}")
        
        # PlayMobile провайдер
        playmobile_key = getattr(settings, "PLAYMOBILE_API_KEY", None)
        playmobile_secret = getattr(settings, "PLAYMOBILE_API_SECRET", None)
        if playmobile_key and playmobile_secret:
            try:
                self.providers[SMSProviderType.PLAYMOBILE] = PlayMobileSMSProvider(
                    api_key=playmobile_key,
                    api_secret=playmobile_secret,
                    sender=getattr(settings, "SMS_SENDER", "Clinic")
                )
                if not self.default_provider:
                    self.default_provider = SMSProviderType.PLAYMOBILE
                logger.info("Initialized PlayMobile SMS provider")
            except Exception as e:
                logger.error(f"Failed to initialize PlayMobile provider: {str(e)}")
        
        # Mock провайдер (всегда доступен для тестирования)
        self.providers[SMSProviderType.MOCK] = MockSMSProvider()
        if not self.default_provider:
            self.default_provider = SMSProviderType.MOCK
        
        logger.info(f"SMS Manager initialized with {len(self.providers)} providers")
    
    def get_provider(self, provider_type: Optional[SMSProviderType] = None) -> Optional[BaseSMSProvider]:
        """Получить провайдер по типу или default"""
        if provider_type:
            return self.providers.get(provider_type)
        elif self.default_provider:
            return self.providers.get(self.default_provider)
        return None
    
    async def send_sms(
        self, 
        phone: str, 
        text: str, 
        provider_type: Optional[SMSProviderType] = None,
        sender: Optional[str] = None
    ) -> SMSResponse:
        """Отправить SMS сообщение"""
        provider = self.get_provider(provider_type)
        if not provider:
            return SMSResponse(
                success=False,
                error="No SMS provider available",
                provider="none"
            )
        
        message = SMSMessage(
            phone=phone,
            text=text,
            sender=sender
        )
        
        return await provider.send_sms(message)
    
    async def send_2fa_code(
        self, 
        phone: str, 
        code: str, 
        provider_type: Optional[SMSProviderType] = None
    ) -> SMSResponse:
        """Отправить код 2FA по SMS"""
        text = f"Ваш код подтверждения: {code}. Код действителен 5 минут. Никому не сообщайте этот код."
        
        return await self.send_sms(
            phone=phone,
            text=text,
            provider_type=provider_type
        )
    
    def get_available_providers(self) -> List[str]:
        """Получить список доступных провайдеров"""
        return [p.value for p in self.providers.keys()]
    
    async def get_balance(self, provider_type: Optional[SMSProviderType] = None) -> Dict[str, Any]:
        """Получить баланс провайдера"""
        provider = self.get_provider(provider_type)
        if not provider:
            return {
                "success": False,
                "error": "No SMS provider available"
            }
        
        return await provider.get_balance()


# Глобальный экземпляр менеджера
sms_manager = SMSManager()


def get_sms_manager() -> SMSManager:
    """Получить экземпляр SMS менеджера"""
    return sms_manager


