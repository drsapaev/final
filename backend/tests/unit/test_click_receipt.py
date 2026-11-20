"""Synthetic in-process receipts: no provider or live database calls."""
import importlib.util
import json
from pathlib import Path
from urllib.parse import urlencode

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models.click_callback_receipt import (
    ClickCallbackReceipt,
    ClickReceiptKeyVersion,
)
from app.services.click_receipt_service import (
    ClickReceiptError,
    ClickReceiptService,
    receipt_key_commitment,
)

KEY_A = b"A" * 64  # Synthetic test material only.
KEY_B = b"B" * 64
SECRET = "SYNTHETIC_SECRET"


@pytest.fixture
def database():
    engine = create_engine("sqlite:///:memory:")
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0119_click_receipt.py"
    spec = importlib.util.spec_from_file_location("test_0119_click_receipt", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as conn:
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
    with Session(engine) as db:
        db.add_all([ClickReceiptKeyVersion(version="v1", commitment=receipt_key_commitment(KEY_A)),
                    ClickReceiptKeyVersion(version="v2", commitment=receipt_key_commitment(KEY_B))])
        db.commit()
        yield db
    engine.dispose()


def callback(*, action="1", amount="23.45", error="0", note="Success"):
    # Fixed Shop API vectors for the synthetic fields below.
    signatures = {
        ("0", "23.45"): "77516c8d659dde2301eaa3a07fc3134a",
        ("1", "23.45"): "25a20b004ef4db7d83ac6723e4c68bcf",
        ("1", "0.001"): "956bda03646beeb77f507c5f0041e17c",
    }
    fields = {"click_trans_id": "12345", "service_id": "100", "click_paydoc_id": "42",
              "merchant_trans_id": "invoice_1", "amount": amount, "action": action,
              "error": error, "error_note": note, "sign_time": "2026-11-17 12:01:00",
              "sign_string": signatures[action, amount]}
    if action == "1":
        fields["merchant_prepare_id"] = "77"
    return urlencode(fields).encode()


def store(db, body, *, ring=None, version="v1"):
    service = ClickReceiptService(db, keyring=ring or {"v1": KEY_A, "v2": KEY_B}, active_version=version)
    return service.store(body=body, content_type="application/x-www-form-urlencoded", service_id="100", secret_key=SECRET)


def test_receipt_encrypted_and_idempotent_after_commit(database):
    body = callback()
    first = store(database, body)
    again = store(database, body)
    assert first.created and not again.created and first.id == again.id
    with database.begin():
        row = database.get(ClickCallbackReceipt, first.id)
        assert body not in row.ciphertext
        assert b"SYNTHETIC_SECRET" not in row.ciphertext
        assert ClickReceiptService(database, keyring={"v1": KEY_A}, active_version="v1")._decrypt(row) == body


def test_different_phase_and_unsigned_conflict_are_preserved(database):
    first = store(database, callback())
    conflict = store(database, callback(error="-9", note="Changed"))
    prepared = store(database, callback(action="0"))
    assert len({first.id, conflict.id, prepared.id}) == 3
    with database.begin():
        rows = database.query(ClickCallbackReceipt).order_by(ClickCallbackReceipt.id).all()
        assert [row.variant_slot for row in rows] == [0, 1, 0]
        assert [row.phase for row in rows] == ["complete", "complete", "prepare"]


def test_key_rotation_requires_retaining_previous_version(database):
    first = store(database, callback(), version="v1")
    second = store(database, callback(error="-9"), version="v2")
    assert first.id != second.id
    with pytest.raises(ClickReceiptError, match="key unavailable"):
        store(database, callback(), ring={"v2": KEY_B}, version="v2")
    assert store(database, callback(), version="v2").id == first.id


def test_wrong_key_and_invalid_signature_do_not_create_receipt(database):
    with pytest.raises(ClickReceiptError, match="key unavailable"):
        store(database, callback(), ring={"v1": b"C" * 64})
    with pytest.raises(ValueError):
        store(database, callback().replace(b"amount=23.45", b"amount=23.46"))
    with database.begin():
        assert database.query(ClickCallbackReceipt).count() == 0


def test_unrepresentable_signed_amount_is_retained_exactly(database):
    body = callback(amount="0.001")
    result = store(database, body)
    with database.begin():
        row = database.get(ClickCallbackReceipt, result.id)
        assert ClickReceiptService(database, keyring={"v1": KEY_A}, active_version="v1")._decrypt(row) == body


def test_ambiguous_json_coercion_is_retained_as_probable_only(database):
    # Decode first: sign_time's form encoding is not JSON content.
    from urllib.parse import parse_qsl

    fields = dict(parse_qsl(callback().decode()))
    body = json.dumps(fields).replace('"amount": "23.45"', '"amount": 23.450').encode()
    service = ClickReceiptService(database, keyring={"v1": KEY_A}, active_version="v1")
    result = service.store(body=body, content_type="application/json", service_id="100", secret_key=SECRET)
    assert result.confidence == "probable"
    with database.begin():
        row = database.get(ClickCallbackReceipt, result.id)
        assert service._decrypt(row) == body


def test_ciphertext_and_metadata_tamper_are_detected(database):
    result = store(database, callback())
    service = ClickReceiptService(database, keyring={"v1": KEY_A}, active_version="v1")
    with database.begin():
        row = database.get(ClickCallbackReceipt, result.id)
        original = row.ciphertext
        row.ciphertext = bytes([original[0] ^ 1]) + original[1:]
        with pytest.raises(ClickReceiptError, match="integrity unavailable"):
            service._decrypt(row)
        database.expire(row, ["ciphertext"])
        row.phase = "prepare"
        with pytest.raises(ClickReceiptError, match="integrity unavailable"):
            service._decrypt(row)
        database.expire(row, ["phase"])


def test_history_is_immutable_and_failed_downgrade_preserves_it(database):
    store(database, callback())
    with pytest.raises(DBAPIError):
        database.execute(text("DELETE FROM click_callback_receipts"))
    database.rollback()
    with pytest.raises(DBAPIError):
        database.execute(text("UPDATE click_receipt_key_versions SET commitment='x' WHERE version='v1'"))
    database.rollback()
    with database.begin():
        path = Path(__file__).resolve().parents[2] / "alembic/versions/0119_click_receipt.py"
        spec = importlib.util.spec_from_file_location("test_0119_downgrade", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        migration.op = Operations(MigrationContext.configure(database.connection()))
        with pytest.raises(DBAPIError), database.begin_nested():
            migration.downgrade()
        assert database.query(ClickCallbackReceipt).count() == 1


def test_commit_failure_never_returns_a_receipt(database):
    def reject_commit(session):
        raise RuntimeError("synthetic commit failure")

    event.listen(database, "before_commit", reject_commit)
    try:
        with pytest.raises(RuntimeError, match="synthetic commit failure"):
            store(database, callback())
    finally:
        event.remove(database, "before_commit", reject_commit)
    assert not database.in_transaction()
    with database.begin():
        assert database.query(ClickCallbackReceipt).count() == 0


def test_variant_overflow_never_returns_success(database):
    for i in range(32):
        store(database, callback(note=f"variant {i}"))
    with pytest.raises(ClickReceiptError, match="operator reconciliation"):
        store(database, callback(note="variant 32"))
    assert not store(database, callback(note="variant 0")).created


def test_empty_sqlite_upgrade_downgrade_reupgrade():
    engine = create_engine("sqlite:///:memory:")
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0119_click_receipt.py"
    spec = importlib.util.spec_from_file_location("test_0119_empty", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    try:
        with engine.begin() as conn:
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            migration.downgrade()
            migration.upgrade()
            assert conn.execute(text("SELECT count(*) FROM click_callback_receipts")).scalar_one() == 0
    finally:
        engine.dispose()
