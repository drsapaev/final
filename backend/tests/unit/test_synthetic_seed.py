"""Unit tests for app.synthetic_seed.

Covers:
- Safety checks (refuses prod DB names, requires confirm flag)
- Patient generator (realistic data, SYNTHETIC- prefix)
- Visit generator (specialty-specific complaints + ICD-10)
- Data pool sanity (all specialties have complaints + ICD-10)

Does NOT cover actual DB insertion — that requires integration tests.
"""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest

from app.synthetic_seed import (
    COMPLAINTS_BY_SPECIALTY,
    ICD10_BY_SPECIALTY,
    PROTECTED_DB_NAMES,
    SYNTHETIC_PREFIX,
    SyntheticSeedSafetyError,
    _check_db_safety,
    _generate_patient,
    _generate_visit,
    _random_birth_date,
    _random_passport,
    _random_phone,
)


# ---------------------------------------------------------------------------
# Safety checks
# ---------------------------------------------------------------------------


class TestCheckDbSafety:
    def test_refuses_protected_prod_names(self):
        for protected in PROTECTED_DB_NAMES:
            url = f"postgresql://user:pass@host:5432/{protected}"
            with pytest.raises(SyntheticSeedSafetyError, match="protected name"):
                _check_db_safety(url)

    def test_refuses_db_without_dev_marker(self):
        # DB name 'clinic' is in PROTECTED, but also any name without dev/staging/test marker
        url = "postgresql://user:pass@host:5432/randomname"
        with pytest.raises(SyntheticSeedSafetyError, match="does not contain"):
            _check_db_safety(url)

    def test_accepts_staging_db(self):
        url = "postgresql://user:pass@host:5432/clinic_staging"
        _check_db_safety(url)  # should not raise

    def test_accepts_dev_db(self):
        url = "postgresql://user:pass@host:5432/clinic_dev"
        _check_db_safety(url)

    def test_accepts_test_db(self):
        url = "postgresql://user:pass@host:5432/test_clinic"
        _check_db_safety(url)

    def test_accepts_synthetic_db(self):
        url = "postgresql://user:pass@host:5432/synthetic_data"
        _check_db_safety(url)

    def test_accepts_sandbox_db(self):
        url = "postgresql://user:pass@host:5432/clinic_sandbox"
        _check_db_safety(url)

    def test_refuses_db_with_prod_in_name(self):
        # Note: this would also fail the dev-marker check, but prod check is first
        url = "postgresql://user:pass@host:5432/clinic_prod"
        with pytest.raises(SyntheticSeedSafetyError):
            _check_db_safety(url)


# ---------------------------------------------------------------------------
# Generators — patient
# ---------------------------------------------------------------------------


class TestGeneratePatient:
    def test_has_synthetic_prefix_in_last_name(self):
        for _ in range(20):  # test multiple random generations
            patient = _generate_patient()
            assert patient["last_name"].startswith(SYNTHETIC_PREFIX), \
                f"last_name {patient['last_name']!r} missing SYNTHETIC- prefix"

    def test_first_name_has_no_synthetic_prefix(self):
        # first_name should be a real name, not SYNTHETIC-prefixed
        patient = _generate_patient()
        assert not patient["first_name"].startswith(SYNTHETIC_PREFIX)

    def test_sex_is_M_or_F(self):
        for _ in range(20):
            patient = _generate_patient()
            assert patient["sex"] in ("M", "F")

    def test_birth_date_is_in_past(self):
        from datetime import date
        patient = _generate_patient()
        assert patient["birth_date"] < date.today()

    def test_birth_date_is_adult(self):
        from datetime import date
        for _ in range(20):
            patient = _generate_patient()
            age_days = (date.today() - patient["birth_date"]).days
            assert age_days >= 365 * 18, f"Patient is {age_days / 365:.1f} years old, expected >=18"

    def test_birth_date_is_not_extremely_old(self):
        from datetime import date
        for _ in range(20):
            patient = _generate_patient()
            age_days = (date.today() - patient["birth_date"]).days
            assert age_days <= 365 * 85, f"Patient is {age_days / 365:.1f} years old, expected <=85"

    def test_phone_is_uz_format(self):
        for _ in range(20):
            phone = _generate_patient()["phone"]
            assert phone.startswith("+998"), f"Phone {phone!r} not Uzbek format"
            assert len(phone) == 13, f"Phone {phone!r} wrong length"

    def test_passport_has_two_letter_prefix(self):
        for _ in range(20):
            passport = _generate_patient()["doc_number"]
            assert re.match(r"^[A-Z]{2}\d{7}$", passport), \
                f"Passport {passport!r} doesn't match AB1234567 pattern"

    def test_doc_type_is_uzbek_passport(self):
        patient = _generate_patient()
        assert patient["doc_type"] == "passport_uz"

    def test_address_mentions_tashkent(self):
        for _ in range(20):
            address = _generate_patient()["address"]
            assert "Ташкент" in address, f"Address {address!r} doesn't mention Tashkent"

    def test_is_deleted_is_false(self):
        patient = _generate_patient()
        assert patient["is_deleted"] is False

    def test_created_at_is_in_past_year(self):
        from datetime import datetime, timedelta
        patient = _generate_patient()
        assert patient["created_at"] < datetime.utcnow()
        assert patient["created_at"] > datetime.utcnow() - timedelta(days=366)

    def test_email_is_none(self):
        patient = _generate_patient()
        assert patient["email"] is None

    def test_returns_all_required_fields(self):
        patient = _generate_patient()
        required = {
            "last_name", "first_name", "middle_name",
            "birth_date", "sex", "phone", "email",
            "doc_type", "doc_number", "address",
            "is_deleted", "created_at",
        }
        assert required.issubset(patient.keys()), \
            f"Missing fields: {required - patient.keys()}"


