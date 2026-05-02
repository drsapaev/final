from __future__ import annotations

import argparse
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, text

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_SQLITE_PATH = _BACKEND_DIR / "clinic.db"


@dataclass(frozen=True)
class LegacyUserRow:
    id: int
    username: str
    email: str | None
    full_name: str | None
    hashed_password: str
    role: str
    is_active: bool
    is_superuser: bool
    must_change_password: bool
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class MigrationSummary:
    source_count: int
    inserted_count: int
    updated_count: int
    preserved_id_count: int
    id_mismatch_updates: int


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                try:
                    parsed = datetime.strptime(normalized, fmt)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError(f"Unsupported datetime value: {value!r}") from None
    else:
        raise TypeError(f"Unsupported datetime type: {type(value)!r}")

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_legacy_users(source_sqlite_path: Path) -> list[LegacyUserRow]:
    logger.info(
        "[FIX:USER-MIGRATION] Loading legacy users from %s",
        source_sqlite_path,
    )
    connection = sqlite3.connect(source_sqlite_path)
    connection.row_factory = sqlite3.Row
    try:
        cursor = connection.execute(
            """
            SELECT
                id,
                username,
                email,
                full_name,
                hashed_password,
                role,
                is_active,
                is_superuser,
                must_change_password,
                created_at,
                updated_at
            FROM users
            ORDER BY id
            """
        )

        users: list[LegacyUserRow] = []
        for row in cursor.fetchall():
            users.append(
                LegacyUserRow(
                    id=int(row["id"]),
                    username=row["username"],
                    email=row["email"],
                    full_name=row["full_name"],
                    hashed_password=row["hashed_password"],
                    role=row["role"] or "Admin",
                    is_active=_parse_bool(row["is_active"]),
                    is_superuser=_parse_bool(row["is_superuser"]),
                    must_change_password=_parse_bool(row["must_change_password"]),
                    created_at=_parse_datetime(row["created_at"]),
                    updated_at=_parse_datetime(row["updated_at"]),
                )
            )

        logger.info(
            "[FIX:USER-MIGRATION] Loaded %d legacy users from SQLite",
            len(users),
        )
        return users
    finally:
        connection.close()


def _load_target_maps(connection) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[int, dict[str, Any]]]:
    rows = connection.execute(
        text(
            """
            SELECT id, username, email
            FROM users
            """
        )
    ).mappings().all()

    by_username: dict[str, dict[str, Any]] = {}
    by_email: dict[str, dict[str, Any]] = {}
    by_id: dict[int, dict[str, Any]] = {}
    for row in rows:
        row_dict = dict(row)
        by_id[int(row_dict["id"])] = row_dict
        by_username[str(row_dict["username"]).lower()] = row_dict
        email = row_dict.get("email")
        if email:
            by_email[str(email).lower()] = row_dict
    return by_username, by_email, by_id


