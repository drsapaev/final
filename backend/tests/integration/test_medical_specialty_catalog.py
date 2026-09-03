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
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.medical_specialty import MedicalSpecialty
from app.models.user import User
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
        # (14) NO hardcoded fallback: empty catalog raises. The shared engine
        # fixture seeds the baseline, so this test empties the table first.
        db_session.execute(text("DELETE FROM medical_specialties"))
        db_session.commit()
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
        db_session.execute(text("DELETE FROM medical_specialties"))
        db_session.commit()
        response = client.get(
            "/api/v1/admin/doctors/specialty-vocabulary", headers=auth_headers
        )
        assert response.status_code == 503
        assert "миграции" in response.json()["detail"]

    def test_vocabulary_requires_admin(self, client: TestClient, seeded_catalog):
        response = client.get("/api/v1/admin/doctors/specialty-vocabulary")
        assert response.status_code in (401, 403)


class TestWriteBoundaryGuards:
    """Codex P1: the catalog must be enforced where specialties are WRITTEN."""

    def _create_doctor_payload(self, test_doctor_user, specialty: str) -> dict:
        return {
            "user_id": test_doctor_user.id,
            "specialty": specialty,
            "active": True,
        }

    def test_post_doctor_rejects_unknown_specialty(
        self, client, auth_headers, seeded_catalog, test_doctor_user
    ):
        response = client.post(
            "/api/v1/admin/doctors",
            headers=auth_headers,
            json=self._create_doctor_payload(test_doctor_user, "kardio"),
        )
        assert response.status_code == 400
        assert "каталоге" in response.json()["detail"]

    def test_post_doctor_rejects_inactive_specialty(
        self, client, auth_headers, seeded_catalog, test_doctor_user
    ):
        row = seeded_catalog.execute(
            select(MedicalSpecialty).where(MedicalSpecialty.code == "dentistry")
        ).scalar_one()
        row.active = False
        seeded_catalog.commit()

        response = client.post(
            "/api/v1/admin/doctors",
            headers=auth_headers,
            json=self._create_doctor_payload(test_doctor_user, "dentistry"),
        )
        assert response.status_code == 400
        assert "деактивирована" in response.json()["detail"]

    def test_post_doctor_accepts_active_catalog_code(
        self, client, auth_headers, seeded_catalog, test_doctor_user, db_session
    ):
        response = client.post(
            "/api/v1/admin/doctors",
            headers=auth_headers,
            json=self._create_doctor_payload(test_doctor_user, "cardiology"),
        )
        assert response.status_code == 200, response.text
        # cleanup the created row so other tests stay isolated
        created = response.json()
        if created.get("id"):
            from sqlalchemy import delete as _delete

            db_session.execute(_delete(Doctor).where(Doctor.id == created["id"]))
            db_session.commit()

    def test_put_doctor_changing_to_unknown_specialty_rejected(
        self, client, auth_headers, seeded_catalog, db_session, test_doctor_user
    ):
        doctor = Doctor(user_id=test_doctor_user.id, specialty="cardiology", active=True)
        seeded_catalog.add(doctor)
        seeded_catalog.commit()

        response = client.put(
            f"/api/v1/admin/doctors/{doctor.id}",
            headers=auth_headers,
            json={"specialty": "stomatolog"},
        )
        assert response.status_code == 400

    def test_put_doctor_without_specialty_untouched(
        self, client, auth_headers, seeded_catalog, test_doctor_user
    ):
        """Editing other fields must not re-validate the stored specialty."""
        doctor = Doctor(user_id=test_doctor_user.id, specialty="cardiology", cabinet="1", active=True)
        seeded_catalog.add(doctor)
        seeded_catalog.commit()

        response = client.put(
            f"/api/v1/admin/doctors/{doctor.id}",
            headers=auth_headers,
            json={"cabinet": "42"},
        )
        assert response.status_code == 200, response.text
        seeded_catalog.refresh(doctor)
        assert doctor.cabinet == "42"
        assert doctor.specialty == "cardiology"


