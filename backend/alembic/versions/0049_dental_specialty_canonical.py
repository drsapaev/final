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
   (case-insensitive, trimmed) becomes the EXACT canonical value
   ``dentistry``. This includes case/padding variants of the canonical
   itself (``Dentistry``, ``DENTISTRY``, `` dentistry ``): stored
   spellings are matched case-insensitively by ``IN`` filters on the
   read side, so only the exact lowercase form survives (Codex round-3
   P1). Non-dental values (``cardiology``, ``dermatology``,
   ``general``, ...) are untouched.
2. Appends ``dentistry`` to EVERY dental-family QueueProfile's
   ``queue_tags`` (JSON list) so the QR/queue-profile join sees canonical
   rows even when a deployment's profile row predates the code-level tag
   update. Profiles under any family key (``dental`` from the departments
   integration writer, ``stomatology`` legacy seed, ...) are covered —
   selection is by family key OR family tag (Codex round-5 P1).

PRECONDITION (informational inventory)
--------------------------------------
The upgrade prints a per-spelling count of the rows it is about to
rewrite. Unlike 0048 no hard stop is required: the rewrite is
deterministic and lossless for the family (any spelling → dentistry),
and the application read layer (``core/specialties.specialty_variants``)
accepts both old and new spellings either way.

POSTCONDITION
-------------
Zero family rows remain whose stored value is not EXACTLY
``dentistry`` (any dental spelling matched case-insensitively but
stored differently — including ``Dentistry`` — fails the migration),
and the stomatology queue profile tags contain ``dentistry``.

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
# Every family spelling — INCLUDING the canonical one — is rewritten to
# the exact canonical value: SQL IN is case-sensitive, so a stored
# ``Dentistry``/`` dentistry `` row would be invisible to the lowercase
# variant queries on the read side (Codex round-3 P1).
FAMILY_SPELLINGS = ("dental", "stomatology", "dentist", "dentistry")
QUEUE_PROFILE_TABLE = "queue_profiles"

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


def _rewrite_family_rows(conn: sa.Connection) -> None:
    """Rewrite every family spelling (case-insensitive, trimmed match) to
    the exact canonical value."""
    conn.execute(
        sa.text(
            "UPDATE doctors SET specialty = :canonical "
            "WHERE specialty IS NOT NULL "
            "AND lower(trim(specialty)) IN ('dental', 'stomatology', 'dentist', 'dentistry')"
        ),
        {"canonical": CANONICAL},
    )


