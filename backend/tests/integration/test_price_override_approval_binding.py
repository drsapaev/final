"""Bound manual price decisions with synthetic invoices and mocked delivery."""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import DBAPIError

from app.models.audit import AuditLog
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.visit import VisitService
from app.services.dental_api_service import DentalApiService
from app.services.price_override_approval import (
    PriceOverrideApprovalError,
    PriceOverrideApprovalService,
)
from app.services.profile_contact_security import ProfileBearerContext
from tests.conftest import mint_access_token
from tests.integration.test_derma_price_override_integrity import _create_user
from tests.integration.test_price_override_request_binding import _post, issuer  # noqa: F401


@pytest.fixture
def review(issuer, monkeypatch):
    assert _post(issuer, '"5.00"').status_code == 200
    db = issuer["db"]
    row = db.query(DoctorPriceOverride).one()
    actor = _create_user(db, role="Registrar", label="review")
    monkeypatch.setattr(DentalApiService, "send_price_override_result_notification", AsyncMock())
    issuer.update({"override": row, "actor": actor, "review_headers": {"Authorization": f"Bearer {mint_access_token(actor)}"}})
    return issuer


def _decide(f, route, action="approve", reason=None):
    data = {"action": action, "rejection_reason": reason}
    if route == "registrar":
        data["override_id"] = f["override"].id
        return f["client"].post("/api/v1/registrar/price-override/approve", headers=f["review_headers"], json=data)
    return f["client"].put(f'/api/v1/dental/price-override/{f["override"].id}/approve', headers=f["review_headers"], json=data)


@pytest.mark.parametrize("issuer", ["derma"], indirect=True)
def test_revoked_session_is_rejected_before_override_existence_is_revealed(review):
    actor = review["actor"]
    actor_id, epoch = actor.id, actor.auth_epoch
    missing_id = review["override"].id + 1000000
    service = PriceOverrideApprovalService(review["db"])
    stale = ProfileBearerContext(actor_id, epoch + 1, None, None, None)
    with pytest.raises(PriceOverrideApprovalError) as invalid:
        service.process(override_id=missing_id, action="reject", rejection_reason="Synthetic",
                        approver_id=actor_id, bearer=stale)
    assert invalid.value.status_code == 401
    valid = ProfileBearerContext(actor_id, epoch, None, None, None)
    with pytest.raises(PriceOverrideApprovalError) as missing:
        service.process(override_id=missing_id, action="reject", rejection_reason="Synthetic",
                        approver_id=actor_id, bearer=valid)
    assert missing.value.status_code == 404


@pytest.mark.parametrize("issuer", ["derma", "dental"], indirect=True)
@pytest.mark.parametrize("route", ["registrar", "dental"])
def test_valid_approval_requotes_draft_invoice_and_audits_once(review, route):
    db, visit, row = (review[key] for key in ("db", "visit", "override"))
    invoice = PaymentInvoice(patient_id=visit.patient_id, total_amount=Decimal("123.45"), currency="UZS")
    db.add(invoice)
    db.flush()
    link = PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visit.id, visit_amount=Decimal("123.45"))
    db.add(link)
    db.commit()

    response = _decide(review, route)
    assert response.status_code == 200, response.text
    assert _decide(review, route).status_code == 409
    db.expire_all()
    assert row.status == "approved"
    assert invoice.total_amount == link.visit_amount == review["line"].price == Decimal("5.00")
    audit = db.query(AuditLog).filter_by(action="price_override_approved", entity_id=row.id).one()
    assert audit.actor_user_id == review["actor"].id
    assert audit.payload["currency"] == "UZS"
    assert audit.payload["previous_unit_price"] == "123.45"
    assert audit.payload["unit_price"] == "5.00"


@pytest.mark.parametrize("issuer", ["derma"], indirect=True)
@pytest.mark.parametrize("route", ["registrar", "dental"])
def test_legacy_reject_remains_available(review, route):
    review["override"].target_scope = None
    review["override"].target_visit_service_id = None
    review["override"].visit_context_epoch = None
    review["db"].commit()
    response = _decide(review, route, action="reject", reason="Synthetic refusal")
    assert response.status_code == 200, response.text
    review["db"].refresh(review["override"])
    assert review["override"].status == "rejected"
    assert review["override"].rejection_reason == "Synthetic refusal"
    assert review["line"].price == Decimal("123.45")


