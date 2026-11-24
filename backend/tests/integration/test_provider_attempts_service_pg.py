"""Synthetic PostgreSQL reservation races; no provider calls are made."""
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.models.authentication import TokenBlacklist
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.provider_attempt import ProviderActiveVisitReservation, ProviderAttempt
from app.models.user import User
from app.models.visit import Visit
from app.services.profile_contact_security import ProfileBearerContext
from app.services.provider_attempt_service import (
    ProviderAttemptError,
    ProviderAttemptService,
)
from tests.integration.test_price_override_request_binding_pg import (  # noqa: F401
    _is_blocked,
    pg_case,
)
from tests.unit.test_provider_attempts_service import FakeManager


@pytest.fixture
def attempt_case(pg_case):
    engine, ids = pg_case
    with Session(engine, expire_on_commit=False) as db:
        actor = User(username="synthetic_attempt_actor", hashed_password="!", role="Registrar", is_active=True)
        other = User(username="synthetic_attempt_other", hashed_password="!", role="Registrar", is_active=True)
        payment = Payment(visit_id=ids["visit"], amount=Decimal("1.15"), currency="UZS", method="online", status="pending", provider="click")
        alternate = Payment(visit_id=ids["visit"], amount=Decimal("1.15"), currency="UZS", method="online", status="pending", provider="payme")
        db.add_all([actor, other, payment, alternate])
        db.flush()
        ids = {**ids, "actor": actor.id, "other": other.id, "payment": payment.id, "alternate": alternate.id}
        db.commit()
    return engine, ids


def _reserve(engine, ids, *, actor=None, alternate=False, ready=None, pids=None, jti=None):
    with Session(engine, expire_on_commit=False) as db:
        if ready is not None:
            pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            ready.set()
        actor_id = actor or ids["actor"]
        bearer = ProfileBearerContext(actor_id, 0, jti, None, None)
        try:
            result = ProviderAttemptService(db, FakeManager()).reserve(
                bearer=bearer, target_kind="payment", target_id=ids["alternate"] if alternate else ids["payment"],
                provider="payme" if alternate else "click", currency="UZS", amount=Decimal("1.15"),
            )
            db.commit()
            return 200, result.public_id, result.created
        except ProviderAttemptError as exc:
            return exc.status_code, None, False


@pytest.mark.parametrize("competing", ["same", "other_provider"])
def test_reservations_serialize_and_replay_once(attempt_case, competing):
    engine, ids = attempt_case
    locked, release, pids, thread_ids = threading.Event(), threading.Event(), [], []

    def pause_after_visit(_conn, _cursor, statement, _params, _context, _many):
        if (threading.get_ident() in thread_ids and "from visits" in statement.lower()
            and "for update" in statement.lower() and not locked.is_set()):
            locked.set()
            if not release.wait(10):
                raise AssertionError("release timeout")

    def first():
        thread_ids.append(threading.get_ident())
        return _reserve(engine, ids)

    event.listen(engine, "after_cursor_execute", pause_after_visit)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(first)
            assert locked.wait(5)
            ready = threading.Event()
            b = pool.submit(_reserve, engine, ids, actor=ids["other"] if competing == "other_provider" else None,
                            alternate=competing == "other_provider", ready=ready, pids=pids)
            try:
                assert ready.wait(5)
                assert _is_blocked(engine, pids[0])
            finally:
                release.set()
            first_result, second_result = a.result(timeout=12), b.result(timeout=12)
        assert first_result[0] == 200 and first_result[2]
        if competing == "same":
            assert second_result == (200, first_result[1], False)
        else:
            assert second_result[0] == 409
        with Session(engine) as db:
            assert db.query(ProviderAttempt).count() == 1
            assert db.query(ProviderActiveVisitReservation).count() == 1
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", pause_after_visit)


def test_atomic_commit_failure_leaves_no_reservation(attempt_case, monkeypatch):
    engine, ids = attempt_case
    with Session(engine) as db:
        service = ProviderAttemptService(db, FakeManager())
        monkeypatch.setattr(db, "commit", lambda: (_ for _ in ()).throw(RuntimeError("synthetic failure")))
        with pytest.raises(RuntimeError, match="synthetic failure"):
            service.reserve(bearer=ProfileBearerContext(ids["actor"], 0, None, None, None),
                            target_kind="payment", target_id=ids["payment"], provider="click",
                            currency="UZS", amount=Decimal("1.15"))
            db.commit()
        db.rollback()
    with Session(engine) as db:
        assert db.query(ProviderAttempt).count() == 0
        assert db.query(ProviderActiveVisitReservation).count() == 0


