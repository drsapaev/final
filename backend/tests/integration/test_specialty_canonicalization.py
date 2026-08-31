"""D-1 canonical specialty vocabulary (migration 0049 + core/specialties).

NEEDS DECISION D-1: ``dentistry`` is THE canonical stored value of the
dental family (``dental`` / ``dentist`` / ``stomatology`` / ``dentistry``).

Covers:
- unit level: canonical_specialty / specialty_variants / expand_queue_tags;
- write boundary: create_doctor / update_doctor normalize specialty;
- read side: get_doctors_by_specialty matches any family spelling;
- queue join: clinic-wide QR join finds a canonical "dentistry" doctor for
  a profile whose stored queue_tags predate migration 0049;
- migration 0049: real upgrade() rewrites doctors, profile tags and
  specialty-keyed clinic_settings values; downgrade is a no-op.
"""
from __future__ import annotations

import importlib.util
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import sqlalchemy as sa

from app.core.specialties import (
    DENTAL_CANONICAL_SPECIALTY,
    canonical_specialty,
    expand_queue_tags,
    specialty_variants,
)
from app.crud import clinic as crud_clinic
from app.models.clinic import ClinicSettings, Doctor
from app.models.online_queue import QueueToken
from app.models.queue_profile import QueueProfile
from app.schemas.clinic import DoctorCreate, DoctorUpdate
from app.services.queue_service import QueueBusinessService


# ===================== A. Unit level =====================


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("dental", "dentistry"),
        ("dentist", "dentistry"),
        ("stomatology", "dentistry"),
        ("dentistry", "dentistry"),
        ("  Dental  ", "dentistry"),
        ("STOMATOLOGY", "dentistry"),
        ("cardiology", "cardiology"),
        ("cardio", "cardio"),
        (None, None),
        ("", ""),
        ("   ", ""),
    ],
)
def test_canonical_specialty(raw, expected) -> None:
    assert canonical_specialty(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("dental", {"dental", "dentist", "dentistry", "stomatology"}),
        ("Dentist", {"dental", "dentist", "dentistry", "stomatology"}),
        ("cardiology", {"cardiology"}),
        ("Cardio", {"Cardio"}),
        (None, set()),
        ("", {""}),
    ],
)
def test_specialty_variants(raw, expected) -> None:
    assert set(specialty_variants(raw)) == expected


def test_expand_queue_tags_family_and_dedupe() -> None:
    expanded = expand_queue_tags(["dental", "stomatology", "cardiology"])
    # every dental spelling present, originals kept, deduplicated
    assert "dentistry" in expanded
    assert "dental" in expanded and "stomatology" in expanded
    assert "cardiology" in expanded
    assert len(expanded) == len(set(expanded))
    assert expanded[0] == "dental"  # original order preserved first


def test_expand_queue_tags_empty() -> None:
    assert expand_queue_tags(None) == []
    assert expand_queue_tags([]) == []


# ===================== B. CRUD write boundary =====================


def test_create_doctor_normalizes_dental_spellings(db_session) -> None:
    doctor = crud_clinic.create_doctor(
        db_session, DoctorCreate(specialty="dental", active=True)
    )
    db_session.refresh(doctor)
    assert doctor.specialty == DENTAL_CANONICAL_SPECIALTY


def test_create_doctor_keeps_non_dental_specialty(db_session) -> None:
    doctor = crud_clinic.create_doctor(
        db_session, DoctorCreate(specialty="cardiology", active=True)
    )
    db_session.refresh(doctor)
    assert doctor.specialty == "cardiology"


def test_update_doctor_normalizes_specialty(db_session) -> None:
    doctor = crud_clinic.create_doctor(
        db_session, DoctorCreate(specialty="cardiology", active=True)
    )
    updated = crud_clinic.update_doctor(
        db_session, doctor.id, DoctorUpdate(specialty=" stomatology ")
    )
    assert updated.specialty == DENTAL_CANONICAL_SPECIALTY


def test_get_doctors_by_specialty_matches_all_family_spellings(db_session) -> None:
    canonical = crud_clinic.create_doctor(
        db_session, DoctorCreate(specialty="dentistry", active=True)
    )
    # a legacy row inserted directly (bypassing the write boundary)
    legacy = Doctor(specialty="stomatology", active=True)
    db_session.add(legacy)
    db_session.commit()

    for query in ("dentistry", "dental", "stomatology", "dentist"):
        found = crud_clinic.get_doctors_by_specialty(db_session, specialty=query)
        ids = {d.id for d in found}
        assert canonical.id in ids, f"canonical doctor missed for query {query!r}"
        assert legacy.id in ids, f"legacy doctor missed for query {query!r}"


def test_get_doctors_by_specialty_eligible_only_still_hides_general(db_session) -> None:
    crud_clinic.create_doctor(
        db_session, DoctorCreate(specialty="dental", active=True)
    )
    db_session.add(Doctor(specialty="general", active=True))
    db_session.commit()

    found = crud_clinic.get_doctors_by_specialty(
        db_session, specialty="dental", eligible_only=True
    )
    assert found
    assert all(d.specialty != "general" for d in found)


