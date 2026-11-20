"""Bank refund currency evidence on disposable PostgreSQL and SQLite."""

import importlib.util
import os
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.schema import CreateSchema, DropSchema

from app.models.payment import Payment
from app.models.refund_deposit import PaymentRefundClaim, RefundRequest, RefundType
from app.services.force_majeure_service import ForceMajeureService
from tests.integration.test_cashier_currency import _visit


def _revision(conn, schema):
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0131_bank_refund_currency.py"
    spec = importlib.util.spec_from_file_location("synthetic_bank_currency", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema}))
    return module


@pytest.fixture(params=["sqlite", "postgresql"])
def old_schema(request):
    admin = schema = None
    if request.param == "postgresql":
        url = sa.make_url(os.environ.get("DATABASE_URL", "sqlite://"))
        if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
            pytest.skip("requires disposable clinic_test PostgreSQL")
        admin = sa.create_engine(url, hide_parameters=True)
        schema = "bank_currency_" + uuid4().hex
        with admin.begin() as conn:
            conn.execute(CreateSchema(schema))
        engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema}"}, hide_parameters=True)
    else:
        engine = sa.create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE visits (id integer PRIMARY KEY, patient_id integer NOT NULL)")
            conn.exec_driver_sql("""CREATE TABLE payments (
                id integer PRIMARY KEY, visit_id integer NOT NULL REFERENCES visits, status text NOT NULL,
                currency text NOT NULL, amount numeric(12,2) NOT NULL, refunded_amount numeric(12,2)
            )""")
            conn.exec_driver_sql("""CREATE TABLE refund_requests (
                id integer PRIMARY KEY, patient_id integer NOT NULL, payment_id integer NOT NULL REFERENCES payments,
                visit_id integer, original_amount numeric(12,2) NOT NULL, refund_amount numeric(12,2) NOT NULL,
                commission_amount numeric(12,2) NOT NULL, refund_type text NOT NULL, is_automatic boolean NOT NULL,
                status text NOT NULL, created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            conn.exec_driver_sql("INSERT INTO visits VALUES (1,7)")
            conn.exec_driver_sql("INSERT INTO payments VALUES (1,1,'paid','KZT',10.25,NULL)")
            conn.exec_driver_sql("""INSERT INTO refund_requests
                (id,patient_id,payment_id,visit_id,original_amount,refund_amount,commission_amount,refund_type,is_automatic,status)
                VALUES (1,7,1,1,10.25,4.25,0,'bank_transfer',true,'pending')
            """)
        yield engine, schema
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as conn:
                conn.execute(DropSchema(schema, cascade=True))
            admin.dispose()


_NEW_REQUEST = sa.text("""INSERT INTO refund_requests
    (id,patient_id,payment_id,visit_id,original_amount,refund_amount,commission_amount,refund_type,is_automatic,status,
      payment_currency_snapshot)
    VALUES (2,:patient,1,1,10.25,:amount,0,'bank_transfer',true,'pending',:currency)
""")
_MATCHING = {"patient": 7, "amount": "4.25", "currency": "KZT"}


def test_bank_currency_starts_at_creation_and_cannot_be_changed(old_schema):
    engine, schema = old_schema
    with engine.begin() as conn:
        revision = _revision(conn, schema)
        revision.upgrade()
        assert conn.exec_driver_sql("SELECT payment_currency_snapshot FROM refund_requests WHERE id=1").scalar() is None
        revision.downgrade()
        assert conn.exec_driver_sql("SELECT id FROM refund_requests").scalar_one() == 1
        revision.upgrade()

        for incorrect in ({"patient": 8}, {"currency": "UZS"}, {"amount": "10.26"}):
            with pytest.raises(sa.exc.DBAPIError, match="invalid bank refund evidence"), conn.begin_nested():
                conn.execute(_NEW_REQUEST, _MATCHING | incorrect)
        conn.execute(_NEW_REQUEST, _MATCHING)
        for query in (
            "UPDATE refund_requests SET payment_currency_snapshot='KZT' WHERE id=1",
            "UPDATE refund_requests SET payment_currency_snapshot=NULL WHERE id=2",
            "UPDATE refund_requests SET refund_amount=1 WHERE id=2",
            "UPDATE refund_requests SET status='completed' WHERE id=2",
            "DELETE FROM refund_requests WHERE id=2",
        ):
            with pytest.raises(sa.exc.DBAPIError, match="immutable bank refund evidence"), conn.begin_nested():
                conn.exec_driver_sql(query)

        conn.exec_driver_sql("UPDATE payments SET currency='UZS' WHERE id=1")
        conn.exec_driver_sql("UPDATE refund_requests SET status='rejected' WHERE id=2")
        with pytest.raises(sa.exc.DBAPIError), conn.begin_nested():
            revision.downgrade()
        assert conn.exec_driver_sql(
            "SELECT payment_currency_snapshot,status FROM refund_requests WHERE id=2"
        ).one() == ("KZT", "rejected")


def test_postgres_role_needs_visible_original_payment(old_schema):
    owner, schema = old_schema
    if schema is None:
        pytest.skip("physical PostgreSQL login required")
    password = uuid4().hex
    role = "bank_refund_writer_" + password
    with owner.begin() as conn:
        _revision(conn, schema).upgrade()
        conn.exec_driver_sql(f"CREATE ROLE {role} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}'")
        conn.exec_driver_sql(f"GRANT USAGE ON SCHEMA {schema} TO {role}")
        conn.exec_driver_sql(f"GRANT SELECT (id,patient_id) ON visits TO {role}")
        conn.exec_driver_sql(f"GRANT INSERT, SELECT ON refund_requests TO {role}")
        conn.exec_driver_sql(f"GRANT SELECT, UPDATE (status) ON payments TO {role}")
        conn.exec_driver_sql("ALTER TABLE payments ENABLE ROW LEVEL SECURITY")
        conn.exec_driver_sql("ALTER TABLE payments FORCE ROW LEVEL SECURITY")
        conn.exec_driver_sql(f"CREATE POLICY bank_visibility ON payments FOR SELECT TO {role} USING (false)")
        conn.exec_driver_sql(f"CREATE POLICY bank_lock ON payments FOR UPDATE TO {role} USING (true) WITH CHECK (false)")
    runtime = sa.create_engine(owner.url.set(username=role, password=password),
                               connect_args={"options": f"-csearch_path={schema}"}, hide_parameters=True)
    try:
        with runtime.begin() as conn:
            assert conn.exec_driver_sql("SELECT CURRENT_USER").scalar_one() == role
            with pytest.raises(sa.exc.DBAPIError, match="invalid bank refund evidence"), conn.begin_nested():
                conn.execute(_NEW_REQUEST, _MATCHING)
            assert conn.exec_driver_sql("SELECT count(*) FROM refund_requests").scalar_one() == 1
        with owner.begin() as conn:
            conn.exec_driver_sql("ALTER POLICY bank_visibility ON payments USING (true)")
        with runtime.begin() as conn:
            conn.execute(_NEW_REQUEST, _MATCHING)
            assert conn.exec_driver_sql("SELECT payment_currency_snapshot FROM refund_requests WHERE id=2").scalar() == "KZT"
    finally:
        runtime.dispose()
        with owner.begin() as conn:
            conn.exec_driver_sql("DROP POLICY bank_visibility ON payments")
            conn.exec_driver_sql("DROP POLICY bank_lock ON payments")
            conn.exec_driver_sql(f"DROP OWNED BY {role}")
            conn.exec_driver_sql(f"DROP ROLE {role}")


def test_automatic_bank_refund_captures_original_currency_and_claim(db_session, test_patient, test_service):
    visit = _visit(db_session, test_patient, test_service, "KZT")
    payment = Payment(visit_id=visit.id, amount=Decimal("10.25"), currency="KZT", status="paid", method="cash")
    db_session.add(payment)
    db_session.commit()
    def create_request():
        return ForceMajeureService(db_session)._create_refund_request(
            patient_id=test_patient.id, payment_id=payment.id, visit_id=visit.id, amount=Decimal("4.25"),
            reason="SYNTHETIC", refund_type=RefundType.BANK_TRANSFER, is_automatic=True,
        )

    def abort_evidence(*_):
        raise RuntimeError("SYNTHETIC bank evidence insert failure")

    sa.event.listen(RefundRequest, "before_insert", abort_evidence)
    try:
        with pytest.raises(RuntimeError, match="SYNTHETIC bank evidence insert failure"):
            create_request()
    finally:
        sa.event.remove(RefundRequest, "before_insert", abort_evidence)
    db_session.commit()
    assert db_session.query(PaymentRefundClaim).filter_by(payment_id=payment.id).count() == 0

    result = create_request()
    db_session.commit()
    request = db_session.get(RefundRequest, result["request_id"])
    claim = db_session.get(PaymentRefundClaim, result["refund_claim_id"])
    assert (request.original_amount, request.refund_amount) == (Decimal("10.25"), Decimal("4.25"))
    assert request.payment_currency_snapshot == "KZT" and request.status == "pending"
    assert claim.refund_request_id == request.id and claim.payment_id == payment.id