@pytest.mark.parametrize("issuer", ["derma"], indirect=True)
@pytest.mark.parametrize("mutation", ["legacy", "target", "epoch", "owner", "generation", "owner_inactive", "doctor_inactive", "service_inactive", "before", "current_price", "line_generation", "owner_price_generation", "doctor_auth_epoch", "requester_epoch", "requester_role", "closed"])
def test_invalid_binding_fails_closed_before_any_financial_decision(review, mutation):
    row = review["override"]
    if mutation == "legacy":
        row.target_scope = None
    elif mutation == "target":
        row.target_visit_service_id = None
    elif mutation == "epoch":
        row.price_context_generation += 1
    elif mutation == "owner":
        row.doctor_owner_user_id = None
    elif mutation == "generation":
        row.doctor_owner_generation += 1
    elif mutation == "owner_inactive":
        review["user"].is_active = False
    elif mutation == "doctor_inactive":
        review["doctor"].active = False
    elif mutation == "service_inactive":
        review["service"].active = False
    elif mutation == "before":
        row.visit_price_before = Decimal("1.00")
    elif mutation == "line_generation":
        row.price_line_generation += 1
    elif mutation == "owner_price_generation":
        row.price_owner_generation += 1
    elif mutation == "doctor_auth_epoch":
        row.doctor_user_auth_epoch += 1
    elif mutation == "requester_epoch":
        row.requester_auth_epoch += 1
    elif mutation == "requester_role":
        review["user"].role = "Patient"
    elif mutation == "closed":
        review["visit"].status = "closed"
    else:
        review["line"].price = Decimal("1.00")
    review["db"].commit()
    response = _decide(review, "registrar")
    assert response.status_code == 409, response.text
    assert "устарел" in response.text
    review["db"].refresh(row)
    assert row.status == "pending"


@pytest.mark.parametrize("issuer", ["derma"], indirect=True)
def test_approval_changes_only_the_bound_line(review):
    line = review["line"]
    second = VisitService(visit_id=line.visit_id, service_id=line.service_id, code=line.code,
                          name=line.name, qty=1, price=Decimal("90.00"), currency=line.currency)
    review["db"].add(second)
    review["db"].commit()
    assert _decide(review, "registrar").status_code == 200
    review["db"].refresh(line)
    review["db"].refresh(second)
    assert (line.price, second.price) == (Decimal("5.00"), Decimal("90.00"))


@pytest.mark.parametrize("issuer", ["derma"], indirect=True)
def test_admin_request_without_doctor_allows_catalog_flag_disabled(review):
    requester, visit, service, row = (review[key] for key in ("user", "visit", "service", "override"))
    requester.role = "Admin"
    visit.doctor_id = None
    service.allow_doctor_price_override = False
    row.requester_type = "admin"
    row.doctor_id = None
    row.doctor_owner_user_id = None
    row.doctor_owner_generation = None
    row.price_owner_generation = None
    row.doctor_user_auth_epoch = None
    review["db"].commit()
    approval = PriceOverrideApprovalService(review["db"])
    assert approval._check_binding({requester.id: requester}, None, visit, service, row).id == review["line"].id
    requester.role = "Patient"
    review["db"].flush()
    with pytest.raises(PriceOverrideApprovalError, match="устарел"):
        approval._check_binding({requester.id: requester}, None, visit, service, row)


@pytest.mark.parametrize("issuer", ["derma"], indirect=True)
def test_unrelated_confirmation_epoch_does_not_invalidate_price_binding(review):
    # Another line or a fresh confirmation changes the broad confirmation
    # epoch; the narrow visit/line generations still pin this exact request.
    review["visit"].confirmation_context_epoch += 1
    review["db"].commit()
    response = _decide(review, "registrar")
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("issuer", ["derma"], indirect=True)
@pytest.mark.parametrize("status", ["pending_confirmation", "confirmation_processing"])
def test_confirmation_context_must_support_atomic_recovery(review, status):
    visit = review["visit"]
    visit.status = status
    visit.confirmation_token = "synthetic-existing-token"
    review["db"].commit()
    # This lightweight schema does not install the confirmation trigger.
    expected = 503 if status == "pending_confirmation" else 409
    assert _decide(review, "registrar").status_code == expected
    review["db"].refresh(visit)
    assert visit.confirmation_token == "synthetic-existing-token"
    review["db"].refresh(review["line"])
    review["db"].refresh(review["override"])
    assert review["line"].price == Decimal("123.45")
    assert review["override"].status == "pending"


@pytest.mark.parametrize("issuer", ["derma"], indirect=True)
@pytest.mark.parametrize("route", ["registrar", "dental"])
def test_justified_rejection_required(review, route):
    assert _decide(review, route, action="reject", reason="  ").status_code == 400
    review["db"].refresh(review["override"])
    assert review["override"].status == "pending"


@pytest.mark.parametrize("dialect,sqlstate,sqlite_code,is_lock", [
    ("postgresql", "55P03", 0, True), ("postgresql", "40P01", 0, True),
    ("postgresql", "40001", 0, True),
    ("postgresql", "23505", 0, False), ("sqlite", None, 5, True),
    ("sqlite", None, 517, True), ("sqlite", None, 2067, False),
])
def test_database_errors_are_mapped_only_for_lock_conflicts(dialect, sqlstate, sqlite_code, is_lock):
    class FakeSession:
        rolled_back = False

        def rollback(self):
            self.rolled_back = True

        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name=dialect))

    class Failure(Exception):
        pass

    original = Failure()
    original.sqlstate = sqlstate
    original.sqlite_errorcode = sqlite_code
    failure = DBAPIError("synthetic", {}, original)
    db = FakeSession()
    service = PriceOverrideApprovalService(db)

    def fail(*args):
        raise failure

    service._lock_request = fail
    expected = PriceOverrideApprovalError if is_lock else DBAPIError
    with pytest.raises(expected) as error:
        service.process(override_id=1, action="reject", rejection_reason="synthetic", approver_id=1, bearer=None)
    assert db.rolled_back
    if is_lock:
        assert error.value.status_code == 409
    else:
        assert error.value is failure