def _assert_exact_canonical_family_rows(conn: sa.Connection) -> None:
    """Postcondition: every dental-family row (matched case-insensitively)
    is stored EXACTLY as ``dentistry`` — no legacy spelling and no
    case/padding variant of the canonical may survive."""
    leftovers = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM doctors "
            "WHERE specialty IS NOT NULL "
            "AND lower(trim(specialty)) IN ('dental', 'stomatology', 'dentist', 'dentistry') "
            "AND specialty <> :canonical"
        ),
        {"canonical": CANONICAL},
    ).scalar_one()
    if leftovers:
        raise RuntimeError(
            f"[0049] postcondition failed: {leftovers} doctor rows carry a "
            f"dental-family specialty that is not exactly '{CANONICAL}' "
            f"(expected 0 after rewrite)"
        )


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
    """Append the canonical spelling to EVERY dental-family profile's tags.

    Codex round-5 P1: dental-family profiles may exist under any family
    key — the departments integration writer creates ``key='dental'``
    with ``queue_tags=['dental']`` — and patching only the exact
    ``stomatology`` key would leave those profiles blind to canonical
    ``dentistry`` doctors after the rewrite (the QR clinic-wide
    specialist matcher normalizes doctors to the machinery key and
    matches profiles by key+tags). Selection: the profile key (matched
    case-insensitively) is a family spelling OR the stored tags already
    contain one. Only the canonical value is appended, once.
    """
    profiles_table = sa.table(
        QUEUE_PROFILE_TABLE,
        sa.column("id", sa.Integer),
        sa.column("key", sa.String),
        sa.column("queue_tags", sa.JSON),
    )
    rows = conn.execute(
        sa.select(
            profiles_table.c.id, profiles_table.c.key, profiles_table.c.queue_tags
        )
    ).fetchall()
    patched = 0
    for row in rows:
        key_is_family = (row.key or "").strip().lower() in FAMILY_SPELLINGS
        tags = row.queue_tags
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except (TypeError, ValueError):
                tags = None
        if not isinstance(tags, list):
            tags = []
        tags_are_family = any(
            isinstance(tag, str)
            and (tag or "").strip().lower() in FAMILY_SPELLINGS
            for tag in tags
        )
        if not (key_is_family or tags_are_family):
            continue
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
    suffix and merge duplicates (most permissive) into one row.

    Rename is implemented as an UPDATE of the surviving row (not
    delete+insert) so ``category='queue'`` and the audit columns survive —
    ``get_queue_settings`` loads rows BY CATEGORY, and a category-less
    replacement row would be invisible (Codex round-2 P1). The ``value``
    column is a JSON column in production: the table construct therefore
    declares ``sa.JSON`` so SQLAlchemy serializes the merged integer on
    bind (Codex round-2 P1).

    The surviving canonical row is stored with the EXACT canonical key
    (``<prefix>dentistry``): suffix matching is case-insensitive, so a
    case-variant row (``start_number_Dentistry``) is normalized the same
    way as the doctors rows — only the exact lowercase key survives
    (Codex round-3 P1).
    """
    settings_table = sa.table(
        SETTINGS_TABLE,
        sa.column("id", sa.Integer),
        sa.column("key", sa.String),
        sa.column("value", sa.JSON),
    )
    rows = conn.execute(
        sa.select(settings_table.c.id, settings_table.c.key, settings_table.c.value)
    ).fetchall()
    # merged value per prefix (max = most permissive); seeded from BOTH
    # existing canonical rows and the dental rows being renamed (otherwise
    # a deployment with only "stomatology"-suffixed rows would lose its
    # configured limits entirely).
    canonical_values: dict[str, int] = {}
    # canonical-suffix row ids per prefix (case-insensitive suffix match).
    canonical_row_ids_by_prefix: dict[str, list[int]] = {}
    # ids of canonical-suffix rows whose key is EXACTLY <prefix>dentistry.
    exact_canonical_row_ids: dict[str, list[int]] = {}
    dental_row_ids_by_prefix: dict[str, list[int]] = {}
    for row in rows:
        key = row.key or ""
        prefix = next((p for p in SETTINGS_PREFIXES if key.startswith(p)), None)
        if prefix is None:
            continue
        suffix = key[len(prefix):].strip().lower()
        if suffix not in NON_CANONICAL_DENTAL and suffix != CANONICAL:
            continue
        if suffix in NON_CANONICAL_DENTAL:
            dental_row_ids_by_prefix.setdefault(prefix, []).append(row.id)
        else:
            canonical_row_ids_by_prefix.setdefault(prefix, []).append(row.id)
            if key == f"{prefix}{CANONICAL}":
                exact_canonical_row_ids.setdefault(prefix, []).append(row.id)
        try:
            existing = int(row.value)
        except (TypeError, ValueError):
            continue
        prev = canonical_values.get(prefix)
        canonical_values[prefix] = existing if prev is None else max(prev, existing)

    touched = 0
    for prefix, value in canonical_values.items():
        canonical_ids = canonical_row_ids_by_prefix.get(prefix, [])
        dental_ids = dental_row_ids_by_prefix.get(prefix, [])
        # survivor: prefer the row whose key is EXACTLY <prefix>dentistry
        # so a case-variant duplicate cannot collide during key
        # normalization; else the oldest canonical-suffix row.
        if exact_canonical_row_ids.get(prefix):
            survivor_id = min(exact_canonical_row_ids[prefix])
        elif canonical_ids:
            survivor_id = min(canonical_ids)
        else:
            survivor_id = None
        if survivor_id is not None:
            # canonical row already exists: merge limits into it under the
            # EXACT canonical key, drop every duplicate-spelling row
            # (legacy spellings AND case-variant canonical keys).
            for row_id in dental_ids + [
                rid for rid in canonical_ids if rid != survivor_id
            ]:
                conn.execute(
                    settings_table.delete().where(settings_table.c.id == row_id)
                )
            conn.execute(
                settings_table.update()
                .where(settings_table.c.id == survivor_id)
                .values(key=f"{prefix}{CANONICAL}", value=value)
            )
        elif dental_ids:
            # no canonical row: RENAME the oldest dental row in place
            # (key + merged value) — category/audit columns preserved —
            # and remove the remaining duplicate-spelling rows.
            keep_id = min(dental_ids)
            for row_id in dental_ids:
                if row_id != keep_id:
                    conn.execute(
                        settings_table.delete().where(settings_table.c.id == row_id)
                    )
            conn.execute(
                settings_table.update()
                .where(settings_table.c.id == keep_id)
                .values(key=f"{prefix}{CANONICAL}", value=value)
            )
        else:
            continue
        touched += 1
    return touched


def upgrade() -> None:
    conn = op.get_bind()

    inventory = _inventory(conn)
    print(
        "[0049] dental-family specialty inventory (spelling -> rows): "
        + (", ".join(f"{s}={n}" for s, n in inventory) or "no rows")
    )

    # 1. doctors: rewrite EVERY family spelling (case-insensitively
    #    matched) to the exact canonical value.
    _rewrite_family_rows(conn)

    # 2. queue_profiles: make every dental-family profile see canonical
    #    rows.
    patched = _patch_queue_profile_tags(conn)
    print(
        f"[0049] dental-family queue profiles patched with '{CANONICAL}' tag: "
        f"{patched}"
    )

    # 3. clinic_settings: rename <prefix><dental-spelling> limit rows
    #    (start_number_* / max_per_day_*) to the canonical suffix so
    #    per-doctor enforcement keeps resolving configured limits.
    settings_patched = _patch_settings_keys(conn)
    print(
        "[0049] clinic_settings limit rows renamed/merged to canonical suffix: "
        f"{settings_patched}"
    )

    # 4. Postcondition: no family row whose stored value is not EXACTLY
    #    the canonical spelling remains (catches case/padding variants
    #    the rewrite must have normalized).
    _assert_exact_canonical_family_rows(conn)


def downgrade() -> None:
    # Deliberate no-op: normalization is one-way (see module docstring).
    print(
        "[0049] downgrade is a no-op: doctors.specialty stays canonical "
        "('dentistry'); the application read layer accepts every "
        "dental-family spelling via core/specialties.specialty_variants."
    )
