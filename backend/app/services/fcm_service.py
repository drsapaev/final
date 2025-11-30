"""
Firebase Cloud Messaging (FCM) сервис для push уведомлений
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class FCMMessage(BaseModel):
    """FCM сообщение"""

    token: str
    title: str
    body: str
    data: Optional[Dict[str, str]] = None
    image: Optional[str] = None
    click_action: Optional[str] = None
    sound: str = "default"
    badge: Optional[int] = None


class FCMResponse(BaseModel):
    """Ответ FCM"""

    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None


class FCMService:
    """Сервис для работы с Firebase Cloud Messaging"""

    def __init__(self):
        self.server_key = getattr(settings, 'FCM_SERVER_KEY', None)
        self.sender_id = getattr(settings, 'FCM_SENDER_ID', None)
        self.fcm_url = "https://fcm.googleapis.com/fcm/send"
        self.active = bool(self.server_key)

        if not self.active:
            logger.warning("FCM не настроен: отсутствует FCM_SERVER_KEY")

    async def send_notification(
        self,
        device_token: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image: Optional[str] = None,
        click_action: Optional[str] = None,
        sound: str = "default",
        badge: Optional[int] = None,
    ) -> FCMResponse:
        """Отправка push уведомления на одно устройство"""

        if not self.active:
            return FCMResponse(success=False, error="FCM service not configured")

        try:
            # Подготавливаем данные для FCM
            notification_data = {"title": title, "body": body, "sound": sound}

            if image:
                notification_data["image"] = image

            if click_action:
                notification_data["click_action"] = click_action

            if badge is not None:
                notification_data["badge"] = str(badge)

            # Подготавливаем payload
            payload = {
                "to": device_token,
                "notification": notification_data,
                "priority": "high",
                "content_available": True,
            }

            # Добавляем дополнительные данные
            if data:
                # Конвертируем все значения в строки (FCM требует)
                string_data = {k: str(v) for k, v in data.items()}
                payload["data"] = string_data

            # Отправляем запрос
            headers = {
                "Authorization": f"key={self.server_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.fcm_url, json=payload, headers=headers
                )

                response_data = response.json()

                if response.status_code == 200:
                    if response_data.get("success", 0) > 0:
                        return FCMResponse(
                            success=True,
                            message_id=response_data.get("results", [{}])[0].get(
                                "message_id"
                            ),
                        )
                    else:
                        error_info = response_data.get("results", [{}])[0].get(
                            "error", "Unknown error"
                        )
                        return FCMResponse(
                            success=False, error=error_info, error_code=error_info
                        )
                else:
                    return FCMResponse(
                        success=False,
                        error=f"HTTP {response.status_code}: {response_data.get('error', 'Unknown error')}",
                    )

        except httpx.TimeoutException:
            logger.error("FCM request timeout")
            return FCMResponse(success=False, error="Request timeout")
        except Exception as e:
            logger.error(f"FCM send error: {e}")
            return FCMResponse(success=False, error=str(e))

    async def send_multicast(
        self,
        device_tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image: Optional[str] = None,
        click_action: Optional[str] = None,
        sound: str = "default",
        badge: Optional[int] = None,
        batch_size: int = 1000,
    ) -> Dict[str, Any]:
        """Массовая отправка push уведомлений"""

        if not self.active:
            return {
                "success": False,
                "error": "FCM service not configured",
                "sent_count": 0,
                "failed_count": len(device_tokens),
            }

        if not device_tokens:
            return {"success": True, "sent_count": 0, "failed_count": 0, "results": []}

        try:
            sent_count = 0
            failed_count = 0
            results = []

            # Разбиваем на батчи
            for i in range(0, len(device_tokens), batch_size):
                batch_tokens = device_tokens[i : i + batch_size]

                # Подготавливаем данные для батча
                notification_data = {"title": title, "body": body, "sound": sound}

                if image:
                    notification_data["image"] = image

                if click_action:
                    notification_data["click_action"] = click_action

                if badge is not None:
                    notification_data["badge"] = str(badge)

                payload = {
                    "registration_ids": batch_tokens,
                    "notification": notification_data,
                    "priority": "high",
                    "content_available": True,
                }

                if data:
                    string_data = {k: str(v) for k, v in data.items()}
                    payload["data"] = string_data

                # Отправляем батч
                headers = {
                    "Authorization": f"key={self.server_key}",
                    "Content-Type": "application/json",
                }

                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        self.fcm_url, json=payload, headers=headers
                    )

                    response_data = response.json()

                    if response.status_code == 200:
                        batch_results = response_data.get("results", [])

                        for j, result in enumerate(batch_results):
                            token_index = i + j
                            if "message_id" in result:
                                sent_count += 1
                                results.append(
                                    {
                                        "token_index": token_index,
                                        "success": True,
                                        "message_id": result["message_id"],
                                    }
                                )
                            else:
                                failed_count += 1
                                results.append(
                                    {
                                        "token_index": token_index,
                                        "success": False,
                                        "error": result.get("error", "Unknown error"),
                                    }
                                )
                    else:
                        # Весь батч провалился
                        failed_count += len(batch_tokens)
                        for j in range(len(batch_tokens)):
                            results.append(
                                {
                                    "token_index": i + j,
                                    "success": False,
                                    "error": f"HTTP {response.status_code}",
                                }
                            )

                # Небольшая задержка между батчами
                if i + batch_size < len(device_tokens):
                    await asyncio.sleep(0.1)

            return {
                "success": sent_count > 0,
                "sent_count": sent_count,
                "failed_count": failed_count,
                "total_count": len(device_tokens),
                "results": results,
            }

        except Exception as e:
            logger.error(f"FCM multicast error: {e}")
            return {
                "success": False,
                "error": str(e),
                "sent_count": 0,
                "failed_count": len(device_tokens),
            }

    async def send_topic_notification(
        self,
        topic: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        image: Optional[str] = None,
        condition: Optional[str] = None,
    ) -> FCMResponse:
        """Отправка уведомления по топику"""

        if not self.active:
            return FCMResponse(success=False, error="FCM service not configured")

        try:
            notification_data = {"title": title, "body": body, "sound": "default"}

            if image:
                notification_data["image"] = image

            payload = {
                "notification": notification_data,
                "priority": "high",
                "content_available": True,
            }

            # Используем топик или условие
            if condition:
                payload["condition"] = condition
            else:
                payload["to"] = f"/topics/{topic}"

            if data:
                string_data = {k: str(v) for k, v in data.items()}
                payload["data"] = string_data

            headers = {
                "Authorization": f"key={self.server_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.fcm_url, json=payload, headers=headers
                )

                response_data = response.json()

                if response.status_code == 200:
                    return FCMResponse(
                        success=True, message_id=response_data.get("message_id")
                    )
                else:
                    return FCMResponse(
                        success=False,
                        error=f"HTTP {response.status_code}: {response_data.get('error', 'Unknown error')}",
                    )

        except Exception as e:
            logger.error(f"FCM topic send error: {e}")
            return FCMResponse(success=False, error=str(e))

    async def subscribe_to_topic(
        self, device_tokens: List[str], topic: str
    ) -> Dict[str, Any]:
        """Подписка устройств на топик"""

        if not self.active:
            return {"success": False, "error": "FCM service not configured"}

        try:
            url = f"https://iid.googleapis.com/iid/v1:batchAdd"

            payload = {"to": f"/topics/{topic}", "registration_tokens": device_tokens}

            headers = {
                "Authorization": f"key={self.server_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response_data = response.json()

                return {
                    "success": response.status_code == 200,
                    "response": response_data,
                }

        except Exception as e:
            logger.error(f"FCM topic subscription error: {e}")
            return {"success": False, "error": str(e)}

    async def unsubscribe_from_topic(
        self, device_tokens: List[str], topic: str
    ) -> Dict[str, Any]:
        """Отписка устройств от топика"""

        if not self.active:
            return {"success": False, "error": "FCM service not configured"}

        try:
            url = f"https://iid.googleapis.com/iid/v1:batchRemove"

            payload = {"to": f"/topics/{topic}", "registration_tokens": device_tokens}

            headers = {
                "Authorization": f"key={self.server_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                response_data = response.json()

                return {
                    "success": response.status_code == 200,
                    "response": response_data,
                }

        except Exception as e:
            logger.error(f"FCM topic unsubscription error: {e}")
            return {"success": False, "error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """Статус FCM сервиса"""
        return {
            "active": self.active,
            "server_key_configured": bool(self.server_key),
            "sender_id_configured": bool(self.sender_id),
            "fcm_url": self.fcm_url,
        }


# Глобальный экземпляр FCM сервиса
fcm_service = FCMService()


def get_fcm_service() -> FCMService:
    """Получить экземпляр FCM сервиса"""
    return fcm_service
