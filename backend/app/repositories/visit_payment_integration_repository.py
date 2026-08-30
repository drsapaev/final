"""Repository helpers for visit-payment integration service."""

from __future__ import annotations

from datetime import UTC, datetime
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
        """Update visit fields via SQLAlchemy Core.

        Issue #06 Phase 4b Gate C+: this method is a generic dict-based
        update that CAN set ANY field on the visits table, including
        ``status`` (the lifecycle field). This makes it a potential
        lifecycle-invariant bypass.

        Audit finding (2026-08-09): the single caller
        (``visit_payment_integration.py:329``) only passes PAYMENT
        PROJECTION fields (``payment_status``, ``payment_processed_at``,
        ``payment_amount``, ``payment_currency``, ``payment_provider``,
        ``payment_transaction_id``, ``payment_webhook_id``) — NEVER
        ``status`` (the lifecycle field). So this is NOT currently a
        lifecycle bypass.

        However, the generic API is dangerous because nothing prevents
        a future caller from passing ``{"status": "open"}``.

        Hardening (this change): reject ``status`` in the values dict
        with a ValueError. This eliminates the capability of bypassing
        the lifecycle invariant through this generic method, rather
        than just wrapping it.

        For payment projection updates, use the new specialized method
        ``update_payment_projection()`` instead.
        """
        # Gate C+ hardening: reject lifecycle field mutations.
        LIFECYCLE_FIELDS = {"status"}
        forbidden = set(values) & LIFECYCLE_FIELDS
        if forbidden:
            raise ValueError(
                f"VisitPaymentIntegrationRepository.update_visit() rejects "
                f"lifecycle field(s) {forbidden}. Use "
                f"VisitLifecycleService for status transitions. For "
                f"payment projection updates, use "
                f"update_payment_projection() instead."
            )

        self.db.execute(
            update(self.visits_table())
            .where(self.visits_table().c.id == visit_id)
            .values(**values)
        )

    def update_payment_projection(
        self,
        visit_id: int,
        *,
        payment_status: str | None = None,
        payment_processed_at=None,
        payment_amount: float | None = None,
        payment_currency: str | None = None,
        payment_provider: str | None = None,
        payment_transaction_id: str | None = None,
        payment_webhook_id: int | None = None,
    ) -> None:
        """Update ONLY the payment projection fields on the visits table.

        Issue #06 Phase 4b Gate C+: specialized replacement for the
        generic ``update_visit()`` method. Accepts only payment-related
        fields — the lifecycle ``status`` field is NOT accepted.

        This method is the correct way to synchronize the denormalized
        payment projection on the visits table after a payment event
        (webhook, manual confirmation, refund).
        """
        values: dict = {}
        if payment_status is not None:
            values["payment_status"] = payment_status
        if payment_processed_at is not None:
            values["payment_processed_at"] = payment_processed_at
        if payment_amount is not None:
            values["payment_amount"] = payment_amount
        if payment_currency is not None:
            values["payment_currency"] = payment_currency
        if payment_provider is not None:
            values["payment_provider"] = payment_provider
        if payment_transaction_id is not None:
            values["payment_transaction_id"] = payment_transaction_id
        if payment_webhook_id is not None:
            values["payment_webhook_id"] = payment_webhook_id

        if not values:
            return  # nothing to update

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
            {"status": status, "processed_at": datetime.now(UTC)},
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
