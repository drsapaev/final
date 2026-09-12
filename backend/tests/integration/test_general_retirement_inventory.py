"""RQ-15.a — Stage E `general` retirement inventory regression pins.

Owner decision D-08 (ADR-001, 2026-09-12) splits Stage E into
RQ-15.a..d and requires a read-only production inventory BEFORE any
cutover. `backend/scripts/inventory_general_retirement.py` is that
inventory; these pins protect its contract:

- the READ-ONLY half: the tool's connection rejects writes at the
  driver level (SQLite ``PRAGMA query_only``), and a full run leaves
  every table byte-identical (snapshot before/after);
- the SCHEMA-CONTRACT half: exit 2 when the 0063 owner XOR / partial
  unique are missing or violated, exit 0 only when nothing needs an
  operator decision;
- the IDENTITY half: exactly the three 0055 synthetic pairs are
  reported (with drift notes when a pair is missing), and doctors
  with specialty ``general`` are reported as the NEVER-delete
  sentinel population, separate from the synthetic pair;
- the INBOUND-REFERENCE half: every introspected doctors/users FK
  surface is counted per synthetic id; the general pair's
  daily_queues.specialist_id history and the pair's own
  doctors.user_id linkage are EXPECTED, everything else blocks;
- the ROUTING-SURFACE half: services on the general-fallback tags
  (general / cardiology_common / dermatology / procedures) or
  department_key='general' or a synthetic doctor_id; queue profiles
  whose tags contain EXACTLY 'general' (the 'general_x' spelling must
  not match); the departments row; a medical_specialties 'general'
  drift row;
- the QUEUE half: general/synthetic-owned queues classified
  active_live_blocker / active_empty / inactive_historical with live
  entry statuses waiting/called/in_service/diagnostics (the 0059
  contract);
- the OPERATOR-MAP half: one fillable decision entry per ACTIVE
  general surface, decision=null, D-08 options only.

The tool runs against a scratch SQLite database shaped like
production (the 0059/0063 test precedent: module import + minimal
tables); production PostgreSQL runs are the operator's handoff step
(docs/runbooks/QUEUE_GENERAL_RETIREMENT_INVENTORY_RUNBOOK.md).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import sqlalchemy as sa

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
TOOL_PATH = BACKEND_ROOT / "scripts" / "inventory_general_retirement.py"

EXPECTED_HEAD = "0063_queue_resource_contract"

# --------------------------------------------------------------- helpers


def _load_tool():
    spec = importlib.util.spec_from_file_location(
        "inventory_general_retirement", TOOL_PATH
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


_TOOL = _load_tool()

_SCHEMA_POST_D = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    hashed_password TEXT,
    role TEXT,
    is_active BOOLEAN DEFAULT 1
);
CREATE TABLE doctors (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    specialty TEXT,
    active BOOLEAN DEFAULT 1,
    start_number_online INTEGER,
    max_online_per_day INTEGER
);
CREATE TABLE services (
    id INTEGER PRIMARY KEY,
    code TEXT,
    name TEXT,
    active BOOLEAN DEFAULT 1,
    requires_doctor BOOLEAN DEFAULT 0,
    queue_tag TEXT,
    department_key TEXT,
    doctor_id INTEGER REFERENCES doctors(id)
);
CREATE TABLE queue_profiles (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    title TEXT,
    is_active BOOLEAN DEFAULT 1,
    show_on_qr_page BOOLEAN DEFAULT 0,
    queue_tags TEXT
);
CREATE TABLE departments (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    name_ru TEXT,
    display_order INTEGER,
    active BOOLEAN DEFAULT 1
);
CREATE TABLE queue_resources (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    queue_tag TEXT,
    display_name TEXT,
    active BOOLEAN DEFAULT 1,
    start_number_online INTEGER,
    max_online_per_day INTEGER,
    default_cabinet TEXT
);
CREATE TABLE daily_queues (
    id INTEGER PRIMARY KEY,
    day TEXT NOT NULL,
    specialist_id INTEGER REFERENCES doctors(id),
    queue_resource_id INTEGER REFERENCES queue_resources(id),
    queue_tag TEXT,
    active BOOLEAN DEFAULT 1,
    cabinet_number TEXT,
    CONSTRAINT ck_daily_queues_owner_xor CHECK (
        (CASE WHEN specialist_id IS NULL THEN 0 ELSE 1 END
         + CASE WHEN queue_resource_id IS NULL THEN 0 ELSE 1 END) = 1
    )
);
CREATE UNIQUE INDEX uq_daily_queues_active_resource_day
    ON daily_queues (day, queue_resource_id)
    WHERE active = 1 AND queue_resource_id IS NOT NULL;
CREATE TABLE queue_entries (
    id INTEGER PRIMARY KEY,
    queue_id INTEGER REFERENCES daily_queues(id),
    status TEXT,
    number INTEGER,
    patient_name TEXT
);
CREATE TABLE medical_specialties (
    id INTEGER PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    title_ru TEXT,
    active BOOLEAN DEFAULT 1
);
CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL);
CREATE TABLE visits (
    id INTEGER PRIMARY KEY, doctor_id INTEGER REFERENCES doctors(id));
CREATE TABLE appointments (
    id INTEGER PRIMARY KEY, doctor_id INTEGER REFERENCES doctors(id));
CREATE TABLE schedules (
    id INTEGER PRIMARY KEY, doctor_id INTEGER NOT NULL REFERENCES doctors(id));
CREATE TABLE telegram_config (
    id INTEGER PRIMARY KEY,
    doctor_id INTEGER REFERENCES doctors(id),
    user_id INTEGER REFERENCES users(id)
);
"""

