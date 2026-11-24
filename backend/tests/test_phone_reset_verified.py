"""Password-reset identity is bound to one verified, live phone owner."""
from __future__ import annotations

import asyncio
import threading
import time
from uuid import uuid4

import pytest

from app.models.authentication import PasswordResetToken
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.password_reset_service import _PHONE_RESET_TASKS, PasswordResetService

PHONE = "+998901023456"


async def drain_dispatches():
    if _PHONE_RESET_TASKS:
        await asyncio.gather(*tuple(_PHONE_RESET_TASKS))


def add_owner(db, *, verified: bool, active: bool = True, phone: str = PHONE):
    user = User(
        username="SYNTHETIC_" + uuid4().hex,
        hashed_password="SYNTHETIC_NO_LOGIN",
        role="Patient",
        is_active=active,
        is_superuser=False,
    )
    db.add(user)
    db.flush()
    db.add(UserProfile(user_id=user.id, phone=phone, phone_verified=verified))
    db.commit()
    return user.id


class FakePhoneVerification:
    def __init__(self):
        self.sent = []
        self.binding = None
        self.verify_thread = None

    async def send_verification_code(self, **kwargs):
        self.sent.append(kwargs)
        self.binding = kwargs["account_binding"]
        return {"success": True}

    def verify_code(self, **kwargs):
        self.verify_thread = threading.get_ident()
        if not self.binding:
            return {"success": False, "error": "Code unavailable", "error_code": "CODE_NOT_FOUND"}
        binding, self.binding = self.binding, None
        return {"success": True, "account_binding": binding, "expires_monotonic": time.monotonic() + 300}


@pytest.mark.asyncio
async def test_unverified_phone_never_receives_reset_code(db_session):
    add_owner(db_session, verified=False)
    service = PasswordResetService()
    service.phone_verification = FakePhoneVerification()
    result = await service.initiate_phone_reset(db_session, PHONE)
    await drain_dispatches()
    assert result["success"] is True
    assert service.phone_verification.sent == []


@pytest.mark.asyncio
async def test_store_failure_has_same_generic_response_without_exception_content(db_session, caplog):
    add_owner(db_session, verified=True)
    service = PasswordResetService()

    class Unavailable:
        async def send_verification_code(self, **kwargs):
            raise RuntimeError("SYNTHETIC_SENSITIVE_ERROR")

    service.phone_verification = Unavailable()
    unknown = await service.initiate_phone_reset(db_session, "+998901023457")
    failed = await service.initiate_phone_reset(db_session, PHONE)
    await drain_dispatches()
    assert unknown == failed
    assert "SYNTHETIC_SENSITIVE_ERROR" not in caplog.text


@pytest.mark.asyncio
async def test_known_and_unknown_return_before_delayed_sms_completes(db_session):
    add_owner(db_session, verified=True)
    service = PasswordResetService()
    entered, release = asyncio.Event(), asyncio.Event()

    class SlowTransport:
        async def send_verification_code(self, **kwargs):
            entered.set()
            await release.wait()
            return {"success": True}

    service.phone_verification = SlowTransport()
    try:
        unknown = await asyncio.wait_for(service.initiate_phone_reset(db_session, "+998901023457"), 2)
        known = await asyncio.wait_for(service.initiate_phone_reset(db_session, PHONE), 2)
        await asyncio.wait_for(entered.wait(), 2)
        assert known == unknown
        assert not release.is_set()
    finally:
        release.set()
        await drain_dispatches()


@pytest.mark.asyncio
async def test_epoch_changed_during_delivery_cannot_authorize_reset(db_session):
    user_id = add_owner(db_session, verified=True)
    service = PasswordResetService()
    entered, release = asyncio.Event(), asyncio.Event()

    class SlowVerification(FakePhoneVerification):
        async def send_verification_code(self, **kwargs):
            entered.set()
            await release.wait()
            return await super().send_verification_code(**kwargs)

    service.phone_verification = SlowVerification()
    try:
        await service.initiate_phone_reset(db_session, PHONE)
        await asyncio.wait_for(entered.wait(), 2)
        db_session.query(User).filter_by(id=user_id).update({"auth_epoch": 1})
        db_session.commit()
    finally:
        release.set()
        await drain_dispatches()
    assert service.phone_verification.binding == (user_id, 0)
    result = await service.verify_phone_and_get_token(db_session, PHONE, "SYNTHETIC")
    assert result["error_code"] == "CODE_NOT_FOUND"
    assert db_session.query(PasswordResetToken).filter_by(user_id=user_id).count() == 0


