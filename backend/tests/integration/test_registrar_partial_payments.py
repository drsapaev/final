"""Registrar receipts must represent money received, not a paid checkbox."""

from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import event, text

from app.db.capability_namespace import capability_schema_name
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.visit import Visit, VisitService
from app.services.payment_invariant_service import PaymentInvariantService
from tests.integration.test_encounter_migration_pg import _migration
from tests.integration.test_staff_confirmation_guard_pg import (
    _module,
    guarded_pg,  # noqa: F401
)


@pytest.fixture
def payment_visits(db_session, test_patient):
    visits = [
        Visit(patient_id=test_patient.id, status="open", discount_mode="none", confirmation_context_epoch=1)
        for _ in range(2)
    ]
    db_session.add_all(visits)
    db_session.flush()
    for visit, amount in zip(visits, (60000, 40000), strict=True):
        db_session.add(
            VisitService(
                visit_id=visit.id,
                service_id=1,
                name="SYNTHETIC-payment",
                qty=1,
                price=amount,
                currency="UZS",
            )
        )
    invoice = PaymentInvoice(patient_id=test_patient.id, total_amount=100000, currency="UZS")
    db_session.add(invoice)
    db_session.flush()
    for visit, amount in zip(visits, (60000, 40000), strict=True):
        db_session.add(
            PaymentInvoiceVisit(
                invoice_id=invoice.id,
                visit_id=visit.id,
                visit_amount=amount,
            )
        )
    db_session.commit()
    return visits, invoice


def records_for(visits):
    return [{"record_kind": "visit", "record_id": visit.id} for visit in visits]


def summary(client, headers, records):
    response = client.post(
        "/api/v1/registrar/records/payment-summary",
        headers=headers,
        json={"records": records},
    )
    assert response.status_code == 200, response.text
    return response.json()


def pay(client, headers, records, amount, snapshot=None):
    return client.post(
        "/api/v1/registrar/records/actions",
        headers=headers,
        json={
            "action": "mark_paid",
            "records": records,
            "amount": amount,
            "method": "cash",
            "payment_snapshot": snapshot,
        },
    )


def test_partial_payment_then_top_up_preserves_invoice_debt(
    client,
    db_session,
    registrar_auth_headers,
    payment_visits,
):
    visits, invoice = payment_visits
    records = records_for(visits)
    before = summary(client, registrar_auth_headers, records)
    assert Decimal(before["remaining_amount"]) == 100000
    first = pay(client, registrar_auth_headers, records, 30000, before["snapshot"])
    assert first.status_code == 200, first.text
    after = first.json()["payment_summary"]
    assert after["payment_status"] == "partial"
    assert Decimal(after["paid_amount"]) == 30000
    assert Decimal(after["remaining_amount"]) == 70000
    db_session.expire_all()
    assert invoice.status == "pending"
    assert sum(p.amount for p in db_session.query(Payment).all()) == 30000
    reloaded = summary(client, registrar_auth_headers, records)
    assert reloaded == after
    final = pay(client, registrar_auth_headers, records, 70000, after["snapshot"])
    assert final.status_code == 200, final.text
    assert final.json()["payment_summary"]["payment_status"] == "paid"
    assert Decimal(final.json()["payment_summary"]["remaining_amount"]) == 0
    db_session.expire_all()
    assert invoice.status == "paid"
    assert [v.status for v in visits] == ["open", "open"]
    amounts = db_session.query(Payment.amount).order_by(Payment.id).all()
    assert [row[0] for row in amounts] == [30000, 30000, 40000]


