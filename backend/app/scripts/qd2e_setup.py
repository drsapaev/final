"""QD-2E test-environment setup: provision the catalog/entities that the
0066 general-retirement cutover expects, at the 2026-09-12 production
SNAPSHOT identities, on a DISPOSABLE test database.

NEVER point this command at production — it creates test accounts with
disabled credentials and force-ids rows to mirror the operator map.

Single transaction: any conflict rolls the whole group back (nothing
partial). Idempotent: the exact existing state is a no-op. Every action
is journaled (no secrets). The decision columns of the mapped services
(doctor_id / requires_doctor / queue_tag flips) are NOT touched — they
belong to migration 0066, which this setup prepares the catalog for.

Usage:
  python -m app.scripts.qd2e_setup --database-url postgresql+psycopg://... \
      [--dry-run]

``--dry-run`` is PLAN + conflict verification only: every identity
check runs, the row writes are rolled back, and — review round 4 (P2)
— the sequences are LEFT UNTOUCHED. PostgreSQL ``setval()``/``nextval()``
are NOT transactional (the rollback never undoes them), so a plan run
must not execute ``setval()`` at all and must not run the auto-id
INSERTs (medical_specialties / queue_resources) that consume
``nextval()``; the explicit-id INSERTs (users / doctors / services)
touch no sequence and still execute inside the rolled-back transaction
(they keep validating the constraints). The apply-mode sequence sync
never DECREASES a sequence: it only advances it up to MAX(id) when the
snapshot ids have passed the serial's next value.

Exit codes: 0 = applied/no-op, 1 = conflict (rolled back, nothing
changed), 2 = usage/schema error.
"""

from __future__ import annotations

import argparse
import sys

import sqlalchemy as sa

_MIGRATION_NAME = "qd2e_setup"

_DISABLED_HASH = "!disabled:qd2e-test-setup"

_SCHEMA_VERSION = "0065_queue_numbering_unique"

# (id, username, role) — the 2026-09-12 production snapshot identities the
# 0066 operator map and the refinement decisions bind against.
_USERS: tuple[tuple[int, str, str], ...] = (
    (22, "Cardio", "Doctor"),
    (26, "Dermatolog", "Doctor"),
    (27, "Stomatolog", "Doctor"),
    (28, "Laboratoriya", "Lab"),
    (29, "UZD", "Doctor"),
    (30, "Невролог", "Doctor"),
)

# (id, user_id, specialty) — start/max caps mirror the 0055 defaults.
_DOCTORS: tuple[tuple[int, int, str], ...] = (
    (10, 22, "cardiology"),
    (15, 26, "dermatology"),
    (16, 27, "dentistry"),
    (17, 29, "ultrason"),
    (18, 30, "neurology"),
)

# (code, title_ru) — the specialty catalog entries the refinement doctors
# carry (ultrason/neurology were added by the operator on 2026-09-14).
_SPECIALTIES: tuple[tuple[str, str, int], ...] = (
    ("cardiology", "Кардиология", 10),
    ("dermatology", "Дерматология", 20),
    ("dentistry", "Стоматология", 30),
    ("ultrason", "УЗИ", 40),
    ("neurology", "Неврология", 50),
)

# (code, queue_tag, display_name) — the 0059-shape ACTIVE registry rows.
_REGISTRY: tuple[tuple[str, str, str], ...] = (
    ("lab", "lab", "Лаборатория"),
    ("ecg", "ecg", "ЭКГ"),
)

