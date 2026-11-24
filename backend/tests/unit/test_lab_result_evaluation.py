from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.main import app
from app.models.lab import LabCatalogReferenceRange
from app.models.lab_specimen import LabSpecimen, LabSpecimenAssignment
from app.schemas.lab_reporting import LabReportValueIn
from app.services.lab_reporting._result_values import (
    age_components,
    normalize_result_value,
)
from app.services.lab_reporting_service import (
    LabReportingDomainError,
    LabReportingService,
)


@pytest.mark.parametrize(
    ("birth", "study_date", "months"),
    [
        (date(2025, 12, 1), date(2026, 11, 24), 11),
        (date(2024, 2, 29), date(2025, 2, 28), 11),
        (date(2024, 2, 29), date(2025, 3, 1), 12),
        (date(2025, 3, 31), date(2025, 4, 30), 0),
        (date(2025, 3, 31), date(2025, 5, 1), 1),
        (date(2025, 5, 1), date(2025, 5, 1), 0),
    ],
)
def test_complete_age_periods(birth, study_date, months):
    assert age_components(birth, study_date) == {
        "age_days": (study_date - birth).days,
        "age_months": months,
        "age_years": months // 12,
    }
    assert age_components(birth, None) == {
        "age_days": None,
        "age_months": None,
        "age_years": None,
    }


@pytest.mark.parametrize(
    "text", ["abc", "NaN", "infinity", "0.00001", "100000000000000", "<", "≥-Infinity"]
)
def test_numeric_values_must_fit_canonical_storage(text):
    with pytest.raises(LabReportingDomainError, match="Invalid numeric value"):
        normalize_result_value(
            {"value_text": text},
            field_key="synthetic",
            value_type="numeric",
            choice_options=None,
        )


def test_decimal_comma_and_comparator_dto():
    wire_value = LabReportValueIn(
        field_key="synthetic", value_numeric="5,2", comparator="lte"
    )
    data = normalize_result_value(
        wire_value.model_dump(),
        field_key="synthetic",
        value_type="numeric",
        choice_options=None,
    )
    assert data["value_numeric"] == Decimal("5.2")
    assert data["value_text"] == "≤5.2"
    assert data["result_payload"] == {"kind": "qualified_numeric", "comparator": "lte"}