class TestMissingTableConfigurationFailure:
    """Codex P2: a rollout ahead of migration 0051 must yield the documented
    503, not a generic 500 from the raw driver error."""

    def test_missing_table_returns_503(
        self, client, auth_headers, db_session
    ):
        from sqlalchemy import text as _text

        db_session.commit()  # release pending state before DDL
        db_session.execute(_text("DROP TABLE medical_specialties"))
        db_session.commit()

        response = client.get(
            "/api/v1/admin/doctors/specialty-vocabulary", headers=auth_headers
        )
        assert response.status_code == 503
        assert "0051" in response.json()["detail"] or "миграции" in response.json()["detail"]


class TestVocabularyTypedContract:
    """Codex P2: typed DTO instead of arbitrary maps in OpenAPI/TS."""

    def test_openapi_publishes_typed_item_schema(self):
        import json as _json
        from pathlib import Path as _Path

        spec = _json.loads(
            (_Path(__file__).resolve().parents[2] / "openapi.json").read_text(
                encoding="utf-8"
            )
        )
        schemas = spec["components"]["schemas"]
        assert "SpecialtyVocabularyItem" in schemas
        props = schemas["SpecialtyVocabularyItem"]["properties"]
        for key in ("code", "title_ru", "title_uz", "title_en"):
            assert key in props
        assert "code" in schemas["SpecialtyVocabularyItem"].get("required", [])
        assert "title_ru" in schemas["SpecialtyVocabularyItem"].get("required", [])

    def test_openapi_typed_503_on_all_catalog_affected_operations(self):
        """Codex round-6 P2: the documented 503 (catalog not configured) is
        declared with a SHARED error-body model on GET specialty-vocabulary,
        POST /admin/doctors and PUT /admin/doctors/{doctor_id} — generated
        clients type the error shape instead of `content?: never`."""
        import json as _json
        from pathlib import Path as _Path

        spec = _json.loads(
            (_Path(__file__).resolve().parents[2] / "openapi.json").read_text(
                encoding="utf-8"
            )
        )
        schemas = spec["components"]["schemas"]
        assert "ServiceUnavailableDetail" in schemas
        assert schemas["ServiceUnavailableDetail"]["required"] == ["detail"]
        ref = "#/components/schemas/ServiceUnavailableDetail"
        for path, method in (
            ("/api/v1/admin/doctors/specialty-vocabulary", "get"),
            ("/api/v1/admin/doctors", "post"),
            ("/api/v1/admin/doctors/{doctor_id}", "put"),
        ):
            declared = spec["paths"][path][method]["responses"]["503"]
            schema = declared["content"]["application/json"]["schema"]
            assert schema["$ref"] == ref, (path, method)


class TestBlankSpecialtyGuard:
    """Codex P2 round 2: specialty:'' must not bypass the catalog guard."""

    def test_post_doctor_blank_specialty_rejected(
        self, client, auth_headers, seeded_catalog, test_doctor_user
    ):
        response = client.post(
            "/api/v1/admin/doctors",
            headers=auth_headers,
            json={
                "user_id": test_doctor_user.id,
                "specialty": "   ",
                "active": True,
            },
        )
        assert response.status_code == 400
        assert "пустой" in response.json()["detail"]