@pytest.mark.asyncio
async def test_dispatch_queue_is_bounded_and_returns_generic_response(db_session, monkeypatch):
    from app.services import password_reset_service

    add_owner(db_session, verified=True)
    service = PasswordResetService()
    entered, release = asyncio.Event(), asyncio.Event()

    class SlowTransport:
        async def send_verification_code(self, **kwargs):
            entered.set()
            await release.wait()
            return {"success": True}

    service.phone_verification = SlowTransport()
    monkeypatch.setattr(password_reset_service, "_PHONE_RESET_MAX_PENDING", 1)
    try:
        first = await service.initiate_phone_reset(db_session, PHONE)
        await asyncio.wait_for(entered.wait(), 2)
        known = await service.initiate_phone_reset(db_session, PHONE)
        unknown = await service.initiate_phone_reset(db_session, "+998901023457")
        assert first == known == unknown
        assert len(_PHONE_RESET_TASKS) == 1
    finally:
        release.set()
        await drain_dispatches()


@pytest.mark.asyncio
async def test_database_phone_scan_does_not_block_event_loop(db_session, monkeypatch):
    service = PasswordResetService()
    entered, release = threading.Event(), threading.Event()

    def slow_scan(db, phone):
        entered.set()
        assert release.wait(3)
        return None

    monkeypatch.setattr(service, "_unique_verified_phone_binding", slow_scan)
    timer = threading.Timer(1, release.set)
    timer.start()
    try:
        task = asyncio.create_task(service.initiate_phone_reset(db_session, PHONE))
        assert await asyncio.to_thread(entered.wait, 2)
        await asyncio.sleep(.01)
        assert not task.done()
        release.set()
        assert (await task)["success"]
        await drain_dispatches()
    finally:
        release.set()
        timer.cancel()


@pytest.mark.asyncio
@pytest.mark.parametrize("second_active", [True, False])
async def test_verified_duplicate_is_rejected_even_when_other_account_inactive(db_session, second_active):
    add_owner(db_session, verified=True)
    add_owner(db_session, verified=True, active=second_active)
    service = PasswordResetService()
    service.phone_verification = FakePhoneVerification()
    result = await service.initiate_phone_reset(db_session, PHONE)
    await drain_dispatches()
    assert result["success"] is True
    assert service.phone_verification.sent == []


@pytest.mark.asyncio
async def test_unique_verified_owner_receives_one_use_reset_token(db_session):
    user_id = add_owner(db_session, verified=True)
    service = PasswordResetService()
    service.phone_verification = FakePhoneVerification()
    assert (await service.initiate_phone_reset(db_session, PHONE))["success"]
    await drain_dispatches()
    assert service.phone_verification.sent[0]["account_binding"] == (user_id, 0)
    caller_thread = threading.get_ident()
    result = await service.verify_phone_and_get_token(db_session, PHONE, "SYNTHETIC")
    assert result["success"] and result["reset_token"]
    assert service.phone_verification.verify_thread != caller_thread
    assert db_session.query(PasswordResetToken).filter_by(user_id=user_id, used=False).count() == 1
    assert not (await service.verify_phone_and_get_token(db_session, PHONE, "SYNTHETIC"))["success"]


@pytest.mark.asyncio
@pytest.mark.parametrize("formatted", [
    "+998 (90) 102-34-56", "+998.90.102.34.56", "+ 9 9 8 901023456",
    "+٩٩٨٩٠١٠٢٣٤٥٦", "+９９８９０１０２３４５６",
])
async def test_formatted_legacy_owner_is_resolved_and_rechecked(db_session, formatted):
    user_id = add_owner(db_session, verified=True, phone=formatted)
    service = PasswordResetService()
    service.phone_verification = FakePhoneVerification()
    assert (await service.initiate_phone_reset(db_session, PHONE))["success"]
    await drain_dispatches()
    assert service.phone_verification.sent[0]["account_binding"] == (user_id, 0)
    assert (await service.verify_phone_and_get_token(db_session, PHONE, "SYNTHETIC"))["success"]


@pytest.mark.asyncio
@pytest.mark.parametrize("formatted", ["+998 (90) 102-34-56", "+ 9 9 8 901023456", "+٩٩٨٩٠١٠٢٣٤٥٦"])
async def test_formatted_legacy_duplicate_fails_closed(db_session, formatted):
    add_owner(db_session, verified=True)
    add_owner(db_session, verified=True, phone=formatted)
    service = PasswordResetService()
    service.phone_verification = FakePhoneVerification()
    assert (await service.initiate_phone_reset(db_session, PHONE))["success"]
    await drain_dispatches()
    assert not service.phone_verification.sent


