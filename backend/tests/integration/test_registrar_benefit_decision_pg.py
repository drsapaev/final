"""Registrar benefit approval on a disposable PostgreSQL migration chain."""

from __future__ import annotations

import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints.registrar_wizard._cart import (
    CartRequest,
    create_cart_appointments,
)
from app.core.config import settings
from app.db.capability_namespace import capability_schema_name
from app.main import app
from app.models.discount_benefits import (
    Benefit,
    BenefitApplication,
    BenefitType,
    PatientBenefit,
)
from app.models.encounter_benefit_ledger import (
    EncounterBenefitAllocation,
    EncounterBenefitApplication,
    EncounterBenefitVisitSnapshot,
)
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.user import User
from app.services.encounter_benefit_allocation import (
    BenefitLine,
    allocate_encounter_benefit,
)
from app.services.encounter_benefit_authority import (
    BenefitUsageEvidence,
    calculate_quota_usage,
)
from tests.conftest import mint_access_token

pytestmark = pytest.mark.integration
ROUTE = "/api/v1/discount-benefits/benefits/encounter/apply"
OWNER = "synthetic_repeat"
RUNTIME = "synthetic_doctor_runtime"
FINANCE = "synthetic_doctor_finance"
SUBJECT = "synthetic_doctor_subject"
DECISION = "synthetic_doctor_decision"
RECONCILIATION = "synthetic_doctor_reconciliation"
PRIVATE = capability_schema_name("public")


def _provision(name):
    path = Path(__file__).resolve().parents[3] / "scripts" / f"provision_{name}_role.py"
    spec = importlib.util.spec_from_file_location(f"benefit_decision_test_{name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.provision


@pytest.fixture(scope="module")
def configured_benefit_db():
    urls = [os.environ.get("BENEFIT_DECISION_TEST_" + key + "_URL") for key in ("ADMIN", "RUNTIME")]
    if not all(urls):
        pytest.skip("requires the expressly configured, fully migrated disposable PostgreSQL fixture")
    admin_url, runtime_url = map(make_url, urls)
    assert all(url.get_backend_name() == "postgresql" and url.host == "127.0.0.1"
               and (url.database or "").startswith("clinic_test") for url in (admin_url, runtime_url))
    assert runtime_url.database == admin_url.database and runtime_url.port == admin_url.port and runtime_url.username == RUNTIME
    admin = create_engine(admin_url, hide_parameters=True)
    runtime = create_engine(runtime_url, hide_parameters=True)
    try:
        with admin.begin() as conn:
            assert conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "0136_deposit_refund_evidence"
            assert conn.exec_driver_sql("SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname='public'").scalar_one() == OWNER
            can_execute = conn.execute(text("SELECT has_function_privilege(:role,:function,'EXECUTE')"), {
                "role": RUNTIME, "function": f"{PRIVATE}.approve_registrar_benefit(integer,integer,integer,bigint,text)",
            }).scalar_one()
            assert can_execute is False
            conn.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {RUNTIME}")
            for table in ("users", "token_blacklist", "patients"):
                conn.exec_driver_sql(f"GRANT SELECT ON {table} TO {RUNTIME}")
                if conn.execute(text("SELECT relrowsecurity FROM pg_class WHERE oid=to_regclass(:table)"), {"table": table}).scalar_one():
                    conn.exec_driver_sql(f"CREATE POLICY synthetic_benefit_select ON {table} FOR SELECT TO {RUNTIME} USING (true)")
            conn.exec_driver_sql(f"GRANT UPDATE (auth_epoch) ON users TO {RUNTIME}")
            if conn.exec_driver_sql("SELECT relrowsecurity FROM pg_class WHERE oid='users'::regclass").scalar_one():
                conn.exec_driver_sql(f"CREATE POLICY synthetic_benefit_actor ON users FOR UPDATE TO {RUNTIME} USING (true) WITH CHECK (false)")
        _provision("all_free_backend")(admin, "public", RUNTIME, expected_owner=OWNER, decision_role=DECISION)
        _provision("confirmation_subject")(admin, "public", SUBJECT, RUNTIME, expected_owner=OWNER)
        _provision("encounter_financial")(admin, schema="public", backend_role=RUNTIME, capability_role=FINANCE, expected_owner=OWNER)
        _provision("encounter_benefit")(admin, schema="public", backend_role=RUNTIME, capability_role=FINANCE,
                                        expected_owner=OWNER, enable_registrar_decisions=True)
        _provision("reconciliation_fence")(admin, schema="public", expected_owner=OWNER, backend_role=RUNTIME, capability_role=RECONCILIATION)

        @event.listens_for(runtime, "handle_error")
        def report_synthetic_failure(context):
            error = context.original_exception
            print("Synthetic benefit SQL diagnostic", getattr(error, "sqlstate", None),
                  getattr(getattr(error, "diag", None), "message_primary", None))

        yield admin, runtime
    finally:
        admin.dispose()
        runtime.dispose()


@pytest.fixture
def benefit_client(configured_benefit_db, monkeypatch):
    _, runtime = configured_benefit_db
    for name, value in {
        "TRUSTED_DB_SCHEMA": "public", "TRUSTED_DB_SCHEMA_OWNER": OWNER, "TRUSTED_DB_RUNTIME_ROLE": RUNTIME,
        "TRUSTED_DB_OWNER_MEMBERS": (), "TRUSTED_AUTH_TABLE_OWNER": OWNER, "TRUSTED_AUTH_OWNER_MEMBERS": (),
        "TRUSTED_AUTH_READ_ROLES": (), "TRUSTED_AUTH_WRITE_ROLES": (), "TRUSTED_AUTH_USERS_OWNER": OWNER,
        "TRUSTED_AUTH_USERS_OWNER_MEMBERS": (), "TRUSTED_AUTH_USERS_WRITE_ROLES": (), "TIMEZONE": "Asia/Tashkent",
    }.items():
        monkeypatch.setattr(settings, name, value)

    def session_override():
        with Session(runtime, autoflush=False) as db:
            assert db.execute(text("SELECT CURRENT_USER=:login AND CURRENT_USER=SESSION_USER"), {"login": RUNTIME}).scalar_one()
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db, session_override)
    with TestClient(app) as client:
        yield client