# ---------------------------------------------------------------------------
# Generators — visit
# ---------------------------------------------------------------------------


class TestGenerateVisit:
    def test_visit_has_patient_id(self):
        visit = _generate_visit(patient_id=42, specialty="cardiology")
        assert visit["patient_id"] == 42

    def test_visit_has_specialty_complaint(self):
        visit = _generate_visit(patient_id=1, specialty="cardiology")
        assert visit["complaints"] in COMPLAINTS_BY_SPECIALTY["cardiology"]

    def test_visit_has_specialty_icd10(self):
        visit = _generate_visit(patient_id=1, specialty="dermatology")
        assert visit["icd10_code"] in ICD10_BY_SPECIALTY["dermatology"]

    def test_visit_date_is_in_last_90_days(self):
        from datetime import datetime, timedelta
        for _ in range(20):
            visit = _generate_visit(patient_id=1, specialty="cardiology")
            assert visit["visit_date"] < datetime.utcnow()
            assert visit["visit_date"] > datetime.utcnow() - timedelta(days=91)

    def test_visit_status_is_valid(self):
        for _ in range(20):
            visit = _generate_visit(patient_id=1, specialty="cardiology")
            assert visit["status"] in ("completed", "scheduled", "cancelled")

    def test_completed_is_most_common_status(self):
        # Run many times — completed should be most common
        from collections import Counter
        statuses = Counter()
        for _ in range(100):
            visit = _generate_visit(patient_id=1, specialty="cardiology")
            statuses[visit["status"]] += 1
        # completed appears 3x in the choices vs 1 each for scheduled/cancelled
        assert statuses["completed"] > statuses["scheduled"]
        assert statuses["completed"] > statuses["cancelled"]


# ---------------------------------------------------------------------------
# Data pool sanity
# ---------------------------------------------------------------------------


class TestDataPools:
    def test_all_specialties_have_complaints(self):
        for specialty, complaints in COMPLAINTS_BY_SPECIALTY.items():
            assert len(complaints) >= 3, \
                f"Specialty {specialty!r} has only {len(complaints)} complaints, need >=3"
            for c in complaints:
                assert isinstance(c, str) and len(c) > 5

    def test_all_specialties_have_icd10_codes(self):
        for specialty, codes in ICD10_BY_SPECIALTY.items():
            assert len(codes) >= 3, \
                f"Specialty {specialty!r} has only {len(codes)} ICD-10 codes, need >=3"

    def test_specialties_match_between_complaints_and_icd10(self):
        assert set(COMPLAINTS_BY_SPECIALTY.keys()) == set(ICD10_BY_SPECIALTY.keys())

    def test_icd10_codes_look_valid(self):
        # ICD-10 codes start with a letter + 2 digits, optional .X
        for specialty, codes in ICD10_BY_SPECIALTY.items():
            for code in codes:
                assert re.match(r"^[A-Z]\d{2}(\.\d+)?$", code), \
                    f"ICD-10 code {code!r} in {specialty!r} doesn't look valid"


# ---------------------------------------------------------------------------
# CLI argument parsing (just verify --confirm-synthetic-seed is required)
# ---------------------------------------------------------------------------


class TestCliEntryPoint:
    def test_returns_2_when_no_confirm_flag(self, capsys):
        from app.synthetic_seed import main
        result = main(["--count-patients", "10"])
        assert result == 2
        captured = capsys.readouterr()
        assert "confirm-synthetic-seed" in captured.err

    def test_returns_2_when_no_database_url(self, capsys, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        from app.synthetic_seed import main
        result = main(["--count-patients", "10", "--confirm-synthetic-seed"])
        assert result == 2

    def test_cleanup_only_does_not_require_confirm_flag(self, monkeypatch):
        # --cleanup-only skips the confirm check
        monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h:5432/test_db")
        monkeypatch.setattr("app.synthetic_seed.cleanup_synthetic", lambda db: {"patients": 0, "visits": 0})
        from app.synthetic_seed import main
        # Should NOT return 2 (no confirm flag needed)
        result = main(["--cleanup-only"])
        assert result == 0
