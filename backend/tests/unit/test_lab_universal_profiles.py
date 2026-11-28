import pytest
from sqlalchemy import CheckConstraint, Enum, String, UniqueConstraint
from sqlalchemy.orm import configure_mappers

from app.models.lab import (
    LAB_CORE_INTEGRATION_PROTOCOLS,
    LAB_CORE_INTEGRATION_TRANSPORTS,
    LabClinicalConfigurationVersion,
    LabEquipmentIntegrationProfile,
    LabEquipmentIntegrationProfileVersion,
    LabReportInstance,
    LabReportValue,
    _assert_immutable_version_update,
)


def _check_sql(model, name: str) -> str:
    constraint = next(
        item
        for item in model.__table__.constraints
        if isinstance(item, CheckConstraint) and item.name == name
    )
    return str(constraint.sqltext)


def test_lab_model_relationships_resolve():
    configure_mappers()


def test_core_protocols_and_transports_are_universal_and_extensible():
    assert {"astm_clsi", "hl7_v2", "file", "manual"} <= LAB_CORE_INTEGRATION_PROTOCOLS
    assert {"tcp_ip", "rs232", "local_agent", "file_drop", "manual"} <= (
        LAB_CORE_INTEGRATION_TRANSPORTS
    )

    protocol_column = LabEquipmentIntegrationProfileVersion.__table__.c.protocol_code
    transport_column = LabEquipmentIntegrationProfileVersion.__table__.c.transport_code
    assert isinstance(protocol_column.type, String)
    assert not isinstance(protocol_column.type, Enum)
    assert isinstance(transport_column.type, String)
    assert not isinstance(transport_column.type, Enum)

    future_protocol = LabEquipmentIntegrationProfileVersion(
        profile_id=1,
        version_no=1,
        adapter_key="extension.example",
        protocol_code="extension.example.v1",
        transport_code="extension_transport",
    )
    assert future_protocol.protocol_code == "extension.example.v1"
    assert future_protocol.transport_code == "extension_transport"


def test_lab_profiles_extend_existing_equipment_inventory():
    equipment_id = LabEquipmentIntegrationProfile.__table__.c.equipment_id
    equipment_fk = next(iter(equipment_id.foreign_keys))
    assert equipment_fk.target_fullname == "equipment.id"
    assert equipment_fk.ondelete == "RESTRICT"
    assert any(
        isinstance(constraint, UniqueConstraint)
        and {column.name for column in constraint.columns}
        == {"equipment_id", "device_role"}
        for constraint in LabEquipmentIntegrationProfile.__table__.constraints
    )

    version_profile_fk = next(
        iter(
            LabEquipmentIntegrationProfileVersion.__table__.c.profile_id.foreign_keys
        )
    )
    assert version_profile_fk.target_fullname == "lab_equipment_integration_profiles.id"


def test_simulator_and_physical_validation_are_separate_gates():
    columns = LabEquipmentIntegrationProfileVersion.__table__.c
    assert "simulator_validation_status" in columns
    assert "physical_validation_status" in columns
    assert "simulator_evidence_ref" in columns
    assert "physical_evidence_ref" in columns

    activation_check = _check_sql(
        LabEquipmentIntegrationProfileVersion,
        "ck_lab_equipment_active_requires_both_validations",
    )
    assert "simulator_validation_status = 'PASS'" in activation_check
    assert "physical_validation_status = 'PASS'" in activation_check


def test_approved_clinical_configuration_captures_responsibility_and_authority():
    table = LabClinicalConfigurationVersion.__table__
    for name in (
        "configuration_snapshot",
        "primary_lab_physician_user_id",
        "substitute_lab_physician_user_id",
        "approved_by_user_id",
        "approved_role_code",
        "approval_authority_snapshot",
        "approved_at",
    ):
        assert name in table.c

    approval_check = _check_sql(
        LabClinicalConfigurationVersion,
        "ck_lab_clinical_configuration_approval_owner",
    )
    assert "approved_by_user_id = primary_lab_physician_user_id" in approval_check
    assert "approved_by_user_id = substitute_lab_physician_user_id" in approval_check

    approved_index = next(
        index
        for index in table.indexes
        if index.name == "uq_lab_clinical_configuration_approved"
    )
    assert approved_index.unique
    assert "status = 'APPROVED'" in str(
        approved_index.dialect_options["postgresql"]["where"]
    )


def test_new_results_can_reference_applied_configuration_without_backfilling_history():
    clinical_config_column = LabReportInstance.__table__.c.clinical_configuration_version_id
    source_profile_column = LabReportValue.__table__.c.source_integration_profile_version_id

    assert clinical_config_column.nullable is True
    assert source_profile_column.nullable is True
    assert next(iter(clinical_config_column.foreign_keys)).ondelete == "RESTRICT"
    assert next(iter(source_profile_column.foreign_keys)).ondelete == "RESTRICT"


def test_approved_versions_are_immutable_except_for_retirement():
    common = {
        "immutable_statuses": {"APPROVED", "ARCHIVED"},
        "retired_status": "ARCHIVED",
        "label": "clinical configuration",
    }

    _assert_immutable_version_update(
        previous_status="DRAFT",
        current_status="DRAFT",
        dirty_fields={"configuration_snapshot"},
        **common,
    )
    with pytest.raises(ValueError, match="immutable"):
        _assert_immutable_version_update(
            previous_status="APPROVED",
            current_status="APPROVED",
            dirty_fields={"configuration_snapshot"},
            **common,
        )
    _assert_immutable_version_update(
        previous_status="APPROVED",
        current_status="ARCHIVED",
        dirty_fields={"status", "archived_at"},
        **common,
    )
    with pytest.raises(ValueError, match="immutable"):
        _assert_immutable_version_update(
            previous_status="ARCHIVED",
            current_status="ARCHIVED",
            dirty_fields={"archived_at"},
            **common,
        )
