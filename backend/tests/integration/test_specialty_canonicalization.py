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
from datetime import date, datetime, time, timedelta
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
    db_session, test_doctor_user, monkeypatch
) -> None:
    """A profile with OLD queue_tags (no 'dentistry') must still see a
    canonical 'dentistry' doctor (the 0049 code-level half of D-1)."""
    # The join path enforces the online booking window (07:00 local):
    # without freezing it this test fails whenever the suite runs between
    # midnight and 07:00 (observed as CI red at 02:50-03:22 local).
    # Same pattern as test_qr_queue_join.py.
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
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


def test_migration_0049_rewrites_case_variants_of_canonical(tmp_path) -> None:
    """Codex round-3 P1: case/padding variants of the CANONICAL itself
    ('Dentistry', 'DENTISTRY', ' dentistry ') must be rewritten to the
    exact lowercase value — SQL IN is case-sensitive on the read side."""
    module = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'd1case.db'}")
    con = _scratch_tables(engine)
    try:
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'Dentistry')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (2, 'DENTISTRY')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (3, ' dentistry ')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (4, 'dental')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (5, 'cardiology')")

        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module.op = Operations(MigrationContext.configure(con))
        module.upgrade()

        stored = {
            r[0]
            for r in con.execute(sa.text("SELECT specialty FROM doctors")).fetchall()
        }
        assert stored == {"dentistry", "cardiology"}
        # every family row is stored EXACTLY canonical
        exact = con.execute(
            sa.text(
                "SELECT COUNT(*) FROM doctors WHERE specialty = 'dentistry'"
            )
        ).scalar_one()
        assert exact == 4

        # the postcondition helper accepts the rewritten state...
        module._assert_exact_canonical_family_rows(con)

        # ...and rejects a family row stored differently (direct unit test)
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (6, 'Stomatology')")
        with pytest.raises(RuntimeError, match="postcondition failed"):
            module._assert_exact_canonical_family_rows(con)
    finally:
        con.close()


def test_migration_0049_postcondition_rejects_legacy_spellings(tmp_path) -> None:
    module = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'd1post.db'}")
    con = _scratch_tables(engine)
    try:
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'dentistry')")
        module._assert_exact_canonical_family_rows(con)  # exact rows pass

        for bad in ("stomatology", "dental", "dentist", "Dentistry", " dentistry "):
            _seed(
                con,
                "INSERT INTO doctors (user_id, specialty) VALUES "
                f"(NULL, '{bad}')",
            )
            with pytest.raises(RuntimeError, match="postcondition failed"):
                module._assert_exact_canonical_family_rows(con)
            con.execute(
                sa.text("DELETE FROM doctors WHERE specialty = :s"), {"s": bad}
            )
            con.commit()
    finally:
        con.close()


