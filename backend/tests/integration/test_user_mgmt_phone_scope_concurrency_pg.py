"""Phase 0 PR-A2 — PostgreSQL User-Management concurrency serialization
proof (review round 4, P1).

The phone-scope invariant must be a TRANSACTIONAL invariant, not just a
sequential one. ``update_user()`` decides whether the phone-scope guard
arms from the state ITS transaction read (role / is_active /
phone_verified). Two PARALLEL partial mutations of the SAME record each
read the pre-mutation state under READ COMMITTED, each guard stays
disarmed, and the combined commit still creates a SECOND login-resolver
candidate — the permanent fail-closed OTP-login lockout:

    A = inactive Registrar, verified phone X
    B = active  Patient,   verified phone X

    T1: update_user(A, role=Patient)      # target inactive -> not armed
    T2: update_user(A, is_active=true)    # target Registrar -> not armed
    T1+T2 commit -> A = active + Patient + verified X  ->  2 candidates

Round-4 fix: candidate-defining state is serialized under ``FOR UPDATE``
(users row -> user_profiles row) BEFORE any decision is computed from
it, on every User Management path (single update, bulk, profile door).
One of the parallel operations must then SERIALIZE, see the new
effective state, and fail with the controlled ``PatientPhoneScopeConflict``
(409) — never both-succeed into two candidates.

Deterministic interleaving (same technique as
test_patient_activation_pg_phone_scope.py): an external connection holds
the users row of the target under ``FOR UPDATE`` (transaction stays open)
while both contender threads are released through a barrier; the test
waits until pg_locks shows BOTH contenders blocked on that row, then
releases the holder — the winner/loser order is forced through the
serialization point. The final assertions are order-independent.

Contract proven on real PostgreSQL:
    - parallel partial mutations can NEVER combine into a second active
      verified Patient-user candidate on the same phone;
    - exactly one contender succeeds, the loser fails with the
      controlled 409 conflict;
    - the bulk surface is serialized the same way (bulk activate vs a
      concurrent role -> Patient).

DSN discipline inherited from RQ-14.a.2 / the activation proof:
localhost-only candidates, verified before use, run-scoped scratch
database, CREATE-only, teardown in finally. Disposable local PostgreSQL
only; production/staging/Supabase are never touched. SQLite conftest
runs are NOT PG evidence. SYNTHETIC data only.
"""

from __future__ import annotations

import os
import threading
import time
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.core.roles import Roles
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.user_management import UserBulkActionRequest, UserUpdateRequest
from app.services.patient_phone_scope import (
    PatientPhoneScopeConflict,
    count_active_verified_patient_users,
)
from app.services.user_management_service import UserManagementService

_RUN = uuid.uuid4().hex[:8]
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
FAMILY_PHONE = "+998900000008"  # SYNTHETIC only (unused by other proofs)


def _candidate_admin_urls() -> list[str]:
    urls: list[str] = []
    explicit = os.getenv("PR_A2_PG_ADMIN_URL", "").strip()
    if explicit:
        urls.append(explicit)
    local_pw = os.getenv("LOCAL_PG_SUPERUSER_PASSWORD", "").strip()
    if local_pw:
        urls.append(f"postgresql://postgres:{local_pw}@localhost:5432/postgres")
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        from sqlalchemy.engine import make_url

        u = make_url(env_url)
        if (u.host or "") in _LOCAL_HOSTS:
            urls.append(
                f"postgresql://{u.username}:{u.password}@{u.host}:{u.port}/postgres"
            )
    return urls


def _verified_admin_url() -> str:
    from sqlalchemy.engine import make_url

    last_error: Exception | None = None
    import psycopg

    for candidate in _candidate_admin_urls():
        try:
            host = make_url(candidate).host or ""
            if host not in _LOCAL_HOSTS:
                last_error = RuntimeError("non-localhost admin DSN rejected")
                continue
            with psycopg.connect(candidate, connect_timeout=5, autocommit=True) as c:
                c.execute("SELECT 1")
            return candidate
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    pytest.skip(
        "disposable local PostgreSQL unavailable — User-Management "
        f"concurrency proof NOT_RUN (last reason: {type(last_error).__name__})"
    )


@pytest.fixture()
def pg_engine():
    from sqlalchemy.engine import make_url

    admin_url = _verified_admin_url()
    u = make_url(admin_url)
    db_name = f"pra2_umlock_{_RUN}"
    base = f"postgresql://{u.username}:{u.password}@{u.host}:{u.port}"
    scratch_url = f"{base}/{db_name}"

    import psycopg

    with psycopg.connect(admin_url, autocommit=True) as c:
        c.execute(f'CREATE DATABASE "{db_name}"')
    engine = create_engine(
        f"postgresql+psycopg://{u.username}:{u.password}@{u.host}:{u.port}/{db_name}",
        pool_pre_ping=True,
    )
    try:
        import app.models  # noqa: F401 - register all ORM tables
        from app.db.base_class import Base

        Base.metadata.create_all(engine)
        assert engine.dialect.name == "postgresql"
        yield engine
    finally:
        engine.dispose()
        with psycopg.connect(admin_url, autocommit=True) as c:
            c.execute(f'DROP DATABASE IF EXISTS "{db_name}"')


