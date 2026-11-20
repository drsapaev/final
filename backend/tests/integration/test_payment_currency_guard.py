"""Payment currency and provider replay checks use server-owned visit data."""
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import payments
from app.models.encounter import Encounter
from app.models.payment import Payment, PaymentVisit
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.provider_attempt import (
    ProviderActiveVisitReservation,
    ProviderAttempt,
    ProviderAttemptVisit,
)
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.services.payment_invariant_service import PaymentInvariantService


def _visit(db, patient, currency):
    service = Service(code=f"SYNTHETIC-CURRENCY-{currency}", name="SYNTHETIC", price=Decimal("1.00"), active=True)
    encounter = Encounter(patient_id=patient.id, provenance="new")
    db.add_all([service, encounter])
    db.flush()
    visit = Visit(patient_id=patient.id, encounter_id=encounter.id, visit_date=date(2099, 1, 1),
                  status="pending_confirmation", confirmation_context_epoch=1)
    db.add(visit)
    db.flush()
    db.add(VisitService(visit_id=visit.id, service_id=service.id, name="SYNTHETIC", qty=1,
                        price=Decimal("1.00"), currency=currency))
    db.commit()
    return visit


@pytest.mark.parametrize("stored,requested", [(None, "UZS"), ("USD", "UZS"), ("UZS", "USD")])
@pytest.mark.parametrize("endpoint", ["init", "test-init"])
def test_online_currency_mismatch_fails_before_provider(
    client, db_session, admin_auth_headers, test_patient, monkeypatch, stored, requested, endpoint,
):
    visit = _visit(db_session, test_patient, stored)
    manager = MagicMock()
    manager.get_providers_for_currency.return_value = ["payme"]
    monkeypatch.setattr(payments, "get_payment_manager", lambda: manager)
    monkeypatch.setattr(payments.settings, "ENABLE_TEST_PAYMENT_INIT", True)
    response = client.post(f"/api/v1/payments/{endpoint}", headers=admin_auth_headers,
                           json={"visit_id": visit.id, "provider": "payme", "amount": 1, "currency": requested})
    assert response.status_code == 409, response.text
    assert db_session.query(Payment).filter_by(visit_id=visit.id).count() == 0
    manager.create_payment.assert_not_called()


@pytest.mark.parametrize("status,provider_id", [("pending", None), ("processing", "SYNTHETIC"), ("failed", "SYNTHETIC")])
def test_existing_provider_attempt_never_starts_a_second_intent(
    client, db_session, admin_auth_headers, test_patient, monkeypatch, status, provider_id,
):
    visit = _visit(db_session, test_patient, "UZS")
    db_session.add(Payment(visit_id=visit.id, amount=Decimal("1.00"), currency="UZS", method="online",
                           provider="click", provider_payment_id=provider_id, status=status))
    db_session.commit()
    manager = MagicMock()
    manager.get_providers_for_currency.return_value = ["payme"]
    monkeypatch.setattr(payments, "get_payment_manager", lambda: manager)
    response = client.post("/api/v1/payments/init", headers=admin_auth_headers,
                           json={"visit_id": visit.id, "provider": "payme", "amount": 1, "currency": "UZS"})
    assert response.status_code == 409, response.text
    assert db_session.query(Payment).filter_by(visit_id=visit.id).count() == 1
    manager.create_payment.assert_not_called()


def test_existing_attempt_linked_through_payment_visit_blocks_new_provider(
    client, db_session, admin_auth_headers, test_patient, monkeypatch,
):
    visit = _visit(db_session, test_patient, "UZS")
    other = Visit(patient_id=test_patient.id, visit_date=date(2099, 1, 1), confirmation_context_epoch=1)
    db_session.add(other)
    db_session.flush()
    existing = Payment(visit_id=other.id, amount=Decimal("1.00"), currency="UZS", method="online",
                       provider="click", status="pending")
    db_session.add(existing)
    db_session.flush()
    db_session.add(PaymentVisit(payment_id=existing.id, visit_id=visit.id, amount=Decimal("1.00")))
    db_session.commit()
    manager = MagicMock()
    manager.get_providers_for_currency.return_value = ["payme"]
    monkeypatch.setattr(payments, "get_payment_manager", lambda: manager)
    response = client.post("/api/v1/payments/init", headers=admin_auth_headers,
                           json={"visit_id": visit.id, "provider": "payme", "amount": 1, "currency": "UZS"})
    assert response.status_code == 409, response.text
    assert db_session.query(Payment).count() == 1
    manager.create_payment.assert_not_called()


def test_unresolved_online_attempt_blocks_manual_collection(db_session, test_patient, admin_user):
    visit = _visit(db_session, test_patient, "UZS")
    db_session.add(Payment(visit_id=visit.id, amount=Decimal("1.00"), currency="UZS", method="online",
                           provider="click", provider_payment_id="SYNTHETIC", status="processing"))
    db_session.commit()
    with pytest.raises(HTTPException) as error:
        PaymentInvariantService(db_session).create_payment_for_visit(
            visit.id, Decimal("1.00"), "cash", "synthetic", admin_user, currency="UZS", commit=False,
        )
    assert error.value.status_code == 409
    assert db_session.query(Payment).filter_by(visit_id=visit.id).count() == 1