class TestCodexRound3:
    def test_put_with_unchanged_historical_specialty_allows_other_edits(
        self, client, auth_headers, seeded_catalog, test_doctor_user
    ):
        """Unchanged (now-deactivated) historical specialty must not block
        unrelated edits — no-cascade contract (Codex P2 round 3)."""
        doctor = Doctor(user_id=test_doctor_user.id, specialty="cardiology", cabinet="1", active=True)
        seeded_catalog.add(doctor)
        seeded_catalog.commit()
        row = seeded_catalog.execute(
            select(MedicalSpecialty).where(MedicalSpecialty.code == "cardiology")
        ).scalar_one()
        row.active = False
        seeded_catalog.commit()

        # UI resubmits the same specialty while editing the cabinet
        response = client.put(
            f"/api/v1/admin/doctors/{doctor.id}",
            headers=auth_headers,
            json={"specialty": "cardiology", "cabinet": "77"},
        )
        assert response.status_code == 200, response.text
        seeded_catalog.refresh(doctor)
        assert doctor.cabinet == "77"

    def test_put_changing_to_deactivated_still_rejected(
        self, client, auth_headers, seeded_catalog, test_doctor_user
    ):
        doctor = Doctor(user_id=test_doctor_user.id, specialty="cardiology", cabinet="1", active=True)
        seeded_catalog.add(doctor)
        seeded_catalog.commit()
        row = seeded_catalog.execute(
            select(MedicalSpecialty).where(MedicalSpecialty.code == "dentistry")
        ).scalar_one()
        row.active = False
        seeded_catalog.commit()

        response = client.put(
            f"/api/v1/admin/doctors/{doctor.id}",
            headers=auth_headers,
            json={"specialty": "dentistry"},
        )
        assert response.status_code == 400

    def test_write_path_empty_catalog_is_503_not_400(
        self, client, auth_headers, db_session, test_doctor_user
    ):
        """Empty catalog is a configuration failure: POST must give 503,
        not a misleading per-code 400 (Codex P2 round 3)."""
        db_session.execute(text("DELETE FROM medical_specialties"))
        db_session.commit()
        response = client.post(
            "/api/v1/admin/doctors",
            headers=auth_headers,
            json={"user_id": test_doctor_user.id, "specialty": "cardiology", "active": True},
        )
        assert response.status_code == 503

    def test_write_path_missing_table_is_503(
        self, client, auth_headers, db_session, test_doctor_user
    ):
        db_session.commit()
        db_session.execute(text("DROP TABLE medical_specialties"))
        db_session.commit()
        response = client.post(
            "/api/v1/admin/doctors",
            headers=auth_headers,
            json={"user_id": test_doctor_user.id, "specialty": "cardiology", "active": True},
        )
        assert response.status_code == 503


class TestUserRoleProvisioningCatalogGuard:
    """Codex round-6 P1: legacy doctor-role auto-provisioning (POST /users
    with role cardio/derma/dentist) respects the runtime catalog — a
    DEACTIVATED specialty must not receive a fresh ACTIVE doctor profile;
    the provisioning downgrades to the incomplete sentinel and the admin
    assigns a real specialty through the validated boundary."""

    def _create_role_user(self, client, auth_headers, role: str) -> dict:
        import uuid as _uuid

        suffix = _uuid.uuid4().hex[:8]
        response = client.post(
            "/api/v1/users/users",
            headers=auth_headers,
            json={
                "username": f"r6-{role}-{suffix}",
                "email": f"r6-{role}-{suffix}@example.com",
                "password": "StrongPass123",
                "role": role,
            },
        )
        assert response.status_code == 200, response.text
        return response.json()

    def _cleanup_user(self, db_session: Session, user_id: int) -> None:
        from app.models.user import User
        from app.models.user_profile import UserAuditLog

        doctor = db_session.query(Doctor).filter(Doctor.user_id == user_id).first()
        if doctor:
            db_session.delete(doctor)
        audit = db_session.query(UserAuditLog).filter(
            UserAuditLog.user_id == user_id
        )
        for row in audit:
            db_session.delete(row)
        user = db_session.query(User).filter(User.id == user_id).first()
        if user:
            db_session.delete(user)
        db_session.commit()

    def test_active_catalog_specialty_keeps_historical_mapping(
        self, client, auth_headers, seeded_catalog, db_session
    ):
        payload = self._create_role_user(client, auth_headers, "derma")
        try:
            doctor = (
                db_session.query(Doctor)
                .filter(Doctor.user_id == payload["id"])
                .first()
            )
            assert doctor is not None
            assert doctor.specialty == "dermatology"
        finally:
            self._cleanup_user(db_session, payload["id"])

    def test_deactivated_catalog_specialty_downgrades_provisioning(
        self, client, auth_headers, seeded_catalog, db_session
    ):
        row = (
            db_session.query(MedicalSpecialty)
            .filter(MedicalSpecialty.code == "dermatology")
            .first()
        )
        assert row is not None
        row.active = False
        db_session.commit()
        try:
            payload = self._create_role_user(client, auth_headers, "derma")
            try:
                doctor = (
                    db_session.query(Doctor)
                    .filter(Doctor.user_id == payload["id"])
                    .first()
                )
                assert doctor is not None
                # the deactivated catalog specialty is NOT provisioned as a
                # fresh active profile — the incomplete sentinel requires
                # assignment through the validated boundary instead
                assert doctor.specialty == "general"
            finally:
                self._cleanup_user(db_session, payload["id"])
        finally:
            row.active = True
            db_session.commit()


