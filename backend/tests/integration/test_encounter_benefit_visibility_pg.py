"""Real nonowner quote under FORCE RLS and actual epoch/fence triggers."""
import importlib.util
import os
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base_class import Base
from app.db.capability_namespace import capability_schema_name
from app.models.all_free_request import AllFreeRequest
from app.models.discount_benefits import Benefit, BenefitType, PatientBenefit
from app.models.encounter import Encounter
from app.models.encounter_benefit_ledger import (
    EncounterBenefitAllocation,
    EncounterBenefitApplication,
    EncounterBenefitVisitSnapshot,
)
from app.models.patient import Patient
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.encounter_benefit_net import BenefitQuoteError, benefit_visit_quote
from app.services.encounter_financial_fence import (
    FinancialFenceError,
    lock_financial_group,
    requote_draft_invoice_prices,
)
from app.services.notifications_pkg._formatting import FormattingMixin
from app.services.payment_invariant_service import PaymentInvariantService
from tests.integration.test_encounter_financial_role_pg import _provision_module
from tests.integration.test_encounter_migration_pg import _migration


@pytest.mark.integration
def test_force_rls_nonowner_exact_benefit_and_stale_sibling(monkeypatch):
    from app.core.config import settings

    url = make_url(os.environ.get("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable PostgreSQL clinic_test database")
    suffix = uuid.uuid4().hex
    schema, backend, cap, recon_cap = "benefit_" + suffix, "benefitback_" + suffix, "benefitcap_" + suffix, "benefitrecon_" + suffix
    password = "synthetic" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
        owner = conn.execute(text("SELECT CURRENT_USER")).scalar_one()
        bootstrap = _migration("0112_doctor_price_context.py")
        bootstrap.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema}))
        bootstrap._bootstrap_capability_namespace(schema)
        conn.execute(text(f'CREATE ROLE "{backend}" LOGIN PASSWORD \'{password}\''))
        conn.execute(text(f'CREATE ROLE "{cap}" NOLOGIN'))
        conn.execute(text(f'CREATE ROLE "{recon_cap}" NOLOGIN'))
    monkeypatch.setattr(settings, "TRUSTED_DB_SCHEMA", schema)
    monkeypatch.setattr(settings, "TRUSTED_DB_SCHEMA_OWNER", owner)
    monkeypatch.setattr(settings, "TRUSTED_DB_RUNTIME_ROLE", backend)
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"})
    runtime = None
    try:
        import app.db.base  # noqa: F401
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE encounter_benefit_visit_snapshots"))
            conn.execute(text("DROP INDEX uq_enc_benefit_app_identity"))
            conn.execute(text("ALTER TABLE visits DROP COLUMN confirmation_context_epoch"))
            for filename in ("0102_visit_confirmation_context.py", "0115_confirmation_trigger_path.py",
                             "0118_encounter_financial_fence.py", "0123_reconciliation_fence.py", "0125_benefit_visibility.py"):
                migration = _migration(filename)
                migration.op = Operations(MigrationContext.configure(conn))
                migration.upgrade()
        with Session(engine) as db:
            user = User(username="synthetic-benefit-admin", hashed_password="!", role="Admin", is_active=True)
            patient = Patient(first_name="SYNTHETIC", last_name="Benefit")
            service = Service(code="SYNTHETIC-BENEFIT", name="SYNTHETIC", price=Decimal("0.07"), active=True)
            benefit = Benefit(name="SYNTHETIC", benefit_type=BenefitType.EMPLOYEE, discount_percentage=50, is_active=True)
            db.add_all([user, patient, service, benefit])
            db.flush()
            assignment = PatientBenefit(patient_id=patient.id, benefit_id=benefit.id, is_active=True, verified=True)
            encounter = Encounter(patient_id=patient.id, provenance="new")
            db.add_all([assignment, encounter])
            db.flush()
            first = Visit(patient_id=patient.id, encounter_id=encounter.id, status="pending_confirmation", visit_date=date(2099,1,1))
            second = Visit(patient_id=patient.id, encounter_id=encounter.id, status="pending_confirmation", visit_date=date(2099,1,1))
            db.add_all([first, second])
            db.flush()
            line = VisitService(visit_id=first.id, service_id=service.id, name="SYNTHETIC", qty=3, price=Decimal("0.07"), currency="UZS")
            other_line = VisitService(visit_id=second.id, service_id=service.id, name="SYNTHETIC", qty=1, price=Decimal("0.05"), currency="UZS")
            db.add_all([line, other_line])
            db.flush()
            db.refresh(first)
            db.refresh(second)
            db.refresh(encounter)
            app = EncounterBenefitApplication(encounter_id=encounter.id, patient_id=patient.id, patient_id_snapshot=patient.id,
                patient_benefit_id=assignment.id, patient_benefit_id_snapshot=assignment.id, benefit_id=benefit.id,
                benefit_id_snapshot=benefit.id, approved_by_user_id=user.id, approved_by_user_id_snapshot=user.id,
                approved_by_role_snapshot="Admin", period_timezone="Asia/Tashkent", period_month=date(2099,1,1), period_year=2099,
                encounter_generation=encounter.generation, percentage=Decimal("50.0000"), monthly_used_before=Decimal("0.00"),
                yearly_used_before=Decimal("0.00"), gross_total=Decimal("0.21"), benefit_total=Decimal("0.10"), net_total=Decimal("0.11"))
            db.add(app)
            db.flush()
            for visit in (first, second):
                db.add(EncounterBenefitVisitSnapshot(application_id=app.id, visit_id=visit.id, encounter_id=encounter.id,
                    patient_id=patient.id, visit_id_snapshot=visit.id, visit_context_epoch=visit.confirmation_context_epoch))
            db.add(EncounterBenefitAllocation(application_id=app.id, visit_id=first.id, visit_id_snapshot=first.id,
                visit_service_id=line.id, visit_service_id_snapshot=line.id, service_id_snapshot=service.id,
                visit_context_epoch=first.confirmation_context_epoch, quantity=3, unit_price=Decimal("0.07"),
                gross_amount=Decimal("0.21"), benefit_amount=Decimal("0.10"), net_amount=Decimal("0.11")))
            other_encounter = Encounter(patient_id=patient.id, provenance="new")
            db.add(other_encounter)
            db.flush()
            plain = Visit(patient_id=patient.id, encounter_id=other_encounter.id, status="pending_confirmation", visit_date=date(2099, 1, 1))
            db.add(plain)
            db.flush()
            plain_line = VisitService(visit_id=plain.id, service_id=service.id, name="SYNTHETIC", qty=1, price=Decimal("0.07"), currency="UZS")
            db.add(plain_line)
            invoice = PaymentInvoice(patient_id=patient.id, total_amount=Decimal("0.07"), status="pending", currency="UZS")
            db.add(invoice)
            db.flush()
            db.add(PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=plain.id, visit_amount=Decimal("0.07")))
            db.commit()
            first_id, second_id, other_id, plain_id, plain_line_id = first.id, second.id, other_line.id, plain.id, plain_line.id
            patient_id, plain_encounter_id, user_id, plain_epoch = patient.id, other_encounter.id, user.id, plain.confirmation_context_epoch
        finance_provision = _provision_module()
        with engine.begin() as conn:
            for table in finance_provision.TABLES:
                conn.execute(text(f'ALTER TABLE "{schema}"."{table}" ENABLE ROW LEVEL SECURITY'))
                conn.execute(text(f'ALTER TABLE "{schema}"."{table}" FORCE ROW LEVEL SECURITY'))
            for table in ("encounter_benefit_applications", "encounter_benefit_allocations", "encounter_benefit_events", "encounter_benefit_visit_snapshots"):
                conn.execute(text(f'ALTER TABLE "{schema}"."{table}" ENABLE ROW LEVEL SECURITY'))
                conn.execute(text(f'ALTER TABLE "{schema}"."{table}" FORCE ROW LEVEL SECURITY'))
            conn.execute(text(f'ALTER TABLE "{schema}".click_callback_receipts ENABLE ROW LEVEL SECURITY'))
            conn.execute(text(f'ALTER TABLE "{schema}".click_callback_receipts FORCE ROW LEVEL SECURITY'))
            conn.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{backend}"'))
            conn.execute(text(f'GRANT SELECT ON "{schema}".all_free_requests TO "{backend}"'))
            conn.execute(text(f'CREATE POLICY allfree_backend_select ON "{schema}".all_free_requests FOR SELECT TO "{backend}" USING (true)'))
        finance_provision.provision(engine, schema=schema, backend_role=backend, capability_role=cap, expected_owner=owner)
        path = Path(__file__).resolve().parents[3] / "scripts/provision_encounter_benefit_role.py"
        spec = importlib.util.spec_from_file_location("benefit_role_provision", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.provision(engine, schema=schema, backend_role=backend, capability_role=cap, expected_owner=owner)
        module.provision(engine, schema=schema, backend_role=backend, capability_role=cap, expected_owner=owner)
        path = Path(__file__).resolve().parents[3] / "scripts/provision_reconciliation_fence_role.py"
        spec = importlib.util.spec_from_file_location("benefit_reconciliation_provision", path)
        recon = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(recon)
        recon.provision(engine, schema=schema, backend_role=backend, capability_role=recon_cap, expected_owner=owner)
        with engine.begin() as conn:
            # Ordinary payment rights are provisioned by the application,
            # separately from the narrow visibility capability under test.
            conn.execute(text(f'GRANT SELECT, INSERT ON "{schema}".payments TO "{backend}"'))
            conn.execute(text(f'GRANT USAGE ON SEQUENCE "{schema}".payments_id_seq TO "{backend}"'))
            conn.execute(text(f'GRANT UPDATE (id) ON "{schema}".visits TO "{backend}"'))
            conn.execute(text(f'CREATE POLICY synthetic_payment_insert ON "{schema}".payments FOR INSERT TO "{backend}" WITH CHECK (true)'))
            conn.execute(text(f'CREATE POLICY synthetic_visit_lock ON "{schema}".visits FOR UPDATE TO "{backend}" USING (true) WITH CHECK (true)'))
        runtime = create_engine(url.set(username=backend, password=password), connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"})
        with Session(runtime) as db:
            assert db.execute(text("SELECT CURRENT_USER,SESSION_USER")).one() == (backend, backend)
            assert benefit_visit_quote(db, first_id).total == Decimal("0.11")
            assert benefit_visit_quote(db, second_id).total == Decimal("0.05")
            visit = db.get(Visit, first_id)
            quote = PaymentInvariantService(db).compute_visit_quote(visit)
            assert quote.total == Decimal("0.11")
            assert list(quote.line_totals.values()) == [Decimal("0.11")]
            assert PaymentInvariantService(db).compute_total_cost(visit) == Decimal("0.11")
            assert PaymentInvariantService(db).compute_total_cost(db.get(Visit, plain_id)) == Decimal("0.07")
        with Session(runtime) as db:
            invariant = PaymentInvariantService(db)
            with pytest.raises(HTTPException) as error:
                invariant.create_payment_for_visit(visit_id=first_id, amount=Decimal("0.12"), method="cash",
                    note="synthetic", current_user=SimpleNamespace(id=user_id), allow_overpayment=False, commit=False)
            assert getattr(error.value, "status_code", None) == 400
            payment = invariant.create_payment_for_visit(visit_id=first_id, amount=Decimal("0.11"), method="cash",
                note="synthetic", current_user=SimpleNamespace(id=user_id), allow_overpayment=False, commit=False)
            assert payment.amount == Decimal("0.11")
            db.rollback()
        # The same nonowner role can reprice a plain draft invoice, but may
        # never silently replace an already approved benefit with gross prices.
        with Session(runtime) as db:
            group = lock_financial_group(db, plain_id)
            requote_draft_invoice_prices(group, {plain_id: Decimal("0.11")})
            assert group.invoices[0].total_amount == Decimal("0.11")
            db.rollback()
        with Session(runtime) as db:
            group = lock_financial_group(db, first_id)
            with pytest.raises(FinancialFenceError):
                requote_draft_invoice_prices(group, {first_id: Decimal("0.31"), second_id: Decimal("0.05")})
            db.rollback()
        # A live session's old Visit cannot be combined with a later quote.
        # Real 0102/0115 triggers advance the context when the line changes.
        with Session(runtime, expire_on_commit=False) as db:
            stale_visit = db.get(Visit, plain_id)
            db.commit()
            with engine.begin() as conn:
                conn.execute(text("UPDATE visit_services SET price=0.08 WHERE id=:id"), {"id": plain_line_id})
            with pytest.raises(HTTPException) as error:
                PaymentInvariantService(db).compute_visit_quote(stale_visit)
            assert error.value.status_code == 409
            db.refresh(stale_visit)
            assert PaymentInvariantService(db).compute_visit_quote(stale_visit).total == Decimal("0.08")
            db.rollback()
        with engine.begin() as conn:
            conn.execute(text("UPDATE visit_services SET price=0.07 WHERE id=:id"), {"id": plain_line_id})
            plain_epoch = conn.execute(text("SELECT confirmation_context_epoch FROM visits WHERE id=:id"), {"id": plain_id}).scalar_one()
        with Session(engine) as db:
            db.add(AllFreeRequest(visit_id=plain_id, patient_id=patient_id, encounter_id=plain_encounter_id,
                visit_id_snapshot=plain_id, patient_id_snapshot=patient_id, encounter_id_snapshot=plain_encounter_id,
                visit_context_epoch=plain_epoch, baseline_total=Decimal("0.07"), status="approved",
                requested_by_user_id_snapshot=user_id, requested_by_role_snapshot="Admin", policy_auto_approve=False,
                decision_kind="admin", decided_by_user_id_snapshot=user_id, decided_by_role_snapshot="Admin",
                decided_at=datetime.now(UTC)))
            db.commit()
        with Session(runtime) as db:
            group = lock_financial_group(db, plain_id)
            with pytest.raises(FinancialFenceError):
                requote_draft_invoice_prices(group, {plain_id: Decimal("0.11")})
            assert group.invoices[0].total_amount == Decimal("0.07")
            db.rollback()
        # Changing even an ineligible sibling line invalidates the group via
        # the real 0102/0115 epoch trigger, not by a mocked context update.
        with engine.begin() as conn:
            conn.execute(text("UPDATE visit_services SET price=0.06 WHERE id=:id"), {"id": other_id})
        with Session(runtime) as db:
            with pytest.raises(BenefitQuoteError):
                benefit_visit_quote(db, first_id)
        # A line update between the amount snapshot and the display metadata
        # must not produce a mixed invitation. No real provider is contacted.
        with Session(runtime) as db:
            visit = db.get(Visit, plain_id)
            patient = SimpleNamespace(id=patient_id, first_name="SYNTHETIC", last_name="Benefit")
            connection = db.connection()
            changed = []

            def change_between_queries(_conn, _cursor, statement, _parameters, _context, _executemany):
                if not changed and "FROM visit_services" in statement:
                    changed.append(True)
                    with engine.begin() as writer:
                        writer.execute(text("UPDATE visit_services SET price=0.09 WHERE id=:id"), {"id": plain_line_id})

            event.listen(connection, "after_cursor_execute", change_between_queries)
            try:
                with pytest.raises(HTTPException) as error:
                    FormattingMixin()._prepare_notification_data(db, visit, patient)
                assert error.value.status_code == 409
                assert changed == [True]
            finally:
                event.remove(connection, "after_cursor_execute", change_between_queries)
                db.rollback()
    finally:
        if runtime:
            runtime.dispose()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(capability_schema_name(schema), cascade=True))
            conn.execute(DropSchema(schema, cascade=True))
            conn.execute(text(f'DROP OWNED BY "{backend}"'))
            conn.execute(text(f'DROP OWNED BY "{cap}"'))
            conn.execute(text(f'DROP OWNED BY "{recon_cap}"'))
            conn.execute(text(f'DROP ROLE "{backend}"'))
            conn.execute(text(f'DROP ROLE "{cap}"'))
            conn.execute(text(f'DROP ROLE "{recon_cap}"'))
        admin.dispose()
