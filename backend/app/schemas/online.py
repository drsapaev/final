from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import Field

from app.schemas.base import ORMModel


class OnlineJoinRequest(ORMModel):
    department: str = Field(max_length=64)
    date: date
    phone: Optional[str] = Field(default=None, max_length=32)
    tg_id: Optional[str] = Field(default=None, max_length=64)
    name: Optional[str] = Field(default=None, max_length=255)


class OnlineJoinResponse(ORMModel):
    queue_entry_id: int
    ticket_number: int
    department: str
    date: date


class OnlineOpenRequest(ORMModel):
    department: str = Field(max_length=64)
    date: date
    start_number: Optional[int] = None
