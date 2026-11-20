"""Payment confirmation must include every linked Visit, including siblings."""
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.payment import Payment, PaymentVisit
from app.services.payment_invariant_service import PaymentInvariantService
from tests.integration.test_group_payment_preflight import _pending, case  # noqa: F401


def test_record_preflight_returns_locked_primary_and_all_link_ids(case):
    db, ids = case
    payment = Payment(visit_id=ids[0], amount=Decimal("1.00"), status="pending", method="cash", currency="UZS")
    db.add(payment)
    db.flush()
    db.add_all([PaymentVisit(payment_id=payment.id, visit_id=ids[1], amount=Decimal("0.50")),
                PaymentVisit(payment_id=payment.id, visit_id=ids[3], amount=Decimal("0.50"))])
    db.commit()
    locked = PaymentInvariantService(db).preflight_payment_record(payment.id)
    assert locked.payment_id == payment.id
    assert locked.primary_visit_id == ids[0]
    assert locked.visit_ids == tuple(sorted({ids[0], ids[1], ids[3]}))
    assert {visit_id for _, visit_id in locked.links} == {ids[1], ids[3]}


def test_record_preflight_blocks_pending_request_in_linked_group(case):
    db, ids = case
    payment = Payment(visit_id=ids[0], amount=Decimal("1.00"), status="pending", method="cash", currency="UZS")
    db.add(payment)
    db.flush()
    db.add(PaymentVisit(payment_id=payment.id, visit_id=ids[1], amount=Decimal("1.00")))
    _pending(db, ids[3])
    db.commit()
    with pytest.raises(HTTPException) as error:
        PaymentInvariantService(db).preflight_payment_record(payment.id)
    assert error.value.status_code == 409
    assert not db.in_transaction()
    assert db.get(Payment, payment.id).status == "pending"


def test_record_preflight_preserves_ordinary_payment_without_links(case):
    db, ids = case
    payment = Payment(visit_id=ids[0], amount=Decimal("1.00"), status="pending", method="cash", currency="UZS")
    db.add(payment)
    db.commit()
    locked = PaymentInvariantService(db).preflight_payment_record(payment.id)
    assert locked.primary_visit_id == ids[0]
    assert locked.visit_ids == (ids[0],)
    assert locked.links == ()