def _seed(admin, *, monthly_limit=None, legacy=False):
    suffix = uuid4().hex[:10]
    with Session(admin, expire_on_commit=False, autoflush=False) as db:
        reviewers = [User(username=f"synthetic-benefit-{suffix}-{index}", hashed_password="!", role=role, is_active=True)
                     for index, role in enumerate(("Admin", "Admin", "Doctor"))]
        patient = Patient(first_name="SYNTHETIC", last_name=f"BENEFIT-{suffix}", is_deleted=False)
        service = Service(code=f"SB-{suffix}", name="Synthetic benefit line", price=Decimal("0.09"), currency="UZS",
                          active=True, requires_doctor=False, is_consultation=False)
        policy = Benefit(name=f"SYNTHETIC-{suffix}", benefit_type=BenefitType.EMPLOYEE, discount_percentage=50,
                         requires_document=False, is_active=True, monthly_limit=monthly_limit)
        db.add_all([*reviewers, patient, service, policy])
        db.flush()
        assignments = [PatientBenefit(patient_id=patient.id, benefit_id=policy.id, is_active=True, verified=True) for _ in range(2)]
        db.add_all(assignments)
        db.flush()
        if legacy:
            db.add(BenefitApplication(patient_benefit_id=assignments[1].id, benefit_id=policy.id, original_amount=1,
                                      benefit_amount=0.1, final_amount=0.9, applied_at=datetime(2005, 1, 1)))
        db.commit()
        start = date.today() + timedelta(days=15)
        cart = CartRequest.model_validate({"patient_id": patient.id, "visits": [
            {"visit_date": start+timedelta(days=index), "department": "general",
             "services": [{"service_id": service.id, "quantity": quantity}]}
            for index, quantity in enumerate((2, 3))
        ]})
        invoices = [create_cart_appointments(cart, db=db, current_user=reviewers[0]) for _ in range(2)]
        return patient.id, [a.id for a in assignments], [u.id for u in reviewers], invoices, [
            {"Authorization": "Bearer " + mint_access_token(u)} for u in reviewers
        ]


