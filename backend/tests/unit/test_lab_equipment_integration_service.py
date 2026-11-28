import pytest

from app.services.lab_equipment_integration_service import (
    IntegrationProfileError,
    _reject_secrets,
    _validate_device_settings,
    _validate_mapping_profile,
    _validate_synthetic_device_probe,
    _validate_transport_settings,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("transport", "settings"),
    [
        (
            "tcp_ip",
            {"host": "127.0.0.1", "port": 10001},
        ),
        (
            "rs232",
            {"serial_port": "COM3", "baud_rate": 9600, "parity": "even"},
        ),
        (
            "local_agent",
            {"agent_id": "clinic-agent-1", "channel": "lab-analyzer-1"},
        ),
        ("file_drop", {"path_alias": "analyzer-results"}),
        ("manual", {}),
    ],
)
def test_supported_transport_settings_are_clinic_local_and_secret_free(
    transport, settings
):
    normalized = _validate_transport_settings(transport, settings)
    if transport == "tcp_ip":
        assert normalized["tls_required"] is True
    assert normalized == settings or transport == "tcp_ip"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("transport", "settings", "code"),
    [
        ("tcp_ip", {"host": "127.0.0.1", "port": 10001, "tls_required": False}, "tcp_tls_required"),
        ("tcp_ip", {"host": "127.0.0.1", "port": 70000}, "tcp_port_invalid"),
        ("rs232", {"serial_port": "../tty0", "baud_rate": 9600}, "serial_port_invalid"),
        ("local_agent", {"agent_id": "agent", "channel": "lab", "token": "secret"}, "credentials_must_not_be_stored"),
        ("file_drop", {"path_alias": "../../results"}, "file_drop_alias_required"),
    ],
)
def test_transport_rejects_unsafe_settings(transport, settings, code):
    with pytest.raises(IntegrationProfileError) as error:
        _validate_transport_settings(transport, settings)
    assert error.value.code == code


@pytest.mark.unit
def test_analyzer_mapping_profiles_require_explicit_exact_code_and_unit_maps():
    _validate_mapping_profile(
        {
            "analyte_codes": {"VENDOR-GLU": "glucose"},
            "unit_codes": {"VENDOR-GLU": {"mmol/L": "mmol_l"}},
            "flag_codes": {"H": "HIGH"},
        }
    )

    with pytest.raises(IntegrationProfileError) as error:
        _validate_mapping_profile(
            {"analyte_codes": {"VENDOR-GLU": "glucose"}, "unit_codes": {}}
        )
    assert error.value.code == "invalid_mapping_profile"

    with pytest.raises(IntegrationProfileError) as invalid_identifier:
        _validate_mapping_profile(
            {
                "analyte_codes": {"VENDOR-GLU": "glucose"},
                "unit_codes": {"VENDOR-GLU": {"mmol/L": "mmol_l"}},
                "specimen_id_source": [],
            }
        )
    assert invalid_identifier.value.code == "invalid_specimen_id_source"


@pytest.mark.unit
def test_nested_credentials_are_never_persisted_in_profile_json():
    with pytest.raises(IntegrationProfileError) as error:
        _reject_secrets({"connection": {"tls": {"private_key": "not persisted"}}})
    assert error.value.code == "credentials_must_not_be_stored"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("role", "settings", "payload", "transport"),
    [
        (
            "printer",
            {"media_width_mm": 80, "media_height_mm": 200},
            '{"probe_id":"SYNTHETIC-PRINT-1","dimensions_mm":{"width":40,"height":50}}',
            {},
        ),
        (
            "label_printer",
            {
                "label_width_mm": 60,
                "label_height_mm": 40,
                "barcode_symbology": "Code128",
            },
            '{"probe_id":"SYNTHETIC-LABEL-1","dimensions_mm":{"width":50,"height":20},"barcode":{"symbology":"Code128","value":"SYNTHETIC-SPECIMEN-1"}}',
            {},
        ),
        (
            "scanner",
            {"barcode_symbologies": ["Code128"]},
            "Code128|SYNTHETIC-SPECIMEN-1",
            {},
        ),
        (
            "local_agent",
            {},
            '{"probe_id":"SYNTHETIC-AGENT-1","agent_id":"clinic-agent","channel":"results","agent_version":"SYNTHETIC-1"}',
            {"agent_id": "clinic-agent", "channel": "results"},
        ),
    ],
)
def test_role_specific_synthetic_probes_validate_configuration_without_hardware(
    role, settings, payload, transport
):
    _validate_device_settings(settings, role)
    assert _validate_synthetic_device_probe(
        device_role=role,
        device_settings=settings,
        transport_settings=transport,
        payload=payload,
    ) == 1


@pytest.mark.unit
@pytest.mark.parametrize(
    ("role", "settings"),
    [
        ("printer", {"media_width_mm": 0, "media_height_mm": 200}),
        (
            "label_printer",
            {"label_width_mm": 60, "label_height_mm": 40, "barcode_symbology": "unknown"},
        ),
        ("scanner", {"barcode_symbologies": []}),
    ],
)
def test_peripheral_profiles_need_explicit_valid_output_or_scan_settings(role, settings):
    with pytest.raises(IntegrationProfileError) as error:
        _validate_device_settings(settings, role)
    assert error.value.code == "invalid_device_settings"


@pytest.mark.unit
@pytest.mark.parametrize("symbology", ["Code128", "QR", "DataMatrix"])
def test_label_printer_output_symbols_are_supported_by_the_pdf_renderer(symbology):
    _validate_device_settings(
        {
            "label_width_mm": 60,
            "label_height_mm": 40,
            "barcode_symbology": symbology,
            "default_for_lab_labels": True,
        },
        "label_printer",
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("role", "settings"),
    [
        (
            "label_printer",
            {
                "label_width_mm": 60,
                "label_height_mm": 40,
                "barcode_symbology": "PDF417",
            },
        ),
        (
            "label_printer",
            {
                "label_width_mm": 60,
                "label_height_mm": 40,
                "barcode_symbology": "Code128",
                "default_for_lab_labels": "true",
            },
        ),
        ("printer", {"media_width_mm": 80, "media_height_mm": 200, "default_for_lab_labels": True}),
    ],
)
def test_label_selection_is_boolean_and_unsupported_output_symbols_fail_closed(
    role, settings
):
    with pytest.raises(IntegrationProfileError) as error:
        _validate_device_settings(settings, role)
    assert error.value.code == "invalid_device_settings"


@pytest.mark.unit
def test_multiple_active_label_defaults_fail_closed():
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.services.lab_specimen_service import LabSpecimenService
    from app.services.lab_reporting_service import LabReportingDomainError

    db = Mock()
    db.scalars.return_value.all.return_value = [
        SimpleNamespace(id=1, device_settings={"default_for_lab_labels": True}),
        SimpleNamespace(id=2, device_settings={"default_for_lab_labels": True}),
    ]
    service = LabSpecimenService(db)
    with pytest.raises(LabReportingDomainError) as error:
        service._selected_label_profile_version()
    assert error.value.status_code == 409


@pytest.mark.unit
def test_peripheral_probe_rejects_non_synthetic_or_unconfigured_input():
    with pytest.raises(IntegrationProfileError) as error:
        _validate_synthetic_device_probe(
            device_role="scanner",
            device_settings={"barcode_symbologies": ["Code128"]},
            transport_settings={},
            payload="Code128|PATIENT-12345",
        )
    assert error.value.code == "synthetic_scanner_probe_invalid"
