"""Exercise doctor All Free requests through the owning HTTP transactions."""

import asyncio
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api.v1.endpoints.registrar_wizard import _cart
from app.models.all_free_request import AllFreeRequest, AllFreeRequestEvent
from app.models.encounter import Encounter
from app.models.payment import Payment
from app.models.telegram_config import TelegramUser
from app.models.visit import Visit, VisitService
from app.models.visit_invitation_delivery import VisitInvitationDelivery
from app.services.all_free_request_service import (
    AllFreeRequestError,
    AllFreeRequestService,
)
from app.services.visit_invitation_delivery import (
    claim_visit_invitation,
    send_claimed_visit_invitation,
)
from tests.integration.test_all_free_registrar_workflow import (
    migrated_visit_confirmation_context,  # noqa: F401
)
from tests.integration.test_docsched_repeat_policy import _setting, mock_invitations  # noqa: F401
from tests.integration.test_docsched_schedule_next_integrity import (
    _clinic_today,
    _prior_context_visit,
    _schedule_payload,
)
from tests.integration.test_registrar_cart_encounter_grouping import _headers

pytestmark = pytest.mark.integration

SCHEDULE = "/api/v1/doctor/visits/schedule-next"


@pytest.fixture
def all_free_settings(db_session, mock_invitations, migrated_visit_confirmation_context):
    _setting(db_session, "all_free_auto_approve", False)
    return mock_invitations


def _doctor_payload(db, patient, service):
    service.price = Decimal("125.50")
    db.commit()
    return _schedule_payload(
        patient, service, visit_date=_clinic_today(db) + timedelta(days=2),
        discount_mode="all_free", services=[{"service_id": service.id, "quantity": 2}],
    )


@pytest.mark.parametrize("action", ["approve", "reject"])
def test_doctor_all_free_waits_for_admin_and_keeps_the_original_prices(
    client, db_session, all_free_settings, monkeypatch, cardio_auth_headers,
    test_patient, test_doctor, test_service, admin_user, action,
):
    monkeypatch.setattr(_cart.notification_sender_service, "send_all_free_decision_notification", AsyncMock())
    _prior_context_visit(db_session, patient=test_patient, doctor=test_doctor)
    test_service.currency = "USD"
    payload = _doctor_payload(db_session, test_patient, test_service)
    doctor_headers = {**cardio_auth_headers, "Idempotency-Key": f"synthetic-{uuid4()}", "Idempotency-Intent": "new"}
    first = client.post(SCHEDULE, headers=doctor_headers, json=payload)
    assert first.status_code == 200, first.text
    visit_id = first.json()["visit_id"]
    assert first.json()["status"] == "pending_confirmation"
    assert first.json()["confirmation"]["token"] is None
    assert first.json()["confirmation"]["expires_at"] is None
    assert first.json()["confirmation"]["total_amount"] == 251.0

    # The legacy flag and explicit mode refer to the same operation.
    retry = client.post(SCHEDULE, headers=doctor_headers, json={**payload, "discount_mode": "none", "all_free": True})
    assert retry.status_code == 200, retry.text
    assert retry.json()["visit_id"] == visit_id and retry.json()["idempotent_replay"] is True
    assert retry.json()["confirmation"]["token"] is None
    db_session.expire_all()
    visit = db_session.get(Visit, visit_id)
    assert visit.discount_mode == "all_free" and visit.approval_status == "pending"
    request = db_session.query(AllFreeRequest).filter_by(visit_id=visit_id).one()
    assert request.status == "pending" and request.baseline_total == Decimal("251.00")
    assert request.requested_by_user_id == test_doctor.user_id
    assert db_session.query(VisitService).filter_by(visit_id=visit_id).one().currency == "USD"
    assert db_session.query(AllFreeRequestEvent).filter_by(request_id=request.id).count() == 1
    assert db_session.query(VisitInvitationDelivery).filter_by(visit_id=visit_id).count() == 0
    assert not all_free_settings

    admin_headers = _headers(admin_user)
    denied = client.post(
        "/api/v1/admin/all-free-approve", headers=cardio_auth_headers,
        json={"visit_id": visit_id, "action": action},
    )
    assert denied.status_code == 403, denied.text
    denied = client.post(f"/api/v1/registrar/visits/{visit_id}/confirm", headers=admin_headers, json={})
    assert denied.status_code == 409, denied.text
    denied = client.post(f"/api/v1/cashier/visits/{visit_id}/mark-paid", headers=admin_headers)
    assert denied.status_code == 409, denied.text
    assert db_session.query(Payment).filter_by(visit_id=visit_id).count() == 0

    test_service.price = Decimal("900.00")
    db_session.commit()
    listing = client.get("/api/v1/admin/all-free-requests", headers=admin_headers)
    assert listing.status_code == 200, listing.text
    listed = next(item for item in listing.json() if item["id"] == visit_id)
    assert Decimal(str(listed["total_original_amount"])) == Decimal("251.00")
    decision = client.post("/api/v1/admin/all-free-approve", headers=admin_headers, json={"visit_id": visit_id, "action": action})
    assert decision.status_code == 200, decision.text
    db_session.expire_all()
    decided = db_session.get(AllFreeRequest, request.id)
    assert decided.baseline_total == Decimal("251.00")
    assert decided.status == ("approved" if action == "approve" else "rejected")
    assert db_session.query(VisitService).filter_by(visit_id=visit_id).one().price == (
        Decimal("0.00") if action == "approve" else Decimal("125.50")
    )
    listing = client.get("/api/v1/admin/all-free-requests", headers=admin_headers, params={"status_filter": "all"})
    assert listing.status_code == 200, listing.text
    listed = next(item for item in listing.json() if item["id"] == visit_id)
    assert Decimal(str(listed["total_original_amount"])) == Decimal("251.00")
    repeated = client.post(SCHEDULE, headers=doctor_headers, json=payload)
    assert repeated.status_code == 200, repeated.text
    assert repeated.json()["idempotent_replay"] and repeated.json()["visit_id"] == visit_id
    confirmation = repeated.json()["confirmation"]
    assert confirmation["token"] is None
    assert confirmation["total_amount"] == (0.0 if action == "approve" else 251.0)


