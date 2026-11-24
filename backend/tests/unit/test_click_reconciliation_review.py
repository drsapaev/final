"""0129 review schema: append-only evidence, never an automatic settlement."""
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import DBAPIError


@pytest.fixture
def review_schema(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'click_review.db'}", connect_args={"timeout": 0.1})

    @event.listens_for(engine, "connect")
    def enable_fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    path = Path(__file__).resolve().parents[2] / "alembic/versions/0129_click_reconciliation.py"
    spec = importlib.util.spec_from_file_location("click_review_0129", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as db:
        for table in ("click_callback_receipts", "provider_reconciliation_events", "click_issued_attempts", "click_prepares", "users"):
            db.execute(text(f"CREATE TABLE {table} (id integer PRIMARY KEY)"))
            db.execute(text(f"INSERT INTO {table} VALUES (1)"))
        db.execute(text("CREATE TABLE click_receipt_key_versions (version text PRIMARY KEY)"))
        db.execute(text("INSERT INTO click_receipt_key_versions VALUES ('v1')"))
        db.execute(text("CREATE TABLE provider_reconciliation_mutex (id integer PRIMARY KEY)"))
        db.execute(text("INSERT INTO provider_reconciliation_mutex VALUES (1)"))
        migration.op = Operations(MigrationContext.configure(db))
        migration.upgrade()
    yield engine, migration
    engine.dispose()


def review(db, *, sequence=1, result="no_debit", reason="provider_cancelled", size=1, proof=b"x" * 17):
    db.execute(text("""INSERT INTO click_reconciliation_reviews
      (receipt_id,event_id,issued_attempt_id,prepare_id,actor_user_id,actor_user_id_snapshot,actor_role,
       review_sequence,receipt_sha256,event_snapshot_sha256,target_context_sha256,proof_sha256,proof_key_version,proof_ciphertext,proof_size,
       source_kind,result,reason_code,amount_minor,currency,reviewed_at)
      VALUES (1,1,1,1,1,1,'Admin',:sequence,:receipt,:receipt,:receipt,:proof,'v1',:ciphertext,:size,
       'official_document',:result,:reason,'1200','UZS','2026-11-17 00:00:00')"""),
      {"sequence": sequence, "receipt": "a" * 64, "proof": "b" * 64, "ciphertext": proof,
       "size": size, "result": result, "reason": reason})


def test_append_only_proof_survives_actor_deletion_and_cannot_be_rebound(review_schema):
    engine, _ = review_schema
    with engine.begin() as db:
        review(db)
        for statement in ("UPDATE click_reconciliation_reviews SET amount_minor='1'", "DELETE FROM click_reconciliation_reviews"):
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(text(statement))
        db.execute(text("DELETE FROM users WHERE id=1"))
        assert db.execute(text("SELECT actor_user_id,actor_user_id_snapshot FROM click_reconciliation_reviews")).one() == (None, 1)
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text("UPDATE click_reconciliation_reviews SET actor_user_id=1"))


def test_reject_conflicting_status_invalid_proof_and_downgrade(review_schema):
    engine, migration = review_schema
    with engine.begin() as db:
        for args in ({"result": "no_debit", "reason": "provider_confirmed_debit"},
                     {"result": "debit_confirmed", "reason": "provider_cancelled"},
                     {"size": 2, "proof": b"short"}):
            with pytest.raises(DBAPIError), db.begin_nested():
                review(db, **args)
        review(db)
        review(db, sequence=2, result="debit_confirmed", reason="provider_confirmed_debit")
    with engine.connect() as db:
        migration.op = Operations(MigrationContext.configure(db))
        with pytest.raises(DBAPIError):
            migration.downgrade()
        db.rollback()
        assert db.execute(text("SELECT count(*) FROM click_reconciliation_reviews")).scalar_one() == 2