def test_migration_0049_normalizes_case_variant_settings_keys(tmp_path) -> None:
    """Codex round-3 P1 (settings half): a canonical-suffix row stored with
    a case-variant key (start_number_Dentistry) is normalized to the exact
    lowercase key; an exact-key row wins the survivor role and duplicates
    are merged (max)."""
    module = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'd1casekey.db'}")
    con = _scratch_tables(engine)
    try:
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'dental')")
        # exact canonical row (survivor) + case-variant duplicate + legacy row
        _seed(
            con,
            "INSERT INTO clinic_settings (key, value, category) VALUES "
            "('max_per_day_dentistry', 20, 'queue')",
        )
        _seed(
            con,
            "INSERT INTO clinic_settings (key, value, category) VALUES "
            "('max_per_day_Dentistry', 8, 'queue')",
        )
        _seed(
            con,
            "INSERT INTO clinic_settings (key, value, category) VALUES "
            "('max_per_day_stomatology', 12, 'queue')",
        )
        # case-variant canonical row WITHOUT an exact twin: must be renamed
        _seed(
            con,
            "INSERT INTO clinic_settings (key, value, category) VALUES "
            "('start_number_Dentistry', 4, 'queue')",
        )

        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module.op = Operations(MigrationContext.configure(con))
        module.upgrade()

        def _scalar(key: str):
            return con.execute(
                sa.text("SELECT value FROM clinic_settings WHERE key=:k"),
                {"k": key},
            ).scalar()

        keys = {
            r[0]
            for r in con.execute(sa.text("SELECT key FROM clinic_settings")).fetchall()
        }
        # survivor kept exact key, merged max(20, 8, 12) = 20
        assert int(_scalar("max_per_day_dentistry")) == 20
        # case-variant canonical row WITHOUT exact twin renamed in place
        assert int(_scalar("start_number_dentistry")) == 4
        # only exact lowercase canonical keys remain for the family
        assert not any(
            k.endswith("_Dentistry") or k.endswith("_stomatology") for k in keys
        )
        cat = con.execute(
            sa.text(
                "SELECT category FROM clinic_settings WHERE key='start_number_dentistry'"
            )
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


# ===================== G. Queue repositories (round-3 P1-2) ==============


def _family_doctor(db_session, specialty: str) -> Doctor:
    """A clinic-eligible doctor: linked to an ACTIVE Doctor-role owner
    (the owner-eligibility contract the quick-call/join candidate queries
    apply — Codex round-5 P2; userless rows are legacy ghosts per
    decision #13)."""
    from app.core.security import get_password_hash
    from app.models.user import User

    ordinal = db_session.query(User).count() + 1
    user = User(
        username=f"d1_family_user_{ordinal}",
        email=f"d1_family_user_{ordinal}@test.com",
        hashed_password=get_password_hash("d1family123"),
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    doctor = Doctor(user_id=user.id, specialty=specialty, active=True)
    db_session.add(doctor)
    db_session.commit()
    return doctor


@pytest.mark.parametrize("query", ["dentistry", "dental", "stomatology", "dentist"])
def test_queue_repositories_match_family_spellings(db_session, query) -> None:
    """Both list_active_doctors filters must route through
    specialty_variants: a legacy spelling query still finds canonical
    'dentistry' doctors after migration 0049 (Codex round-3 P1)."""
    from app.repositories.queue_limits_repository import QueueLimitsRepository
    from app.repositories.queue_read_repository import QueueReadRepository

    canonical = _family_doctor(db_session, "dentistry")
    legacy = _family_doctor(db_session, "dental")
    cardiologist = _family_doctor(db_session, "cardiology")

    for repo_cls in (QueueReadRepository, QueueLimitsRepository):
        found = repo_cls(db_session).list_active_doctors(specialty=query)
        ids = {d.id for d in found}
        assert canonical.id in ids, f"{repo_cls.__name__} missed canonical for {query!r}"
        assert legacy.id in ids, f"{repo_cls.__name__} missed legacy for {query!r}"
        assert cardiologist.id not in ids


def test_queue_repositories_unfiltered_still_returns_all(db_session) -> None:
    from app.repositories.queue_limits_repository import QueueLimitsRepository
    from app.repositories.queue_read_repository import QueueReadRepository

    _family_doctor(db_session, "dentistry")
    _family_doctor(db_session, "cardiology")
    for repo_cls in (QueueReadRepository, QueueLimitsRepository):
        found = repo_cls(db_session).list_active_doctors(specialty=None)
        assert len(found) == 2


# ===================== H. /queues/profiles settings_key (round-3 P1-3) ==


def test_queue_profiles_response_carries_canonical_settings_key(db_session) -> None:
    """The profiles payload must carry the backend-computed canonical
    settings segment so the admin screen reads/edits clinic_settings by
    the SAME key the runtime writes (dentistry, not stomatology)."""
    from app.api.v1.endpoints.registrar_integration._queue_profiles import (
        get_queue_profiles,
    )

    payload = get_queue_profiles(active_only=True, db=db_session, current_user=None)
    profiles = payload["profiles"]
    assert profiles, "expected fallback profiles when the table is empty"

    by_key = {p["key"]: p for p in profiles}
    assert "settings_key" in by_key["stomatology"]
    # the machinery key normalizes to the canonical settings segment
    assert by_key["stomatology"]["settings_key"] == "dentistry"
    # non-dental keys pass through unchanged
    assert by_key["cardiology"]["settings_key"] == "cardiology"
    assert by_key["dermatology"]["settings_key"] == "dermatology"


def test_queue_profiles_db_path_settings_key_canonical(db_session) -> None:
    """Database-backed profiles expose the same canonical settings_key."""
    from app.api.v1.endpoints.registrar_integration._queue_profiles import (
        get_queue_profiles,
    )

    db_session.add(
        QueueProfile(
            key="stomatology",
            title="Dental",
            title_ru="Стоматология",
            queue_tags=["dental", "stomatology", "dentist", "dentistry"],
            department_key="stomatology",
            display_order=4,
            is_active=True,
            show_on_qr_page=True,
        )
    )
    db_session.commit()

    payload = get_queue_profiles(active_only=True, db=db_session, current_user=None)
    assert payload["source"] == "database"
    dental = next(p for p in payload["profiles"] if p["key"] == "stomatology")
    assert dental["settings_key"] == "dentistry"


# ===================== I. Round-4 P1: department writer + display ======


def test_reconcile_queue_setting_aliases_renames_when_no_canonical(db_session) -> None:
    """No canonical row: the oldest alias row is renamed IN PLACE (value,
    category, audit columns survive) — get_queue_settings sees ONE row."""
    from app.api.v1.endpoints.admin_departments._helpers import (
        _reconcile_queue_setting_aliases,
    )

    alias = ClinicSettings(
        key="start_number_dental", value=7, category="queue"
    )
    db_session.add(alias)
    db_session.commit()

    _reconcile_queue_setting_aliases(db_session, "start_number_", "dental")
    db_session.commit()

    keys = {s.key for s in db_session.query(ClinicSettings)}
    assert "start_number_dentistry" in keys
    assert "start_number_dental" not in keys
    row = (
        db_session.query(ClinicSettings)
        .filter(ClinicSettings.key == "start_number_dentistry")
        .first()
    )
    assert int(row.value) == 7
    assert row.category == "queue"


def test_reconcile_queue_setting_aliases_deletes_when_canonical_exists(db_session) -> None:
    """Canonical row already present: alias rows are removed so the
    unordered read cannot collapse a stale alias over the enforced value."""
    from app.api.v1.endpoints.admin_departments._helpers import (
        _reconcile_queue_setting_aliases,
    )

    db_session.add_all(
        [
            ClinicSettings(key="max_per_day_dentistry", value=50, category="queue"),
            ClinicSettings(key="max_per_day_dental", value=13, category="queue"),
            ClinicSettings(key="max_per_day_stomatology", value=9, category="queue"),
        ]
    )
    db_session.commit()

    _reconcile_queue_setting_aliases(db_session, "max_per_day_", "dental")
    db_session.commit()

    keys = {s.key for s in db_session.query(ClinicSettings)}
    assert keys == {"max_per_day_dentistry"}
    row = (
        db_session.query(ClinicSettings)
        .filter(ClinicSettings.key == "max_per_day_dentistry")
        .first()
    )
    assert int(row.value) == 50  # canonical value untouched by reconciliation


def test_reconcile_queue_setting_aliases_passthrough_non_dental(db_session) -> None:
    from app.api.v1.endpoints.admin_departments._helpers import (
        _reconcile_queue_setting_aliases,
    )

    db_session.add(
        ClinicSettings(key="start_number_cardiology", value=3, category="queue")
    )
    db_session.commit()

    _reconcile_queue_setting_aliases(db_session, "start_number_", "cardiology")

    keys = {s.key for s in db_session.query(ClinicSettings)}
    assert keys == {"start_number_cardiology"}


def test_department_integration_writes_canonical_settings_keys(db_session) -> None:
    """Codex round-4 P1: re-integrating the 'dental' department must write
    start_number_dentistry / max_per_day_dentistry and reconcile legacy
    alias rows instead of creating a colliding duplicate."""
    from app.api.v1.endpoints.admin_departments._helpers import (
        _ensure_department_integrations,
    )
    from app.models.department import Department

    legacy_alias = ClinicSettings(
        key="start_number_dental", value=7, category="queue"
    )
    db_session.add(legacy_alias)
    db_session.add(
        Department(key="dental", name_ru="Стоматология", active=True)
    )
    db_session.commit()

    department = (
        db_session.query(Department).filter(Department.key == "dental").first()
    )
    result = _ensure_department_integrations(db_session, department, None)
    db_session.commit()

    keys = {s.key for s in db_session.query(ClinicSettings)}
    assert "start_number_dental" not in keys
    assert "max_per_day_dental" not in keys
    assert "start_number_dentistry" in keys
    assert "max_per_day_dentistry" in keys
    # renamed in place: legacy configured value preserved
    start_row = (
        db_session.query(ClinicSettings)
        .filter(ClinicSettings.key == "start_number_dentistry")
        .first()
    )
    assert int(start_row.value) == 7
    # integration result reports the canonical keys
    assert "start_number_dentistry" in result["clinic_settings_updated"] or (
        "max_per_day_dentistry" in result["clinic_settings_updated"]
    )
    # and the screen reads ONE canonical value per key
    settings = crud_clinic.get_queue_settings(db_session)
    assert settings["start_numbers"]["dentistry"] == 7


def test_display_repository_matches_family_spellings(db_session) -> None:
    """Codex round-4 P1: /display/quick/call-next resolves a canonical
    'dentistry' doctor for the still-live 'stomatology' profile key."""
    from app.repositories.display_websocket_api_repository import (
        DisplayWebSocketApiRepository,
    )

    doctor = _family_doctor(db_session, "dentistry")
    found = DisplayWebSocketApiRepository(db_session).get_active_doctor_by_specialty(
        "stomatology"
    )
    assert found is not None
    assert found.id == doctor.id

    doctor.active = False
    db_session.commit()
    assert (
        DisplayWebSocketApiRepository(db_session).get_active_doctor_by_specialty(
            "dentistry"
        )
        is None
    )


@pytest.mark.parametrize(
    "left,right,expected",
    [
        ("dentistry", "stomatology", True),
        ("dental", "dentistry", True),
        ("Dentistry", " dentistry ", True),
        ("dentist", "stomatology", True),
        ("cardiology", "Cardiology", True),
        ("cardiology", "cardio", False),
        ("dentistry", "cardiology", False),
        ("", "", True),
        (None, None, True),
        ("", "dentistry", False),
    ],
)
def test_same_specialty_canonical_comparison(left, right, expected) -> None:
    """The doctor-branch quick-call guard must accept family spellings."""
    from app.services.display_websocket_api_service import DisplayWebSocketApiService

    assert DisplayWebSocketApiService._same_specialty(left, right) is expected


# ===================== J. Round-5: family profiles + remaining filters ==


def test_migration_0049_patches_every_dental_family_profile(tmp_path) -> None:
    """Codex round-5 P1: the departments integration writer creates a
    profile key='dental' with tags=['dental'] — the migration must patch
    EVERY dental-family profile (by key OR by tag), not only
    key='stomatology'."""
    module = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'd1prof.db'}")
    con = _scratch_tables(engine)
    try:
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'dental')")
        _seed(
            con,
            "INSERT INTO queue_profiles (key, queue_tags) VALUES "
            "('dental', '[\"dental\"]')",
        )
        _seed(
            con,
            "INSERT INTO queue_profiles (key, queue_tags) VALUES "
            "('stomatology', '[\"dental\", \"stomatology\", \"dentist\"]')",
        )
        # non-family key with a family tag (service profile tagged dental)
        _seed(
            con,
            "INSERT INTO queue_profiles (key, queue_tags) VALUES "
            "('implants', '[\"dental\", \"implants\"]')",
        )
        # already canonical -> untouched
        _seed(
            con,
            "INSERT INTO queue_profiles (key, queue_tags) VALUES "
            "('dentistry-seed', '[\"dentistry\"]')",
        )
        # non-dental profile -> untouched
        _seed(
            con,
            "INSERT INTO queue_profiles (key, queue_tags) VALUES "
            "('cardiology', '[\"cardio\", \"cardiology\"]')",
        )

        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module.op = Operations(MigrationContext.configure(con))
        module.upgrade()

        tags_by_key = {}
        for key, tags in con.execute(
            sa.text("SELECT key, queue_tags FROM queue_profiles")
        ).fetchall():
            if isinstance(tags, str):
                import json as _json

                tags = _json.loads(tags)
            tags_by_key[key] = tags

        assert "dentistry" in tags_by_key["dental"]
        assert "dentistry" in tags_by_key["stomatology"]
        assert "dentistry" in tags_by_key["implants"]
        assert tags_by_key["dentistry-seed"] == ["dentistry"]
        assert "dentistry" not in tags_by_key["cardiology"]
    finally:
        con.close()


