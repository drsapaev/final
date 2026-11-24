"""End-to-end acceptance tests for registrar all-free decisions."""

import importlib.util
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.api.v1.endpoints.cashier import _visits as cashier_visits
from app.api.v1.endpoints.registrar_wizard import _cart
from app.models.all_free_request import AllFreeRequest, AllFreeRequestEvent
from app.models.clinic import ClinicSettings
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.visit import Visit, VisitService
from app.services.all_free_request_service import (
    AllFreeRequestError,
    AllFreeRequestService,
)
from tests.integration.test_registrar_cart_encounter_grouping import (
    _counts,
    _headers,
    _service,
    _visit,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.usefixtures("migrated_visit_confirmation_context"),
]


@pytest.fixture
def migrated_visit_confirmation_context(db_session):
    """Exercise service-line and visit generations from the real 0102 revision."""
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0102_visit_confirmation_context.py"
    spec = importlib.util.spec_from_file_location("synthetic_allfree_http_0102", path)
    assert spec is not None and spec.loader is not None
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    connection = db_session.connection()
    connection.exec_driver_sql("ALTER TABLE visits DROP COLUMN confirmation_context_epoch")
    with Operations.context(MigrationContext.configure(connection)):
        revision.upgrade()


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_pending_decision_preserves_baseline_and_requotes_invoice(
    client, db_session, admin_user, test_patient, monkeypatch, action
):
    monkeypatch.setattr(_cart.notification_sender_service, "send_all_free_request_notification", AsyncMock(return_value=True))
    monkeypatch.setattr(_cart.notification_sender_service, "send_all_free_decision_notification", AsyncMock(return_value=True))
    setting = db_session.query(ClinicSettings).filter_by(key="all_free_auto_approve").first()
    if setting is None:
        setting = ClinicSettings(key="all_free_auto_approve", value=False, category="benefits")
        db_session.add(setting)
    else:
        setting.value = False
    db_session.commit()
    service = _service(db_session)
    item = _visit(service.id, date.today() + timedelta(days=1))
    item["services"][0]["quantity"] = 2
    response = client.post(
        "/api/v1/registrar/cart", headers=_headers(admin_user),
        json={"patient_id": test_patient.id, "discount_mode": "all_free", "all_free": True,
              "payment_method": "cash", "visits": [item]},
    )
    assert response.status_code == 200, response.text
    visit_id = response.json()["visit_ids"][0]
    invoice_id = response.json()["invoice_id"]
    db_session.expire_all()
    visit = db_session.get(Visit, visit_id)
    line = db_session.query(VisitService).filter_by(visit_id=visit_id).one()
    invoice = db_session.get(PaymentInvoice, invoice_id)
    link = db_session.query(PaymentInvoiceVisit).filter_by(invoice_id=invoice_id, visit_id=visit_id).one()
    request = db_session.query(AllFreeRequest).filter_by(visit_id=visit_id).one()
    assert request.status == "pending" and request.baseline_total == Decimal("200.00")
    assert line.price == Decimal("100.00") and line.qty == 2
    assert invoice.total_amount == link.visit_amount == Decimal("200.00")
    assert visit.status == "pending_confirmation" and visit.confirmation_token is None
    assert response.json()["queue_numbers"] == {}
    assert response.json()["created_visits"][0]["confirmation_required"] is False
    assert response.json()["created_visits"][0]["approval_status"] == "pending"

    service.price = Decimal("175.00")
    db_session.commit()

    decision = client.post(
        "/api/v1/admin/all-free-approve", headers=_headers(admin_user),
        json={"visit_id": visit_id, "action": action},
    )
    assert decision.status_code == 200, decision.text
    db_session.expire_all()
    expected = Decimal("0.00") if action == "approve" else Decimal("200.00")
    assert db_session.get(PaymentInvoice, invoice_id).total_amount == expected
    assert db_session.query(PaymentInvoiceVisit).filter_by(invoice_id=invoice_id, visit_id=visit_id).one().visit_amount == expected
    assert db_session.query(VisitService).filter_by(visit_id=visit_id).one().price * 2 == expected
    decided = db_session.query(AllFreeRequest).filter_by(visit_id=visit_id).one()
    assert decided.status == ("approved" if action == "approve" else "rejected")
    assert decided.baseline_total == Decimal("200.00")
    assert db_session.query(AllFreeRequestEvent).filter_by(request_id=decided.id, event_type=decided.status).count() == 1
    if action == "reject":
        monkeypatch.setattr(cashier_visits, "_emit_payment_notification", AsyncMock())
        payment_url = f"/api/v1/cashier/visits/{visit_id}/mark-paid"
        paid = client.post(payment_url, headers=_headers(admin_user))
        assert paid.status_code == 200, paid.text
        client.post(payment_url, headers=_headers(admin_user))
        assert db_session.query(Payment).filter_by(visit_id=visit_id).one().amount == expected


