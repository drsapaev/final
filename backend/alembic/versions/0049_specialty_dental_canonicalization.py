"""DATA NORMALIZATION: dental-family specialties → canonical 'dentistry' (D-1).

NEEDS DECISION D-1 (2026-08-31): ``dentistry`` is the single canonical
stored value of the dental specialty family. Historically four spellings
coexisted in ``doctors.specialty`` depending on the creation channel:

- ``dentistry``   — user provisioning / EMR canonical / frontend routing;
- ``dental``      — admin DoctorModal (dropdown fed by departments API);
- ``stomatology`` — queue machinery profile key (legacy rows);
- ``dentist``     — legacy role spelling.

A free string column means every exact-match consumer (registrar selector,
``/mobile/doctors`` filter, queue-profile join) silently misses doctors
whose spelling differs — the audit F7 contradiction class.

WHAT THIS MIGRATION DOES
------------------------
1. Rewrites ``doctors.specialty``: any dental-family spelling
   (case-insensitive, trimmed) becomes ``dentistry``. Non-dental values
   (``cardiology``, ``dermatology``, ``general``, ...) are untouched.
2. Appends ``dentistry`` to the stomatology QueueProfile ``queue_tags``
   (JSON list) so the QR/queue-profile join sees canonical rows even when
   a deployment's profile row predates the code-level tag update.

PRECONDITION (informational inventory)
--------------------------------------
The upgrade prints a per-spelling count of the rows it is about to
rewrite. Unlike 0048 no hard stop is required: the rewrite is
deterministic and lossless for the family (any spelling → dentistry),
and the application read layer (``core/specialties.specialty_variants``)
accepts both old and new spellings either way.

POSTCONDITION
-------------
Zero rows with a non-canonical dental spelling remain, and the
stomatology queue profile tags contain ``dentistry``.

ROLLBACK
--------
Downgrade is a deliberate NO-OP: the original spelling per row is not
recoverable after normalization (that is the point of canonicalization)
and reverting would immediately re-introduce the exact-match divergence.
The application layer keeps accepting every family spelling, so a
downgraded schema still works with canonical data.
"""
from __future__ import annotations

import json
import sqlalchemy as sa
from alembic import op

# Revision identifiers — chained after 0048_doctors_user_id_unique.
revision = "0049_specialty_dental_canonicalization"
down_revision = "0048_doctors_user_id_unique"
branch_labels = None
depends_on = None

CANONICAL = "dentistry"
# Family spellings that must NOT remain stored (canonical excluded here).
NON_CANONICAL_DENTAL = ("dental", "stomatology", "dentist")
QUEUE_PROFILE_TABLE = "queue_profiles"
QUEUE_PROFILE_DENTAL_KEY = "stomatology"

# ClinicSettings rows whose JSON value maps specialty -> number. Their dict
# keys are raw Doctor.specialty spellings, so a stored "stomatology" key
# would silently stop matching canonical "dentistry" doctors after the
# rewrite; rename those keys too (limits enforcement reads them per doctor).
SETTINGS_KEY_COLUMN = "key"
SETTINGS_SPECIALTY_KEYS = ("max_per_day", "start_numbers")


def _inventory(conn: sa.Connection) -> list[tuple[str, int]]:
    rows = conn.execute(
        sa.text(
            "SELECT lower(trim(specialty)) AS spelling, COUNT(*) AS n "
            "FROM doctors "
            "WHERE specialty IS NOT NULL "
            "AND lower(trim(specialty)) IN ('dental', 'stomatology', 'dentist', 'dentistry') "
            "GROUP BY 1 ORDER BY 1"
        )
    ).fetchall()
    return [(r[0], int(r[1])) for r in rows]


