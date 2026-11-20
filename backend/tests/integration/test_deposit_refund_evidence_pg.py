"""Exercise deposit settlement, report visibility and ownership on synthetic PostgreSQL."""

from decimal import Decimal

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi.testclient import TestClient
from sqlalchemy import insert, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.payment import Payment, PaymentVisit
from app.models.refund_deposit import (
    DepositTransaction,
    PatientDeposit,
    PaymentRefundClaim,
)
from app.models.visit import Visit
from app.services.force_majeure_service import ForceMajeureError, ForceMajeureService
from tests.integration.test_encounter_migration_pg import _migration
from tests.integration.test_staff_confirmation_guard_pg import guarded_pg  # noqa: F401


def install_deposit_guards(connection, schema: str) -> None:
    """Install the real guard in schemas whose ORM already created the column."""
    migration = _migration("0136_deposit_refund_evidence.py")
    migration.op = Operations(MigrationContext.configure(connection, opts={"version_table_schema": schema}))
    migration._install_postgres_guards(connection.dialect.identifier_preparer.quote_schema(schema))


@pytest.fixture
def settlement_case(guarded_pg, monkeypatch):
    from tests.integration.test_cashier_daily_currency import _daily_pg_app

    return _daily_pg_app(guarded_pg, monkeypatch)


def _payment_subject(db, visit_id):
    payment = db.scalars(select(Payment).filter_by(visit_id=visit_id, status="paid")).one()
    return payment.id, db.get(Visit, visit_id).patient_id


def _credit(db, payment_id, patient_id, visit_id):
    return ForceMajeureService(db)._add_to_deposit(
        patient_id=patient_id, amount=Decimal("4.00"), reason="SYNTHETIC",
        payment_id=payment_id, visit_id=visit_id, performed_by_id=None,
    )


def test_deposit_refund_is_atomic_immutable_and_counted_once(settlement_case):
    engine, runtime, ids, app, headers, _, _, _ = settlement_case
    visit_id = ids["visit"]
    with Session(engine) as writer:
        payment_id, patient_id = _payment_subject(writer, visit_id)
        result = _credit(writer, payment_id, patient_id, visit_id)
        assert result["new_balance"] == 4.0
        writer.commit()
        assert _credit(writer, payment_id, patient_id, visit_id)["already_refunded"] is True
        writer.commit()
        deposit = writer.scalars(select(PatientDeposit).filter_by(patient_id=patient_id)).one()
        credit = writer.scalars(select(DepositTransaction).filter_by(payment_id=payment_id)).one()
        claim = writer.scalars(select(PaymentRefundClaim).filter_by(payment_id=payment_id)).one()
        assert deposit.balance == credit.amount == credit.balance_after == Decimal("4.00")
        assert credit.refund_currency_snapshot == "UZS" and claim.deposit_transaction_id == credit.id
        assert not writer.get(Payment, payment_id).refunded_amount
        credit_id = credit.id

    for statement in ("UPDATE deposit_transactions SET amount=1 WHERE id=:id",
                      "DELETE FROM deposit_transactions WHERE id=:id"):
        with pytest.raises(DBAPIError, match="immutable deposit refund evidence"), engine.begin() as conn:
            conn.execute(text(statement), {"id": credit_id})

    migration = _migration("0136_deposit_refund_evidence.py")
    with pytest.raises(DBAPIError, match="deposit refund evidence prevents downgrade"), engine.begin() as conn:
        migration.op = Operations(MigrationContext.configure(conn))
        migration.downgrade()

    with runtime.connect() as conn:
        assert not conn.execute(text(
            "SELECT pg_catalog.has_table_privilege(CURRENT_USER,'deposit_transactions','SELECT')"
        )).scalar_one()
    with TestClient(app) as http:
        response = http.get("/api/v1/cashier/stats/by-currency", headers=headers)
        assert response.status_code == 200, response.text
        [bucket] = response.json()
        assert bucket["total_amount"] == "4.00"
        assert bucket["refunded_amount"] == "4.00" and bucket["net_total_amount"] == "0.00"
        assert bucket["requires_reconciliation"] is False

        with engine.begin() as conn:
            conn.exec_driver_sql("ALTER TABLE deposit_transactions DISABLE TRIGGER trg_protect_deposit_refund_evidence")
        assert http.get("/api/v1/cashier/stats/by-currency", headers=headers).status_code == 503


