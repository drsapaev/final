from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services.lab_import_adapters import (
    ANALYZER_ADAPTERS,
    ASTMCLSIAdapter,
    AnalyzerAdapterError,
    AnalyzerAdapterRegistry,
    AnalyzerMappingProfile,
    HL7V2ORUAdapter,
    to_lab_import_row,
)


HL7_SYNTHETIC = (
    "MSH|^~\\&|SYNTHETIC-ANALYZER|SYNTHETIC-LAB|FC|SYNTHETIC-LAB|"
    "202611271200||ORU^R01|SYNTHETIC-HL7-1|P|2.5.1\r"
    "PID|1||SYNTHETIC-PATIENT-DO-NOT-READ||Synthetic^Patient\r"
    "OBR|1|SYNTHETIC-PLACER-1|SYNTHETIC-ACCESSION-1\r"
    "SPM|1|SYNTHETIC-SPECIMEN-1\r"
    "OBX|1|NM|GLU^Glucose^99SYNTHETIC||4.2|mmol/L||H||F\r"
)

ASTM_SYNTHETIC = (
    "H|\\^&|||SYNTHETIC-ANALYZER||||||SYNTHETIC-ASTM-1\r"
    "P|1||SYNTHETIC-PATIENT-DO-NOT-READ\r"
    "O|1|SYNTHETIC-SPECIMEN-2|SYNTHETIC-ACCESSION-2|^^^GLU|R\r"
    "R|1|^^^GLU|4.2|mmol/L|3.9-6.1|H||F\r"
    "L|1|N\r"
)


def _mapping() -> AnalyzerMappingProfile:
    return AnalyzerMappingProfile(
        analyte_codes={"GLU": "glucose"},
        unit_codes={("GLU", "mmol/L"): "mmol_l"},
        flag_codes={"H": "HIGH"},
    )


@pytest.mark.unit
def test_registry_exposes_standard_protocols_and_allows_vendor_extension():
    assert ANALYZER_ADAPTERS.keys() == ("astm_clsi", "hl7_v2")

    @dataclass
    class VendorAdapter:
        adapter_key: str = "vendor:clinic-neutral"

        def parse(self, payload):
            raise NotImplementedError

    registry = AnalyzerAdapterRegistry()
    registry.register(VendorAdapter())
    assert registry.get("VENDOR:CLINIC-NEUTRAL").adapter_key == "vendor:clinic-neutral"
    with pytest.raises(ValueError, match="adapter_key_must_be_unique"):
        registry.register(VendorAdapter())


@pytest.mark.unit
def test_hl7_v2_extracts_order_specimen_observation_and_ignores_pid():
    parsed = HL7V2ORUAdapter().parse(HL7_SYNTHETIC)

    assert parsed.adapter_key == "hl7_v2"
    assert parsed.accession_id == "SYNTHETIC-ACCESSION-1"
    assert parsed.specimen_id == "SYNTHETIC-SPECIMEN-1"
    assert parsed.observations[0].source_analyte_code == "GLU"
    assert parsed.observations[0].raw_value == "4.2"
    assert parsed.observations[0].source_unit_code == "mmol/L"
    assert parsed.observations[0].instrument_flags == ("H",)
    assert "SYNTHETIC-PATIENT-DO-NOT-READ" not in repr(parsed)


@pytest.mark.unit
def test_astm_clsi_extracts_one_order_and_result_without_patient_record_data():
    parsed = ASTMCLSIAdapter().parse(ASTM_SYNTHETIC.encode())

    assert parsed.adapter_key == "astm_clsi"
    assert parsed.accession_id == "SYNTHETIC-ACCESSION-2"
    assert parsed.specimen_id == "SYNTHETIC-SPECIMEN-2"
    assert parsed.observations[0].source_analyte_code == "GLU"
    assert parsed.observations[0].raw_value == "4.2"
    assert parsed.observations[0].source_unit_code == "mmol/L"
    assert parsed.observations[0].instrument_flags == ("H",)
    assert "SYNTHETIC-PATIENT-DO-NOT-READ" not in repr(parsed)