# (snapshot_id, code, name, queue_tag, department_key, requires_doctor,
#  is_consultation) — the mapped services at their PRE-STATES with the
# PRODUCTION is_consultation values (read-only production census
# 2026-09-15; never derived from requires_doctor). The decision columns
# (the doctor assignments, the requires_doctor flips, the lab retags) are
# NOT touched here: migration 0066 applies them from the embedded map.
_SERVICES: tuple[tuple[int, str, str, str, str | None, bool, bool], ...] = (
    (3, "S01", "Консультация стоматолога", "stomatology", None, True, True),
    (1, "D01", "Консультация дерматолога-косметолога", "dermatology", None, True, True),
    (2, "K01", "Консультация кардиолога", "cardio", "cardiology", True, True),
    (127, "K11", "ЭхоКГ", "cardio", "cardiology", True, False),
    (90, "S10", "Рентгенография зуба", "stomatology", None, True, False),
    (125, "O10", "УЗИ", "ultrason", None, False, False),
    (126, "O20", "Невропатолог", "neurology", None, False, True),
    *[
        (sid, code, f"Лаб-услуга {code}", "general", None, False, False)
        for sid, code in (
            (21, "L03"), (11, "L14"), (27, "L15"), (22, "L16"), (24, "L17"),
            (23, "L18"), (20, "L19"), (28, "L20"), (29, "L21"), (52, "L22"),
            (63, "L23"), (53, "L24"), (12, "L25"), (72, "L26"), (30, "L27"),
            (32, "L28"), (73, "L29"), (44, "L30"), (74, "L31"), (62, "L32"),
            (61, "L33"), (60, "L34"), (33, "L35"), (25, "LAB_ALT"),
            (26, "LAB_AST"), (36, "LAB_BILE_URINE"), (31, "LAB_CA"),
            (51, "LAB_CRP"), (70, "LAB_FUNGI"), (34, "LAB_HBA1C"),
            (75, "LAB_IGE"), (71, "LAB_MALAS"), (50, "LAB_RF"),
        )
    ],
    *[
        (sid, code, f"Процедура {code}", "procedures", None, True, False)
        for sid, code in (
            (100, "P08"), (101, "P03"), (102, "P09"), (103, "P07"),
            (104, "P10"), (110, "C07"), (111, "C08"), (112, "C03"),
            (113, "C06"), (114, "C09"), (115, "C12"), (116, "C11"),
            (117, "C10"), (120, "D06"), (121, "D05"), (122, "D07"),
        )
    ],
)


def _journal(action: str, detail: str) -> None:
    """The change journal: every action, no secrets."""
    print(f"{_MIGRATION_NAME}: {action}: {detail}", flush=True)


