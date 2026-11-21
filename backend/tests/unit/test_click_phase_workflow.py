"""0127 schema tests; no payment settlement is implied by these records."""
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import DBAPIError


@pytest.fixture
def phase_schema(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'click_phase.db'}", connect_args={"timeout": 0.1})

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0127_click_phase_binding.py"
    spec = importlib.util.spec_from_file_location("click_phase_0127", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as db:
        db.execute(text("PRAGMA foreign_keys=ON"))
        db.execute(text("""CREATE TABLE provider_attempts (
            id integer PRIMARY KEY, order_ref text NOT NULL, merchant_hash text NOT NULL, fingerprint text NOT NULL,
            amount_minor text NOT NULL, currency text NOT NULL, currency_exponent integer NOT NULL,
            provider text NOT NULL, target_kind text NOT NULL, actor_user_id_snapshot integer NOT NULL,
            payment_id_snapshot integer, invoice_id_snapshot integer, public_id text, client_key_hash text,
            payment_id integer, invoice_id integer, actor_user_id integer, status text, updated_at text)"""))
        db.execute(text("""CREATE TABLE provider_attempt_visits (
            id integer PRIMARY KEY, attempt_id integer NOT NULL, visit_id integer, visit_id_snapshot integer NOT NULL,
            patient_id_snapshot integer NOT NULL, context_epoch integer NOT NULL, amount_minor text NOT NULL, created_at text)"""))
        for number in (1, 2):
            db.execute(text("""INSERT INTO provider_attempts VALUES (:id,:order,:merchant,:fingerprint,'1234','UZS',2,
                'click','payment',1,1,NULL,:public,NULL,1,NULL,1,'prepared',NULL)"""),
                {"id": number, "order": f"invoice_{number}_issued", "merchant": "a" * 64,
                 "fingerprint": "b" * 64, "public": f"p{number}"})
        for table in ("click_callback_receipts", "provider_reconciliation_events"):
            db.execute(text(f"CREATE TABLE {table} (id integer PRIMARY KEY)"))
            db.execute(text(f"INSERT INTO {table} VALUES (1), (2)"))
        migration.op = Operations(MigrationContext.configure(db))
        migration.upgrade()
    yield engine, migration
    engine.dispose()


def insert_prepare(db, *, attempt=1, receipt=1, transaction="123", minor="1234"):
    db.execute(text("""INSERT INTO click_issued_attempts
      (attempt_id,order_ref,merchant_hash,fingerprint,amount_minor,currency,currency_exponent,provider,target_kind,actor_user_id_snapshot,allocations_sha256)
      SELECT id,order_ref,merchant_hash,fingerprint,amount_minor,currency,currency_exponent,provider,target_kind,actor_user_id_snapshot,:digest
      FROM provider_attempts WHERE id=:attempt ON CONFLICT(attempt_id) DO NOTHING"""), {"digest": "c" * 64, "attempt": attempt})
    db.execute(text("""
      INSERT INTO click_prepares(attempt_id,receipt_id,click_trans_id,service_id,merchant_hash,order_ref,amount_minor,currency)
      VALUES (:attempt,:receipt,:transaction,'100',:merchant,'invoice_1_issued',:minor,'UZS')
    """), {"attempt": attempt, "receipt": receipt, "transaction": transaction, "merchant": "a" * 64, "minor": minor})


def test_prepare_uniqueness_immutability_and_foreign_keys(phase_schema):
    engine, _ = phase_schema
    with engine.begin() as db:
        insert_prepare(db)
        for args in ({"attempt": 1, "receipt": 2, "transaction": "different"},
                     {"attempt": 2, "receipt": 2}, {"attempt": 99, "receipt": 2, "transaction": "different"},
                     {"attempt": 2, "receipt": 2, "transaction": "different", "minor": "1.5"}):
            with pytest.raises(DBAPIError), db.begin_nested():
                insert_prepare(db, **args)
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text("UPDATE click_prepares SET amount_minor='999'"))
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text("DELETE FROM click_prepares"))
        assert db.execute(text("SELECT amount_minor FROM click_prepares")).scalar_one() == "1234"


def test_receipt_event_links_immutable_and_downgrade_preserves_evidence(phase_schema):
    engine, migration = phase_schema
    with engine.begin() as db:
        db.execute(text("INSERT INTO click_receipt_reconciliation_links (receipt_id,event_id) VALUES (1,1)"))
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text("DELETE FROM click_receipt_reconciliation_links"))
    with engine.connect() as db:
        migration.op = Operations(MigrationContext.configure(db))
        with pytest.raises(DBAPIError):
            migration.downgrade()
        db.rollback()
        assert db.execute(text("SELECT count(*) FROM click_receipt_reconciliation_links")).scalar_one() == 1


def test_empty_schema_downgrades_and_reupgrades(phase_schema):
    engine, migration = phase_schema
    with engine.begin() as db:
        migration.op = Operations(MigrationContext.configure(db))
        migration.downgrade()
        migration.upgrade()
        assert db.execute(text("SELECT count(*) FROM click_prepares")).scalar_one() == 0