@pytest.mark.parametrize("path", [
    "/api/v1/payments/webhook/click",
    "/api/v1/payments/reconcile/click/receipts/42/review",
    "POST /api/v1/payments/reconcile/click/receipts/{receipt_id}/attest",
])
def test_sensitive_payment_sentry_drops_body_exception_locals_and_breadcrumbs(path):
    from app.core.sentry import sanitize_event

    marker = "UNIQUE_PROVIDER_PROOF_DO_NOT_LEAK"
    event = {"event_id": "test", "transaction": path,
             "request": {"url": path, "method": "POST", "data": {"proof": marker, "sign_string": marker}},
             "exception": {"values": [{"type": "ValueError", "value": marker,
                                         "stacktrace": {"frames": [{"vars": {"raw": marker}}]}}]},
             "breadcrumbs": {"values": [{"message": marker, "data": {"url": path}}]},
             "extra": {"raw": marker}}
    sanitized = sanitize_event(event)
    assert marker not in str(sanitized)
    assert sanitized["transaction"] == "[REDACTED PAYMENT EVIDENCE]"
    assert sanitized["exception"] == {"values": [{"type": "ValueError"}]}


def test_payment_privacy_is_exact_and_validation_cannot_echo_proof(caplog):
    import logging

    from fastapi import Request

    from app.core.exception_handlers import _sanitize_validation_errors
    from app.core.pii_masker import is_sensitive_payment_evidence_path
    from app.middleware.audit_middleware import AuditMiddleware

    marker = "UNIQUE_PROVIDER_EVIDENCE_DO_NOT_LOG"
    path = "/api/v1/payments/reconcile/click/receipts/42/attest"
    assert is_sensitive_payment_evidence_path(path)
    assert not is_sensitive_payment_evidence_path(path + "/other")
    errors = [{"type": "int_parsing", "loc": ("body", marker), "msg": marker,
               "input": marker, "ctx": {"error": marker}}]
    assert marker not in str(_sanitize_validation_errors(errors, sensitive_payment=True))
    request = Request({"type": "http", "method": "POST", "scheme": "https", "server": ("test", 443),
                       "path": path, "query_string": ("proof=" + marker).encode(), "headers": []})
    with caplog.at_level(logging.INFO, logger="app.middleware.audit_middleware"):
        AuditMiddleware._audit_log_request(request, "synthetic", "POST")
    assert marker not in caplog.text
    assert "?[REDACTED]" in caplog.text


def test_real_validation_handler_never_echoes_rejected_proof_or_field_name(caplog):
    import logging

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from pydantic import BaseModel, ConfigDict

    from app.core.exception_handlers import register_exception_handlers

    class ReviewBody(BaseModel):
        model_config = ConfigDict(extra="forbid")
        proof: int

    app = FastAPI()
    register_exception_handlers(app)

    @app.post("/api/v1/payments/reconcile/click/receipts/{receipt_id}/attest")
    async def route(receipt_id: int, payload: ReviewBody):
        return {"ok": True}

    marker = "UNIQUE_BAD_PROOF_VALUE_AND_KEY"
    with caplog.at_level(logging.WARNING), TestClient(app) as client:
        response = client.post("/api/v1/payments/reconcile/click/receipts/1/attest", json={"proof": marker, marker: "x"})
    assert response.status_code == 422
    assert response.headers["cache-control"] == "no-store"
    assert marker not in response.text
    assert marker not in caplog.text


