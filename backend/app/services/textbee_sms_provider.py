"""TextBee adapter reserved for isolated staging patient OTP acceptance."""

from __future__ import annotations

import re
from typing import Any

from app.services.sms_providers import (
    SMS_PROVIDER_BALANCE_ERROR,
    SMS_PROVIDER_SEND_ERROR,
    SMS_PROVIDER_STATUS_ERROR,
    BaseSMSProvider,
    SMSMessage,
    SMSResponse,
    _log_provider_failure,
)


class TextBeeSMSProvider(BaseSMSProvider):
    """Queue one E.164 SMS through TextBee's fixed HTTPS API host.

    TextBee's HTTP 200 confirms queue acceptance, not carrier delivery.
    """

    API_BASE_URL = "https://api.textbee.dev/api/v1"
    _E164_RE = re.compile(r"^\+[1-9]\d{1,14}$")

    def __init__(self, api_key: str, device_id: str | None = None, **kwargs):
        super().__init__(api_key=api_key, timeout=kwargs.get("timeout", 10))
        self.base_url = self.API_BASE_URL
        self.device_id = device_id.strip() if device_id else None

    async def send_sms(self, message: SMSMessage) -> SMSResponse:
        if not self._E164_RE.fullmatch(message.phone):
            return SMSResponse(
                success=False,
                error=SMS_PROVIDER_SEND_ERROR,
                provider="textbee",
            )

        payload: dict[str, Any] = {
            "recipients": [message.phone],
            "message": message.text,
        }
        if self.device_id:
            payload["deviceId"] = self.device_id

        try:
            import httpx

            async with httpx.AsyncClient(
                timeout=self.timeout, follow_redirects=False
            ) as client:
                response = await client.post(
                    f"{self.base_url}/gateway/send-sms",
                    json=payload,
                    headers={
                        "x-api-key": self.api_key,
                        "Content-Type": "application/json",
                    },
                )

            if response.status_code != 200:
                return SMSResponse(
                    success=False,
                    error=SMS_PROVIDER_SEND_ERROR,
                    provider="textbee",
                )

            body = response.json()
            data = body.get("data", {}) if isinstance(body, dict) else {}
            batch_id = data.get("smsBatchId") if isinstance(data, dict) else None
            recipient_count = (
                data.get("recipientCount") if isinstance(data, dict) else None
            )
            if (
                not isinstance(data, dict)
                or data.get("success") is not True
                or not isinstance(batch_id, str)
                or not batch_id.strip()
                or isinstance(recipient_count, bool)
                or not isinstance(recipient_count, int)
                or recipient_count != 1
            ):
                return SMSResponse(
                    success=False,
                    error=SMS_PROVIDER_SEND_ERROR,
                    provider="textbee",
                )

            return SMSResponse(
                success=True,
                message_id=batch_id,
                provider="textbee",
                status="queued",
            )
        except Exception as exc:  # noqa: BLE001 - provider boundary fails closed
            _log_provider_failure("textbee", "send_sms", exc)
            return SMSResponse(
                success=False,
                error=SMS_PROVIDER_SEND_ERROR,
                provider="textbee",
            )

    async def get_balance(self) -> dict[str, Any]:
        return {
            "success": False,
            "error": SMS_PROVIDER_BALANCE_ERROR,
            "provider": "textbee",
        }

    async def get_message_status(self, message_id: str) -> dict[str, Any]:
        return {
            "success": False,
            "error": SMS_PROVIDER_STATUS_ERROR,
            "provider": "textbee",
        }
