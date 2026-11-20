"""Real PostgreSQL link/FK races for staff payment confirmation."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentVisit
from app.services.payment_invariant_service import PaymentInvariantService
from tests.integration.test_group_payment_preflight_pg import pg_case  # noqa: F401


def _payment(engine, visit_id):
    with Session(engine) as db:
        payment = Payment(visit_id=visit_id, amount=Decimal("1.00"), status="pending", method="cash", currency="UZS")
        db.add(payment)
        db.flush()
        payment_id = payment.id
        db.commit()
        return payment_id


def test_existing_writer_first_causes_safe_retry_then_complete_links(pg_case):
    runtime, ids, admin = pg_case
    payment_id = _payment(admin, ids[0])
    with Session(admin) as writer:
        writer.add(PaymentVisit(payment_id=payment_id, visit_id=ids[1], amount=Decimal("1.00")))
        writer.flush()  # Holds FK KEY SHARE on Payment and the linked Visit.
        with Session(runtime) as confirmer:
            with pytest.raises(HTTPException) as error:
                PaymentInvariantService(confirmer).preflight_payment_record(payment_id)
            assert error.value.status_code == 409
            assert not confirmer.in_transaction()
        writer.commit()
    with Session(runtime) as confirmer:
        record = PaymentInvariantService(confirmer).preflight_payment_record(payment_id)
        assert record.visit_ids == tuple(sorted([ids[0], ids[1]]))
        assert {visit_id for _, visit_id in record.links} == {ids[1]}
        confirmer.rollback()


@pytest.mark.parametrize("mutation", ["insert", "update", "delete"])
def test_confirm_first_blocks_link_mutations_before_commit(pg_case, mutation):
    runtime, ids, admin = pg_case
    payment_id = _payment(admin, ids[0])
    with Session(admin) as db:
        existing = PaymentVisit(payment_id=payment_id, visit_id=ids[1], amount=Decimal("1.00"))
        db.add(existing)
        db.flush()
        link_id = existing.id
        db.commit()
    with Session(runtime) as confirmer:
        locked = PaymentInvariantService(confirmer).preflight_payment_record(payment_id)
        assert locked.visit_ids == tuple(sorted([ids[0], ids[1]]))
        def mutate():
            with Session(admin) as db:
                db.execute(text("SET LOCAL lock_timeout='100ms'"))
                try:
                    if mutation == "insert":
                        db.add(PaymentVisit(payment_id=payment_id, visit_id=ids[2], amount=Decimal("0.00")))
                    elif mutation == "update":
                        db.get(PaymentVisit, link_id).visit_id = ids[2]
                    else:
                        db.delete(db.get(PaymentVisit, link_id))
                    db.flush()
                except DBAPIError as exc:
                    db.rollback()
                    return getattr(exc.orig, "sqlstate", None)
                return "unexpected-success"
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(mutate).result(timeout=10) == "55P03"
        confirmer.rollback()