def test_review_token_and_encrypted_document_bind_context_and_session():
    from dataclasses import replace

    from app.services.click_reconciliation_review import (
        ClickReviewError,
        ReviewContext,
        decrypt_proof,
        encrypt_proof,
        proof_digest,
        review_token,
        session_digest,
    )

    proof = b"%PDF-1.4\nsynthetic provider document\n%%EOF"
    context = ReviewContext(actor_id=1, actor_epoch=2, session_digest=session_digest("session-a", 1, 2),
        receipt_id=3, receipt_sha256="a" * 64, event_id=4, event_snapshot_sha256="b" * 64,
        target_context_sha256="c" * 64, issued_attempt_id=5, prepare_id=6, proof_sha256=proof_digest(proof),
        source_kind="official_document", result="no_debit", reason_code="provider_cancelled", expires_at=1000)
    ciphertext = encrypt_proof(proof, context=context, key_version="v1", key=b"K" * 64)
    assert decrypt_proof(ciphertext, context=context, key_version="v1", key=b"K" * 64) == proof
    baseline = review_token(context, "synthetic-secret")
    for changed in (replace(context, session_digest=session_digest("session-b", 1, 2)),
                    replace(context, actor_epoch=3), replace(context, receipt_id=4),
                    replace(context, target_context_sha256="d" * 64),
                    replace(context, event_snapshot_sha256="e" * 64),
                    replace(context, proof_sha256="f" * 64)):
        assert review_token(changed, "synthetic-secret") != baseline
    with pytest.raises(ClickReviewError):
        decrypt_proof(ciphertext, context=replace(context, event_snapshot_sha256="e" * 64), key_version="v1", key=b"K" * 64)
    with pytest.raises(ClickReviewError):
        decrypt_proof(ciphertext, context=context, key_version="v2", key=b"X" * 64)
    with pytest.raises(ClickReviewError):
        proof_digest(b"synthetic screenshot bytes")
    with pytest.raises(ClickReviewError):
        session_digest(None, 1, 2)


def test_review_graph_rejects_unmatched_legacy_tampering_and_stale_targets():
    import hashlib
    import json
    from dataclasses import replace

    from app.services.click_reconciliation_review import (
        ClickReviewError,
        ReviewGraph,
        provider_reference_digest,
        verify_review_graph,
    )

    public_id = "550e8400-e29b-41d4-a716-446655440000"
    order = f"invoice_1_{public_id}"
    merchant = hashlib.sha256(json.dumps(["click", "merchant", "100"], separators=(",", ":")).encode()).hexdigest()
    reference = provider_reference_digest("100", "123", order, "6")
    graph = ReviewGraph(receipt_id=1, receipt_phase="complete", receipt_confidence="authenticated",
        receipt_event_key="a" * 64, raw_receipt_sha256="b" * 64, event_id=2, event_provider="click",
        event_source="webhook", event_phase="complete", event_status="needs_review", event_key="a" * 64,
        event_raw_sha256="b" * 64, event_reference_sha256=reference, event_transaction_id="123",
        event_target_kind="payment_invoice", event_live_target_id=1, event_target_id_snapshot=1,
        event_amount_minor="1200", event_currency="UZS", link_receipt_id=1, link_event_id=2,
        issued_id=3, issued_attempt_id=4, issued_order=order, issued_merchant_hash=merchant,
        issued_amount_minor="1200", issued_currency="UZS", prepare_id=6,
        prepare_receipt_id=7, prepare_bound_receipt_id=7, prepare_receipt_confidence="authenticated", prepare_receipt_action=0,
        prepare_receipt_transaction_id="123", prepare_receipt_service_id="100", prepare_receipt_order=order,
        prepare_receipt_amount_minor="1200", prepare_attempt_id=4,
        prepare_transaction_id="123", prepare_service_id="100", prepare_order=order,
        prepare_merchant_hash=merchant, prepare_amount_minor="1200", complete_transaction_id="123",
        complete_service_id="100", complete_order=order, complete_prepare_ref="6", complete_amount_minor="1200",
        attempt_id=4, attempt_public_id=public_id, attempt_status="dispatching", attempt_target_kind="payment_invoice",
        attempt_live_target_id=1, attempt_target_id_snapshot=1, confirmed_merchant_id="merchant")
    verify_review_graph(graph)
    for changes in ({"receipt_confidence": "probable"}, {"link_event_id": 9}, {"event_raw_sha256": "c" * 64},
                    {"event_target_kind": "unmatched"}, {"event_live_target_id": None},
                    {"complete_prepare_ref": "7"}, {"complete_amount_minor": "1201"},
                    {"prepare_receipt_confidence": "probable"}, {"prepare_bound_receipt_id": 8},
                    {"prepare_transaction_id": "124"}, {"confirmed_merchant_id": "other"},
                    {"attempt_public_id": "legacy"}, {"attempt_status": "prepared"},
                    {"event_reference_sha256": "d" * 64}):
        with pytest.raises(ClickReviewError):
            verify_review_graph(replace(graph, **changes))
