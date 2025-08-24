from __future__ import annotations
from app.schemas.base import ORMModel
from pydantic import Field


class QueueStatsOut(ORMModel):
    last_ticket: int = Field(ge=0)
    waiting: int = Field(ge=0)
    serving: int = Field(ge=0)
    done: int = Field(ge=0)


class NextTicketOut(ORMModel):
    ticket_number: int = Field(ge=1)
    stats: QueueStatsOut
