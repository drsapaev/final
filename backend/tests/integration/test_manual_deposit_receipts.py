"""Verify durable manual deposit commands using synthetic staff and ledger data."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal
from json import dumps
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.force_majeure import AddDepositRequest, UseDepositRequest
from app.api.v1.endpoints.registrar_wizard import _invoice
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment import Payment, PaymentVisit
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.refund_deposit import (
    DepositTransaction,
    PatientDeposit,
    PaymentRefundClaim,
    RefundRequest,
    RefundType,
)
from app.models.user import User
from app.models.visit import VisitService
from app.repositories.force_majeure_api_repository import ForceMajeureApiRepository
from app.services.force_majeure_api_service import (
    ForceMajeureApiDomainError,
    ForceMajeureApiService,
)
from app.services.force_majeure_service import ForceMajeureError, ForceMajeureService
from app.services.payment_init_service import PaymentInitDomainError, PaymentInitService
from app.services.payment_invariant_service import PaymentInvariantService
from tests.conftest import mint_access_token
from tests.integration.test_cashier_appointment_source_locks_pg import pg_cashier  # noqa: F401
from tests.integration.test_deposit_refund_evidence_pg import install_deposit_guards
from tests.integration.test_encounter_migration_pg import _migration
from tests.integration.test_staff_confirmation_guard_pg import guarded_pg  # noqa: F401

PREFIX = "/api/v1/force-majeure/deposits"


def _body(patient_id: int, amount: str) -> dict:
    return {"patient_id": patient_id, "amount": amount, "client_request_id": str(uuid4())}


@pytest.mark.parametrize("action", ("add", "use"))
def test_manual_deposit_requires_exact_amount_and_uuid(client, auth_headers, test_patient, action):
    path = f"{PREFIX}/{action}"
    patient_id = test_patient.id
    assert client.post(path, headers=auth_headers, json={"patient_id": patient_id, "amount": "1.00"}).status_code == 422
    for amount in ("0", "1.001", "10000000000.00", "Infinity"):
        assert client.post(path, headers=auth_headers, json=_body(patient_id, amount)).status_code == 422
    invalid = _body(patient_id, "1.00") | {"client_request_id": "synthetic-not-a-uuid"}
    assert client.post(path, headers=auth_headers, json=invalid).status_code == 422


@pytest.mark.parametrize("action", ["add", "use"])
def test_http_deposit_rejects_subcent_json_before_writing(
    client, db_session, auth_headers, test_patient, action,
):
    patient_id = test_patient.id
    funding = _body(patient_id, "20.25") | {"amount": 20.25}
    assert client.post(f"{PREFIX}/add", headers=auth_headers, json=funding).status_code == 200
    amount = "1.00000000000000000001"
    raw_body = dumps(_body(patient_id, amount)).replace(dumps(amount), amount)
    result = client.post(
        f"{PREFIX}/{action}",
        headers={**auth_headers, "Content-Type": "application/json"},
        content=raw_body,
    )
    assert result.status_code == 422
    db_session.expire_all()
    balance = db_session.scalar(select(PatientDeposit.balance).filter_by(patient_id=patient_id))
    assert balance == Decimal("20.25")
    assert db_session.scalar(select(func.count()).select_from(DepositTransaction)) == 1


def _price_visit(db, visit, service):
    db.add(VisitService(
        visit_id=visit.id, service_id=service.id, name="SYNTHETIC DEPOSIT SERVICE",
        qty=1, price=Decimal("80.00"), currency="UZS",
    ))
    db.commit()


def test_credit_and_debit_replay_original_balances(
    client, db_session, auth_headers, test_visit, test_service,
):
    _price_visit(db_session, test_visit, test_service)
    patient_id = test_visit.patient_id
    credit = _body(patient_id, "100.00")
    debit = _body(patient_id, "80.00") | {"visit_id": test_visit.id}

    def apply(action, body):
        response = client.post(f"{PREFIX}/{action}", headers=auth_headers, json=body)
        assert response.status_code == 200, response.text
        return response.json()

    credited = apply("add", credit)
    debited = apply("use", debit)
    later = apply("add", _body(patient_id, "5.00"))
    assert (credited["balance"], debited["balance"], later["balance"]) == (100, 20, 25)
    assert apply("add", credit) == credited
    assert apply("use", debit) == debited
    repeat_charge = _body(patient_id, "5.00") | {"visit_id": test_visit.id}
    refused = client.post(f"{PREFIX}/use", headers=auth_headers, json=repeat_charge)
    assert refused.status_code == 400, refused.text
    db_session.expire_all()
    deposit = db_session.scalar(select(PatientDeposit).filter_by(patient_id=patient_id))
    entries = db_session.scalars(select(DepositTransaction).filter_by(deposit_id=deposit.id)).all()
    assert deposit.balance == Decimal("25.00")
    assert len(entries) == len({entry.client_request_id for entry in entries}) == 3
    assert all(entry.command_currency == "UZS" and entry.command_is_active for entry in entries)
    [payment] = db_session.scalars(select(Payment).filter_by(visit_id=test_visit.id)).all()
    debit_entry = next(entry for entry in entries if entry.transaction_type == "debit")
    assert debit_entry.payment_id == payment.id and debit_entry.visit_id == payment.visit_id
    assert payment.amount == debit_entry.amount == Decimal("80.00")
    assert payment.currency == debit_entry.command_currency == "UZS"
    assert payment.method == "deposit" and payment.status == "paid"
    assert payment.client_request_id == debit["client_request_id"]


def test_visit_deposit_rolls_back_payment_if_debit_record_cannot_be_stored(
    db_session, admin_user, test_visit, test_service, monkeypatch,
):
    _price_visit(db_session, test_visit, test_service)
    patient_id, visit_id = test_visit.patient_id, test_visit.id
    deposit = PatientDeposit(patient_id=patient_id, balance=Decimal("100.00"), currency="UZS")
    db_session.add(deposit)
    db_session.commit()
    repository = ForceMajeureApiRepository(db_session)

    def reject_debit(row):
        assert row.payment_id is not None
        raise RuntimeError("synthetic debit receipt failure")

    monkeypatch.setattr(repository, "add", reject_debit)
    command = UseDepositRequest(**_body(patient_id, "80.00"), visit_id=visit_id)
    with pytest.raises(RuntimeError, match="synthetic debit receipt failure"):
        ForceMajeureApiService(db_session, repository=repository).use_deposit_for_payment(
            request=command, current_user_id=admin_user.id,
        )
    assert db_session.scalar(select(PatientDeposit.balance).filter_by(patient_id=patient_id)) == Decimal("100.00")
    assert db_session.scalar(select(func.count()).select_from(Payment).filter_by(visit_id=visit_id)) == 0
    assert db_session.scalar(select(func.count()).select_from(DepositTransaction).filter_by(visit_id=visit_id)) == 0


def test_visit_deposit_waits_for_pending_provider_intent(
    client, db_session, auth_headers, test_visit, test_service,
):
    _price_visit(db_session, test_visit, test_service)
    patient_id, visit_id = test_visit.patient_id, test_visit.id
    db_session.add_all([
        PatientDeposit(patient_id=patient_id, balance=Decimal("100.00"), currency="UZS"),
        Payment(visit_id=visit_id, amount=Decimal("80.00"), currency="UZS",
                provider="click", method="click", status="pending"),
    ])
    db_session.commit()

    response = client.post(
        f"{PREFIX}/use", headers=auth_headers,
        json=_body(patient_id, "80.00") | {"visit_id": visit_id},
    )
    assert response.status_code == 409
    assert db_session.scalar(select(PatientDeposit.balance).filter_by(patient_id=patient_id)) == Decimal("100.00")
    assert db_session.scalar(select(func.count()).select_from(Payment).filter_by(visit_id=visit_id)) == 1
    assert db_session.scalar(select(func.count()).select_from(DepositTransaction).filter_by(visit_id=visit_id)) == 0


@pytest.mark.parametrize("evidence", ["original", "missing", "multiple_tenders"])
def test_queue_cancellation_returns_deposit_only_to_proven_original_source(
    db_session, admin_user, test_visit, test_service, test_doctor, evidence,
):
    _price_visit(db_session, test_visit, test_service)
    patient_id, visit_id = test_visit.patient_id, test_visit.id
    funding = AddDepositRequest(**_body(patient_id, "100.00"))
    service = ForceMajeureApiService(db_session)
    service.add_to_deposit(request=funding, current_user_id=admin_user.id)
    if evidence == "missing":
        db_session.add(Payment(visit_id=visit_id, amount=Decimal("40.00"), currency="UZS",
                               method="deposit", status="paid"))
    else:
        command = UseDepositRequest(**_body(patient_id, "40.00"), visit_id=visit_id)
        service.use_deposit_for_payment(request=command, current_user_id=admin_user.id)
    if evidence == "multiple_tenders":
        db_session.add(Payment(visit_id=visit_id, amount=Decimal("40.00"), currency="UZS",
                               method="cash", status="paid"))
    queue = DailyQueue(day=date.today(), specialist_id=test_doctor.id, queue_tag="deposit_refund", active=True)
    db_session.add(queue)
    db_session.flush()
    entry = OnlineQueueEntry(queue_id=queue.id, visit_id=visit_id, patient_id=patient_id,
                             patient_name="SYNTHETIC", number=1, status="waiting", source="desk")
    db_session.add(entry)
    db_session.commit()

    result = ForceMajeureService(db_session).cancel_entries_with_refund(
        [entry], reason="SYNTHETIC", refund_type=RefundType.BANK_TRANSFER,
        performed_by_id=admin_user.id, send_notifications=False,
    )
    refund_expected = evidence == "original"
    assert result["cancelled"] == result["deposit_credits_created"] == int(refund_expected)
    assert result["failed"] == int(not refund_expected)
    assert result["refund_requests_created"] == 0
    assert entry.status == ("cancelled" if refund_expected else "waiting")
    assert db_session.scalar(select(PatientDeposit.balance).filter_by(patient_id=patient_id)) == (
        Decimal("60.00") if evidence == "multiple_tenders" else Decimal("100.00")
    )
    if refund_expected:
        assert result["details"][0]["refund_type"] == "deposit"
    assert db_session.scalar(select(func.count()).select_from(PaymentRefundClaim)) == int(refund_expected)
    assert db_session.scalar(select(func.count()).select_from(RefundRequest)) == 0


def test_deposit_key_reuse_cannot_change_amount_or_action(client, db_session, auth_headers, test_patient):
    credit = _body(test_patient.id, "20.00")
    assert client.post(f"{PREFIX}/add", headers=auth_headers, json=credit).status_code == 200
    for action, body in (("add", credit | {"amount": "21.00"}), ("use", credit)):
        response = client.post(f"{PREFIX}/{action}", headers=auth_headers, json=body)
        assert response.status_code == 409
        assert response.json() == {"detail": "Параметры депозитной операции не совпадают"}
    assert db_session.scalar(select(func.count()).select_from(DepositTransaction)) == 1


def test_deposit_replay_requires_the_original_cashier(client, db_session, auth_headers, test_patient):
    credit = _body(test_patient.id, "20.00")
    assert client.post(f"{PREFIX}/add", headers=auth_headers, json=credit).status_code == 200
    cashier = User(username="synthetic-other-deposit-cashier", hashed_password="!", role="Cashier", is_active=True)
    db_session.add(cashier)
    db_session.commit()
    other_headers = {"Authorization": f"Bearer {mint_access_token(cashier)}"}
    other_operation = client.post(f"{PREFIX}/add", headers=other_headers, json=_body(test_patient.id, "5.00"))
    assert other_operation.status_code == 200, other_operation.text
    response = client.post(f"{PREFIX}/add", headers=other_headers, json=credit)
    assert response.status_code == 409
    assert response.json() == {"detail": "Параметры депозитной операции не совпадают"}
    assert db_session.scalar(select(func.count()).select_from(DepositTransaction)) == 2


def _install_manual_deposit_runtime(owner, runtime):
    schema_name = owner.dialect.default_schema_name
    quote = owner.dialect.identifier_preparer.quote_identifier
    schema, role = quote(schema_name), quote(runtime.url.username)
    with owner.begin() as conn:
        install_deposit_guards(conn, schema_name)
        conn.exec_driver_sql(f"GRANT SELECT, INSERT ON {schema}.patient_deposits TO {role}")
        conn.exec_driver_sql(f"GRANT UPDATE (balance, updated_at) ON {schema}.patient_deposits TO {role}")
        conn.exec_driver_sql(f"GRANT SELECT, INSERT ON {schema}.deposit_transactions TO {role}")
        conn.exec_driver_sql(
            f"GRANT USAGE ON SEQUENCE {schema}.patient_deposits_id_seq, {schema}.deposit_transactions_id_seq TO {role}"
        )


@pytest.fixture
def manual_deposit_pg(guarded_pg):
    _install_manual_deposit_runtime(*guarded_pg[:2])
    return guarded_pg


@pytest.fixture
def visit_deposit_pg(pg_cashier, request):
    owner, runtime, ids = pg_cashier
    _install_manual_deposit_runtime(owner, runtime)
    if getattr(request, "param", None) == "unpaired_debit":
        # Preserve the shape that the pre-migration writer stored.
        with Session(owner) as db:
            deposit = PatientDeposit(patient_id=ids["patient"], balance=Decimal("20.00"), currency="UZS")
            db.add(deposit)
            db.flush()
            db.add(DepositTransaction(deposit_id=deposit.id, visit_id=ids["visit"], performed_by=ids["stage"],
                                      transaction_type="debit", amount=Decimal("5.00"), balance_after=deposit.balance))
            db.commit()
    quote = owner.dialect.identifier_preparer.quote_identifier
    schema_name = owner.dialect.default_schema_name
    schema, role = quote(schema_name), quote(runtime.url.username)
    with owner.begin() as conn:
        revision = _migration("0142_deposit_visit_payment.py")
        revision.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema_name}))
        revision.upgrade()
        conn.exec_driver_sql(f"ALTER TABLE {schema}.deposit_transactions ENABLE ROW LEVEL SECURITY")
        conn.exec_driver_sql(f"ALTER TABLE {schema}.deposit_transactions FORCE ROW LEVEL SECURITY")
        conn.exec_driver_sql(f"CREATE POLICY synthetic_debit_read ON {schema}.deposit_transactions FOR SELECT TO {role} USING (true)")
        conn.exec_driver_sql(f"CREATE POLICY synthetic_debit_write ON {schema}.deposit_transactions FOR INSERT TO {role} WITH CHECK (true)")
        for table in ("refund_requests", "payment_refund_claims"):
            conn.exec_driver_sql(f"GRANT SELECT ON {schema}.{table} TO {role}")
        for table in ("payments", "payment_refund_claims"):
            conn.exec_driver_sql(f"GRANT INSERT ON {schema}.{table} TO {role}")
            conn.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {schema}.{table}_id_seq TO {role}")
        conn.exec_driver_sql(f"GRANT SELECT (client_request_id) ON {schema}.payments TO {role}")
        conn.exec_driver_sql(f"GRANT SELECT (created_at) ON {schema}.payment_visits TO {role}")
        conn.exec_driver_sql(f"GRANT UPDATE (id) ON {schema}.visits TO {role}")
        conn.exec_driver_sql(f"GRANT EXECUTE ON FUNCTION {schema}.protect_deposit_refund_evidence() TO {role}")
        conn.exec_driver_sql(f"CREATE POLICY synthetic_deposit_paid ON {schema}.payments FOR INSERT TO {role} WITH CHECK (true)")
    return pg_cashier


@pytest.mark.parametrize("visit_deposit_pg", ["unpaired_debit"], indirect=True)
@pytest.mark.parametrize("can_see_history", [True, False])
def test_postgres_refuses_a_new_tender_with_unpaired_historical_debit(visit_deposit_pg, can_see_history):
    owner, runtime, ids = visit_deposit_pg
    patient_id, visit_id, actor_id = ids["patient"], ids["visit"], ids["stage"]
    if not can_see_history:
        with owner.begin() as conn:
            conn.exec_driver_sql("ALTER POLICY synthetic_debit_read ON deposit_transactions USING (visit_id IS NULL)")
    command = UseDepositRequest(**_body(patient_id, "10.00"), visit_id=visit_id)
    with Session(runtime) as db:
        api = ForceMajeureApiService(db)
        if can_see_history:
            with pytest.raises(ForceMajeureApiDomainError, match="Историческое списание") as error:
                api.use_deposit_for_payment(request=command, current_user_id=actor_id)
            assert error.value.status_code == 409
        else:
            with pytest.raises(DBAPIError, match="ledger visibility unavailable"):
                api.use_deposit_for_payment(request=command, current_user_id=actor_id)
    with Session(owner) as db:
        assert db.scalar(select(PatientDeposit.balance).filter_by(patient_id=patient_id)) == Decimal("20.00")
        assert db.scalar(select(func.count()).select_from(Payment)) == 0
        [old_debit] = db.scalars(select(DepositTransaction).filter_by(visit_id=visit_id)).all()
        assert old_debit.payment_id is None and old_debit.amount == Decimal("5.00")


@pytest.mark.parametrize("visit_deposit_pg", ["unpaired_debit"], indirect=True)
@pytest.mark.parametrize("can_see_history", [True, False])
def test_new_cash_and_provider_collection_waits_for_deposit_reconciliation(
    visit_deposit_pg, can_see_history, monkeypatch,
):
    owner, runtime, ids = visit_deposit_pg
    patient_id, visit_id, actor_id = ids["patient"], ids["visit"], ids["stage"]
    with Session(owner, expire_on_commit=False) as db:
        invoice = PaymentInvoice(patient_id=patient_id, total_amount=Decimal("10.00"), currency="UZS", status="pending")
        db.add(invoice)
        db.flush()
        db.add(PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visit_id, visit_amount=Decimal("10.00")))
        db.commit()
    if not can_see_history:
        with owner.begin() as conn:
            conn.exec_driver_sql("ALTER POLICY synthetic_debit_read ON deposit_transactions USING (visit_id IS NULL)")

    actor = SimpleNamespace(id=actor_id, role="Admin")
    expected = ("Историческое списание с депозита требует сверки" if can_see_history
                else "История списаний с депозита временно недоступна")
    with Session(runtime) as db:
        with pytest.raises(HTTPException) as cash:
            PaymentInvariantService(db).create_payment_for_visit(visit_id, Decimal("10.00"), "cash", None, actor)
        assert (cash.value.status_code, cash.value.detail) == (409, expected)

        gateway = Mock()
        gateway.get_providers_for_currency.return_value = ["click"]
        with pytest.raises(PaymentInitDomainError) as pending:
            PaymentInitService(db, gateway).init_payment(
                request=SimpleNamespace(state=None), current_user_id=actor_id,
                visit_id=visit_id, provider="click", amount=10.0, currency="UZS",
                description=None, return_url=None, cancel_url=None,
            )
        assert (pending.value.status_code, pending.value.detail) == (409, expected)
        gateway.create_payment.assert_not_called()

        factory = Mock()
        monkeypatch.setattr(_invoice, "get_payment_manager", factory)
        with pytest.raises(HTTPException) as invoice_error:
            _invoice.init_invoice_payment(_invoice.InvoicePaymentRequest(invoice_id=invoice.id, provider="click"), db, actor)
        assert (invoice_error.value.status_code, invoice_error.value.detail) == (409, expected)
        factory.assert_not_called()

    with Session(owner) as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 0
        assert db.get(PaymentInvoice, invoice.id).status == "pending"
        assert db.scalar(select(PatientDeposit.balance).filter_by(patient_id=patient_id)) == Decimal("20.00")
        assert db.scalar(select(func.count()).select_from(DepositTransaction)) == 1


def test_linked_deposit_conserves_ledger_and_returns_to_same_deposit_on_postgres(visit_deposit_pg):
    owner, runtime, ids = visit_deposit_pg
    patient_id, visit_id, actor_id = ids["patient"], ids["visit"], ids["stage"]
    credit = AddDepositRequest(**_body(patient_id, "10.00"))
    debit = UseDepositRequest(**_body(patient_id, "10.00"), visit_id=visit_id)
    with Session(runtime) as db:
        api = ForceMajeureApiService(db)
        funding = api.add_to_deposit(request=credit, current_user_id=actor_id)
        purchase = api.use_deposit_for_payment(request=debit, current_user_id=actor_id)
        assert funding["balance"] == 10.0 and purchase["balance"] == 0.0
        payment_id = db.scalar(select(Payment.id).filter_by(visit_id=visit_id))
        action = ForceMajeureService(db)
        refund = {"patient_id": patient_id, "visit_id": visit_id, "payment_id": payment_id,
                  "amount": Decimal("10.00"), "reason": "SYNTHETIC"}
        with pytest.raises(ForceMajeureError, match="исходный депозит"):
            action._create_refund_request(**refund, refund_type=RefundType.BANK_TRANSFER, is_automatic=True)
        db.rollback()
        returned = action._add_to_deposit(**refund, performed_by_id=actor_id)
        assert returned["deposit_id"] == funding["id"] and returned["new_balance"] == 10.0
        db.commit()
        assert action._add_to_deposit(**refund, performed_by_id=actor_id)["already_refunded"]
        assert api.use_deposit_for_payment(request=debit, current_user_id=actor_id) == purchase
    with Session(owner) as db:
        [outgoing, incoming] = db.scalars(select(DepositTransaction).filter_by(payment_id=payment_id)
                                        .order_by(DepositTransaction.id)).all()
        assert outgoing.transaction_type == "debit" and incoming.transaction_type == "credit"
        assert outgoing.deposit_id == incoming.deposit_id == funding["id"]
        assert outgoing.amount == incoming.amount == Decimal("10.00")
        assert db.get(PatientDeposit, funding["id"]).balance == Decimal("10.00")
        claim = db.scalars(select(PaymentRefundClaim).filter_by(payment_id=payment_id)).one()
        assert claim.deposit_transaction_id == incoming.id and claim.channel == "deposit"
        assert db.scalar(select(func.count()).select_from(RefundRequest)) == 0

        for record, reason in (
            (PaymentVisit(payment_id=payment_id, visit_id=visit_id, amount=Decimal("10.00")), "single visit"),
            (RefundRequest(patient_id=patient_id, payment_id=payment_id, visit_id=visit_id,
                           original_amount=Decimal("10.00"), refund_amount=Decimal("10.00"),
                           refund_type="bank_transfer", status="pending"), "requires a deposit refund"),
        ):
            with pytest.raises(DBAPIError, match=reason), db.begin_nested():
                db.add(record)
                db.flush()

        with pytest.raises(DBAPIError, match="evidence is immutable"), db.begin_nested():
            db.get(Payment, payment_id).amount = Decimal("11.00")
            db.flush()

    schema_name = owner.dialect.default_schema_name
    revision = _migration("0142_deposit_visit_payment.py")
    with pytest.raises(DBAPIError, match="evidence prevents downgrade"), owner.begin() as conn:
        revision.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema_name}))
        revision.downgrade()


def test_postgres_rejects_deposit_payment_without_a_debit_receipt(visit_deposit_pg):
    owner, runtime, ids = visit_deposit_pg
    with Session(runtime) as db:
        db.add(Payment(
            visit_id=ids["visit"], amount=Decimal("10.00"), currency="UZS", method="deposit",
            status="paid", paid_at=datetime.now(UTC), client_request_id=str(uuid4()),
        ))
        db.flush()
        with pytest.raises(DBAPIError, match="requires a debit receipt"):
            db.commit()
        db.rollback()
    with Session(owner) as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 0
        assert db.scalar(select(func.count()).select_from(DepositTransaction)) == 0


def test_postgres_deposit_tender_requires_the_atomic_balance_trigger(visit_deposit_pg):
    owner, runtime, ids = visit_deposit_pg
    actor_id, patient_id, visit_id = ids["stage"], ids["patient"], ids["visit"]
    with Session(runtime) as db:
        funded = ForceMajeureApiService(db).add_to_deposit(
            request=AddDepositRequest(**_body(patient_id, "10.00")), current_user_id=actor_id,
        )
    with owner.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE deposit_transactions DISABLE TRIGGER trg_apply_visit_deposit_transaction")
    with Session(runtime) as db:
        with pytest.raises(ForceMajeureApiDomainError) as error:
            ForceMajeureApiService(db).use_deposit_for_payment(
                request=UseDepositRequest(**_body(patient_id, "10.00"), visit_id=visit_id), current_user_id=actor_id,
            )
        assert error.value.status_code == 409
    with Session(owner) as db:
        assert db.get(PatientDeposit, funded["id"]).balance == Decimal("10.00")
        assert db.scalar(select(func.count()).select_from(Payment)) == 0
        assert db.scalar(select(func.count()).select_from(DepositTransaction)) == 1


def test_concurrent_retries_create_only_one_deposit_credit(manual_deposit_pg):
    owner, runtime, ids = manual_deposit_pg
    command = AddDepositRequest(**_body(ids["patient"], "25.00"))
    start = Barrier(2)

    def apply():
        with Session(runtime) as db:
            start.wait(timeout=5)
            return ForceMajeureApiService(db).add_to_deposit(request=command, current_user_id=ids["stage"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(apply), pool.submit(apply)
        assert first.result(timeout=12) == second.result(timeout=12)
    with Session(owner) as db:
        receipt = db.scalars(select(DepositTransaction).filter_by(client_request_id=command.client_request_id)).one()
        assert receipt.deposit.balance == receipt.balance_after == Decimal("25.00")
        assert receipt.performed_by == ids["stage"]


def test_deposit_key_race_rolls_back_the_other_patients_balance(manual_deposit_pg):
    owner, runtime, ids = manual_deposit_pg
    with Session(owner, expire_on_commit=False) as db:
        other = Patient(first_name="SYNTHETIC", last_name="SECOND DEPOSIT")
        db.add(other)
        db.commit()
        subjects = (ids["patient"], other.id)
    request_id = uuid4()
    ready = Barrier(2)

    class RacingRepository(ForceMajeureApiRepository):
        def commit(self) -> None:
            ready.wait(timeout=5)
            super().commit()

    def apply(patient_id):
        command = AddDepositRequest(patient_id=patient_id, amount=Decimal("25.00"), client_request_id=request_id)
        with Session(runtime) as db:
            service = ForceMajeureApiService(db, repository=RacingRepository(db))
            try:
                service.add_to_deposit(request=command, current_user_id=ids["stage"])
                return 200
            except ForceMajeureApiDomainError as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(apply, subjects)) == [200, 409]
    with Session(owner) as db:
        [deposit] = db.scalars(select(PatientDeposit).where(PatientDeposit.patient_id.in_(subjects))).all()
        assert deposit.balance == Decimal("25.00")
        assert db.scalar(select(func.count()).select_from(DepositTransaction)) == 1


def test_manual_deposit_receipt_is_immutable_and_prevents_downgrade(manual_deposit_pg):
    owner, runtime, ids = manual_deposit_pg
    command = AddDepositRequest(**_body(ids["patient"], "25.00"))
    with Session(runtime) as db:
        ForceMajeureApiService(db).add_to_deposit(request=command, current_user_id=ids["stage"])
    with owner.connect() as conn:
        receipt_id = conn.scalar(select(DepositTransaction.id).filter_by(client_request_id=command.client_request_id))
    for statement in (
        "UPDATE deposit_transactions SET amount=1 WHERE id=:id",
        "DELETE FROM deposit_transactions WHERE id=:id",
    ):
        with pytest.raises(DBAPIError, match="immutable manual deposit receipt"), owner.begin() as conn:
            conn.execute(text(statement), {"id": receipt_id})
    migration = _migration("0137_deposit_manual_receipts.py")
    with pytest.raises(DBAPIError, match="manual deposit receipts prevent downgrade"), owner.begin() as conn:
        migration.op = Operations(MigrationContext.configure(conn))
        migration.downgrade()


def test_deposit_ledger_refuses_truncation_and_preserves_command_replay(manual_deposit_pg):
    owner, runtime, ids = manual_deposit_pg
    revision = _migration("0139_deposit_receipt_truncate.py")
    schema = owner.dialect.default_schema_name
    options = {"version_table_schema": schema}
    quoted = owner.dialect.identifier_preparer.quote_schema(schema)
    with owner.begin() as conn:
        revision.op = Operations(MigrationContext.configure(conn, opts=options))
        revision.upgrade()

    command = AddDepositRequest(**_body(ids["patient"], "25.00"))
    with Session(runtime) as db:
        committed = ForceMajeureApiService(db).add_to_deposit(request=command, current_user_id=ids["stage"])

    for table in ("deposit_transactions", "patient_deposits"):
        with pytest.raises(DBAPIError, match="deposit receipt ledger cannot be truncated") as denied:
            with owner.begin() as conn:
                conn.exec_driver_sql(f"TRUNCATE {quoted}.{table} CASCADE")
        assert denied.value.orig.sqlstate == "23514"

    with pytest.raises(DBAPIError, match="deposit receipts prevent downgrade"), owner.begin() as conn:
        revision.op = Operations(MigrationContext.configure(conn, opts=options))
        revision.downgrade()

    with Session(runtime) as db:
        replay = ForceMajeureApiService(db).add_to_deposit(request=command, current_user_id=ids["stage"])
        assert replay == committed
    with Session(owner) as db:
        receipt = db.scalars(select(DepositTransaction).filter_by(client_request_id=command.client_request_id)).one()
        assert receipt.amount == Decimal("25.00")
        assert receipt.balance_after == receipt.deposit.balance == receipt.amount
        assert receipt.performed_by == ids["stage"]