def test_partial_refund_reopens_debt_and_allows_top_up(
    client,
    db_session,
    admin_auth_headers,
    registrar_auth_headers,
    payment_visits,
):
    visits, invoice = payment_visits
    records = records_for(visits)
    before = summary(client, registrar_auth_headers, records)
    settled_response = pay(
        client,
        registrar_auth_headers,
        records,
        100000,
        before["snapshot"],
    )
    assert settled_response.status_code == 200, settled_response.text
    settled = settled_response.json()["payment_summary"]
    assert settled["payment_status"] == "paid"

    first_payment = db_session.query(Payment).order_by(Payment.id).first()
    refund_response = client.post(
        f"/api/v1/cashier/payments/{first_payment.id}/refund",
        headers=admin_auth_headers,
        json={"amount": 10000, "reason": "SYNTHETIC-partial-refund", "client_request_id": str(uuid4())},
    )
    assert refund_response.status_code == 200, refund_response.text
    db_session.refresh(invoice)
    assert invoice.status == "pending"
    assert invoice.paid_at is None

    after_refund = summary(client, registrar_auth_headers, records)
    assert Decimal(after_refund["paid_amount"]) == 90000
    assert Decimal(after_refund["remaining_amount"]) == 10000
    assert after_refund["payment_status"] == "partial"
    assert after_refund["can_pay"] is True
    assert after_refund["snapshot"] != settled["snapshot"]

    stale = pay(
        client,
        registrar_auth_headers,
        records,
        10000,
        settled["snapshot"],
    )
    assert stale.status_code == 409, stale.text

    top_up = pay(
        client,
        registrar_auth_headers,
        records,
        10000,
        after_refund["snapshot"],
    )
    assert top_up.status_code == 200, top_up.text
    assert top_up.json()["payment_summary"]["payment_status"] == "paid"
    db_session.refresh(invoice)
    assert invoice.status == "paid"


def test_provider_refund_requires_reconciliation_before_amount_and_invoice_change(
    client,
    db_session,
    admin_auth_headers,
    registrar_auth_headers,
    payment_visits,
    monkeypatch,
):
    from app.services import payment_provider_manager_factory

    visits, invoice = payment_visits
    records = records_for(visits)
    before = summary(client, registrar_auth_headers, records)
    settled = pay(
        client,
        registrar_auth_headers,
        records,
        100000,
        before["snapshot"],
    )
    assert settled.status_code == 200, settled.text

    payment = db_session.query(Payment).order_by(Payment.id).first()
    payment.provider = "click"
    payment.provider_payment_id = "SYNTHETIC-provider-payment"
    db_session.commit()

    get_manager = Mock()
    monkeypatch.setattr(payment_provider_manager_factory, "get_payment_manager", get_manager)

    response = client.post(
        f"/api/v1/cashier/payments/{payment.id}/refund",
        headers=admin_auth_headers,
        json={"amount": 10000, "reason": "SYNTHETIC-provider-failure", "client_request_id": str(uuid4())},
    )
    assert response.status_code == 409, response.text
    get_manager.assert_not_called()

    db_session.expire_all()
    persisted_payment = db_session.get(Payment, payment.id)
    persisted_invoice = db_session.get(PaymentInvoice, invoice.id)
    assert persisted_payment.refunded_amount in {None, Decimal("0")}
    assert persisted_payment.status == "paid"
    assert persisted_invoice.status == "paid"


def test_payment_summary_loads_payment_ledger_once(db_session, payment_visits):
    visits, _ = payment_visits
    db_session.add_all(
        Payment(
            visit_id=visit.id,
            amount=10000,
            currency="UZS",
            method="cash",
            status="paid",
        )
        for visit in visits
    )
    db_session.commit()

    payment_selects: list[str] = []

    def capture_payment_select(_conn, _cursor, statement, _parameters, _context, _many):
        normalized = " ".join(statement.lower().split())
        if normalized.startswith("select") and " from payments" in normalized:
            payment_selects.append(normalized)

    bind = db_session.get_bind()
    event.listen(bind, "before_cursor_execute", capture_payment_select)
    try:
        result = PaymentInvariantService(db_session).summarize_visits(visits)
    finally:
        event.remove(bind, "before_cursor_execute", capture_payment_select)

    assert Decimal(result["paid_amount"]) == 20000
    assert len(payment_selects) == 1


def test_duplicate_request_snapshot_cannot_charge_twice(
    client,
    db_session,
    registrar_auth_headers,
    payment_visits,
):
    visits, _ = payment_visits
    records = records_for(visits)
    before = summary(client, registrar_auth_headers, records)
    assert (
        pay(
            client, registrar_auth_headers, records, 10000, before["snapshot"]
        ).status_code
        == 200
    )
    repeated = pay(client, registrar_auth_headers, records, 10000, before["snapshot"])
    assert repeated.status_code == 409, repeated.text
    assert db_session.query(Payment).count() == 1


