"""RQ-17 §3.2 — DTO минимального QueueResource admin-контракта.

Mutability contract зашит в формы DTO: `QueueResourceUpdate` НЕ содержит
`code`/`queue_tag` (immutable после create — routing-ключ завязан на
исторические `DailyQueue.queue_tag`, `Service.queue_tag`,
`QueueProfile.queue_tags[]`) и запрещает их передачу (`extra="forbid"`):
PATCH с `queue_tag`/`code` отклоняется самой схемой (пин §3.2).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    (extra="forbid" -> 422 на попытку).

    Nullable здесь только `default_cabinet` (единственная nullable-колонка
    в таблице). Explicit `null` для остальных полей — 422 (round-3
    owner-ревью P2): DB-колонки NOT NULL, и без этого пина explicit null
    проходил Pydantic (`exclude_unset` сохранял его) и падал на
    constraint violation уже в БД -> 500 вместо 422. Отличать explicit
    null от unset позволяет `model_fields_set` — absent-поле в него не
    попадает и остаётся «нет изменения»."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    start_number_online: int | None = Field(default=None, ge=1)
    max_online_per_day: int | None = Field(default=None, ge=1)
    default_cabinet: str | None = Field(default=None, max_length=20)
    active: bool | None = None

    # NOT NULL-колонки: explicit null запрещён (422); nullable только default_cabinet
    _NOT_NULL_FIELDS = ("display_name", "start_number_online", "max_online_per_day", "active")

    @model_validator(mode="after")
    def _reject_explicit_null_for_not_null_fields(self) -> QueueResourceUpdate:
        # exclude_unset-семантика endpoint'а опирается на model_fields_set:
        # absent = «нет изменения», explicit null = попытка затереть NOT NULL
        for field in self._NOT_NULL_FIELDS:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(
                    f"Field '{field}' must not be null: the column is NOT NULL "
                    "(explicit null would fail in the database as a 500); "
                    "omit the field to leave it unchanged"
                )
        return self
