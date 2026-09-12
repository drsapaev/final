"""RQ-15.a — read-only `general` retirement inventory (ADR-001 Stage E handoff).

Run this on PRODUCTION or STAGING (the Windows host works too) to produce
the Stage E inventory and the operator map BEFORE any catalog/runtime
cutover (RQ-15.b), historical-owner conversion (RQ-15.c) or the exact
paired deletion (RQ-15.d). Owner decision D-08 (2026-09-12, ADR-001
"Stage E `general` decision"): `general` is retired as a routing
destination and stays only the incomplete-Doctor onboarding sentinel;
nothing in Stage E may proceed from an empty CI database — production
inventory is a hard prerequisite, and this script is that inventory.

    cd backend
    python scripts/inventory_general_retirement.py \
        --database-url "postgresql+psycopg://user:pass@host/clinic" \
        --json ../evidence/stage_e_inventory.json \
        --operator-map ../evidence/stage_e_operator_map.json

(or export DATABASE_URL and omit --database-url; --pretty for human
output on stdout).

The script NEVER writes to the target database. Safety is enforced, not
promised: the connection is opened with SQLite ``PRAGMA query_only = ON``
or PostgreSQL ``default_transaction_read_only = on`` as a libpq connect
OPTION (applied at session start, before any transaction) — any
accidental write raises. No statement outside SELECT / PRAGMA /
introspection exists in this file (the
precheck_doctors_user_id_unique precedent).

The report (JSON, ``report_version`` 1) covers every gate of the ADR
production-gate list for deleting the three 0055 synthetic pairs:

1.  schema_contract — alembic_version, presence of both 0063 constraints
    (``ck_daily_queues_owner_xor`` CHECK + ``uq_daily_queues_active_
    resource_day`` partial unique), owner-XOR violations, ACTIVE
    (day, queue_resource_id) duplicate groups;
2.  synthetic_pairs — the exact 0055 identities (ecg_resource /
    lab_resource / general_resource): user row, linked Doctor row,
    specialty, password marker, activity — with drift notes;
3.  inbound_references — for EVERY introspected foreign key referencing
    ``doctors`` or ``users``: the row count pointing at each synthetic
    user/doctor id (the exact-ID dry-run deletion proof, gate 6);
4.  routing_surfaces — everything that still routes onto `general`:
    services whose queue_tag has NO ACTIVE queue_resources row (the
    runtime fallback is UNIVERSAL — morning_assignment pre-creates/batches
    every non-registry tag under general_resource; the legacy vocabulary
    general / cardiology_common / dermatology / procedures is only the
    named part of it), or department_key='general', or doctor_id on a
    synthetic Doctor; queue profiles whose queue_tags contain 'general';
    the departments row; a medical_specialties 'general' row (a drift:
    the catalog never stores the sentinel);
5.  general_queues — every daily_queues row tagged 'general' or owned
    by a synthetic Doctor: entry totals, live-entry counts (waiting /
    called / in_service / diagnostics — the 0059 live contract) and the
    classification (active_live_blocker / active_empty /
    inactive_historical);
6.  sentinel_doctors — Doctors with specialty='general' EXCLUDING the
    synthetic pair: the population that must NEVER be deleted (the
    incomplete-onboarding sentinel, ADR gate 6);
7.  registry — queue_resources rows; a 'general' row (active or not) is
    a Stage E drift (E must not seed an active general resource);
8.  blockers + operator_map — the consolidated list of what blocks
    RQ-15.b and the fillable decision map (every active general surface
    with a null ``decision`` the operator completes).

Exit codes:
    0 — inventory complete; no blockers and no open operator decisions.
    1 — inventory complete, but blockers and/or open decisions exist
        (EXPECTED on production: the operator map must be completed
        and the blockers resolved before RQ-15.b).
    2 — Stage E prerequisites missing: the 0063 contract is not present
        or is violated (wrong alembic head, missing constraints, XOR
        violations, ACTIVE resource duplicates). Fix the schema first.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa

# The exact 0055_queue_resource_provisioning identity (single source:
# backend/alembic/versions/0055_queue_resource_provisioning.py). The
# deletion in RQ-15.d targets THESE rows only — never all Doctors with
# specialty='general'.
SYNTHETIC_PAIR_SPECS = (
    {"username": "ecg_resource", "queue_tag": "ecg", "seed_role": "Nurse"},
    {"username": "lab_resource", "queue_tag": "lab", "seed_role": "Lab"},
    {"username": "general_resource", "queue_tag": "general", "seed_role": "Nurse"},
)

# 0055 seeds unusable passwords with this marker; a live row without it
# is drift worth reporting (the pair may have been hand-recreated).
DISABLED_PASSWORD_MARKER = "!disabled:queue-resource"

# The internal-only role all three synthetic users must carry at the
# post-0063 schema: 0056 moved ecg_resource/general_resource from
# 'Nurse' to 'Resource', 0057 moved lab_resource from 'Lab' to
# 'Resource' (core/roles.py INTERNAL_ONLY_ROLE_SPELLINGS). A pair whose
# user carries any other role is not the provisioned sentinel identity
# and must not be approved for exact deletion (Codex round-1 P2).
EXPECTED_SYNTHETIC_ROLE = "Resource"

# The runtime fallback vocabulary that routes onto general_resource
# (sources: app/services/batch_patient_service.py
# _BATCH_CREATE_RESOURCE_MAPPING and the morning_assignment pre-create
# map + universal fallback — RQ-15.b removes them; this inventory must
# see every tag they would route). NOTE: this list is only the NAMED
# legacy vocabulary — the runtime fallback is UNIVERSAL: every service
# tag WITHOUT an ACTIVE queue_resources row (general, cardio,
# cosmetology, ...) is pre-created/batched under general_resource
# (MorningAssignmentService.ensure_daily_queues_for_all_tags /
# _assign_visit_to_queue), so the inventory derives the surface from
# the ACTIVE registry contents, not from this list alone (Codex
# round-1 P1).
GENERAL_FALLBACK_TAGS = ("general", "cardiology_common", "dermatology", "procedures")

# Live queue-entry statuses (the 0059 abort-inventory contract: a queue
# with any of these still has patients inside and blocks the cutover).
LIVE_ENTRY_STATUSES = ("waiting", "called", "in_service", "diagnostics")

# The Stage D schema contract this inventory assumes (ADR gate 1: the
# production head must include 0063 and both constraints). The head
# must be EXACTLY 0063 in this tool's lifecycle: stale (0059/0062
# with manually-repaired constraints), multi-head and unrecognized
# states all exit 2 (Codex round-1 P2). When a LATER revision is
# deployed (RQ-15.d's 0064+), update EXPECTED_ALEMBIC_HEAD.
EXPECTED_ALEMBIC_HEAD = "0063_queue_resource_contract"
CHECK_CONSTRAINT_NAME = "ck_daily_queues_owner_xor"
PARTIAL_UNIQUE_NAME = "uq_daily_queues_active_resource_day"

# Owner CASE-sum, semantically identical to the 0063 / model constant
# (app/models/online_queue.py _OWNER_XOR_CHECK). Recomputed here so the
# script stays app-import-free (the 0048 precheck convention); when the
# constraint is present this count is structurally zero — it exists to
# catch drifted schemas where it is not.
_OWNER_XOR_SQL = """
    (CASE WHEN specialist_id IS NULL THEN 0 ELSE 1 END
     + CASE WHEN queue_resource_id IS NULL THEN 0 ELSE 1 END)
