"""Internal reservations only; no live provider or checkout URL."""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.provider_attempt import (
    ProviderActiveVisitReservation,
    ProviderAttempt,
    ProviderAttemptVisit,
)
from app.services.profile_contact_security import ProfileBearerContext
from app.services.provider_attempt_service import (
    ProviderAttemptError,
    ProviderAttemptService,
    _minor_units,
)
from tests.integration.test_derma_price_override_integrity import (
    _create_doctor,
    _create_patient,
    _create_service,
    _create_user,
    _create_visit_with_service,
    _suffix,
)


class FakeManager:
    def get_provider(self, name):
        return SimpleNamespace(merchant_id="synthetic-merchant", service_id="synthetic-service")

    def supports_registrar_invoice_payment(self, name):
        return name == "click"


@pytest.fixture
def case(db_session):
    actor = _create_user(db_session, role="Registrar", label="attempt")
    doctor_user = _create_user(db_session, role="derma", label="owner")
    doctor = _create_doctor(db_session, doctor_user, specialty="dermatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label=_suffix(), price=Decimal("100.00"))
    visit, _line = _create_visit_with_service(db_session, patient=patient, doctor=doctor, service=service, price=Decimal("100.00"))
    visit.confirmation_context_epoch = 120
    payment = Payment(visit_id=visit.id, amount=Decimal("1.15"), currency="UZS", method="online", status="pending", provider="click")
    db_session.add(payment)
    db_session.commit()
    context = ProfileBearerContext(actor.id, actor.auth_epoch, None, None, None)
    return SimpleNamespace(db=db_session, actor=actor, doctor=doctor, patient=patient,
                           catalog_service=service, visit=visit, payment=payment, context=context)


def _reserve(case, **kwargs):
    request = {"bearer": case.context, "target_kind": "payment", "target_id": case.payment.id,
               "provider": "click", "currency": "UZS", "amount": Decimal("1.15"),
               "description": "synthetic", "return_url": "https://example.invalid/success",
               "cancel_url": "https://example.invalid/cancel", "client_request_id": "synthetic-key"}
    request.update(kwargs)
    return ProviderAttemptService(case.db, FakeManager()).reserve(**request)


@pytest.mark.parametrize("provider,currency,amount,expected", [
    ("click", "UZS", "0.29", ("29", 2)),
    ("payme", "UZS", "1.15", ("115", 2)),
    ("kaspi", "KZT", "120.00", ("120", 0)),
])
def test_minor_units_are_decimal_exact(provider, currency, amount, expected):
    assert _minor_units(Decimal(amount), provider, currency) == expected


@pytest.mark.parametrize("provider,currency,amount", [
    ("click", "UZS", Decimal("0.001")), ("click", "UZS", 0.29),
    ("click", "UZS", Decimal("NaN")), ("click", "UZS", Decimal("0")),
    ("click", "UZS", Decimal("10000000000")), ("kaspi", "KZT", Decimal("1.01")),
    ("click", "KZT", Decimal("1")),
])
def test_invalid_amount_or_exponent_is_rejected(provider, currency, amount):
    with pytest.raises(ProviderAttemptError) as error:
        _minor_units(amount, provider, currency)
    assert error.value.status_code == 422


def test_reservation_replay_and_unknown_are_non_secret(case):
    first = _reserve(case)
    replay = _reserve(case)
    assert first.created and not replay.created and first.public_id == replay.public_id
    assert first.status == replay.status == "prepared"
    attempt = case.db.query(ProviderAttempt).one()
    assert attempt.amount_minor == "115" and attempt.currency_exponent == 2
    assert attempt.order_ref == f"clinic_{case.payment.id}_{first.public_id}"
    history = case.db.query(ProviderAttemptVisit).one()
    assert (history.visit_id, history.context_epoch, history.amount_minor) == (case.visit.id, 120, "115")
    assert case.db.query(ProviderActiveVisitReservation).count() == 1
    assert not hasattr(attempt, "payment_url")
    assert "example.invalid" not in repr(attempt.__dict__)
    with pytest.raises(ProviderAttemptError) as error:
        ProviderAttemptService(case.db, FakeManager()).claim_dispatch(public_id=first.public_id, bearer=case.context)
    assert error.value.status_code == 409
    case.db.refresh(attempt)
    assert attempt.status == "prepared"
    attempt.status = "dispatching"
    case.db.commit()
    service = ProviderAttemptService(case.db, FakeManager())
    assert service.mark_unknown(first.public_id)
    assert not service.mark_unknown(first.public_id)
    assert case.db.query(ProviderActiveVisitReservation).count() == 1
    assert _reserve(case).status == "unknown"


@pytest.mark.parametrize("change", ["description", "return_url", "client_request_id", "actor", "context"])
def test_different_intent_or_actor_cannot_reuse_reservation(case, change):
    _reserve(case)
    case.db.commit()
    kwargs = {}
    if change == "actor":
        other = _create_user(case.db, role="Registrar", label="other")
        kwargs["bearer"] = ProfileBearerContext(other.id, other.auth_epoch, None, None, None)
    elif change == "context":
        case.visit.confirmation_context_epoch += 1
        case.db.commit()
    else:
        kwargs[change] = "different"
    with pytest.raises(ProviderAttemptError) as error:
        _reserve(case, **kwargs)
    assert error.value.status_code == 409
    assert case.db.query(ProviderAttempt).count() == 1


def test_existing_reference_or_revoked_actor_fails_closed(case):
    case.payment.provider_payment_id = "legacy-unknown"
    case.db.commit()
    with pytest.raises(ProviderAttemptError) as error:
        _reserve(case)
    assert error.value.status_code == 409
    case.payment.provider_payment_id = None
    case.actor.is_active = False
    case.db.commit()
    with pytest.raises(ProviderAttemptError) as error:
        _reserve(case)
    assert error.value.status_code == 401
    assert case.db.query(ProviderAttempt).count() == 0


@pytest.mark.parametrize("change,expected", [("actor", 401), ("paid", 409)])
def test_replay_rechecks_actor_and_target_status(case, change, expected):
    _reserve(case)
    case.db.commit()
    if change == "actor":
        case.actor.is_active = False
    else:
        case.payment.status = "paid"
    case.db.commit()
    with pytest.raises(ProviderAttemptError) as error:
        _reserve(case)
    assert error.value.status_code == expected
    assert case.db.query(ProviderAttempt).count() == 1
    assert case.db.query(ProviderActiveVisitReservation).count() == 1


def test_group_reserves_all_visits_including_zero(case):
    second, _ = _create_visit_with_service(case.db, patient=case.patient, doctor=case.doctor,
                                            service=case.catalog_service, price=Decimal("0.00"))
    second.confirmation_context_epoch = 121
    invoice = PaymentInvoice(patient_id=case.patient.id, total_amount=Decimal("1.15"), currency="UZS", status="pending")
    case.db.add(invoice)
    case.db.flush()
    case.db.add_all([PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=case.visit.id, visit_amount=Decimal("1.15")),
                     PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=second.id, visit_amount=Decimal("0.00"))])
    case.db.commit()
    result = _reserve(case, target_kind="payment_invoice", target_id=invoice.id)
    assert result.created
    assert {row.visit_id for row in case.db.query(ProviderActiveVisitReservation).all()} == {case.visit.id, second.id}
    assert {row.amount_minor for row in case.db.query(ProviderAttemptVisit).all()} == {"115", "0"}