def test_prepare_binding_checks_each_visit_and_preserves_zero_links():
    from app.services.click_webhook_protocol import ClickObservation
    from app.services.click_webhook_reducer import (
        AttemptAllocation,
        ClickReductionError,
        InvoiceAllocation,
        allocation_digest,
        verify_prepare_binding,
    )

    order = "invoice_1_550e8400-e29b-41d4-a716-446655440000"
    allocations = [AttemptAllocation(1, 1, 42, 10, "1200"), AttemptAllocation(2, 2, 42, 11, "0")]
    links = [InvoiceAllocation(10, 1, "1200"), InvoiceAllocation(11, 2, "0")]
    observation = ClickObservation("123", "100", order, None, "12.00", None, "1200", 0, "time", "0", "")
    values = {"observation": observation, "confidence": "authenticated", "issued_order": order, "service_id": "100",
              "expected_minor": "1200", "expected_merchant_hash": "a" * 64, "actual_merchant_hash": "a" * 64,
              "expected_allocation_digest": allocation_digest(allocations, links), "allocations": allocations, "links": links}
    verify_prepare_binding(**values)
    # Equal-and-opposite changes preserve the total yet invalidate the per-link snapshot.
    changed = [InvoiceAllocation(10, 1, "1100"), InvoiceAllocation(11, 2, "100")]
    with pytest.raises(ClickReductionError):
        verify_prepare_binding(**{**values, "links": changed})
    for changed_fields in ({"confidence": "probable"}, {"service_id": "101"},
                           {"expected_minor": "1201"}, {"actual_merchant_hash": "b" * 64},
                           {"issued_order": "invoice_1"}):
        with pytest.raises(ClickReductionError):
            verify_prepare_binding(**{**values, **changed_fields})


def test_allocation_digest_detects_epoch_and_link_identity_changes():
    from app.services.click_webhook_reducer import (
        AttemptAllocation,
        InvoiceAllocation,
        allocation_digest,
    )

    allocations = [AttemptAllocation(1, 1, 42, 10, "1200")]
    baseline = allocation_digest(allocations, [InvoiceAllocation(10, 1, "1200")])
    assert baseline != allocation_digest([AttemptAllocation(1, 1, 42, 11, "1200")], [InvoiceAllocation(10, 1, "1200")])
    assert baseline != allocation_digest(allocations, [InvoiceAllocation(12, 1, "1200")])


@pytest.fixture
def attempt_case(case):
    # Reuse the canonical synthetic actor/visit fixture from the attempt suite.
    return case


@pytest.fixture
def case(request):
    from tests.unit.test_provider_attempts_service import case as existing_case

    return existing_case.__wrapped__(request.getfixturevalue("db_session"))


def test_seal_attempt_revalidates_owner_and_visit_before_dispatch_marker(attempt_case, monkeypatch):
    from app.models.click_prepare import ClickIssuedAttempt
    from app.models.provider_attempt import ProviderAttempt
    from app.services.provider_attempt_service import (
        ProviderAttemptError,
        ProviderAttemptService,
    )
    from tests.unit.test_provider_attempts_service import FakeManager

    checked = []
    monkeypatch.setattr("app.services.encounter_financial_fence.preflight_payment_groups", lambda db, visits: checked.append(visits))
    service = ProviderAttemptService(attempt_case.db, FakeManager())
    result = service.reserve_click_issuance(bearer=attempt_case.context, target_kind="payment",
        target_id=attempt_case.payment.id, amount="1.15")
    order = service.seal_click_issuance(public_id=result.public_id, bearer=attempt_case.context)
    assert checked == [[attempt_case.visit.id], [attempt_case.visit.id]]
    assert attempt_case.db.query(ClickIssuedAttempt).one().order_ref == order
    assert attempt_case.db.query(ProviderAttempt).one().status == "dispatching"
    attempt_case.db.commit()
    with pytest.raises(ProviderAttemptError, match="История оплаты требует сверки"):
        service.seal_click_issuance(public_id=result.public_id, bearer=attempt_case.context)


def test_seal_rejects_revoked_actor_and_preserves_no_marker(attempt_case, monkeypatch):
    from app.models.click_prepare import ClickIssuedAttempt
    from app.services.provider_attempt_service import (
        ProviderAttemptError,
        ProviderAttemptService,
    )
    from tests.unit.test_provider_attempts_service import FakeManager

    monkeypatch.setattr("app.services.encounter_financial_fence.preflight_payment_groups", lambda db, visits: None)
    service = ProviderAttemptService(attempt_case.db, FakeManager())
    result = service.reserve_click_issuance(bearer=attempt_case.context, target_kind="payment",
        target_id=attempt_case.payment.id, amount="1.15")
    attempt_case.db.commit()
    attempt_case.actor.is_active = False
    attempt_case.db.commit()
    with pytest.raises(ProviderAttemptError) as error:
        ProviderAttemptService(attempt_case.db, FakeManager()).seal_click_issuance(public_id=result.public_id, bearer=attempt_case.context)
    assert error.value.status_code == 401
    assert attempt_case.db.query(ClickIssuedAttempt).count() == 0