def test_openapi_exposes_typed_result_input_and_evaluation_output():
    contract = app.openapi()
    operations = contract["paths"][
        "/api/v1/lab/report-instances/{instance_id}/bulk-values"
    ]
    request = operations["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert request["items"]["$ref"] == "#/components/schemas/LabReportValueIn"
    schemas = contract["components"]["schemas"]
    fields_in = schemas["LabReportValueIn"]["properties"]
    assert set(fields_in["result_kind"]["anyOf"][0]["enum"]) == {
        "numeric",
        "qualified_numeric",
        "coded_qualitative",
        "text",
        "absent",
    }
    fields_out = schemas["LabReportRenderedFieldOut"]["properties"]
    assert set(fields_out["evaluation_status"]["enum"]) == {
        "missing",
        "not_evaluated",
        "not_applicable",
        "evaluated",
        "unknown",
    }


def test_qualitative_and_absent_results_are_typed_without_inference_from_unknown_values():
    for text in ["Не обнаружено", "АНИҚЛАНМАДИ", "Aniqlanmadi"]:
        result = normalize_result_value(
            {"value_text": text},
            field_key="synthetic",
            value_type="text",
            choice_options=None,
        )
        assert result["result_payload"] == {
            "kind": "coded_qualitative",
            "qualitative_code": "negative",
        }
    result = normalize_result_value(
        {"result_kind": "absent", "absence_reason": "SYNTHETIC-UNPERFORMED"},
        field_key="synthetic",
        value_type="numeric",
        choice_options=None,
    )
    assert result["value_numeric"] is None
    assert result["value_text"] is None
    assert result["result_payload"] == {
        "kind": "absent",
        "absence_reason": "SYNTHETIC-UNPERFORMED",
    }


def test_draft_evaluation_requires_study_date_and_preserves_qualifiers(
    db_session, test_patient
):
    test_patient.birth_date = date(2025, 12, 1)
    db_session.commit()
    service = LabReportingService(db_session)
    template = next(
        item for item in service.list_templates() if item.code == "ige_total"
    )
    instance = service.create_instance(
        {"patient_id": test_patient.id, "template_id": template.id}
    )
    instance, _ = service.bulk_upsert_values(
        instance.id, [{"field_key": "total_ige", "value_text": "40"}]
    )
    field = service.materialize_instance(instance)[0]["fields"][0]
    assert instance.patient_snapshot["age_months"] is None
    assert field["reference_text"] == ""
    assert field["evaluation_status"] == "not_applicable"
    assert field["interpretation"] is None

    instance = service.update_instance(instance.id, {"study_date": date(2026, 11, 24)})
    field = service.materialize_instance(instance)[0]["fields"][0]
    assert instance.patient_snapshot["age_months"] == 11
    assert field["reference_text"] == "< 30 МЕ/мл"
    assert field["interpretation"] == "high"

    instance, _ = service.bulk_upsert_values(
        instance.id, [{"field_key": "total_ige", "value_text": "<0,01"}]
    )
    field = service.materialize_instance(instance)[0]["fields"][0]
    assert field["value_numeric"] == Decimal("0.01")
    assert field["value_display"] == "<0.01"
    assert field["comparator"] == "lt"
    assert field["evaluation_status"] == "not_evaluated"
    assert field["interpretation"] is None

    instance, _ = service.bulk_upsert_values(
        instance.id, [{"field_key": "total_ige", "value_text": "0"}]
    )
    field = service.materialize_instance(instance)[0]["fields"][0]
    assert field["value_display"] == "0"
    assert field["interpretation"] == "normal"


def test_legacy_negative_rule_does_not_raise_critical_for_alias_or_unknown(
    db_session, test_patient
):
    service = LabReportingService(db_session)
    template = next(
        item for item in service.list_templates() if item.code == "demodex_panel"
    )
    instance = service.create_instance(
        {"patient_id": test_patient.id, "template_id": template.id}
    )
    for text, outcome, code, flag in [
        ("Не обнаружено", "evaluated", "negative", None),
        ("ноаниқ", "not_evaluated", "indeterminate", None),
        ("SYNTHETIC-UNRECOGNIZED", "not_evaluated", None, None),
        ("aniqlandi", "evaluated", "positive", "critical"),
    ]:
        instance, _ = service.bulk_upsert_values(
            instance.id,
            [{"field_key": "demodex_folliculorum", "value_text": text}],
        )
        field = service.materialize_instance(instance)[0]["fields"][0]
        assert field["evaluation_status"] == outcome
        assert field["qualitative_code"] == code
        assert field["resolved_flag"] == flag


def test_specimen_scope_and_released_reference_are_snapshotted(
    db_session, test_patient
):
    test_patient.birth_date = date(2025, 11, 24)
    db_session.commit()
    service = LabReportingService(db_session)
    template = next(
        item for item in service.list_templates() if item.code == "glucose_panel"
    )
    specimen_range = LabCatalogReferenceRange(
        analyte_code="glucose",
        material_code="serum",
        method_code="synthetic_method",
        unit_code="mmol_per_l",
        low=Decimal("0"),
        high=Decimal("8"),
        sort_order=10,
        text="SYNTHETIC-REFERENCE",
    )
    db_session.add(specimen_range)
    db_session.commit()

    instance = service.create_instance(
        {"patient_id": test_patient.id, "template_id": template.id}
    )
    collected_at = datetime(2026, 11, 23, 20, tzinfo=UTC)
    specimen = LabSpecimen(
        order_id=instance.order_id,
        barcode="SYNTHETIC-SERUM",
        material_code="serum",
        container_code="tube",
        status="accepted",
        revision=4,
        create_request_id="SYNTHETIC-COLLECTION",
        created_at=collected_at,
        collected_at=collected_at,
    )
    db_session.add(specimen)
    db_session.flush()
    db_session.add(
        LabSpecimenAssignment(specimen_id=specimen.id, report_instance_id=instance.id)
    )
    db_session.commit()

    with pytest.raises(LabReportingDomainError, match="Unit does not match"):
        service.bulk_upsert_values(
            instance.id,
            [{"field_key": "glucose", "value_text": "6,1", "unit_code": "umol_per_l"}],
        )
    instance, _ = service.bulk_upsert_values(
        instance.id,
        [
            {
                "field_key": "glucose",
                "value_text": "6,1",
                "unit_code": "mmol_per_l",
                "method_code": "synthetic_method",
            }
        ],
    )
    assert instance.patient_snapshot["age_at_date"] == "2026-11-24"
    assert instance.patient_snapshot["age_date_source"] == "specimen_collection"
    assert instance.patient_snapshot["age_months"] == 12
    finalized = service.finalize(instance.id)
    first_field = service.materialize_instance(finalized)[0]["fields"][0]
    assert first_field["interpretation"] == "normal"
    assert first_field["reference_text"] == "SYNTHETIC-REFERENCE"
    assert (
        first_field["evaluation_snapshot"]["reference"]["reference_range_id"]
        == specimen_range.id
    )
    assert first_field["evaluation_snapshot"]["material_code"] == "serum"

    specimen_range.text = "SYNTHETIC-CHANGED-REFERENCE"
    specimen_range.high = Decimal("4")
    db_session.commit()
    next_service = LabReportingService(db_session)
    unchanged = next_service.materialize_instance(
        next_service.get_instance(finalized.id)
    )[0]["fields"][0]
    assert unchanged["evaluation_snapshot"] == first_field["evaluation_snapshot"]
    assert unchanged["reference_text"] == first_field["reference_text"]
    assert unchanged["interpretation"] == "normal"
