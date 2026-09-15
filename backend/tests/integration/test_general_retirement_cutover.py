"""QD-2E (RQ-15.b) — the `general` retirement cutover.

Stage E of the QD-2 staged rollout (ADR-001 "Stage E ``general``
decision", owner decision D-08, 2026-09-12). This suite pins BOTH
halves of the cutover this PR lands:

- the CATALOG half — migration ``0066_general_retirement_cutover``:
  the operator map (``evidence/stage_e_operator_map_20260912.json``,
  36/57 decided) applied EXACTLY (33 lab retags + 2 cardio doctor
  assignments), inventory-before-mutation, the loud-abort categories
  (ACTIVE general-surface queues, undecided surfaces, stale/invalid
  assign targets, inactive retag targets, ambiguous codes), the
  clean no-op on an empty (CI) database, idempotence and the strict
  guarded downgrade. Parity: the embedded decision tables must match
  the evidence operator map file (they cannot drift);
- the RUNTIME half — fail-closed owner resolution (D-08): no
  ``general_resource`` fallback anywhere (the synthetic users may
  EXIST in the database and are never consulted), no
  arbitrary-active-doctor fallback, no silent skip. Unknown owner =
  ``QueueOwnerConfigurationError`` (a ``ValueError`` subclass — the
  registrar cart surfaces it as 422), while registry tags, explicit
  visit doctors, single service doctors and existing owner surfaces
  keep working byte-identically.
"""

from __future__ import annotations

import importlib.util
import json
import os
import uuid
from datetime import date, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.crud.queue_owner_policy import (
    QueueOwnerConfigurationError,
    owner_configuration_error,
    single_active_service_doctor,
)
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueResource
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
MIGRATION_0064 = (
    BACKEND_ROOT / "alembic" / "versions" / "0066_general_retirement_cutover.py"
)
OPERATOR_MAP = REPO_ROOT / "evidence" / "stage_e_operator_map_20260912.json"
REFINEMENT_MAP = (
    REPO_ROOT / "evidence" / "stage_e_operator_map_refinement_20260915.json"
)

WIZARD_HELPERS = (
    BACKEND_ROOT
    / "app"
    / "api"
    / "v1"
    / "endpoints"
    / "registrar_wizard"
    / "_helpers.py"
)
BATCH_SERVICE = BACKEND_ROOT / "app" / "services" / "batch_patient_service.py"

# non-secret placeholder mirroring the 0055 seed marker
_DISABLED_HASH = "!disabled:queue-resource"

_DAY = date(2026, 9, 12)

# The 36 decided service codes (33 retag -> lab, 2 assign -> doctor 10)
# plus the one keep_profile — the 2026-09-12 production map snapshot.
_RETAG_CODES = (
    "L03",
    "L14",
    "L15",
    "L16",
    "L17",
    "L18",
    "L19",
    "L20",
    "L21",
    "L22",
    "L23",
    "L24",
    "L25",
    "L26",
    "L27",
    "L28",
    "L29",
    "L30",
    "L31",
    "L32",
    "L33",
    "L34",
    "L35",
    "LAB_ALT",
    "LAB_AST",
    "LAB_BILE_URINE",
    "LAB_CA",
    "LAB_CRP",
    "LAB_FUNGI",
    "LAB_HBA1C",
    "LAB_IGE",
    "LAB_MALAS",
    "LAB_RF",
)
_ASSIGN_CODES = ("K01", "K11")
_TARGET_DOCTOR_ID = 10  # the production single real cardiologist

# The 2026-09-12 production snapshot identities (thread 3995689408):
# every decision binds the exact (id, code) object it was approved
# for — the seeded catalog must mirror them (like doctor id 10).
_RETAG_SNAPSHOT_IDS = {
    "L03": 21,
    "L14": 11,
    "L15": 27,
    "L16": 22,
    "L17": 24,
    "L18": 23,
    "L19": 20,
    "L20": 28,
    "L21": 29,
    "L22": 52,
    "L23": 63,
    "L24": 53,
    "L25": 12,
    "L26": 72,
    "L27": 30,
    "L28": 32,
    "L29": 73,
    "L30": 44,
    "L31": 74,
    "L32": 62,
    "L33": 61,
    "L34": 60,
    "L35": 33,
    "LAB_ALT": 25,
    "LAB_AST": 26,
    "LAB_BILE_URINE": 36,
    "LAB_CA": 31,
    "LAB_CRP": 51,
    "LAB_FUNGI": 70,
    "LAB_HBA1C": 34,
    "LAB_IGE": 75,
    "LAB_MALAS": 71,
    "LAB_RF": 50,
}
_ASSIGN_SNAPSHOT_IDS = {
    "K01": 2,
    "K11": 127,
    # the 2026-09-15 refinement assignments (part of the embedded map)
    "O10": 125,
    "O20": 126,
    "S10": 90,
}

# The 2026-09-15 D-08 refinement identities (owner decisions: O10 -> UZD
# doctor 17, O20 -> Невролог doctor 18, S10 -> Stomatolog doctor 16; the
# 16 procedure services move onto the QueueResource('procedures') axis).
_REFINEMENT_ASSIGN_SNAPSHOT_IDS = {"O10": 125, "O20": 126, "S10": 90}
_REFINEMENT_DOCTORS = {17: 29, 18: 30, 16: 27}  # doctor_id -> user_id
_CLEAR_CODES = (
    "P08", "P03", "P09", "P07", "P10",
    "C07", "C08", "C03", "C06", "C09",
    "C12", "C11", "C10", "D06", "D05", "D07",
)
_CLEAR_SNAPSHOT_IDS = {
    "P08": 100, "P03": 101, "P09": 102, "P07": 103, "P10": 104,
    "C07": 110, "C08": 111, "C03": 112, "C06": 113, "C09": 114,
    "C12": 115, "C11": 116, "C10": 117, "D06": 120, "D05": 121, "D07": 122,
}


# ===================== helpers =====================


def _load_migration_0064():
    spec = importlib.util.spec_from_file_location(
        "migration_0066_general_retirement_cutover", MIGRATION_0064
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cutover_metadata() -> sa.MetaData:
    """Minimal tables for the cutover: services + queue_profiles joined
    against users/doctors/queue_resources/daily_queues/queue_entries
    (the 0063 scratch pattern; the tool's surface definition joins the
    same tables). Shared by the sqlite scratch harness and the
    PostgreSQL two-connection race fixture."""
    metadata = sa.MetaData()
    sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
    )
    sa.Table(
        "doctors",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=True),
        sa.Column("specialty", sa.String(100), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, default=True),
    )
    sa.Table(
        "queue_resources",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("queue_tag", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, default=True),
        # 0058 EXPAND columns (the D-08 refinement seed inserts them);
        # nullable here — the minimal scratch table only needs the columns
        # to EXIST, and the legacy lab-registry helper inserts without them
        sa.Column("start_number_online", sa.Integer, nullable=True),
        sa.Column("max_online_per_day", sa.Integer, nullable=True),
        sa.Column("default_cabinet", sa.String(20), nullable=True),
    )
    sa.Table(
        "services",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("queue_tag", sa.String(32), nullable=True),
        sa.Column("department_key", sa.String(50), nullable=True),
        sa.Column("doctor_id", sa.Integer, nullable=True),
        sa.Column("requires_doctor", sa.Boolean, nullable=False, default=True),
        sa.Column("active", sa.Boolean, nullable=False, default=True),
    )
    sa.Table(
        "queue_profiles",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
    )
    sa.Table(
        "daily_queues",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("day", sa.String(10), nullable=False),
        sa.Column("specialist_id", sa.Integer, nullable=True),
        sa.Column("queue_resource_id", sa.Integer, nullable=True),
        sa.Column("queue_tag", sa.String(32), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False, default=True),
    )
    sa.Table(
        "queue_entries",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("queue_id", sa.Integer, nullable=False),
        sa.Column("number", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="waiting"),
    )
    return metadata


def _create_cutover_tables(engine) -> None:
    """Create the minimal cutover tables on ANY engine (sqlite scratch or
    the isolated PostgreSQL schema of the race fixture)."""
    _cutover_metadata().create_all(engine)


def _scratch():
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    _create_cutover_tables(engine)
    return engine.connect()


def _seed_user(conn, username: str, *, role: str = "Resource") -> int:
    conn.execute(
        sa.text(
            "INSERT INTO users (username, role, is_active, hashed_password)"
            " VALUES (:u, :r, :a, :p)"
        ),
        {"u": username, "r": role, "a": True, "p": _DISABLED_HASH},
    )
    (user_id,) = conn.execute(
        sa.text("SELECT id FROM users WHERE username = :u"), {"u": username}
    ).fetchone()
    return user_id


def _seed_doctor(conn, user_id: int | None, *, specialty: str, active: bool = True):
    conn.execute(
        sa.text(
            "INSERT INTO doctors (user_id, specialty, active)" " VALUES (:u, :s, :a)"
        ),
        {"u": user_id, "s": specialty, "a": bool(active)},
    )
    (doctor_id,) = conn.execute(
        sa.text("SELECT id FROM doctors ORDER BY id DESC LIMIT 1")
    ).fetchone()
    return doctor_id


def _seed_synthetic_world(conn) -> None:
    """The 0055 production identities (user ids 23/24/25, doctor ids
    12/13/14 on production; exact ids do not matter here — only the
    username/specialty shape) + the real cardiologist (doctor id 10 is
    FORCED to mirror the operator map target)."""
    for username, tag in (
        ("ecg_resource", "ecg"),
        ("lab_resource", "lab"),
        ("general_resource", "general"),
    ):
        user_id = _seed_user(conn, username)
        _seed_doctor(conn, user_id, specialty=tag)
    # the single real cardiologist, forced to the production map target id
    cardio_user = _seed_user(conn, "dr_cardio", role="doctor")
    conn.execute(
        sa.text(
            "INSERT INTO doctors (id, user_id, specialty, active)"
            " VALUES (10, :u, 'cardio', :a)"
        ),
        {"u": cardio_user, "a": True},
    )
    # the ACTIVE lab registry row (the 0059 seed shape)
    conn.execute(
        sa.text(
            "INSERT INTO queue_resources (code, queue_tag, display_name, active)"
            " VALUES ('lab', 'lab', 'Лаборатория', :a)"
        ),
        {"a": True},
    )


def _seed_decided_services(conn) -> None:
    """The 36-decided production snapshot WITH the snapshot identities
    (thread 3995689408): 33 lab services tagged 'general'
    (requires_doctor=false) + K01/K11 cardio consults, every row at
    its 2026-09-12 production id — the map's decisions bind (id, code),
    so the seeded catalog must mirror them exactly like doctor id 10."""
    for code in _RETAG_CODES:
        conn.execute(
            sa.text(
                "INSERT INTO services (id, code, name, queue_tag,"
                " department_key, doctor_id, requires_doctor, active)"
                " VALUES (:id, :c, :n, 'general', NULL, NULL, :rd, :a)"
            ),
            {
                "id": _RETAG_SNAPSHOT_IDS[code],
                "c": code,
                "n": f"Лаб-услуга {code}",
                "rd": False,
                "a": True,
            },
        )
    for code in _ASSIGN_CODES:
        conn.execute(
            sa.text(
                "INSERT INTO services (id, code, name, queue_tag,"
                " department_key, doctor_id, requires_doctor, active)"
                " VALUES (:id, :c, :n, 'cardio', 'cardiology', NULL, :rd, :a)"
            ),
            {
                "id": _ASSIGN_SNAPSHOT_IDS[code],
                "c": code,
                "n": f"Кардио-услуга {code}",
                "rd": True,
                "a": True,
            },
        )
    conn.execute(
        sa.text(
            "INSERT INTO queue_profiles (key, is_active) VALUES ('general', :a)"
        ),
        {"a": True},
    )


def _service_state(conn, code: str):
    return conn.execute(
        sa.text("SELECT queue_tag, doctor_id, active FROM services WHERE code = :c"),
        {"c": code},
    ).fetchone()


def _assert_abort(conn, needle: str) -> None:
    """Run upgrade and assert the loud RuntimeError with the needle,
    leaving the transaction untouched (no rows changed is asserted by
    the callers through _service_state)."""
    module = _load_migration_0064()
    with pytest.raises(RuntimeError, match=needle) as excinfo:
        module.upgrade_with_conn(conn)
    assert "aborting with no rows changed" in str(excinfo.value)