def test_doctor_all_free_auto_approval_is_recorded_before_invitation(
    client, db_session, all_free_settings, cardio_auth_headers, test_patient, test_doctor, test_service,
):
    _setting(db_session, "all_free_auto_approve", True)
    _prior_context_visit(db_session, patient=test_patient, doctor=test_doctor)
    result = client.post(SCHEDULE, headers=cardio_auth_headers, json=_doctor_payload(db_session, test_patient, test_service))
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["confirmation"]["token"] and body["confirmation"]["total_amount"] == 0.0
    db_session.expire_all()
    request = db_session.query(AllFreeRequest).filter_by(visit_id=body["visit_id"]).one()
    assert request.status == "approved" and request.decision_kind == "policy"
    events = db_session.query(AllFreeRequestEvent).filter_by(request_id=request.id).order_by(AllFreeRequestEvent.id).all()
    assert [event.event_type for event in events] == ["requested", "approved"]
    assert db_session.query(VisitInvitationDelivery).filter_by(visit_id=body["visit_id"], state="pending").count() == 1
    assert not all_free_settings


def test_doctor_paid_visit_still_issues_a_confirmation(
    client, db_session, all_free_settings, cardio_auth_headers, test_patient, test_doctor, test_service,
):
    _prior_context_visit(db_session, patient=test_patient, doctor=test_doctor)
    payload = _doctor_payload(db_session, test_patient, test_service)
    payload["discount_mode"] = "none"
    result = client.post(SCHEDULE, headers=cardio_auth_headers, json=payload)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["confirmation"]["token"] and body["confirmation"]["total_amount"] == 251.0
    assert db_session.query(AllFreeRequest).filter_by(visit_id=body["visit_id"]).count() == 0
    assert db_session.query(VisitInvitationDelivery).filter_by(visit_id=body["visit_id"], state="pending").count() == 1
    assert not all_free_settings


