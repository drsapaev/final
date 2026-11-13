from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class DisplayBoardDeviceCreateRequest(BaseModel):
    device_name: str = Field(min_length=1, max_length=120)

    @field_validator("device_name")
    @classmethod
    def device_name_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Device name must not be blank")
        return value


class DisplayBoardDeviceTokenRequest(BaseModel):
    device_id: int = Field(gt=0)
    secret: str = Field(min_length=32, max_length=128)


class DisplayBoardDeviceTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    board_name: str


class DisplayBoardDeviceCreatedResponse(BaseModel):
    id: int
    board_id: int
    device_name: str
    status: str
    secret: str


class DisplayBoardDeviceResponse(BaseModel):
    id: int
    board_id: int
    device_name: str
    status: str
    last_connected_at: datetime | None = None
    created_at: datetime | None = None
    rotated_at: datetime | None = None