class TestActivationLoopholeFollowUp:
    """Round-6 follow-up: activating an inactive profile with an unchanged
    non-assignable specialty (sentinel or deactivated code) is a NEW
    assignment and must pass the catalog."""

    def test_activating_sentinel_profile_with_unchanged_specialty_rejected(
        self, client, auth_headers, seeded_catalog, test_doctor_user
    ):
        doctor = Doctor(
            user_id=test_doctor_user.id,
            specialty="general",  # incomplete sentinel (never in catalog)
            active=False,
        )
        seeded_catalog.add(doctor)
        seeded_catalog.commit()

        response = client.put(
            f"/api/v1/admin/doctors/{doctor.id}",
            headers=auth_headers,
            json={"specialty": "general", "active": True},
        )
        assert response.status_code == 400

    def test_activating_with_active_catalog_code_succeeds(
        self, client, auth_headers, seeded_catalog, test_doctor_user
    ):
        doctor = Doctor(
            user_id=test_doctor_user.id, specialty="cardiology", active=False
        )
        seeded_catalog.add(doctor)
        seeded_catalog.commit()

        response = client.put(
            f"/api/v1/admin/doctors/{doctor.id}",
            headers=auth_headers,
            json={"specialty": "cardiology", "active": True},
        )
        assert response.status_code == 200, response.text


