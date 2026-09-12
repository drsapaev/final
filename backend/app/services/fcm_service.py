"""
Firebase Cloud Messaging (FCM) сервис для push уведомлений
Поддерживает HTTP v1 API
"""

import asyncio
import logging
import os
import time
from typing import Any

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class FCMResponse(BaseModel):
    """Ответ FCM"""

    success: bool
    message_id: str | None = None
    error: str | None = None
    error_code: str | None = None


def is_unregistered_token_response(response: FCMResponse) -> bool:
    """True only for a canonical FCM UNREGISTERED verdict.

    PR-5 (codex round 1): ``error_code`` carries the generic HTTP status, so
    a bare 404/410 (proxy/gateway hiccup, wrong fcm_url) must NOT wipe the
    user's token. The token is dropped only when the v1 error body itself
    reports the unregistered verdict: HTTP 410 with status UNREGISTERED, or
    HTTP 404 with the canonical "Requested entity was not found" message.
    """
    if response.success or response.error_code not in {"404", "410"}:
        return False
    message = (response.error or "").lower()
    return (
        "unregistered" in message
        or "requested entity was not found" in message
    )


class FCMService:
    """Сервис для работы с Firebase Cloud Messaging (HTTP v1 API)"""

    def __init__(self):
        self.project_id = getattr(settings, 'FCM_PROJECT_ID', None)
        self.fcm_url = f"https://fcm.googleapis.com/v1/projects/{self.project_id}/messages:send"

        # OAuth2 credentials
        self.credentials = None
        self.access_token = None
        self.token_expiry = 0

        # Concurrency cap for multicast fan-out (bounded, unlike a bare gather).
        self._send_semaphore = asyncio.Semaphore(10)

        # PR-5 (codex round 2): serialize OAuth refreshes — concurrent sends
        # on a cold/expired cache must not refresh the shared credentials
        # object in parallel (redundant token-endpoint calls, throttling,
        # racing failures).
        self._refresh_lock = asyncio.Lock()

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

    def _get_access_token(self) -> str | None:
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

    async def _get_access_token_async(self) -> str | None:
        """Off-loop token fetch with single-flight refresh (codex round 2).

        Fast path: a still-valid cached token returns without touching the
        lock. Otherwise the refresh runs in a worker thread while the lock
        guarantees exactly one concurrent refresh; waiters re-check the cache
        and reuse the freshly minted token.
        """
        if not self.credentials:
            return None

        now = time.time()
        if self.access_token and now < self.token_expiry - 60:
            return self.access_token

        async with self._refresh_lock:
            now = time.time()
            if self.access_token and now < self.token_expiry - 60:
                return self.access_token
            return await asyncio.to_thread(self._get_access_token)

    @property
    def active(self) -> bool:
        """True only when the feature flag AND credentials AND project are set.

        PR-5: previously ``FCM_ENABLED=false`` did not actually disable the
        service (the flag was read by nothing), so /fcm/status reported the
        service as usable while push could never be honestly attempted.
        """
        return bool(
            getattr(settings, "FCM_ENABLED", False)
            and self.credentials is not None
            and bool(self.project_id)
        )

    async def send_notification(
        self,
        device_token: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
        image: str | None = None,
        sound: str = "default",
        badge: int | None = None,
        click_action: str | None = None,
    ) -> FCMResponse:
        """Отправка push уведомления (HTTP v1)"""

        if not self.active:
            return FCMResponse(success=False, error="FCM service not configured")

        # PR-5: credentials.refresh() is a blocking network call — keep it
        # off the event loop (same class of issue as the PR-4 blocking-send
        # fix); single-flight lock prevents parallel refreshes.
        token = await self._get_access_token_async()
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

            if click_action:
                message["android"]["notification"]["click_action"] = click_action

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

                if response.status_code != 200:
                    # Guard against non-JSON error bodies (proxies, HTML pages).
                    try:
                        response_data = response.json()
                    except ValueError:
                        response_data = {}
                    error_data = response_data.get("error", {})
                    raw_code = error_data.get("code")
                    return FCMResponse(
                        success=False,
                        error=error_data.get("message", "Unknown error"),
                        error_code=str(raw_code) if raw_code is not None else str(response.status_code),
                    )

                try:
                    response_data = response.json()
                except ValueError:
                    return FCMResponse(
                        success=False,
                        error="FCM returned a non-JSON success response",
                    )

                # Успешный ответ v1 содержит name (message_id)
                return FCMResponse(
                    success=True,
                    message_id=response_data.get("name"),
                )

        except Exception as e:
            logger.error(f"FCM send error: {e}")
            return FCMResponse(success=False, error=str(e))

    async def send_multicast(
        self,
        device_tokens: list[str],
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
        **kwargs
    ) -> dict[str, Any]:
        """
        Массовая отправка (эмуляция через индивидуальные запросы, т.к. v1 не поддерживает multicast)
        """
        results = []
        sent_count = 0
        failed_count = 0

        # Ограничиваем concurrency семафором (bare gather заливает FCM при
        # больших списках токенов)
        async def _bounded_send(single_token: str) -> FCMResponse:
            async with self._send_semaphore:
                return await self.send_notification(
                    single_token, title, body, data, **kwargs
                )

        tasks = [_bounded_send(token) for token in device_tokens]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for i, response in enumerate(responses):
            if isinstance(response, FCMResponse):
                if response.success:
                    sent_count += 1
                    results.append({"token_index": i, "success": True, "message_id": response.message_id})
                else:
                    failed_count += 1
                    results.append(
                        {
                            "token_index": i,
                            "success": False,
                            "error": response.error,
                            "error_code": response.error_code,
                        }
                    )
            else:
                failed_count += 1
                results.append({"token_index": i, "success": False, "error": str(response), "error_code": None})

        return {
            "success": sent_count > 0,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "total_count": len(device_tokens),
            "results": results
        }

    def get_status(self) -> dict[str, Any]:
        """Return a serializable snapshot of FCM service configuration.

        PR-2: previously the /fcm/status endpoint called a non-existent
        ``get_status`` method and crashed with HTTP 500.
        """
        return {
            "active": self.active,
            "enabled": bool(getattr(settings, "FCM_ENABLED", False)),
            "project_id": self.project_id,
            "credentials_loaded": self.credentials is not None,
            "fcm_url": self.fcm_url if self.active else None,
        }


# Глобальный экземпляр FCM сервиса
fcm_service = FCMService()


def get_fcm_service() -> FCMService:
    """Получить экземпляр FCM сервиса"""
    return fcm_service

