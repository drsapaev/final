"""RQ-16.c — unit: model registration, SQLite create_all parity, generator.

E-055 §12: «SQLite/create_all parity проверить отдельно, если модель
участвует в Base.metadata tests» — QueueDirectionPublicAddress регистрируется
в ``app.models`` (autogenerate visibility), so this module proves the model
DDL itself on SQLite (constraints the dialect can enforce) and pins the
public-code generator/normalizer primitives of the registry.

PostgreSQL-specific behavior (partial unique index under concurrency, FK
ON DELETE SET NULL tombstone, RLS) is proven by
``tests/integration/test_rq16c_direction_public_address_pg.py`` — SQLite
is never a substitute for the PG acceptance, only a parity check for the
metadata-level constraints (precedent: push_device registry partial index
is declared for both dialects).

SYNTHETIC data only; the registry holds no PII/secret columns (pinned
below).
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (registry import side-effect — autogenerate visibility)
from app.models.queue_direction_public_address import (
    PUBLIC_CODE_ALPHABET,
    PUBLIC_CODE_LENGTH,
    QueueDirectionPublicAddress,
    generate_public_code,
    normalize_public_code,
)
from app.models.queue_profile import QueueProfile

EXPECTED_COLUMNS = {"id", "queue_profile_id", "public_code", "created_at", "retired_at"}


@pytest.fixture()
def sqlite_session():
    engine = create_engine("sqlite://", future=True)
    from app.db.base import Base  # imports the full model registry

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


def _make_profile(session: Session, key: str) -> QueueProfile:
    profile = QueueProfile(
        key=key,
        title=f"Synthetic {key}",
        queue_tags=[f"tag_{key}"],
        display_order=999,
        is_active=True,
        show_on_qr_page=True,
    )
    session.add(profile)
    session.flush()
    return profile


def _make_address(session: Session, profile_id: int, code: str) -> QueueDirectionPublicAddress:
    row = QueueDirectionPublicAddress(queue_profile_id=profile_id, public_code=code)
    session.add(row)
    session.flush()
    return row


# ----------------------------------------------------------------- model


def test_model_registered_in_metadata_with_expected_shape():
    """Registry visibility for autogenerate + exact column set (no PII)."""
    from app.db.base import Base

    assert "queue_direction_public_addresses" in Base.metadata.tables
    cols = {c.name for c in QueueDirectionPublicAddress.__table__.columns}
    assert cols == EXPECTED_COLUMNS, (
        "registry holds ONLY id/link/code/timestamps — no PII, no secret data"
    )


def test_table_constraints_declared():
    table = QueueDirectionPublicAddress.__table__
    constraint_names = {c.name for c in table.constraints if c.name}
    index_names = {ix.name for ix in table.indexes}
    assert "uq_qdpa_public_code" in constraint_names, "global UNIQUE forever"
    assert "ck_qdpa_code_length" in constraint_names
    assert "ck_qdpa_code_canonical" in constraint_names
    assert "uq_qdpa_one_active_per_profile" in index_names, (
        "one active address per profile — partial unique index"
    )
    fks = {fk.target_fullname.split(".")[0] for fk in table.foreign_keys}
    assert fks == {"queue_profiles"}


# ------------------------------------------------- SQLite create_all parity


def test_sqlite_create_all_parity_and_checks(sqlite_session):
    inspector = inspect(sqlite_session.bind)
    assert "queue_direction_public_addresses" in inspector.get_table_names()
    columns = {c["name"] for c in inspector.get_columns("queue_direction_public_addresses")}
    assert columns == EXPECTED_COLUMNS

    profile = _make_profile(sqlite_session, "rq16c_unit_a")
    row = _make_address(sqlite_session, profile.id, generate_public_code())
    assert row.id is not None

    # Duplicate public_code is rejected on SQLite too (global UNIQUE).
    other = _make_profile(sqlite_session, "rq16c_unit_b")
    with pytest.raises(IntegrityError):
        _make_address(sqlite_session, other.id, row.public_code)
    sqlite_session.rollback()

    # CHECK length is enforced by the DDL.
    with pytest.raises(IntegrityError):
        _make_address(sqlite_session, other.id, "2")
    sqlite_session.rollback()

    # CHECK canonical lowercase is enforced by the DDL.
    with pytest.raises(IntegrityError):
        _make_address(sqlite_session, other.id, "A2345678BCDE")
    sqlite_session.rollback()

    # One ACTIVE address per profile — partial unique (sqlite_where parity).
    first = generate_public_code()
    second = generate_public_code()
    while second == first:
        second = generate_public_code()
    _make_address(sqlite_session, other.id, first)
    try:
        with pytest.raises(IntegrityError):
            _make_address(sqlite_session, other.id, second)
    except OperationalError:  # pragma: no cover - dialect shortfall guard
        pytest.fail("SQLite parity for the partial unique index is expected to hold")
    sqlite_session.rollback()


# ---------------------------------------------------------------- generator


def test_generate_public_code_shape_and_uniqueness():
    codes = {generate_public_code() for _ in range(1000)}
    assert len(codes) == 1000, "1000 crypto-random draws never collide (12 chars, 30^12)"
    for code in codes:
        assert len(code) == PUBLIC_CODE_LENGTH == 12
        assert code == code.lower()
        assert all(ch in PUBLIC_CODE_ALPHABET for ch in code)
        assert not any(ch in "0o1il" for ch in code), "no ambiguous glyphs"


def test_normalize_public_code_ascii_case_only():
    assert normalize_public_code("  AbC234DEF5Gh ") == "abc234def5gh"
    assert normalize_public_code("23456789ABCDEF") == "23456789abcdef"
    # No transliteration, no locale dependency — ASCII lowering only.
    assert normalize_public_code("АВС") == "авс"  # Cyrillic letters pass through untouched