def test_group_failure_rolls_back_all_receipts(
    client,
    db_session,
    registrar_auth_headers,
    payment_visits,
    monkeypatch,
):
    from fastapi import HTTPException

    from app.services.payment_invariant_service import PaymentInvariantService

    visits, invoice = payment_visits
    original = PaymentInvariantService.create_payment_for_visit

    def fail_second(self, *, visit_id, **kwargs):
        if visit_id == visits[1].id:
            raise HTTPException(409, "SYNTHETIC-payment-rejection")
        return original(self, visit_id=visit_id, **kwargs)

    monkeypatch.setattr(
        PaymentInvariantService, "create_payment_for_visit", fail_second
    )
    response = pay(client, registrar_auth_headers, records_for(visits), 100000)
    assert response.status_code == 409, response.text
    assert db_session.query(Payment).count() == 0
    db_session.refresh(invoice)
    assert invoice.status == "pending"


def test_visit_endpoint_honors_amount_and_allows_next_payment(
    client,
    db_session,
    registrar_auth_headers,
    payment_visits,
):
    visits, _ = payment_visits
    url = f"/api/v1/registrar/visits/{visits[0].id}/mark-paid"
    first = client.post(url, headers=registrar_auth_headers, json={"amount": 10000})
    assert first.status_code == 200, first.text
    assert first.json()["payment_status"] == "partial"
    second = client.post(url, headers=registrar_auth_headers, json={"amount": 50000})
    assert second.status_code == 200, second.text
    assert second.json()["payment_status"] == "paid"
    assert db_session.query(Payment).count() == 2


def test_payment_summary_rejects_doctor(client, cardio_auth_headers, payment_visits):
    visits, _ = payment_visits
    response = client.post(
        "/api/v1/registrar/records/payment-summary",
        headers=cardio_auth_headers, json={"records": records_for(visits)},
    )
    assert response.status_code == 403


def test_duplicate_visit_and_queue_refs_allocate_only_once(
    client,
    db_session,
    registrar_auth_headers,
    payment_visits,
    test_daily_queue,
):
    from app.models.online_queue import OnlineQueueEntry

    visits, _ = payment_visits
    entry = OnlineQueueEntry(
        queue_id=test_daily_queue.id,
        number=92,
        patient_id=visits[0].patient_id,
        visit_id=visits[0].id,
        patient_name="SYNTHETIC-payment",
        source="desk",
        status="waiting",
    )
    db_session.add(entry)
    db_session.commit()
    records = records_for(visits) + [
        {"record_kind": "online_queue", "record_id": entry.id}
    ]
    response = pay(client, registrar_auth_headers, records, 30000)
    assert response.status_code == 200, response.text
    assert db_session.query(Payment).count() == 1
    assert db_session.query(Payment).one().amount == 30000
    assert (
        summary(client, registrar_auth_headers, records)["payment_status"] == "partial"
    )


def test_both_read_adapters_keep_partial_debt_despite_newer_failed_payment(
    client,
    db_session,
    registrar_auth_headers,
    payment_visits,
):
    from app.api.v1.endpoints.registrar_integration._helpers import (
        _resolve_payment_truth as queue_truth,
    )
    from app.api.v1.endpoints.registrar_wizard._helpers import (
        _resolve_payment_truth as visit_truth,
    )

    visits, _ = payment_visits
    pay(client, registrar_auth_headers, records_for(visits), 30000)
    db_session.add(
        Payment(visit_id=visits[0].id, amount=9000, method="card", status="failed")
    )
    db_session.commit()
    for resolver in (queue_truth, visit_truth):
        assert resolver(db_session, visit_id=visits[0].id) == ("partial", "cash")


def test_rejects_cross_patient_group_before_any_receipt(
    client,
    db_session,
    registrar_auth_headers,
    payment_visits,
):
    from app.models.patient import Patient

    visits, _ = payment_visits
    other = Patient(last_name="SYNTHETIC-Other", first_name="SYNTHETIC-Test")
    db_session.add(other)
    db_session.flush()
    visits[1].patient_id = other.id
    db_session.commit()
    response = pay(client, registrar_auth_headers, records_for(visits), 30000)
    assert response.status_code == 400, response.text
    assert db_session.query(Payment).count() == 0