def _reserve_without_payment(db_session, patient, visit):
    attempt = ProviderAttempt(public_id=str(uuid4()), target_kind="payment_invoice", invoice_id_snapshot=123,
                              actor_user_id_snapshot=1, provider="click", merchant_hash="a" * 64,
                              order_ref=str(uuid4()), fingerprint="b" * 64, amount_minor="100",
                              currency="UZS", currency_exponent=2, status="prepared")
    db_session.add(attempt)
    db_session.flush()
    history = ProviderAttemptVisit(attempt_id=attempt.id, visit_id=visit.id, visit_id_snapshot=visit.id,
                                   patient_id_snapshot=patient.id, context_epoch=1, amount_minor="100")
    db_session.add(history)
    db_session.flush()
    db_session.add(ProviderActiveVisitReservation(visit_id=visit.id, attempt_id=attempt.id,
                                                   attempt_visit_id=history.id))
    db_session.commit()


@pytest.mark.parametrize("method", ["cash", "pending"])
def test_active_reservation_blocks_collection_without_payment_row(db_session, test_patient, admin_user, method):
    visit = _visit(db_session, test_patient, "UZS")
    _reserve_without_payment(db_session, test_patient, visit)
    service = PaymentInvariantService(db_session)
    with pytest.raises(HTTPException) as error:
        if method == "cash":
            service.create_payment_for_visit(visit.id, Decimal("1.00"), "cash", "synthetic", admin_user,
                                             currency="UZS", commit=False)
        else:
            service.create_pending_payment(visit.id, Decimal("1.00"), "UZS", "online", "click", None,
                                           admin_user, commit=False)
    assert error.value.status_code == 409
    assert db_session.query(Payment).filter_by(visit_id=visit.id).count() == 0


@pytest.mark.parametrize("endpoint", ["init", "test-init"])
def test_active_reservation_prevents_provider_call(
    client, db_session, admin_auth_headers, test_patient, monkeypatch, endpoint,
):
    visit = _visit(db_session, test_patient, "UZS")
    _reserve_without_payment(db_session, test_patient, visit)
    manager = MagicMock()
    manager.get_providers_for_currency.return_value = ["payme"]
    monkeypatch.setattr(payments, "get_payment_manager", lambda: manager)
    monkeypatch.setattr(payments.settings, "ENABLE_TEST_PAYMENT_INIT", True)
    response = client.post(f"/api/v1/payments/{endpoint}", headers=admin_auth_headers,
                           json={"visit_id": visit.id, "provider": "payme", "amount": 1, "currency": "UZS"})
    assert response.status_code == 409, response.text
    assert db_session.query(Payment).filter_by(visit_id=visit.id).count() == 0
    manager.create_payment.assert_not_called()


def test_public_intent_assertion_requires_preflight_and_checks_sibling(db_session, test_patient):
    visit = _visit(db_session, test_patient, "UZS")
    sibling = Visit(patient_id=test_patient.id, encounter_id=visit.encounter_id,
                    visit_date=date(2099, 1, 1), status="pending_confirmation", confirmation_context_epoch=1)
    db_session.add(sibling)
    db_session.commit()
    service = PaymentInvariantService(db_session)
    with pytest.raises(HTTPException) as no_preflight:
        service.assert_no_unresolved_payment_intent(visit.id)
    assert no_preflight.value.status_code == 409
    service.preflight_payment_groups([visit.id])
    service.assert_no_unresolved_payment_intent(visit.id)
    db_session.rollback()
    with pytest.raises(HTTPException) as old_marker:
        service.assert_no_unresolved_payment_intent(visit.id)
    assert old_marker.value.status_code == 409
    _reserve_without_payment(db_session, test_patient, sibling)
    service.preflight_payment_groups([visit.id])
    with pytest.raises(HTTPException) as unresolved:
        service.assert_no_unresolved_payment_intent(visit.id)
    assert unresolved.value.status_code == 409


@pytest.mark.parametrize("boundary", ["commit", "savepoint"])
def test_public_intent_assertion_refuses_stale_transaction_marker(db_session, test_patient, boundary):
    visit = _visit(db_session, test_patient, "UZS")
    visit_id = visit.id
    service = PaymentInvariantService(db_session)
    service.preflight_payment_groups([visit_id])
    if boundary == "commit":
        db_session.commit()
    else:
        db_session.begin_nested()
    with pytest.raises(HTTPException) as error:
        service.assert_no_unresolved_payment_intent(visit_id)
    assert error.value.status_code == 409
    assert not db_session.in_transaction()


def test_invoice_currency_conflict_blocks_before_payment(db_session, test_patient, admin_user):
    visit = _visit(db_session, test_patient, "UZS")
    invoice = PaymentInvoice(patient_id=test_patient.id, total_amount=Decimal("1.00"), currency="USD", status="pending")
    db_session.add(invoice)
    db_session.flush()
    db_session.add(PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visit.id, visit_amount=Decimal("1.00")))
    db_session.commit()
    with pytest.raises(HTTPException) as error:
        PaymentInvariantService(db_session).create_payment_for_visit(
            visit.id, Decimal("1.00"), "cash", "synthetic", admin_user, currency="UZS", commit=False,
        )
    assert error.value.status_code == 409
    assert db_session.query(Payment).filter_by(visit_id=visit.id).count() == 0


def test_matching_non_uzs_currency_is_not_blanket_rejected(db_session, test_patient, admin_user):
    visit = _visit(db_session, test_patient, "USD")
    payment = PaymentInvariantService(db_session).create_payment_for_visit(
        visit.id, Decimal("1.00"), "cash", "synthetic", admin_user, currency="USD", commit=False,
    )
    assert payment.currency == "USD"
    assert payment.amount == Decimal("1.00")
