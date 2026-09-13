"""PR-6: HTTP contracts for the push device registry.

Contract rules:

- ``provider`` / ``platform`` mirror the DB CHECK constraints (closed
  enums): provider ∈ {fcm, webpush}, platform ∈ {android, web}.
- ``token`` is bounded by the CONTRACT (1..4096, non-blank), not by the
  column: the DB column is TEXT on purpose so future provider credentials
  are never squeezed into a legacy width.
- A Web Push subscription is NEVER forced into the FCM-token format:
  ``provider="webpush"`` requires the provider-specific ``credential``
  payload (PushSubscription keys ``p256dh`` / ``auth`` per RFC 8291) and
  the ``token`` must be the HTTPS subscription endpoint (RFC 8030).
- Responses NEVER carry token/endpoint values or raw credential keys —
  only a non-reversible SHA-256 fingerprint (nothing to leak into logs
  or Sentry).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

PROVIDERS = Literal["fcm", "webpush"]
PLATFORMS = Literal["android", "web"]


class PushDeviceRegisterRequest(BaseModel):
    """Register (or refresh) one device credential for the caller."""

    provider: PROVIDERS
    platform: PLATFORMS
    # FCM registration token, or Web Push subscription endpoint.
    token: str = Field(min_length=1, max_length=4096)
    # App-generated stable identifier of the physical device (client UUID).
    # Optional: legacy clients may not send one (rotation then relies on
    # the UNREGISTERED purge path instead).
    device_id: str | None = Field(default=None, max_length=128)
    # Provider-specific payload (webpush: {"keys": {"p256dh", "auth"}}).
    credential: dict[str, Any] | None = None

    @field_validator("token")
    @classmethod
    def _token_not_blank(cls, value: str) -> str:
        # PR-5 lesson: whitespace-only values pass min_length=1 and would
        # persist a credential every sender treats as absent.
        stripped = value.strip()
        if not stripped:
            raise ValueError("token must contain non-whitespace characters")
        return stripped

    @field_validator("device_id")
    @classmethod
    def _device_id_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return stripped

    @model_validator(mode="after")
    def _webpush_contract(self) -> "PushDeviceRegisterRequest":
        if self.provider == "webpush":
            if not self.token.startswith("https://"):
                raise ValueError(
                    "webpush token must be the HTTPS PushSubscription endpoint"
                )
            keys = (self.credential or {}).get("keys")
            if not isinstance(keys, dict):
                raise ValueError("webpush credential must contain keys")
            for required in ("p256dh", "auth"):
                key_value = keys.get(required)
                if not isinstance(key_value, str) or not key_value.strip():
                    raise ValueError(f"webpush credential keys.{required} is required")
        return self


class PushDeviceOut(BaseModel):
    """API-safe projection — deliberately NO token / raw credential."""

    id: int
    provider: str
    platform: str
    device_id: str | None = None
    enabled: bool
    # False when invalidated_at is set (credential known dead/superseded).
    active: bool
    last_seen_at: str | None = None
    invalidated_at: str | None = None
    created_at: str | None = None
    token_fingerprint: str


class PushDeviceRegisterResponse(BaseModel):
    success: bool
    created: bool
    message: str
    device: PushDeviceOut


class PushDeviceListResponse(BaseModel):
    devices: list[PushDeviceOut]
    total_count: int


class PushDeviceMutationResponse(BaseModel):
    success: bool
    message: str
