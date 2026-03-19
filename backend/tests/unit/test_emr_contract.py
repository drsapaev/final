from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.emr_contract import (
    canonical_emr_to_legacy_payload,
    legacy_emr_to_v2_data,
    normalize_emr_data,
    normalize_specialty,
)


@pytest.mark.unit
class TestEMRContract:
    def test_normalize_specialty_maps_aliases(self):
        assert normalize_specialty("cardio") == "cardiology"
        assert normalize_specialty("stomatology") == "dentistry"
        assert normalize_specialty("laboratory") == "lab"

    def test_normalize_emr_data_enforces_required_fields(self):
        payload = normalize_emr_data({"complaints": "Pain"}, fallback_specialty="derma")

        assert payload["specialty"] == "dermatology"
        assert isinstance(payload["specialty_data"], dict)
        assert payload["specialty_data"]["photos"] == []

    def test_legacy_payload_is_upgraded_to_v2_shape(self):
        payload = legacy_emr_to_v2_data(
            {
                "complaints": "Pain in chest",
                "anamnesis": "Started yesterday",
                "diagnosis": "I20.0",
                "icd10": "I20.0",
                "specialty": "cardio",
            }
        )

        assert payload["specialty"] == "cardiology"
        assert payload["diagnosis"]["main"] == "I20.0"
        assert payload["diagnosis"]["icd10_code"] == "I20.0"
        assert "cardio_labs" in payload["specialty_data"]

    def test_canonical_payload_can_be_adapted_to_legacy_shape(self):
        emr = SimpleNamespace(
            id=5,
            data={
                "complaints": "Rash",
                "anamnesis_morbi": "One week",
                "diagnosis": {"main": "L20.9", "icd10_code": "L20.9"},
                "recommendations": "Follow-up",
                "specialty": "dermatology",
                "specialty_data": {"photos": []},
            },
            status="signed",
            created_at=None,
            updated_at=None,
            signed_at=None,
        )

        payload = canonical_emr_to_legacy_payload(emr, appointment_id=42)

        assert payload["appointment_id"] == 42
        assert payload["complaints"] == "Rash"
        assert payload["diagnosis"] == "L20.9"
        assert payload["icd10"] == "L20.9"
        assert payload["specialty"] == "dermatology"
        assert payload["is_draft"] is False