def run_setup_in_connection(
    conn: sa.Connection, *, plan_only: bool = False
) -> dict[str, int]:
    """Provision everything inside the CALLER's transaction. Raises
    RuntimeError on any identity conflict (the caller rolls back).

    ``plan_only=True`` (the ``--dry-run`` mode) keeps every check and
    journal entry but performs ONLY the writes that PostgreSQL can
    fully undo: the auto-id INSERTs (medical_specialties /
    queue_resources — they consume a non-rollbackable ``nextval()``)
    and the sequence synchronization (``setval()`` is never undone by
    a rollback) are planned, not executed (review round 4, P2)."""
    counts: dict[str, int] = {
        "specialties": 0,
        "users": 0,
        "doctors": 0,
        "registry": 0,
        "services": 0,
    }
    _create_action = "would-create" if plan_only else "create"

    # ---------- specialties (natural key: code) ----------
    for code, title_ru, sort_order in _SPECIALTIES:
        row = conn.execute(
            sa.text("SELECT id FROM medical_specialties WHERE code = :c"),
            {"c": code},
        ).fetchone()
        if row is None:
            _journal(
                _create_action,
                f"medical_specialty {code!r}",
            )
            counts["specialties"] += 1
            if not plan_only:
                # auto-id INSERT -> consumes nextval(), which PostgreSQL
                # NEVER rolls back: a plan run must stay read-only for the
                # sequence (review round 4, P2)
                conn.execute(
                    sa.text(
                        "INSERT INTO medical_specialties (code, title_ru,"
                        " sort_order, active) VALUES (:c, :t, :s, true)"
                    ),
                    {"c": code, "t": title_ru, "s": sort_order},
                )
        else:
            _journal("no-op", f"medical_specialty {code!r} exists")

    # ---------- users (snapshot id + username identity) ----------
    for user_id, username, role in _USERS:
        row = conn.execute(
            sa.text("SELECT id, username FROM users WHERE id = :i"),
            {"i": user_id},
        ).fetchone()
        if row is None:
            _journal(
                _create_action,
                f"user id={user_id} {username!r} ({role})",
            )
            counts["users"] += 1
            # explicit snapshot id -> no sequence consumption: the plan
            # run still executes it inside the rolled-back transaction
            conn.execute(
                sa.text(
                    "INSERT INTO users (id, username, hashed_password, role,"
                    " is_active, is_superuser, must_change_password,"
                    " push_notifications_enabled)"
                    " VALUES (:i, :u, :p, :r, true, false, false, false)"
                ),
                {"i": user_id, "u": username, "p": _DISABLED_HASH, "r": role},
            )
        elif row.username != username:
            raise RuntimeError(
                f"user id={user_id} exists as {row.username!r}, the map "
                f"expects {username!r} — resolve the identity conflict "
                "manually"
            )
        else:
            _journal("no-op", f"user id={user_id} {username!r} exists")

    # ---------- doctors (snapshot id identity, user linkage pinned) ----------
    for doctor_id, user_id, specialty in _DOCTORS:
        row = conn.execute(
            sa.text(
                "SELECT id, user_id, specialty, active FROM doctors"
                " WHERE id = :i"
            ),
            {"i": doctor_id},
        ).fetchone()
        if row is not None and not row.active:
            # review P2 (e0248660a): an INACTIVE matching doctor would pass
            # the setup and make migration 0066 abort in its target-doctor
            # validation — report the conflict now, not after the fact
            raise RuntimeError(
                f"doctor id={doctor_id} exists but is INACTIVE — activate "
                "it (operator decision) or remove the row; the setup must "
                "leave a runnable environment"
            )
        if row is None:
            owner = conn.execute(
                sa.text("SELECT id FROM users WHERE id = :i"), {"i": user_id}
            ).fetchone()
            if owner is None:
                raise RuntimeError(
                    f"doctor id={doctor_id} expects owner user id={user_id} "
                    "— the user is missing; fix the environment"
                )
            _journal(
                _create_action,
                f"doctor id={doctor_id} user={user_id} specialty={specialty!r}",
            )
            counts["doctors"] += 1
            conn.execute(
                sa.text(
                    "INSERT INTO doctors (id, user_id, specialty,"
                    " start_number_online, max_online_per_day, active)"
                    " VALUES (:i, :u, :s, 1, 15, true)"
                ),
                {"i": doctor_id, "u": user_id, "s": specialty},
            )
        elif row.user_id != user_id or row.specialty != specialty:
            raise RuntimeError(
                f"doctor id={doctor_id} exists as (user={row.user_id}, "
                f"specialty={row.specialty!r}), the map expects "
                f"(user={user_id}, {specialty!r}) — resolve the identity "
                "conflict manually"
            )
        else:
            _journal("no-op", f"doctor id={doctor_id} exists")

    # ---------- registry rows (natural key: queue_tag) ----------
    for code, tag, display in _REGISTRY:
        # QD-2E review P2 (c48081f03): the probe used to check EXISTENCE
        # only (``SELECT id ... fetchone()``). Two failure shapes:
        # - an INACTIVE row passed as a ready resource and the setup
        #   reported a no-op — while migration 0066 (the next step of the
        #   runbook) requires EXACTLY ONE ACTIVE registry row per mapped
        #   tag and aborts: a false-green test environment;
        # - queue_resources.queue_tag carries NO unique constraint in the
        #   deployed 0058 DDL, so two rows can share the tag — a
        #   fetchone() saw whichever row the engine returned first (the
        #   same defect family as the services code-owner probe).
        # The probe now reads EVERY row of the tag and requires exactly
        # one ACTIVE carrier; anything else is an explicit conflict the
        # operator resolves (re-activating a disabled resource is an
        # operator decision — the deactivation may be intentional).
        rows = conn.execute(
            sa.text(
                "SELECT id, code, active FROM queue_resources WHERE queue_tag = :t"
            ),
            {"t": tag},
        ).fetchall()
        if len(rows) > 1:
            raise RuntimeError(
                f"queue_resources tag {tag!r} is ambiguous: {len(rows)} rows"
                " carry the tag (ids "
                + ", ".join(str(row.id) for row in rows)
                + ") — repair the registry, then re-run the setup"
            )
        if not rows:
            _journal(_create_action, f"queue_resource {code!r} ({tag!r})")
            counts["registry"] += 1
            if not plan_only:
                # auto-id INSERT -> consumes nextval(), which PostgreSQL
                # NEVER rolls back: a plan run must stay read-only for the
                # sequence (review round 4, P2)
                conn.execute(
                    sa.text(
                        "INSERT INTO queue_resources (code, queue_tag,"
                        " display_name, active, start_number_online,"
                        " max_online_per_day) VALUES (:c, :t, :d, true, 1, 15)"
                    ),
                    {"c": code, "t": tag, "d": display},
                )
        elif not bool(rows[0].active):
            raise RuntimeError(
                f"queue_resources tag {tag!r} (id={rows[0].id},"
                f" code={rows[0].code!r}) exists but is INACTIVE — the"
                " migration the setup prepares for requires exactly one"
                " ACTIVE registry row per mapped tag; re-activating it is"
                " an operator decision (the deactivation may itself be"
                " intentional), the setup never makes it silently"
            )
        elif rows[0].code != code:
            raise RuntimeError(
                f"queue_resources tag {tag!r} exists with code"
                f" {rows[0].code!r} (id={rows[0].id}), the map expects"
                f" {code!r} — resolve the identity conflict manually"
            )
        else:
            _journal("no-op", f"queue_resource {tag!r} exists")

    # ---------- services (snapshot id + code identity, PRE-STATES only) --
    for sid, code, name, tag, dept, requires, is_consultation in _SERVICES:
        # code-ownership check (review P1, 2026-09-15; review P2 on
        # 2c5ea05ce): a populated test database may carry a mapped code
        # under a DIFFERENT id — inserting a second logical service would
        # pollute the environment and make migration 0066 abort on the
        # undecided original; report the conflict instead.
        # QD-2E review P2 (2c5ea05ce): the conflict probe asks for ANY
        # FOREIGN owner of the code (id <> snapshot_id), not for the
        # first row the engine happens to return. Service.code carries
        # NO unique constraint (only Service.service_code does), so the
        # correct snapshot row and a foreign carrier of the same code can
        # coexist — a bare fetchone() then depends on the arbitrary row
        # order (reproduced on SQLite: the snapshot row first → the
        # conflict is missed → setup reports a clean no-op while the
        # catalog holds a conflict that the 0066 by-code pre-state check
        # would abort on). Any row the exclusion query returns is a
        # conflict, regardless of order.
        carrier = conn.execute(
            sa.text(
                "SELECT id FROM services WHERE code = :c AND id <> :sid"
            ),
            {"c": code, "sid": sid},
        ).fetchone()
        if carrier is not None:
            raise RuntimeError(
                f"service code={code!r} is owned by id={carrier.id}, the "
                f"map decides id={sid} — resolve the identity conflict "
                "manually"
            )
        row = conn.execute(
            sa.text("SELECT id, code FROM services WHERE id = :i"), {"i": sid}
        ).fetchone()
        if row is None:
            _journal(
                _create_action,
                f"service id={sid} {code!r} tag={tag!r} "
                f"requires_doctor={requires}",
            )
            counts["services"] += 1
            # explicit snapshot id -> no sequence consumption: the plan
            # run still executes it inside the rolled-back transaction
            conn.execute(
                sa.text(
                    "INSERT INTO services (id, code, name, queue_tag,"
                    " department_key, doctor_id, requires_doctor, active,"
                    " created_at, is_consultation,"
                    " allow_doctor_price_override)"
                    " VALUES (:i, :c, :n, :t, :d, NULL, :r, true,"
                    " now(), :ic, :ao)"
                ),
                {
                    "i": sid,
                    "c": code,
                    "n": name,
                    "t": tag,
                    "d": dept,
                    "r": requires,
                    "ic": is_consultation,
                    "ao": False,
                },
            )
        elif row.code != code:
            raise RuntimeError(
                f"service id={sid} exists as {row.code!r}, the map expects "
                f"{code!r} — resolve the identity conflict manually"
            )
        else:
            _journal("no-op", f"service id={sid} {code!r} exists")

    # ---------- synchronize the id sequences (review P1: forced ids do
    # not advance the serials — the next ordinary insert would collide
    # with a snapshot id) ----------
    # Review round 4 (P2): setval() is NOT transactional in PostgreSQL —
    # a rollback never restores the previous sequence state, so the
    # plan (--dry-run) mode must NOT touch the sequences at all. The
    # apply-mode sync also never DECREASES a sequence: it advances the
    # serial to MAX(id) only when the snapshot ids have passed the
    # serial's next value (a rollback-decrease would make later inserts
    # collide with previously handed-out ids).
    if plan_only:
        _journal(
            "sequence-plan",
            "users/doctors/services synchronization SKIPPED (setval is not"
            " transactional — a dry run must leave the sequences intact)",
        )
    else:
        for table in ("users", "doctors", "services"):
            _synchronize_table_sequence(conn, table)

    return counts