def test_department_integration_profile_tags_cover_family(db_session) -> None:
    """Codex round-5 P1: the integration writer must not create a
    'dental'-tag-only profile blind to canonical 'dentistry' doctors."""
    from app.api.v1.endpoints.admin_departments._helpers import (
        _ensure_department_integrations,
    )
    from app.models.department import Department

    db_session.add(
        Department(key="dental", name_ru="Стоматология", active=True)
    )
    db_session.commit()
    department = (
        db_session.query(Department).filter(Department.key == "dental").first()
    )

    _ensure_department_integrations(db_session, department, None)
    db_session.commit()

    profile = (
        db_session.query(QueueProfile).filter(QueueProfile.key == "dental").first()
    )
    assert profile is not None
    assert "dentistry" in (profile.queue_tags or [])
    assert "dental" in (profile.queue_tags or [])

    # and the QR clinic-wide matcher now sees canonical dentistry doctors
    from app.models.clinic import Doctor as DoctorModel
    from app.services.qr_queue import QRQueueService

    doctor = DoctorModel(specialty="dentistry", active=True)
    db_session.add(doctor)
    db_session.commit()

    selectable = QRQueueService(db_session)._get_clinic_wide_selectable_specialists()
    # the dental-family profile (key 'dental', machinery-normalized tags)
    # must surface the canonical doctor; the entry label is the profile key
    assert any(s["id"] == doctor.id for s in selectable)