def _seed_scene(Session) -> tuple[int, int, int]:
    """A = inactive Registrar with a verified family phone X;
    B = active Patient-user, the ONLY candidate on X; plus an Admin actor.
    Returns (a_id, b_id, admin_id)."""
    seed = Session()
    suffix = _RUN[:6]
    admin = User(
        username=f"synthetic_admin_{suffix}",
        email=f"synthetic_admin_{suffix}@synthetic.local",
        full_name="SYNTHETIC Admin",
        hashed_password="argon2$synthetic",  # never verified here
        role="Admin",
        is_active=True,
        is_superuser=True,
    )
    a = User(
        username=f"synthetic_inactive_{suffix}",
        email=f"synthetic_inactive_{suffix}@synthetic.local",
        full_name="SYNTHETIC Inactive Registrar",
        hashed_password="argon2$synthetic",
        role=Roles.REGISTRAR,
        is_active=False,
        is_superuser=False,
    )
    b = User(
        username=f"synthetic_patient_{suffix}",
        email=f"synthetic_patient_{suffix}@synthetic.local",
        full_name="SYNTHETIC Active Patient",
        hashed_password="argon2$synthetic",
        role=Roles.PATIENT,
        is_active=True,
        is_superuser=False,
    )
    seed.add_all([admin, a, b])
    seed.flush()
    seed.add_all(
        [
            UserProfile(
                user_id=a.id,
                full_name="SYNTHETIC Inactive Registrar",
                phone=FAMILY_PHONE,
                phone_verified=True,
            ),
            UserProfile(
                user_id=b.id,
                full_name="SYNTHETIC Active Patient",
                phone=FAMILY_PHONE,
                phone_verified=True,
            ),
        ]
    )
    seed.commit()
    ids = (a.id, b.id, admin.id)
    seed.close()
    return ids


def _candidate_ids(check) -> list[int]:
    return (
        check.execute(
            select(User.id)
            .join(UserProfile, UserProfile.user_id == User.id)
            .where(
                UserProfile.phone == FAMILY_PHONE,
                UserProfile.phone_verified.is_(True),
                User.role == Roles.PATIENT,
                User.is_active.is_(True),
            )
            .order_by(User.id)
        )
        .scalars()
        .all()
    )


def _hold_target_row_and_release_when_both_blocked(engine, target_id: int):
    """Serialization pin: hold the users row FOR UPDATE on an external
    connection whose transaction STAYS OPEN (no rollback between polls);
    the returned callable blocks until BOTH contender threads are waiting
    on that row (>= 2 ungranted pg_locks entries — the first waiter shows
    as a transactionid wait, queued followers as tuple waits), then
    releases it. Polls run on separate short-lived connections so the
    holder's lock is never dropped while the contenders are positioned."""
    holder = engine.connect()
    holder.execute(
        text("SELECT id FROM users WHERE id = :id FOR UPDATE"), {"id": target_id}
    )

    def _release_when_both_blocked() -> bool:
        deadline = time.monotonic() + 20
        waiting = 0
        while time.monotonic() < deadline:
            with engine.connect() as poll:
                waiting = (
                    poll.execute(
                        text(
                            "SELECT count(*) FROM pg_locks WHERE NOT granted"
                        )
                    ).scalar()
                    or 0
                )
            if waiting >= 2:
                break
            time.sleep(0.05)
        holder.rollback()
        holder.close()
        # Not pinned => the contenders never queued on the users row: with
        # the round-4 fix in place both MUST block (the lock is the first
        # statement of each path). If the fix is stashed away (RED proof)
        # nothing serializes — release after the deadline anyway and let
        # the final candidate assertions expose the materialized race.
        return waiting >= 2

    return _release_when_both_blocked