def migrate_users(*, source_sqlite_path: Path, target_engine: Engine, dry_run: bool = False) -> MigrationSummary:
    legacy_users = load_legacy_users(source_sqlite_path)
    inserted_count = 0
    updated_count = 0
    preserved_id_count = 0
    id_mismatch_updates = 0

    with target_engine.begin() as connection:
        by_username, by_email, by_id = _load_target_maps(connection)

        for user in legacy_users:
            username_key = user.username.lower()
            email_key = user.email.lower() if user.email else None

            existing_by_username = by_username.get(username_key)
            existing_by_email = by_email.get(email_key) if email_key else None

            if (
                existing_by_username
                and existing_by_email
                and existing_by_username["id"] != existing_by_email["id"]
            ):
                raise RuntimeError(
                    "[FIX:USER-MIGRATION] Username/email conflict detected for "
                    f"{user.username} / {user.email}"
                )

            existing = existing_by_username or existing_by_email
            payload = {
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "hashed_password": user.hashed_password,
                "role": user.role,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
                "must_change_password": user.must_change_password,
                "device_token": None,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
            }

            if existing:
                target_id = int(existing["id"])
                if target_id == user.id:
                    preserved_id_count += 1
                else:
                    id_mismatch_updates += 1
                    logger.warning(
                        "[FIX:USER-MIGRATION] Updating existing user %s with target id=%s instead of legacy id=%s",
                        user.username,
                        target_id,
                        user.id,
                    )

                logger.info(
                    "[FIX:USER-MIGRATION] Updating target user id=%s username=%s",
                    target_id,
                    user.username,
                )
                if not dry_run:
                    connection.execute(
                        text(
                            """
                            UPDATE users
                            SET username = :username,
                                email = :email,
                                full_name = :full_name,
                                hashed_password = :hashed_password,
                                role = :role,
                                is_active = :is_active,
                                is_superuser = :is_superuser,
                                must_change_password = :must_change_password,
                                device_token = :device_token,
                                created_at = :created_at,
                                updated_at = :updated_at
                            WHERE id = :target_id
                            """
                        ),
                        payload | {"target_id": target_id},
                    )
                updated_count += 1
                by_id[target_id] = {"id": target_id, "username": user.username, "email": user.email}
                by_username[username_key] = {"id": target_id, "username": user.username, "email": user.email}
                if email_key:
                    by_email[email_key] = {"id": target_id, "username": user.username, "email": user.email}
                continue

            conflict = by_id.get(user.id)
            if conflict:
                raise RuntimeError(
                    "[FIX:USER-MIGRATION] Cannot preserve legacy id "
                    f"{user.id}; target already uses it for username={conflict['username']}"
                )

            logger.info(
                "[FIX:USER-MIGRATION] Inserting user id=%s username=%s",
                user.id,
                user.username,
            )
            if not dry_run:
                connection.execute(
                    text(
                        """
                        INSERT INTO users (
                            id,
                            username,
                            full_name,
                            email,
                            hashed_password,
                            role,
                            is_active,
                            is_superuser,
                            must_change_password,
                            device_token,
                            created_at,
                            updated_at
                        ) VALUES (
                            :id,
                            :username,
                            :full_name,
                            :email,
                            :hashed_password,
                            :role,
                            :is_active,
                            :is_superuser,
                            :must_change_password,
                            :device_token,
                            :created_at,
                            :updated_at
                        )
                        """
                    ),
                    {"id": user.id} | payload,
                )
            inserted_count += 1
            preserved_id_count += 1
            row_dict = {"id": user.id, "username": user.username, "email": user.email}
            by_id[user.id] = row_dict
            by_username[username_key] = row_dict
            if email_key:
                by_email[email_key] = row_dict

        if not dry_run and target_engine.dialect.name == "postgresql":
            connection.execute(
                text(
                    """
                    SELECT setval(
                        pg_get_serial_sequence('users', 'id'),
                        COALESCE((SELECT MAX(id) FROM users), 1),
                        true
                    )
                    """
                )
            )
            logger.info("[FIX:USER-MIGRATION] Synced PostgreSQL users.id sequence")

    summary = MigrationSummary(
        source_count=len(legacy_users),
        inserted_count=inserted_count,
        updated_count=updated_count,
        preserved_id_count=preserved_id_count,
        id_mismatch_updates=id_mismatch_updates,
    )
    logger.info("[FIX:USER-MIGRATION] Migration summary: %s", summary)
    return summary


def _resolve_target_url(explicit_target_url: str | None) -> str:
    if explicit_target_url:
        return explicit_target_url

    from app.core.config import get_settings

    return get_settings().DATABASE_URL


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate users from legacy SQLite clinic.db into PostgreSQL users table.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE_SQLITE_PATH,
        help=f"Path to legacy SQLite DB (default: {DEFAULT_SOURCE_SQLITE_PATH})",
    )
    parser.add_argument(
        "--target-url",
        default=None,
        help="Target SQLAlchemy database URL. Defaults to backend/app config DATABASE_URL.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and log planned changes without modifying the target DB.",
    )
    return parser


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    parser = _build_parser()
    args = parser.parse_args()
    source_path = args.source.resolve()

    if not source_path.exists():
        raise FileNotFoundError(
            f"[FIX:USER-MIGRATION] Legacy SQLite DB not found: {source_path}"
        )

    target_url = _resolve_target_url(args.target_url)
    logger.info(
        "[FIX:USER-MIGRATION] Starting migration source=%s target=%s dry_run=%s",
        source_path,
        target_url,
        args.dry_run,
    )
    target_engine = create_engine(target_url)
    summary = migrate_users(
        source_sqlite_path=source_path,
        target_engine=target_engine,
        dry_run=args.dry_run,
    )

    logger.info(
        "[FIX:USER-MIGRATION] Completed: source=%d inserted=%d updated=%d preserved_ids=%d mismatched_ids=%d",
        summary.source_count,
        summary.inserted_count,
        summary.updated_count,
        summary.preserved_id_count,
        summary.id_mismatch_updates,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