# the same schema minus the two 0063 constraints (a pre-D database)
_SCHEMA_PRE_D = _SCHEMA_POST_D.replace(
    """    cabinet_number TEXT,
    CONSTRAINT ck_daily_queues_owner_xor CHECK (
        (CASE WHEN specialist_id IS NULL THEN 0 ELSE 1 END
         + CASE WHEN queue_resource_id IS NULL THEN 0 ELSE 1 END) = 1
    )
""",
    """    cabinet_number TEXT
""",
).replace(
    """CREATE UNIQUE INDEX uq_daily_queues_active_resource_day
    ON daily_queues (day, queue_resource_id)
    WHERE active = 1 AND queue_resource_id IS NOT NULL;
""",
    "",
)

_SYNTHETICS = [
    # (user_id, username, role) -> doctor_id, specialty
    (1, "ecg_resource", "Resource"),
    (2, "lab_resource", "Resource"),
    (3, "general_resource", "Resource"),
]


def _make_db(tmp_path: Path, variant: str = "canonical") -> str:
    """Scratch production-shaped DB; returns the sqlite URL."""
    url = f"sqlite:///{tmp_path / f'{variant}.db'}"
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        schema_script = _SCHEMA_PRE_D if variant == "pre_d" else _SCHEMA_POST_D
        # sqlite3 refuses multi-statement scripts through one execute()
        for statement in [s.strip() for s in schema_script.split(";") if s.strip()]:
            conn.execute(sa.text(statement))
        seed = []
        if variant in ("canonical", "pre_d"):
            seed += [
                # the three 0055 synthetic pairs
                "INSERT INTO users (id, username, hashed_password, role, is_active)"
                " VALUES (1,'ecg_resource','!disabled:queue-resource','Resource',1),"
                " (2,'lab_resource','!disabled:queue-resource','Resource',1),"
                " (3,'general_resource','!disabled:queue-resource','Resource',1)",
                "INSERT INTO doctors (id, user_id, specialty, active,"
                " start_number_online, max_online_per_day)"
                " VALUES (1,1,'ecg',1,1,15),(2,2,'lab',1,1,15),(3,3,'general',1,1,15)",
                # real people: sentinel population (never deleted)
                "INSERT INTO users (id, username, hashed_password, role, is_active)"
                " VALUES (10,'ivan','x','Doctor',1),(11,'maria','x','Doctor',0)",
                "INSERT INTO doctors (id, user_id, specialty, active,"
                " start_number_online, max_online_per_day)"
                " VALUES (10,10,'general',1,1,15),(11,11,' General ',0,1,15)",
                # registry: lab/ecg only (the 0059 seeds)
                "INSERT INTO queue_resources (id, code, queue_tag, display_name,"
                " active, start_number_online, max_online_per_day)"
                " VALUES (1,'lab','lab','Лаборатория',1,1,15),"
                " (2,'ecg','ecg','ЭКГ',1,1,15)",
                # services on the general routing surface
                "INSERT INTO services (id, code, name, active, requires_doctor,"
                " queue_tag, department_key, doctor_id) VALUES"
                " (1,'G1','Приём общий',1,0,'general',NULL,NULL),"
                " (2,'C1','Кардио общая',1,1,'cardiology_common',NULL,NULL),"
                " (3,'G2','Старый общий',0,0,'general',NULL,NULL),"
                " (4,'K1','Кардио',1,1,'cardio',NULL,NULL),"
                " (5,'D1','Дерма',1,1,'derma2','general',NULL),"
                " (6,'L1','Лаб анализ',1,0,'lab',NULL,2)",
                # profiles: exact-tag membership trap included
                "INSERT INTO queue_profiles (id, key, title, is_active,"
                " show_on_qr_page, queue_tags) VALUES"
                " (1,'general','Общая очередь',1,0,'[\"general\"]'),"
                " (2,'specialists','Специалисты',1,0,'[\"cardio\",\"lab\"]'),"
                " (3,'general_x','Ловушка',1,0,'[\"general_x\"]')",
                "INSERT INTO departments (id, key, name_ru, display_order, active)"
                " VALUES (1,'general','Общая очередь',5,1)",
                # queues: blocker / active-empty / historical / fallback-tag
                "INSERT INTO daily_queues (id, day, specialist_id,"
                " queue_resource_id, queue_tag, active) VALUES"
                " (1,'2026-09-12',3,NULL,'general',1),"
                " (2,'2026-09-12',3,NULL,'general',1),"
                " (3,'2026-09-11',3,NULL,'general',0),"
                " (4,'2026-09-12',3,NULL,'cardiology_common',1),"
                " (5,'2026-09-12',NULL,1,'lab',1)",
                "INSERT INTO queue_entries (id, queue_id, status, number,"
                " patient_name) VALUES"
                " (1,1,'waiting',1,'Пациент А'),"
                " (2,1,'completed',2,'Пациент Б'),"
                " (3,2,'completed',1,'Пациент В'),"
                " (4,2,'cancelled',2,'Пациент Г'),"
                " (5,3,'cancelled',1,'Пациент Д')",
                # inbound references beyond the expected ones
                "INSERT INTO visits (id, doctor_id) VALUES (1,3)",
                "INSERT INTO appointments (id, doctor_id) VALUES (1,2)",
                "INSERT INTO schedules (id, doctor_id) VALUES (1,1)",
                "INSERT INTO telegram_config (id, doctor_id, user_id)"
                " VALUES (1,1,3)",
            ]
        elif variant == "no_general_user":
            seed += [
                "INSERT INTO users (id, username, hashed_password, role, is_active)"
                " VALUES (1,'ecg_resource','!disabled:queue-resource','Resource',1),"
                " (2,'lab_resource','!disabled:queue-resource','Resource',1)",
                "INSERT INTO doctors (id, user_id, specialty, active,"
                " start_number_online, max_online_per_day)"
                " VALUES (1,1,'ecg',1,1,15),(2,2,'lab',1,1,15)",
                "INSERT INTO queue_resources (id, code, queue_tag, display_name,"
                " active, start_number_online, max_online_per_day)"
                " VALUES (1,'lab','lab','Лаборатория',1,1,15),"
                " (2,'ecg','ecg','ЭКГ',1,1,15)",
            ]
        elif variant == "registry_general":
            seed += [
                "INSERT INTO users (id, username, hashed_password, role, is_active)"
                " VALUES (3,'general_resource','!disabled:queue-resource','Resource',1)",
                "INSERT INTO doctors (id, user_id, specialty, active,"
                " start_number_online, max_online_per_day)"
                " VALUES (3,3,'general',1,1,15)",
                "INSERT INTO queue_resources (id, code, queue_tag, display_name,"
                " active, start_number_online, max_online_per_day)"
                " VALUES (1,'general','general','Архив?',1,1,15)",
            ]
        elif variant == "clean":
            seed += [
                "INSERT INTO users (id, username, hashed_password, role, is_active)"
                " VALUES (1,'ecg_resource','!disabled:queue-resource','Resource',1),"
                " (2,'lab_resource','!disabled:queue-resource','Resource',1),"
                " (3,'general_resource','!disabled:queue-resource','Resource',1)",
                "INSERT INTO doctors (id, user_id, specialty, active,"
                " start_number_online, max_online_per_day)"
                " VALUES (1,1,'ecg',1,1,15),(2,2,'lab',1,1,15),(3,3,'general',1,1,15)",
                "INSERT INTO queue_resources (id, code, queue_tag, display_name,"
                " active, start_number_online, max_online_per_day)"
                " VALUES (1,'lab','lab','Лаборатория',1,1,15),"
                " (2,'ecg','ecg','ЭКГ',1,1,15)",
                "INSERT INTO queue_profiles (id, key, title, is_active,"
                " show_on_qr_page, queue_tags) VALUES"
                " (2,'specialists','Специалисты',1,0,'[\"cardio\",\"lab\"]')",
            ]
        if variant == "registry_general":
            seed.append(
                "INSERT INTO medical_specialties (id, code, title_ru, active)"
                " VALUES (1,'general','Общая',1)"
            )
        head = "0062_telegram_webhook_dedup" if variant == "pre_d" else EXPECTED_HEAD
        seed.append(f"INSERT INTO alembic_version (version_num) VALUES ('{head}')")
        for statement in seed:
            conn.execute(sa.text(statement))
    engine.dispose()
    return url


