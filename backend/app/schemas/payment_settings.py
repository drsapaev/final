"""Schemas for payment provider settings API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    enabled: bool = True
    test_mode: bool = True


class ClickConfig(ProviderConfig):
    service_id: str = ""
    merchant_id: str = ""
    secret_key: str = ""
    base_url: str = "https://api.click.uz/v2"


class PayMeConfig(ProviderConfig):
    merchant_id: str = ""
    secret_key: str = ""
    base_url: str = "https://checkout.paycom.uz"
    api_url: str = "https://api.paycom.uz"


class PaymentProviderSettings(BaseModel):
    default_provider: str = Field(default="click", pattern="^(click|payme)$")
    enabled_providers: list[str] = Field(default=["click"])
    click: ClickConfig = Field(default_factory=ClickConfig)
    payme: PayMeConfig = Field(default_factory=PayMeConfig)


class TestProviderRequest(BaseModel):
    provider: str = Field(pattern="^(click|payme)$")
    config: dict[str, Any]


class TestProviderResponse(BaseModel):
    success: bool
    message: str
    details: dict[str, Any] | None = None