def test_historical_attempt_cannot_be_reclassified_as_issued(attempt_case, monkeypatch):
    from app.models.click_prepare import ClickIssuedAttempt
    from app.services.provider_attempt_service import (
        ProviderAttemptError,
        ProviderAttemptService,
    )
    from tests.unit.test_provider_attempts_service import FakeManager, _reserve

    monkeypatch.setattr("app.services.encounter_financial_fence.preflight_payment_groups", lambda db, visits: None)
    old = _reserve(attempt_case)
    attempt_case.db.commit()
    with pytest.raises(ProviderAttemptError, match="История оплаты требует сверки"):
        ProviderAttemptService(attempt_case.db, FakeManager()).seal_click_issuance(public_id=old.public_id, bearer=attempt_case.context)
    assert attempt_case.db.query(ClickIssuedAttempt).count() == 0


def test_configured_receipt_keys_support_rotation_and_reject_ambiguous_config():
    import base64
    import json

    from pydantic import SecretStr

    from app.services.click_receipt_service import (
        ClickReceiptError,
        configured_receipt_keys,
    )

    encoded = base64.b64encode(b"K" * 64).decode()
    secret = SecretStr(json.dumps({"v1": encoded, "v2": encoded}))
    assert configured_receipt_keys(secret, "v2") == {"v1": b"K" * 64, "v2": b"K" * 64}
    for invalid, version in ((SecretStr('{"v1":"x","v1":"x"}'), "v1"),
                             (SecretStr(json.dumps({"v1": encoded})), "v2"),
                             (SecretStr(json.dumps({"v1": "bad"})), "v1"),
                             (None, "v1")):
        with pytest.raises(ClickReceiptError, match="receipt key unavailable"):
            configured_receipt_keys(invalid, version)


def test_retained_webhook_credentials_cover_old_keys_and_reject_invalid_config():
    import json

    from pydantic import SecretStr

    from app.services.click_receipt_service import (
        ClickReceiptError,
        configured_webhook_credentials,
    )

    retained = SecretStr(json.dumps([{"service_id": "100", "secret": "old"}, {"service_id": "100", "secret": "new"}]))
    assert configured_webhook_credentials(retained, "100", "new") == (("100", "new"), ("100", "old"))
    assert configured_webhook_credentials(retained, None, None) == (("100", "old"), ("100", "new"))
    for config, service, secret in ((None, "100", None),
                                    (SecretStr('[{"service_id":"100","secret":"x","secret":"y"}]'), None, None),
                                    (SecretStr('[{"service_id":"100","secret":""}]'), None, None),
                                    (None, None, None)):
        with pytest.raises(ClickReceiptError, match="credentials unavailable"):
            configured_webhook_credentials(config, service, secret)


def test_webhook_credential_selection_accepts_old_but_not_retired_signature():
    import hashlib
    from urllib.parse import urlencode

    from app.services.click_receipt_service import select_webhook_credential
    from app.services.click_webhook_protocol import ClickProtocolError

    fields = {"click_trans_id": "12", "service_id": "100", "merchant_trans_id": "invoice_1",
              "amount": "12.00", "action": "0", "error": "0", "error_note": "",
              "sign_time": "2026-11-17 10:00:00", "click_paydoc_id": "42"}
    fields["sign_string"] = hashlib.md5(b"12100oldinvoice_112.0002026-11-17 10:00:00", usedforsecurity=False).hexdigest()
    body = urlencode(fields).encode()
    assert select_webhook_credential(body, "application/x-www-form-urlencoded", (("100", "new"), ("100", "old"))) == ("100", "old")
    with pytest.raises(ClickProtocolError, match="unverified"):
        select_webhook_credential(body, "application/x-www-form-urlencoded", (("100", "new"),))


def test_sqlite_writer_serializes_marker_and_new_visit(phase_schema):
    engine, _ = phase_schema
    with engine.connect() as issuer, engine.connect() as writer:
        issuer.execute(text("""INSERT INTO provider_attempt_visits(id,attempt_id,visit_id,visit_id_snapshot,patient_id_snapshot,context_epoch,amount_minor)
          VALUES (1,1,1,1,1,1,'1234')"""))
        insert_prepare(issuer)
        with pytest.raises(DBAPIError):
            writer.execute(text("""INSERT INTO provider_attempt_visits(id,attempt_id,visit_id,visit_id_snapshot,patient_id_snapshot,context_epoch,amount_minor)
              VALUES (2,1,2,2,1,1,'0')"""))
        writer.rollback()
        issuer.commit()
        with pytest.raises(DBAPIError, match="immutable"):
            writer.execute(text("""INSERT INTO provider_attempt_visits(id,attempt_id,visit_id,visit_id_snapshot,patient_id_snapshot,context_epoch,amount_minor)
              VALUES (2,1,2,2,1,1,'0')"""))
        writer.rollback()
        writer.execute(text("UPDATE provider_attempt_visits SET visit_id=NULL WHERE id=1"))
        with pytest.raises(DBAPIError, match="immutable"), writer.begin_nested():
            writer.execute(text("UPDATE provider_attempt_visits SET visit_id=1 WHERE id=1"))
        writer.commit()