def _approve(client, headers, invoice_id, assignment):
    return client.post(ROUTE, headers=headers, json={"invoice_id": invoice_id, "patient_benefit_id": assignment})


def test_group_approval_and_legacy_quota_are_exact(configured_benefit_db, benefit_client):
    admin, runtime = configured_benefit_db
    patient, assignments, users, bills, headers = _seed(admin, monthly_limit=0.30, legacy=True)
    first, next_bill = bills
    wrong_role = _approve(benefit_client, headers[2], first.invoice_id, assignments[0])
    assert wrong_role.status_code == 403, wrong_role.text
    result = _approve(benefit_client, headers[0], first.invoice_id, assignments[0])
    assert result.status_code == 200, result.text
    assert (result.json()["gross_total"], result.json()["benefit_total"], result.json()["total_amount"]) == ("0.45", "0.19", "0.26")
    assert _approve(benefit_client, headers[0], first.invoice_id, assignments[0]).status_code == 409
    exhausted = _approve(benefit_client, headers[1], next_bill.invoice_id, assignments[1])
    assert exhausted.status_code == 409, exhausted.text

    with Session(admin) as db:
        approval = db.query(EncounterBenefitApplication).filter_by(patient_id_snapshot=patient).one()
        assert (approval.approved_by_user_id_snapshot, approval.monthly_used_before) == (users[0], Decimal("0.11"))
        membership = db.query(EncounterBenefitVisitSnapshot).filter_by(application_id=approval.id).all()
        assert {visit.visit_id_snapshot for visit in membership} == set(first.visit_ids)
        allocations = db.query(EncounterBenefitAllocation).filter_by(application_id=approval.id).order_by(EncounterBenefitAllocation.visit_service_id_snapshot).all()
        expected = allocate_encounter_benefit(
            [BenefitLine(row.visit_service_id_snapshot, row.visit_id_snapshot, row.quantity, row.unit_price) for row in allocations],
            percent=Decimal("50"), remaining_monthly=Decimal("0.19"),
        )
        assert [row.benefit_amount for row in allocations] == [line.discount for line in expected.lines]
        links = db.query(PaymentInvoiceVisit).filter_by(invoice_id=first.invoice_id).all()
        assert {link.visit_id: link.visit_amount for link in links} == {line.visit_id: line.net for line in expected.lines}
        assert db.get(PaymentInvoice, next_bill.invoice_id).total_amount == Decimal("0.45")
    with runtime.connect() as conn:
        assert conn.exec_driver_sql("SELECT has_table_privilege(CURRENT_USER,'encounter_benefit_applications','INSERT,UPDATE,DELETE')").scalar_one() is False


@pytest.mark.parametrize("failed_write", ["RAISE EXCEPTION 'Synthetic invoice write failure';", "RETURN NULL;"])
def test_failed_invoice_write_rolls_back_approval(configured_benefit_db, benefit_client, failed_write):
    admin, _ = configured_benefit_db
    patient, assignments, _, bills, headers = _seed(admin)
    invoice = bills[0].invoice_id
    with admin.begin() as conn:
        conn.exec_driver_sql(f"""CREATE FUNCTION public.synthetic_requote_failure() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN {failed_write} END $$""")
        conn.exec_driver_sql(f"""CREATE TRIGGER trg_synthetic_requote_failure BEFORE UPDATE OF total_amount ON payment_invoices
            FOR EACH ROW WHEN (NEW.id={invoice}) EXECUTE FUNCTION public.synthetic_requote_failure()""")
    try:
        failure = _approve(benefit_client, headers[0], invoice, assignments[0])
        assert failure.status_code == 409, failure.text
    finally:
        with admin.begin() as conn:
            conn.exec_driver_sql("DROP TRIGGER trg_synthetic_requote_failure ON payment_invoices")
            conn.exec_driver_sql("DROP FUNCTION public.synthetic_requote_failure()")
    with Session(admin) as db:
        assert not db.query(EncounterBenefitApplication).filter_by(patient_id_snapshot=patient).count()
        assert db.get(PaymentInvoice, invoice).total_amount == Decimal("0.45")
        assert sorted(link.visit_amount for link in db.query(PaymentInvoiceVisit).filter_by(invoice_id=invoice)) == [Decimal("0.18"), Decimal("0.27")]
    done = _approve(benefit_client, headers[0], invoice, assignments[0])
    assert done.status_code == 200, done.text
    assert done.json()["benefit_total"] == "0.22"  # half-even once on the aggregate