def test_target_row_conflict_fails_fast_then_can_retry(attempt_case):
    engine, ids = attempt_case
    with Session(engine) as editor:
        editor.query(Payment).filter_by(id=ids["payment"]).with_for_update().one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(_reserve, engine, ids).result(timeout=8)[0] == 409
        editor.rollback()
    assert _reserve(engine, ids)[0] == 200


@pytest.mark.parametrize("change,expected", [("inactive", 401), ("role", 403), ("epoch", 401)])
def test_actor_rechecked_under_lock(attempt_case, change, expected):
    engine, ids = attempt_case
    ready, pids = threading.Event(), []
    with Session(engine) as editor:
        actor = editor.get(User, ids["actor"])
        if change == "inactive":
            actor.is_active = False
        elif change == "role":
            actor.role = "Patient"
        else:
            actor.auth_epoch = 1
        editor.flush()
        with ThreadPoolExecutor(max_workers=1) as pool:
            attempt = pool.submit(_reserve, engine, ids, ready=ready, pids=pids)
            try:
                assert ready.wait(5)
                assert _is_blocked(engine, pids[0])
            finally:
                editor.commit()
            assert attempt.result(timeout=12)[0] == expected
    with Session(engine) as db:
        assert db.query(ProviderAttempt).count() == 0