@pytest.mark.parametrize("amount", ["0.001", "1.234", "100000.01"])
def test_does_not_round_or_overallocate_submitted_amount(
    amount,
    client,
    db_session,
    registrar_auth_headers,
    payment_visits,
):
    visits, _ = payment_visits
    response = pay(client, registrar_auth_headers, records_for(visits), amount)
    assert response.status_code in {400, 422}, response.text
    assert db_session.query(Payment).count() == 0


@pytest.fixture
def payment_engines(guarded_pg):
    """Use the deployed guards for independent receipt writer sessions."""
    admin, runtime, _ = guarded_pg
    quote = admin.dialect.identifier_preparer.quote_identifier
    schema_name, runtime_name = admin.dialect.default_schema_name, runtime.url.username
    schema, role = map(quote, (schema_name, runtime_name))
    private = quote(capability_schema_name(schema_name))
    with admin.begin() as conn:
        migration = _migration("0123_reconciliation_fence.py")
        migration.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema_name}))
        migration.upgrade()
        conn.exec_driver_sql(f"ALTER TABLE {schema}.click_callback_receipts ENABLE ROW LEVEL SECURITY")
        conn.exec_driver_sql(f"ALTER TABLE {schema}.click_callback_receipts FORCE ROW LEVEL SECURITY")
        owner = conn.scalar(text("SELECT CURRENT_USER"))
        capability = conn.scalar(text("""
            SELECT pg_catalog.pg_get_userbyid(p.proowner) FROM pg_catalog.pg_proc p
            WHERE p.oid=pg_catalog.to_regprocedure(:signature)
        """), {"signature": f"{private}.financial_lock_rows(text,integer[])"})
        conn.exec_driver_sql(f"GRANT SELECT, INSERT ON {schema}.payments TO {role}")
        conn.exec_driver_sql(f"GRANT SELECT ON {schema}.payment_visits TO {role}")
        conn.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {schema}.payments_id_seq TO {role}")
        conn.exec_driver_sql(
            f"CREATE POLICY receipt_insert ON {schema}.payments FOR INSERT TO {role} WITH CHECK (true)"
        )
        conn.exec_driver_sql(
            f"GRANT UPDATE (status, payment_method, paid_at, updated_at) ON {schema}.payment_invoices TO {role}"
        )
        conn.exec_driver_sql(
            f"CREATE POLICY receipt_invoice_status ON {schema}.payment_invoices FOR UPDATE TO {role} "
            "USING (true) WITH CHECK (true)"
        )
        conn.exec_driver_sql(f"GRANT SELECT ON {schema}.queue_entries TO {role}")
    root = Path(__file__).resolve().parents[3]
    reconciler = _module(root / "scripts/provision_reconciliation_fence_role.py")
    reconciler.provision(admin, schema=schema_name, expected_owner=owner,
                         backend_role=runtime_name, capability_role=capability)
    return admin, runtime


@pytest.mark.gate_d
@pytest.mark.parametrize("use_snapshot", [True, False])
def test_concurrent_payment_rechecks_locked_balance(payment_engines, use_snapshot):
    from fastapi import HTTPException
    from sqlalchemy.orm import Session

    from app.models.patient import Patient
    from app.services.payment_invariant_service import PaymentInvariantService

    admin, runtime = payment_engines
    with Session(admin) as seed:
        patient = Patient(last_name="SYNTHETIC-Payment", first_name="SYNTHETIC-Test")
        seed.add(patient)
        seed.flush()
        visit = Visit(patient_id=patient.id, status="open")
        seed.add(visit)
        seed.flush()
        seed.add(
            VisitService(
                visit_id=visit.id,
                service_id=1,
                name="SYNTHETIC-payment",
                qty=1,
                price=100000,
                currency="UZS",
            )
        )
        seed.commit()
        visit_id = visit.id

    with Session(runtime) as first, Session(runtime) as second:
        second.get(Visit, visit_id)  # A stale identity map must refresh after the conflict.
        service = PaymentInvariantService(first)
        snapshot = service.summarize_visits([first.get(Visit, visit_id)])["snapshot"]
        service.receive_grouped_payment(
            visit_ids=[visit_id],
            amount=Decimal(30000),
            method="cash",
            current_user=None,
            snapshot=snapshot,
        )

        competing = {
            "visit_ids": [visit_id],
            "amount": Decimal(30000 if use_snapshot else 80000),
            "method": "cash",
            "current_user": None,
            "snapshot": snapshot if use_snapshot else None,
        }
        with pytest.raises(HTTPException) as busy:
            PaymentInvariantService(second).receive_grouped_payment(**competing)
        assert busy.value.status_code == 409
        assert busy.value.detail == "Обращение занято, повторите оплату"
        assert not second.in_transaction()
        first.commit()

        with pytest.raises(HTTPException) as rejected:
            PaymentInvariantService(second).receive_grouped_payment(**competing)
        assert rejected.value.status_code == (409 if use_snapshot else 400)
        assert rejected.value.detail != busy.value.detail
    with Session(admin) as check:
        assert check.query(Payment).one().amount == 30000