class TestRoleChangePromotionGuard:
    """Codex #3010 follow-up P1: the role-change lifecycle
    (PUT /users/users/{id}) is the SHARED doctor-provisioning path —
    fresh inserts and reactivations must respect the catalog SSOT exactly
    like the POST /users auto-map, so a deactivated specialty can never be
    carried into an ACTIVE doctor profile."""

    def _make_registrar_with_inactive_profile(
        self, seeded_catalog, specialty: str
    ):
        from app.core.security import get_password_hash
        from app.models.user import User

        user = User(
            username=f"promo_{specialty}_{id(self) % 100000}",
            email=f"promo-{specialty}-{id(self) % 100000}@test.com",
            full_name="Promotion Guard",
            hashed_password=get_password_hash("secret123"),
            role="Registrar",
            is_active=True,
        )
        seeded_catalog.add(user)
        seeded_catalog.commit()
        seeded_catalog.refresh(user)

        doctor = Doctor(
            user_id=user.id, specialty=specialty, active=False
        )
        seeded_catalog.add(doctor)
        seeded_catalog.commit()
        seeded_catalog.refresh(doctor)
        return user, doctor

    def _deactivate(self, seeded_catalog, code: str):
        row = (
            seeded_catalog.query(MedicalSpecialty)
            .filter(MedicalSpecialty.code == code)
            .first()
        )
        row.active = False
        seeded_catalog.commit()
        return row

    def test_promotion_to_legacy_role_with_deactivated_specialty_provisions_sentinel(
        self, client, auth_headers, seeded_catalog, db_session
    ):
        row = self._deactivate(seeded_catalog, "dermatology")
        try:
            user = User(
                username="promo_derma_downgrade",
                email="promo-derma-downgrade@test.com",
                full_name="Promotion Downgrade",
                hashed_password="x",
                role="Registrar",
                is_active=True,
            )
            seeded_catalog.add(user)
            seeded_catalog.commit()
            seeded_catalog.refresh(user)

            response = client.put(
                f"/api/v1/users/users/{user.id}",
                json={"role": "derma"},
                headers=auth_headers,
            )
            assert response.status_code == 200, response.text

            doctor = (
                db_session.query(Doctor)
                .filter(Doctor.user_id == user.id)
                .first()
            )
            assert doctor is not None
            # the deactivated mapped code is NOT provisioned as a fresh
            # active profile — the incomplete sentinel requires assignment
            # through the validated /admin/doctors boundary
            assert doctor.specialty == "general"
        finally:
            row.active = True
            seeded_catalog.commit()

    def test_promotion_to_legacy_role_with_active_specialty_keeps_mapping(
        self, client, auth_headers, seeded_catalog, db_session
    ):
        user = User(
            username="promo_derma_active",
            email="promo-derma-active@test.com",
            full_name="Promotion Active",
            hashed_password="x",
            role="Registrar",
            is_active=True,
        )
        seeded_catalog.add(user)
        seeded_catalog.commit()
        seeded_catalog.refresh(user)

        response = client.put(
            f"/api/v1/users/users/{user.id}",
            json={"role": "derma"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        doctor = (
            db_session.query(Doctor)
            .filter(Doctor.user_id == user.id)
            .first()
        )
        assert doctor is not None
        assert doctor.specialty == "dermatology"
        assert doctor.active is True

    def test_reactivation_with_deactivated_stored_specialty_rejects_role_change(
        self, client, auth_headers, seeded_catalog, db_session
    ):
        user, doctor = self._make_registrar_with_inactive_profile(
            seeded_catalog, "dermatology"
        )
        row = self._deactivate(seeded_catalog, "dermatology")
        try:
            response = client.put(
                f"/api/v1/users/users/{user.id}",
                json={"role": "derma"},
                headers=auth_headers,
            )
            # the role change is rejected with the remediation message —
            # nothing is activated, the stored specialty is untouched
            assert response.status_code == 400, response.text
            assert "недоступную в каталоге" in response.json()["detail"]
            db_session.expire_all()
            stored = (
                db_session.query(Doctor)
                .filter(Doctor.id == doctor.id)
                .one()
            )
            assert stored.active is False
            assert stored.specialty == "dermatology"
        finally:
            row.active = True
            seeded_catalog.commit()

    def test_reactivation_with_sentinel_stored_specialty_succeeds(
        self, client, auth_headers, seeded_catalog, db_session
    ):
        # promote -> demote -> promote cycle: a mechanically provisioned
        # 'general' profile stays reactivatable (not bookable, excluded
        # from active-only selectors, so no catalog danger)
        user, doctor = self._make_registrar_with_inactive_profile(
            seeded_catalog, "general"
        )
        response = client.put(
            f"/api/v1/users/users/{user.id}",
            json={"role": "Doctor"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        db_session.expire_all()
        reactivated = (
            db_session.query(Doctor).filter(Doctor.id == doctor.id).one()
        )
        assert reactivated.active is True
        assert reactivated.specialty == "general"

    def test_activation_only_payload_with_deactivated_stored_specialty_rejected(
        self, client, auth_headers, seeded_catalog, db_session, test_doctor_user
    ):
        # Codex #3010 round-6 P1: {"active": true} WITHOUT a specialty in
        # the payload must not bypass the catalog gate
        doctor = Doctor(
            user_id=test_doctor_user.id,
            specialty="dermatology",
            active=False,
        )
        seeded_catalog.add(doctor)
        seeded_catalog.commit()
        row = self._deactivate(seeded_catalog, "dermatology")
        try:
            response = client.put(
                f"/api/v1/admin/doctors/{doctor.id}",
                headers=auth_headers,
                json={"active": True},
            )
            assert response.status_code == 400, response.text
            db_session.expire_all()
            stored = (
                db_session.query(Doctor)
                .filter(Doctor.id == doctor.id)
                .one()
            )
            assert stored.active is False
        finally:
            row.active = True
            seeded_catalog.commit()

    def test_activation_only_payload_with_sentinel_rejected(
        self, client, auth_headers, seeded_catalog, test_doctor_user
    ):
        doctor = Doctor(
            user_id=test_doctor_user.id,
            specialty="general",
            active=False,
        )
        seeded_catalog.add(doctor)
        seeded_catalog.commit()

        response = client.put(
            f"/api/v1/admin/doctors/{doctor.id}",
            headers=auth_headers,
            json={"active": True},
        )
        assert response.status_code == 400, response.text

    def test_activation_only_payload_with_active_catalog_code_succeeds(
        self, client, auth_headers, seeded_catalog, test_doctor_user
    ):
        doctor = Doctor(
            user_id=test_doctor_user.id, specialty="cardiology", active=False
        )
        seeded_catalog.add(doctor)
        seeded_catalog.commit()

        response = client.put(
            f"/api/v1/admin/doctors/{doctor.id}",
            headers=auth_headers,
            json={"active": True},
        )
        assert response.status_code == 200, response.text


class TestRoleActivationRaceAndCatalogPropagation:
    """Codex #3031 round-1: the is_active mirror (_sync_doctor_active) runs
    BEFORE the role-change lifecycle — a simultaneous {"role": "derma",
    "is_active": true} on an inactive user activates the stored profile
    first, so the promotion guard must validate whenever the user is active,
    not only when the lifecycle itself performs the reactivation. An UNUSABLE
    catalog must propagate as a configuration error, not the generic 400."""

    def test_simultaneous_role_and_activation_validates_stored_specialty(
        self, client, auth_headers, seeded_catalog, db_session
    ):
        # codex's exact scenario: INACTIVE non-doctor user with an inactive
        # Doctor row is updated in ONE request with both role and is_active
        from app.core.security import get_password_hash

        user = User(
            username="promo_race_derma",
            email="promo-race-derma@test.com",
            full_name="Race Guard",
            hashed_password=get_password_hash("secret123"),
            role="Registrar",
            is_active=False,
        )
        seeded_catalog.add(user)
        seeded_catalog.commit()
        seeded_catalog.refresh(user)
        doctor = Doctor(user_id=user.id, specialty="dermatology", active=False)
        seeded_catalog.add(doctor)
        seeded_catalog.commit()
        seeded_catalog.refresh(doctor)

        row = TestRoleChangePromotionGuard()._deactivate(seeded_catalog, "dermatology")
        try:
            response = client.put(
                f"/api/v1/users/users/{user.id}",
                json={"role": "derma", "is_active": True},
                headers=auth_headers,
            )
            assert response.status_code == 400, response.text
            assert "недоступную в каталоге" in response.json()["detail"]
            db_session.expire_all()
            stored = db_session.query(Doctor).filter(Doctor.id == doctor.id).one()
            # the earlier _sync_doctor_active activation is rolled back —
            # the profile stays inactive and the owner keeps the old role
            assert stored.active is False
            assert stored.specialty == "dermatology"
            owner = db_session.query(User).filter(User.id == user.id).one()
            assert owner.role == "Registrar"
            assert owner.is_active is False
        finally:
            row.active = True
            seeded_catalog.commit()

    def test_simultaneous_role_and_activation_with_sentinel_succeeds(
        self, client, auth_headers, seeded_catalog, db_session
    ):
        user, doctor = TestRoleChangePromotionGuard()._make_registrar_with_inactive_profile(
            seeded_catalog, "general"
        )
        response = client.put(
            f"/api/v1/users/users/{user.id}",
            json={"role": "Doctor", "is_active": True},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        db_session.expire_all()
        reactivated = db_session.query(Doctor).filter(Doctor.id == doctor.id).one()
        assert reactivated.active is True
        assert reactivated.specialty == "general"

    def test_catalog_unavailable_propagates_as_configuration_error(
        self, client, auth_headers, seeded_catalog, db_session, monkeypatch
    ):
        from app.services.medical_specialty_catalog import (
            MedicalSpecialtyCatalogError,
            MedicalSpecialtyCatalogService,
        )

        def _raise(self, code):
            raise MedicalSpecialtyCatalogError("catalog probe failed")

        monkeypatch.setattr(
            MedicalSpecialtyCatalogService,
            "is_selectable_for_onboarding",
            _raise,
        )
        user, doctor = TestRoleChangePromotionGuard()._make_registrar_with_inactive_profile(
            seeded_catalog, "dermatology"
        )
        response = client.put(
            f"/api/v1/users/users/{user.id}",
            json={"role": "Doctor"},
            headers=auth_headers,
        )
        # the configuration failure surfaces with the SAME remediation
        # message the POST /users catalog boundary documents — not the
        # generic "Внутренняя ошибка"
        assert response.status_code == 400, response.text
        assert "не настроен" in response.json()["detail"]
