from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class QueueTicket(Base):
    """
    Ежедневные талоны очереди.
    Поля:
      - department: отделение (строка)
      - date_str: YYYY-MM-DD
      - ticket_number: порядковый номер в рамках department+date
      - status: waiting|serving|done
    """
    __tablename__ = "queue_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    department: Mapped[str] = mapped_column(String(64), index=True)
    date_str: Mapped[str] = mapped_column(String(16), index=True)
    ticket_number: Mapped[int] = mapped_column(Integer, index=True)
    status: Mapped[str] = mapped_column(String(16), index=True, default="waiting")

    # Для уникальности номера в дне/отделении желательно иметь constraint.
    # Он создаётся миграцией (см. versions/20250814_0003_queue.py).