"""Phase 0 PR-A2 — PostgreSQL phone-scope concurrency proof (owner GO
2026-09-18, variant A, point 6).

Two DIFFERENT unlinked Patient cards share one normalized phone (a legal
family number). Two concurrent `activate()` calls run on SEPARATE
connections. A single `Patient ... FOR UPDATE` locks only ONE row — two
family cards are different rows — so the phone-scope PostgreSQL advisory
lock (`pg_advisory_xact_lock` keyed by a hashed phone fingerprint) is what
serializes them. Deterministic interleaving: an external session-level
`pg_advisory_lock` holds the phone scope while the loser thread is already
past its precheck; the "winner" portal identity is created by a second
connection; only then is the lock released and the loser's authoritative
re-read fires.

Contract proven on real PostgreSQL:
    - exactly ONE activation may create a portal identity for a phone;
    - the loser gets a controlled 409 (ERR_PHONE_ALREADY_BOUND) and its
      card stays user_id=NULL with the token NOT consumed;
    - afterwards the DB holds exactly ONE active verified Patient-user for
      the phone and NO orphan User/UserProfile rows.

DSN discipline inherited from RQ-14.a.2: localhost-only candidates,
verified before use, run-scoped scratch database, CREATE-only, teardown in
finally. Disposable local PostgreSQL only; production/staging/Supabase are
never touched. SQLite conftest runs are NOT PG evidence. SYNTHETIC data
only.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.models.patient import Patient
from app.models.user import User
from app.models.user_profile import UserProfile

BACKEND_DIR = Path(__file__).resolve().parents[2]
_RUN = uuid.uuid4().hex[:8]
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
FAMILY_PHONE = "+998900000002"  # SYNTHETIC only

pytestmark = pytest.mark.asyncio


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
        "disposable local PostgreSQL unavailable — PR-A2 phone-scope proof "
        f"NOT_RUN (last reason: {type(last_error).__name__})"
    )


@pytest.fixture()
def pg_engine():
    from sqlalchemy.engine import make_url

    admin_url = _verified_admin_url()
    u = make_url(admin_url)
    db_name = f"pra2_phonescope_{_RUN}"
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


async def test_two_cards_same_phone_exactly_one_portal_identity_pg(
    pg_engine, monkeypatch
):
    """Owner GO point 6: concurrent activation of two different unlinked
    cards with one normalized phone -> exactly one portal identity, the
    loser gets controlled 409, no orphans."""
    from app.services.patient_activation_service import (
        ERR_PHONE_ALREADY_BOUND,
        ActivationError,
        PatientActivationService,
        _phone_lock_key,
    )
    from app.services.patient_otp_service import get_patient_otp_service

    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )

    Session = sessionmaker(bind=pg_engine, expire_on_commit=False)
    svc = PatientActivationService()
    otp = get_patient_otp_service()
    otp._reset_backend_for_tests()
    backend = otp.get_backend()
    backend.last_sent_code.clear()
    try:
        # -- seed: two cards, one family phone
        seed = Session()
        mother = Patient(
            first_name="SYNTHETIC-Mother",
            last_name="FamilyCard",
            phone=FAMILY_PHONE,
            birth_date=None,
        )
        child = Patient(
            first_name="SYNTHETIC-Child",
            last_name="FamilyCard",
            phone=FAMILY_PHONE,
            birth_date=None,
        )
        seed.add_all([mother, child])
        seed.commit()
        mother_id, child_id = mother.id, child.id
        seed.close()

        db_mother = Session()
        db_child = Session()
        mother_token = svc.issue_activation_token(db_mother, mother_id)[
            "activation_token"
        ]
        child_token = svc.issue_activation_token(db_child, child_id)["activation_token"]
        await svc.request_activation_otp(db_child, child_token)
        code = backend.last_sent_code[f"patact:{FAMILY_PHONE}"]

        # -- hold the phone scope externally (session-level lock): models the
        # window between the loser's precheck and its authoritative re-read
        lock_key = _phone_lock_key(FAMILY_PHONE)
        holder = pg_engine.connect()
        holder.execute(text("SELECT pg_advisory_lock(:k)"), {"k": lock_key})

        outcome: dict = {}

        def _loser():
            s = Session()
            try:
                outcome["ok"] = svc.activate(s, child_token, code)
            except ActivationError as exc:
                outcome["err"] = exc
            finally:
                s.close()

        loser = threading.Thread(target=_loser, daemon=True)
        loser.start()

        # wait until the loser is BLOCKED on the advisory xact lock
        deadline = time.monotonic() + 15
        blocked = False
        while time.monotonic() < deadline:
            if not loser.is_alive():
                break  # pre-lock implementation finishes early (RED world)
            waiting = holder.execute(
                text(
                    "SELECT count(*) FROM pg_locks "
                    "WHERE locktype='advisory' AND NOT granted"
                )
            ).scalar()
            if waiting:
                blocked = True
                break
            time.sleep(0.05)

        # the WINNER portal identity appears on a second connection while
        # the loser waits under the phone-scope lock
        winner = Session()
        user = User(
            username=f"synthetic_winner_{_RUN[:6]}",
            email=f"synthetic_winner_{_RUN[:6]}@synthetic.local",
            full_name="SYNTHETIC Winner",
            hashed_password="argon2$synthetic",  # never verified here
            role="Patient",
            is_active=True,
            is_superuser=False,
        )
        winner.add(user)
        winner.flush()
        winner.add(
            UserProfile(
                user_id=user.id,
                full_name="SYNTHETIC Winner",
                phone=FAMILY_PHONE,
                phone_verified=True,
            )
        )
        winner.flush()
        mother_row = winner.execute(
            select(Patient).where(Patient.id == mother_id).with_for_update()
        ).scalar_one()
        mother_row.user_id = user.id
        winner.commit()
        winner_id = user.id
        winner.close()

        holder.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": lock_key})
        loser.join(15)
        assert not loser.is_alive(), "loser activation did not finish"

        # -- owner point 6 assertions
        # (1) the loser failed with the CONTROLLED conflict, not a 500
        err = outcome.get("err")
        assert blocked, "loser was not serialized by the phone-scope lock"
        assert err is not None, "second activation must fail, not succeed"
        assert err.status_code == 409
        assert err.detail == ERR_PHONE_ALREADY_BOUND
        assert "ok" not in outcome

        # (2) exactly ONE active verified Patient-user for the phone
        check = Session()
        candidates = (
            check.execute(
                select(User.id)
                .join(UserProfile, UserProfile.user_id == User.id)
                .where(
                    UserProfile.phone == FAMILY_PHONE,
                    UserProfile.phone_verified.is_(True),
                    User.role == "Patient",
                    User.is_active.is_(True),
                )
            )
            .scalars()
            .all()
        )
        assert candidates == [winner_id]

        # (3) the loser card stays unlinked; no orphan rows
        child_row = check.execute(
            select(Patient).where(Patient.id == child_id)
        ).scalar_one()
        assert child_row.user_id is None
        patient_users = (
            check.execute(
                select(User.id).where(User.role == "Patient", User.is_active.is_(True))
            )
            .scalars()
            .all()
        )
        assert patient_users == [winner_id]  # no orphan User rows
        profiles = (
            check.execute(
                select(UserProfile.id).where(UserProfile.phone == FAMILY_PHONE)
            )
            .scalars()
            .all()
        )
        assert len(profiles) == 1  # no orphan UserProfile rows
        check.close()

        holder.close()
        db_child.close()
        db_mother.close()
    finally:
        otp._reset_backend_for_tests()
