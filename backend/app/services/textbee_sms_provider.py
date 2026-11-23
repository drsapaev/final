"""TextBee adapter reserved for isolated staging patient OTP acceptance."""

from __future__ import annotations

import re
from dataclasses import dataclass
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


@dataclass
class TextBeeSMSResponse(SMSResponse):
    """TextBee result with a conservative pre-acceptance failure signal."""

    definitely_not_accepted: bool = False


class TextBeeSMSProvider(BaseSMSProvider):
    """Send one E.164 SMS through TextBee's fixed HTTPS API host.

    HTTP 200 confirms queue acceptance or device dispatch, not carrier delivery.
    """

    API_BASE_URL = "https://api.textbee.dev/api/v1"
    _E164_RE = re.compile(r"^\+[1-9]\d{1,14}$")

    def __init__(self, api_key: str, device_id: str | None = None, **kwargs):
        super().__init__(api_key=api_key, timeout=kwargs.get("timeout", 10))
        self.base_url = self.API_BASE_URL
        self.device_id = device_id.strip() if device_id else None

    async def send_sms(self, message: SMSMessage) -> SMSResponse:
        if not self._E164_RE.fullmatch(message.phone):
            return TextBeeSMSResponse(
                success=False,
                error=SMS_PROVIDER_SEND_ERROR,
                provider="textbee",
                definitely_not_accepted=True,
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
                rejected_before_delivery = response.status_code in {400, 401, 403, 429}
                return TextBeeSMSResponse(
                    success=False,
                    error=SMS_PROVIDER_SEND_ERROR,
                    provider="textbee",
                    # TextBee documents these statuses as rejected before
                    # delivery. Other statuses stay ambiguous by default.
                    definitely_not_accepted=rejected_before_delivery,
                )

            body = response.json()
            data = body.get("data", {}) if isinstance(body, dict) else {}
            batch_id = data.get("smsBatchId") if isinstance(data, dict) else None
            recipient_count = (
                data.get("recipientCount") if isinstance(data, dict) else None
            )
            if (
                isinstance(data, dict)
                and data.get("success") is True
                and isinstance(batch_id, str)
                and batch_id.strip()
                and isinstance(recipient_count, int)
                and not isinstance(recipient_count, bool)
                and recipient_count == 1
            ):
                return TextBeeSMSResponse(
                    success=True,
                    message_id=batch_id,
                    provider="textbee",
                    status="queued",
                )

            success_count = data.get("successCount") if isinstance(data, dict) else None
            failure_count = data.get("failureCount") if isinstance(data, dict) else None
            counts_are_integers = (
                isinstance(success_count, int)
                and not isinstance(success_count, bool)
                and isinstance(failure_count, int)
                and not isinstance(failure_count, bool)
            )
            if counts_are_integers and success_count == 1 and failure_count == 0:
                return TextBeeSMSResponse(
                    success=True,
                    provider="textbee",
                    status="sent",
                )

            definitely_not_accepted = bool(
                counts_are_integers and success_count == 0 and failure_count == 1
            )
            return TextBeeSMSResponse(
                success=False,
                error=SMS_PROVIDER_SEND_ERROR,
                provider="textbee",
                definitely_not_accepted=definitely_not_accepted,
            )
        except Exception as exc:  # noqa: BLE001 - provider boundary fails closed
            _log_provider_failure("textbee", "send_sms", exc)
            return TextBeeSMSResponse(
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
