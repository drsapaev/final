"""RQ-17 §3.2 — DTO минимального QueueResource admin-контракта.

Mutability contract зашит в формы DTO: `QueueResourceUpdate` НЕ содержит
`code`/`queue_tag` (immutable после create — routing-ключ завязан на
исторические `DailyQueue.queue_tag`, `Service.queue_tag`,
`QueueProfile.queue_tags[]`) и запрещает их передачу (`extra="forbid"`):
PATCH с `queue_tag`/`code` отклоняется самой схемой (пин §3.2).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.base import ORMModel


class QueueResourceOut(ORMModel):
    id: int
    code: str
    queue_tag: str
    display_name: str
    active: bool
    start_number_online: int
    max_online_per_day: int
    default_cabinet: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class QueueResourceCreate(BaseModel):
    """Draft-by-default (S-14: услуги/профиль → draft-ресурс → активация
    через gate §3.1); `active=true` сразу — только при пройденном gate."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=50)
    queue_tag: str = Field(min_length=1, max_length=32)
    display_name: str = Field(min_length=1, max_length=200)
    start_number_online: int = Field(default=1, ge=1)
    max_online_per_day: int = Field(default=15, ge=1)
    default_cabinet: str | None = Field(default=None, max_length=20)
    active: bool = False


class QueueResourceUpdate(BaseModel):
    """§3.2: ordinary PATCH — `display_name`/`start_number_online`/
    `max_online_per_day`/`default_cabinet`; `active` — lifecycle-переход
    под serialization-scope §3.1(б). `code`/`queue_tag` immutable
    (extra="forbid" -> 422 на попытку)."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    start_number_online: int | None = Field(default=None, ge=1)
    max_online_per_day: int | None = Field(default=None, ge=1)
    default_cabinet: str | None = Field(default=None, max_length=20)
    active: bool | None = None