def test_group_link_changes_are_not_hidden_by_same_visit_total(case):
    invoice = PaymentInvoice(patient_id=case.patient.id, total_amount=Decimal("1.15"), currency="UZS", status="pending")
    case.db.add(invoice)
    case.db.flush()
    a = PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=case.visit.id, visit_amount=Decimal("0.50"))
    b = PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=case.visit.id, visit_amount=Decimal("0.65"))
    case.db.add_all([a, b])
    case.db.commit()
    invoice_id = invoice.id
    _reserve(case, target_kind="payment_invoice", target_id=invoice_id)
    case.db.commit()
    a.visit_amount = Decimal("0.40")
    b.visit_amount = Decimal("0.75")
    case.db.commit()
    with pytest.raises(ProviderAttemptError) as error:
        _reserve(case, target_kind="payment_invoice", target_id=invoice_id)
    assert error.value.status_code == 409
    assert case.db.query(ProviderAttempt).count() == 1


def test_invalid_allocation_and_dirty_session_are_rejected(case):
    invoice = PaymentInvoice(patient_id=case.patient.id, total_amount=Decimal("1.15"), currency="UZS", status="pending")
    case.db.add(invoice)
    case.db.flush()
    case.db.add(PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=case.visit.id, visit_amount=Decimal("1.14")))
    case.db.commit()
    with pytest.raises(ProviderAttemptError) as error:
        _reserve(case, target_kind="payment_invoice", target_id=invoice.id)
    assert error.value.status_code == 409
    case.actor.full_name = "pending unrelated mutation"
    with pytest.raises(ProviderAttemptError) as error:
        _reserve(case)
    assert error.value.status_code == 409
    assert case.actor.full_name == "pending unrelated mutation"
    case.db.rollback()
    assert case.db.query(ProviderAttempt).count() == 0