def test_two_registrations_share_one_patient_benefit_quota(configured_benefit_db, benefit_client):
    admin, _ = configured_benefit_db
    patient, assignments, _, bills, headers = _seed(admin, monthly_limit=0.22)
    start = Barrier(2, timeout=8)

    def apply(index):
        start.wait()
        return _approve(benefit_client, headers[index], bills[index].invoice_id, assignments[index])

    with ThreadPoolExecutor(max_workers=2) as pool:
        one, two = pool.map(apply, range(2))
    assert sorted([one.status_code, two.status_code]) == [200, 409], (one.text, two.text)
    with Session(admin) as db:
        assert db.query(EncounterBenefitApplication).filter_by(patient_id_snapshot=patient).one().benefit_total == Decimal("0.22")
        assert sorted(db.get(PaymentInvoice, bill.invoice_id).total_amount for bill in bills) == [Decimal("0.23"), Decimal("0.45")]


def test_legacy_money_matches_the_python_reference(configured_benefit_db):
    admin, _ = configured_benefit_db
    with admin.connect() as conn:
        for value in (0.0, 0.10, 0.25, 0.02, 0.07, 5e-324, 1234.56):
            expected = calculate_quota_usage([BenefitUsageEvidence(value, legacy=True)],
                                             period_month=date(2099, 1, 1), period_timezone="Asia/Tashkent")
            actual = conn.execute(text(f"SELECT {PRIVATE}.legacy_benefit_cents(CAST(:value AS double precision))"), {"value": value}).scalar_one()
            assert actual == expected.monthly_used * 100


def test_wrong_patient_unmarked_invoice_and_paid_sibling_do_not_change_amount(configured_benefit_db, benefit_client):
    admin, _ = configured_benefit_db
    patient, assignments, _, bills, headers = _seed(admin)
    first = bills[0]
    foreign_assignments = _seed(admin)[1]
    with Session(admin, expire_on_commit=False) as db:
        old_invoice = PaymentInvoice(patient_id=patient, total_amount=Decimal("0.45"), currency="UZS")
        db.add(old_invoice)
        db.commit()
    for invoice_id, assignment in ((first.invoice_id, foreign_assignments[0]), (old_invoice.id, assignments[0])):
        result = _approve(benefit_client, headers[0], invoice_id, assignment)
        assert result.status_code == 409, result.text

    with Session(admin) as db:
        db.add(Payment(visit_id=first.visit_ids[-1], amount=Decimal("0.27"), currency="UZS", method="cash", status="paid"))
        db.commit()
    blocked = _approve(benefit_client, headers[0], first.invoice_id, assignments[0])
    assert blocked.status_code == 409, blocked.text
    with Session(admin) as db:
        assert not db.query(EncounterBenefitApplication).filter_by(patient_id_snapshot=patient).count()
        assert db.get(PaymentInvoice, first.invoice_id).total_amount == Decimal("0.45")


def test_runtime_with_unexpected_direct_ledger_write_is_rejected(configured_benefit_db, benefit_client):
    admin, _ = configured_benefit_db
    patient, assignments, _, bills, headers = _seed(admin)
    with admin.begin() as db:
        db.exec_driver_sql(f"GRANT UPDATE (percentage) ON encounter_benefit_applications TO {RUNTIME}")
    try:
        result = _approve(benefit_client, headers[0], bills[0].invoice_id, assignments[0])
        assert result.status_code == 503, result.text
    finally:
        with admin.begin() as db:
            db.exec_driver_sql(f"REVOKE UPDATE (percentage) ON encounter_benefit_applications FROM {RUNTIME}")
    with Session(admin) as db:
        assert not db.query(EncounterBenefitApplication).filter_by(patient_id_snapshot=patient).count()


def test_caller_amount_is_not_part_of_the_approval_contract(client, admin_auth_headers):
    response = client.post(ROUTE, headers=admin_auth_headers,
                           json={"invoice_id": 1, "patient_benefit_id": 1, "amount": "0.01"})
    assert response.status_code == 422, response.text