def _make_user(db_session: Session, *, username: str, role: str) -> User:
    user = User(
        username=username, hashed_password=_DISABLED_HASH, role=role, is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_doctor(db_session: Session, *, user_id: int, specialty: str) -> Doctor:
    doctor = Doctor(user_id=user_id, specialty=specialty, active=True)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _make_service(
    db_session: Session,
    *,
    code: str,
    queue_tag: str | None,
    name: str,
    requires_doctor: bool = False,
    doctor_id: int | None = None,
    department_key: str | None = None,
) -> Service:
    service = Service(
        code=code,
        name=name,
        queue_tag=queue_tag,
        requires_doctor=requires_doctor,
        doctor_id=doctor_id,
        department_key=department_key,
        active=True,
        price=0,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _make_visit(db_session: Session, *, doctor_id: int | None = None) -> Visit:
    patient = Patient(last_name="Тестов", first_name="Тест")
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    visit = Visit(
        patient_id=patient.id,
        status="confirmed",
        visit_date=_DAY,
        doctor_id=doctor_id,
    )
    db_session.add(visit)
    db_session.commit()
    db_session.refresh(visit)
    return visit


def _link_visit_service(db_session: Session, visit: Visit, service: Service) -> None:
    db_session.add(
        VisitService(
            visit_id=visit.id,
            service_id=service.id,
            name=service.name,
            code=service.code,
        )
    )
    db_session.commit()


# ===================== A. migration data logic (scratch SQLite) =====================


def test_upgrade_applies_the_operator_map_exactly() -> None:
    conn = _scratch()
    _seed_synthetic_world(conn)
    _seed_decided_services(conn)
    module = _load_migration_0064()

    module.upgrade_with_conn(conn)

    for code in _RETAG_CODES:
        tag, doctor_id, _active = _service_state(conn, code)
        assert tag == "lab", f"{code}: retag to the ACTIVE lab resource"
        assert doctor_id is None, f"{code}: retag never invents a doctor"
    for code in _ASSIGN_CODES:
        tag, doctor_id, active = _service_state(conn, code)
        assert (tag, doctor_id, active) == ("cardio", _TARGET_DOCTOR_ID, 1)
    # the keep_profile decision writes nothing
    (profile_active,) = conn.execute(
        sa.text("SELECT is_active FROM queue_profiles WHERE key = 'general'")
    ).fetchone()
    assert profile_active == 1
    # the synthetic pairs themselves are untouched (RQ-15.d territory)
    assert (
        conn.execute(sa.text("SELECT COUNT(*) FROM users")).scalar() == 4
    )  # 3 synthetics + the cardiologist's user


def test_upgrade_aborts_on_undecided_surface() -> None:
    """The D-08 gate (no silent stranding): after the 2026-09-15
    refinement 19 of the 21 nulls are decided (and the procedures tag
    is registry-resolved by the seeded QueueResource) — the migration
    still REFUSES to run while S01/D01 remain undecided."""
    conn = _scratch()
    _seed_synthetic_world(conn)
    _seed_decided_services(conn)
    # an ACTIVE undecided surface — S01 is one of the two remaining nulls
    conn.execute(
        sa.text(
            "INSERT INTO services (code, name, queue_tag, department_key,"
            " doctor_id, requires_doctor, active)"
            " VALUES ('S01', 'Консультация стоматолога', 'stomatology',"
            " NULL, NULL, 1, 1)"
        )
    )

    _assert_abort(conn, "NO operator decision")

    # no rows changed: the decided services are untouched
    tag, doctor_id, _ = _service_state(conn, "L03")
    assert (tag, doctor_id) == ("general", None)
    tag, doctor_id, _ = _service_state(conn, "K01")
    assert (tag, doctor_id) == ("cardio", None)


def test_upgrade_aborts_on_stale_from_tag() -> None:
    """Codex round-1 P1: a service hand-moved to a THIRD tag after the
    snapshot must abort the cutover (stale map), not be silently
    retagged onto the map's target."""
    conn = _scratch()
    _seed_synthetic_world(conn)
    _seed_decided_services(conn)
    # the operator moved L03 from 'general' to 'procedures' after the map
    conn.execute(
        sa.text("UPDATE services SET queue_tag = 'procedures' WHERE code = 'L03'")
    )

    _assert_abort(conn, "stale operator map for 'L03'")
    tag, _, _ = _service_state(conn, "L03")
    assert tag == "procedures"  # the newer operator decision survives
    tag, _, _ = _service_state(conn, "L14")
    assert tag == "general"  # nothing applied at all


def test_upgrade_aborts_on_foreign_doctor_assignment() -> None:
    """Codex round-1 P1: K01 hand-assigned to another real doctor after
    the snapshot aborts the cutover — the newer assignment is never
    overwritten with the embedded target."""
    conn = _scratch()
    _seed_synthetic_world(conn)
    _seed_decided_services(conn)
    # another real doctor (id 11) was assigned to K01 after the map
    other_user = _seed_user(conn, "dr_other", role="doctor")
    conn.execute(
        sa.text(
            "INSERT INTO doctors (id, user_id, specialty, active)"
            " VALUES (11, :u, 'cardio', 1)"
        ),
        {"u": other_user},
    )
    conn.execute(sa.text("UPDATE services SET doctor_id = 11 WHERE code = 'K01'"))

    _assert_abort(conn, "stale operator map for 'K01'")
    _, doctor_id, _ = _service_state(conn, "K01")
    assert doctor_id == 11  # the newer operator assignment survives


def test_upgrade_aborts_on_mapped_service_moved_to_active_resource_tag() -> None:
    """Codex round-2 P1: a mapped L03 the operator moved onto ANOTHER
    ACTIVE resource tag ('ecg') is invisible to the fallback-surface
    inventory (the tag resolves) — the by-code pre-state check must
    still abort the cutover instead of treating the decision as inert
    and mutating the other mapped rows on a stale map."""
    conn = _scratch()
    _seed_synthetic_world(conn)
    _seed_decided_services(conn)
    # an ACTIVE ecg registry row (the 0059 seed shape)
    conn.execute(
        sa.text(
            "INSERT INTO queue_resources (code, queue_tag, display_name, active)"
            " VALUES ('ecg', 'ecg', 'ЭКГ', 1)"
        )
    )
    # the operator hand-moved L03 onto the resolvable 'ecg' tag
    conn.execute(sa.text("UPDATE services SET queue_tag = 'ecg' WHERE code = 'L03'"))

    _assert_abort(conn, "stale operator map for 'L03'")
    tag, _, _ = _service_state(conn, "L03")
    assert tag == "ecg"  # the newer operator decision survives
    tag, _, _ = _service_state(conn, "L14")
    assert tag == "general"  # nothing applied at all


def test_upgrade_aborts_on_assign_code_moved_to_active_resource_tag() -> None:
    """Codex round-3 P1: a mapped assign code (K01, snapshot tag
    'cardio') hand-moved onto ANOTHER ACTIVE resource tag while staying
    doctorless is invisible to the surface inventory (the tag resolves)
    and passes the doctor check (None == original) — the snapshot-tag
    validation must abort it as a stale map."""
    conn = _scratch()
    _seed_synthetic_world(conn)
    _seed_decided_services(conn)
    conn.execute(
        sa.text(
            "INSERT INTO queue_resources (code, queue_tag, display_name, active)"
            " VALUES ('ecg', 'ecg', 'ЭКГ', 1)"
        )
    )
    conn.execute(sa.text("UPDATE services SET queue_tag = 'ecg' WHERE code = 'K01'"))

    _assert_abort(conn, "stale operator map for 'K01'")
    tag, _, _ = _service_state(conn, "K01")
    assert tag == "ecg"  # the newer operator decision survives
    tag, _, _ = _service_state(conn, "L14")
    assert tag == "general"  # nothing applied at all


def test_upgrade_aborts_on_active_general_queue() -> None:
    conn = _scratch()
    _seed_synthetic_world(conn)
    _seed_decided_services(conn)
    (general_doctor_id,) = conn.execute(
        sa.text("SELECT id FROM doctors WHERE specialty = 'general'")
    ).fetchone()
    conn.execute(
        sa.text(
            "INSERT INTO daily_queues (day, specialist_id, queue_resource_id,"
            " queue_tag, active) VALUES ('2026-09-12', :d, NULL, 'general', 1)"
        ),
        {"d": general_doctor_id},
    )

    _assert_abort(conn, "ACTIVE general-surface daily_queues")
    tag, _, _ = _service_state(conn, "L03")
    assert tag == "general"


def test_upgrade_aborts_on_synthetic_owned_active_queue() -> None:
    """A lab-tagged ACTIVE queue still owned by the lab synthetic is a
    general-surface queue too (the tool's owner-based half)."""
    conn = _scratch()
    _seed_synthetic_world(conn)
    _seed_decided_services(conn)
    (lab_doctor_id,) = conn.execute(
        sa.text("SELECT id FROM doctors WHERE specialty = 'lab'")
    ).fetchone()
    (lab_resource_id,) = conn.execute(
        sa.text("SELECT id FROM queue_resources WHERE queue_tag = 'lab'")
    ).fetchone()
    conn.execute(
        sa.text(
            "INSERT INTO daily_queues (day, specialist_id, queue_resource_id,"
            " queue_tag, active) VALUES ('2026-09-12', :d, :r, 'lab', 1)"
        ),
        {"d": lab_doctor_id, "r": lab_resource_id},
    )

    _assert_abort(conn, "ACTIVE general-surface daily_queues")


def test_upgrade_aborts_when_target_doctor_missing() -> None:
    conn = _scratch()
    # synthetic world WITHOUT the cardiologist (id 10 absent)
    for username, tag in (
        ("ecg_resource", "ecg"),
        ("lab_resource", "lab"),
        ("general_resource", "general"),
    ):
        user_id = _seed_user(conn, username)
        _seed_doctor(conn, user_id, specialty=tag)
    conn.execute(
        sa.text(
            "INSERT INTO queue_resources (code, queue_tag, display_name, active)"
            " VALUES ('lab', 'lab', 'Лаборатория', 1)"
        )
    )
    _seed_decided_services(conn)

    _assert_abort(conn, "assign_doctor target doctor id=10 does not exist")
    tag, doctor_id, _ = _service_state(conn, "K01")
    assert doctor_id is None


def test_upgrade_aborts_when_target_doctor_is_synthetic() -> None:
    conn = _scratch()
    _seed_synthetic_world(conn)
    # re-point doctor id 10 at the general synthetic user (drift shape)
    (general_user_id,) = conn.execute(
        sa.text("SELECT u.id FROM users u WHERE u.username = 'general_resource'")
    ).fetchone()
    conn.execute(sa.text("DELETE FROM doctors WHERE id = 10"))
    conn.execute(
        sa.text(
            "INSERT INTO doctors (id, user_id, specialty, active)"
            " VALUES (10, :u, 'general', 1)"
        ),
        {"u": general_user_id},
    )
    _seed_decided_services(conn)

    _assert_abort(conn, "synthetic/internal resource identity")


def test_upgrade_aborts_when_target_doctor_inactive() -> None:
    conn = _scratch()
    _seed_synthetic_world(conn)
    conn.execute(sa.text("UPDATE doctors SET active = 0 WHERE id = 10"))
    _seed_decided_services(conn)

    _assert_abort(conn, "is inactive")
    _, doctor_id, _ = _service_state(conn, "K01")
    assert doctor_id is None


def test_upgrade_aborts_when_retag_target_resource_missing() -> None:
    conn = _scratch()
    _seed_synthetic_world(conn)
    conn.execute(sa.text("UPDATE queue_resources SET active = 0"))
    _seed_decided_services(conn)

    _assert_abort(conn, "retag_resource target 'lab'")
    tag, _, _ = _service_state(conn, "L03")
    assert tag == "general"


def test_upgrade_aborts_on_ambiguous_service_code() -> None:
    conn = _scratch()
    _seed_synthetic_world(conn)
    _seed_decided_services(conn)
    conn.execute(
        sa.text(
            "INSERT INTO services (code, name, queue_tag, department_key,"
            " doctor_id, requires_doctor, active)"
            " VALUES ('L03', 'дубль кода', 'general', NULL, NULL, 0, 1)"
        )
    )

    _assert_abort(conn, "ambiguous service code 'L03'")


def test_upgrade_is_a_clean_noop_on_an_empty_database() -> None:
    """The CI contract: ``alembic upgrade head`` runs on an EMPTY
    database — no surfaces, no decisions to apply, a clean pass."""
    conn = _scratch()
    module = _load_migration_0064()
    module.upgrade_with_conn(conn)  # must not raise
    assert conn.execute(sa.text("SELECT COUNT(*) FROM services")).scalar() == 0


def test_upgrade_is_idempotent_second_pass() -> None:
    conn = _scratch()
    _seed_synthetic_world(conn)
    _seed_decided_services(conn)
    module = _load_migration_0064()
    module.upgrade_with_conn(conn)
    # a second pass re-validates and applies nothing new
    module.upgrade_with_conn(conn)
    for code in _RETAG_CODES:
        tag, _, _ = _service_state(conn, code)
        assert tag == "lab"
    for code in _ASSIGN_CODES:
        _, doctor_id, _ = _service_state(conn, code)
        assert doctor_id == _TARGET_DOCTOR_ID


def test_inert_decision_proceeds_with_a_log() -> None:
    """A decision whose service is gone (disabled after the map was
    made) is inert — the cutover proceeds (the surface set shrank)."""
    conn = _scratch()
    _seed_synthetic_world(conn)
    _seed_decided_services(conn)
    conn.execute(sa.text("DELETE FROM services WHERE code = 'K11'"))

    module = _load_migration_0064()
    module.upgrade_with_conn(conn)  # must not raise
    _, doctor_id, _ = _service_state(conn, "K01")
    assert doctor_id == _TARGET_DOCTOR_ID


# ========== the snapshot-identity contract (thread 3995689408, P1) ==========

from contextlib import contextmanager


@contextmanager
def _scratch_engine_disposed():
    """A scratch connection whose engine is disposed DETERMINISTICALLY at
    test end (test hygiene, the QD-2C round-5 ruling): a leaked engine
    perturbs the process heap long after the test, and the lab seed
    cache (app/services/lab_reporting/_base.py) keys its per-bind state
    by ``id(bind)`` — CPython address reuse then flips a later lab test
    into skipping its seeding. Disposing here keeps this suite's
    footprint bounded and deterministic."""
    conn = _scratch()
    try:
        yield conn
    finally:
        conn.engine.dispose()


def test_identity_snapshot_object_deleted_and_code_reused_aborts() -> None:
    """The exact finding scenario: the map approved a decision for
    id=21/code='L03'; the original object was deleted; a NEW row
    id=999/code='L03' sits on the fallback surface. The migration must
    NOT apply the old decision to id=999 — the coverage gate aborts
    with the different-object message and NOTHING is written."""
    with _scratch_engine_disposed() as conn:
        _seed_synthetic_world(conn)
        _seed_decided_services(conn)
        conn.execute(sa.text("DELETE FROM services WHERE id = 21"))
        conn.execute(
            sa.text(
                "INSERT INTO services (id, code, name, queue_tag,"
                " department_key, doctor_id, requires_doctor, active)"
                " VALUES (999, 'L03', 'Новый анализ', 'general', NULL, NULL, 0, 1)"
            )
        )

        _assert_abort(conn, "the map decides id\\(s\\) 21 for that code")

        # no rows changed: the replacement keeps the operator's 'general'
        # and the rest of the map was never touched
        tag, _, _ = _service_state(conn, "L03")
        assert tag == "general"
        tag, _, _ = _service_state(conn, "L14")
        assert tag == "general"
        _, doctor_id, _ = _service_state(conn, "K01")
        assert doctor_id is None


def test_identity_approved_object_disabled_with_active_replacement_aborts() -> None:
    """Variant of the finding: the approved object id=21 was DISABLED
    (not deleted) while a different active row re-uses the code on the
    fallback surface — the decision does not cover the replacement and
    the map aborts with no rows changed."""
    with _scratch_engine_disposed() as conn:
        _seed_synthetic_world(conn)
        _seed_decided_services(conn)
        conn.execute(sa.text("UPDATE services SET active = 0 WHERE id = 21"))
        conn.execute(
            sa.text(
                "INSERT INTO services (id, code, name, queue_tag,"
                " department_key, doctor_id, requires_doctor, active)"
                " VALUES (999, 'L03', 'Новый анализ', 'general', NULL, NULL, 0, 1)"
            )
        )

        _assert_abort(conn, "the map decides id\\(s\\) 21 for that code")
        tag, _, _ = _service_state(conn, "L03")
        assert tag == "general"
        tag, _, _ = _service_state(conn, "L14")
        assert tag == "general"


def test_identity_deleted_object_with_off_surface_carrier_aborts() -> None:
    """The coverage gate only sees fallback-surface rows; a carrier
    hidden behind an ACTIVE resource tag would slip past it. The
    application-phase identity resolution must still refuse: the
    approved id=21 is gone while a live id=999 carries the code."""
    with _scratch_engine_disposed() as conn:
        _seed_synthetic_world(conn)
        _seed_decided_services(conn)
        # an ACTIVE ecg registry row (the 0059 seed shape)
        conn.execute(
            sa.text(
                "INSERT INTO queue_resources (code, queue_tag, display_name, active)"
                " VALUES ('ecg', 'ecg', 'ЭКГ', 1)"
            )
        )
        conn.execute(sa.text("DELETE FROM services WHERE id = 21"))
        # the replacement sits on the RESOLVED 'ecg' tag: invisible to the
        # coverage inventory, visible to the identity resolution
        conn.execute(
            sa.text(
                "INSERT INTO services (id, code, name, queue_tag,"
                " department_key, doctor_id, requires_doctor, active)"
                " VALUES (999, 'L03', 'Новый анализ', 'ecg', NULL, NULL, 0, 1)"
            )
        )

        _assert_abort(conn, "id=21 no longer exists but 1 ACTIVE row")
        tag, _, _ = _service_state(conn, "L03")
        assert tag == "ecg"  # the replacement is never retagged by the old decision
        tag, _, _ = _service_state(conn, "L14")
        assert tag == "general"
def test_identity_disabled_object_with_off_surface_carrier_aborts() -> None:
    """Same as above with the disabled variant: the approved object is
    inactive, a different live row carries the code behind a resolved
    tag — abort, never re-point the decision."""
    with _scratch_engine_disposed() as conn:
        _seed_synthetic_world(conn)
        _seed_decided_services(conn)
        conn.execute(
            sa.text(
                "INSERT INTO queue_resources (code, queue_tag, display_name, active)"
                " VALUES ('ecg', 'ecg', 'ЭКГ', 1)"
            )
        )
        conn.execute(sa.text("UPDATE services SET active = 0 WHERE id = 21"))
        conn.execute(
            sa.text(
                "INSERT INTO services (id, code, name, queue_tag,"
                " department_key, doctor_id, requires_doctor, active)"
                " VALUES (999, 'L03', 'Новый анализ', 'ecg', NULL, NULL, 0, 1)"
            )
        )

        _assert_abort(conn, "id=21 is disabled while 1 ACTIVE row")
        # the replacement (id=999) keeps the operator's 'ecg' — never retagged
        (replacement_tag,) = conn.execute(
            sa.text("SELECT queue_tag FROM services WHERE id = 999")
        ).fetchone()
        assert replacement_tag == "ecg"
        # the disabled approved object is never re-activated or re-tagged
        approved_tag, approved_active = conn.execute(
            sa.text("SELECT queue_tag, active FROM services WHERE id = 21")
        ).fetchone()
        assert (approved_tag, bool(approved_active)) == ("general", False)
def test_identity_row_id_reused_for_a_different_code_aborts() -> None:
    """ID matched but the code/expected state changed: the snapshot row
    id=21 now carries a different code — the catalog identity drifted
    after the map was approved and the migration must abort instead of
    silently skipping (a silent skip would let the rest of the map
    apply onto a database that no longer matches the approval)."""
    with _scratch_engine_disposed() as conn:
        _seed_synthetic_world(conn)
        _seed_decided_services(conn)
        # id=21 re-keyed off the fallback surface entirely (tag NULL,
        # no department, no doctor — invisible to the coverage inventory)
        conn.execute(
            sa.text("UPDATE services SET code = 'L99', queue_tag = NULL WHERE id = 21")
        )

        _assert_abort(conn, "service id=21 now carries code='L99'")
        # no rows changed anywhere in the map
        tag, _, _ = _service_state(conn, "L14")
        assert tag == "general"
        _, doctor_id, _ = _service_state(conn, "K01")
        assert doctor_id is None
def test_identity_object_already_in_proven_final_state_is_a_noop() -> None:
    """The original object exists with its snapshot identity and ALREADY
    sits on the decision's final state (a hand-applied decision or an
    earlier pass) — the migration proves the no-op and completes the
    REST of the map."""
    with _scratch_engine_disposed() as conn:
        _seed_synthetic_world(conn)
        _seed_decided_services(conn)
        # the operator hand-applied the L03 decision before running the
        # cutover (the 0063 no-op precedent)
        conn.execute(sa.text("UPDATE services SET queue_tag = 'lab' WHERE id = 21"))

        module = _load_migration_0064()
        module.upgrade_with_conn(conn)  # must not raise

        tag, _, _ = _service_state(conn, "L03")
        assert tag == "lab"
        # the rest of the map still applied
        for code in ("L14", "L15", "LAB_RF"):
            tag, _, _ = _service_state(conn, code)
            assert tag == "lab", code
        _, doctor_id, _ = _service_state(conn, "K01")
        assert doctor_id == _TARGET_DOCTOR_ID
def test_identity_one_conflict_rolls_back_the_whole_map() -> None:
    """One conflicting decision in the map (a stale row the operator
    moved to a third tag) aborts the cutover with NO other decision
    applied — the map is atomic, never partially applied."""
    with _scratch_engine_disposed() as conn:
        _seed_synthetic_world(conn)
        _seed_decided_services(conn)
        # the operator moved L20 (id=28) to 'procedures' after the snapshot
        conn.execute(
            sa.text("UPDATE services SET queue_tag = 'procedures' WHERE id = 28")
        )

        _assert_abort(conn, "stale operator map for 'L20'")

        # EVERY decided service is untouched — no partial application;
        # L20 itself keeps the operator's newer 'procedures' decision
        for code in _RETAG_CODES:
            tag, _, _ = _service_state(conn, code)
            assert tag == ("procedures" if code == "L20" else "general"), code
        for code in _ASSIGN_CODES:
            _, doctor_id, _ = _service_state(conn, code)
            assert doctor_id is None, code
def test_identity_disabled_object_without_replacement_is_inert() -> None:
    """The operator resolved an approved object himself by disabling it
    (no replacement row re-uses the code): the decision is inert with an
    explicit identity-aware log line, and the rest of the map applies."""
    with _scratch_engine_disposed() as conn:
        _seed_synthetic_world(conn)
        _seed_decided_services(conn)
        conn.execute(sa.text("UPDATE services SET active = 0 WHERE id = 127"))  # K11

        module = _load_migration_0064()
        module.upgrade_with_conn(conn)  # must not raise

        _, doctor_id, active = _service_state(conn, "K11")
        assert (doctor_id, bool(active)) == (None, False)  # never re-activated
        _, doctor_id, _ = _service_state(conn, "K01")
        assert doctor_id == _TARGET_DOCTOR_ID  # the rest of the map applied
def test_identity_other_database_shape_aborts_with_the_boundary_message() -> None:
    """The documented boundary: the map's snapshot ids are PRODUCTION
    identities — another installation whose rows carry the same codes
    under different ids does not match the approved map and needs its
    own decisions (the D-08 runbook cycle), NOT a silent re-target."""
    with _scratch_engine_disposed() as conn:
        _seed_synthetic_world(conn)
        # same codes, DIFFERENT ids (a non-production database shape)
        next_id = 500
        for code in _RETAG_CODES:
            conn.execute(
                sa.text(
                    "INSERT INTO services (id, code, name, queue_tag,"
                    " department_key, doctor_id, requires_doctor, active)"
                    " VALUES (:id, :c, :n, 'general', NULL, NULL, 0, 1)"
                ),
                {"id": next_id, "c": code, "n": f"Лаб-услуга {code}"},
            )
            next_id += 1
        for code in _ASSIGN_CODES:
            conn.execute(
                sa.text(
                    "INSERT INTO services (id, code, name, queue_tag,"
                    " department_key, doctor_id, requires_doctor, active)"
                    " VALUES (:id, :c, :n, 'cardio', 'cardiology', NULL, 1, 1)"
                ),
                {"id": next_id, "c": code, "n": f"Кардио-услуга {code}"},
            )
            next_id += 1
        conn.execute(
            sa.text("INSERT INTO queue_profiles (key, is_active) VALUES ('general', 1)")
        )

        _assert_abort(conn, "a DIFFERENT object carries it now")
        tag, _, _ = _service_state(conn, "L03")
        assert tag == "general"
def test_downgrade_is_validate_only_and_writes_nothing() -> None:
    """Codex round-1 P1 (the 0059 round-2 / 0063 ruling): the data
    downgrade cannot prove WHICH rows the upgrade changed — a mapped
    code on the post-state tag may be an inert no-op (hand-applied
    before the cutover) — so the downgrade validates and explains,
    restores NOTHING, and a pre-E backup / the upgrade log are the
    recovery paths."""
    conn = _scratch()
    _seed_synthetic_world(conn)
    _seed_decided_services(conn)
    module = _load_migration_0064()
    module.upgrade_with_conn(conn)

    module.downgrade_with_conn(conn)  # must not raise and must not write

    # the catalog stays in the post-upgrade state — untouched
    for code in _RETAG_CODES:
        tag, _, _ = _service_state(conn, code)
        assert tag == "lab"
    for code in _ASSIGN_CODES:
        _, doctor_id, _ = _service_state(conn, code)
        assert doctor_id == _TARGET_DOCTOR_ID


def test_downgrade_never_clobbers_a_pre_existing_post_state() -> None:
    """The exact corruption scenario codex flagged: an L03 service
    ALREADY on 'lab' before the upgrade (a hand-applied decision the
    upgrade treats as an inert no-op) — the validate-only downgrade
    leaves it untouched."""
    conn = _scratch()
    _seed_synthetic_world(conn)
    _seed_decided_services(conn)
    conn.execute(sa.text("UPDATE services SET queue_tag = 'lab' WHERE code = 'L03'"))
    module = _load_migration_0064()
    module.upgrade_with_conn(conn)  # L03 inert — idempotent no-op pass

    module.downgrade_with_conn(conn)

    tag, _, _ = _service_state(conn, "L03")
    assert tag == "lab"  # neither the upgrade nor the downgrade moved it


def test_migration_source_never_deletes_or_inserts() -> None:
    """Source pin (the 0059/0063 NOTE convention): the cutover carries
    no DELETE and no INSERT against the CLINIC data tables — the only
    data writes are the guarded service/profile UPDATEs plus the SINGLE
    documented registry seed (QueueResource('procedures'), the D-08
    2026-09-15 refinement)."""
    source = MIGRATION_0064.read_text(encoding="utf-8")
    assert "DELETE" not in source
    assert "INSERT INTO services" not in source
    assert "INSERT INTO daily_queues" not in source
    assert "INSERT INTO queue_entries" not in source
    assert "INSERT INTO queue_resources" in source
    assert "UPDATE services" in source


# ===================== the preflight→write race (3995689409, P1) =====================


def test_upgrade_aborts_when_operator_edits_row_between_preflight_and_write() -> None:
    """The race the review exposed: an operator edit lands AFTER the
    pre-state check read the row (deploy reality — alembic runs while
    uvicorn still serves catalog writes). The guarded UPDATE (identity
    id+code AND the expected source tag) matches zero rows and the map
    aborts; the operator's edit is NOT overwritten and the caller's
    rollback discards every write the migration made before the abort.

    Sqlite single-connection simulation: the edit joins the migration's
    transaction, so the pre-rollback assertions prove the not-overwritten
    half and the post-rollback assertions prove the atomic half; the
    committed-separate-transaction proof runs on PostgreSQL below."""
    conn = _scratch()
    _seed_synthetic_world(conn)
    _seed_decided_services(conn)
    conn.commit()

    module = _load_migration_0064()
    original_assert = module._assert_registry_target

    def operator_edit_between_preflight_and_write(migration_conn, to_tag):
        migration_conn.execute(
            sa.text("UPDATE services SET queue_tag = 'ecg' WHERE code = 'LAB_CA'")
        )
        return original_assert(migration_conn, to_tag)

    module._assert_registry_target = operator_edit_between_preflight_and_write

    trans = conn.begin()
    with pytest.raises(RuntimeError, match="concurrently modified"):
        module.upgrade_with_conn(conn)

    # NOT overwritten: the guarded predicate refused the foreign source
    # state; rows the migration already wrote before the abort are still
    # in THIS transaction (to be discarded by the caller's rollback).
    assert _service_state(conn, "LAB_CA").queue_tag == "ecg"
    assert _service_state(conn, "L03").queue_tag == "lab"
    trans.rollback()

    # Atomic: the caller's rollback discards EVERY migration write — no
    # partial application of the map.
    for code in _RETAG_CODES:
        assert _service_state(conn, code).queue_tag == "general", code
    for code in _ASSIGN_CODES:
        assert _service_state(conn, code).doctor_id is None


def test_upgrade_treats_a_concurrent_same_target_edit_as_a_proven_no_op(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """rowcount=0 alone justifies NOTHING (the 3995689409 ruling): when
    the operator concurrently moved the row to the exact post-state, the
    guard re-reads and PROVES the no-op before continuing; the migration
    completes and the remaining map applies."""
    conn = _scratch()
    _seed_synthetic_world(conn)
    _seed_decided_services(conn)
    conn.commit()

    module = _load_migration_0064()
    original_assert = module._assert_registry_target

    def operator_applies_the_same_target(migration_conn, to_tag):
        migration_conn.execute(
            sa.text("UPDATE services SET queue_tag = 'lab' WHERE code = 'LAB_CA'")
        )
        return original_assert(migration_conn, to_tag)

    module._assert_registry_target = operator_applies_the_same_target

    module.upgrade_with_conn(conn)  # must NOT raise
    conn.commit()

    assert "proven idempotent no-op" in capsys.readouterr().out
    for code in _RETAG_CODES:
        assert _service_state(conn, code).queue_tag == "lab", code
    for code in _ASSIGN_CODES:
        assert _service_state(conn, code).doctor_id == _TARGET_DOCTOR_ID


def test_assign_doctor_guard_matches_the_null_source_state_and_refuses_foreign_edits() -> None:
    """NULL comparison semantics (the 3995689409 ruling): ``doctor_id =
    :expected`` never matches NULL, so the guarded assign UPDATE carries
    an explicit IS NULL arm. K01 sits on the NULL pre-state — a clean
    apply must match it; a concurrent foreign doctor (99) must make the
    guard abort without writing the target over it."""
    conn = _scratch()
    _seed_synthetic_world(conn)
    _seed_decided_services(conn)
    conn.commit()

    module = _load_migration_0064()
    original_assert = module._assert_target_doctor

    def operator_sets_a_foreign_doctor(migration_conn, doctor_id, _user=None):
        migration_conn.execute(
            sa.text("UPDATE services SET doctor_id = 99 WHERE code = 'K01'")
        )
        return original_assert(migration_conn, doctor_id)

    module._assert_target_doctor = operator_sets_a_foreign_doctor

    trans = conn.begin()
    with pytest.raises(RuntimeError, match="concurrently modified"):
        module.upgrade_with_conn(conn)

    # the operator's foreign doctor survived the refused write; the 33
    # retags the migration had already written sit in the transaction
    assert _service_state(conn, "K01").doctor_id == 99
    assert _service_state(conn, "L03").queue_tag == "lab"
    trans.rollback()

    # and the caller's rollback discards them all
    assert _service_state(conn, "K01").doctor_id is None
    for code in _RETAG_CODES:
        assert _service_state(conn, code).queue_tag == "general", code


@pytest.fixture
def cutover_pg_engine():
    """An isolated PostgreSQL schema with the minimal cutover tables —
    the two-connection race proof (3995689409): one connection runs the
    migration, a SECOND connection plays the operator, and the final
    state is verified from a fresh third read."""
    database_url = os.environ.get("DATABASE_URL", "sqlite:///:memory:")
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        pytest.skip("guarded-write race proof requires PostgreSQL")
    if os.environ.get("CI", "").lower() != "true" and not (
        url.database or ""
    ).startswith("clinic_test"):
        pytest.skip("use CI or an explicitly disposable clinic_test database")

    schema = "test_cutover_race_" + uuid.uuid4().hex
    admin_engine = create_engine(url, pool_pre_ping=True)
    with admin_engine.begin() as connection:
        connection.execute(CreateSchema(schema))

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={
            "options": (
                f"-csearch_path={schema} "
                "-cstatement_timeout=10000 -clock_timeout=8000"
            )
        },
    )
    try:
        _create_cutover_tables(engine)
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin_engine.dispose()


@pytest.mark.integration
@pytest.mark.migration
def test_pg_two_connections_operator_edit_is_never_overwritten_and_migration_rolls_back_whole_map(
    cutover_pg_engine,
) -> None:
    """The MANDATORY PostgreSQL proof (thread 3995689409): the operator
    CHANGES the row between the migration's preflight and its write
    attempt, in a SEPARATE COMMITTED transaction. His edit must survive;
    the migration's own changes must roll back ENTIRELY — verified in the
    DATABASE by a fresh third read, not by HTTP codes or return values."""
    with cutover_pg_engine.connect() as setup_conn:
        _seed_synthetic_world(setup_conn)
        _seed_decided_services(setup_conn)
        setup_conn.commit()

    module = _load_migration_0064()
    original_assert = module._assert_registry_target

    def operator_edits_between_preflight_and_write(migration_conn, to_tag):
        # connection B: the operator's own COMMITTED transaction, landing
        # exactly between the pre-state check and the guarded write
        with cutover_pg_engine.connect() as operator_conn:
            with operator_conn.begin():
                operator_conn.execute(
                    sa.text(
                        "UPDATE services SET queue_tag = 'ecg'"
                        " WHERE code = 'LAB_CA'"
                    )
                )
        return original_assert(migration_conn, to_tag)

    module._assert_registry_target = operator_edits_between_preflight_and_write

    with cutover_pg_engine.connect() as migration_conn:
        migration_trans = migration_conn.begin()
        with pytest.raises(RuntimeError, match="concurrently modified"):
            module.upgrade_with_conn(migration_conn)
        migration_trans.rollback()

    # fresh third read: the operator's edit is the ONLY surviving change
    with cutover_pg_engine.connect() as verify_conn:
        assert _service_state(verify_conn, "LAB_CA").queue_tag == "ecg"
        for code in _RETAG_CODES:
            if code != "LAB_CA":
                assert _service_state(verify_conn, code).queue_tag == "general", code
        for code in _ASSIGN_CODES:
            assert _service_state(verify_conn, code).doctor_id is None


@pytest.mark.integration
@pytest.mark.migration
def test_pg_two_connections_concurrent_same_target_is_a_proven_no_op(
    cutover_pg_engine,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """PostgreSQL counterpart: the operator concurrently applies the
    SAME decision (moves LAB_CA onto the 'lab' target) in his own
    committed transaction. The guarded UPDATE matches zero rows, the
    guard re-reads and PROVES the exact post-state, and the migration
    completes the rest of the map."""
    with cutover_pg_engine.connect() as setup_conn:
        _seed_synthetic_world(setup_conn)
        _seed_decided_services(setup_conn)
        setup_conn.commit()

    module = _load_migration_0064()
    original_assert = module._assert_registry_target

    def operator_applies_the_same_target(migration_conn, to_tag):
        with cutover_pg_engine.connect() as operator_conn:
            with operator_conn.begin():
                operator_conn.execute(
                    sa.text(
                        "UPDATE services SET queue_tag = 'lab'"
                        " WHERE code = 'LAB_CA'"
                    )
                )
        return original_assert(migration_conn, to_tag)

    module._assert_registry_target = operator_applies_the_same_target

    with cutover_pg_engine.connect() as migration_conn:
        migration_trans = migration_conn.begin()
        module.upgrade_with_conn(migration_conn)  # must NOT raise
        migration_trans.commit()

    assert "proven idempotent no-op" in capsys.readouterr().out
    with cutover_pg_engine.connect() as verify_conn:
        for code in _RETAG_CODES:
            assert _service_state(verify_conn, code).queue_tag == "lab", code
        for code in _ASSIGN_CODES:
            assert _service_state(verify_conn, code).doctor_id == _TARGET_DOCTOR_ID


@pytest.mark.integration
@pytest.mark.migration
def test_pg_two_connections_assign_guard_null_semantics_foreign_doctor(
    cutover_pg_engine,
) -> None:
    """PostgreSQL counterpart for the assign half: K01 sits on the NULL
    pre-state (the ``= :expected`` arm alone would never match it); the
    operator sets a foreign doctor (99) between preflight and write in
    his own committed transaction — the guard refuses, the operator's
    row survives and the whole map (retags included) rolls back."""
    with cutover_pg_engine.connect() as setup_conn:
        _seed_synthetic_world(setup_conn)
        _seed_decided_services(setup_conn)
        setup_conn.commit()

    module = _load_migration_0064()
    original_assert = module._assert_target_doctor

    def operator_sets_a_foreign_doctor(migration_conn, doctor_id):
        with cutover_pg_engine.connect() as operator_conn:
            with operator_conn.begin():
                operator_conn.execute(
                    sa.text(
                        "UPDATE services SET doctor_id = 99 WHERE code = 'K01'"
                    )
                )
        return original_assert(migration_conn, doctor_id)

    module._assert_target_doctor = operator_sets_a_foreign_doctor

    with cutover_pg_engine.connect() as migration_conn:
        migration_trans = migration_conn.begin()
        with pytest.raises(RuntimeError, match="concurrently modified"):
            module.upgrade_with_conn(migration_conn)
        migration_trans.rollback()

    with cutover_pg_engine.connect() as verify_conn:
        assert _service_state(verify_conn, "K01").doctor_id == 99
        for code in _RETAG_CODES:
            assert _service_state(verify_conn, code).queue_tag == "general", code
        assert _service_state(verify_conn, "K11").doctor_id is None


def test_embedded_decisions_match_the_operator_map_evidence() -> None:
    """Parity pin: the embedded tables ARE the completed-map snapshot
    (evidence/stage_e_operator_map_20260912.json) — they cannot drift,
    INCLUDING the snapshot service ids (thread 3995689408: the identity
    is part of the approved decision, not a code-only key)."""
    payload = json.loads(OPERATOR_MAP.read_text(encoding="utf-8"))
    items = payload["items"]
    map_retags = {
        item["code"]: (
            item["id"],
            item["queue_tag"],
            item["target_queue_tag"],
        )
        for item in items
        if item["surface"] == "service" and item["decision"] == "retag_resource"
    }
    map_assigns = {
        item["code"]: (
            item["id"],
            item["target_doctor_id"],
            item["doctor_id"],
            item["queue_tag"],
        )
        for item in items
        if item["surface"] == "service" and item["decision"] == "assign_doctor"
    }
    map_disables = {
        item["code"]: item["id"]
        for item in items
        if item["surface"] == "service" and item["decision"] == "disable_service"
    }
    map_profiles = {
        item["key"]: item["decision"]
        for item in items
        if item["surface"] == "queue_profile"
    }

    module = _load_migration_0064()
    assert {
        code: (snapshot_id, from_tag, to_tag)
        for snapshot_id, code, from_tag, to_tag in module._RETAG_DECISIONS
    } == map_retags
    # the 2026-09-12 evidence file decides exactly K01/K11 on the doctor
    # axis; the O10/O20/S10 assignments come from the 2026-09-15
    # REFINEMENT file (pinned by its own test below) and must NOT appear
    # in this original-map comparison.
    embedded_assigns = {
        code: (snapshot_id, target, original, snapshot_tag, expected_user, set_requires)
        for (
            snapshot_id,
            code,
            target,
            original,
            expected_user,
            snapshot_tag,
            set_requires,
        ) in module._ASSIGN_DOCTOR_DECISIONS
    }
    # the original 2026-09-12 map decides exactly K01/K11 (no requires_doctor
    # flip, no user-linkage pin there) — the refinement entries are pinned by
    # their own test
    assert {
        code: (entry[0], entry[1], entry[2], entry[3])
        for code, entry in embedded_assigns.items()
        if code in map_assigns
    } == map_assigns
    assert all(
        entry[4] is None and entry[5] is None
        for code, entry in embedded_assigns.items()
        if code in map_assigns
    )
    assert module._DISABLE_DECISIONS == ()
    assert map_disables == {}
    assert module._PROFILE_DECISIONS == map_profiles
    # the snapshot really is the 36-decided production state
    assert len(map_retags) == 33
    assert len(map_assigns) == 2
    assert sum(1 for item in items if item["decision"] is None) == 21
    # the seed mirrors the same identities (the scratch fixtures and
    # the embedded map cannot drift either)
    assert _RETAG_SNAPSHOT_IDS == {
        code: snapshot_id for snapshot_id, code, _f, _t in module._RETAG_DECISIONS
    }
    assert _ASSIGN_SNAPSHOT_IDS == {
        code: snapshot_id
        for (
            snapshot_id,
            code,
            _target,
            _original,
            _expected_user,
            _snapshot_tag,
            _set_requires,
        ) in module._ASSIGN_DOCTOR_DECISIONS
    }


# ===================== B. runtime fail-closed (db_session) =====================


def test_owner_configuration_error_is_a_value_error() -> None:
    """The dedicated type subclasses ValueError so the existing
    endpoint handlers (``except ValueError -> 4xx``) surface it to the
    operator with the message instead of a bare 500."""
    error = owner_configuration_error(queue_tag="procedures")
    assert isinstance(error, ValueError)
    assert isinstance(error, QueueOwnerConfigurationError)
    message = str(error)
    assert "procedures" in message
    assert "D-08" in message
    # the message names the three operator resolutions
    for option in ("Назначьте врача", "queue_tag", "отключите услугу"):
        assert option in message


def test_single_active_service_doctor_semantics(db_session: Session) -> None:
    """Zero owners -> None (fail-closed surface), one eligible owner ->
    the id, two owners -> None (the PR-26 per-doctor contract, never a
    guess). The ineligible-owner rejection is pinned separately (the
    Codex round-1 P2 stale-assignment test below)."""
    # zero owners
    _make_service(db_session, code="P03", queue_tag="procedures", name="УФО терапия")
    assert single_active_service_doctor(db_session, "procedures") is None

    # exactly one explicit doctor
    doc_user = _make_user(db_session, username="dr_cosm", role="doctor")
    doc = _make_doctor(db_session, user_id=doc_user.id, specialty="procedures")
    service = _make_service(
        db_session, code="C03", queue_tag="procedures", name="Мезотерапия"
    )
    service.doctor_id = doc.id
    db_session.commit()
    assert single_active_service_doctor(db_session, "procedures") == doc.id

    # two distinct owners -> ambiguous, never guessed
    doc2_user = _make_user(db_session, username="dr_cosm2", role="doctor")
    doc2 = _make_doctor(db_session, user_id=doc2_user.id, specialty="procedures")
    service2 = _make_service(
        db_session, code="C06", queue_tag="procedures", name="Чистка лица"
    )
    service2.doctor_id = doc2.id
    db_session.commit()
    assert single_active_service_doctor(db_session, "procedures") is None


def test_single_active_service_doctor_rejects_stale_assignment(
    db_session: Session,
) -> None:
    """Codex round-1 P2: the single candidate must be an ELIGIBLE real
    owner — an inactive Doctor row or an internal 'Resource' sentinel
    fails closed (None), so no queue is silently built on it."""
    from app.crud.queue_owner_policy import eligible_real_doctor

    # an inactive doctor
    doc_user = _make_user(db_session, username="dr_stale", role="doctor")
    doc = _make_doctor(db_session, user_id=doc_user.id, specialty="cardio")
    doc.active = False
    db_session.commit()
    service = _make_service(
        db_session,
        code="K09",
        queue_tag="cardio",
        name="Старая привязка",
        doctor_id=doc.id,
    )
    assert service.doctor_id == doc.id
    assert single_active_service_doctor(db_session, "cardio") is None
    assert not eligible_real_doctor(db_session, doc.id)

    # an internal Resource sentinel assigned to a service (drift shape)
    res_user = _make_user(db_session, username="lab_resource", role="Resource")
    res_doc = _make_doctor(db_session, user_id=res_user.id, specialty="cardio")
    _make_service(
        db_session,
        code="K099",
        queue_tag="cardio",
        name="Дрейф",
        doctor_id=res_doc.id,
    )
    db_session.commit()
    assert not eligible_real_doctor(db_session, res_doc.id)


def test_batch_resolver_fails_closed_with_synthetics_present(
    db_session: Session,
) -> None:
    """D-08 hard pin: the synthetic users/doctors EXIST in the database
    (as on production until RQ-15.d) and are NEVER consulted — the old
    _BATCH_CREATE_RESOURCE_MAPPING would have silently routed this
    surface onto general_resource."""
    from app.services.batch_patient_service import BatchPatientService, EntryAction

    # the three 0055 synthetics, exactly as production holds them
    gen_user = _make_user(db_session, username="general_resource", role="Resource")
    _make_doctor(db_session, user_id=gen_user.id, specialty="general")
    lab_user = _make_user(db_session, username="lab_resource", role="Resource")
    _make_doctor(db_session, user_id=lab_user.id, specialty="lab")

    _make_service(
        db_session,
        code="P03",
        queue_tag="procedures",
        name="УФО терапия",
        requires_doctor=True,
    )
    svc = BatchPatientService(db_session)
    with pytest.raises(QueueOwnerConfigurationError, match="D-08"):
        svc._resolve_create_action_specialist_id(
            action=EntryAction(id=None, action="create", entry_type="online_queue"),
            queue_tag="procedures",
            service=None,
        )


def test_batch_resolver_source_has_no_synthetic_mapping() -> None:
    """Source pin: the fallback vocabulary is gone from the module —
    the mapping TABLE (the ``=``-assignment) and its lookup variable
    must not re-enter (docstrings explaining the removal are fine)."""
    source = BATCH_SERVICE.read_text(encoding="utf-8")
    assert "_BATCH_CREATE_RESOURCE_MAPPING =" not in source
    assert "resource_username" not in source


def test_morning_assign_raises_for_unowned_tag(db_session: Session) -> None:
    """The pre-2E silent None (the QD-0 root cause) is now an explicit
    configuration error — synthetics present, still never consulted."""
    from app.services.morning_assignment import MorningAssignmentService

    gen_user = _make_user(db_session, username="general_resource", role="Resource")
    _make_doctor(db_session, user_id=gen_user.id, specialty="general")
    service = _make_service(
        db_session,
        code="D01",
        queue_tag="dermatology",
        name="Консультация дерматолога-косметолога",
        requires_doctor=True,
    )
    visit = _make_visit(db_session)
    _link_visit_service(db_session, visit, service)

    with pytest.raises(QueueOwnerConfigurationError, match="dermatology"):
        MorningAssignmentService(db_session).prepare_wizard_queue_assignment(
            visit, "dermatology", _DAY
        )


def test_morning_assign_resolves_visit_service_doctor(db_session: Session) -> None:
    """K01 after the map application: the visit carries no doctor, the
    service does — the explicit owner wins, the queue is the doctor's
    (the cutover outcome for cardio consults)."""
    from app.services.morning_assignment import MorningAssignmentService

    doc_user = _make_user(db_session, username="dr_kardio", role="doctor")
    doc = _make_doctor(db_session, user_id=doc_user.id, specialty="cardio")
    service = _make_service(
        db_session,
        code="K01",
        queue_tag="cardio",
        name="Консультация кардиолога",
        requires_doctor=True,
        doctor_id=doc.id,
    )
    visit = _make_visit(db_session)  # NO visit doctor
    _link_visit_service(db_session, visit, service)

    prepared = MorningAssignmentService(db_session).prepare_wizard_queue_assignment(
        visit, "cardio", _DAY
    )
    assert prepared is not None
    assert prepared.create_handoff is not None
    queue = prepared.create_handoff.create_entry_kwargs["daily_queue"]
    assert queue.specialist_id == doc.id
    assert queue.queue_resource_id is None


def test_morning_assign_reuses_the_resolved_owners_existing_surface(
    db_session: Session,
) -> None:
    """QD-2E surface-reuse ruling (PR review thread 3995689410 — the
    FINAL decision supersedes the old borrowing): an already-opened
    queue is the surface ONLY for its OWN owner. The visit resolves
    dr_stom (the visit doctor) and the per-doctor get_or_create returns
    that doctor's existing queue; an UNOWNED visit never adopts the
    queue's specialist — it fails closed with the D-08 error instead."""
    from app.services.morning_assignment import MorningAssignmentService

    doc_user = _make_user(db_session, username="dr_stom", role="doctor")
    doc = _make_doctor(db_session, user_id=doc_user.id, specialty="stomatology")
    service = _make_service(
        db_session,
        code="S01",
        queue_tag="stomatology",
        name="Консультация стоматолога",
        requires_doctor=True,
    )
    existing = DailyQueue(
        day=_DAY, specialist_id=doc.id, queue_tag="stomatology", active=True
    )
    db_session.add(existing)
    db_session.commit()

    visit = _make_visit(db_session, doctor_id=doc.id)
    _link_visit_service(db_session, visit, service)
    prepared = MorningAssignmentService(db_session).prepare_wizard_queue_assignment(
        visit, "stomatology", _DAY
    )
    assert prepared is not None
    assert prepared.create_handoff is not None
    queue = prepared.create_handoff.create_entry_kwargs["daily_queue"]
    assert queue.id == existing.id

    # the superseded borrowing: an unowned visit (no visit doctor, the
    # service carries none) must NOT adopt the dentist's queue
    unowned_visit = _make_visit(db_session)
    _link_visit_service(db_session, unowned_visit, service)
    with pytest.raises(QueueOwnerConfigurationError):
        MorningAssignmentService(db_session).prepare_wizard_queue_assignment(
            unowned_visit, "stomatology", _DAY
        )


def test_prepare_new_entry_goes_to_resolved_doctors_queue(
    db_session: Session,
) -> None:
    """Codex round-2 P1: with an explicit owner resolved from the visit's
    services (K01 -> doctor 10), a NEW entry is created on THAT doctor's
    queue even when the tag surface already holds another doctor's
    (day, tag) queue — never piggybacked onto doctor 11's queue."""
    from app.services.morning_assignment import MorningAssignmentService

    doc_user = _make_user(db_session, username="dr_kardio_10", role="doctor")
    doc10 = _make_doctor(db_session, user_id=doc_user.id, specialty="cardio")
    other_user = _make_user(db_session, username="dr_kardio_11", role="doctor")
    doc11 = _make_doctor(db_session, user_id=other_user.id, specialty="cardio")
    service = _make_service(
        db_session,
        code="K01",
        queue_tag="cardio",
        name="Консультация кардиолога",
        requires_doctor=True,
        doctor_id=doc10.id,
    )
    # doctor 11 already opened the sole (day, tag) cardio queue
    foreign_queue = DailyQueue(
        day=_DAY, specialist_id=doc11.id, queue_tag="cardio", active=True
    )
    db_session.add(foreign_queue)
    db_session.commit()

    visit = _make_visit(db_session)  # NO visit doctor
    _link_visit_service(db_session, visit, service)

    prepared = MorningAssignmentService(db_session).prepare_wizard_queue_assignment(
        visit, "cardio", _DAY
    )
    assert prepared is not None
    assert prepared.create_handoff is not None
    queue = prepared.create_handoff.create_entry_kwargs["daily_queue"]
    assert queue.specialist_id == doc10.id
    assert queue.id != foreign_queue.id


def test_prepare_multiple_tag_surfaces_prefer_owners_queue(
    db_session: Session,
) -> None:
    """Codex round-3 P1: the PR-26 multi-doctor topology (BOTH doctors
    hold active (day, tag) cardio queues) must not raise the ambiguity
    error for a patient without an existing claim — the resolved owner's
    queue is the surface for the new entry."""
    from app.services.morning_assignment import MorningAssignmentService

    doc_user = _make_user(db_session, username="dr_kardio_a", role="doctor")
    doc10 = _make_doctor(db_session, user_id=doc_user.id, specialty="cardio")
    other_user = _make_user(db_session, username="dr_kardio_b", role="doctor")
    doc11 = _make_doctor(db_session, user_id=other_user.id, specialty="cardio")
    service = _make_service(
        db_session,
        code="K01",
        queue_tag="cardio",
        name="Консультация кардиолога",
        requires_doctor=True,
        doctor_id=doc10.id,
    )
    db_session.add_all(
        [
            DailyQueue(
                day=_DAY, specialist_id=doc10.id, queue_tag="cardio", active=True
            ),
            DailyQueue(
                day=_DAY, specialist_id=doc11.id, queue_tag="cardio", active=True
            ),
        ]
    )
    db_session.commit()

    visit = _make_visit(db_session)  # NO visit doctor
    _link_visit_service(db_session, visit, service)

    prepared = MorningAssignmentService(db_session).prepare_wizard_queue_assignment(
        visit, "cardio", _DAY
    )
    assert prepared is not None
    assert prepared.create_handoff is not None
    queue = prepared.create_handoff.create_entry_kwargs["daily_queue"]
    assert queue.specialist_id == doc10.id


def test_confirmation_ticket_carries_resolved_owner(
    db_session: Session,
) -> None:
    """Codex round-2 P2: the doctorless K01 confirmation ticket names the
    resolved service doctor (the cardiologist), not «Без врача»."""
    from app.services.visit_confirmation_service import VisitConfirmationService

    doc_user = _make_user(db_session, username="dr_kardio_t", role="doctor")
    doc_user.full_name = "Кардиолог Тест"
    db_session.commit()
    doc = _make_doctor(db_session, user_id=doc_user.id, specialty="cardio")
    service = _make_service(
        db_session,
        code="K01",
        queue_tag="cardio",
        name="Консультация кардиолога",
        requires_doctor=True,
        doctor_id=doc.id,
    )
    visit = _make_visit(db_session)  # NO visit doctor
    _link_visit_service(db_session, visit, service)

    _numbers, tickets = VisitConfirmationService(
        db_session
    )._assign_queue_numbers_on_confirmation(visit)
    assert len(tickets) == 1
    assert tickets[0]["doctor_name"] == "Кардиолог Тест"


def test_visit_confirmation_raises_on_unowned_tag(db_session: Session) -> None:
    """The pre-2E silent ``continue`` (a confirmed visit with NO queue
    number, nobody knows why) is now an explicit configuration error."""
    from app.services.visit_confirmation_service import (
        VisitConfirmationDomainError,
        VisitConfirmationService,
    )

    gen_user = _make_user(db_session, username="general_resource", role="Resource")
    _make_doctor(db_session, user_id=gen_user.id, specialty="general")
    service = _make_service(
        db_session,
        code="O10",
        queue_tag="ultrason",
        name="УЗИ",
        requires_doctor=False,
    )
    visit = _make_visit(db_session)
    _link_visit_service(db_session, visit, service)

    svc = VisitConfirmationService(db_session)
    # QD-2E (Codex round-3 P2): ошибка владельца — ДОМЕННАЯ ошибка
    # подтверждения (422 + причина), не голый ValueError/500 у обёрток
    with pytest.raises(VisitConfirmationDomainError) as excinfo:
        svc._assign_queue_numbers_on_confirmation(visit)
    assert excinfo.value.status_code == 422
    assert "ultrason" in excinfo.value.detail
    assert "D-08" in excinfo.value.detail


def test_visit_confirmation_registry_tag_keeps_working(db_session: Session) -> None:
    """The preserved path: a lab service confirms onto the resource
    axis exactly as QD-2C shipped it."""
    from app.services.visit_confirmation_service import VisitConfirmationService

    resource = QueueResource(code="lab", queue_tag="lab", display_name="Лаборатория")
    db_session.add(resource)
    db_session.commit()
    service = _make_service(db_session, code="L14", queue_tag="lab", name="Гемоглобин")
    visit = _make_visit(db_session)
    _link_visit_service(db_session, visit, service)

    numbers, _tickets = VisitConfirmationService(
        db_session
    )._assign_queue_numbers_on_confirmation(visit)
    assert len(numbers) == 1
    assert numbers[0]["queue_tag"] == "lab"
    queue = (
        db_session.query(DailyQueue)
        .filter(DailyQueue.id == numbers[0]["queue_id"])
        .one()
    )
    assert queue.queue_resource_id == resource.id
    assert queue.specialist_id is None


def test_confirmation_reuses_resource_claim_when_visit_has_doctor(
    db_session: Session,
    monkeypatch,
) -> None:
    """A visit doctor must not turn a registry tag into a doctor queue."""
    from app.services import visit_confirmation_service as confirmation_module
    from app.services.visit_confirmation_service import VisitConfirmationService

    # The service resolves the queue day internally (clinic_today); the
    # file's fixed _DAY world must stay date-stable (the QD-2A timezone
    # flake precedent — same monkeypatch pattern as
    # test_queue_resource_runtime_switch.py).
    monkeypatch.setattr(confirmation_module, "_clinic_today", lambda _db: _DAY)

    resource = QueueResource(code="lab", queue_tag="lab", display_name="Лаборатория")
    doctor_user = _make_user(
        db_session, username="dr_with_lab_visit", role="doctor"
    )
    doctor = _make_doctor(
        db_session, user_id=doctor_user.id, specialty="cardiology"
    )
    db_session.add(resource)
    db_session.commit()
    service = _make_service(
        db_session, code="L14", queue_tag="lab", name="Гемоглобин"
    )
    visit = _make_visit(db_session, doctor_id=doctor.id)
    _link_visit_service(db_session, visit, service)
    resource_queue = DailyQueue(
        day=_DAY,
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag="lab",
        active=True,
    )
    db_session.add(resource_queue)
    db_session.commit()
    existing_claim = OnlineQueueEntry(
        queue_id=resource_queue.id,
        number=8,
        patient_id=visit.patient_id,
        source="online",
        status="waiting",
    )
    db_session.add(existing_claim)
    db_session.commit()

    numbers, _tickets = VisitConfirmationService(
        db_session
    )._assign_queue_numbers_on_confirmation(visit)

    assert numbers == [
        {"queue_tag": "lab", "number": 8, "queue_id": resource_queue.id}
    ]
    assert existing_claim.visit_id == visit.id
    assert (
        db_session.query(OnlineQueueEntry)
        .join(DailyQueue, DailyQueue.id == OnlineQueueEntry.queue_id)
        .filter(DailyQueue.day == _DAY, DailyQueue.queue_tag == "lab")
        .count()
        == 1
    )


def test_confirmation_reuses_resource_claim_after_registry_deactivation(
    db_session: Session,
    monkeypatch,
) -> None:
    """A live resource queue remains the routing surface for its day."""
    from app.services import visit_confirmation_service as confirmation_module
    from app.services.visit_confirmation_service import VisitConfirmationService

    monkeypatch.setattr(confirmation_module, "_clinic_today", lambda _db: _DAY)

    resource = QueueResource(code="lab", queue_tag="lab", display_name="Лаборатория")
    db_session.add(resource)
    db_session.commit()
    service = _make_service(
        db_session, code="L14", queue_tag="lab", name="Гемоглобин"
    )
    visit = _make_visit(db_session)
    _link_visit_service(db_session, visit, service)
    resource_queue = DailyQueue(
        day=_DAY,
        specialist_id=None,
        queue_resource_id=resource.id,
        queue_tag="lab",
        active=True,
    )
    db_session.add(resource_queue)
    db_session.commit()
    resource.active = False
    existing_claim = OnlineQueueEntry(
        queue_id=resource_queue.id,
        number=9,
        patient_id=visit.patient_id,
        source="online",
        status="waiting",
    )
    db_session.add(existing_claim)
    db_session.commit()

    numbers, _tickets = VisitConfirmationService(
        db_session
    )._assign_queue_numbers_on_confirmation(visit)

    assert numbers == [
        {"queue_tag": "lab", "number": 9, "queue_id": resource_queue.id}
    ]
    assert existing_claim.visit_id == visit.id
    assert (
        db_session.query(OnlineQueueEntry)
        .join(DailyQueue, DailyQueue.id == OnlineQueueEntry.queue_id)
        .filter(DailyQueue.day == _DAY, DailyQueue.queue_tag == "lab")
        .count()
        == 1
    )


def test_visit_confirmation_resolves_mapped_service_doctor(
    db_session: Session,
) -> None:
    """Codex round-1 P2: a doctorless visit whose service carries the
    operator-map doctor (K01 -> the cardiologist) confirms on THAT
    doctor's queue — the ownership entry points stay consistent."""
    from app.services.visit_confirmation_service import VisitConfirmationService

    doc_user = _make_user(db_session, username="dr_kardio_c", role="doctor")
    doc = _make_doctor(db_session, user_id=doc_user.id, specialty="cardio")
    service = _make_service(
        db_session,
        code="K01",
        queue_tag="cardio",
        name="Консультация кардиолога",
        requires_doctor=True,
        doctor_id=doc.id,
    )
    visit = _make_visit(db_session)  # NO visit doctor
    _link_visit_service(db_session, visit, service)

    numbers, _tickets = VisitConfirmationService(
        db_session
    )._assign_queue_numbers_on_confirmation(visit)
    assert len(numbers) == 1
    assert numbers[0]["queue_tag"] == "cardio"
    queue = (
        db_session.query(DailyQueue)
        .filter(DailyQueue.id == numbers[0]["queue_id"])
        .one()
    )
    assert queue.specialist_id == doc.id
    assert queue.queue_resource_id is None


def test_confirmation_new_entry_goes_to_resolved_doctors_queue(
    db_session: Session,
) -> None:
    """Codex round-4 P1: the doctorless K01 confirmation with doctor 11
    holding the only active (day, tag) cardio queue — the new entry
    lands on the resolved cardiologist's (doctor 10's) queue, never
    piggybacked onto a foreign doctor's tag-only surface."""
    from app.services.visit_confirmation_service import VisitConfirmationService

    doc_user = _make_user(db_session, username="dr_kardio_r4", role="doctor")
    doc10 = _make_doctor(db_session, user_id=doc_user.id, specialty="cardio")
    other_user = _make_user(db_session, username="dr_kardio_r4b", role="doctor")
    doc11 = _make_doctor(db_session, user_id=other_user.id, specialty="cardio")
    service = _make_service(
        db_session,
        code="K01",
        queue_tag="cardio",
        name="Консультация кардиолога",
        requires_doctor=True,
        doctor_id=doc10.id,
    )
    foreign_queue = DailyQueue(
        day=_DAY, specialist_id=doc11.id, queue_tag="cardio", active=True
    )
    db_session.add(foreign_queue)
    db_session.commit()

    visit = _make_visit(db_session)  # NO visit doctor
    _link_visit_service(db_session, visit, service)

    numbers, _tickets = VisitConfirmationService(
        db_session
    )._assign_queue_numbers_on_confirmation(visit)
    assert len(numbers) == 1
    queue = (
        db_session.query(DailyQueue)
        .filter(DailyQueue.id == numbers[0]["queue_id"])
        .one()
    )
    assert queue.specialist_id == doc10.id
    assert queue.id != foreign_queue.id


def test_confirmation_rejects_foreign_owner_claim_before_creating_queue(
    db_session: Session,
    monkeypatch,
) -> None:
    """A same-patient claim is found across the tag before queue creation.

    The existing claim belongs to another doctor, so confirmation reports an
    owner conflict instead of allocating a second active ticket or creating an
    otherwise unused queue for the newly resolved doctor.
    """
    from app.services import visit_confirmation_service as confirmation_module
    from app.services.visit_confirmation_service import (
        VisitConfirmationDomainError,
        VisitConfirmationService,
    )

    monkeypatch.setattr(confirmation_module, "_clinic_today", lambda _db: _DAY)

    owner_user = _make_user(db_session, username="dr_kardio_r5", role="doctor")
    resolved_owner = _make_doctor(
        db_session, user_id=owner_user.id, specialty="cardio"
    )
    foreign_user = _make_user(
        db_session, username="dr_kardio_r5b", role="doctor"
    )
    foreign_owner = _make_doctor(
        db_session, user_id=foreign_user.id, specialty="cardio"
    )
    service = _make_service(
        db_session,
        code="K01",
        queue_tag="cardio",
        name="Консультация кардиолога",
        requires_doctor=True,
        doctor_id=resolved_owner.id,
    )
    foreign_queue = DailyQueue(
        day=_DAY,
        specialist_id=foreign_owner.id,
        queue_tag="cardio",
        active=True,
    )
    db_session.add(foreign_queue)
    db_session.commit()

    visit = _make_visit(db_session)  # NO visit doctor
    _link_visit_service(db_session, visit, service)
    existing_claim = OnlineQueueEntry(
        queue_id=foreign_queue.id,
        number=7,
        patient_id=visit.patient_id,
        source="online",
        status="waiting",
    )
    db_session.add(existing_claim)
    db_session.commit()

    with pytest.raises(VisitConfirmationDomainError) as excinfo:
        VisitConfirmationService(db_session)._assign_queue_numbers_on_confirmation(
            visit
        )

    assert excinfo.value.status_code == 409
    assert "different owner" in excinfo.value.detail
    assert existing_claim.visit_id is None
    assert (
        db_session.query(OnlineQueueEntry)
        .join(DailyQueue, DailyQueue.id == OnlineQueueEntry.queue_id)
        .filter(
            DailyQueue.day == _DAY,
            DailyQueue.queue_tag == "cardio",
            DailyQueue.active.is_(True),
            OnlineQueueEntry.status.in_(
                ("waiting", "called", "in_service", "diagnostics")
            ),
        )
        .count()
        == 1
    )
    assert (
        db_session.query(DailyQueue)
        .filter(
            DailyQueue.day == _DAY,
            DailyQueue.queue_tag == "cardio",
            DailyQueue.specialist_id == resolved_owner.id,
        )
        .count()
        == 0
    )


def test_confirmation_keeps_multi_tag_allocation_atomic_on_late_owner_error(
    db_session: Session,
    monkeypatch,
) -> None:
    """A later tag failure must leave the first flushed ticket rollbackable."""
    from app.services import visit_confirmation_service as confirmation_module
    from app.services.visit_confirmation_service import (
        VisitConfirmationDomainError,
        VisitConfirmationService,
    )

    monkeypatch.setattr(confirmation_module, "_clinic_today", lambda _db: _DAY)

    owner_user = _make_user(db_session, username="dr_atomic_confirm", role="doctor")
    owner = _make_doctor(
        db_session, user_id=owner_user.id, specialty="cardiology"
    )
    owned_service = _make_service(
        db_session,
        code="K01",
        queue_tag="a_cardio",
        name="Консультация кардиолога",
        requires_doctor=True,
        doctor_id=owner.id,
    )
    unowned_service = _make_service(
        db_session,
        code="P08",
        queue_tag="z_unowned",
        name="Неразмеченная процедура",
        requires_doctor=True,
    )
    visit = _make_visit(db_session)
    _link_visit_service(db_session, visit, owned_service)
    _link_visit_service(db_session, visit, unowned_service)

    with pytest.raises(VisitConfirmationDomainError) as excinfo:
        VisitConfirmationService(db_session)._assign_queue_numbers_on_confirmation(
            visit
        )

    assert excinfo.value.status_code == 422
    db_session.rollback()
    assert (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == visit.patient_id)
        .count()
        == 0
    )
    assert (
        db_session.query(DailyQueue)
        .filter(
            DailyQueue.day == _DAY,
            DailyQueue.queue_tag.in_(("a_cardio", "z_unowned")),
        )
        .count()
        == 0
    )


def test_confirmation_multiple_service_doctors_is_domain_error(
    db_session: Session,
) -> None:
    """Codex round-4 P2: the multiple-explicit-owner branch raises the
    confirmation DOMAIN error (422 + the D-08 message), not the bare
    ValueError the PWA/Telegram wrappers would render as a 500."""
    from app.services.visit_confirmation_service import (
        VisitConfirmationDomainError,
        VisitConfirmationService,
    )

    doc_user = _make_user(db_session, username="dr_cosm_a", role="doctor")
    doc_a = _make_doctor(db_session, user_id=doc_user.id, specialty="procedures")
    doc_user_b = _make_user(db_session, username="dr_cosm_b", role="doctor")
    doc_b = _make_doctor(db_session, user_id=doc_user_b.id, specialty="procedures")
    _make_service(
        db_session,
        code="C03",
        queue_tag="procedures",
        name="Мезотерапия",
        requires_doctor=True,
        doctor_id=doc_a.id,
    )
    _make_service(
        db_session,
        code="C06",
        queue_tag="procedures",
        name="Чистка лица",
        requires_doctor=True,
        doctor_id=doc_b.id,
    )
    visit = _make_visit(db_session)  # NO visit doctor
    svc_a = (
        db_session.query(Service).filter(Service.code == "C03").one()
    )
    svc_b = (
        db_session.query(Service).filter(Service.code == "C06").one()
    )
    _link_visit_service(db_session, visit, svc_a)
    _link_visit_service(db_session, visit, svc_b)

    with pytest.raises(VisitConfirmationDomainError) as excinfo:
        VisitConfirmationService(db_session)._assign_queue_numbers_on_confirmation(
            visit
        )
    assert excinfo.value.status_code == 422
    assert "procedures" in excinfo.value.detail


def test_morning_assignment_job_aborts_on_config_error(db_session: Session) -> None:
    """Codex round-1 P2: the automated morning job cannot bury the
    configuration error as a per-visit 'Внутренняя ошибка' with
    success: True — the job returns success: False carrying the D-08
    message (the operator fixes the catalog and re-runs)."""
    from app.services.morning_assignment import MorningAssignmentService

    gen_user = _make_user(db_session, username="general_resource", role="Resource")
    _make_doctor(db_session, user_id=gen_user.id, specialty="general")
    service = _make_service(
        db_session,
        code="O20",
        queue_tag="neurology",
        name="Невропатолог",
        requires_doctor=False,
    )
    visit = _make_visit(db_session)
    _link_visit_service(db_session, visit, service)

    visit.confirmed_at = datetime(2026, 9, 12, 7, 0, 0)
    db_session.commit()

    result = MorningAssignmentService(db_session).run_morning_assignment(_DAY)
    assert result["success"] is False
    assert "neurology" in str(result)


def test_wizard_assignment_service_propagates_config_error(
    db_session: Session,
) -> None:
    """Codex round-1 P1: the PER-TAG loop of the wizard assignment
    re-raises before its compensating cleanup — the cart endpoint sees
    the error (422), never a 200 with visits minus queue numbers."""
    from app.crud.queue_owner_policy import QueueOwnerConfigurationError
    from app.services.registrar_wizard_queue_assignment_service import (
        RegistrarWizardQueueAssignmentService,
    )

    gen_user = _make_user(db_session, username="general_resource", role="Resource")
    _make_doctor(db_session, user_id=gen_user.id, specialty="general")
    service = _make_service(
        db_session,
        code="O30",
        queue_tag="ultrason",
        name="УЗИ",
        requires_doctor=False,
    )
    visit = _make_visit(db_session)
    _link_visit_service(db_session, visit, service)

    with pytest.raises(QueueOwnerConfigurationError, match="ultrason"):
        RegistrarWizardQueueAssignmentService(db_session).assign_same_day_queue_numbers(
            [visit], target_day=_DAY, source="desk"
        )


def test_wizard_helpers_general_default_is_gone() -> None:
    """Source pin: the dead _create_queue_entries helper (the only
    place that defaulted UNTAGGED services onto the 'general' tag and
    resolved the ecg/lab synthetics) is removed from the wizard."""
    source = WIZARD_HELPERS.read_text(encoding="utf-8")
    assert "def _create_queue_entries" not in source
    assert 'add("general")' not in source


def test_no_new_general_routes_in_morning_precreate(
    db_session: Session,
    monkeypatch,
) -> None:
    """End-to-end pre-create guard: with the map applied (a lab service
    and a cardio service with its doctor) the morning pre-create never
    creates a queue owned by a synthetic or tagged 'general'."""
    from app.services.morning_assignment import MorningAssignmentService

    class _FlatNested:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(db_session, "begin_nested", lambda *a, **k: _FlatNested())

    resource = QueueResource(code="lab", queue_tag="lab", display_name="Лаборатория")
    db_session.add(resource)
    doc_user = _make_user(db_session, username="dr_kardio2", role="doctor")
    doc = _make_doctor(db_session, user_id=doc_user.id, specialty="cardio")
    gen_user = _make_user(db_session, username="general_resource", role="Resource")
    gen_doctor = _make_doctor(db_session, user_id=gen_user.id, specialty="general")
    _make_service(db_session, code="L14", queue_tag="lab", name="Гемоглобин")
    cardio = _make_service(
        db_session,
        code="K01",
        queue_tag="cardio",
        name="Консультация кардиолога",
        requires_doctor=True,
        doctor_id=doc.id,
    )
    assert cardio.doctor_id == doc.id
    # an undecided surface (kept in the world to prove no queue for it)
    _make_service(db_session, code="P03", queue_tag="procedures", name="УФО терапия")

    MorningAssignmentService(db_session).ensure_daily_queues_for_all_tags(_DAY)

    queues = db_session.query(DailyQueue).filter(DailyQueue.day == _DAY).all()
    assert len(queues) == 2
    for queue in queues:
        assert queue.specialist_id != gen_doctor.id
        assert queue.queue_tag != "general"
    tags = {queue.queue_tag for queue in queues}
    assert tags == {"lab", "cardio"}


# ===================== D-08 refinement (2026-09-15) =====================


def test_refinement_matches_the_refinement_evidence_file() -> None:
    """Parity pin for the dated refinement: the O10/O20/S10 assignments
    (with the requires_doctor flip) and the 16 clear_requires_doctor
    decisions are EXACTLY the owner-approved refinement file."""
    payload = json.loads(REFINEMENT_MAP.read_text(encoding="utf-8"))
    items = payload["items"]
    module = _load_migration_0064()

    refinement_assigns = {
        item["code"]: (
            item["id"],
            item["target_doctor_id"],
            item["set_requires_doctor"],
        )
        for item in items
        if item["decision"] == "assign_doctor"
    }
    refinement_clears = {
        item["code"]: (item["id"], item["queue_tag"])
        for item in items
        if item["decision"] == "clear_requires_doctor"
    }
    assert payload["registry_seed"]["code"] == "procedures"
    assert payload["registry_seed"]["active"] is True

    embedded_assigns = {
        code: (snapshot_id, target, set_requires)
        for (
            snapshot_id,
            code,
            target,
            _original,
            expected_user,
            _snapshot_tag,
            set_requires,
        ) in module._ASSIGN_DOCTOR_DECISIONS
        if code in refinement_assigns
    }
    assert embedded_assigns == refinement_assigns
    embedded_clears = {
        code: (snapshot_id, snapshot_tag)
        for snapshot_id, code, snapshot_tag in (
            module._CLEAR_DOCTOR_REQUIREMENT_DECISIONS
        )
    }
    assert embedded_clears == refinement_clears
    # the doctor-to-owner linkage is part of the approved refinement
    assert module._REFINEMENT_DOCTOR_USER_LINKAGE == {17: 29, 18: 30, 16: 27}


def _seed_refinement_world(conn) -> None:
    """The decided world + the 2026-09-15 refinement objects: the
    O10/O20/S10 services (snapshot ids 125/126/90), the 16 procedure
    services, and the three refinement doctors FORCED to the production
    ids 17/18/16 with the owner-approved user linkage 29/30/27."""
    _seed_synthetic_world(conn)
    _seed_decided_services(conn)

    # users with the production ids (the migration pins doctor -> user)
    for user_id, username in ((29, "UZD"), (30, "Невролог"), (27, "Stomatolog")):
        conn.execute(
            sa.text(
                "INSERT INTO users (id, username, role, is_active,"
                " hashed_password) VALUES (:i, :u, 'doctor', 1, :p)"
            ),
            {"i": user_id, "u": username, "p": _DISABLED_HASH},
        )
    for doctor_id, user_id, specialty in (
        (17, 29, "ultrason"),
        (18, 30, "neurology"),
        (16, 27, "dentistry"),
    ):
        conn.execute(
            sa.text(
                "INSERT INTO doctors (id, user_id, specialty, active)"
                " VALUES (:i, :u, :s, 1)"
            ),
            {"i": doctor_id, "u": user_id, "s": specialty},
        )

    refinement_tags = {"O10": "ultrason", "O20": "neurology", "S10": "stomatology"}
    for code, snapshot_id in _REFINEMENT_ASSIGN_SNAPSHOT_IDS.items():
        requires = 0 if code in ("O10", "O20") else 1
        conn.execute(
            sa.text(
                "INSERT INTO services (id, code, name, queue_tag,"
                " department_key, doctor_id, requires_doctor, active)"
                " VALUES (:i, :c, :n, :t, NULL, NULL, :r, 1)"
            ),
            {
                "i": snapshot_id,
                "c": code,
                "n": f"service {code}",
                "t": refinement_tags[code],
                "r": requires,
            },
        )
    for code in _CLEAR_CODES:
        conn.execute(
            sa.text(
                "INSERT INTO services (id, code, name, queue_tag,"
                " department_key, doctor_id, requires_doctor, active)"
                " VALUES (:i, :c, :n, 'procedures', NULL, NULL, 1, 1)"
            ),
            {"i": _CLEAR_SNAPSHOT_IDS[code], "c": code, "n": f"service {code}"},
        )
    # commit: the abort tests roll the connection back and must still see
    # the seeded world (only the migration's own writes are discarded)
    conn.commit()


def test_upgrade_applies_the_refined_decisions() -> None:
    conn = _scratch()
    _seed_refinement_world(conn)
    conn.execute(
        sa.text(
            "INSERT INTO daily_queues (day, specialist_id, queue_resource_id,"
            " queue_tag, active) VALUES ('2026-09-12', NULL, 1, 'lab', 1)"
        )
    )
    conn.execute(
        sa.text(
            "INSERT INTO queue_entries (queue_id, number, status)"
            " VALUES (1, 7, 'waiting')"
        )
    )
    entries_before = conn.execute(
        sa.text("SELECT id, queue_id, number, status FROM queue_entries")
    ).fetchall()

    module = _load_migration_0064()
    module.upgrade_with_conn(conn)

    # O10/O20/S10: the doctor axis, requires_doctor True
    for code, doctor_id in (("O10", 17), ("O20", 18), ("S10", 16)):
        row = conn.execute(
            sa.text(
                "SELECT doctor_id, requires_doctor, queue_tag FROM services"
                " WHERE code = :c"
            ),
            {"c": code},
        ).fetchone()
        assert (row.doctor_id, bool(row.requires_doctor)) == (doctor_id, True), code
        assert row.queue_tag == {"O10": "ultrason", "O20": "neurology", "S10": "stomatology"}[code], code
    # the 16 procedures: the resource axis
    for code in _CLEAR_CODES:
        row = conn.execute(
            sa.text(
                "SELECT requires_doctor, doctor_id, queue_tag FROM services"
                " WHERE code = :c"
            ),
            {"c": code},
        ).fetchone()
        assert (bool(row.requires_doctor), row.doctor_id) == (False, None), code
        assert row.queue_tag == "procedures", code
    # the registry seed
    reg = conn.execute(
        sa.text(
            "SELECT code, queue_tag, active FROM queue_resources"
            " WHERE queue_tag = 'procedures'"
        )
    ).fetchall()
    assert reg == [("procedures", "procedures", 1)]
    # the existing history is untouched
    entries_after = conn.execute(
        sa.text("SELECT id, queue_id, number, status FROM queue_entries")
    ).fetchall()
    assert entries_after == entries_before


def test_refinement_is_idempotent_second_pass() -> None:
    conn = _scratch()
    _seed_refinement_world(conn)
    module = _load_migration_0064()
    module.upgrade_with_conn(conn)
    # the clean second pass applies nothing and does not abort
    module.upgrade_with_conn(conn)
    for code, doctor_id in (("O10", 17), ("O20", 18), ("S10", 16)):
        row = conn.execute(
            sa.text("SELECT doctor_id, requires_doctor FROM services WHERE code = :c"),
            {"c": code},
        ).fetchone()
        assert (row.doctor_id, bool(row.requires_doctor)) == (doctor_id, True), code


def test_refinement_abort_on_o10_replacement_row() -> None:
    """The approved O10 decision binds (id=125, code='O10'); a different
    live row re-using the code must not inherit it (thread 3995689408)."""
    conn = _scratch()
    _seed_refinement_world(conn)
    conn.execute(sa.text("UPDATE services SET id = 999 WHERE code = 'O10'"))

    # the D-08 coverage gate runs before identity resolution and reports
    # the replacement row as UNDECIDED for the map's purposes
    _assert_abort(conn, "a DIFFERENT object carries it now")


def test_refinement_abort_leaves_no_partial_map() -> None:
    """One invalid target aborts the WHOLE map — the single transaction
    leaves every other decided service untouched."""
    conn = _scratch()
    _seed_refinement_world(conn)
    # the neurology target doctor 18 is never seeded -> abort
    conn.execute(sa.text("DELETE FROM doctors WHERE id = 18"))

    _assert_abort(conn, "does not exist")
    # mirror the production alembic behaviour: the failed migration is
    # rolled back as a whole
    conn.rollback()

    for code, doctor_id, requires in (
        ("O10", None, False),
        ("S10", None, True),
    ):
        row = conn.execute(
            sa.text("SELECT doctor_id, requires_doctor FROM services WHERE code = :c"),
            {"c": code},
        ).fetchone()
        assert (
            row.doctor_id,
            bool(row.requires_doctor),
        ) == (doctor_id, requires), code
    for code in _CLEAR_CODES:
        row = conn.execute(
            sa.text("SELECT requires_doctor FROM services WHERE code = :c"),
            {"c": code},
        ).fetchone()
        assert bool(row.requires_doctor) is True, code
    assert (
        conn.execute(
            sa.text(
                "SELECT COUNT(*) FROM queue_resources WHERE queue_tag = 'procedures'"
            )
        ).scalar()
        == 0
    )


def test_refinement_abort_when_o10_doctor_linked_to_wrong_user() -> None:
    conn = _scratch()
    _seed_refinement_world(conn)
    # link doctor 17 to a DIFFERENT EXISTING account (user 30) so the
    # foreign-owner check fires (a nonexistent user would trip the
    # inactive-owner branch first)
    conn.execute(sa.text("UPDATE doctors SET user_id = 30 WHERE id = 17"))

    _assert_abort(conn, "linked to user id=30")


def test_refinement_abort_when_neurology_doctor_inactive() -> None:
    conn = _scratch()
    _seed_refinement_world(conn)
    conn.execute(sa.text("UPDATE doctors SET active = 0 WHERE id = 18"))

    _assert_abort(conn, "is inactive")


def test_refinement_registry_seed_never_overwrites_operator_settings() -> None:
    conn = _scratch()
    _seed_refinement_world(conn)
    # an operator-configured procedures resource (different numbering)
    conn.execute(
        sa.text(
            "INSERT INTO queue_resources (code, queue_tag, display_name,"
            " active, start_number_online, max_online_per_day)"
            " VALUES ('proc_cab', 'procedures', 'Процедурный кабинет', 1, 30, 40)"
        )
    )

    _assert_abort(conn, "exists as code='proc_cab'")

    row = conn.execute(
        sa.text(
            "SELECT start_number_online, max_online_per_day FROM"
            " queue_resources WHERE queue_tag = 'procedures'"
        )
    ).fetchone()
    assert tuple(row) == (30, 40)  # the operator settings survive


def test_refinement_history_and_entries_are_never_rewritten() -> None:
    """The cutover writes ONLY services + the seeded registry row — the
    visit/queue/entry history is byte-identical before and after."""
    conn = _scratch()
    _seed_refinement_world(conn)
    conn.execute(
        sa.text(
            "INSERT INTO daily_queues (day, specialist_id, queue_resource_id,"
            " queue_tag, active) VALUES ('2026-09-12', NULL, 1, 'lab', 1)"
        )
    )
    conn.execute(
        sa.text(
            "INSERT INTO queue_entries (queue_id, number, status)"
            " VALUES (1, 3, 'called')"
        )
    )
    queues_before = conn.execute(sa.text("SELECT * FROM daily_queues")).fetchall()
    entries_before = conn.execute(sa.text("SELECT * FROM queue_entries")).fetchall()

    module = _load_migration_0064()
    module.upgrade_with_conn(conn)

    assert (
        conn.execute(sa.text("SELECT * FROM daily_queues")).fetchall() == queues_before
    )
    assert conn.execute(sa.text("SELECT * FROM queue_entries")).fetchall() == entries_before
