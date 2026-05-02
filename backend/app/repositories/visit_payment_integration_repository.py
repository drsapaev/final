"""Repository helpers for visit-payment integration service."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import MetaData, Table, select, update
from sqlalchemy.orm import Session

from app.crud.appointment import appointment as crud_appointment
from app.crud.payment_webhook import update_webhook


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

    def update_webhook_status(self, *, webhook_id: int, status: str) -> None:
        update_webhook(
            self.db,
            webhook_id,
            {"status": status, "processed_at": datetime.utcnow()},
        )

    def update_appointment_status(
        self,
        *,
        appointment_id: int,
        new_status: str,
        validate_transition: bool = True,
    ) -> bool:
        updated = crud_appointment.update_status(
            self.db,
            appointment_id=appointment_id,
            new_status=new_status,
            validate_transition=validate_transition,
        )
        return updated is not None

    def update_appointment_fields(
        self,
        *,
        appointment_id: int,
        values: dict[str, Any],
    ) -> bool:
        appointment = crud_appointment.get(self.db, appointment_id)
        if not appointment:
            return False
        crud_appointment.update(self.db, db_obj=appointment, obj_in=values)
        return True

    def create_appointment(self, appointment_in):  # type: ignore[no-untyped-def]
        return crud_appointment.create(self.db, obj_in=appointment_in)
