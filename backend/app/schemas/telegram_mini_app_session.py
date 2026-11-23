"""Explicit patient Mini App credential and device contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, SecretStr


class TelegramMiniAppExchangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    init_data: SecretStr


class TelegramMiniAppRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: SecretStr


class TelegramMiniAppTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class TelegramMiniAppSessionItem(BaseModel):
    id: UUID
    device_label: str
    created_at: datetime
    last_active_at: datetime
    expires_at: datetime
    is_current: bool


class TelegramMiniAppSessionListResponse(BaseModel):
    sessions: list[TelegramMiniAppSessionItem]
    total: int


class TelegramMiniAppRevokeResponse(BaseModel):
    revoked: bool = True
    revoked_count: int
