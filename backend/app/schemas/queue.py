from __future__ import annotations

from pydantic import Field

from app.schemas.base import ORMModel


class QueueStatsOut(ORMModel):
    last_ticket: int = Field(ge=0)
    waiting: int = Field(ge=0)
    serving: int = Field(ge=0)
    done: int = Field(ge=0)


class NextTicketOut(ORMModel):
    ticket_number: int = Field(ge=1)
    stats: QueueStatsOut
