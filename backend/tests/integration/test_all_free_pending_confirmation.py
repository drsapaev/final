"""Confirmation and registration behavior while an All Free request waits."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints.registrar_wizard import _cart, _invoice
from app.crud.clinic import clinic_today
from app.models.online_queue import OnlineQueueEntry
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.all_free_approval import ALL_FREE_DECISION_REQUIRED
from app.services.visit_lifecycle_service import VisitLifecycleService
from tests.integration.test_all_free_decision_concurrency_pg import (  # noqa: F401
    approval_case,
    decision_engines,
)
from tests.integration.test_all_free_registrar_workflow import (
    migrated_visit_confirmation_context,  # noqa: F401
)
from tests.integration.test_registrar_benefit_decision_pg import (  # noqa: F401
    benefit_client,
    configured_benefit_db,
)

pytestmark = pytest.mark.integration


@pytest.mark.usefixtures("migrated_visit_confirmation_context")
def test_registrar_stages_requested_visit_without_confirmation_or_queue(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
    test_service,
    monkeypatch,
):
    notify = AsyncMock()
    monkeypatch.setattr(
        _cart.notification_sender_service, "send_all_free_request_notification", notify
    )
    test_service.currency = "UZS"
    db_session.commit()
    response = client.post(
        "/api/v1/registrar/cart",
        headers=registrar_auth_headers,
        json={
            "patient_id": test_patient.id,
            "discount_mode": "all_free",
            "all_free": True,
            "payment_method": "cash",
            "visits": [
                {
                    "doctor_id": test_doctor.id,
                    "visit_date": clinic_today(db_session).isoformat(),
                    "visit_time": "10:30",
                    "department": "cardiology",
                    "services": [{"service_id": test_service.id, "quantity": 1}],
                }
            ],
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    visit = db_session.get(Visit, data["visit_ids"][0])
    assert (visit.status, visit.approval_status) == ("pending_confirmation", "pending")
    assert visit.confirmed_at is None
    assert visit.confirmation_token is None
    assert data["created_visits"][0]["confirmation_required"] is False
    assert data["created_visits"][0]["confirmation_token"] is None
    assert data["message"] == ALL_FREE_DECISION_REQUIRED
    assert data["queue_numbers"] == {}
    assert db_session.query(OnlineQueueEntry).filter_by(visit_id=visit.id).count() == 0
    notify.assert_awaited_once()


def test_staff_confirmation_and_status_transition_wait_for_approval(
    db_session, test_visit, admin_user
):
    test_visit.discount_mode = "all_free"
    test_visit.approval_status = "pending"
    db_session.commit()
    lifecycle = VisitLifecycleService(db_session)

    with pytest.raises(HTTPException) as confirm_error:
        lifecycle.confirm_visit(test_visit.id, admin_user)
    with pytest.raises(HTTPException) as transition_error:
        lifecycle.transition_status(test_visit.id, "confirmed", admin_user)

    for error in (confirm_error, transition_error):
        assert error.value.status_code == 409
        assert error.value.detail == ALL_FREE_DECISION_REQUIRED
    assert test_visit.status == "pending_confirmation"
    assert test_visit.confirmed_at is None


def test_existing_pwa_invitation_waits_for_all_free_decision(
    client, db_session, test_visit, test_service,
):
    test_visit.discount_mode = "all_free"
    test_visit.approval_status = "pending"
    test_visit.confirmation_channel = "pwa"
    test_visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
    db_session.add(VisitService(
        visit_id=test_visit.id, service_id=test_service.id,
        name="Synthetic consultation", qty=1, price=Decimal("50000.00"), currency="UZS",
    ))
    db_session.commit()

    response = client.post(
        "/api/v1/patient/visits/confirm",
        json={
            "token": test_visit.confirmation_token,
            "patient_phone": test_visit.patient.phone,
        },
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == ALL_FREE_DECISION_REQUIRED
    db_session.refresh(test_visit)
    assert test_visit.status == "pending_confirmation"
    assert test_visit.confirmed_at is None


def test_captured_invoice_is_recorded_without_confirming_pending_all_free(
    db_session, test_visit, test_service, admin_user, monkeypatch
):
    test_visit.discount_mode = "all_free"
    test_visit.approval_status = "pending"
    amount = Decimal("50000.00")
    invoice = PaymentInvoice(
        patient_id=test_visit.patient_id,
        status="processing",
        total_amount=amount,
        currency="UZS",
        provider="click",
        provider_payment_id="synthetic-preexisting-checkout",
    )
    db_session.add_all(
        [
            invoice,
            VisitService(
                visit_id=test_visit.id,
                service_id=test_service.id,
                name="Synthetic service",
                price=amount,
                qty=1,
                currency="UZS",
            ),
        ]
    )
    db_session.flush()
    db_session.add(
        PaymentInvoiceVisit(
            invoice_id=invoice.id, visit_id=test_visit.id, visit_amount=amount
        )
    )
    db_session.commit()
    manager = Mock()
    manager.supports_registrar_invoice_payment.return_value = True
    manager.check_payment_status.return_value = SimpleNamespace(
        success=True, status="completed", payment_id=invoice.provider_payment_id,
        provider_data={
            "merchant_trans_id": invoice.provider_payment_id,
            "status": 2,
            "amount": str(amount),
            "currency": "UZS",
            "click_trans_id": "10401",
        },
    )
    monkeypatch.setattr(_invoice, "get_payment_manager", lambda: manager)

    result = _invoice.check_invoice_status(invoice.id, db_session, admin_user)

    assert result["status"] == "paid"
    assert (
        db_session.query(Payment)
        .filter_by(visit_id=test_visit.id, status="paid")
        .one()
        .amount
        == amount
    )
    assert test_visit.status == "pending_confirmation"
    assert test_visit.confirmed_at is None


def test_staff_confirmation_checks_fresh_approval_on_postgres(approval_case):
    engine, runtime, _, visit_id, _, _, admin_ids = approval_case
    with Session(engine) as db:
        visit = db.get(Visit, visit_id)
        visit.approval_status = "approved"
        visit.status = "pending_confirmation"
        db.commit()

    with Session(runtime) as confirmation_db:
        cached_visit = confirmation_db.get(Visit, visit_id)
        assert cached_visit.approval_status == "approved"
        with Session(engine) as request_db:
            request_db.get(Visit, visit_id).approval_status = "pending"
            request_db.commit()

        with pytest.raises(HTTPException) as error:
            VisitLifecycleService(confirmation_db).confirm_visit(
                visit_id, confirmation_db.get(User, admin_ids[0])
            )
        assert error.value.status_code == 409
        assert error.value.detail == ALL_FREE_DECISION_REQUIRED
        assert cached_visit.status == "pending_confirmation"