def test_visit_contention_or_wrong_subject_cannot_credit_a_deposit(settlement_case):
    engine, _, ids, _, _, _, _, _ = settlement_case
    visit_id = ids["visit"]
    with Session(engine) as writer:
        payment_id, patient_id = _payment_subject(writer, visit_id)
        unrelated = Patient(first_name="SYNTHETIC", last_name="REFUND SUBJECT")
        writer.add(unrelated)
        writer.flush()
        unrelated_id = unrelated.id
        writer.commit()
        with Session(engine) as editor:
            editor.execute(select(Visit.id).filter_by(id=visit_id).with_for_update())
            with pytest.raises(ForceMajeureError, match="повторите операцию"):
                _credit(writer, payment_id, patient_id, visit_id)
        with pytest.raises(ForceMajeureError, match="требует сверки"):
            _credit(writer, payment_id, unrelated_id, visit_id)
        writer.commit()
        assert writer.scalars(select(DepositTransaction.id).filter_by(payment_id=payment_id)).all() == []
        assert writer.scalars(select(PaymentRefundClaim.id).filter_by(payment_id=payment_id)).all() == []
        assert writer.scalars(select(PatientDeposit.id).where(
            PatientDeposit.patient_id.in_((patient_id, unrelated_id)),
        )).all() == []


def test_a_single_visit_cannot_refund_an_entire_linked_payment(settlement_case):
    engine, _, ids, _, _, _, _, _ = settlement_case
    visit_id = ids["visit"]
    with Session(engine) as writer:
        payment_id, patient_id = _payment_subject(writer, visit_id)
        additional_visit = Visit(patient_id=patient_id, status="open", confirmation_context_epoch=1)
        writer.add(additional_visit)
        writer.flush()
        writer.add_all([
            PaymentVisit(payment_id=payment_id, visit_id=visit_id, amount=Decimal("2.00")),
            PaymentVisit(payment_id=payment_id, visit_id=additional_visit.id, amount=Decimal("2.00")),
        ])
        writer.commit()

        with pytest.raises(ForceMajeureError, match="требует сверки"):
            _credit(writer, payment_id, patient_id, visit_id)
        writer.commit()
        assert writer.scalars(select(DepositTransaction.id).filter_by(payment_id=payment_id)).all() == []
        assert writer.scalars(select(PaymentRefundClaim.id).filter_by(payment_id=payment_id)).all() == []
        assert writer.scalars(select(PatientDeposit.id).filter_by(patient_id=patient_id)).all() == []


def test_postgres_delegates_only_the_guarded_settlement(settlement_case):
    engine, runtime, ids, _, _, schema, role, _ = settlement_case
    visit_id = ids["visit"]
    quote = engine.dialect.identifier_preparer.quote_identifier
    table = f"{quote(schema)}.deposit_transactions"
    guard = f"{quote(schema)}.protect_deposit_refund_evidence()"
    grantee = quote(role)
    with Session(engine) as writer:
        payment_id, patient_id = _payment_subject(writer, visit_id)
        deposit = PatientDeposit(patient_id=patient_id, balance=Decimal("0.00"), currency="UZS")
        claim = PaymentRefundClaim(payment_id=payment_id, channel="deposit")
        writer.add_all([deposit, claim])
        writer.flush()
        deposit_id, claim_id = deposit.id, claim.id
        writer.commit()

    with engine.begin() as conn:
        conn.exec_driver_sql(f"GRANT INSERT ON {table} TO {grantee}")
        conn.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {quote(schema)}.deposit_transactions_id_seq TO {grantee}")
        conn.exec_driver_sql(f"CREATE POLICY synthetic_credit ON {table} FOR INSERT TO {grantee} WITH CHECK (true)")
        conn.exec_driver_sql(f"REVOKE EXECUTE ON FUNCTION {guard} FROM {grantee}")
    statement = insert(DepositTransaction).values(
        deposit_id=deposit_id, transaction_type="credit", payment_id=payment_id, visit_id=visit_id,
        amount=Decimal("4.00"), balance_after=Decimal("0.00"), refund_currency_snapshot="UZS",
    ).returning(DepositTransaction.id)

    with pytest.raises(DBAPIError, match="deposit refund capability required"), runtime.begin() as conn:
        conn.execute(statement)
    with Session(engine) as writer:
        assert writer.get(PatientDeposit, deposit_id).balance == Decimal("0.00")
        assert writer.get(PaymentRefundClaim, claim_id).deposit_transaction_id is None

    with engine.begin() as conn:
        conn.exec_driver_sql(f"GRANT EXECUTE ON FUNCTION {guard} TO {grantee}")
    with runtime.begin() as conn:
        assert not conn.execute(text(
            "SELECT pg_catalog.has_column_privilege(CURRENT_USER,'patient_deposits','balance','UPDATE')"
        )).scalar_one()
        transaction_id = conn.execute(statement).scalar_one()

    with Session(engine) as writer:
        assert writer.get(PatientDeposit, deposit_id).balance == Decimal("4.00")
        assert writer.get(PaymentRefundClaim, claim_id).deposit_transaction_id == transaction_id
        assert writer.get(DepositTransaction, transaction_id).balance_after == Decimal("4.00")
