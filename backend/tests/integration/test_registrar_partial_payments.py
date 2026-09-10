"""Registrar receipts must represent money received, not a paid checkbox."""

from decimal import Decimal

import pytest
from sqlalchemy import event

from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.visit import Visit, VisitService
from app.services.payment_invariant_service import PaymentInvariantService


@pytest.fixture
def payment_visits(db_session, test_patient):
    visits = [
        Visit(patient_id=test_patient.id, status="open", discount_mode="none"),
        Visit(patient_id=test_patient.id, status="open", discount_mode="none"),
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
            )
        )
    invoice = PaymentInvoice(patient_id=test_patient.id, total_amount=100000)
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
    registrar_auth_headers,
    payment_visits,
):
    visits, _ = payment_visits
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
    first_payment.refunded_amount = Decimal("10000")
    db_session.commit()

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


def test_payment_summary_loads_payment_ledger_once(db_session, payment_visits):
    visits, _ = payment_visits
    db_session.add_all(
        Payment(
            visit_id=visit.id,
            amount=10000,
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
def payment_engine():
    import os
    from uuid import uuid4

    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.schema import CreateSchema, DropSchema

    from app.db.base_class import Base

    url = make_url(os.environ["DATABASE_URL"])
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith(
        "clinic_test"
    ):
        pytest.fail("Use an explicitly disposable clinic_test PostgreSQL database")
    schema = "test_partial_payment_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = create_engine(
        url,
        connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=8000"},
    )
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()


@pytest.mark.gate_d
@pytest.mark.parametrize("use_snapshot", [True, False])
def test_concurrent_payment_rechecks_locked_balance(payment_engine, use_snapshot):
    import threading
    import time

    from fastapi import HTTPException
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from app.models.patient import Patient
    from app.services.payment_invariant_service import PaymentInvariantService

    with Session(payment_engine) as seed:
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
            )
        )
        seed.commit()
        visit_id = visit.id

    ready, finished = threading.Event(), threading.Event()
    observed = {}
    with Session(payment_engine) as first:
        service = PaymentInvariantService(first)
        snapshot = service.summarize_visits([first.get(Visit, visit_id)])["snapshot"]
        service.receive_grouped_payment(
            visit_ids=[visit_id],
            amount=Decimal(30000),
            method="cash",
            current_user=None,
            snapshot=snapshot,
        )

        def second_payment():
            with Session(payment_engine) as second:
                observed["pid"] = second.scalar(text("SELECT pg_backend_pid()"))
                second.get(
                    Visit, visit_id
                )  # stale identity map must refresh after waiting
                ready.set()
                try:
                    PaymentInvariantService(second).receive_grouped_payment(
                        visit_ids=[visit_id],
                        amount=Decimal(30000 if use_snapshot else 80000),
                        method="cash",
                        current_user=None,
                        snapshot=snapshot if use_snapshot else None,
                    )
                    second.commit()
                    observed["status"] = 200
                except HTTPException as exc:
                    observed["status"] = exc.status_code
                    second.rollback()
                except Exception as exc:
                    observed["error"] = type(exc).__name__
                finally:
                    finished.set()

        worker = threading.Thread(target=second_payment)
        worker.start()
        try:
            assert ready.wait(5)
            deadline = time.monotonic() + 5
            blocked = False
            with payment_engine.connect() as observer:
                while time.monotonic() < deadline and not finished.is_set():
                    if observer.scalar(
                        text("SELECT cardinality(pg_blocking_pids(:pid))"),
                        {"pid": observed["pid"]},
                    ):
                        blocked = True
                        break
                    finished.wait(0.01)
            assert blocked, observed
            first.commit()
        finally:
            first.rollback()
            worker.join(10)
        assert not worker.is_alive()
        assert observed.get("status") == (409 if use_snapshot else 400), observed
    with Session(payment_engine) as check:
        assert check.query(Payment).one().amount == 30000


@pytest.mark.gate_d
def test_concurrent_visits_close_their_shared_invoice(payment_engine, monkeypatch):
    import threading
    from types import SimpleNamespace

    from sqlalchemy.orm import Session

    from app.api.v1.endpoints.registrar_wizard._helpers import (
        MarkPaidRequest,
        RegistrarRecordRef,
    )
    from app.api.v1.endpoints.registrar_wizard._visits import _receive_registrar_payment
    from app.models.patient import Patient
    from app.services.payment_invariant_service import PaymentInvariantService

    with Session(payment_engine) as seed:
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
                )
            )
            seed.add(
                PaymentInvoiceVisit(
                    invoice_id=invoice.id, visit_id=visit.id, visit_amount=100
                )
            )
        seed.commit()
        visit_ids, invoice_id = [v.id for v in visits], invoice.id

    staged = threading.Barrier(2, timeout=5)
    original = PaymentInvariantService.receive_grouped_payment

    def synchronize(self, **kwargs):
        result = original(self, **kwargs)
        staged.wait()  # Both independent receipts exist before either invoice sync.
        return result

    monkeypatch.setattr(PaymentInvariantService, "receive_grouped_payment", synchronize)
    failures = []

    def receive(visit_id):
        with Session(payment_engine) as session:
            try:
                _receive_registrar_payment(
                    session,
                    SimpleNamespace(role="Registrar", id=None),
                    [RegistrarRecordRef(record_kind="visit", record_id=visit_id)],
                    MarkPaidRequest(amount=100, method="cash"),
                )
            except Exception as exc:
                failures.append(type(exc).__name__)

    workers = [
        threading.Thread(target=receive, args=(visit_id,)) for visit_id in visit_ids
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(12)
        assert not worker.is_alive()
    assert not failures, failures
    with Session(payment_engine) as check:
        assert check.query(Payment).count() == 2
        assert check.get(PaymentInvoice, invoice_id).status == "paid"
