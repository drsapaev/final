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


@pytest.mark.unit
class TestDermaPhaseCWriteBoundaryPin:
    """Phase C (P3 #3490/#3491): контрактный пин одного ключа записи
    косметологических процедур дермы — specialty_data.cosmetic_procedures.
    Legacy-ключ specialty_data.procedures (эпоха #3491) на границе записи
    (normalize_emr_data, только dermatology) переносится в канонический
    ключ (append, без дедупликации — семантика Phase B normalize), сам
    ключ снимается. Другие специальности не затрагиваются."""

    @staticmethod
    def _derma_data(specialty_data: dict) -> dict:
        return {"specialty": "dermatology", "specialty_data": specialty_data}

    def test_derma_legacy_key_merged_into_canonical(self):
        legacy_entry = {
            "procedure_date": "2026-10-01",
            "procedure_type": "Пилинг",
        }
        canonical_entry = {"procedure_type": "Маска"}

        payload = normalize_emr_data(
            self._derma_data(
                {"cosmetic_procedures": [canonical_entry], "procedures": [legacy_entry]}
            )
        )

        sd = payload["specialty_data"]
        assert "procedures" not in sd
        assert sd["cosmetic_procedures"] == [canonical_entry, legacy_entry]

    def test_derma_legacy_only_becomes_canonical(self):
        legacy_entry = {"procedure_type": "Чистка"}

        payload = normalize_emr_data(self._derma_data({"procedures": [legacy_entry]}))

        sd = payload["specialty_data"]
        assert "procedures" not in sd
        assert sd["cosmetic_procedures"] == [legacy_entry]

    def test_derma_without_legacy_key_untouched(self):
        canonical_entry = {"procedure_type": "Маска"}

        payload = normalize_emr_data(
            self._derma_data({"cosmetic_procedures": [canonical_entry]})
        )

        sd = payload["specialty_data"]
        assert sd["cosmetic_procedures"] == [canonical_entry]
        assert "procedures" not in sd

    def test_non_derma_specialty_procedures_key_untouched(self):
        """У не-дерма специальностей ключ specialty_data.procedures своей
        семантики не имеет и не переносится — пин строго дерма-скоупный."""
        entry = {"procedure_type": "Что-то кардиологическое"}

        payload = normalize_emr_data(
            {"specialty": "cardiology", "specialty_data": {"procedures": [entry]}}
        )

        assert payload["specialty_data"]["procedures"] == [entry]
        assert "cosmetic_procedures" not in payload["specialty_data"]

    def test_non_list_legacy_value_key_dropped_no_crash(self):
        """Аномальный тип значения (не массив) — ключ снимается, содержимое
        не переносится, сохранение не ломается; пустой canonical-ключ НЕ
        создаётся (как и скелет специальности не создаёт пустых ключей)."""
        payload = normalize_emr_data(
            self._derma_data({"procedures": "мусорное значение"})
        )

        sd = payload["specialty_data"]
        assert "procedures" not in sd
        assert "cosmetic_procedures" not in sd

    def test_idempotent_second_normalize_no_change(self):
        legacy_entry = {"procedure_type": "Пилинг"}

        once = normalize_emr_data(self._derma_data({"procedures": [legacy_entry]}))
        twice = normalize_emr_data(once)

        assert twice == once
        assert twice["specialty_data"]["cosmetic_procedures"] == [legacy_entry]