def test_admin_doctors_filter_matches_family_spellings(db_session) -> None:
    """Codex round-5 P2: GET /admin/doctors?specialty=<legacy spelling>
    keeps finding canonical rows after 0049."""
    from app.api.v1.endpoints.admin_doctors import get_doctors

    canonical = crud_clinic.create_doctor(
        db_session, DoctorCreate(specialty="dentistry", active=True)
    )
    for query in ("dental", "stomatology", "dentist", "dentistry"):
        result = get_doctors(
            skip=0,
            limit=100,
            active_only=False,
            specialty=query,
            db=db_session,
            current_user=None,
        )
        ids = {item.id for item in result}
        assert canonical.id in ids, f"admin doctors filter missed for {query!r}"

    result = get_doctors(
        skip=0,
        limit=100,
        active_only=False,
        specialty="cardiology",
        db=db_session,
        current_user=None,
    )
    assert canonical.id not in {item.id for item in result}


def test_analytics_department_filter_matches_family_spellings(db_session) -> None:
    """Codex round-5 P2: dental queue analytics filtered by a legacy
    department key must match canonical 'dentistry' doctors."""
    from datetime import datetime, timedelta

    from app.models.online_queue import DailyQueue as DailyQueueModel
    from app.services.analytics import AnalyticsService

    doctor = _family_doctor(db_session, "dentistry")
    day = datetime.utcnow() - timedelta(days=1)
    queue = DailyQueueModel(day=day.date(), specialist_id=doctor.id, active=True)
    db_session.add(queue)
    db_session.commit()

    stats = AnalyticsService.get_queue_statistics(
        db_session,
        start_date=day - timedelta(days=1),
        end_date=day + timedelta(days=1),
        department="dental",
    )
    assert stats["total_queues"] >= 1

    # canonical spelling works too
    stats = AnalyticsService.get_queue_statistics(
        db_session,
        start_date=day - timedelta(days=1),
        end_date=day + timedelta(days=1),
        department="dentistry",
    )
    assert stats["total_queues"] >= 1