def _quote_qualified_identifier(name: str) -> str:
    """Quote a schema-qualified identifier returned by the catalog
    (pg_get_serial_sequence) for safe inlining into a statement."""
    parts = name.split(".")
    return ".".join('"' + part.replace('"', '""') + '"' for part in parts)


def _synchronize_table_sequence(conn: sa.Connection, table: str) -> None:
    """Advance the table's id serial up to MAX(id) — never decrease it.

    The forced-id INSERTs above leave the serial behind MAX(id); the
    next ordinary insert would collide with a snapshot id. The sync
    reads the sequence's true NEXT value (last_value + is_called) and
    only calls setval when MAX(id) has passed it."""
    seq_name = conn.execute(
        sa.text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": table}
    ).scalar()
    if seq_name is None:
        raise RuntimeError(
            f"table {table!r} has no serial id column — cannot synchronize"
            " the sequence"
        )
    state = conn.execute(
        sa.text(
            "SELECT last_value, is_called FROM "
            + _quote_qualified_identifier(seq_name)
        )
    ).fetchone()
    next_from_seq = int(state.last_value) + (1 if state.is_called else 0)
    max_id = int(
        conn.execute(
            sa.text("SELECT COALESCE(MAX(id), 0) FROM " + table)
        ).scalar()
    )
    if max_id >= next_from_seq:
        conn.execute(
            sa.text("SELECT setval(:s, :v)"), {"s": seq_name, "v": max_id}
        )
        _journal("sequence-sync", f"{table} -> {max_id}")
    else:
        _journal(
            "sequence-ok", f"{table} (serial next={next_from_seq} > MAX={max_id})"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "plan + conflict verification only: the row writes are rolled"
            " back and the sequences are left untouched (setval/nextval"
            " are not transactional in PostgreSQL)"
        ),
    )
    args = parser.parse_args(argv)

    engine = sa.create_engine(args.database_url, pool_pre_ping=True)
    with engine.connect() as conn:
        row = conn.execute(sa.text("SELECT version_num FROM alembic_version")).fetchone()
        current = row[0] if row else None
        if current != _SCHEMA_VERSION:
            print(
                f"{_MIGRATION_NAME}: schema version is {current!r}, expected "
                f"{_SCHEMA_VERSION!r} — run the alembic chain to 0065 first",
                file=sys.stderr,
            )
            return 2

        try:
            counts = run_setup_in_connection(conn, plan_only=args.dry_run)
        except RuntimeError as exc:
            conn.rollback()
            print(
                f"{_MIGRATION_NAME}: CONFLICT — {exc}; the group was rolled "
                "back, nothing changed",
                file=sys.stderr,
            )
            return 1
        if args.dry_run:
            conn.rollback()
            print(
                f"{_MIGRATION_NAME}: DRY-RUN — rolled back, no changes; the "
                "id sequences were left untouched (setval/nextval are not "
                "transactional in PostgreSQL)"
            )
        else:
            conn.commit()
        journal_tail = ", ".join(f"{k}={v}" for k, v in counts.items())
        print(f"{_MIGRATION_NAME}: {'dry-run plan' if args.dry_run else 'applied'} — {journal_tail}")
    engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
