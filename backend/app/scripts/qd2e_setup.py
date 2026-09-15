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
_SPECIALTIES: tuple[tuple[str, str], ...] = (
    ("cardiology", "Кардиология"),
    ("dermatology", "Дерматология"),
    ("dentistry", "Стоматология"),
    ("ultrason", "УЗИ"),
    ("neurology", "Неврология"),
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


def run_setup_in_connection(conn: sa.Connection) -> dict[str, int]:
    """Provision everything inside the CALLER's transaction. Raises
    RuntimeError on any identity conflict (the caller rolls back)."""
    counts: dict[str, int] = {
        "specialties": 0,
        "users": 0,
        "doctors": 0,
        "registry": 0,
        "services": 0,
    }

    # ---------- specialties (natural key: code) ----------
    for code, title_ru in _SPECIALTIES:
        row = conn.execute(
            sa.text("SELECT id FROM medical_specialties WHERE code = :c"),
            {"c": code},
        ).fetchone()
        if row is None:
            _journal("create", f"medical_specialty {code!r}")
            counts["specialties"] += 1
            conn.execute(
                sa.text(
                    "INSERT INTO medical_specialties (code, title_ru, active)"
                    " VALUES (:c, :t, true)"
                ),
                {"c": code, "t": title_ru},
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
            _journal("create", f"user id={user_id} {username!r} ({role})")
            counts["users"] += 1
            conn.execute(
                sa.text(
                    "INSERT INTO users (id, username, hashed_password, role,"
                    " is_active, is_superuser, must_change_password)"
                    " VALUES (:i, :u, :p, :r, true, false, false)"
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
            sa.text("SELECT id, user_id, specialty FROM doctors WHERE id = :i"),
            {"i": doctor_id},
        ).fetchone()
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
                "create",
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
        row = conn.execute(
            sa.text("SELECT id FROM queue_resources WHERE queue_tag = :t"),
            {"t": tag},
        ).fetchone()
        if row is None:
            _journal("create", f"queue_resource {code!r} ({tag!r})")
            counts["registry"] += 1
            conn.execute(
                sa.text(
                    "INSERT INTO queue_resources (code, queue_tag,"
                    " display_name, active, start_number_online,"
                    " max_online_per_day) VALUES (:c, :t, :d, true, 1, 15)"
                ),
                {"c": code, "t": tag, "d": display},
            )
        else:
            _journal("no-op", f"queue_resource {tag!r} exists")

    # ---------- services (snapshot id + code identity, PRE-STATES only) --
    for sid, code, name, tag, dept, requires, is_consultation in _SERVICES:
        # code-ownership check (review P1, 2026-09-15): a populated test
        # database may carry a mapped code under a DIFFERENT id — inserting
        # a second logical service would pollute the environment and make
        # migration 0066 abort on the undecided original; report the
        # conflict instead.
        carrier = conn.execute(
            sa.text("SELECT id FROM services WHERE code = :c"), {"c": code}
        ).fetchone()
        if carrier is not None and carrier.id != sid:
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
                "create",
                f"service id={sid} {code!r} tag={tag!r} "
                f"requires_doctor={requires}",
            )
            counts["services"] += 1
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
    for table in ("users", "doctors", "services"):
        conn.execute(
            sa.text(
                "SELECT setval(pg_get_serial_sequence(:t, 'id'),"
                " (SELECT COALESCE(MAX(id), 1) FROM " + table + "))"
            ),
            {"t": table},
        )
        _journal("sequence-sync", table)

    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="apply inside a transaction and roll it back (verify only)",
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
            counts = run_setup_in_connection(conn)
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
            print(f"{_MIGRATION_NAME}: DRY-RUN — rolled back, no changes")
        else:
            conn.commit()
        journal_tail = ", ".join(f"{k}={v}" for k, v in counts.items())
        print(f"{_MIGRATION_NAME}: {'dry-run plan' if args.dry_run else 'applied'} — {journal_tail}")
    engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