def test_get_department_info_localizes_canonical_dental(db_session) -> None:
    """Codex round-5 P2: canonical 'dentistry' maps to the localized
    dental department name, not the .title() fallback 'Dentistry'."""
    from app.services.doctor_info_service import DoctorInfoService

    _family_doctor(db_session, "dentistry")
    info = DoctorInfoService(db_session).get_department_info("dentistry")
    assert info is not None
    assert info["name"] == "Стоматология"
    assert info["description"] == "Отделение Стоматология"
    assert info["doctors_count"] == 1


# ===================== K. Round-6 P1: profile CRUD tag expansion =======


def test_queue_profile_create_expands_family_tags(db_session) -> None:
    """Codex round-6 P1: POST /queues/profiles with a dental-family key and
    omitted/empty tags must persist tags covering the canonical spelling."""
    from app.api.v1.endpoints.registrar_integration._queue_profiles import (
        QueueProfileCreate,
        create_queue_profile,
    )

    created = create_queue_profile(
        profile_data=QueueProfileCreate(key="dental", title="Dental"),
        db=db_session,
        current_user=None,
    )
    tags = created["profile"]["queue_tags"]
    assert "dentistry" in tags
    assert "dental" in tags

    # explicit unrelated tags on a family-key profile STILL cover the family
    created2 = create_queue_profile(
        profile_data=QueueProfileCreate(
            key="implants", title="Implants", queue_tags=["implants"]
        ),
        db=db_session,
        current_user=None,
    )
    # non-family key: passthrough (key unioned, no family)
    assert created2["profile"]["queue_tags"] == ["implants"]

    created2b = create_queue_profile(
        profile_data=QueueProfileCreate(
            key="dentist", title="Dentist", queue_tags=["caries"]
        ),
        db=db_session,
        current_user=None,
    )
    # family key ('dentist' is a family spelling) -> canonical guaranteed
    assert "dentistry" in created2b["profile"]["queue_tags"]
    assert "caries" in created2b["profile"]["queue_tags"]

    # non-dental profile passes through unchanged
    created3 = create_queue_profile(
        profile_data=QueueProfileCreate(key="cardio2", title="Cardio2"),
        db=db_session,
        current_user=None,
    )
    assert created3["profile"]["queue_tags"] == ["cardio2"]


