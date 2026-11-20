"""Manual repricing against a fully migrated disposable PostgreSQL instance."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.audit import AuditLog
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.models.visit_invitation_delivery import VisitInvitationApprovalRecovery
from app.services.price_override_approval import PriceOverrideApprovalService
from app.services.profile_contact_security import ProfileBearerContext
from tests.conftest import mint_access_token
from tests.integration.test_all_free_decision_concurrency_pg import decision_engines  # noqa: F401
from tests.integration.test_registrar_benefit_decision_pg import (
    OWNER,
    RUNTIME,
    benefit_client,  # noqa: F401
    configured_benefit_db,  # noqa: F401
)

pytestmark = pytest.mark.integration
APPROVAL_URL = "/api/v1/registrar/price-override/approve"


@pytest.fixture(scope="module")
def review_engines(decision_engines):
    admin, runtime = decision_engines
    with admin.begin() as conn:
        for table, privilege in (
            ("services", "SELECT"),
            ("services", "UPDATE (id)"),
            ("doctor_price_overrides", "SELECT"),
            ("doctor_price_overrides", "UPDATE (status, approved_by, approved_at, rejection_reason, updated_at)"),
            ("visits", "UPDATE (doctor_price_override)"),
            ("payment_invoices", "UPDATE (total_amount, updated_at)"),
            ("payment_invoice_visits", "UPDATE (visit_amount)"),
        ):
            conn.exec_driver_sql(f"GRANT {privilege} ON {table} TO {RUNTIME}")
            if conn.exec_driver_sql(
                f"SELECT relrowsecurity FROM pg_class WHERE oid='{table}'::regclass"
            ).scalar_one():
                command = privilege.split()[0]
                check = " WITH CHECK (true)" if command == "UPDATE" else ""
                conn.exec_driver_sql(
                    f"CREATE POLICY synthetic_price_review_{command.lower()} ON {table} "
                    f"FOR {command} TO {RUNTIME} USING (true){check}"
                )
        for name in ("visit_confirmation_generation_seq", "doctor_price_generation_seq"):
            conn.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {name} TO {RUNTIME}")
    path = Path(__file__).resolve().parents[2] / "scripts/provision_invitation_delivery_role.py"
    spec = spec_from_file_location("synthetic_price_recovery_provision", path)
    assert spec is not None and spec.loader is not None
    provisioner = module_from_spec(spec)
    spec.loader.exec_module(provisioner)
    provisioner.provision(admin, "public", RUNTIME)
    return admin, runtime


@pytest.fixture
def review_case(review_engines, benefit_client, monkeypatch):
    admin, runtime = review_engines
    for name, value in {
        "INVITATION_DB_SCHEMA": "public",
        "INVITATION_DB_SCHEMA_OWNER": OWNER,
        "INVITATION_DB_TABLE_OWNER": OWNER,
    }.items():
        monkeypatch.setattr(settings, name, value)

    def seed(*, waiting=False):
        suffix = uuid4().hex[:12]
        with Session(admin, expire_on_commit=False) as db:
            requester = User(username=f"synthetic-price-requester-{suffix}", hashed_password="!", role="Admin", is_active=True)
            reviewers = [
                User(username=f"synthetic-price-reviewer-{suffix}-{i}", hashed_password="!", role="Registrar", is_active=True)
                for i in range(2)
            ]
            patient = Patient(first_name="SYNTHETIC", last_name=f"PRICE-{suffix}", is_deleted=False)
            service = Service(code=f"SP-{suffix}", name="Synthetic price line", price=Decimal("30.00"), currency="UZS")
            db.add_all([requester, *reviewers, patient, service])
            db.flush()
            encounter = Encounter(patient_id=patient.id, provenance="new")
            db.add(encounter)
            db.flush()
            visit, sibling = [
                Visit(patient_id=patient.id, encounter_id=encounter.id, visit_date=date(2030, 1, 1),
                      status=status, source="desk")
                for status in ("pending_confirmation" if waiting else "open", "open")
            ]
            db.add_all([visit, sibling])
            db.flush()
            target = VisitService(visit_id=visit.id, service_id=service.id, name=service.name,
                                  qty=2, price=Decimal("30.00"), currency="UZS")
            other = VisitService(visit_id=sibling.id, service_id=service.id, name=service.name,
                                 qty=1, price=Decimal("30.00"), currency="UZS")
            invoice = PaymentInvoice(patient_id=patient.id, total_amount=Decimal("90.00"), currency="UZS")
            db.add_all([target, other, invoice])
            db.flush()
            db.add_all([
                PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visit.id, visit_amount=Decimal("60.00")),
                PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=sibling.id, visit_amount=Decimal("30.00")),
            ])
            if waiting:
                visit.confirmation_token = f"synthetic-price-confirmation-{suffix}"
                visit.confirmation_expires_at = datetime.now(UTC) + timedelta(hours=1)
                db.flush()
            db.refresh(visit)
            db.refresh(target)
            request = DoctorPriceOverride(
                visit_id=visit.id, service_id=service.id, target_scope="visit_service",
                target_visit_service_id=target.id, visit_context_epoch=visit.confirmation_context_epoch,
                price_context_generation=visit.price_context_generation, price_line_generation=target.price_line_generation,
                requester_type="admin", requester_user_id=requester.id, requester_user_id_snapshot=requester.id,
                requester_auth_epoch=requester.auth_epoch,
                original_price=Decimal("30.00"), visit_price_before=Decimal("30.00"),
                new_price=Decimal("27.15"), reason="Synthetic price review", status="pending",
            )
            db.add(request)
            db.commit()
            headers = [{"Authorization": f"Bearer {mint_access_token(actor)}"} for actor in reviewers]
            return visit.id, sibling.id, target.id, invoice.id, request.id, [actor.id for actor in reviewers], headers

    return admin, runtime, benefit_client, seed


def _decision(client, request_id, headers):
    return client.post(APPROVAL_URL, headers=headers, json={"override_id": request_id, "action": "approve"})


def test_concurrent_reviews_requote_one_invoice_and_keep_protected_recovery(review_case):
    admin, _, client, seed = review_case
    visit_id, sibling_id, line_id, invoice_id, request_id, reviewers, headers = seed(waiting=True)
    ready = Barrier(2, timeout=5)

    def approve(index):
        ready.wait()
        response = _decision(client, request_id, headers[index])
        return response.status_code, response.json(), reviewers[index]

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcome = sorted(pool.map(approve, (0, 1)), key=lambda item: item[0])
    assert [item[0] for item in outcome] == [200, 409], outcome
    with Session(admin) as db:
        row = db.get(DoctorPriceOverride, request_id)
        assert row.status == "approved" and row.approved_by == outcome[0][2]
        assert db.get(VisitService, line_id).price == Decimal("27.15")
        assert db.get(PaymentInvoice, invoice_id).total_amount == Decimal("84.30")
        amounts = dict(db.execute(
            select(PaymentInvoiceVisit.visit_id, PaymentInvoiceVisit.visit_amount).filter_by(invoice_id=invoice_id)
        ).all())
        assert amounts == {visit_id: Decimal("54.30"), sibling_id: Decimal("30.00")}
        audit = db.scalars(select(AuditLog).filter_by(action="price_override_approved", entity_id=request_id)).one()
        assert audit.actor_user_id == row.approved_by
        visit = db.get(Visit, visit_id)
        assert visit.confirmation_token is None and visit.confirmation_expires_at is None
        recovery = db.scalars(select(VisitInvitationApprovalRecovery).filter_by(override_id=request_id)).one()
        assert recovery.state == "pending" and recovery.context_epoch == visit.confirmation_context_epoch


def test_locked_and_committed_payment_each_prevents_requote(review_case):
    admin, runtime, client, seed = review_case
    visit_id, _, line_id, invoice_id, request_id, _, headers = seed()
    sqlstates = []

    def capture_lock_conflict(context):
        sqlstates.append(getattr(context.original_exception, "sqlstate", None))

    with Session(admin) as payer:
        payer.query(Visit.id).filter_by(id=visit_id).with_for_update().one()
        payer.add(Payment(visit_id=visit_id, amount=Decimal("60.00"), currency="UZS", method="cash", status="paid"))
        payer.flush()
        event.listen(runtime, "handle_error", capture_lock_conflict)
        try:
            reply = _decision(client, request_id, headers[0])
        finally:
            event.remove(runtime, "handle_error", capture_lock_conflict)
        assert reply.status_code == 409 and "55P03" in sqlstates, reply.text
        payer.commit()
    reply = _decision(client, request_id, headers[0])
    assert reply.status_code == 409 and "Платежи" in reply.json()["detail"], reply.text
    with Session(admin) as db:
        assert db.get(DoctorPriceOverride, request_id).status == "pending"
        assert db.get(VisitService, line_id).price == Decimal("30.00")
        assert db.get(PaymentInvoice, invoice_id).total_amount == Decimal("90.00")
        assert db.scalars(select(AuditLog).filter_by(action="price_override_approved", entity_id=request_id)).first() is None


def test_child_writer_lock_cannot_deadlock_approval(review_case):
    admin, _, client, seed = review_case
    _, _, line_id, invoice_id, request_id, _, headers = seed()
    with Session(admin) as writer:
        writer.query(VisitService.id).filter_by(id=line_id).with_for_update().one()
        reply = _decision(client, request_id, headers[0])
        assert reply.status_code == 409, reply.text
        writer.rollback()
    reply = _decision(client, request_id, headers[0])
    assert reply.status_code == 200, reply.text
    with Session(admin) as db:
        assert db.get(PaymentInvoice, invoice_id).total_amount == Decimal("84.30")


def test_audit_write_failure_rolls_back_price_invoice_and_invitation(review_case):
    admin, runtime, _, seed = review_case
    visit_id, _, line_id, invoice_id, request_id, reviewers, _ = seed(waiting=True)

    def fail_audit(_conn, _cursor, statement, parameters, _context, _many):
        if statement.startswith("INSERT INTO audit_logs") and parameters.get("action") == "price_override_approved":
            raise RuntimeError("Synthetic price audit write failure")

    event.listen(runtime, "before_cursor_execute", fail_audit)
    try:
        now = datetime.now(UTC)
        bearer = ProfileBearerContext(reviewers[0], 0, "synthetic-review-jti", int((now + timedelta(minutes=2)).timestamp()), None)
        with Session(runtime, autoflush=False) as db, pytest.raises(RuntimeError, match="Synthetic price audit write failure"):
            PriceOverrideApprovalService(db).process(
                override_id=request_id, action="approve", rejection_reason=None,
                approver_id=reviewers[0], bearer=bearer,
            )
    finally:
        event.remove(runtime, "before_cursor_execute", fail_audit)
    with Session(admin) as db:
        assert db.get(DoctorPriceOverride, request_id).status == "pending"
        assert db.get(VisitService, line_id).price == Decimal("30.00")
        assert db.get(PaymentInvoice, invoice_id).total_amount == Decimal("90.00")
        visit = db.get(Visit, visit_id)
        assert visit.confirmation_token is not None and visit.confirmation_expires_at is not None
        assert db.scalars(select(AuditLog).filter_by(action="price_override_approved", entity_id=request_id)).first() is None
        assert db.scalars(select(VisitInvitationApprovalRecovery).filter_by(override_id=request_id)).first() is None