@pytest.mark.parametrize("ownership", ["unverified", "before_claim", "after_claim", "reattested", "current"])
def test_doctor_invitation_requires_current_chat_ownership(
    client, db_session, all_free_settings, monkeypatch, cardio_auth_headers,
    test_patient, test_doctor, test_service, ownership,
):
    _setting(db_session, "all_free_auto_approve", True)
    _prior_context_visit(db_session, patient=test_patient, doctor=test_doctor)
    link = TelegramUser(
        patient_id=test_patient.id, chat_id=90000 + test_patient.id, patient_link_epoch=5,
        patient_owner_generation_snapshot=(
            None if ownership == "unverified" else test_patient.notification_owner_generation
        ),
    )
    db_session.add(link)
    db_session.commit()
    payload = _doctor_payload(db_session, test_patient, test_service)
    payload["confirmation_channel"] = "telegram"
    result = client.post(SCHEDULE, headers=cardio_auth_headers, json=payload)
    assert result.status_code == 200, result.text
    delivery = db_session.query(VisitInvitationDelivery).filter_by(visit_id=result.json()["visit_id"]).one_or_none()
    if ownership == "unverified":
        assert delivery is None
        return
    assert delivery is not None
    if ownership == "before_claim":
        link.patient_owner_generation_snapshot = None
        db_session.commit()
        assert claim_visit_invitation(db_session, delivery.id) is None
        assert db_session.get(VisitInvitationDelivery, delivery.id).state == "cancelled"
        return
    claimed = claim_visit_invitation(db_session, delivery.id)
    assert claimed is not None
    if ownership in {"after_claim", "reattested"}:
        link.patient_owner_generation_snapshot = None
        db_session.commit()
    if ownership == "reattested":
        link.patient_owner_generation_snapshot = test_patient.notification_owner_generation
        db_session.commit()
    sender = SimpleNamespace(_send_telegram_invitation=AsyncMock(return_value={"success": True}))
    sent = asyncio.run(send_claimed_visit_invitation(db_session, claimed, sender))
    assert sent is (ownership == "current")
    assert sender._send_telegram_invitation.await_count == (1 if ownership == "current" else 0)


@pytest.mark.parametrize("case,expected_status", [("unassigned", 403), ("benefit", 409), ("different_price", 409), ("audit_failure", 409)])
def test_doctor_all_free_denials_leave_no_new_visit_or_request(
    client, db_session, all_free_settings, monkeypatch, cardio_auth_headers,
    test_patient, test_doctor, test_service, case, expected_status,
):
    if case != "unassigned":
        _prior_context_visit(db_session, patient=test_patient, doctor=test_doctor)
    payload = _doctor_payload(db_session, test_patient, test_service)
    if case == "benefit":
        payload["discount_mode"] = "benefit"
    if case == "different_price":
        test_service.allow_doctor_price_override = True
        db_session.commit()
        payload["services"][0]["custom_price"] = "100.00"
    if case == "audit_failure":
        stage = AllFreeRequestService.stage_request

        def fail_after_staging(self, **kwargs):
            stage(self, **kwargs)
            raise AllFreeRequestError(409, "SYNTHETIC audit failure")

        monkeypatch.setattr(AllFreeRequestService, "stage_request", fail_after_staging)
    result = client.post(SCHEDULE, headers=cardio_auth_headers, json=payload)
    assert result.status_code == expected_status, result.text
    if case == "audit_failure":
        assert result.json()["detail"] == "SYNTHETIC audit failure"
    assert db_session.query(Visit).filter_by(patient_id=test_patient.id, status="pending_confirmation").count() == 0
    assert db_session.query(Encounter).filter_by(patient_id=test_patient.id).count() == 0
    assert db_session.query(AllFreeRequest).filter_by(patient_id=test_patient.id).count() == 0
    assert db_session.query(VisitInvitationDelivery).filter_by(patient_id=test_patient.id).count() == 0
