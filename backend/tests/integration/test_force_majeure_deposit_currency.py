"""Currency mismatch must never leave a partial force-majeure refund."""
from datetime import date
from decimal import Decimal

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.payment import Payment
from app.models.refund_deposit import (
    DepositTransaction,
    PatientDeposit,
    PaymentRefundClaim,
    RefundType,
)
from app.models.visit import Visit
from app.services.force_majeure_service import ForceMajeureService


@pytest.mark.parametrize("payment_currency,deposit_currency,expected", [
    ("UZS", None, True), ("UZS", "UZS", True), ("USD", None, False),
    ("USD", "UZS", False), ("UZS", "USD", False), ("", "UZS", False),
])
def test_refund_currency_mismatch_does_not_cancel_or_credit(
    db_session, test_patient, test_doctor, payment_currency, deposit_currency, expected,
):
    queue = DailyQueue(day=date.today(), specialist_id=test_doctor.id, queue_tag="currency_test", active=True)
    visit = Visit(patient_id=test_patient.id, visit_date=date.today(), status="open")
    db_session.add_all([queue, visit])
    db_session.flush()
    entry = OnlineQueueEntry(queue_id=queue.id, visit_id=visit.id, patient_id=test_patient.id,
                             patient_name="SYNTHETIC", number=1, status="waiting", source="desk")
    payment = Payment(visit_id=visit.id, amount=Decimal("10.25"), currency=payment_currency,
                      method="cash", status="paid")
    db_session.add_all([entry, payment])
    if deposit_currency is not None:
        db_session.add(PatientDeposit(patient_id=test_patient.id, balance=Decimal("7.00"),
                                      currency=deposit_currency))
    db_session.commit()
    result = ForceMajeureService(db_session).cancel_entries_with_refund(
        [entry], reason="synthetic", refund_type=RefundType.DEPOSIT,
        performed_by_id=1, send_notifications=False,
    )
    db_session.expire_all()
    deposit = db_session.query(PatientDeposit).filter_by(patient_id=test_patient.id).one_or_none()
    assert entry.status == ("cancelled" if expected else "waiting")
    assert result["cancelled"] == int(expected)
    assert result["failed"] == int(not expected)
    assert db_session.query(DepositTransaction).filter_by(payment_id=payment.id).count() == int(expected)
    assert db_session.query(PaymentRefundClaim).filter_by(payment_id=payment.id).count() == int(expected)
    if deposit_currency is None:
        assert (deposit is not None) == expected
        if expected:
            assert deposit.currency == "UZS"
            assert deposit.balance == Decimal("10.25")
    else:
        assert deposit.currency == deposit_currency
        assert deposit.balance == (Decimal("17.25") if expected else Decimal("7.00"))