@pytest.mark.unit
def test_canonical_import_row_requires_exact_profile_mapping_and_keeps_source_flag():
    parsed = HL7V2ORUAdapter().parse(HL7_SYNTHETIC)
    row = to_lab_import_row(
        parsed,
        _mapping(),
        report_instance_id=37,
        method_code="clinic-approved-method",
    )

    assert row.report_instance_id == 37
    assert row.specimen_barcode == "SYNTHETIC-SPECIMEN-1"
    assert row.message_id == to_lab_import_row(
        parsed, _mapping(), report_instance_id=37
    ).message_id
    assert row.values[0].field_key == "glucose"
    assert row.values[0].unit_code == "mmol_l"
    assert row.values[0].value_text == "4.2"
    assert row.values[0].instrument_flags == ["HIGH"]
    assert row.values[0].method_code == "clinic-approved-method"


@pytest.mark.unit
def test_mapping_profile_selects_only_the_configured_specimen_or_accession_identifier():
    parsed = HL7V2ORUAdapter().parse(HL7_SYNTHETIC)
    mapping = AnalyzerMappingProfile(
        analyte_codes={"GLU": "glucose"},
        unit_codes={("GLU", "mmol/L"): "mmol_l"},
        specimen_id_source="accession_id",
    )

    row = to_lab_import_row(parsed, mapping, report_instance_id=37)

    assert row.specimen_barcode == "SYNTHETIC-ACCESSION-1"
    assert row.specimen_barcode != parsed.specimen_id
    with pytest.raises(ValueError, match="invalid_specimen_id_source"):
        AnalyzerMappingProfile(
            analyte_codes={"GLU": "glucose"},
            unit_codes={("GLU", "mmol/L"): "mmol_l"},
            specimen_id_source="patient_id",
        )

    long_specimen = HL7V2ORUAdapter().parse(
        HL7_SYNTHETIC.replace(
            "SYNTHETIC-SPECIMEN-1", "SYNTHETIC-SPECIMEN-IDENTIFIER-TOO-LONG"
        )
    )
    with pytest.raises(AnalyzerAdapterError) as too_long:
        to_lab_import_row(long_specimen, _mapping(), report_instance_id=37)
    assert too_long.value.code == "specimen_identifier_too_long"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("profile", "error_code"),
    [
        (
            AnalyzerMappingProfile(analyte_codes={}, unit_codes={}),
            "unmapped_analyte_code",
        ),
        (
            AnalyzerMappingProfile(
                analyte_codes={"GLU": "glucose"}, unit_codes={}
            ),
            "unmapped_unit_code",
        ),
    ],
)
def test_unknown_codes_fail_closed_without_heuristic_mapping(profile, error_code):
    parsed = HL7V2ORUAdapter().parse(HL7_SYNTHETIC)

    with pytest.raises(AnalyzerAdapterError) as error:
        to_lab_import_row(parsed, profile, report_instance_id=37)
    assert error.value.code == error_code


@pytest.mark.unit
def test_hl7_ambiguous_multiple_order_groups_are_rejected():
    payload = HL7_SYNTHETIC.replace(
        "SPM|1|SYNTHETIC-SPECIMEN-1\r",
        "OBR|2|SYNTHETIC-PLACER-2|SYNTHETIC-ACCESSION-2\r"
        "SPM|1|SYNTHETIC-SPECIMEN-1\r",
    )

    with pytest.raises(AnalyzerAdapterError) as error:
        HL7V2ORUAdapter().parse(payload)
    assert error.value.code == "expected_single_hl7_order_and_specimen"


@pytest.mark.unit
def test_oversized_or_malformed_protocol_messages_fail_without_echoing_payload():
    with pytest.raises(AnalyzerAdapterError) as oversized:
        HL7V2ORUAdapter().parse("x" * 1_000_001)
    assert oversized.value.code == "message_too_large"
    assert "x" * 100 not in str(oversized.value)

    with pytest.raises(AnalyzerAdapterError) as malformed:
        ASTMCLSIAdapter().parse("SYNTHETIC-PHI-DO-NOT-ECHO")
    assert malformed.value.code == "invalid_astm_header"
    assert "SYNTHETIC-PHI-DO-NOT-ECHO" not in str(malformed.value)
