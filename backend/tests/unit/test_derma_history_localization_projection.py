"""DERMAHIST-BE-001 (owner registry #4063; fourteenth review group) — the
canonical skin-examination history loses lesion **localization** entirely,
even for localization-only exams.

The clinical editor (``DermatologySection.tsx``) writes
``specialty_data.localization.description``; ``derma_exam_has_content``
already treats a non-empty localization dict as sufficient content to
produce a history row — but ``_emr_examination_items`` builds
``DermaExaminationHistoryOut`` WITHOUT localization, and the
``DermaExaminationOut`` schema has no such property. A localization-only
examination therefore reaches the history as a row whose displayed fields
are all blank.

Required behaviour (audit acceptance): the canonical visit localization
survives the round-trip into the history projection as a schema-safe
compatible field — only the human-readable ``description`` value is
projected (other localization dict keys must NOT leak into the API
payload), whitespace-only descriptions stay ``None``, and legacy rows
(the closed ``derma_examinations`` table has no localization column)
keep validating with ``localization=None`` without changing the
historical source marker.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from app.models.derma_examination import DermaExamination
from app.schemas.derma import DermaExaminationHistoryOut
from app.services.derma_history_projection import (
    _emr_examination_items,
    _legacy_examination_items,
    emr_entry_dicts,
)


def _record(specialty_data: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id=501,
        patient_id=17,
        visit_id=None,
        data={
            "specialty": "dermatology",
            "diagnosis": {"main": "", "secondary": []},
            "specialty_data": specialty_data,
        },
        created_at=datetime(2026, 11, 16, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 11, 16, 9, 0, tzinfo=UTC),
    )


def _examination_payload(specialty_data: dict) -> dict:
    items = _emr_examination_items([_record(specialty_data)], {})
    assert items, "локализация — достаточное содержимое: строка истории должна создаваться"
    (row, _record_id, _position) = items[0]
    return row.model_dump(mode="json")


def test_localization_only_examination_survives_round_trip() -> None:
    payload = _examination_payload({"localization": {"description": "left cheek"}})
    assert payload["source"] == "emr"
    assert payload["localization"] == "left cheek"


def test_localization_projects_description_without_leaking_other_keys() -> None:
    payload = _examination_payload(
        {
            "lesions": "папулы",
            "localization": {"description": "левая щека", "internal_tag": "SECRET-TAG"},
        }
    )
    assert payload["localization"] == "левая щека"
    assert payload["lesions"] == "папулы"
    assert "SECRET-TAG" not in str(payload)


def test_whitespace_only_description_is_an_empty_skeleton() -> None:
    # "Пустой каркас дерма-ЭМК не должен попадать в историю" — a
    # whitespace-only localization with no other content produces no row.
    dicts = emr_entry_dicts([_record({"localization": {"description": "   "}})], {})
    assert not [d for d in dicts if d["kind"] == "examination"]


def test_non_description_keys_never_fabricate_localization() -> None:
    # A row whose localization dict carries content only in OTHER keys is
    # still a history row, but the projected localization stays None —
    # nothing is fabricated into the display field.
    payload = _examination_payload(
        {"localization": {"description": "   ", "internal_tag": "SECRET-TAG"}}
    )
    assert payload["localization"] is None
    assert "SECRET-TAG" not in str(payload)


def test_legacy_row_without_column_validates_with_none() -> None:
    row = DermaExamination(
        id=3,
        patient_id=17,
        examination_date=date.today(),
        skin_type="combination",
    )
    items = _legacy_examination_items([row])
    (history_row, _record_id, _position) = items[0]
    assert isinstance(history_row, DermaExaminationHistoryOut)
    assert history_row.source == "legacy"
    assert history_row.localization is None


def test_emr_entry_dicts_carries_localization_in_read_model_payload() -> None:
    dicts = emr_entry_dicts([_record({"localization": {"description": "спина"}})], {})
    examinations = [d for d in dicts if d["kind"] == "examination"]
    assert examinations and examinations[0]["payload"]["localization"] == "спина"
