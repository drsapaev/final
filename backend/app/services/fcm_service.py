"""
Firebase Cloud Messaging (FCM) сервис для push уведомлений
Поддерживает HTTP v1 API
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import httpx
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class FCMResponse(BaseModel):
    """Ответ FCM"""

    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


class FCMService:
    """Сервис для работы с Firebase Cloud Messaging (HTTP v1 API)"""

    def __init__(self):
        self.project_id = getattr(settings, 'FCM_PROJECT_ID', None)
        self.fcm_url = f"https://fcm.googleapis.com/v1/projects/{self.project_id}/messages:send"
        
        # OAuth2 credentials
        self.credentials = None
        self.access_token = None
        self.token_expiry = 0
        
        self._load_credentials()

    def _load_credentials(self):
        """Загрузка учетных данных сервисного аккаунта"""
        try:
            # Пытаемся найти путь к JSON файлу в env или settings
            cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            
            if cred_path and os.path.exists(cred_path):
                scopes = ['https://www.googleapis.com/auth/firebase.messaging']
                self.credentials = service_account.Credentials.from_service_account_file(
                    cred_path, scopes=scopes
                )
                logger.info("FCM credentials loaded successfully")
            else:
                logger.warning("GOOGLE_APPLICATION_CREDENTIALS not found or invalid. FCM disabled.")
                
        except Exception as e:
            logger.error(f"Failed to load FCM credentials: {e}")

    def _get_access_token(self) -> Optional[str]:
        """Получение валидного OAuth2 токена (синхронно, так как редко)"""
        if not self.credentials:
            return None
            
        current_time = time.time()
        
        if self.access_token and current_time < self.token_expiry - 60:
            return self.access_token
            
        try:
            self.credentials.refresh(Request())
            self.access_token = self.credentials.token
            # Токен обычно живет 1 час
            self.token_expiry = current_time + 3500 
            return self.access_token
        except Exception as e:
            logger.error(f"Failed to refresh FCM token: {e}")
            return None

    @property
    def active(self) -> bool:
        return bool(self.credentials and self.project_id)

    async def send_notification(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image: Optional[str] = None,
        sound: str = "default",
        badge: Optional[int] = None,
    ) -> FCMResponse:
        """Отправка push уведомления (HTTP v1)"""

        if not self.active:
            return FCMResponse(success=False, error="FCM service not configured")
        
        token = self._get_access_token()
        if not token:
            return FCMResponse(success=False, error="Failed to get access token")

        try:
            # Формируем payload для v1 API
            message = {
                "token": device_token,
                "notification": {
                    "title": title,
                    "body": body
                },
                "android": {
                    "notification": {
                        "sound": sound
                    },
                    "priority": "high"
                },
                "apns": {
                    "payload": {
                        "aps": {
                            "sound": sound,
                            "badge": badge if badge is not None else 0
                        }
                    }
                }
            }

            if image:
                message["notification"]["image"] = image

            if data:
                # Все значения data должны быть строками
                message["data"] = {k: str(v) for k, v in data.items()}

            payload = {"message": message}

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.fcm_url, json=payload, headers=headers
                )
                
                response_data = response.json()

                if response.status_code == 200:
                    # Успешный ответ v1 содержит name (message_id)
                    return FCMResponse(
                        success=True,
                        message_id=response_data.get("name"),
                    )
                else:
                    error_data = response_data.get("error", {})
                    return FCMResponse(
                        success=False,
                        error=error_data.get("message", "Unknown error"),
                        error_code=str(error_data.get("code")),
                    )

        except Exception as e:
            logger.error(f"FCM send error: {e}")
            return FCMResponse(success=False, error=str(e))

    async def send_multicast(
        self,
        device_tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Массовая отправка (эмуляция через индивидуальные запросы, т.к. v1 не поддерживает multicast)
        """
        results = []
        sent_count = 0
        failed_count = 0
        
        # Отправляем параллельно
        tasks = [
            self.send_notification(token, title, body, data, **kwargs)
            for token in device_tokens
        ]
        
        # Ограничиваем concurrency если нужно, но пока просто gather
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, response in enumerate(responses):
            if isinstance(response, FCMResponse):
                if response.success:
                    sent_count += 1
                    results.append({"token_index": i, "success": True, "message_id": response.message_id})
                else:
                    failed_count += 1
                    results.append({"token_index": i, "success": False, "error": response.error})
            else:
                failed_count += 1
                results.append({"token_index": i, "success": False, "error": str(response)})
                
        return {
            "success": sent_count > 0,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "total_count": len(device_tokens),
            "results": results
        }


# Глобальный экземпляр FCM сервиса
fcm_service = FCMService()


def get_fcm_service() -> FCMService:
    """Получить экземпляр FCM сервиса"""
    return fcm_service

