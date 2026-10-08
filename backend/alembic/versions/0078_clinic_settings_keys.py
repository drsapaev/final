"""Copy legacy clinic-setting values onto their canonical clinic_* keys.

Site-plan step 1 (docs/plans/2026-09-28-kosmed-public-site-plan.md, handoff
2026-10-06): the setup wizard wrote clinic_* keys while the admin settings
screen historically saved the bare legacy spelling (address, phone, email,
timezone, logo_url) into the same clinic_settings category, so one data point
could live under two rows. This data-only migration makes the canonical
clinic_* rows carry the freshest of the two values:

- canonical row missing or empty -> copy the legacy value onto it;
- both present -> the newer ``updated_at`` wins on the canonical row;
- nothing is ever deleted, so the operation is lossless and re-runnable.

The runtime writer (crud.clinic.update_settings_batch) normalizes legacy keys
on write, so legacy rows stop receiving new values after deploy.

Revision ID: 0078_clinic_settings_keys
Revises: 0077_daily_queue_policy
Create Date: 2026-10-07
"""

from __future__ import annotations

import json
from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "0078_clinic_settings_keys"
down_revision = "0077_daily_queue_policy"
branch_labels = None
depends_on = None

CLINIC_SETTINGS_CATEGORY = "clinic"
CLINIC_SETTING_KEY_ALIASES = {
    "address": "clinic_address",
    "phone": "clinic_phone",
    "email": "clinic_email",
    "timezone": "clinic_timezone",
    "logo_url": "clinic_logo_url",
}


def _fetch_row(conn: sa.Connection, key: str) -> dict | None:
    row = conn.execute(
        sa.text(
            "SELECT id, key, value, updated_at FROM clinic_settings "
            "WHERE category = :category AND key = :key"
        ),
        {"category": CLINIC_SETTINGS_CATEGORY, "key": key},
    ).mappings()
    result = row.fetchone()
    return dict(result) if result else None


def _is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _decode(value):
    """JSON columns may surface dict/list or a JSON-encoded string."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def _newer(legacy_updated_at, canonical_updated_at) -> bool:
    if canonical_updated_at is None:
        return True
    if legacy_updated_at is None:
        return False
    return legacy_updated_at > canonical_updated_at


def upgrade() -> None:
    conn = op.get_bind()
    for legacy_key, canonical_key in CLINIC_SETTING_KEY_ALIASES.items():
        legacy_row = _fetch_row(conn, legacy_key)
        if legacy_row is None or _is_empty(legacy_row["value"]):
            continue

        canonical_row = _fetch_row(conn, canonical_key)
        legacy_updated_at: datetime | None = legacy_row["updated_at"]

        if canonical_row is None:
            conn.execute(
                sa.text(
                    "INSERT INTO clinic_settings "
                    "(key, value, category, description, created_at, updated_at) "
                    "VALUES (:key, CAST(:value AS JSON), :category, :description, "
                    "NOW(), COALESCE(:updated_at, NOW()))"
                ),
                {
                    "key": canonical_key,
                    "value": json.dumps(
                        _decode(legacy_row["value"]), ensure_ascii=False
                    ),
                    "category": CLINIC_SETTINGS_CATEGORY,
                    "description": f"migrated from legacy key '{legacy_key}' (0078)",
                    "updated_at": legacy_updated_at,
                },
            )
        elif _is_empty(canonical_row["value"]) or _newer(
            legacy_updated_at, canonical_row["updated_at"]
        ):
            conn.execute(
                sa.text(
                    "UPDATE clinic_settings SET value = CAST(:value AS JSON), "
                    "updated_at = COALESCE(:updated_at, updated_at) "
                    "WHERE id = :id"
                ),
                {
                    "value": json.dumps(
                        _decode(legacy_row["value"]), ensure_ascii=False
                    ),
                    "updated_at": legacy_updated_at,
                    "id": canonical_row["id"],
                },
            )


def downgrade() -> None:
    # Deliberately a no-op: the migration only adds/updates canonical rows and
    # never touches the legacy rows, so pre-migration state is fully preserved
    # by leaving the copied canonical values in place.
    pass