@pytest.mark.gate_d
def test_concurrent_visits_close_their_shared_invoice(payment_engines, monkeypatch):
    import threading
    from types import SimpleNamespace

    from fastapi import HTTPException
    from sqlalchemy.orm import Session

    from app.api.v1.endpoints.registrar_wizard._helpers import (
        MarkPaidRequest,
        RegistrarRecordRef,
    )
    from app.api.v1.endpoints.registrar_wizard._visits import _receive_registrar_payment
    from app.models.patient import Patient
    from app.services.payment_invariant_service import PaymentInvariantService

    admin, runtime = payment_engines
    with Session(admin) as seed:
        patient = Patient(last_name="SYNTHETIC-Invoice", first_name="SYNTHETIC-Test")
        seed.add(patient)
        seed.flush()
        visits = [Visit(patient_id=patient.id, status="open") for _ in range(2)]
        seed.add_all(visits)
        seed.flush()
        invoice = PaymentInvoice(patient_id=patient.id, total_amount=200)
        seed.add(invoice)
        seed.flush()
        for visit in visits:
            seed.add(
                VisitService(
                    visit_id=visit.id,
                    service_id=1,
                    name="SYNTHETIC-payment",
                    qty=1,
                    price=100,
                    currency="UZS",
                )
            )
            seed.add(
                PaymentInvoiceVisit(
                    invoice_id=invoice.id, visit_id=visit.id, visit_amount=100
                )
            )
        seed.commit()
        visit_ids, invoice_id = [v.id for v in visits], invoice.id

    first_received = threading.Event()
    release_first = threading.Event()
    worker_errors = []
    original = PaymentInvariantService.receive_grouped_payment

    def synchronize(self, **kwargs):
        result = original(self, **kwargs)
        if kwargs["visit_ids"] == [visit_ids[0]]:
            first_received.set()
            assert release_first.wait(5)
        return result

    monkeypatch.setattr(PaymentInvariantService, "receive_grouped_payment", synchronize)

    def pay_visit(session, visit_id):
        return _receive_registrar_payment(
            session, SimpleNamespace(role="Registrar", id=None),
            [RegistrarRecordRef(record_kind="visit", record_id=visit_id)],
            MarkPaidRequest(amount=100, method="cash"),
        )

    def receive_first_visit():
        with Session(runtime) as session:
            try:
                assert pay_visit(session, visit_ids[0]).success
            except Exception as exc:
                worker_errors.append(exc)

    first = threading.Thread(target=receive_first_visit)
    first.start()
    try:
        assert first_received.wait(5), worker_errors
        with Session(runtime) as second:
            with pytest.raises(HTTPException) as busy:
                pay_visit(second, visit_ids[1])
            assert busy.value.status_code == 409
            assert busy.value.detail == "Обращение занято, повторите оплату"
    finally:
        release_first.set()
        first.join(8)
    assert not first.is_alive()
    assert not worker_errors, worker_errors
    with Session(runtime) as retry:
        assert pay_visit(retry, visit_ids[1]).success
    with Session(admin) as check:
        assert check.query(Payment).count() == 2
        assert check.get(PaymentInvoice, invoice_id).status == "paid"