def test_individual_token_revocation_wins_before_user_lock(attempt_case):
    engine, ids = attempt_case
    ready, pids = threading.Event(), []
    with Session(engine) as editor:
        editor.query(User).filter_by(id=ids["actor"]).with_for_update().one()
        editor.add(TokenBlacklist(jti="synthetic-attempt-jti", user_id=ids["actor"],
                                  expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
        editor.flush()
        with ThreadPoolExecutor(max_workers=1) as pool:
            attempt = pool.submit(_reserve, engine, ids, ready=ready, pids=pids, jti="synthetic-attempt-jti")
            try:
                assert ready.wait(5)
                assert _is_blocked(engine, pids[0])
            finally:
                editor.commit()
            assert attempt.result(timeout=12)[0] == 401
    with Session(engine) as db:
        assert db.query(ProviderAttempt).count() == 0


def test_unknown_transition_has_one_winner_without_releasing_visit(attempt_case):
    engine, ids = attempt_case
    status, public_id, _ = _reserve(engine, ids)
    assert status == 200
    with Session(engine) as db:
        attempt = db.query(ProviderAttempt).filter_by(public_id=public_id).one()
        attempt.status = "dispatching"
        db.commit()
    locked, release, pids, thread_ids = threading.Event(), threading.Event(), [], []

    def pause_after_attempt(_conn, _cursor, statement, _params, _context, _many):
        if (threading.get_ident() in thread_ids and "from provider_attempts" in statement.lower()
            and "for update" in statement.lower() and not locked.is_set()):
            locked.set()
            if not release.wait(10):
                raise AssertionError("release timeout")

    def mark(first, ready=None):
        if first:
            thread_ids.append(threading.get_ident())
        with Session(engine) as db:
            if ready:
                pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
                ready.set()
            result = ProviderAttemptService(db, FakeManager()).mark_unknown(public_id)
            db.commit()
            return result

    event.listen(engine, "after_cursor_execute", pause_after_attempt)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(mark, True)
            assert locked.wait(5)
            ready = threading.Event()
            second = pool.submit(mark, False, ready)
            try:
                assert ready.wait(5)
                assert _is_blocked(engine, pids[0])
            finally:
                release.set()
            assert (first.result(timeout=12), second.result(timeout=12)) == (True, False)
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", pause_after_attempt)
    with Session(engine) as db:
        assert db.query(ProviderAttempt).one().status == "unknown"
        assert db.query(ProviderActiveVisitReservation).count() == 1


def test_overlapping_group_invoices_cannot_reserve_same_visit(attempt_case):
    engine, ids = attempt_case
    with Session(engine, expire_on_commit=False) as db:
        first_visit = db.get(Visit, ids["visit"])
        second_visit = Visit(patient_id=first_visit.patient_id, visit_date=first_visit.visit_date,
                             status="open", source="desk", confirmation_context_epoch=33)
        db.add(second_visit)
        db.flush()
        first_invoice = PaymentInvoice(patient_id=first_visit.patient_id, total_amount=Decimal("1.15"), currency="UZS", status="pending")
        second_invoice = PaymentInvoice(patient_id=first_visit.patient_id, total_amount=Decimal("1.15"), currency="UZS", status="pending")
        db.add_all([first_invoice, second_invoice])
        db.flush()
        db.add_all([
            PaymentInvoiceVisit(invoice_id=first_invoice.id, visit_id=first_visit.id, visit_amount=Decimal("0.00")),
            PaymentInvoiceVisit(invoice_id=first_invoice.id, visit_id=second_visit.id, visit_amount=Decimal("1.15")),
            PaymentInvoiceVisit(invoice_id=second_invoice.id, visit_id=second_visit.id, visit_amount=Decimal("1.15")),
        ])
        first_id, second_id = first_invoice.id, second_invoice.id
        db.commit()
    locked, release, pids, thread_ids = threading.Event(), threading.Event(), [], []

    def pause_after_visits(_conn, _cursor, statement, _params, _context, _many):
        if (threading.get_ident() in thread_ids and "from visits" in statement.lower()
            and "for update" in statement.lower() and not locked.is_set()):
            locked.set()
            if not release.wait(10):
                raise AssertionError("release timeout")

    def reserve(invoice_id, actor, first=False, ready=None):
        if first:
            thread_ids.append(threading.get_ident())
        with Session(engine) as db:
            if ready:
                pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
                ready.set()
            try:
                result = ProviderAttemptService(db, FakeManager()).reserve(
                    bearer=ProfileBearerContext(actor, 0, None, None, None), target_kind="payment_invoice",
                    target_id=invoice_id, provider="click", currency="UZS", amount=Decimal("1.15"),
                )
                db.commit()
                return 200, result.public_id
            except ProviderAttemptError as exc:
                return exc.status_code, None

    event.listen(engine, "after_cursor_execute", pause_after_visits)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(reserve, first_id, ids["actor"], True)
            assert locked.wait(5)
            ready = threading.Event()
            second = pool.submit(reserve, second_id, ids["other"], False, ready)
            try:
                assert ready.wait(5)
                assert _is_blocked(engine, pids[0])
            finally:
                release.set()
            assert first.result(timeout=12)[0] == 200
            assert second.result(timeout=12)[0] == 409
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", pause_after_visits)
    with Session(engine) as db:
        assert db.query(ProviderActiveVisitReservation).count() == 2


def test_same_actor_key_cannot_race_across_different_visits(attempt_case):
    engine, ids = attempt_case
    with Session(engine, expire_on_commit=False) as db:
        source = db.get(Visit, ids["visit"])
        other_visit = Visit(patient_id=source.patient_id, visit_date=source.visit_date,
                            status="open", source="desk", confirmation_context_epoch=44)
        db.add(other_visit)
        db.flush()
        other_payment = Payment(visit_id=other_visit.id, amount=Decimal("1.15"), currency="UZS",
                                method="online", status="pending", provider="click")
        db.add(other_payment)
        db.flush()
        other_payment_id = other_payment.id
        db.commit()
    locked, release, pids, thread_ids = threading.Event(), threading.Event(), [], []

    def pause_after_user(_conn, _cursor, statement, _params, _context, _many):
        if (threading.get_ident() in thread_ids and "from users" in statement.lower()
            and "for update" in statement.lower() and not locked.is_set()):
            locked.set()
            if not release.wait(10):
                raise AssertionError("release timeout")

    def reserve(target_id, first=False, ready=None):
        if first:
            thread_ids.append(threading.get_ident())
        with Session(engine) as db:
            if ready:
                pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
                ready.set()
            try:
                ProviderAttemptService(db, FakeManager()).reserve(
                    bearer=ProfileBearerContext(ids["actor"], 0, None, None, None), target_kind="payment",
                    target_id=target_id, provider="click", currency="UZS", amount=Decimal("1.15"),
                    client_request_id="same-synthetic-key",
                )
                db.commit()
                return 200
            except ProviderAttemptError as exc:
                return exc.status_code

    event.listen(engine, "after_cursor_execute", pause_after_user)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(reserve, ids["payment"], True)
            assert locked.wait(5)
            ready = threading.Event()
            second = pool.submit(reserve, other_payment_id, False, ready)
            try:
                assert ready.wait(5)
                assert _is_blocked(engine, pids[0])
            finally:
                release.set()
            assert first.result(timeout=12) == 200
            assert second.result(timeout=12) == 409
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", pause_after_user)
    with Session(engine) as db:
        assert db.query(ProviderAttempt).count() == 1