def test_different_provider_for_same_visit_is_rejected(case):
    alternate = Payment(visit_id=case.visit.id, amount=Decimal("1.15"), currency="UZS",
                        method="online", status="pending", provider="payme")
    case.db.add(alternate)
    case.db.commit()
    _reserve(case)
    case.db.commit()
    with pytest.raises(ProviderAttemptError) as error:
        _reserve(case, target_id=alternate.id, provider="payme")
    assert error.value.status_code == 409
    assert case.db.query(ProviderActiveVisitReservation).count() == 1


def test_client_key_is_scoped_to_actor_and_cannot_change_target(case):
    first = _reserve(case)
    case.db.commit()
    visit, _ = _create_visit_with_service(case.db, patient=case.patient, doctor=case.doctor,
                                          service=case.catalog_service, price=Decimal("100.00"))
    visit.confirmation_context_epoch = 150
    other_payment = Payment(visit_id=visit.id, amount=Decimal("1.15"), currency="UZS",
                            method="online", status="pending", provider="click")
    case.db.add(other_payment)
    case.db.commit()
    other_id = other_payment.id
    with pytest.raises(ProviderAttemptError) as error:
        _reserve(case, target_id=other_id)
    assert error.value.status_code == 409
    assert case.db.query(ProviderAttempt).count() == 1
    other_actor = _create_user(case.db, role="Registrar", label="otherkey")
    other_context = ProfileBearerContext(other_actor.id, other_actor.auth_epoch, None, None, None)
    second = _reserve(case, target_id=other_id, bearer=other_context)
    assert second.created and second.public_id != first.public_id


def test_empty_client_key_is_rejected(case):
    with pytest.raises(ProviderAttemptError) as error:
        _reserve(case, client_request_id="  ")
    assert error.value.status_code == 422


def test_commit_failure_rolls_back_header_and_all_reservations(case, monkeypatch):
    def fail_commit():
        raise RuntimeError("synthetic commit failure")

    monkeypatch.setattr(case.db, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="synthetic commit failure"):
        _reserve(case)
        case.db.commit()
    case.db.rollback()
    assert case.db.query(ProviderAttempt).count() == 0
    assert case.db.query(ProviderAttemptVisit).count() == 0
    assert case.db.query(ProviderActiveVisitReservation).count() == 0


def test_reserve_does_not_commit_previously_flushed_caller_work(case):
    original_name = case.actor.full_name
    actor_id = case.actor.id
    case.actor.full_name = "synthetic uncommitted edit"
    case.db.flush()
    assert _reserve(case).created
    case.db.rollback()
    assert case.db.get(type(case.actor), actor_id).full_name == original_name
    assert case.db.query(ProviderAttempt).count() == 0
    assert case.db.query(ProviderActiveVisitReservation).count() == 0
