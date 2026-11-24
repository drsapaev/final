"""Real PostgreSQL link/FK races for staff payment confirmation."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC
from decimal import Decimal
from threading import Barrier
from types import SimpleNamespace

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import event, inspect, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.payment import Payment, PaymentVisit
from app.models.payment_webhook import PaymentTransaction, PaymentWebhook
from app.repositories.provider_webhook_repository import ProviderWebhookRepository
from app.services.payment_invariant_service import PaymentInvariantService
from app.services import provider_webhook_service
from tests.integration.test_encounter_migration_pg import _migration
from tests.integration.test_group_payment_preflight_pg import pg_case  # noqa: F401


def _payment(engine, visit_id):
    with Session(engine) as db:
        payment = Payment(visit_id=visit_id, amount=Decimal("1.00"), status="pending", method="cash", currency="UZS")
        db.add(payment)
        db.flush()
        payment_id = payment.id
        db.commit()
        return payment_id


def test_existing_writer_first_causes_safe_retry_then_complete_links(pg_case):
    runtime, ids, admin = pg_case
    payment_id = _payment(admin, ids[0])
    with Session(admin) as writer:
        writer.add(PaymentVisit(payment_id=payment_id, visit_id=ids[1], amount=Decimal("1.00")))
        writer.flush()  # Holds FK KEY SHARE on Payment and the linked Visit.
        with Session(runtime) as confirmer:
            with pytest.raises(HTTPException) as error:
                PaymentInvariantService(confirmer).preflight_payment_record(payment_id)
            assert error.value.status_code == 409
            assert not confirmer.in_transaction()
        writer.commit()
    with Session(runtime) as confirmer:
        record = PaymentInvariantService(confirmer).preflight_payment_record(payment_id)
        assert record.visit_ids == tuple(sorted([ids[0], ids[1]]))
        assert {visit_id for _, visit_id in record.links} == {ids[1]}
        confirmer.rollback()


@pytest.mark.parametrize("mutation", ["insert", "update", "delete"])
def test_confirm_first_blocks_link_mutations_before_commit(pg_case, mutation):
    runtime, ids, admin = pg_case
    payment_id = _payment(admin, ids[0])
    with Session(admin) as db:
        existing = PaymentVisit(payment_id=payment_id, visit_id=ids[1], amount=Decimal("1.00"))
        db.add(existing)
        db.flush()
        link_id = existing.id
        db.commit()
    with Session(runtime) as confirmer:
        locked = PaymentInvariantService(confirmer).preflight_payment_record(payment_id)
        assert locked.visit_ids == tuple(sorted([ids[0], ids[1]]))
        def mutate():
            with Session(admin) as db:
                db.execute(text("SET LOCAL lock_timeout='100ms'"))
                try:
                    if mutation == "insert":
                        db.add(PaymentVisit(payment_id=payment_id, visit_id=ids[2], amount=Decimal("0.00")))
                    elif mutation == "update":
                        db.get(PaymentVisit, link_id).visit_id = ids[2]
                    else:
                        db.delete(db.get(PaymentVisit, link_id))
                    db.flush()
                except DBAPIError as exc:
                    db.rollback()
                    return getattr(exc.orig, "sqlstate", None)
                return "unexpected-success"
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(mutate).result(timeout=10) == "55P03"
        confirmer.rollback()


def _install_payment_visit_uniqueness(conn):
    migration = _migration("0156_payment_visit_pair_unique.py")
    schema = conn.scalar(text("SELECT pg_catalog.current_schema()"))
    migration.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema}))
    migration.upgrade()


def test_payment_visit_uniqueness_preserves_distinct_allocations(pg_case):
    _, ids, admin = pg_case
    with admin.begin() as conn:
        original_timeout = conn.scalar(text("SHOW lock_timeout"))
        _install_payment_visit_uniqueness(conn)
        assert conn.scalar(text("SHOW lock_timeout")) == original_timeout
    first = _payment(admin, ids[0])
    second = _payment(admin, ids[0])
    with Session(admin) as db:
        db.add_all([
            PaymentVisit(payment_id=first, visit_id=ids[0], amount=Decimal("0.40")),
            PaymentVisit(payment_id=first, visit_id=ids[1], amount=Decimal("0.60")),
            PaymentVisit(payment_id=second, visit_id=ids[0], amount=Decimal("1.00")),
        ])
        db.commit()
        db.add(PaymentVisit(payment_id=first, visit_id=ids[0], amount=Decimal("0.20")))
        with pytest.raises(IntegrityError) as error:
            db.flush()
        assert error.value.orig.sqlstate == "23505"
        assert error.value.orig.diag.constraint_name == "uq_payment_visits_payment_visit"
        db.rollback()
        allocations = db.execute(select(PaymentVisit.amount).order_by(PaymentVisit.id)).scalars().all()
        assert allocations == [Decimal("0.40"), Decimal("0.60"), Decimal("1.00")]


def test_payment_visit_uniqueness_rolls_back_on_existing_duplicate_pair(pg_case):
    _, ids, admin = pg_case
    payment = _payment(admin, ids[0])
    with Session(admin) as db:
        db.add_all([
            PaymentVisit(payment_id=payment, visit_id=ids[0], amount=Decimal("0.40")),
            PaymentVisit(payment_id=payment, visit_id=ids[0], amount=Decimal("0.60")),
        ])
        db.commit()
    with pytest.raises(IntegrityError) as error, admin.begin() as conn:
        _install_payment_visit_uniqueness(conn)
    assert error.value.orig.sqlstate == "23505"
    assert error.value.orig.diag.message_primary == "Payment visit links require reconciliation"
    assert error.value.orig.diag.message_detail is None
    with admin.connect() as conn:
        schema = conn.scalar(text("SELECT pg_catalog.current_schema()"))
        assert all(
            index["name"] != "uq_payment_visits_payment_visit"
            for index in inspect(conn).get_indexes("payment_visits", schema=schema)
        )
        allocations = conn.execute(select(PaymentVisit.amount).order_by(PaymentVisit.id)).scalars().all()
        assert allocations == [Decimal("0.40"), Decimal("0.60")]


def test_provider_reference_locks_only_the_matching_payment(pg_case):
    _, ids, admin = pg_case
    reference = "SYNTHETIC-SHARED-PROVIDER-REFERENCE"
    with Session(admin) as db:
        payments = [
            Payment(
                visit_id=visit_id,
                amount=Decimal("1.00"),
                status="pending",
                method="online",
                currency="KZT",
                provider=provider,
                provider_payment_id=reference,
            )
            for visit_id, provider in zip(ids, ("payme", "kaspi"), strict=False)
        ]
        db.add_all(payments)
        db.flush()
        other_id, kaspi_id = [payment.id for payment in payments]
        db.commit()

    with Session(admin) as bound:
        selected = ProviderWebhookRepository(bound).get_payment_by_provider_payment_id_for_update(
            provider="kaspi", provider_payment_id=reference
        )
        assert selected is not None and selected.id == kaspi_id
        with Session(admin) as concurrent:
            other = select(Payment.id).where(Payment.id == other_id).with_for_update(nowait=True)
            assert concurrent.scalar(other) == other_id
            same = select(Payment.id).where(Payment.id == kaspi_id).with_for_update(nowait=True)
            with pytest.raises(DBAPIError) as error:
                concurrent.scalar(same)
            assert error.value.orig.sqlstate == "55P03"


def test_payme_replay_locks_payment_and_same_provider_transaction(pg_case):
    _, ids, admin = pg_case
    reference = "SYNTHETIC-PAYME-REPLAY"
    with Session(admin) as db:
        payment = Payment(
            visit_id=ids[0], amount=Decimal("1.00"), method="online", currency="UZS",
            status="processing", provider="payme", provider_payment_id="SYNTHETIC-PAYME-ORDER",
        )
        db.add(payment)
        db.flush()
        payment_id = payment.id
        transaction = PaymentTransaction(
            transaction_id=reference, provider="payme", status="processing",
            amount=100, currency="UZS", payment_id=payment_id, visit_id=ids[0],
        )
        db.add(transaction)
        db.flush()
        transaction_id = transaction.id
        db.commit()

    with Session(admin) as db:
        repo = ProviderWebhookRepository(db)
        assert repo.get_payment_by_id_for_update(payment_id, provider="kaspi") is None
        assert repo.get_payment_by_id_for_update(payment_id, provider="payme").id == payment_id
        assert repo.get_existing_transaction(
            transaction_id=reference, provider="payme", for_update=True
        ).id == transaction_id

        for model, row_id in ((Payment, payment_id), (PaymentTransaction, transaction_id)):
            with Session(admin) as concurrent:
                query = select(model.id).where(model.id == row_id).with_for_update(nowait=True)
                with pytest.raises(DBAPIError) as error:
                    concurrent.scalar(query)
                assert error.value.orig.sqlstate == "55P03"


def test_concurrent_payme_creates_reuse_one_receipt(pg_case, monkeypatch):
    _, ids, admin = pg_case
    order = "SYNTHETIC-PAYME-ORDER"
    reference = "synthetic-payme-registration"
    payme_time = 1735689600000
    with Session(admin) as db:
        db.add_all([
            Payment(
                visit_id=ids[0], amount=Decimal("1.00"), method="online", currency="UZS",
                status="pending", provider="payme", provider_payment_id=order,
            ),
            PaymentWebhook(
                provider="kaspi", webhook_id="synthetic-unrelated-webhook",
                transaction_id="synthetic-unrelated", status="ignored",
                amount=100, currency="KZT", raw_data={},
            ),
        ])
        db.commit()

    provider = SimpleNamespace(validate_webhook_signature=lambda *args: True)
    result = SimpleNamespace(
        success=True, payment_id=order, status="processing", provider_data={"amount": "1.00"},
    )
    manager = SimpleNamespace(get_provider=lambda name: provider, process_webhook=lambda *args: result)
    monkeypatch.setattr(provider_webhook_service, "get_payment_manager", lambda: manager)

    barrier = Barrier(2)
    current_lookup = ProviderWebhookRepository.get_existing_transaction

    def initial_lookup(repository, *, transaction_id, provider, for_update=False):
        existing = current_lookup(
            repository, transaction_id=transaction_id, provider=provider, for_update=for_update
        )
        if transaction_id == reference and not for_update and existing is None:
            barrier.wait(timeout=8)
        return existing

    monkeypatch.setattr(ProviderWebhookRepository, "get_existing_transaction", initial_lookup)

    def submit(transaction_id, *, method="CreateTransaction"):
        params = {"id": transaction_id}
        if method == "CreateTransaction":
            params.update(amount=100, time=payme_time, account={"order_id": order})
        elif method == "CancelTransaction":
            params["reason"] = 5
        with Session(admin) as db:
            service = provider_webhook_service.ProviderWebhookService(db)
            return service.process_payme_webhook(
                {"id": "synthetic-rpc", "method": method, "params": params},
                "Basic synthetic",
            )

    def statement(start, end):
        with Session(admin) as db:
            service = provider_webhook_service.ProviderWebhookService(db)
            return service.process_payme_webhook(
                {
                    "id": "synthetic-statement",
                    "method": "GetStatement",
                    "params": {"from": start, "to": end},
                },
                "Basic synthetic",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(submit, (reference, reference))
    assert first["result"] == second["result"]
    assert submit(reference)["result"] == first["result"]
    assert submit("synthetic-other-registration")["error"]["code"] == -31008

    with Session(admin) as db:
        receipt = db.scalars(select(PaymentWebhook).where(PaymentWebhook.provider == "payme")).one()
        transaction = db.scalars(select(PaymentTransaction).where(PaymentTransaction.provider == "payme")).one()
        assert receipt.status == "processed"
        assert transaction.webhook_id == receipt.id
        assert first["result"]["transaction"] == receipt.id
        assert first["result"]["transaction"] != transaction.id
        created_at = receipt.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        assert first["result"]["create_time"] == int(created_at.timestamp() * 1000)
        assert first["result"]["state"] == 1

    created_status = submit(reference, method="CheckTransaction")["result"]
    assert created_status == {
        **first["result"], "transaction": str(first["result"]["transaction"]),
        "perform_time": 0, "cancel_time": 0, "reason": None,
    }

    completed = submit(reference, method="PerformTransaction")
    replayed = submit(reference, method="PerformTransaction")
    with Session(admin) as db:
        payment = db.scalar(select(Payment).where(Payment.provider_payment_id == order))
        transaction = db.scalar(select(PaymentTransaction).where(
            PaymentTransaction.provider == "payme", PaymentTransaction.transaction_id == reference
        ))
        assert payment.status == "paid"
        assert transaction.status == "completed"
        assert completed["result"] == replayed["result"] == {
            "state": 2,
            "perform_time": int(payment.paid_at.timestamp() * 1000),
            "transaction": first["result"]["transaction"],
        }


    performed_status = submit(reference, method="CheckTransaction")["result"]
    assert performed_status == {
        **created_status, **completed["result"], "transaction": created_status["transaction"],
    }

    with ThreadPoolExecutor(max_workers=2) as pool:
        cancellations = list(pool.map(
            lambda _: submit(reference, method="CancelTransaction"), range(2)
        ))
    assert cancellations[0]["result"] == cancellations[1]["result"]
    assert cancellations[0]["result"]["transaction"] == first["result"]["transaction"]
    assert cancellations[0]["result"]["state"] == -2
    assert submit(reference, method="CancelTransaction")["result"] == cancellations[0]["result"]
    cancelled_status = submit(reference, method="CheckTransaction")["result"]
    assert cancelled_status == {
        **performed_status, **cancellations[0]["result"],
        "transaction": created_status["transaction"], "reason": 5,
    }
    assert statement(payme_time, payme_time)["result"] == {"transactions": [{
        "id": reference, "time": payme_time, "amount": 100,
        "account": {"order_id": order}, **cancelled_status,
    }]}
    assert statement(payme_time + 1, payme_time + 1)["result"] == {"transactions": []}

    with Session(admin) as db:
        payment = db.scalar(select(Payment).where(Payment.provider_payment_id == order))
        transaction = db.scalar(select(PaymentTransaction).where(
            PaymentTransaction.provider == "payme", PaymentTransaction.transaction_id == reference
        ))
        assert payment.status == transaction.status == "refunded"
        assert transaction.payme_cancel_receipt["cancel_time"] == cancellations[0]["result"]["cancel_time"]
        assert len(db.scalars(select(PaymentWebhook).where(PaymentWebhook.provider == "payme")).all()) == 1
        assert db.scalars(select(AuditLog).where(
            AuditLog.action == provider_webhook_service.PAYME_TX_PRE_CANCEL_STATE_ACTION,
            AuditLog.entity_id == transaction.id,
        )).one().payload == {"pre_cancel_status": "completed"}

    with Session(admin) as db:
        db.add(PaymentWebhook(
            provider="payme", webhook_id="synthetic-legacy-outside-int8",
            transaction_id="synthetic-legacy-order", status="processed", amount=100,
            currency="UZS", raw_data={"method": "CreateTransaction", "params": {"time": 173568960000000000000}},
        ))
        db.commit()
    assert statement(payme_time, payme_time)["error"]["code"] == -32400


@pytest.mark.parametrize("failed_write", ["secondary_audit", "cancellation_receipt"])
def test_payme_cancel_handles_audit_and_receipt_failures_atomically(pg_case, monkeypatch, failed_write):
    _, ids, admin = pg_case
    reference = f"synthetic-payme-cancellation-{failed_write}"
    with Session(admin) as db:
        payment = Payment(
            visit_id=ids[0], amount=Decimal("1.00"), method="online", currency="UZS",
            status="paid", provider="payme", provider_payment_id=f"SYNTHETIC-ORDER-{failed_write}",
        )
        db.add(payment)
        db.flush()
        transaction = PaymentTransaction(
            transaction_id=reference, provider="payme", status="completed",
            amount=100, currency="UZS", payment_id=payment.id, visit_id=ids[0],
        )
        db.add(transaction)
        db.flush()
        payment_id, transaction_id = payment.id, transaction.id
        db.commit()

    provider = SimpleNamespace(validate_webhook_signature=lambda *args: True)
    monkeypatch.setattr(
        provider_webhook_service, "get_payment_manager",
        lambda: SimpleNamespace(get_provider=lambda name: provider),
    )
    request = {
        "id": "synthetic-rpc",
        "method": "CancelTransaction",
        "params": {"id": reference, "reason": 5},
    }
    failed = []

    def fail_statement(_conn, cursor, statement, _params, _context, _executemany):
        audit = statement.startswith("INSERT INTO audit_logs")
        receipt = statement.startswith("UPDATE payment_transactions") and "payme_cancel_receipt" in statement
        if not failed and (
            (audit and failed_write == "secondary_audit")
            or (receipt and failed_write == "cancellation_receipt")
        ):
            failed.append(True)
            cursor.execute("SELECT 1 / 0")

    event.listen(admin, "before_cursor_execute", fail_statement)
    try:
        with Session(admin) as db:
            service = provider_webhook_service.ProviderWebhookService(db)
            update_payment_status = service._update_payment_status

            def verify_locks_then_update(**kwargs):
                if failed_write == "secondary_audit":
                    assert failed
                    assert db.scalar(text("SELECT 1")) == 1
                    for model, row_id in ((Payment, payment_id), (PaymentTransaction, transaction_id)):
                        with Session(admin) as concurrent:
                            query = select(model.id).where(model.id == row_id).with_for_update(nowait=True)
                            with pytest.raises(DBAPIError) as error:
                                concurrent.scalar(query)
                            assert error.value.orig.sqlstate == "55P03"
                return update_payment_status(**kwargs)

            service._update_payment_status = verify_locks_then_update
            response = service.process_payme_webhook(request, "Basic synthetic")
    finally:
        event.remove(admin, "before_cursor_execute", fail_statement)

    assert failed
    with Session(admin) as db:
        payment = db.get(Payment, payment_id)
        transaction = db.get(PaymentTransaction, transaction_id)
        assert db.scalar(select(AuditLog).where(
            AuditLog.action == provider_webhook_service.PAYME_TX_PRE_CANCEL_STATE_ACTION,
            AuditLog.entity_id == transaction_id,
        )) is None
        if failed_write == "cancellation_receipt":
            assert response["error"]["code"] == -32603
            assert payment.status == "paid"
            assert transaction.status == "completed"
            assert transaction.payme_cancel_receipt is None
        else:
            assert payment.status == transaction.status == "refunded"
            assert response["result"]["state"] == -2
            assert transaction.payme_cancel_receipt["cancel_time"] == response["result"]["cancel_time"]

    with Session(admin) as db:
        retry = provider_webhook_service.ProviderWebhookService(db).process_payme_webhook(
            request, "Basic synthetic"
        )
    assert retry["result"]["state"] == -2
    if failed_write == "secondary_audit":
        assert retry["result"] == response["result"]
        assert retry["payment_status"] is None