# ===================== C. Queue join (tag expansion) =====================


@pytest.mark.queue
def test_clinic_wide_join_finds_canonical_dentistry_doctor(
    db_session, test_doctor_user
) -> None:
    """A profile with OLD queue_tags (no 'dentistry') must still see a
    canonical 'dentistry' doctor (the 0049 code-level half of D-1)."""
    doctor = Doctor(user_id=test_doctor_user.id, specialty="dentistry", active=True)
    db_session.add(doctor)
    db_session.flush()
    profile = QueueProfile(
        key="stomatology",
        title="Dental",
        title_ru="Стоматология",
        queue_tags=["dental", "stomatology", "dentist"],  # pre-0049 tags
        department_key="stomatology",
        display_order=4,
        is_active=True,
        show_on_qr_page=True,
    )
    db_session.add(profile)
    db_session.flush()

    local_now = datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)
    token = QueueToken(
        token="d1-canonical-join-token",
        day=date.today(),
        specialist_id=None,
        department=None,
        is_clinic_wide=True,
        expires_at=local_now + timedelta(hours=2),
        active=True,
    )
    db_session.add(token)
    db_session.commit()

    svc = QueueBusinessService()
    result = svc.join_queue_with_token(
        db_session,
        token_str=token.token,
        patient_name="D-1 Patient",
        phone="+998900000111",
        specialist_id_override=profile.id,
    )
    # The join resolved the profile to the canonical doctor instead of
    # raising "Нет активных врачей для профиля ...".
    assert result["entry"] is not None
    assert result.get("specialist_name") or doctor.user is not None


# ===================== D. Migration 0049 =====================


def _load_migration():
    path = (
        Path(__file__)
        .resolve()
        .parents[2]
        / "alembic"
        / "versions"
        / "0049_dental_specialty_canonical.py"
    )
    spec = importlib.util.spec_from_file_location("mig_0049", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scratch_tables(engine: sa.Engine) -> sa.Connection:
    con = engine.connect()
    con.execute(
        sa.text(
            """
            CREATE TABLE doctors (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                specialty VARCHAR(100) NOT NULL,
                active BOOLEAN NOT NULL DEFAULT 1
            )
            """
        )
    )
    con.execute(
        sa.text(
            """
            CREATE TABLE queue_profiles (
                id INTEGER PRIMARY KEY,
                key VARCHAR(50),
                queue_tags JSON
            )
            """
        )
    )
    con.execute(
        sa.text(
            """
            CREATE TABLE clinic_settings (
                id INTEGER PRIMARY KEY,
                key VARCHAR(100) UNIQUE,
                value JSON,
                category VARCHAR(50)
            )
            """
        )
    )
    con.commit()
    return con


def _seed(con: sa.Connection, sql: str) -> None:
    con.execute(sa.text(sql))
    con.commit()


def test_migration_0049_rewrites_doctors_profiles_and_settings(tmp_path) -> None:
    module = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'd1.db'}")
    con = _scratch_tables(engine)
    try:
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'dental')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (2, 'Dentist')")
        _seed(
            con,
            "INSERT INTO doctors (user_id, specialty) VALUES (3, '  stomatology ')",
        )
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (4, 'dentistry')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (5, 'cardiology')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (NULL, 'general')")
        _seed(
            con,
            "INSERT INTO queue_profiles (key, queue_tags) VALUES "
            "('stomatology', '[\"dental\", \"stomatology\", \"dentist\"]')",
        )
        # limits use the REAL storage representation: one row per
        # <prefix><specialty>, category='queue' (Codex round-2 P1)
        _seed(
            con,
            "INSERT INTO clinic_settings (key, value, category) VALUES "
            "('max_per_day_stomatology', 12, 'queue')",
        )
        _seed(
            con,
            "INSERT INTO clinic_settings (key, value, category) VALUES "
            "('start_number_Dental', 4, 'queue')",
        )
        # an existing canonical row must be MERGED (max wins), not duplicated
        _seed(
            con,
            "INSERT INTO clinic_settings (key, value, category) VALUES "
            "('max_per_day_dentistry', 20, 'queue')",
        )
        # non-dental rows untouched
        _seed(
            con,
            "INSERT INTO clinic_settings (key, value, category) VALUES "
            "('max_per_day_cardiology', 30, 'queue')",
        )

        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module.op = Operations(MigrationContext.configure(con))
        module.upgrade()

        spellings = {
            r[0]: r[1]
            for r in con.execute(
                sa.text("SELECT specialty, COUNT(*) FROM doctors GROUP BY 1")
            ).fetchall()
        }
        assert spellings == {"dentistry": 4, "cardiology": 1, "general": 1}

        tags = con.execute(
            sa.text("SELECT queue_tags FROM queue_profiles WHERE key='stomatology'")
        ).scalar()
        if isinstance(tags, str):
            import json as _json

            tags = _json.loads(tags)
        assert "dentistry" in tags
        assert "dental" in tags and "dentist" in tags  # originals preserved

        def _scalar_one(key: str):
            return con.execute(
                sa.text("SELECT value FROM clinic_settings WHERE key=:k"),
                {"k": key},
            ).scalar()

        def _exists(key: str) -> bool:
            return con.execute(
                sa.text("SELECT COUNT(*) FROM clinic_settings WHERE key=:k"),
                {"k": key},
            ).scalar_one() > 0

        # merge semantics: max(12 stomatology, 20 canonical) -> 20
        assert int(_scalar_one("max_per_day_dentistry")) == 20
        assert not _exists("max_per_day_stomatology")
        # dental-only row renamed IN PLACE: canonical created from dental
        # value with its category preserved (get_queue_settings reads by
        # category — a category-less row would be invisible)
        assert int(_scalar_one("start_number_dentistry")) == 4
        assert not _exists("start_number_Dental")
        assert not _exists("start_number_dental")
        row_cat = con.execute(
            sa.text("SELECT category FROM clinic_settings WHERE key='start_number_dentistry'")
        ).scalar()
        assert row_cat == "queue"
        # non-dental untouched
        assert int(_scalar_one("max_per_day_cardiology")) == 30
    finally:
        con.close()


