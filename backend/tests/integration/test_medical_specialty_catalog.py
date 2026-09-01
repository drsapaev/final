"""Medical Specialty Catalog foundation — owner-pinned test set (2026-09-01).

Contract under test:
- migration 0051 creates the table with baseline seed (3 canonical rows);
- seeding is deterministic/idempotent and never overwrites existing titles;
- the catalog is the runtime SSOT for onboarding vocabulary: active rows
  only, ordered by sort_order then code; NO hardcoded fallback — an empty
  catalog is an explicit configuration failure;
- ``active`` semantics: selectable for NEW assignment only — existing
  Doctor rows are untouched when a specialty is deactivated;
- catalog independence from Department / QueueProfile (separate domains);
- production reality (DISTINCT doctors.specialty = cardiology) stays valid.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.medical_specialty import MedicalSpecialty
from app.services.medical_specialty_catalog import (
    MedicalSpecialtyCatalogError,
    MedicalSpecialtyCatalogService,
)
from app.services.medical_specialty_seed import (
    MEDICAL_SPECIALTY_BASELINE,
    seed_medical_specialties,
)

BASELINE_CODES = [row[0] for row in MEDICAL_SPECIALTY_BASELINE]


@pytest.fixture
def seeded_catalog(db_session: Session) -> Session:
    seed_medical_specialties(db_session.connection())
    db_session.commit()
    return db_session


class TestCatalogTableAndSeed:
    def test_table_exists_with_expected_columns(self, db_session: Session):
        # (1) migration creates the table — in tests the identical DDL comes
        # from Base.metadata.create_all; alembic chain 0050->0051 is verified
        # separately (heads/history run in CI migrations checks).
        columns = {
            col["name"]
            for col in inspect(db_session.bind).get_columns("medical_specialties")
        }
        assert columns == {
            "id", "code", "title_ru", "title_uz", "title_en",
            "active", "sort_order", "created_at", "updated_at",
        }

    def test_baseline_three_specialties_seeded(self, seeded_catalog: Session):
        # (2) baseline rows
        codes = {
            row.code
            for row in seeded_catalog.execute(select(MedicalSpecialty)).scalars()
        }
        assert set(BASELINE_CODES) <= codes

    def test_seed_is_idempotent_no_duplicates(self, seeded_catalog: Session):
        # (3) repeat seeding creates no duplicates
        inserted = seed_medical_specialties(seeded_catalog.connection())
        seeded_catalog.commit()
        assert inserted == 0
        rows = seeded_catalog.execute(select(MedicalSpecialty)).scalars().all()
        assert len([r for r in rows if r.code in BASELINE_CODES]) == 3

    def test_existing_titles_not_overwritten(self, db_session: Session):
        # (4) admin-edited display titles survive reseeding
        seed_medical_specialties(db_session.connection())
        db_session.commit()
        row = db_session.execute(
            select(MedicalSpecialty).where(MedicalSpecialty.code == "cardiology")
        ).scalar_one()
        row.title_ru = "Кардиология (зимний приём)"
        db_session.commit()

        seed_medical_specialties(db_session.connection())
        db_session.commit()
        refreshed = db_session.execute(
            select(MedicalSpecialty).where(MedicalSpecialty.code == "cardiology")
        ).scalar_one()
        assert refreshed.title_ru == "Кардиология (зимний приём)"

    def test_sentinel_and_legacy_aliases_never_seeded(self, seeded_catalog: Session):
        codes = {
            row.code
            for row in seeded_catalog.execute(select(MedicalSpecialty)).scalars()
        }
        assert "general" not in codes
        assert {"dental", "stomatology", "dentist"}.isdisjoint(codes)


class TestCatalogReadLayer:
    def test_active_vocabulary_ordered(self, seeded_catalog: Session):
        # (5) active rows, sort_order then code
        rows = MedicalSpecialtyCatalogService(seeded_catalog).list_active()
        assert [r.code for r in rows] == BASELINE_CODES  # 10,20,30

    def test_inactive_excluded_from_vocabulary(self, seeded_catalog: Session):
        # (6)
        row = seeded_catalog.execute(
            select(MedicalSpecialty).where(MedicalSpecialty.code == "dermatology")
        ).scalar_one()
        row.active = False
        seeded_catalog.commit()

        codes = [r.code for r in MedicalSpecialtyCatalogService(seeded_catalog).list_active()]
        assert "dermatology" not in codes
        assert "cardiology" in codes

    def test_active_code_selectable_for_onboarding(self, seeded_catalog: Session):
        # (7) + (15) production reality: cardiology stays valid
        catalog = MedicalSpecialtyCatalogService(seeded_catalog)
        assert catalog.is_selectable_for_onboarding("cardiology") is True
        assert catalog.is_selectable_for_onboarding("dentistry") is True

    def test_inactive_code_rejected_for_onboarding(self, seeded_catalog: Session):
        # (8)
        row = seeded_catalog.execute(
            select(MedicalSpecialty).where(MedicalSpecialty.code == "dentistry")
        ).scalar_one()
        row.active = False
        seeded_catalog.commit()
        assert MedicalSpecialtyCatalogService(seeded_catalog).is_selectable_for_onboarding("dentistry") is False

    def test_unknown_code_rejected(self, seeded_catalog: Session):
        # (9)
        assert MedicalSpecialtyCatalogService(seeded_catalog).is_selectable_for_onboarding("neurology") is False

    def test_general_sentinel_rejected(self, seeded_catalog: Session):
        # (10) general is the lifecycle/recovery sentinel, never an onboarding specialty
        assert MedicalSpecialtyCatalogService(seeded_catalog).is_selectable_for_onboarding("general") is False

    def test_empty_catalog_is_explicit_configuration_failure(self, db_session: Session):
        # (14) NO hardcoded fallback: empty catalog raises
        with pytest.raises(MedicalSpecialtyCatalogError):
            MedicalSpecialtyCatalogService(db_session).list_active()


class TestActiveSemanticsNoCascade:
    def test_existing_doctor_survives_specialty_deactivation(
        self, seeded_catalog: Session, test_doctor_user
    ):
        # (11) deactivating a specialty never touches existing doctors
        doctor = Doctor(
            user_id=test_doctor_user.id,
            specialty="cardiology",
            cabinet="1",
            active=True,
        )
        seeded_catalog.add(doctor)
        seeded_catalog.commit()

        row = seeded_catalog.execute(
            select(MedicalSpecialty).where(MedicalSpecialty.code == "cardiology")
        ).scalar_one()
        row.active = False
        seeded_catalog.commit()

        seeded_catalog.refresh(doctor)
        assert doctor.active is True
        assert doctor.specialty == "cardiology"
        # and it is no longer selectable for NEW assignment
        assert MedicalSpecialtyCatalogService(seeded_catalog).is_selectable_for_onboarding("cardiology") is False


class TestDomainIndependence:
    def test_catalog_independent_of_departments_and_queue_profiles(
        self, seeded_catalog: Session
    ):
        # (12)+(13) the catalog reads only medical_specialties — no join to
        # departments/queue_profiles exists; assert the read layer works with
        # those tables empty (production reality: both are empty).
        from sqlalchemy import text

        assert seeded_catalog.execute(text("SELECT COUNT(*) FROM departments")).scalar() == 0
        assert seeded_catalog.execute(text("SELECT COUNT(*) FROM queue_profiles")).scalar() == 0
        rows = MedicalSpecialtyCatalogService(seeded_catalog).list_active()
        assert [r.code for r in rows] == BASELINE_CODES


class TestVocabularyEndpoint:
    def test_vocabulary_returns_active_catalog_with_titles(
        self, client: TestClient, auth_headers, seeded_catalog
    ):
        response = client.get(
            "/api/v1/admin/doctors/specialty-vocabulary", headers=auth_headers
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert [item["code"] for item in payload] == BASELINE_CODES
        cardiology = payload[0]
        assert cardiology["title_ru"] == "Кардиология"
        assert cardiology["title_uz"] == "Kardiologiya"
        assert cardiology["title_en"] == "Cardiology"

    def test_vocabulary_empty_catalog_returns_503_configuration_error(
        self, client: TestClient, auth_headers, db_session
    ):
        response = client.get(
            "/api/v1/admin/doctors/specialty-vocabulary", headers=auth_headers
        )
        assert response.status_code == 503
        assert "миграции" in response.json()["detail"]

    def test_vocabulary_requires_admin(self, client: TestClient, seeded_catalog):
        response = client.get("/api/v1/admin/doctors/specialty-vocabulary")
        assert response.status_code in (401, 403)