def test_queue_profile_update_expands_family_tags(db_session) -> None:
    """Codex round-6 P1: PUT /queues/profiles/{key} must expand tags —
    clearing tags falls back to the profile key; a family-key profile
    stays canonical-covered even when the admin sets unrelated tags."""
    from app.api.v1.endpoints.registrar_integration._queue_profiles import (
        QueueProfileUpdate,
        update_queue_profile,
    )

    db_session.add(
        QueueProfile(
            key="dental",
            title="Dental",
            queue_tags=["dental"],
            display_order=9,
            is_active=True,
            show_on_qr_page=True,
        )
    )
    db_session.commit()

    # explicit unrelated tags on a family-key profile: key unioned in
    updated = update_queue_profile(
        profile_key="dental",
        profile_data=QueueProfileUpdate(queue_tags=["prosthesis"]),
        db=db_session,
        current_user=None,
    )
    tags = updated["profile"]["queue_tags"]
    assert "prosthesis" in tags
    assert "dentistry" in tags
    assert "dental" in tags

    # clearing the tags: falls back to [profile.key] -> family covered
    cleared = update_queue_profile(
        profile_key="dental",
        profile_data=QueueProfileUpdate(queue_tags=[]),
        db=db_session,
        current_user=None,
    )
    assert "dentistry" in cleared["profile"]["queue_tags"]

    # a NON-family key update never gains dental tags
    db_session.add(
        QueueProfile(
            key="orthodontics2",
            title="Ortho2",
            queue_tags=["ortho"],
            display_order=10,
            is_active=True,
            show_on_qr_page=True,
        )
    )
    db_session.commit()
    updated2 = update_queue_profile(
        profile_key="orthodontics2",
        profile_data=QueueProfileUpdate(queue_tags=["ortho2"]),
        db=db_session,
        current_user=None,
    )
    # non-family profile: EXACTLY the submitted tags (Codex round-7 P2 —
    # the key is never silently re-added after an explicit removal)
    assert updated2["profile"]["queue_tags"] == ["ortho2"]