"""

REPORT_VERSION = 1
TOOL_NAME = "inventory_general_retirement.py"


# ============================================================================
# connection (read-only enforced)
# ============================================================================


REPORT_VERSION = 1
TOOL_NAME = "inventory_general_retirement.py"


def _connect_read_only(url: str):
    """Open ONE engine+connection with writes disabled at the driver.

    SQLite gets ``PRAGMA query_only = ON`` (any INSERT/UPDATE/DELETE/
    DDL raises). PostgreSQL gets ``default_transaction_read_only = on``
    as a libpq connect OPTION (the app/db/session.py statement_timeout
    precedent): the GUC applies at session start, BEFORE SQLAlchemy
    autobegins any transaction — a ``SET`` issued through
    ``conn.execute`` lands INSIDE the already-begun transaction and
    leaves that first transaction writable (Codex round-1 P2). The
    caller keeps this connection for the whole run — the enforcement
    is per-connection, not per-engine.
    """
    dialect_name = sa.engine.url.make_url(url).get_dialect().name
    if dialect_name == "postgresql":
        engine = sa.create_engine(
            url,
            echo=False,
            connect_args={"options": "-c default_transaction_read_only=on"},
        )
        conn = engine.connect()
        # hard invariant: the GUC must be visible on this very session
        setting = conn.execute(
            sa.text("SELECT current_setting('default_transaction_read_only')")
        ).scalar()
        if str(setting).lower() != "on":
            conn.close()
            engine.dispose()
            raise RuntimeError(
                "default_transaction_read_only is not 'on' on this "
                "connection — refusing to run the inventory"
            )
        return engine, conn
    if dialect_name == "sqlite":
        engine = sa.create_engine(url, echo=False)
        conn = engine.connect()
        conn.execute(sa.text("PRAGMA query_only = ON"))
        return engine, conn
    raise RuntimeError(
        f"unsupported dialect {dialect_name!r} — this inventory targets "
        "postgresql (production) and sqlite (tests)"
    )


def _tags_list(value) -> list:
    """queue_tags normalizer: PostgreSQL drivers parse the JSON column
    into a list, SQLite returns the raw string — normalize to a list so
    membership is exact on both dialects (a substring check would false-
    positive on tags like 'general_x')."""
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else [parsed]
        except ValueError:
            return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _quote(conn, identifier: str) -> str:
    return conn.dialect.identifier_preparer.quote(identifier)


def _rows(conn, sql: str, params: dict | None = None):
    return conn.execute(sa.text(sql), params or {}).mappings().fetchall()


def _scalar(conn, sql: str, params: dict | None = None):
    row = conn.execute(sa.text(sql), params or {}).scalar()
    return row


# ============================================================================
# foreign-key introspection (doctors / users referencing surfaces)
# ============================================================================


def _introspect_fk_surfaces(conn) -> list[dict]:
    """Every (table, column) with a foreign key to doctors or users,
    plus each table's primary-key columns.

    Introspected from the live schema — not hardcoded — so surfaces
    added after this script was written still appear in the
    inbound-reference dry-run (ADR gate 6: "exact-ID dry-run deletion
    reports zero inbound references"). Single-column FKs only: every
    doctors/users reference in this schema is single-column.

    The pk_columns ride along because association tables (user_roles,
    role_permissions, group_roles, user_groups_members — the
    role_permission.py models) carry COMPOSITE primary keys and no
    ``id`` column: sampling must not assume one (Codex round-1 P1).
    """
    dialect = conn.dialect.name
    surfaces: list[dict] = []
    if dialect == "postgresql":
        rows = _rows(
            conn,
            """
            SELECT conrelid::regclass::text AS table_name,
                   a.attname AS column_name,
                   confrelid::regclass::text AS ref_table
            FROM pg_constraint c
            JOIN pg_attribute a
              ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
            WHERE c.contype = 'f'
              AND c.confrelid IN ('doctors'::regclass, 'users'::regclass)
            ORDER BY table_name, column_name
            """,
        )
        for r in rows:
            surfaces.append(
                {
                    "table": r["table_name"],
                    "column": r["column_name"],
                    "ref_table": r["ref_table"],
                }
            )
    else:  # sqlite
        tables = _rows(
            conn,
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name NOT LIKE 'sqlite_%'",
        )
        for t in tables:
            for fk in _rows(
                conn, f"PRAGMA foreign_key_list({_quote(conn, t['name'])})"
            ):
                if fk["table"] in ("doctors", "users"):
                    surfaces.append(
                        {
                            "table": t["name"],
                            "column": fk["from"],
                            "ref_table": fk["table"],
                        }
                    )
        surfaces.sort(key=lambda s: (s["table"], s["column"]))

    # attach the primary-key columns per referencing table (sampling
    # uses them; a composite PK means NO single-column sample)
    for surface in surfaces:
        surface["pk_columns"] = _pk_columns(conn, surface["table"])
    return surfaces


def _pk_columns(conn, table: str) -> list[str]:
    """The table's primary-key column names (order-stable, may be [])."""
    if conn.dialect.name == "postgresql":
        return [
            r["attname"]
            for r in _rows(
                conn,
                """
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a
                  ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = :t::regclass AND i.indisprimary
                ORDER BY a.attnum
                """,
                {"t": table},
            )
        ]
    return [
        r["name"]
        for r in _rows(conn, f"PRAGMA table_info({_quote(conn, table)})")
        if r["pk"]
    ]


# ============================================================================
# report sections
# ============================================================================


def _collect_schema_contract(conn) -> tuple[dict, list[str]]:
    dialect = conn.dialect.name
    problems: list[str] = []

    versions: list[str] = []
    try:
        versions = [
            str(r["version_num"])
            for r in _rows(conn, "SELECT version_num FROM alembic_version")
        ]
    except Exception:
        problems.append("alembic_version table missing (not an alembic DB?)")

    version = versions[0] if len(versions) == 1 else None
    # STRICT head validation (Codex round-1 P2): a stale head
    # (0059/0062 with manually-repaired constraints) or a multi-head
    # state must exit 2, not silently pass on the constraint names.
    if len(versions) == 0 and "alembic_version table missing" not in " ".join(problems):
        problems.append("alembic_version is empty")
    elif len(versions) > 1:
        problems.append(
            "alembic_version has multiple heads: "
            + ", ".join(repr(v) for v in versions)
        )
    elif len(versions) == 1 and versions[0] != EXPECTED_ALEMBIC_HEAD:
        problems.append(
            f"alembic head is {versions[0]!r}, expected exactly "
            f"{EXPECTED_ALEMBIC_HEAD!r} (stale, unrecognized or newer "
            "than this tool pins — see EXPECTED_ALEMBIC_HEAD)"
        )

    check_present = False
    partial_unique_present = False
    if dialect == "postgresql":
        constraint_names = {
            r["conname"]
            for r in _rows(
                conn,
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = 'daily_queues'::regclass",
            )
        }
        index_names = {
            r["indexname"]
            for r in _rows(
                conn,
                "SELECT indexname FROM pg_indexes WHERE tablename = 'daily_queues'",
            )
        }
        check_present = CHECK_CONSTRAINT_NAME in constraint_names
        partial_unique_present = PARTIAL_UNIQUE_NAME in index_names
    else:  # sqlite
        ddl = _scalar(
            conn,
            "SELECT sql FROM sqlite_master WHERE type = 'table' "
            "AND name = 'daily_queues'",
        )
        check_present = bool(ddl) and CHECK_CONSTRAINT_NAME in (ddl or "")
        partial_unique_present = False
        for idx in _rows(conn, "PRAGMA index_list('daily_queues')"):
            if (
                idx["name"] == PARTIAL_UNIQUE_NAME
                and idx["unique"]
                and idx.get("partial")
            ):
                partial_unique_present = True
                break

    if not check_present:
        problems.append(f"daily_queues CHECK {CHECK_CONSTRAINT_NAME} not found")
    if not partial_unique_present:
        problems.append(f"daily_queues partial unique {PARTIAL_UNIQUE_NAME} not found")

    xor_violations = int(
        _scalar(
            conn,
            f"SELECT COUNT(*) FROM daily_queues WHERE {_OWNER_XOR_SQL} <> 1",
        )
        or 0
    )
    if xor_violations:
        problems.append(
            f"{xor_violations} daily_queues rows violate the owner XOR contract"
        )

    active_dup_groups = int(
        _scalar(
            conn,
            "SELECT COUNT(*) FROM ("
            "  SELECT day, queue_resource_id FROM daily_queues"
            "  WHERE active = true AND queue_resource_id IS NOT NULL"
            "  GROUP BY day, queue_resource_id HAVING COUNT(*) > 1"
            ")",
        )
        or 0
    )
    if active_dup_groups:
        problems.append(
            f"{active_dup_groups} ACTIVE (day, queue_resource_id) duplicate "
            "groups (the 0063 partial unique is violated or absent)"
        )

    section = {
        "alembic_version": version,
        "check_constraint": {
            "name": CHECK_CONSTRAINT_NAME,
            "present": check_present,
        },
        "partial_unique": {
            "name": PARTIAL_UNIQUE_NAME,
            "present": partial_unique_present,
        },
        "owner_xor_violations": xor_violations,
        "active_resource_day_duplicate_groups": active_dup_groups,
        "stage_d_contract_ok": not problems,
        "problems": problems,
    }
    return section, problems


def _collect_synthetic_pairs(conn) -> tuple[dict, list[dict]]:
    """The exact 0055 identities + drift notes (never an abort)."""
    pairs: list[dict] = []
    notes: list[str] = []

    for spec in SYNTHETIC_PAIR_SPECS:
        username = spec["username"]
        users = _rows(
            conn,
            "SELECT id, username, role, is_active FROM users "
            "WHERE username = :u ORDER BY id",
            {"u": username},
        )
        pair: dict = {
            "username": username,
            "expected_doctor_specialty": spec["queue_tag"],
            "seed_role": spec["seed_role"],
            "user_rows": len(users),
            "user": None,
            "doctor": None,
            "drift": [],
        }
        if len(users) != 1:
            pair["drift"].append(
                f"expected exactly 1 users row for {username!r}, " f"found {len(users)}"
            )
            if users:
                pair["user"] = dict(users[0])
            pairs.append(pair)
            continue

        u = dict(users[0])
        password_marker_ok = None
        # hashed_password is opaque; only the marker prefix is knowable
        # without verification (the value is a disabled hash, not a
        # secret comparison).
        stored_hash = _scalar(
            conn, "SELECT hashed_password FROM users WHERE id = :i", {"i": u["id"]}
        )
        if isinstance(stored_hash, str) and stored_hash:
            password_marker_ok = stored_hash.startswith("!disabled:")
        u["disabled_marker_ok"] = password_marker_ok
        if password_marker_ok is False:
            pair["drift"].append(
                "hashed_password does not carry the '!disabled:' marker — "
                "the row may not be the provisioned synthetic"
            )
        # the internal-only role sentinel (Codex round-1 P2): 0056
        # moved ecg_resource/general_resource to 'Resource', 0057 moved
        # lab_resource — any other role is not the provisioned identity
        u["role_matches_sentinel"] = u.get("role") == EXPECTED_SYNTHETIC_ROLE
        if not u["role_matches_sentinel"]:
            pair["drift"].append(
                f"user role is {u.get('role')!r}, expected the internal-only "
                f"{EXPECTED_SYNTHETIC_ROLE!r} sentinel (0056/0057)"
            )
        pair["user"] = u
        if not u["is_active"]:
            pair["drift"].append("user row is inactive")

        doctors = _rows(
            conn,
            "SELECT id, specialty, active, start_number_online, "
            "max_online_per_day FROM doctors WHERE user_id = :i ORDER BY id",
            {"i": u["id"]},
        )
        pair["doctor_rows"] = len(doctors)
        if len(doctors) != 1:
            pair["drift"].append(
                f"expected exactly 1 linked doctors row, found {len(doctors)}"
            )
        if doctors:
            d = dict(doctors[0])
            pair["doctor"] = d
            if d["specialty"] != spec["queue_tag"]:
                pair["drift"].append(
                    f"linked Doctor specialty={d['specialty']!r}, expected "
                    f"{spec['queue_tag']!r}"
                )
            if not d["active"]:
                pair["drift"].append("linked Doctor row is inactive")
        pairs.append(pair)

    for p in pairs:
        notes.extend(p["drift"])

    return {"pairs": pairs, "drift_notes": notes}, pairs


def _collect_inbound_references(conn, pairs: list[dict]) -> tuple[dict, list[dict]]:
    """Per synthetic pair: referencing-row counts on EVERY FK surface.

    This is the exact-ID dry-run (ADR gate 6): what RQ-15.d deletion
    would have to clear first. Two references are EXPECTED and do not
    block: daily_queues.specialist_id on the general pair (its history
    is exactly what RQ-15.c transfers to the archival resource) and
    the pair's own doctors.user_id linkage (deleted together with the
    user). Everything else — including a lab/ecg specialist reference,
    which the 0063 conversion should have cleared — is a blocker.
    """
    surfaces = _introspect_fk_surfaces(conn)
    findings: list[dict] = []

    for pair in pairs:
        per_surface: list[dict] = []
        user = pair.get("user") or {}
        doctor = pair.get("doctor") or {}
        for surface in surfaces:
            row_id = None
            if surface["ref_table"] == "users" and user.get("id") is not None:
                row_id = user["id"]
            elif surface["ref_table"] == "doctors" and doctor.get("id") is not None:
                row_id = doctor["id"]
            if row_id is None:
                per_surface.append(
                    {
                        "table": surface["table"],
                        "column": surface["column"],
                        "ref_table": surface["ref_table"],
                        "count": None,
                    }
                )
                continue
            table_q = _quote(conn, surface["table"])
            column_q = _quote(conn, surface["column"])
            count = int(
                _scalar(
                    conn,
                    f"SELECT COUNT(*) FROM {table_q} WHERE {column_q} = :rid",
                    {"rid": row_id},
                )
                or 0
            )
            # sample via the table's OWN primary key; association tables
            # (user_roles, role_permissions, group_roles,
            # user_groups_members) carry composite PKs and no id column
            # — there the count is the evidence and samples are None
            # (Codex round-1 P1)
            sample: list | None = None if count else []
            if count and len(surface.get("pk_columns") or []) == 1:
                pk_q = _quote(conn, surface["pk_columns"][0])
                sample = [
                    r["sid"]
                    for r in _rows(
                        conn,
                        f"SELECT {pk_q} AS sid FROM {table_q} "
                        f"WHERE {column_q} = :rid ORDER BY {pk_q} LIMIT 5",
                        {"rid": row_id},
                    )
                ]
            expected = False
            if (
                surface["table"] == "daily_queues"
                and surface["column"] == "specialist_id"
                and pair["username"] == "general_resource"
            ):
                expected = True  # RQ-15.c converts this history
            elif surface["table"] == "doctors" and surface["column"] == "user_id":
                # the pair's own linkage is deleted together with the
                # user; any OTHER doctor row linking this user is drift
                expected = count == 1 and doctor.get("id") in sample
            per_surface.append(
                {
                    "table": surface["table"],
                    "column": surface["column"],
                    "ref_table": surface["ref_table"],
                    "count": count,
                    "sample_ids": sample,
                    "expected": expected,
                }
            )
        blocking = [s for s in per_surface if s.get("count") and not s["expected"]]
        findings.append(
            {
                "username": pair["username"],
                "user_id": user.get("id"),
                "doctor_id": doctor.get("id"),
                "surfaces": per_surface,
                "blocking_surfaces": blocking,
            }
        )

    return {"surfaces_introspected": len(surfaces), "pairs": findings}, findings


def _collect_routing_surfaces(conn, pairs: list[dict]) -> tuple[dict, list[dict]]:
    """Everything still routing onto `general` or a synthetic Doctor.

    The fallback surface is derived from the COMPLETE runtime behavior,
    not just the named legacy vocabulary (Codex round-1 P1):
    MorningAssignmentService.ensure_daily_queues_for_all_tags and
    _assign_visit_to_queue write EVERY service tag WITHOUT an ACTIVE
    queue_resources row under general_resource (the universal
    fallback). So an active service is on the general-fallback surface
    when its queue_tag is non-NULL and NOT resolvable by an ACTIVE
    registry row — 'cardio' and 'cosmetology' exactly as much as
    'general' itself. Plus department_key='general' and services whose
    doctor_id IS a synthetic Doctor.
    """
    synthetic_doctor_ids = [(p.get("doctor") or {}).get("id") for p in pairs]
    synthetic_doctor_ids = [i for i in synthetic_doctor_ids if i is not None]

    active_registry_tags = {
        r["queue_tag"]
        for r in _rows(
            conn,
            "SELECT queue_tag FROM queue_resources WHERE active = true",
        )
    }

    stmt = sa.text("""
        SELECT id, code, name, active, requires_doctor, queue_tag,
               department_key, doctor_id
        FROM services
        WHERE queue_tag IS NOT NULL
           OR department_key = 'general'
           OR doctor_id IN :doc_ids
        ORDER BY id
        """).bindparams(sa.bindparam("doc_ids", expanding=True))
    services = [
        dict(r)
        for r in conn.execute(stmt, {"doc_ids": synthetic_doctor_ids or [0]}).mappings()
    ]
    # classify each service's reason against the complete fallback
    services = [
        s
        for s in services
        if s["queue_tag"] is not None
        or s["department_key"] == "general"
        or s["doctor_id"] in synthetic_doctor_ids
    ]
    for s in services:
        reasons = []
        if s["queue_tag"] is not None and s["queue_tag"] not in active_registry_tags:
            if s["queue_tag"] in GENERAL_FALLBACK_TAGS:
                reasons.append(
                    f"queue_tag={s['queue_tag']!r} (legacy general-fallback "
                    "vocabulary, no ACTIVE QueueResource)"
                )
            else:
                reasons.append(
                    f"queue_tag={s['queue_tag']!r} has no ACTIVE QueueResource "
                    "— the morning pre-create/batch universal fallback "
                    "writes it under general_resource"
                )
        if s["department_key"] == "general":
            reasons.append("department_key='general'")
        if s["doctor_id"] in synthetic_doctor_ids:
            reasons.append("doctor_id is a synthetic Doctor")
        s["reasons"] = reasons

    # a service whose tag resolves to an ACTIVE registry row (and with no
    # department/doctor reason) is NOT a general surface — keep it out
    services = [s for s in services if s["reasons"]]

    profiles = [
        dict(r)
        for r in _rows(
            conn,
            "SELECT id, key, title, is_active, show_on_qr_page, queue_tags "
            "FROM queue_profiles ORDER BY id",
        )
    ]
    for p in profiles:
        p["queue_tags"] = _tags_list(p.get("queue_tags"))
    profiles = [p for p in profiles if "general" in p["queue_tags"]]

    department = _rows(
        conn,
        "SELECT * FROM departments WHERE key = 'general'",
    )
    department = [dict(r) for r in department]

    specialty_drift = [
        dict(r)
        for r in _rows(
            conn,
            "SELECT id, code, title_ru, active FROM medical_specialties "
            "WHERE code = 'general'",
        )
    ]

    section = {
        "legacy_fallback_vocabulary": list(GENERAL_FALLBACK_TAGS),
        "active_registry_tags": sorted(active_registry_tags),
        "services": services,
        "queue_profiles_with_general_tag": profiles,
        "department_general": department,
        "medical_specialty_general_drift": specialty_drift,
    }
    return section, services


def _collect_general_queues(conn, pairs: list[dict]) -> tuple[dict, list[dict]]:
    """Every queue tagged 'general' or owned by a synthetic Doctor.

    Per row: entry totals, live-entry count (waiting/called/in_service/
    diagnostics — the 0059 contract) and the cutover classification:
    active_live_blocker / active_empty / inactive_historical.
    """
    synthetic_doctor_ids = [(p.get("doctor") or {}).get("id") for p in pairs]
    synthetic_doctor_ids = [i for i in synthetic_doctor_ids if i is not None]

    stmt = sa.text("""
        SELECT q.id, q.day, q.queue_tag, q.active, q.specialist_id,
               q.queue_resource_id, q.cabinet_number,
               (SELECT COUNT(*) FROM queue_entries e WHERE e.queue_id = q.id)
                   AS entry_count,
               (SELECT COUNT(*) FROM queue_entries e
                WHERE e.queue_id = q.id AND e.status IN :live)
                   AS live_entry_count,
               (SELECT COUNT(*) FROM queue_entries e
                WHERE e.queue_id = q.id AND e.status = 'completed')
                   AS completed_entry_count,
               (SELECT COUNT(*) FROM queue_entries e
                WHERE e.queue_id = q.id AND e.status = 'cancelled')
                   AS cancelled_entry_count
        FROM daily_queues q
        WHERE q.specialist_id IN :doc_ids OR q.queue_tag = 'general'
        ORDER BY q.day, q.id
        """).bindparams(
        sa.bindparam("doc_ids", expanding=True),
        sa.bindparam("live", expanding=True),
    )
    queues = [
        dict(r)
        for r in conn.execute(
            stmt,
            {
                "doc_ids": synthetic_doctor_ids or [0],
                "live": list(LIVE_ENTRY_STATUSES),
            },
        ).mappings()
    ]

    for q in queues:
        q["day"] = str(q["day"])
        q["live_entry_statuses"] = list(LIVE_ENTRY_STATUSES)
        if q["active"] and q["live_entry_count"]:
            q["classification"] = "active_live_blocker"
        elif q["active"]:
            q["classification"] = "active_empty"
        else:
            q["classification"] = "inactive_historical"

    section = {
        "total": len(queues),
        "classifications": {
            "active_live_blocker": sum(
                1 for q in queues if q["classification"] == "active_live_blocker"
            ),
            "active_empty": sum(
                1 for q in queues if q["classification"] == "active_empty"
            ),
            "inactive_historical": sum(
                1 for q in queues if q["classification"] == "inactive_historical"
            ),
        },
        "queues": queues,
    }
    return section, queues


def _collect_sentinel_doctors(conn, pairs: list[dict]) -> dict:
    """Doctors with specialty='general' EXCLUDING the synthetic pair.

    The population RQ-15.d must NEVER touch (the incomplete-onboarding
    sentinel, ADR gate 6). Listed so the operator can see the blast
    radius of any naive "delete where specialty='general'".
    """
    synthetic_doctor_ids = [(p.get("doctor") or {}).get("id") for p in pairs]
    synthetic_doctor_ids = [i for i in synthetic_doctor_ids if i is not None]

    stmt = sa.text("""
        SELECT d.id, d.active, d.user_id, u.username
        FROM doctors d
        LEFT JOIN users u ON u.id = d.user_id
        WHERE LOWER(TRIM(d.specialty)) = 'general'
        """)
    rows = [dict(r) for r in conn.execute(stmt).mappings()]
    sentinel = [r for r in rows if r["id"] not in synthetic_doctor_ids]
    for r in sentinel:
        r["never_delete"] = True
    return {
        "total_specialty_general": len(rows),
        "synthetic_among_them": len(rows) - len(sentinel),
        "sentinel_doctors": sentinel,
        "policy": "these rows are the incomplete-Doctor onboarding "
        "sentinel (INCOMPLETE_DOCTOR_SPECIALTY) — RQ-15.d never deletes "
        "them; only the exact 0055 synthetic pairs are deleted",
    }


def _collect_registry(conn) -> dict:
    resources = [
        dict(r)
        for r in _rows(
            conn,
            "SELECT id, code, queue_tag, display_name, active, "
            "default_cabinet FROM queue_resources ORDER BY id",
        )
    ]
    general_rows = [r for r in resources if r["queue_tag"] == "general"]
    return {
        "rows": resources,
        "general_resource_rows": general_rows,
        "note": "Stage E must not seed an active general resource; any "
        "general row (active or not) is drift against the D-08 decision "
        "until the RQ-15.c archival row is created deliberately",
    }


# ============================================================================
# blockers + operator map
# ============================================================================


def _build_blockers(
    schema_problems: list[str],
    synthetic_drift: list[str],
    inbound: list[dict],
    services: list[dict],
    queues: list[dict],
    specialty_drift: list[dict],
    registry: dict,
) -> list[dict]:
    blockers: list[dict] = []
    for p in schema_problems:
        blockers.append({"kind": "stage_d_contract", "detail": p})

    # a missing/malformed synthetic pair is drift the operator must
    # adjudicate: the exact paired deletion targets these rows, and a
    # pair that does not match the 0055 identity is not deletable blindly
    for note in synthetic_drift:
        blockers.append({"kind": "synthetic_pair_drift", "detail": note})

    for pair in inbound:
        for s in pair["blocking_surfaces"]:
            blockers.append(
                {
                    "kind": "inbound_reference",
                    "detail": (
                        f"table {s['table']}.{s['column']} holds "
                        f"{s['count']} row(s) referencing the synthetic "
                        f"{pair['username']} "
                        f"({'user' if s['ref_table'] == 'users' else 'doctor'})"
                    ),
                }
            )

    active_services = [s for s in services if s["active"]]
    for s in active_services:
        blockers.append(
            {
                "kind": "active_general_service",
                "detail": (
                    f"service id={s['id']} code={s.get('code')!r} "
                    f"name={s.get('name')!r} still routes via "
                    f"{', '.join(s['reasons'])} — assign an explicit "
                    "owner (Doctor or resource tag) or disable it"
                ),
            }
        )

    for q in queues:
        if q["classification"] == "active_live_blocker":
            blockers.append(
                {
                    "kind": "live_general_queue",
                    "detail": (
                        f"daily_queues id={q['id']} day={q['day']} "
                        f"tag={q['queue_tag']!r} is ACTIVE with "
                        f"{q['live_entry_count']} live entries — the "
                        "cutover blocks until an operator resolves them"
                    ),
                }
            )

    for r in specialty_drift:
        blockers.append(
            {
                "kind": "medical_specialty_drift",
                "detail": (
                    f"medical_specialties id={r['id']} code='general' — "
                    "the catalog never stores the sentinel; remove the row"
                ),
            }
        )

    for r in registry["general_resource_rows"]:
        blockers.append(
            {
                "kind": "general_registry_row",
                "detail": (
                    f"queue_resources id={r['id']} carries queue_tag="
                    "'general' — unexpected before the deliberate "
                    "RQ-15.c archival row"
                ),
            }
        )

    return blockers


def _build_operator_map(
    services: list[dict], queues: list[dict], profiles: list[dict]
) -> dict:
    """The fillable decision map for the operator (D-08: no guessing).

    Every entry ships with decision=null; the operator completes each
    one explicitly (assign a real Doctor, an explicit resource tag, or
    disable/deactivate). RQ-15.b consumes the completed map.
    """
    items: list[dict] = []

    for s in services:
        if not s["active"]:
            continue
        items.append(
            {
                "surface": "service",
                "id": s["id"],
                "code": s.get("code"),
                "name": s.get("name"),
                "queue_tag": s.get("queue_tag"),
                "requires_doctor": s.get("requires_doctor"),
                "doctor_id": s.get("doctor_id"),
                "reasons": s["reasons"],
                "decision": None,
                "decision_options": [
                    "assign_doctor",
                    "retag_resource",
                    "disable_service",
                ],
            }
        )

    for q in queues:
        if q["classification"] == "inactive_historical":
            continue  # RQ-15.c archives these; no per-row operator input
        items.append(
            {
                "surface": "daily_queue",
                "id": q["id"],
                "day": q["day"],
                "queue_tag": q.get("queue_tag"),
                "active": q["active"],
                "live_entry_count": q["live_entry_count"],
                "classification": q["classification"],
                "decision": None,
                "decision_options": [
                    "resolve_entries_then_deactivate",
                    "deactivate",
                ],
            }
        )

    for p in profiles:
        if not p["is_active"]:
            continue
        items.append(
            {
                "surface": "queue_profile",
                "id": p["id"],
                "key": p.get("key"),
                "queue_tags": p.get("queue_tags"),
                "show_on_qr_page": p.get("show_on_qr_page"),
                "decision": None,
                "decision_options": ["retire_profile", "keep_profile"],
            }
        )

    return {
        "report_version": REPORT_VERSION,
        "how_to_fill": (
            "For every item set decision to one of decision_options "
            "(plus the accompanying target fields). No inference from "
            "service names is allowed (D-08). RQ-15.b consumes the "
            "completed map; an item with decision=null blocks it."
        ),
        "items": items,
    }


# ============================================================================
# runner
# ============================================================================


def run_inventory(database_url: str) -> tuple[dict, dict, int]:
    """Produce (report, operator_map, exit_code) — 0/1/2, module docstring."""
    engine, conn = _connect_read_only(database_url)
    dialect = engine.dialect.name
    try:
        schema, schema_problems = _collect_schema_contract(conn)
        pairs_section, pairs = _collect_synthetic_pairs(conn)
        inbound_section, inbound_findings = _collect_inbound_references(conn, pairs)
        routing_section, services = _collect_routing_surfaces(conn, pairs)
        queues_section, queues = _collect_general_queues(conn, pairs)
        sentinel_section = _collect_sentinel_doctors(conn, pairs)
        registry_section = _collect_registry(conn)

        blockers = _build_blockers(
            schema_problems,
            pairs_section["drift_notes"],
            inbound_findings,
            services,
            queues,
            routing_section["medical_specialty_general_drift"],
            registry_section,
        )
        operator_map = _build_operator_map(
            services,
            queues,
            routing_section["queue_profiles_with_general_tag"],
        )
    finally:
        conn.close()
        engine.dispose()

    report = {
        "report_version": REPORT_VERSION,
        "tool": TOOL_NAME,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        # the DIALECT only, never the URL: these files are retained as
        # Stage E evidence and a database URL (even password-redacted)
        # must not land in evidence files or logs; the operator records
        # the exact target via the runbook's command line
        "database_dialect": dialect,
        "schema_contract": schema,
        "synthetic_pairs": pairs_section,
        "inbound_references": inbound_section,
        "routing_surfaces": routing_section,
        "general_queues": queues_section,
        "sentinel_doctors": sentinel_section,
        "registry": registry_section,
        "blockers": blockers,
        "operator_map_items": len(operator_map["items"]),
    }

    if schema_problems:
        exit_code = 2
    elif blockers or operator_map["items"]:
        exit_code = 1
    else:
        exit_code = 0
    return report, operator_map, exit_code


def _print_summary(report: dict, exit_code: int) -> None:
    schema = report["schema_contract"]
    print(f"[{TOOL_NAME}] Stage E general retirement inventory")
    print(f"  database dialect: {report['database_dialect']}")
    print(f"  alembic_version: {schema['alembic_version']}")
    print(
        f"  stage D contract: "
        f"{'OK' if schema['stage_d_contract_ok'] else 'MISSING/VIOLATED'} "
        f"(check={schema['check_constraint']['present']}, "
        f"partial_unique={schema['partial_unique']['present']}, "
        f"xor_violations={schema['owner_xor_violations']}, "
        f"active_dups={schema['active_resource_day_duplicate_groups']})"
    )
    for pair in report["synthetic_pairs"]["pairs"]:
        u, d = pair["user"], pair["doctor"]
        print(
            f"  synthetic {pair['username']}: "
            f"user_id={u['id'] if u else None} "
            f"doctor_id={d['id'] if d else None} "
            f"specialty={d['specialty'] if d else None} "
            f"drift={pair['drift'] or 'none'}"
        )
    print(
        f"  inbound references: "
        f"{report['inbound_references']['surfaces_introspected']} FK surfaces "
        "introspected (see report for counts)"
    )
    rq = report["routing_surfaces"]
    print(
        f"  routing surfaces: services={len(rq['services'])} "
        f"profiles={len(rq['queue_profiles_with_general_tag'])} "
        f"specialty_catalog_drift={len(rq['medical_specialty_general_drift'])}"
    )
    gq = report["general_queues"]["classifications"]
    print(
        f"  general queues: {report['general_queues']['total']} "
        f"(blockers={gq['active_live_blocker']}, "
        f"active_empty={gq['active_empty']}, "
        f"historical={gq['inactive_historical']})"
    )
    sd = report["sentinel_doctors"]
    print(f"  sentinel doctors (NEVER deleted): {len(sd['sentinel_doctors'])}")
    print(f"  registry rows: {len(report['registry']['rows'])}")
    print(f"  blockers: {len(report['blockers'])}")
    print(f"  operator map items: {report['operator_map_items']}")
    print(f"exit code: {exit_code}")


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "RQ-15.a read-only inventory for the Stage E `general` "
            "retirement (ADR-001 D-08). Never writes to the database."
        )
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy database URL. Falls back to DATABASE_URL env.",
    )
    parser.add_argument(
        "--json",
        default=None,
        help="Write the full JSON report to this path.",
    )
    parser.add_argument(
        "--operator-map",
        default=None,
        help="Write the fillable operator map (JSON) to this path.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Also print the full JSON report to stdout.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    import os

    args = _parse_args(argv)
    database_url = args.database_url or os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "error: --database-url or DATABASE_URL is required",
            file=sys.stderr,
        )
        return 2

    report, operator_map, exit_code = run_inventory(database_url)

    _print_summary(report, exit_code)

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8"
        )
        print(f"report written to {args.json}")
    if args.operator_map:
        Path(args.operator_map).parent.mkdir(parents=True, exist_ok=True)
        Path(args.operator_map).write_text(
            json.dumps(operator_map, indent=2, default=str), encoding="utf-8"
        )
        print(f"operator map written to {args.operator_map}")
    if args.pretty:
        print(json.dumps(report, indent=2, default=str))

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