def test_parallel_role_change_and_activation_cannot_combine_candidate_pg(
    pg_engine,
):
    """T1 role -> Patient and T2 is_active -> true on the SAME inactive
    Registrar: with row-locked candidate state one operation serializes,
    sees the new effective state and fails with the controlled 409; the
    final DB state keeps exactly ONE candidate on the phone (B)."""
    Session = sessionmaker(bind=pg_engine, expire_on_commit=False)
    svc = UserManagementService()
    a_id, b_id, admin_id = _seed_scene(Session)

    barrier = threading.Barrier(2, timeout=20)
    results: dict[str, tuple[object, object]] = {}
    unexpected: dict[str, Exception] = {}

    def _run(label: str, request: UserUpdateRequest) -> None:
        s = Session()
        try:
            barrier.wait()
            results[label] = (svc.update_user(s, a_id, request, admin_id), None)
        except PatientPhoneScopeConflict as exc:
            results[label] = (None, exc)
        except Exception as exc:  # noqa: BLE001 - surfaced via assertions
            unexpected[label] = exc
        finally:
            s.close()

    release = _hold_target_row_and_release_when_both_blocked(pg_engine, a_id)
    t1 = threading.Thread(
        target=_run,
        args=("role", UserUpdateRequest(role=Roles.PATIENT)),
        daemon=True,
    )
    t2 = threading.Thread(
        target=_run,
        args=("activate", UserUpdateRequest(is_active=True)),
        daemon=True,
    )
    t1.start()
    t2.start()
    release()
    t1.join(30)
    t2.join(30)
    assert not t1.is_alive() and not t2.is_alive(), "contenders did not finish"
    assert not unexpected, f"unexpected contender failures: {unexpected}"

    role_res, role_err = results["role"]
    act_res, act_err = results["activate"]
    outcomes = {"role": results["role"], "activate": results["activate"]}
    oks = [label for label, (_r, e) in outcomes.items() if e is None]
    conflicts = [e for (_r, e) in outcomes.values() if e is not None]

    # exactly one contender wins; the loser hits the CONTROLLED conflict
    assert len(oks) == 1, (
        f"expected exactly one success, got {oks} "
        f"(role={role_res!r}/{role_err!r}, activate={act_res!r}/{act_err!r})"
    )
    assert len(conflicts) == 1, (
        "the serialized loser must fail with PatientPhoneScopeConflict, "
        f"got role={role_res!r}/{role_err!r}, activate={act_res!r}/{act_err!r}"
    )
    assert conflicts[0].status_code == 409
    assert role_res is None or role_res[0] is True
    assert act_res is None or act_res[0] is True

    # the invariant holds: exactly ONE candidate remains, and it is B
    check = Session()
    ids = _candidate_ids(check)
    assert ids == [b_id], (
        f"parallel partial mutations combined into candidates {ids} — "
        "the phone-scope invariant is not transactional"
    )
    assert count_active_verified_patient_users(check, FAMILY_PHONE) == 1
    check.close()


def test_bulk_activate_vs_parallel_role_change_serialized_pg(pg_engine):
    """bulk activate [A] vs concurrent update_user(A, role -> Patient):
    the bulk preflight must read ROW-LOCKED state, so the pair cannot
    combine into a second candidate; exactly one of the two operations
    is blocked (per-user bulk failure or controlled 409)."""
    Session = sessionmaker(bind=pg_engine, expire_on_commit=False)
    svc = UserManagementService()
    a_id, b_id, admin_id = _seed_scene(Session)

    barrier = threading.Barrier(2, timeout=20)
    results: dict[str, object] = {}
    unexpected: dict[str, Exception] = {}

    def _bulk() -> None:
        s = Session()
        try:
            barrier.wait()
            results["bulk"] = svc.bulk_action_users(
                s,
                UserBulkActionRequest(action="activate", user_ids=[a_id]),
                admin_id,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced via assertions
            unexpected["bulk"] = exc
        finally:
            s.close()

    def _role() -> None:
        s = Session()
        try:
            barrier.wait()
            results["role"] = (
                svc.update_user(
                    s, a_id, UserUpdateRequest(role=Roles.PATIENT), admin_id
                ),
                None,
            )
        except PatientPhoneScopeConflict as exc:
            results["role"] = (None, exc)
        except Exception as exc:  # noqa: BLE001 - surfaced via assertions
            unexpected["role"] = exc
        finally:
            s.close()

    release = _hold_target_row_and_release_when_both_blocked(pg_engine, a_id)
    t1 = threading.Thread(target=_bulk, daemon=True)
    t2 = threading.Thread(target=_role, daemon=True)
    t1.start()
    t2.start()
    release()
    t1.join(30)
    t2.join(30)
    assert not t1.is_alive() and not t2.is_alive(), "contenders did not finish"
    assert not unexpected, f"unexpected contender failures: {unexpected}"

    bulk = results["bulk"]
    assert isinstance(bulk, tuple) and len(bulk) == 3, f"bulk result: {bulk!r}"
    bulk_ok, _bulk_msg, bulk_detail = bulk
    role_res, role_err = results["role"]  # type: ignore[misc]
    a_failed_in_bulk = any(
        item.get("user_id") == a_id for item in bulk_detail.get("failed_users", [])
    )
    a_processed_bulk = bool(bulk_ok) and not a_failed_in_bulk
    role_blocked = (
        role_err is not None or (role_res is not None and role_res[0] is False)
    )

    # exactly one of the two operations must be blocked — never both
    assert role_blocked != a_failed_in_bulk, (
        f"expected exactly one blocked operation: bulk_detail={bulk_detail!r}, "
        f"role={role_res!r}/{role_err!r}"
    )
    if role_err is not None:
        assert role_err.status_code == 409
    assert not (a_processed_bulk and role_res is not None and role_res[0] is True), (
        "both operations succeeded — the bulk preflight raced the concurrent "
        "role change (candidate state was not serialized)"
    )

    # the invariant holds: exactly ONE candidate remains, and it is B
    check = Session()
    ids = _candidate_ids(check)
    assert ids == [b_id], (
        f"bulk activate + concurrent role change combined into candidates "
        f"{ids} — the phone-scope invariant is not transactional"
    )
    assert count_active_verified_patient_users(check, FAMILY_PHONE) == 1
    check.close()
