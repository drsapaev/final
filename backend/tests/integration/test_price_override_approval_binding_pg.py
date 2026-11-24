"""Synthetic PG barrier tests for the temporary review boundary."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.models.authentication import TokenBlacklist
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.user import User
from app.models.visit import VisitService
from app.services.price_override_approval import (
    PriceOverrideApprovalError,
    PriceOverrideApprovalService,
)
from app.services.profile_contact_security import ProfileBearerContext
from tests.integration.test_price_override_request_binding_pg import (  # noqa: F401
    _is_blocked,
    _issue,
    pg_case,
)


@pytest.fixture
def review_case(pg_case):
    engine, ids = pg_case
    status, override_id = _issue(engine, ids)
    assert status == 200
    with Session(engine, expire_on_commit=False) as db:
        actor = User(username="synthetic_reviewer", hashed_password="!", role="Registrar", is_active=True)
        db.add(actor)
        db.flush()
        ids = {**ids, "actor": actor.id, "override": override_id}
        db.commit()
    return engine, ids


def _review(engine, ids, action="approve", ready=None, pids=None):
    with Session(engine, expire_on_commit=False) as db:
        if ready:
            pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            ready.set()
        bearer = ProfileBearerContext(ids["actor"], 0, "review-jti", int(time.time()) + 60, None)
        try:
            row = PriceOverrideApprovalService(db).process(
                override_id=ids["override"], action=action,
                rejection_reason="Synthetic refusal", approver_id=ids["actor"], bearer=bearer,
            )
            return 200, row.status
        except PriceOverrideApprovalError as exc:
            return exc.status_code, None


def test_child_delete_cannot_deadlock_rejection(review_case):
    engine, ids = review_case
    locked, release, writer_done, pids = threading.Event(), threading.Event(), threading.Event(), []
    reviewer_thread = []

    def pause_after_visit(_conn, _cursor, statement, _parameters, _context, _many):
        if threading.get_ident() in reviewer_thread and "from visits" in statement.lower() and "for update" in statement.lower():
            locked.set()
            if not release.wait(10):
                raise AssertionError("review release timeout")

    def review():
        reviewer_thread.append(threading.get_ident())
        with Session(engine, expire_on_commit=False) as db:
            bearer = ProfileBearerContext(ids["actor"], 0, "review-jti", int(time.time()) + 60, None)
            service = PriceOverrideApprovalService(db)
            with pytest.raises(PriceOverrideApprovalError) as error:
                service.process(override_id=ids["override"], action="reject", rejection_reason="Synthetic refusal",
                                approver_id=ids["actor"], bearer=bearer)
            if not writer_done.wait(10):
                raise AssertionError("writer completion timeout")
            retried = service.process(override_id=ids["override"], action="reject", rejection_reason="Synthetic refusal",
                                      approver_id=ids["actor"], bearer=bearer)
            return error.value.status_code, retried.status

    def delete(ready):
        with Session(engine) as db:
            pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            ready.set()
            db.delete(db.get(VisitService, ids["line"]))
            db.commit()

    event.listen(engine, "after_cursor_execute", pause_after_visit)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            reviewer = pool.submit(review)
            assert locked.wait(5)
            ready = threading.Event()
            writer = pool.submit(delete, ready)
            try:
                assert ready.wait(5)
                assert _is_blocked(engine, pids[0])
            finally:
                release.set()
            try:
                writer.result(timeout=12)
            finally:
                writer_done.set()
            assert reviewer.result(timeout=12) == (409, "rejected")
    finally:
        release.set()
        writer_done.set()
        event.remove(engine, "after_cursor_execute", pause_after_visit)
    with Session(engine) as db:
        assert db.get(DoctorPriceOverride, ids["override"]).status == "rejected"


def test_concurrent_rejections_have_one_winner(review_case):
    engine, ids = review_case
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(_review, engine, ids, "reject")
        second = pool.submit(_review, engine, ids, "reject")
        assert sorted([first.result(timeout=12)[0], second.result(timeout=12)[0]]) == [200, 409]
    with Session(engine) as db:
        assert db.get(DoctorPriceOverride, ids["override"]).status == "rejected"


def test_logout_preceding_locked_review_is_rechecked(review_case):
    engine, ids = review_case
    ready, pids = threading.Event(), []
    with Session(engine) as logout:
        logout.query(User).filter_by(id=ids["actor"]).with_for_update().one()
        logout.add(TokenBlacklist(jti="review-jti", user_id=ids["actor"],
                                  expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
        logout.flush()
        with ThreadPoolExecutor(max_workers=1) as pool:
            review = pool.submit(_review, engine, ids, "reject", ready, pids)
            try:
                assert ready.wait(5)
                assert _is_blocked(engine, pids[0])
            finally:
                logout.commit()
            assert review.result(timeout=12)[0] == 401
    with Session(engine) as db:
        assert db.get(DoctorPriceOverride, ids["override"]).status == "pending"


@pytest.mark.parametrize("change,expected", [("inactive", 401), ("role", 403), ("epoch", 401)])
def test_actor_changes_preceding_locked_review_are_rechecked(review_case, change, expected):
    engine, ids = review_case
    ready, pids = threading.Event(), []
    with Session(engine) as editor:
        user = editor.get(User, ids["actor"])
        if change == "inactive":
            user.is_active = False
        elif change == "role":
            user.role = "Patient"
        else:
            user.auth_epoch = 1
        editor.flush()
        with ThreadPoolExecutor(max_workers=1) as pool:
            review = pool.submit(_review, engine, ids, "reject", ready, pids)
            try:
                assert ready.wait(5)
                assert _is_blocked(engine, pids[0])
            finally:
                editor.commit()
            assert review.result(timeout=12)[0] == expected
    with Session(engine) as db:
        assert db.get(DoctorPriceOverride, ids["override"]).status == "pending"
