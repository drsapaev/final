"""Payment interlocks for visits awaiting an All Free decision."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.endpoints.force_majeure import UseDepositRequest
from app.api.v1.endpoints.registrar_wizard import _invoice
from app.crud.clinic import clinic_today
from app.models.all_free_request import (
    AllFreeRequest,
    AllFreeRequestEvent,
    AllFreeRequestLine,
)
from app.models.audit import AuditLog
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.refund_deposit import DepositTransaction, PatientDeposit
from app.models.service import Service
from app.models.user import User
from app.models.user_profile import UserAuditLog
from app.models.visit import Visit, VisitService
from app.services.all_free_approval import ALL_FREE_DECISION_REQUIRED
from app.services.force_majeure_api_service import (
    ForceMajeureApiDomainError,
    ForceMajeureApiService,
)
from app.services.payment_init_service import PaymentInitDomainError, PaymentInitService
from app.services.payment_invariant_service import PaymentInvariantService
from app.services.registrar_edit_delta_service import RegistrarEditDeltaService
from tests.conftest import mint_access_token
from tests.integration.test_all_free_decision_concurrency_pg import (  # noqa: F401
    approval_case,
    benefit_client,
    configured_benefit_db,
    decision_engines,
)
from tests.integration.test_registrar_benefit_decision_pg import RUNTIME

pytestmark = pytest.mark.integration

AMOUNT = Decimal("50000.00")


def _add_charge(db, visit, service):
    db.add(
        VisitService(
            visit_id=visit.id,
            service_id=service.id,
            name="Synthetic consultation",
            qty=1,
            price=AMOUNT,
            currency="UZS",
        )
    )


@pytest.mark.parametrize("approval_status", ["pending", "none"])
def test_cash_and_group_receipts_wait_for_decision(
    db_session, test_visit, test_service, admin_user, approval_status
):
    test_visit.discount_mode = "all_free"
    test_visit.approval_status = approval_status
    _add_charge(db_session, test_visit, test_service)
    db_session.commit()
    payment = PaymentInvariantService(db_session)

    with pytest.raises(HTTPException) as direct_error:
        payment.create_payment_for_visit(
            test_visit.id, AMOUNT, "cash", None, admin_user
        )
    with pytest.raises(HTTPException) as group_error:
        payment.receive_grouped_payment(
            visit_ids=[test_visit.id],
            amount=AMOUNT,
            method="cash",
            current_user=admin_user,
        )

    for error in (direct_error, group_error):
        assert error.value.status_code == 409
        assert error.value.detail == ALL_FREE_DECISION_REQUIRED
    assert db_session.query(Payment).filter_by(visit_id=test_visit.id).count() == 0


def test_provider_initialization_waits_without_creating_a_payment(
    db_session, test_visit, admin_user
):
    test_visit.discount_mode = "all_free"
    test_visit.approval_status = "pending"
    db_session.commit()
    manager = Mock()
    manager.get_providers_for_currency.return_value = ["click"]

    with pytest.raises(PaymentInitDomainError) as error:
        PaymentInitService(db_session, manager).init_payment(
            request=SimpleNamespace(state=None),
            current_user_id=admin_user.id,
            visit_id=test_visit.id,
            provider="click",
            amount=float(AMOUNT),
            currency="UZS",
            description=None,
            return_url=None,
            cancel_url=None,
        )

    assert error.value.status_code == 409
    assert error.value.detail == ALL_FREE_DECISION_REQUIRED
    manager.create_payment.assert_not_called()
    assert db_session.query(Payment).filter_by(visit_id=test_visit.id).count() == 0


def test_invoice_initialization_checks_pending_zero_price_member(
    db_session, test_visit, test_service, admin_user, monkeypatch
):
    pending_visit = Visit(
        patient_id=test_visit.patient_id,
        visit_date=test_visit.visit_date,
        status="pending_confirmation",
        discount_mode="all_free",
        approval_status="pending",
        confirmation_context_epoch=1,
    )
    invoice = PaymentInvoice(
        patient_id=test_visit.patient_id,
        total_amount=AMOUNT,
        status="pending",
        currency="UZS",
    )
    db_session.add_all([pending_visit, invoice])
    _add_charge(db_session, test_visit, test_service)
    db_session.flush()
    db_session.add_all(
        [
            PaymentInvoiceVisit(
                invoice_id=invoice.id, visit_id=test_visit.id, visit_amount=AMOUNT
            ),
            PaymentInvoiceVisit(
                invoice_id=invoice.id, visit_id=pending_visit.id, visit_amount=0
            ),
        ]
    )
    db_session.commit()
    factory = Mock()
    monkeypatch.setattr(_invoice, "get_payment_manager", factory)

    with pytest.raises(HTTPException) as error:
        _invoice.init_invoice_payment(
            _invoice.InvoicePaymentRequest(invoice_id=invoice.id, provider="click"),
            db_session,
            admin_user,
        )

    assert error.value.status_code == 409
    assert error.value.detail == ALL_FREE_DECISION_REQUIRED
    assert db_session.get(PaymentInvoice, invoice.id).status == "pending"
    factory.assert_not_called()


def test_deposit_debit_preserves_balance_until_decision(
    db_session, test_visit, admin_user
):
    test_visit.discount_mode = "all_free"
    test_visit.approval_status = "pending"
    deposit = PatientDeposit(
        patient_id=test_visit.patient_id, currency="UZS", balance=AMOUNT, is_active=True
    )
    db_session.add(deposit)
    db_session.commit()

    with pytest.raises(ForceMajeureApiDomainError) as error:
        ForceMajeureApiService(db_session).use_deposit_for_payment(
            request=UseDepositRequest(
                patient_id=test_visit.patient_id, visit_id=test_visit.id, amount=AMOUNT,
                client_request_id=uuid4(),
            ),
            current_user_id=admin_user.id,
        )

    assert error.value.status_code == 409
    assert error.value.detail == ALL_FREE_DECISION_REQUIRED
    assert db_session.get(PatientDeposit, deposit.id).balance == AMOUNT
    assert (
        db_session.query(DepositTransaction).filter_by(deposit_id=deposit.id).count()
        == 0
    )


def test_rejected_visit_can_pay_persisted_regular_price(
    db_session, test_visit, test_service, admin_user
):
    test_visit.discount_mode = "all_free"
    test_visit.approval_status = "rejected"
    _add_charge(db_session, test_visit, test_service)
    db_session.commit()

    payment = PaymentInvariantService(db_session).create_payment_for_visit(
        test_visit.id, AMOUNT, "cash", None, admin_user, allow_overpayment=False
    )

    assert payment.amount == AMOUNT
    assert payment.status == "paid"


def test_prior_invoice_settlement_can_record_already_received_funds(
    db_session, test_visit, test_service, admin_user
):
    test_visit.discount_mode = "all_free"
    test_visit.approval_status = "pending"
    _add_charge(db_session, test_visit, test_service)
    invoice = PaymentInvoice(
        patient_id=test_visit.patient_id,
        total_amount=AMOUNT,
        status="processing",
        currency="UZS",
        provider="click",
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(
        PaymentInvoiceVisit(
            invoice_id=invoice.id, visit_id=test_visit.id, visit_amount=AMOUNT
        )
    )
    db_session.commit()

    payment = PaymentInvariantService(db_session).create_payment_for_visit(
        test_visit.id,
        AMOUNT,
        "click",
        None,
        admin_user,
        provider="click",
        allow_overpayment=False,
        settling_invoice_id=invoice.id,
    )

    assert payment.amount == AMOUNT
    assert payment.status == "paid"


def test_payment_rereads_committed_approval_under_postgres_lock(approval_case):
    owner, runtime, _client, visit_id, *_ = approval_case
    with Session(owner) as db:
        db.get(Visit, visit_id).approval_status = "approved"
        db.commit()

    with Session(runtime) as payment_db:
        cached_visit = payment_db.get(Visit, visit_id)
        assert cached_visit.approval_status == "approved"
        with Session(owner) as request_db:
            request_db.get(Visit, visit_id).approval_status = "pending"
            request_db.commit()

        with pytest.raises(HTTPException) as error:
            PaymentInvariantService(payment_db).check_payment_allowed(visit_id, AMOUNT)

        assert error.value.status_code == 409
        assert error.value.detail == ALL_FREE_DECISION_REQUIRED
        assert cached_visit.approval_status == "pending"


@pytest.fixture(scope="module")
def qr_financial_engines(decision_engines):
    owner, runtime = decision_engines
    with owner.begin() as connection:
        grants = {
            "daily_queues": ("SELECT",),
            "doctors": ("SELECT",),
            "encounters": ("INSERT (patient_id, provenance, legacy_visit_id, generation)",),
            "services": ("SELECT", "UPDATE (price)"),
            "queue_entries": ("SELECT", "UPDATE"),
            "user_audit_logs": ("INSERT", "SELECT (id, created_at)"),
            "visits": (
                "UPDATE (status, encounter_id, discount_mode, approval_status, department, doctor_id, updated_at, "
                "confirmation_context_epoch, confirmation_token, confirmation_expires_at, "
                "reminder_sent_at, reminder_generation, repeat_evidence_generation, repeat_proof_generation, "
                "repeat_proof_consultation, repeat_proof_doctor_user_id)",
            ),
            "visit_services": ("INSERT", "DELETE"),
        }
        for table, privileges in grants.items():
            connection.exec_driver_sql(f"GRANT {', '.join(privileges)} ON {table} TO {RUNTIME}")
            if connection.exec_driver_sql(
                f"SELECT relrowsecurity FROM pg_class WHERE oid='{table}'::regclass"
            ).scalar_one():
                for privilege in privileges:
                    command = privilege.split()[0]
                    clause = {
                        "SELECT": "USING (true)",
                        "UPDATE": "USING (true) WITH CHECK (true)",
                        "INSERT": "WITH CHECK (true)",
                        "DELETE": "USING (true)",
                    }[command]
                    connection.exec_driver_sql(
                        f"CREATE POLICY synthetic_qr_{command.lower()} ON {table} FOR {command} TO {RUNTIME} {clause}"
                    )
        connection.exec_driver_sql(
            "GRANT USAGE ON SEQUENCE encounters_id_seq, visit_services_id_seq, visit_confirmation_generation_seq, "
            f"repeat_evidence_generation_seq, user_audit_logs_id_seq TO {RUNTIME}"
        )
    return owner, runtime


def _seed_qr_all_free(owner):
    suffix = uuid4().hex[:12]
    with Session(owner, expire_on_commit=False) as db:
        registrar = User(username=f"synthetic-qr-{suffix}", hashed_password="!", role="Registrar", is_active=True)
        physician = User(
            username=f"synthetic-qr-doctor-{suffix}", hashed_password="!", role="Doctor",
            full_name="SYNTHETIC QR Doctor", is_active=True,
        )
        patient = Patient(first_name="SYNTHETIC", last_name=f"QR-{suffix}")
        service = Service(
            code=f"SQR-{suffix}", name="SYNTHETIC-QR service", price=AMOUNT, currency="UZS",
            active=True, requires_doctor=False, is_consultation=False,
        )
        db.add_all([registrar, physician, patient, service])
        db.flush()
        doctor = Doctor(user_id=physician.id, specialty="general", active=True)
        db.add(doctor)
        db.flush()
        day = clinic_today(db)
        queue = DailyQueue(day=day, specialist_id=doctor.id, queue_tag="general", active=True)
        visit = Visit(
            patient_id=patient.id, doctor_id=doctor.id, visit_date=day, status="open",
            source="online", department="general", discount_mode="none", approval_status="approved",
        )
        db.add_all([queue, visit])
        db.flush()
        line = VisitService(visit_id=visit.id, service_id=service.id, name=service.name, qty=1, price=AMOUNT, currency="UZS")
        queue_time = datetime.now(UTC)
        entry = OnlineQueueEntry(
            queue_id=queue.id, number=1, patient_id=patient.id, visit_id=visit.id, source="online",
            status="waiting", queue_time=queue_time, total_amount=int(AMOUNT), discount_mode="none",
            services=json.dumps([{
                "service_id": service.id, "price": int(AMOUNT), "quantity": 1, "queue_time": queue_time.isoformat(),
            }]),
        )
        db.add_all([line, entry])
        db.commit()
        headers = {"Authorization": f"Bearer {mint_access_token(registrar)}"}
        return visit.id, line.id, entry.id, service.id, headers


@pytest.mark.parametrize("case", ("posted", "competing", "hidden", "unbilled"))
def test_qr_all_free_financial_fence_with_restricted_postgres_login(
    qr_financial_engines, benefit_client, case,
):
    owner, runtime = qr_financial_engines
    visit_id, line_id, entry_id, service_id, headers = _seed_qr_all_free(owner)

    def request_repricing():
        return benefit_client.put(
            f"/api/v1/queue/online-entry/{entry_id}/full-update", headers=headers,
            json={"patient_data": {}, "visit_type": "paid", "discount_mode": "none", "all_free": True,
                  "services": [{"service_id": service_id, "quantity": 2}]},
        )

    if case != "unbilled":
        with Session(owner) as payment_db:
            payment = Payment(
                visit_id=visit_id, amount=AMOUNT, currency="UZS", status="paid", method="cash",
                paid_at=datetime.now(UTC), receipt_no="SYNTHETIC-Posted QR receipt",
            )
            payment_db.add(payment)
            payment_db.flush()
            payment_id = payment.id
            if case == "competing":
                locked = request_repricing()
                assert locked.status_code == 409, locked.text
                assert "занято" in locked.json()["detail"]
            payment_db.commit()

    if case == "hidden":
        with owner.begin() as connection:
            connection.exec_driver_sql(
                f"CREATE POLICY synthetic_qr_hide_payment ON payments AS RESTRICTIVE FOR SELECT TO {RUNTIME} USING (false)"
            )
        try:
            with Session(runtime) as db:
                assert db.scalar(select(Payment.id).where(Payment.id == payment_id)) is None
            blocked = request_repricing()
            assert blocked.status_code == 409, blocked.text
            assert "недоступна" in blocked.json()["detail"]
        finally:
            with owner.begin() as connection:
                connection.exec_driver_sql("DROP POLICY synthetic_qr_hide_payment ON payments")

    response = request_repricing()
    with Session(owner) as db:
        visit = db.get(Visit, visit_id)
        entry = db.get(OnlineQueueEntry, entry_id)
        services = db.scalars(select(VisitService).where(VisitService.visit_id == visit_id)).all()
        if case == "unbilled":
            assert response.status_code == 200, response.text
            assert visit.approval_status == "pending"
            assert entry.visit_id == visit_id
            assert [(line.qty, line.price, line.currency) for line in services] == [(2, AMOUNT, "UZS")]
            approval = db.scalars(select(AllFreeRequest).filter_by(visit_id=visit_id)).one()
            assert (approval.status, approval.baseline_total, approval.encounter_id) == (
                "pending", 2 * AMOUNT, entry.encounter_id,
            )
        else:
            assert response.status_code == 409, response.text
            assert "Обратитесь в кассу" in response.json()["detail"]
            assert (visit.discount_mode, visit.approval_status) == ("none", "approved")
            assert (entry.visit_id, entry.total_amount, entry.discount_mode) == (visit_id, int(AMOUNT), "none")
            assert [(line.id, line.qty, line.price) for line in services] == [(line_id, 1, AMOUNT)]
            posted = db.get(Payment, payment_id)
            assert (posted.status, posted.amount, posted.currency) == ("paid", AMOUNT, "UZS")


@pytest.mark.parametrize("lock_target", ("visit", "ticket"))
def test_native_regular_qr_edit_waits_for_an_available_link(
    qr_financial_engines, benefit_client, lock_target,
):
    owner, _ = qr_financial_engines
    visit_id, line_id, entry_id, service_id, headers = _seed_qr_all_free(owner)
    command = {
        "patient_data": {}, "visit_type": "paid", "discount_mode": "none",
        "services": [{"service_id": service_id, "quantity": 1}],
    }
    route = f"/api/v1/queue/online-entry/{entry_id}/full-update"
    model, row_id = (Visit, visit_id) if lock_target == "visit" else (OnlineQueueEntry, entry_id)
    with Session(owner) as blocker:
        assert blocker.get(model, row_id, with_for_update=True) is not None
        blocked = benefit_client.put(route, headers=headers, json=command)
        assert blocked.status_code == 409, blocked.text
        assert "занято" in blocked.json()["detail"]

    saved = benefit_client.put(route, headers=headers, json=command)
    assert saved.status_code == 200, saved.text
    assert saved.json()["entry"]["total_amount"] == AMOUNT
    with Session(owner) as db:
        entry = db.get(OnlineQueueEntry, entry_id)
        line = db.get(VisitService, line_id)
        assert (entry.visit_id, entry.total_amount) == (visit_id, AMOUNT)
        assert (line.visit_id, line.qty, line.price) == (visit_id, 1, AMOUNT)
        assert db.scalar(select(AllFreeRequest.id).where(AllFreeRequest.visit_id == visit_id)) is None


def test_native_qr_cancellation_audits_only_the_unlinked_ticket(qr_financial_engines, benefit_client):
    owner, _ = qr_financial_engines
    visit_id, line_id, linked_id, service_id, headers = _seed_qr_all_free(owner)
    with Session(owner, expire_on_commit=False) as db:
        linked = db.get(OnlineQueueEntry, linked_id)
        unlinked = OnlineQueueEntry(
            queue_id=linked.queue_id, number=2, patient_id=linked.patient_id,
            source="online", status="waiting", queue_time=datetime.now(UTC),
            total_amount=int(AMOUNT), services=linked.services,
        )
        db.add(unlinked)
        db.commit()
        unlinked_id = unlinked.id

    request = {"service_id": service_id, "cancel_reason": "SYNTHETIC review"}
    linked_response = benefit_client.post(
        f"/api/v1/queue/online-entry/{linked_id}/cancel-service", headers=headers, json=request,
    )
    assert linked_response.status_code == 409, linked_response.text
    route = f"/api/v1/queue/online-entry/{unlinked_id}/cancel-service"
    canceled = benefit_client.post(route, headers=headers, json=request)
    assert canceled.status_code == 200, canceled.text
    assert canceled.json()["new_total_amount"] == 0
    assert benefit_client.post(route, headers=headers, json=request).status_code == 404

    with Session(owner) as db:
        assert db.get(OnlineQueueEntry, unlinked_id).total_amount == 0
        assert db.get(OnlineQueueEntry, linked_id).total_amount == AMOUNT
        assert db.get(VisitService, line_id).price == AMOUNT
        audit = db.scalars(select(UserAuditLog).where(
            UserAuditLog.action == "CANCEL_SERVICE",
            UserAuditLog.resource_type == "online_queue_entries",
            UserAuditLog.resource_id.in_([unlinked_id, linked_id]),
        )).one()
        assert audit.resource_id == unlinked_id
        assert (audit.old_values["total_amount"], audit.new_values["total_amount"]) == (AMOUNT, 0)


@pytest.mark.parametrize(("action", "final_status", "final_price"), (
    ("approve", "approved", Decimal("0.00")),
    ("reject", "rejected", AMOUNT),
))
def test_native_qr_all_free_decision_and_audit(
    qr_financial_engines, benefit_client, action, final_status, final_price,
):
    owner, runtime = qr_financial_engines
    visit_id, _, entry_id, service_id, registrar_headers = _seed_qr_all_free(owner)
    command = {
        "patient_data": {}, "visit_type": "paid", "discount_mode": "none", "all_free": True,
        "services": [{"service_id": service_id, "quantity": 2}],
    }
    route = f"/api/v1/queue/online-entry/{entry_id}/full-update"
    staged = benefit_client.put(route, headers=registrar_headers, json=command)
    assert staged.status_code == 200, staged.text
    assert Decimal(str(staged.json()["entry"]["total_amount"])) == 2 * AMOUNT

    repeated = benefit_client.put(route, headers=registrar_headers, json=command)
    assert repeated.status_code == 409, repeated.text
    regular_command = {**command, "all_free": False, "services": [{"service_id": service_id, "quantity": 1}]}
    regular_pending = benefit_client.put(route, headers=registrar_headers, json=regular_command)
    assert regular_pending.status_code == 409, regular_pending.text
    assert "корзину регистратуры" in regular_pending.json()["detail"]

    with Session(runtime) as db:
        entry = db.get(OnlineQueueEntry, entry_id)
        with pytest.raises(HTTPException) as pending_edit:
            RegistrarEditDeltaService(db).require_editable_visit_prices(entry)
        assert pending_edit.value.status_code == 409
        with pytest.raises(HTTPException) as pending_payment:
            PaymentInvariantService(db).check_payment_allowed(visit_id, 2 * AMOUNT)
        assert pending_payment.value.status_code == 409
        assert pending_payment.value.detail == ALL_FREE_DECISION_REQUIRED

    with Session(owner, expire_on_commit=False) as db:
        request = db.scalars(select(AllFreeRequest).filter_by(visit_id=visit_id)).one()
        request_id = request.id
        line = db.scalars(select(AllFreeRequestLine).filter_by(request_id=request_id)).one()
        assert (request.status, request.baseline_total) == ("pending", 2 * AMOUNT)
        assert (line.quantity, line.unit_price, line.gross_amount, line.currency) == (2, AMOUNT, 2 * AMOUNT, "UZS")
        admin = User(
            username=f"synthetic-qr-approver-{uuid4().hex[:12]}", hashed_password="!", role="Admin", is_active=True,
        )
        db.add(admin)
        db.get(Service, service_id).price = 3 * AMOUNT
        db.commit()
        admin_headers = {"Authorization": f"Bearer {mint_access_token(admin)}"}

    decision = benefit_client.post(
        "/api/v1/admin/all-free-approve", headers=admin_headers,
        json={"visit_id": visit_id, "action": action, "rejection_reason": "SYNTHETIC review"},
    )
    assert decision.status_code == 200, decision.text
    regular_decided = benefit_client.put(route, headers=registrar_headers, json=regular_command)
    assert regular_decided.status_code == 409, regular_decided.text
    assert regular_decided.json() == regular_pending.json()
    with Session(owner) as db:
        visit = db.get(Visit, visit_id)
        entry = db.get(OnlineQueueEntry, entry_id)
        line = db.scalars(select(VisitService).filter_by(visit_id=visit_id)).one()
        request = db.get(AllFreeRequest, request_id)
        assert (visit.status, visit.approval_status, visit.confirmed_at) == ("pending_confirmation", final_status, None)
        assert (line.qty, line.price, line.currency) == (2, final_price, "UZS")
        assert (entry.visit_id, entry.discount_mode, entry.total_amount) == (visit_id, "all_free", 2 * AMOUNT)
        assert (request.status, request.baseline_total, request.decided_by_user_id) == (final_status, 2 * AMOUNT, admin.id)
        events = db.scalars(
            select(AllFreeRequestEvent.event_type).filter_by(request_id=request_id).order_by(AllFreeRequestEvent.id)
        ).all()
        audit = db.scalars(
            select(AuditLog.action).filter_by(entity_type="all_free_request", entity_id=request_id).order_by(AuditLog.id)
        ).all()
        assert events == ["requested", final_status]
        assert audit == ["all_free_requested", "all_free_decided"]

    with Session(runtime) as db:
        entry = db.get(OnlineQueueEntry, entry_id)
        if action == "approve":
            with pytest.raises(HTTPException) as approved_edit:
                RegistrarEditDeltaService(db).require_editable_visit_prices(entry)
            assert approved_edit.value.status_code == 409
        else:
            RegistrarEditDeltaService(db).require_editable_visit_prices(entry)
        payable = 2 * final_price
        assert PaymentInvariantService(db).check_payment_allowed(
            visit_id, payable, allow_overpayment=False,
        ) == (payable, Decimal("0.00"), payable)