# ===================== L. Round-7 P2: doctor-info specialization ========


def test_get_doctors_by_specialization_matches_family(db_session) -> None:
    """Codex round-7 P2: the ILIKE specialization filter matches every
    family spelling — legacy 'stomatology' keeps finding canonical rows."""
    from app.services.doctor_info_service import DoctorInfoService

    canonical = _family_doctor(db_session, "dentistry")
    _family_doctor(db_session, "cardiology")

    for query in ("dentistry", "dental", "stomatology", "dentist"):
        result = DoctorInfoService(db_session).get_doctors_by_specialization(query)
        ids = {item["id"] for item in result}
        assert canonical.id in ids, f"specialization filter missed for {query!r}"

    # a cardiology query never returns the dental doctor
    result = DoctorInfoService(db_session).get_doctors_by_specialization("cardiology")
    assert canonical.id not in {item["id"] for item in result}


# ===================== M. Round-8 P2: GraphQL filter + stats metadata ===


def test_graphql_doctors_filter_matches_family(db_session, monkeypatch) -> None:
    """Codex round-8 P2: the GraphQL doctors() specialty filter matches
    every family spelling via variants (OR of ILIKEs).

    NOTE: the session is injected because ALL resolvers share a
    pre-existing defect (db = get_db_session() without 'with') that is
    out of scope for D-1 — the filter logic itself is under test."""
    from app.graphql import resolvers as gql_resolvers
    from app.graphql.types import DoctorFilter, PaginatedDoctors

    monkeypatch.setattr(gql_resolvers, "get_db_session", lambda: db_session)

    canonical = _family_doctor(db_session, "dentistry")

    for query_value in ("stomatology", "dental", "dentistry", "dentist"):
        page = gql_resolvers.Query().doctors(
            filter=DoctorFilter(specialty=query_value), pagination=None
        )
        assert isinstance(page, PaginatedDoctors)
        ids = {item.id for item in page.items}
        assert canonical.id in ids, f"GraphQL filter missed for {query_value!r}"


def test_admin_specialties_metadata_covers_canonical(db_session) -> None:
    """Codex round-8 P2: /admin/doctors/specialties returns the localized
    dental metadata for the canonical 'dentistry' code, not raw labels."""
    from app.services.admin_doctors_stats_service import AdminDoctorsStatsService

    _family_doctor(db_session, "dentistry")
    service = AdminDoctorsStatsService(db_session)
    rows = service.get_specialties()

    dental = next(r for r in rows if r["code"] == "dentistry")
    assert dental["name_ru"] == "Стоматология"
    assert dental["name_en"] == "Dentistry"
    assert dental["color"] == "#007bff"
    assert dental["description"] == "Стоматологические услуги"
    assert dental["doctor_count"] == 1


# ===================== F. Mobile search variants (round-2 P2) ===========


def test_search_doctors_matches_family_spellings(db_session) -> None:
    canonical = crud_clinic.create_doctor(
        db_session, DoctorCreate(specialty="dentistry", active=True)
    )
    for query in ("dental", "stomatology", "dentist"):
        found = crud_clinic.search_doctors(db_session, specialty=query)
        assert canonical.id in {d.id for d in found}, f"missed for {query!r}"