def test_migration_0049_dental_only_limits_are_not_lost(tmp_path) -> None:
    """Deployment with ONLY stomatology-suffixed rows: canonical rows are
    created from the dental values (limits not silently reset to defaults)."""
    module = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'd1only.db'}")
    con = _scratch_tables(engine)
    try:
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'dental')")
        _seed(
            con,
            "INSERT INTO clinic_settings (key, value, category) VALUES "
            "('max_per_day_stomatology', 12, 'queue')",
        )
        _seed(
            con,
            "INSERT INTO clinic_settings (key, value, category) VALUES "
            "('start_number_stomatology', 7, 'queue')",
        )

        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module.op = Operations(MigrationContext.configure(con))
        module.upgrade()

        mx = con.execute(
            sa.text("SELECT value FROM clinic_settings WHERE key='max_per_day_dentistry'")
        ).scalar()
        sn = con.execute(
            sa.text("SELECT value FROM clinic_settings WHERE key='start_number_dentistry'")
        ).scalar()
        assert int(mx) == 12
        assert int(sn) == 7
        keys = {
            r[0]
            for r in con.execute(sa.text("SELECT key FROM clinic_settings")).fetchall()
        }
        assert not any(k.endswith("_stomatology") for k in keys)
        cat = con.execute(
            sa.text("SELECT category FROM clinic_settings WHERE key='max_per_day_dentistry'")
        ).scalar()
        assert cat == "queue"
    finally:
        con.close()


def test_migration_0049_downgrade_is_noop(tmp_path) -> None:
    module = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'd1down.db'}")
    con = _scratch_tables(engine)
    try:
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'dental')")

        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module.op = Operations(MigrationContext.configure(con))
        module.upgrade()
        module.downgrade()  # must not raise, must not revert data

        spellings = {
            r[0] for r in con.execute(sa.text("SELECT specialty FROM doctors"))
        }
        assert spellings == {"dentistry"}
    finally:
        con.close()


# ===================== E. Settings-key normalization (round-2 P1-3) =====


def test_get_queue_settings_exposes_canonical_keys(db_session) -> None:
    """Legacy prefixed rows (any dental spelling) read as ONE canonical key."""
    from app.models.clinic import ClinicSettings

    db_session.add_all(
        [
            ClinicSettings(
                key="max_per_day_stomatology", value=12, category="queue"
            ),
            ClinicSettings(key="start_number_Dental", value=4, category="queue"),
        ]
    )
    db_session.commit()

    settings = crud_clinic.get_queue_settings(db_session)
    assert settings["max_per_day"]["dentistry"] == 12
    assert settings["start_numbers"]["dentistry"] == 4
    assert "stomatology" not in settings["max_per_day"]


def test_update_queue_settings_writes_canonical_keys(db_session) -> None:
    """A screen editing by a legacy profile key must not resurrect a row
    runtime code ignores: the stored key uses the canonical segment."""
    crud_clinic.update_queue_settings(
        db_session,
        {"start_numbers": {"stomatology": 9}, "max_per_day": {"dental": 21}},
        user_id=1,
    )

    keys = {
        s.key
        for s in db_session.query(ClinicSettings).filter(
            ClinicSettings.category == "queue"
        )
    }
    assert "start_number_dentistry" in keys
    assert "max_per_day_dentistry" in keys
    assert not any(k.endswith("_stomatology") for k in keys)
    assert not any(k.endswith("_dental") for k in keys)

    # and it reads back canonically
    settings = crud_clinic.get_queue_settings(db_session)
    assert settings["start_numbers"]["dentistry"] == 9
    assert settings["max_per_day"]["dentistry"] == 21


# ===================== F. Mobile search variants (round-2 P2) ===========


def test_search_doctors_matches_family_spellings(db_session) -> None:
    canonical = crud_clinic.create_doctor(
        db_session, DoctorCreate(specialty="dentistry", active=True)
    )
    for query in ("dental", "stomatology", "dentist"):
        found = crud_clinic.search_doctors(db_session, specialty=query)
        assert canonical.id in {d.id for d in found}, f"missed for {query!r}"