@pytest.mark.asyncio
async def test_unicode_phone_input_is_generic_and_not_sent(db_session):
    add_owner(db_session, verified=True)
    service = PasswordResetService()
    service.phone_verification = FakePhoneVerification()
    assert (await service.initiate_phone_reset(db_session, "+998٩٠١٠٢٣٤٥٦"))["success"]
    await drain_dispatches()
    assert not service.phone_verification.sent
    result = await service.verify_phone_and_get_token(db_session, "+998٩٠١٠٢٣٤٥٦", "SYNTHETIC")
    assert result["error_code"] == "CODE_NOT_FOUND"


def test_candidate_scan_cap_is_fail_closed(db_session, monkeypatch):
    from app.services import patient_phone_scope

    # Two non-ASCII but nonmatching profiles both pass the broad safe SQL
    # prefilter; a truncated scan must never be interpreted as uniqueness.
    add_owner(db_session, verified=True, phone="+٩٩٨٩٠١٠٢٣٤٥٧")
    add_owner(db_session, verified=True, phone="+٩٩٨٩٠١٠٢٣٤٥٨")
    monkeypatch.setattr(patient_phone_scope, "_VERIFIED_PHONE_SCAN_LIMIT", 1)
    assert patient_phone_scope.verified_phone_candidates(db_session, PHONE) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["unverify", "deactivate", "epoch", "duplicate"])
async def test_stale_or_ambiguous_proof_does_not_issue_token(db_session, mutation):
    user_id = add_owner(db_session, verified=True)
    service = PasswordResetService()
    service.phone_verification = FakePhoneVerification()
    await service.initiate_phone_reset(db_session, PHONE)
    await drain_dispatches()
    user = db_session.get(User, user_id)
    profile = db_session.query(UserProfile).filter_by(user_id=user_id).one()
    if mutation == "unverify":
        profile.phone_verified = False
    elif mutation == "deactivate":
        user.is_active = False
    elif mutation == "epoch":
        user.auth_epoch += 1
    else:
        add_owner(db_session, verified=True)
    db_session.commit()
    result = await service.verify_phone_and_get_token(db_session, PHONE, "SYNTHETIC")
    assert not result["success"]
    assert result["error_code"] == "CODE_NOT_FOUND"
    assert db_session.query(PasswordResetToken).filter_by(user_id=user_id, used=False).count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("deadline", [None, True, float("nan"), float("inf"), -1, 10**1000])
async def test_malformed_or_expired_proof_deadline_never_issues_token(db_session, deadline):
    user_id = add_owner(db_session, verified=True)
    service = PasswordResetService()

    class InvalidProof:
        def verify_code(self, **kwargs):
            return {"success": True, "account_binding": (user_id, 0), "expires_monotonic": deadline}

    service.phone_verification = InvalidProof()
    result = await service.verify_phone_and_get_token(db_session, PHONE, "SYNTHETIC")
    assert result["error_code"] == "CODE_NOT_FOUND"
    assert db_session.query(PasswordResetToken).filter_by(user_id=user_id).count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("proof_live", [True, False])
async def test_worker_wall_clock_skew_does_not_determine_proof_validity(db_session, proof_live):
    user_id = add_owner(db_session, verified=True)
    service = PasswordResetService()

    class SkewedClockProof:
        def verify_code(self, **kwargs):
            return {
                "success": True,
                "account_binding": (user_id, 0),
                # Emulate the sending worker's wall clock being very far
                # behind or ahead. Only the local consumed TTL matters.
                "expires_at": 1 if proof_live else time.time() + 10**6,
                "expires_monotonic": time.monotonic() + (60 if proof_live else -1),
            }

    service.phone_verification = SkewedClockProof()
    result = await service.verify_phone_and_get_token(db_session, PHONE, "SYNTHETIC")
    assert result["success"] is proof_live
    assert db_session.query(PasswordResetToken).filter_by(user_id=user_id).count() == int(proof_live)


@pytest.mark.asyncio
async def test_bearer_is_not_returned_when_commit_outlasts_proof(db_session, monkeypatch):
    user_id = add_owner(db_session, verified=True)
    service = PasswordResetService()
    deadline = time.monotonic() + 1.5

    class ShortProof:
        def verify_code(self, **kwargs):
            return {"success": True, "account_binding": (user_id, 0), "expires_monotonic": deadline}

    service.phone_verification = ShortProof()
    original_commit = db_session.commit
    commits = 0

    def delayed_commit():
        nonlocal commits
        commits += 1
        original_commit()
        if commits == 2:
            while time.monotonic() <= deadline:
                time.sleep(.02)

    monkeypatch.setattr(db_session, "commit", delayed_commit)
    result = await service.verify_phone_and_get_token(db_session, PHONE, "SYNTHETIC")
    assert commits == 2
    assert result["error_code"] == "CODE_NOT_FOUND"
    assert "reset_token" not in result