def test_configured_auto_approval_is_audited_and_applied(
    client, db_session, admin_user, test_patient, monkeypatch
):
    monkeypatch.setattr(_cart.notification_sender_service, "send_all_free_request_notification", AsyncMock(return_value=True))
    monkeypatch.setattr(_cart.notification_sender_service, "send_all_free_decision_notification", AsyncMock(return_value=True))
    setting = db_session.query(ClinicSettings).filter_by(key="all_free_auto_approve").first()
    if setting is None:
        db_session.add(ClinicSettings(key="all_free_auto_approve", value=True, category="benefits"))
    else:
        setting.value = True
    db_session.commit()
    service = _service(db_session)
    response = client.post(
        "/api/v1/registrar/cart", headers=_headers(admin_user),
        json={"patient_id": test_patient.id, "discount_mode": "all_free", "all_free": True,
              "payment_method": "cash", "visits": [_visit(service.id, date.today() + timedelta(days=1))]},
    )
    assert response.status_code == 200, response.text
    visit_id = response.json()["visit_ids"][0]
    db_session.expire_all()
    request = db_session.query(AllFreeRequest).filter_by(visit_id=visit_id).one()
    assert request.status == "approved" and request.decision_kind == "policy"
    assert request.policy_auto_approve is True and request.baseline_total == Decimal("100.00")
    assert db_session.query(AllFreeRequestEvent).filter_by(request_id=request.id, event_type="approved").count() == 1
    assert db_session.get(PaymentInvoice, response.json()["invoice_id"]).total_amount == Decimal("0.00")
    assert db_session.get(Visit, visit_id).status == "confirmed"


@pytest.mark.parametrize("second_action", ["approve", "reject"])
def test_multiple_requests_in_one_encounter_are_decided_independently(
    client, db_session, admin_user, test_patient, monkeypatch, second_action
):
    monkeypatch.setattr(_cart.notification_sender_service, "send_all_free_request_notification", AsyncMock(return_value=True))
    monkeypatch.setattr(_cart.notification_sender_service, "send_all_free_decision_notification", AsyncMock(return_value=True))
    setting = db_session.query(ClinicSettings).filter_by(key="all_free_auto_approve").first()
    if setting is None:
        db_session.add(ClinicSettings(key="all_free_auto_approve", value=False, category="benefits"))
    else:
        setting.value = False
    db_session.commit()
    service = _service(db_session)
    first_day = date.today() + timedelta(days=1)
    response = client.post(
        "/api/v1/registrar/cart", headers=_headers(admin_user),
        json={"patient_id": test_patient.id, "discount_mode": "all_free", "all_free": True,
              "payment_method": "cash", "visits": [_visit(service.id, first_day), _visit(service.id, first_day + timedelta(days=1))]},
    )
    assert response.status_code == 200, response.text
    visit_a, visit_b = response.json()["visit_ids"]
    invoice_id = response.json()["invoice_id"]
    first = client.post("/api/v1/admin/all-free-approve", headers=_headers(admin_user),
                        json={"visit_id": visit_a, "action": "approve"})
    assert first.status_code == 200, first.text
    db_session.expire_all()
    assert db_session.query(AllFreeRequest).filter_by(visit_id=visit_b).one().status == "pending"
    assert db_session.get(PaymentInvoice, invoice_id).total_amount == Decimal("100.00")
    assert db_session.query(VisitService).filter_by(visit_id=visit_b).one().price == Decimal("100.00")
    blocked = client.post(f"/api/v1/cashier/visits/{visit_a}/mark-paid", headers=_headers(admin_user))
    assert blocked.status_code == 409, blocked.text
    second = client.post("/api/v1/admin/all-free-approve", headers=_headers(admin_user),
                         json={"visit_id": visit_b, "action": second_action})
    assert second.status_code == 200, second.text
    db_session.expire_all()
    expected = Decimal("0.00") if second_action == "approve" else Decimal("100.00")
    assert db_session.get(PaymentInvoice, invoice_id).total_amount == expected


def test_cart_rolls_back_every_visit_when_a_request_cannot_be_staged(
    client, db_session, admin_user, test_patient, monkeypatch,
):
    notification = AsyncMock(return_value=True)
    monkeypatch.setattr(_cart.notification_sender_service, "send_all_free_request_notification", notification)
    stage = AllFreeRequestService.stage_request
    staged = []

    def fail_second_request(service, **kwargs):
        if staged:
            raise AllFreeRequestError(409, "Synthetic request staging failure")
        request = stage(service, **kwargs)
        staged.append(request.id)
        return request

    monkeypatch.setattr(AllFreeRequestService, "stage_request", fail_second_request)
    service = _service(db_session)
    patient_id = test_patient.id
    before = _counts(db_session, patient_id)
    first_day = date.today() + timedelta(days=1)
    response = client.post(
        "/api/v1/registrar/cart",
        headers=_headers(admin_user),
        json={"patient_id": patient_id, "discount_mode": "all_free", "visits": [
            _visit(service.id, first_day), _visit(service.id, first_day + timedelta(days=1)),
        ]},
    )

    assert response.status_code == 409 and staged, response.text
    db_session.expire_all()
    assert _counts(db_session, patient_id) == before
    assert db_session.get(AllFreeRequest, staged[0]) is None
    assert db_session.query(AllFreeRequestEvent).filter_by(request_id=staged[0]).count() == 0
    notification.assert_not_awaited()


def test_legacy_rejection_without_a_baseline_requires_reconciliation(
    client, db_session, admin_user, test_patient, monkeypatch,
):
    notify = AsyncMock(return_value=True)
    monkeypatch.setattr(_cart.notification_sender_service, "send_all_free_decision_notification", notify)
    visit = Visit(
        patient_id=test_patient.id, status="pending_confirmation",
        discount_mode="all_free", approval_status="pending",
    )
    db_session.add(visit)
    db_session.commit()
    visit_id = visit.id

    decision = client.post(
        "/api/v1/admin/all-free-approve", headers=_headers(admin_user),
        json={"visit_id": visit_id, "action": "reject"},
    )

    assert decision.status_code == 409, decision.text
    assert "требуют сверки" in decision.json()["detail"]
    db_session.expire_all()
    assert db_session.get(Visit, visit_id).approval_status == "pending"
    notify.assert_not_awaited()
