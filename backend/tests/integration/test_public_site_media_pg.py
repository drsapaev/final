"""PostgreSQL acceptance tests for public-site media metadata.

The module creates one uniquely named database on a verified local PostgreSQL
server, applies the checked-in migrations, and drops only that database.
Remote hosts and clinic/staging database names are never used as test targets.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.base_class import Base  # noqa: E402
from app.models import Doctor, PublicSiteMedia  # noqa: E402,F401

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_INSERT_MEDIA_SQL = """
INSERT INTO public.public_site_media (
    asset_kind, doctor_id, storage_key, mime_type, byte_size,
    sha256, is_published, published_at
) VALUES (
    :asset_kind, :doctor_id, :storage_key, :mime_type, :byte_size,
    :sha256, :is_published, :published_at
) RETURNING id
"""


def _candidate_admin_dsns() -> list[str]:
    candidates: list[str] = []
    for variable in ("PUBLIC_SITE_MEDIA_PG_ADMIN_URL", "LAB_PG_ADMIN_DSN"):
        value = os.getenv(variable, "").strip()
        if value:
            candidates.append(value)

    local_password = os.getenv("LOCAL_PG_SUPERUSER_PASSWORD", "").strip()
    if local_password:
        from sqlalchemy.engine import URL

        candidates.append(
            URL.create(
                "postgresql",
                username="postgres",
                password=local_password,
                host="localhost",
                port=5432,
                database="postgres",
            ).render_as_string(hide_password=False)
        )

    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        try:
            parsed = make_url(database_url)
        except Exception:  # noqa: BLE001 - invalid local test configuration
            parsed = None
        if parsed is not None and parsed.host in _LOCAL_HOSTS:
            candidates.append(
                parsed.set(drivername="postgresql").render_as_string(
                    hide_password=False
                )
            )
    return candidates


def _local_admin_dsn() -> str:
    last_error: Exception | None = None
    for candidate in _candidate_admin_dsns():
        try:
            parsed = make_url(candidate)
            if parsed.host not in _LOCAL_HOSTS:
                continue
            dsn = parsed.set(drivername="postgresql").render_as_string(
                hide_password=False
            )
            with psycopg.connect(dsn, connect_timeout=5, autocommit=True) as conn:
                conn.execute("SELECT 1")
            return dsn
        except Exception as exc:  # noqa: BLE001 - try the next local candidate
            last_error = exc

    detail = f" ({type(last_error).__name__})" if last_error else ""
    pytest.skip(
        "requires a reachable loopback PostgreSQL server with CREATEDB" + detail
    )


def _scratch_sa_url(admin_dsn: str, database_name: str) -> str:
    return (
        make_url(admin_dsn)
        .set(drivername="postgresql+psycopg", database=database_name)
        .render_as_string(hide_password=False)
    )


@pytest.fixture(scope="module")
def migrated_media_db_url():
    admin_dsn = _local_admin_dsn()
    database_name = f"public_site_media_{uuid.uuid4().hex[:10]}"
    created = False
    try:
        try:
            with psycopg.connect(admin_dsn, connect_timeout=5, autocommit=True) as conn:
                conn.execute(
                    sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
                )
                created = True
        except Exception as exc:  # noqa: BLE001 - no CREATEDB or server unavailable
            pytest.skip(
                "cannot create a disposable local PostgreSQL database "
                f"({type(exc).__name__})"
            )

        sa_url = _scratch_sa_url(admin_dsn, database_name)
        env = dict(os.environ, DATABASE_URL=sa_url, TESTING="1")
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=str(BACKEND_DIR),
            env=env,
            timeout=240,
        )
        diagnostics = (result.stdout + result.stderr).replace(
            sa_url, "<disposable PostgreSQL database>"
        )
        assert result.returncode == 0, (
            "Alembic upgrade failed on the disposable database:\n" + diagnostics[-2500:]
        )
        yield sa_url
    finally:
        if created:
            with psycopg.connect(admin_dsn, connect_timeout=5, autocommit=True) as conn:
                conn.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                        sql.Identifier(database_name)
                    )
                )


@pytest.fixture(scope="module")
def media_engine(migrated_media_db_url):
    engine = create_engine(migrated_media_db_url, future=True, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="module")
def doctor_ids(media_engine) -> tuple[int, int]:
    with Session(media_engine) as session:
        doctors = [
            Doctor(specialty="public-site-media-test"),
            Doctor(specialty="public-site-media-test"),
        ]
        session.add_all(doctors)
        session.commit()
        return doctors[0].id, doctors[1].id


def _storage_key() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex


def _insert_media(connection, **overrides) -> int:
    values = {
        "asset_kind": "clinic_logo",
        "doctor_id": None,
        "storage_key": _storage_key(),
        "mime_type": "image/png",
        "byte_size": 256,
        "sha256": "a" * 64,
        "is_published": False,
        "published_at": None,
    }
    values.update(overrides)
    result = connection.execute(
        text(_INSERT_MEDIA_SQL),
        values,
    )
    return int(result.scalar_one())


def _assert_constraint_violation(
    connection, expected_constraint: str, **overrides
) -> None:
    with pytest.raises(IntegrityError) as error:
        with connection.begin_nested():
            _insert_media(connection, **overrides)
    diagnostic = getattr(error.value.orig, "diag", None)
    actual_constraint = getattr(diagnostic, "constraint_name", None)
    assert actual_constraint == expected_constraint


def _publish(connection, media_id: int) -> None:
    connection.execute(
        text(
            "UPDATE public.public_site_media "
            "SET is_published = true, published_at = :published_at WHERE id = :id"
        ),
        {"id": media_id, "published_at": datetime.now(UTC)},
    )


def _unpublish(connection, media_id: int) -> None:
    connection.execute(
        text(
            "UPDATE public.public_site_media "
            "SET is_published = false, published_at = NULL WHERE id = :id"
        ),
        {"id": media_id},
    )


def test_public_site_media_is_registered_in_model_metadata() -> None:
    assert PublicSiteMedia.__table__ is Base.metadata.tables["public_site_media"]


@pytest.mark.integration
def test_alembic_autogenerate_does_not_propose_media_table_changes(
    media_engine,
) -> None:
    with media_engine.connect() as connection:
        diffs = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    media_diffs = [
        diff
        for diff in diffs
        if any(
            item == "public_site_media"
            or getattr(item, "name", None) == "public_site_media"
            or getattr(getattr(item, "table", None), "name", None)
            == "public_site_media"
            for item in diff
        )
    ]
    assert not media_diffs, repr(media_diffs)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"asset_kind": "service_image"}, "ck_public_site_media_asset_kind"),
        (
            {"storage_key": "not-a-64-character-hex-key"},
            "ck_public_site_media_storage_key_format",
        ),
        ({"mime_type": "image/svg+xml"}, "ck_public_site_media_mime_type"),
        ({"byte_size": 0}, "ck_public_site_media_byte_size_positive"),
        ({"sha256": "not-a-digest"}, "ck_public_site_media_sha256_format"),
        (
            {"is_published": True, "published_at": None},
            "ck_public_site_media_publication_state",
        ),
        (
            {"is_published": False, "published_at": datetime.now(UTC)},
            "ck_public_site_media_publication_state",
        ),
    ],
)
def test_media_check_constraints_reject_invalid_metadata(
    media_engine, overrides, constraint
) -> None:
    with media_engine.begin() as connection:
        _assert_constraint_violation(connection, constraint, **overrides)


@pytest.mark.integration
def test_media_owner_constraint_requires_doctor_only_for_portraits(
    media_engine, doctor_ids
) -> None:
    with media_engine.begin() as connection:
        _assert_constraint_violation(
            connection,
            "ck_public_site_media_owner",
            asset_kind="clinic_logo",
            doctor_id=doctor_ids[0],
        )
        _assert_constraint_violation(
            connection,
            "ck_public_site_media_owner",
            asset_kind="doctor_portrait",
            doctor_id=None,
        )


@pytest.mark.integration
def test_published_logo_index_allows_one_published_logo_and_replacement(
    media_engine,
) -> None:
    with media_engine.begin() as connection:
        first = _insert_media(connection)
        second = _insert_media(connection)
        _publish(connection, first)

        with pytest.raises(IntegrityError) as error:
            with connection.begin_nested():
                _publish(connection, second)

        diagnostic = getattr(error.value.orig, "diag", None)
        assert (
            getattr(diagnostic, "constraint_name", None)
            == "uq_public_site_media_published_clinic_logo"
        )

        _unpublish(connection, first)
        _publish(connection, second)
        state = connection.execute(
            text(
                "SELECT is_published, published_at "
                "FROM public.public_site_media WHERE id = :id"
            ),
            {"id": second},
        ).one()
        assert state.is_published is True
        assert state.published_at is not None


@pytest.mark.integration
def test_published_portrait_index_is_per_doctor_and_can_be_replaced(
    media_engine, doctor_ids
) -> None:
    first_doctor, second_doctor = doctor_ids
    with media_engine.begin() as connection:
        first = _insert_media(
            connection, asset_kind="doctor_portrait", doctor_id=first_doctor
        )
        replacement = _insert_media(
            connection, asset_kind="doctor_portrait", doctor_id=first_doctor
        )
        other_doctor = _insert_media(
            connection, asset_kind="doctor_portrait", doctor_id=second_doctor
        )
        _publish(connection, first)
        _publish(connection, other_doctor)

        with pytest.raises(IntegrityError) as error:
            with connection.begin_nested():
                _publish(connection, replacement)

        diagnostic = getattr(error.value.orig, "diag", None)
        assert (
            getattr(diagnostic, "constraint_name", None)
            == "uq_public_site_media_published_doctor_portrait"
        )

        _unpublish(connection, first)
        _publish(connection, replacement)
