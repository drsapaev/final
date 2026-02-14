"""Repository helpers for visit-payment integration service."""

from __future__ import annotations

from sqlalchemy import MetaData, Table, select, update
from sqlalchemy.orm import Session


class VisitPaymentIntegrationRepository:
    """Encapsulates low-level SQL access for visit-payment integration."""

    def __init__(self, db: Session):
        self.db = db

    def visits_table(self) -> Table:
        metadata = MetaData()
        return Table("visits", metadata, autoload_with=self.db.get_bind())

    def appointments_table(self) -> Table:
        metadata = MetaData()
        return Table("appointments", metadata, autoload_with=self.db.get_bind())

    def insert_visit(self, values: dict) -> int:
        result = self.db.execute(self.visits_table().insert().values(**values))
        return int(result.inserted_primary_key[0])

    def get_visit(self, visit_id: int):
        query = select(self.visits_table()).where(self.visits_table().c.id == visit_id)
        return self.db.execute(query).first()

    def update_visit(self, visit_id: int, values: dict) -> None:
        self.db.execute(
            update(self.visits_table())
            .where(self.visits_table().c.id == visit_id)
            .values(**values)
        )

    def get_visit_payment_projection(self, visit_id: int):
        table = self.visits_table()
        query = select(
            table.c.id,
            table.c.payment_status,
            table.c.payment_amount,
            table.c.payment_currency,
            table.c.payment_provider,
            table.c.payment_transaction_id,
            table.c.payment_processed_at,
        ).where(table.c.id == visit_id)
        return self.db.execute(query).first()

    def list_visits_by_payment_status(
        self, payment_status: str, limit: int = 100, offset: int = 0
    ):
        table = self.visits_table()
        query = (
            select(table)
            .where(table.c.payment_status == payment_status)
            .order_by(table.c.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return self.db.execute(query).fetchall()

    def find_appointment_by_visit_id(self, visit_id: int):
        table = self.appointments_table()
        query = select(table).where(table.c.visit_id == visit_id)
        return self.db.execute(query).first()