def _patch_queue_profile_tags(conn: sa.Connection) -> int:
    """Append 'dentistry' to the stomatology profile tags; return patched count."""
    profiles_table = sa.table(
        QUEUE_PROFILE_TABLE,
        sa.column("id", sa.Integer),
        sa.column("key", sa.String),
        sa.column("queue_tags", sa.JSON),
    )
    rows = conn.execute(
        sa.select(profiles_table.c.id, profiles_table.c.queue_tags).where(
            profiles_table.c.key == QUEUE_PROFILE_DENTAL_KEY
        )
    ).fetchall()
    patched = 0
    for row in rows:
        tags = row.queue_tags
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (TypeError, ValueError):
                tags = None
        if not isinstance(tags, list):
            tags = []
        if CANONICAL in tags:
            continue
        tags.append(CANONICAL)
        conn.execute(
            profiles_table.update()
            .where(profiles_table.c.id == row.id)
            .values(queue_tags=tags)
        )
        patched += 1
    return patched


def _patch_settings_keys(conn: sa.Connection) -> int:
    """Rename non-canonical dental keys inside specialty-keyed settings JSON."""
    settings_table = sa.table(
        "clinic_settings",
        sa.column("id", sa.Integer),
        sa.column(SETTINGS_KEY_COLUMN, sa.String),
        sa.column("value", sa.JSON),
    )
    rows = conn.execute(
        sa.select(settings_table.c.id, settings_table.c.value).where(
            settings_table.c.key.in_(SETTINGS_SPECIALTY_KEYS)
        )
    ).fetchall()
    patched = 0
    for row in rows:
        value = row.value
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (TypeError, ValueError):
                value = None
        if not isinstance(value, dict):
            continue
        changed = False
        for spelling in NON_CANONICAL_DENTAL:
            # rename any-case keys: "Stomatology" -> "dentistry" etc.
            # First spelling wins if several coexisted (setdefault keeps
            # an already-written canonical value).
            for actual_key in [k for k in value if str(k).strip().lower() == spelling]:
                old = value.pop(actual_key)
                value.setdefault(CANONICAL, old)
                changed = True
        if changed:
            conn.execute(
                settings_table.update()
                .where(settings_table.c.id == row.id)
                .values(value=value)
            )
            patched += 1
    return patched


def upgrade() -> None:
    conn = op.get_bind()

    inventory = _inventory(conn)
    print(
        "[0049] dental-family specialty inventory (spelling -> rows): "
        + (", ".join(f"{s}={n}" for s, n in inventory) or "no rows")
    )

    # 1. doctors: rewrite non-canonical dental spellings.
    conn.execute(
        sa.text(
            "UPDATE doctors SET specialty = :canonical "
            "WHERE specialty IS NOT NULL "
            "AND lower(trim(specialty)) IN ('dental', 'stomatology', 'dentist')"
        ),
        {"canonical": CANONICAL},
    )

    # 2. queue_profiles: make the stomatology profile see canonical rows.
    patched = _patch_queue_profile_tags(conn)
    print(f"[0049] stomatology queue profiles patched with '{CANONICAL}' tag: {patched}")

    # 3. clinic_settings: rename dental-family dict keys in specialty-keyed
    #    limit settings so per-doctor enforcement keeps resolving.
    settings_patched = _patch_settings_keys(conn)
    print(f"[0049] clinic_settings rows with dental keys renamed: {settings_patched}")

    # 4. Postcondition: no non-canonical dental spellings remain.
    leftovers = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM doctors "
            "WHERE specialty IS NOT NULL "
            "AND lower(trim(specialty)) IN ('dental', 'stomatology', 'dentist')"
        )
    ).scalar_one()
    if leftovers:
        raise RuntimeError(
            f"[0049] postcondition failed: {leftovers} doctor rows still carry a "
            f"non-canonical dental specialty (expected 0 after rewrite)"
        )


def downgrade() -> None:
    # Deliberate no-op: normalization is one-way (see module docstring).
    print(
        "[0049] downgrade is a no-op: doctors.specialty stays canonical "
        "('dentistry'); the application read layer accepts every "
        "dental-family spelling via core/specialties.specialty_variants."
    )