def _run_tool(url: str, tmp_path: Path):
    """Run the inventory CLI; returns (exit_code, report, operator_map)."""
    report_path = tmp_path / "report.json"
    map_path = tmp_path / "operator_map.json"
    code = _TOOL.main(
        [
            "--database-url",
            url,
            "--json",
            str(report_path),
            "--operator-map",
            str(map_path),
        ]
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    operator_map = json.loads(map_path.read_text(encoding="utf-8"))
    return code, report, operator_map


def _snapshot(url: str) -> dict[str, list[tuple]]:
    engine = sa.create_engine(url)
    try:
        with engine.connect() as conn:
            tables = [
                r["name"]
                for r in conn.execute(
                    sa.text(
                        "SELECT name FROM sqlite_master WHERE type='table' "
                        "AND name NOT LIKE 'sqlite_%'"
                    )
                ).mappings()
            ]
            return {
                t: [
                    tuple(row)
                    for row in conn.execute(sa.text(f"SELECT * FROM {t} ORDER BY 1"))
                ]
                for t in sorted(tables)
            }
    finally:
        engine.dispose()


@pytest.fixture()
def canonical_db(tmp_path):
    return _make_db(tmp_path, "canonical")


# ---------------------------------------------------- read-only pins


def test_read_only_connection_blocks_writes(canonical_db):
    engine, conn = _TOOL._connect_read_only(canonical_db)
    try:
        flag = conn.execute(sa.text("PRAGMA query_only")).scalar()
        assert flag == 1
        with pytest.raises(sa.exc.OperationalError):
            conn.execute(sa.text("UPDATE departments SET name_ru = 'nope'"))
        with pytest.raises(sa.exc.OperationalError):
            conn.execute(sa.text("DELETE FROM users WHERE id = 3"))
    finally:
        conn.close()
        engine.dispose()


def test_full_run_leaves_every_table_unchanged(canonical_db, tmp_path):
    before = _snapshot(canonical_db)
    code, _, _ = _run_tool(canonical_db, tmp_path)
    assert code == 1
    after = _snapshot(canonical_db)
    assert before == after


# ---------------------------------------------------- schema contract


def test_canonical_exit_code_and_report_shape(canonical_db, tmp_path):
    code, report, operator_map = _run_tool(canonical_db, tmp_path)
    assert code == 1  # blockers + open decisions, contract itself OK
    assert report["report_version"] == 1
    assert report["tool"] == "inventory_general_retirement.py"
    assert report["database"].startswith("sqlite:///")


def test_schema_contract_section_ok(canonical_db, tmp_path):
    _, report, _ = _run_tool(canonical_db, tmp_path)
    schema = report["schema_contract"]
    assert schema["alembic_version"] == EXPECTED_HEAD
    assert schema["check_constraint"]["present"] is True
    assert schema["partial_unique"]["present"] is True
    assert schema["owner_xor_violations"] == 0
    assert schema["active_resource_day_duplicate_groups"] == 0
    assert schema["stage_d_contract_ok"] is True
    assert schema["problems"] == []


def test_exit_2_when_stage_d_constraints_missing(tmp_path):
    url = _make_db(tmp_path, "pre_d")
    code, report, _ = _run_tool(url, tmp_path)
    assert code == 2
    schema = report["schema_contract"]
    assert schema["alembic_version"] == "0062_telegram_webhook_dedup"
    assert schema["check_constraint"]["present"] is False
    assert schema["partial_unique"]["present"] is False
    problems = " ".join(schema["problems"])
    assert "ck_daily_queues_owner_xor" in problems
    assert "uq_daily_queues_active_resource_day" in problems
    kinds = {b["kind"] for b in report["blockers"]}
    assert "stage_d_contract" in kinds


def test_exit_2_on_owner_xor_violation(tmp_path):
    url = _make_db(tmp_path, "pre_d")
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        # both owners NULL — impossible post-0063, loud drift on a pre-D DB
        conn.execute(
            sa.text(
                "INSERT INTO daily_queues (id, day, specialist_id,"
                " queue_resource_id, queue_tag, active)"
                " VALUES (99,'2026-09-12',NULL,NULL,'general',0)"
            )
        )
    engine.dispose()
    code, report, _ = _run_tool(url, tmp_path)
    assert code == 2
    assert report["schema_contract"]["owner_xor_violations"] == 1


# ---------------------------------------------------- synthetic pairs


def test_synthetic_pairs_identity(canonical_db, tmp_path):
    _, report, _ = _run_tool(canonical_db, tmp_path)
    pairs = report["synthetic_pairs"]["pairs"]
    assert len(pairs) == 3
    by_name = {p["username"]: p for p in pairs}
    assert by_name["ecg_resource"]["user"]["id"] == 1
    assert by_name["ecg_resource"]["doctor"]["id"] == 1
    assert by_name["ecg_resource"]["doctor"]["specialty"] == "ecg"
    assert by_name["lab_resource"]["doctor"]["specialty"] == "lab"
    assert by_name["general_resource"]["doctor"]["specialty"] == "general"
    assert all(p["drift"] == [] for p in pairs)
    assert all(p["user"]["disabled_marker_ok"] for p in pairs)
    assert report["synthetic_pairs"]["drift_notes"] == []


def test_missing_pair_is_drift_not_crash(tmp_path):
    url = _make_db(tmp_path, "no_general_user")
    code, report, _ = _run_tool(url, tmp_path)
    by_name = {p["username"]: p for p in report["synthetic_pairs"]["pairs"]}
    assert (
        "expected exactly 1 users row for 'general_resource', found 0"
        in by_name["general_resource"]["drift"]
    )
    assert by_name["general_resource"]["doctor"] is None
    # the run still completes and reports the rest
    assert code in (1, 2)


# ---------------------------------------------------- inbound references


def test_inbound_references_expected_vs_blocking(canonical_db, tmp_path):
    _, report, _ = _run_tool(canonical_db, tmp_path)
    by_name = {p["username"]: p for p in report["inbound_references"]["pairs"]}
    # every doctors/users FK surface is introspected
    surfaces = {
        (s["table"], s["column"])
        for p in report["inbound_references"]["pairs"]
        for s in p["surfaces"]
    }
    assert ("daily_queues", "specialist_id") in surfaces
    assert ("doctors", "user_id") in surfaces
    assert ("services", "doctor_id") in surfaces
    assert ("visits", "doctor_id") in surfaces
    assert ("telegram_config", "user_id") in surfaces
    assert report["inbound_references"]["surfaces_introspected"] >= 8

    general = by_name["general_resource"]
    per = {(s["table"], s["column"]): s for s in general["surfaces"]}
    # the general history: 4 specialist-owned queues, EXPECTED
    assert per[("daily_queues", "specialist_id")]["count"] == 4
    assert per[("daily_queues", "specialist_id")]["expected"] is True
    # the pair's own doctors.user_id linkage: EXPECTED
    assert per[("doctors", "user_id")]["count"] == 1
    assert per[("doctors", "user_id")]["expected"] is True
    # telegram + visit references: BLOCKING
    assert per[("telegram_config", "user_id")]["count"] == 1
    assert per[("visits", "doctor_id")]["count"] == 1
    blocking = {(s["table"], s["column"]) for s in general["blocking_surfaces"]}
    assert ("telegram_config", "user_id") in blocking
    assert ("visits", "doctor_id") in blocking
    assert ("daily_queues", "specialist_id") not in blocking

    lab = by_name["lab_resource"]
    lab_blocking = {(s["table"], s["column"]) for s in lab["blocking_surfaces"]}
    assert ("appointments", "doctor_id") in lab_blocking
    assert ("services", "doctor_id") in lab_blocking  # S6 points at the pair

    ecg = by_name["ecg_resource"]
    ecg_blocking = {(s["table"], s["column"]) for s in ecg["blocking_surfaces"]}
    assert ("schedules", "doctor_id") in ecg_blocking
    assert ("telegram_config", "doctor_id") in ecg_blocking


# ---------------------------------------------------- routing surfaces


def test_routing_surfaces_services(canonical_db, tmp_path):
    _, report, _ = _run_tool(canonical_db, tmp_path)
    services = {s["id"]: s for s in report["routing_surfaces"]["services"]}
    assert set(services) == {1, 2, 3, 5, 6}  # S4 (cardio) is not a surface
    assert "queue_tag='general' (general fallback)" in services[1]["reasons"]
    assert "queue_tag='cardiology_common' (general fallback)" in services[2]["reasons"]
    assert not services[3]["active"]
    assert "department_key='general'" in services[5]["reasons"]
    assert "doctor_id is a synthetic Doctor" in services[6]["reasons"]


def test_routing_surfaces_profiles_department_specialty(canonical_db, tmp_path):
    _, report, _ = _run_tool(canonical_db, tmp_path)
    routing = report["routing_surfaces"]
    profiles = [p["key"] for p in routing["queue_profiles_with_general_tag"]]
    # exact-tag membership: 'general' matches, 'general_x' does NOT
    assert profiles == ["general"]
    assert routing["department_general"][0]["key"] == "general"
    assert routing["medical_specialty_general_drift"] == []
    assert routing["fallback_tags"] == [
        "general",
        "cardiology_common",
        "dermatology",
        "procedures",
    ]


def test_registry_general_row_is_reported_as_drift(tmp_path):
    url = _make_db(tmp_path, "registry_general")
    code, report, _ = _run_tool(url, tmp_path)
    registry = report["registry"]
    assert [r["queue_tag"] for r in registry["general_resource_rows"]] == ["general"]
    kinds = {b["kind"] for b in report["blockers"]}
    assert "general_registry_row" in kinds


def test_medical_specialty_general_row_is_drift(tmp_path):
    url = _make_db(tmp_path, "registry_general")
    code, report, _ = _run_tool(url, tmp_path)
    drift = report["routing_surfaces"]["medical_specialty_general_drift"]
    assert drift and drift[0]["code"] == "general"
    kinds = {b["kind"] for b in report["blockers"]}
    assert "medical_specialty_drift" in kinds


# ---------------------------------------------------- queues


def test_general_queues_classification(canonical_db, tmp_path):
    _, report, _ = _run_tool(canonical_db, tmp_path)
    section = report["general_queues"]
    assert section["total"] == 4  # Q5 (resource-owned lab) is NOT included
    by_id = {q["id"]: q for q in section["queues"]}
    assert by_id[1]["classification"] == "active_live_blocker"
    assert by_id[1]["live_entry_count"] == 1
    assert by_id[1]["entry_count"] == 2
    assert by_id[2]["classification"] == "active_empty"
    assert by_id[2]["live_entry_count"] == 0
    assert by_id[3]["classification"] == "inactive_historical"
    assert by_id[4]["classification"] == "active_empty"
    assert by_id[4]["queue_tag"] == "cardiology_common"
    assert by_id[1]["live_entry_statuses"] == [
        "waiting",
        "called",
        "in_service",
        "diagnostics",
    ]
    assert section["classifications"] == {
        "active_live_blocker": 1,
        "active_empty": 2,
        "inactive_historical": 1,
    }


# ---------------------------------------------------- sentinel doctors


def test_sentinel_doctors_never_delete(canonical_db, tmp_path):
    _, report, _ = _run_tool(canonical_db, tmp_path)
    section = report["sentinel_doctors"]
    ids = [d["id"] for d in section["sentinel_doctors"]]
    assert ids == [10, 11]  # the synthetic doctor (id 3) is excluded
    assert all(d["never_delete"] is True for d in section["sentinel_doctors"])
    assert section["total_specialty_general"] == 3
    assert section["synthetic_among_them"] == 1
    assert "INCOMPLETE_DOCTOR_SPECIALTY" in section["policy"]


# ---------------------------------------------------- blockers + map


def test_blockers_kinds(canonical_db, tmp_path):
    _, report, _ = _run_tool(canonical_db, tmp_path)
    kinds = [b["kind"] for b in report["blockers"]]
    assert kinds.count("active_general_service") == 4  # S1 S2 S5 S6
    assert kinds.count("live_general_queue") == 1  # Q1
    assert kinds.count("inbound_reference") == 6
    # drift kinds absent on the canonical fixture
    assert "stage_d_contract" not in kinds
    assert "general_registry_row" not in kinds
    assert "medical_specialty_drift" not in kinds


def test_operator_map_items_and_decisions(canonical_db, tmp_path):
    code, report, operator_map = _run_tool(canonical_db, tmp_path)
    items = operator_map["items"]
    surfaces = [(i["surface"], i["id"]) for i in items]
    # active services S1/S2/S5/S6, active queues Q1/Q2/Q4, profile P1;
    # the inactive service S3 and the historical queue Q3 are excluded
    assert surfaces == [
        ("service", 1),
        ("service", 2),
        ("service", 5),
        ("service", 6),
        ("daily_queue", 1),
        ("daily_queue", 2),
        ("daily_queue", 4),
        ("queue_profile", 1),
    ]
    assert all(i["decision"] is None for i in items)
    service_opts = {
        i["id"]: i["decision_options"] for i in items if i["surface"] == "service"
    }
    assert set(service_opts[1]) == {
        "assign_doctor",
        "retag_resource",
        "disable_service",
    }
    queue1 = next(i for i in items if i["surface"] == "daily_queue" and i["id"] == 1)
    assert queue1["classification"] == "active_live_blocker"
    assert "resolve_entries_then_deactivate" in queue1["decision_options"]
    profile = next(i for i in items if i["surface"] == "queue_profile")
    assert set(profile["decision_options"]) == {"retire_profile", "keep_profile"}
    assert report["operator_map_items"] == len(items)
    assert "No inference" in operator_map["how_to_fill"]
    assert operator_map["report_version"] == 1


def test_clean_world_exit_0(tmp_path):
    url = _make_db(tmp_path, "clean")
    code, report, operator_map = _run_tool(url, tmp_path)
    assert code == 0
    assert report["blockers"] == []
    assert report["operator_map_items"] == 0
    assert operator_map["items"] == []
    assert report["schema_contract"]["stage_d_contract_ok"] is True


# ---------------------------------------------------- unit pins


def test_tags_list_normalization():
    assert _TOOL._tags_list('["general"]') == ["general"]
    assert _TOOL._tags_list(["general", "lab"]) == ["general", "lab"]
    assert _TOOL._tags_list(None) == []
    assert _TOOL._tags_list('["general_x"]') == ["general_x"]
    assert _TOOL._tags_list('not json') == []


def test_expected_constant_identity():
    # the exact 0055 usernames and their doctor specialties
    assert [p["username"] for p in _TOOL.SYNTHETIC_PAIR_SPECS] == [
        "ecg_resource",
        "lab_resource",
        "general_resource",
    ]
    assert [p["queue_tag"] for p in _TOOL.SYNTHETIC_PAIR_SPECS] == [
        "ecg",
        "lab",
        "general",
    ]
    assert _TOOL.DISABLED_PASSWORD_MARKER == "!disabled:queue-resource"
