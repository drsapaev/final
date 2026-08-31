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
revision = "0049_dental_specialty_canonical"
down_revision = "0048_doctors_user_id_unique"
branch_labels = None
depends_on = None

CANONICAL = "dentistry"
# Family spellings that must NOT remain stored (canonical excluded here).
NON_CANONICAL_DENTAL = ("dental", "stomatology", "dentist")
QUEUE_PROFILE_TABLE = "queue_profiles"
QUEUE_PROFILE_DENTAL_KEY = "stomatology"

# ClinicSettings (category 'queue') stores per-specialty limits as SEPARATE
# rows keyed ``start_number_<specialty>`` / ``max_per_day_<specialty>``
# (written by crud update_queue_settings, read by get_queue_settings —
# Codex round-1 P1). A stored ``start_number_stomatology`` row would stop
# matching canonical ``dentistry`` doctors after the doctors rewrite, so
# those rows are renamed to the canonical suffix; if several family
# spellings coexisted for one prefix, the values are merged into ONE row
# (most permissive: max for both limit kinds) and the duplicate spelling
# rows are removed — operational settings only, no clinical data touched.
SETTINGS_TABLE = "clinic_settings"
SETTINGS_PREFIXES = ("start_number_", "max_per_day_")


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
    """Rename ``<prefix><dental-spelling>`` settings rows to the canonical
    suffix; merge duplicates (most permissive) and drop the extra rows."""
    settings_table = sa.table(
        SETTINGS_TABLE,
        sa.column("id", sa.Integer),
        sa.column("key", sa.String),
        sa.column("value", sa.Integer),
    )
    rows = conn.execute(
        sa.select(settings_table.c.id, settings_table.c.key, settings_table.c.value)
    ).fetchall()
    # canonical target value per prefix (max = most permissive); seeded
    # from BOTH existing canonical rows and the dental rows being renamed
    # (otherwise a deployment with only "stomatology"-suffixed rows would
    # lose its configured limits entirely).
    canonical_values: dict[str, int] = {}
    canonical_row_ids: dict[str, int] = {}
    dental_row_ids: list[int] = []
    for row in rows:
        key = row.key or ""
        prefix = next((p for p in SETTINGS_PREFIXES if key.startswith(p)), None)
        if prefix is None:
            continue
        suffix = key[len(prefix):].strip().lower()
        if suffix not in NON_CANONICAL_DENTAL and suffix != CANONICAL:
            continue
        if suffix in NON_CANONICAL_DENTAL:
            dental_row_ids.append(row.id)
        else:
            canonical_row_ids.setdefault(prefix, row.id)
        try:
            existing = int(row.value)
        except (TypeError, ValueError):
            continue
        prev = canonical_values.get(prefix)
        canonical_values[prefix] = existing if prev is None else max(prev, existing)

    removed = 0
    for row_id in dental_row_ids:
        conn.execute(
            settings_table.delete().where(settings_table.c.id == row_id)
        )
        removed += 1

    touched = 0
    for prefix, value in canonical_values.items():
        existing_id = canonical_row_ids.get(prefix)
        if existing_id is not None:
            # canonical row already exists: merge limits into it
            conn.execute(
                settings_table.update()
                .where(settings_table.c.id == existing_id)
                .values(value=value)
            )
        else:
            conn.execute(
                settings_table.insert().values(
                    key=f"{prefix}{CANONICAL}", value=value
                )
            )
        touched += 1
    return removed + touched


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

    # 3. clinic_settings: rename <prefix><dental-spelling> limit rows
    #    (start_number_* / max_per_day_*) to the canonical suffix so
    #    per-doctor enforcement keeps resolving configured limits.
    settings_patched = _patch_settings_keys(conn)
    print(
        "[0049] clinic_settings limit rows renamed/merged to canonical suffix: "
        f"{settings_patched}"
    )

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
