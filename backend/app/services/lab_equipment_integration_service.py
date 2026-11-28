"""Versioned clinic-local integration configuration for existing equipment."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.clinic import Equipment
from app.models.lab import (
    LAB_CORE_INTEGRATION_PROTOCOLS,
    LAB_CORE_INTEGRATION_TRANSPORTS,
    LabEquipmentIntegrationProfile,
    LabEquipmentIntegrationProfileVersion,
)
from app.models.user import User
from app.services.audit_service import log_audit_event
from app.services.lab_clinical_configuration_service import (
    get_current_approved_configuration,
)
from app.services.lab_import_adapters import (
    ANALYZER_ADAPTERS,
    AnalyzerAdapterError,
    AnalyzerMappingProfile,
)

DEVICE_ROLES = {"analyzer", "printer", "label_printer", "scanner", "local_agent"}
VALIDATION_STATES = {"NOT_RUN", "PASS", "FAIL"}
EVIDENCE_REF = re.compile(r"^clinic-evidence://[A-Za-z0-9._/-]{1,220}$")
SAFE_ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
SECRET_KEY_PARTS = {
    "password",
    "secret",
    "token",
    "apikey",
    "authorization",
    "credential",
    "privatekey",
    "clientsecret",
}


class IntegrationProfileError(ValueError):
    def __init__(self, code: str, status_code: int = 400):
        self.code = code
        self.status_code = status_code
        super().__init__(code)


def _audit(
    db: Session,
    actor: User,
    *,
    event_type: str,
    resource_type: str,
    resource_id: int,
    action: str,
    outcome: str = "success",
    reason_code: str,
    extra_data: dict[str, Any] | None = None,
) -> None:
    log_audit_event(
        db,
        event_type=event_type,
        actor_user_id=actor.id,
        actor_role=actor.role,
        resource_type=resource_type,
        resource_id=str(resource_id),
        action=action,
        outcome=outcome,
        reason_code={"code": reason_code},
        extra_data=extra_data,
    )


def _reject_secrets(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if any(part in normalized_key for part in SECRET_KEY_PARTS):
                raise IntegrationProfileError("credentials_must_not_be_stored")
            _reject_secrets(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _reject_secrets(nested)


def _validate_transport_settings(transport_code: str, settings: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(settings)
    _reject_secrets(normalized)
    if transport_code == "tcp_ip":
        host = normalized.get("host")
        port = normalized.get("port")
        if not isinstance(host, str) or not host.strip() or len(host) > 255:
            raise IntegrationProfileError("tcp_host_required")
        if type(port) is not int or not 1 <= port <= 65535:
            raise IntegrationProfileError("tcp_port_invalid")
        if normalized.get("tls_required", True) is not True:
            raise IntegrationProfileError("tcp_tls_required")
        normalized["tls_required"] = True
    elif transport_code == "rs232":
        port = normalized.get("serial_port")
        baud = normalized.get("baud_rate")
        if not isinstance(port, str) or not SAFE_ALIAS.fullmatch(port):
            raise IntegrationProfileError("serial_port_invalid")
        if type(baud) is not int or not 300 <= baud <= 4_000_000:
            raise IntegrationProfileError("serial_baud_rate_invalid")
        if normalized.get("data_bits", 8) not in {7, 8}:
            raise IntegrationProfileError("serial_data_bits_invalid")
        if normalized.get("parity", "none") not in {"none", "even", "odd"}:
            raise IntegrationProfileError("serial_parity_invalid")
        if normalized.get("stop_bits", 1) not in {1, 2}:
            raise IntegrationProfileError("serial_stop_bits_invalid")
    elif transport_code == "local_agent":
        agent_id = normalized.get("agent_id")
        channel = normalized.get("channel")
        if not isinstance(agent_id, str) or not SAFE_ALIAS.fullmatch(agent_id):
            raise IntegrationProfileError("local_agent_id_required")
        if not isinstance(channel, str) or not SAFE_ALIAS.fullmatch(channel):
            raise IntegrationProfileError("local_agent_channel_required")
    elif transport_code == "file_drop":
        alias = normalized.get("path_alias")
        if not isinstance(alias, str) or not SAFE_ALIAS.fullmatch(alias):
            raise IntegrationProfileError("file_drop_alias_required")
    elif transport_code == "manual" and normalized:
        raise IntegrationProfileError("manual_transport_settings_not_allowed")
    return normalized


def _validate_mapping_profile(mapping_profile: dict[str, Any]) -> None:
    _reject_secrets(mapping_profile)
    if not isinstance(mapping_profile, dict):
        raise IntegrationProfileError("invalid_mapping_profile")
    if not all(
        isinstance(mapping_profile.get(name), dict)
        for name in ("analyte_codes", "unit_codes")
    ):
        raise IntegrationProfileError("invalid_mapping_profile")
    analytes = mapping_profile["analyte_codes"]
    units = mapping_profile["unit_codes"]
    flags = mapping_profile.get("flag_codes", {})
    specimen_id_source = mapping_profile.get("specimen_id_source", "specimen_id")
    if not isinstance(flags, dict):
        raise IntegrationProfileError("invalid_mapping_profile")
    if not isinstance(specimen_id_source, str) or specimen_id_source not in {
        "specimen_id", "accession_id"
    }:
        raise IntegrationProfileError("invalid_specimen_id_source")
    if not analytes or set(units) != set(analytes):
        raise IntegrationProfileError("invalid_mapping_profile")
    flattened_units = {}
    for source_code, code_units in units.items():
        if (
            not isinstance(source_code, str)
            or not isinstance(code_units, dict)
            or not code_units
        ):
            raise IntegrationProfileError("invalid_mapping_profile")
        for source_unit, target_unit in code_units.items():
            if not isinstance(source_unit, str) or not (
                target_unit is None or isinstance(target_unit, str)
            ):
                raise IntegrationProfileError("invalid_mapping_profile")
            flattened_units[(source_code, source_unit)] = target_unit
    if any(
        not isinstance(source, str) or not isinstance(target, str)
        for source, target in analytes.items()
    ) or any(
        not isinstance(source, str) or not isinstance(target, str)
        for source, target in flags.items()
    ):
        raise IntegrationProfileError("invalid_mapping_profile")
    try:
        AnalyzerMappingProfile(
            analyte_codes=analytes,
            unit_codes=flattened_units,
            flag_codes=flags,
            specimen_id_source=specimen_id_source,
        )
    except (TypeError, ValueError) as exc:
        raise IntegrationProfileError("invalid_mapping_profile") from exc


def _validate_device_settings(
    device_settings: dict[str, Any], device_role: str
) -> None:
    if not isinstance(device_settings, dict):
        raise IntegrationProfileError("invalid_device_settings")
    _reject_secrets(device_settings)
    try:
        json.dumps(device_settings, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise IntegrationProfileError("invalid_device_settings") from exc
    if device_role != "label_printer" and "default_for_lab_labels" in device_settings:
        raise IntegrationProfileError("invalid_device_settings")

    def bounded_dimension(name: str) -> None:
        value = device_settings.get(name)
        if type(value) not in {int, float} or not 1 <= value <= 500:
            raise IntegrationProfileError("invalid_device_settings")

    if device_role == "printer":
        bounded_dimension("media_width_mm")
        bounded_dimension("media_height_mm")
    elif device_role == "label_printer":
        bounded_dimension("label_width_mm")
        bounded_dimension("label_height_mm")
        if device_settings.get("barcode_symbology") not in {
            "Code128", "QR", "DataMatrix"
        }:
            raise IntegrationProfileError("invalid_device_settings")
        if "default_for_lab_labels" in device_settings and type(
            device_settings["default_for_lab_labels"]
        ) is not bool:
            raise IntegrationProfileError("invalid_device_settings")
    elif device_role == "scanner":
        symbologies = device_settings.get("barcode_symbologies")
        if (
            not isinstance(symbologies, list)
            or not symbologies
            or any(
                value not in {"Code128", "QR", "DataMatrix", "PDF417", "EAN13"}
                for value in symbologies
            )
        ):
            raise IntegrationProfileError("invalid_device_settings")


def _validate_synthetic_device_probe(
    *,
    device_role: str,
    device_settings: dict[str, Any],
    transport_settings: dict[str, Any],
    payload: str | bytes,
) -> int:
    """Validate a role-specific synthetic probe without touching a device.

    A passing result proves that the saved settings accept the test contract. It
    never opens TCP/serial connections, prints, scans hardware, or contacts an
    integration agent. Physical acceptance remains an independent clinic step.
    """
    raw = payload if isinstance(payload, bytes) else payload.encode("utf-8")
    if not raw or len(raw) > 1_000_000:
        raise IntegrationProfileError("synthetic_probe_size_invalid", 422)

    if device_role == "analyzer":
        raise IntegrationProfileError("analyzer_probe_requires_protocol_adapter", 422)

    if device_role == "scanner":
        try:
            symbology, barcode = raw.decode("ascii").split("|", 1)
        except (UnicodeDecodeError, ValueError) as exc:
            raise IntegrationProfileError("synthetic_scanner_probe_invalid", 422) from exc
        configured = device_settings.get("barcode_symbologies")
        if (
            not isinstance(configured, list)
            or symbology not in configured
            or not re.fullmatch(r"SYNTHETIC-[A-Z0-9][A-Z0-9._/-]{0,63}", barcode)
        ):
            raise IntegrationProfileError("synthetic_scanner_probe_invalid", 422)
        return 1

    try:
        probe = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntegrationProfileError("synthetic_probe_json_invalid", 422) from exc
    if not isinstance(probe, dict) or not isinstance(probe.get("probe_id"), str):
        raise IntegrationProfileError("synthetic_probe_json_invalid", 422)
    if not re.fullmatch(r"SYNTHETIC-[A-Z0-9][A-Z0-9._/-]{0,63}", probe["probe_id"]):
        raise IntegrationProfileError("synthetic_probe_identifier_required", 422)

    if device_role == "local_agent":
        expected_agent_id = transport_settings.get("agent_id")
        expected_channel = transport_settings.get("channel")
        # This attests only that the supplied synthetic probe matches the saved
        # route; it deliberately never calls a local agent or opens a socket.
        if (
            probe.get("agent_id") != expected_agent_id
            or probe.get("channel") != expected_channel
            or not isinstance(probe.get("agent_version"), str)
            or not probe["agent_version"].startswith("SYNTHETIC-")
        ):
            raise IntegrationProfileError("synthetic_agent_probe_invalid", 422)
        return 1

    if device_role in {"printer", "label_printer"}:
        dimensions = probe.get("dimensions_mm")
        expected_keys = {"probe_id", "dimensions_mm"}
        if device_role == "label_printer":
            expected_keys.add("barcode")
        if (
            set(probe) != expected_keys
            or not isinstance(dimensions, dict)
            or set(dimensions) != {"width", "height"}
        ):
            raise IntegrationProfileError("synthetic_print_probe_invalid", 422)
        width = dimensions.get("width")
        height = dimensions.get("height")
        if any(type(value) not in {int, float} or not 1 <= value <= 500 for value in (width, height)):
            raise IntegrationProfileError("synthetic_print_probe_invalid", 422)
        if device_role == "printer":
            if width > device_settings["media_width_mm"] or height > device_settings["media_height_mm"]:
                raise IntegrationProfileError("synthetic_print_probe_exceeds_media", 422)
            return 1

        barcode = probe.get("barcode")
        if (
            not isinstance(barcode, dict)
            or set(barcode) != {"symbology", "value"}
            or barcode.get("symbology") != device_settings["barcode_symbology"]
            or not isinstance(barcode.get("value"), str)
            or not re.fullmatch(
                r"SYNTHETIC-[A-Z0-9][A-Z0-9._/-]{0,63}", barcode["value"]
            )
            or width > device_settings["label_width_mm"]
            or height > device_settings["label_height_mm"]
        ):
            raise IntegrationProfileError("synthetic_label_probe_invalid", 422)
        return 1

    raise IntegrationProfileError("unsupported_device_role", 422)


def create_profile(
    db: Session, *, equipment_id: int, device_role: str, actor: User
) -> LabEquipmentIntegrationProfile:
    if device_role not in DEVICE_ROLES:
        raise IntegrationProfileError("unsupported_device_role")
    equipment = db.get(Equipment, equipment_id)
    if equipment is None:
        raise IntegrationProfileError("equipment_not_found", 404)
    profile = LabEquipmentIntegrationProfile(
        equipment_id=equipment.id,
        device_role=device_role,
        created_by_user_id=actor.id,
    )
    db.add(profile)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise IntegrationProfileError("equipment_role_already_registered", 409) from exc
    _audit(
        db,
        actor,
        event_type="LAB_EQUIPMENT_INTEGRATION_PROFILE_CREATED",
        resource_type="lab_equipment_integration_profile",
        resource_id=profile.id,
        action="create",
        reason_code="equipment_role_registered",
    )
    db.commit()
    db.refresh(profile)
    return profile


def create_profile_version(
    db: Session,
    *,
    profile_id: int,
    adapter_key: str,
    protocol_code: str,
    transport_code: str,
    mapping_profile: dict[str, Any],
    transport_settings: dict[str, Any],
    device_settings: dict[str, Any],
    actor: User,
) -> LabEquipmentIntegrationProfileVersion:
    profile = db.get(LabEquipmentIntegrationProfile, profile_id)
    if profile is None:
        raise IntegrationProfileError("profile_not_found", 404)
    if not adapter_key or len(adapter_key) > 100:
        raise IntegrationProfileError("adapter_key_invalid")
    if not protocol_code or len(protocol_code) > 64:
        raise IntegrationProfileError("protocol_code_invalid")
    if not transport_code or len(transport_code) > 32:
        raise IntegrationProfileError("transport_code_invalid")
    # Core protocols/transports are stable defaults; any additional value remains
    # a clinic-neutral extension key and needs a registered runtime adapter.
    if protocol_code in LAB_CORE_INTEGRATION_PROTOCOLS:
        if protocol_code in {"astm_clsi", "hl7_v2"} and profile.device_role != "analyzer":
            raise IntegrationProfileError("analyzer_protocol_requires_analyzer_role")
    if transport_code not in LAB_CORE_INTEGRATION_TRANSPORTS and not re.fullmatch(
        r"[a-z][a-z0-9_.-]{0,31}", transport_code
    ):
        raise IntegrationProfileError("transport_code_invalid")
    if protocol_code not in LAB_CORE_INTEGRATION_PROTOCOLS and not re.fullmatch(
        r"[a-z][a-z0-9_.-]{0,63}", protocol_code
    ):
        raise IntegrationProfileError("protocol_code_invalid")
    if not isinstance(mapping_profile, dict) or not isinstance(transport_settings, dict):
        raise IntegrationProfileError("invalid_profile_settings")
    if profile.device_role == "analyzer":
        _validate_mapping_profile(mapping_profile)
    else:
        _reject_secrets(mapping_profile)
    _validate_device_settings(device_settings, profile.device_role)
    safe_transport = _validate_transport_settings(transport_code, transport_settings)
    current_version = db.scalar(
        select(LabEquipmentIntegrationProfileVersion.version_no)
        .where(LabEquipmentIntegrationProfileVersion.profile_id == profile_id)
        .order_by(LabEquipmentIntegrationProfileVersion.version_no.desc())
        .limit(1)
    )
    version = LabEquipmentIntegrationProfileVersion(
        profile_id=profile.id,
        version_no=(current_version or 0) + 1,
        status="DRAFT",
        adapter_key=adapter_key,
        protocol_code=protocol_code,
        transport_code=transport_code,
        mapping_profile=mapping_profile,
        transport_settings=safe_transport,
        device_settings=device_settings,
        simulator_validation_status="NOT_RUN",
        physical_validation_status="NOT_RUN",
        created_by_user_id=actor.id,
        created_at=datetime.now(UTC),
    )
    db.add(version)
    db.flush()
    _audit(
        db,
        actor,
        event_type="LAB_EQUIPMENT_INTEGRATION_VERSION_CREATED",
        resource_type="lab_equipment_integration_profile_version",
        resource_id=version.id,
        action="create",
        reason_code="version_created_as_draft",
        extra_data={"version_no": version.version_no},
    )
    db.commit()
    db.refresh(version)
    return version


def record_simulator_check(
    db: Session,
    *,
    version_id: int,
    payload: str | bytes,
    actor: User,
) -> dict[str, Any]:
    version = db.get(LabEquipmentIntegrationProfileVersion, version_id)
    if version is None:
        raise IntegrationProfileError("profile_version_not_found", 404)
    if version.status != "DRAFT":
        raise IntegrationProfileError("profile_version_not_draft", 409)
    digest = hashlib.sha256(
        payload if isinstance(payload, bytes) else payload.encode("utf-8")
    ).hexdigest()
    profile = db.get(LabEquipmentIntegrationProfile, version.profile_id)
    if profile is None:
        raise IntegrationProfileError("profile_not_found", 404)
    result_count = 0
    try:
        if profile.device_role == "analyzer":
            marker_text = (
                payload.decode("ascii", errors="ignore")
                if isinstance(payload, bytes)
                else payload
            )
            if re.search(r"(?:^|[\r\n])(?:PID|P)\|", marker_text):
                raise AnalyzerAdapterError("synthetic_payload_must_omit_patient_segments")
            adapter = ANALYZER_ADAPTERS.get(version.adapter_key)
            parsed = adapter.parse(payload)
            if not parsed.accession_id.startswith("SYNTHETIC-") or not parsed.specimen_id.startswith(
                "SYNTHETIC-"
            ):
                raise AnalyzerAdapterError("synthetic_identifiers_required")
            mapping_data = version.mapping_profile
            analytes = mapping_data["analyte_codes"]
            nested_units = mapping_data["unit_codes"]
            flattened = {
                (source_code, source_unit): target_unit
                for source_code, values in nested_units.items()
                for source_unit, target_unit in values.items()
            }
            mapping = AnalyzerMappingProfile(
                analyte_codes=analytes,
                unit_codes=flattened,
                flag_codes=mapping_data.get("flag_codes", {}),
                specimen_id_source=mapping_data.get(
                    "specimen_id_source", "specimen_id"
                ),
            )
            selected_specimen_id = mapping.specimen_barcode(parsed)
            if not selected_specimen_id.startswith("SYNTHETIC-"):
                raise AnalyzerAdapterError("synthetic_identifiers_required")
            mapped = mapping.map_values(parsed)
            result_count = len(mapped)
        else:
            result_count = _validate_synthetic_device_probe(
                device_role=profile.device_role,
                device_settings=version.device_settings,
                transport_settings=version.transport_settings,
                payload=payload,
            )
    except (AnalyzerAdapterError, IntegrationProfileError, KeyError, TypeError, ValueError) as exc:
        code = (
            exc.code
            if isinstance(exc, (AnalyzerAdapterError, IntegrationProfileError))
            else "invalid_simulator_profile"
        )
        _store_simulator_result(
            db,
            version,
            actor,
            status="FAIL",
            evidence_ref=f"synthetic-test://sha256/{digest}",
            reason_code=code,
            result_count=0,
        )
        raise IntegrationProfileError(code, 422) from exc

    evidence_ref = f"synthetic-test://sha256/{digest}"
    _store_simulator_result(
        db,
        version,
        actor,
        status="PASS",
        evidence_ref=evidence_ref,
        reason_code="synthetic_protocol_and_mapping_passed",
        result_count=result_count,
    )
    return {
        "version_id": version.id,
        "adapter_key": version.adapter_key,
        "status": version.simulator_validation_status,
        "result_count": result_count,
        "evidence_ref": evidence_ref,
    }


def _store_simulator_result(
    db: Session,
    version: LabEquipmentIntegrationProfileVersion,
    actor: User,
    *,
    status: str,
    evidence_ref: str,
    reason_code: str,
    result_count: int,
) -> None:
    version.simulator_validation_status = status
    version.simulator_validated_at = datetime.now(UTC)
    version.simulator_evidence_ref = evidence_ref
    _audit(
        db,
        actor,
        event_type="LAB_EQUIPMENT_INTEGRATION_SIMULATOR_CHECKED",
        resource_type="lab_equipment_integration_profile_version",
        resource_id=version.id,
        action="validate",
        outcome="success" if status == "PASS" else "error",
        reason_code=reason_code,
        extra_data={"result_count": result_count, "status": status},
    )
    db.commit()


def record_physical_validation(
    db: Session,
    *,
    version_id: int,
    status: str,
    evidence_ref: str,
    actor: User,
) -> LabEquipmentIntegrationProfileVersion:
    version = db.get(LabEquipmentIntegrationProfileVersion, version_id)
    if version is None:
        raise IntegrationProfileError("profile_version_not_found", 404)
    if version.status != "DRAFT":
        raise IntegrationProfileError("profile_version_not_draft", 409)
    if status not in {"PASS", "FAIL"}:
        raise IntegrationProfileError("physical_validation_status_invalid")
    if not EVIDENCE_REF.fullmatch(evidence_ref):
        raise IntegrationProfileError("physical_evidence_reference_required")
    version.physical_validation_status = status
    version.physical_validated_at = datetime.now(UTC)
    version.physical_validated_by_user_id = actor.id
    version.physical_evidence_ref = evidence_ref
    _audit(
        db,
        actor,
        event_type="LAB_EQUIPMENT_INTEGRATION_PHYSICAL_VALIDATION_RECORDED",
        resource_type="lab_equipment_integration_profile_version",
        resource_id=version.id,
        action="validate",
        outcome="success" if status == "PASS" else "error",
        reason_code="clinic_physical_validation_recorded",
        extra_data={"status": status, "evidence_ref": evidence_ref},
    )
    db.commit()
    db.refresh(version)
    return version


def activate_profile_version(
    db: Session, *, version_id: int, actor: User
) -> LabEquipmentIntegrationProfileVersion:
    version = db.scalar(
        select(LabEquipmentIntegrationProfileVersion)
        .where(LabEquipmentIntegrationProfileVersion.id == version_id)
        .with_for_update()
    )
    if version is None:
        raise IntegrationProfileError("profile_version_not_found", 404)
    if version.status != "DRAFT":
        raise IntegrationProfileError("profile_version_not_draft", 409)
    profile = db.get(LabEquipmentIntegrationProfile, version.profile_id)
    if profile is None:
        raise IntegrationProfileError("profile_not_found", 404)
    if (
        version.simulator_validation_status != "PASS"
        or not version.simulator_evidence_ref
        or version.physical_validation_status != "PASS"
        or not version.physical_evidence_ref
        or version.physical_validated_by_user_id is None
    ):
        raise IntegrationProfileError("simulator_and_physical_validation_required", 409)
    if profile.device_role == "analyzer":
        clinical_configuration = get_current_approved_configuration(db)
        if (
            version.clinical_approved_by_user_id is None
            or version.clinical_approved_at is None
            or version.clinical_approval_configuration_version_id is None
            or clinical_configuration is None
            or clinical_configuration.id
            != version.clinical_approval_configuration_version_id
        ):
            raise IntegrationProfileError("current_lab_physician_approval_required", 409)
    now = datetime.now(UTC)
    active_versions = db.scalars(
        select(LabEquipmentIntegrationProfileVersion)
        .where(
            LabEquipmentIntegrationProfileVersion.profile_id == version.profile_id,
            LabEquipmentIntegrationProfileVersion.status == "ACTIVE",
        )
        .with_for_update()
    ).all()
    for previous in active_versions:
        previous.status = "RETIRED"
        previous.retired_at = now
    db.flush()
    version.status = "ACTIVE"
    version.activated_at = now
    _audit(
        db,
        actor,
        event_type="LAB_EQUIPMENT_INTEGRATION_VERSION_ACTIVATED",
        resource_type="lab_equipment_integration_profile_version",
        resource_id=version.id,
        action="activate",
        reason_code="both_validation_gates_passed",
        extra_data={"version_no": version.version_no},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise IntegrationProfileError("active_profile_version_conflict", 409) from exc
    db.refresh(version)
    return version


def list_pending_analyzer_approvals(
    db: Session, *, actor: User
) -> list[dict[str, Any]]:
    """Return reviewable analyzer mappings without network or credential settings."""
    configuration = get_current_approved_configuration(db)
    if actor.role == "Lab":
        if (
            configuration is None
            or actor.id
            not in {
                configuration.primary_lab_physician_user_id,
                configuration.substitute_lab_physician_user_id,
            }
        ):
            return []
    elif actor.role != "Admin":
        return []

    rows = db.execute(
        select(
            LabEquipmentIntegrationProfileVersion,
            LabEquipmentIntegrationProfile,
            Equipment,
        )
        .join(
            LabEquipmentIntegrationProfile,
            LabEquipmentIntegrationProfile.id
            == LabEquipmentIntegrationProfileVersion.profile_id,
        )
        .join(Equipment, Equipment.id == LabEquipmentIntegrationProfile.equipment_id)
        .where(
            LabEquipmentIntegrationProfile.device_role == "analyzer",
            LabEquipmentIntegrationProfileVersion.status == "DRAFT",
            LabEquipmentIntegrationProfileVersion.clinical_approved_by_user_id.is_(None),
        )
        .order_by(
            LabEquipmentIntegrationProfileVersion.created_at,
            LabEquipmentIntegrationProfileVersion.id,
        )
    ).all()
    return [
        {
            "version_id": version.id,
            "profile_id": profile.id,
            "version_no": version.version_no,
            "equipment_id": equipment.id,
            "equipment_name": equipment.name,
            "equipment_model": equipment.model,
            "adapter_key": version.adapter_key,
            "protocol_code": version.protocol_code,
            "mapping_profile": version.mapping_profile,
            "simulator_validation_status": version.simulator_validation_status,
            "simulator_evidence_ref": version.simulator_evidence_ref,
            "physical_validation_status": version.physical_validation_status,
            "physical_evidence_ref": version.physical_evidence_ref,
            "created_at": version.created_at,
        }
        for version, profile, equipment in rows
    ]


def approve_analyzer_mapping_version(
    db: Session, *, version_id: int, actor: User
) -> LabEquipmentIntegrationProfileVersion:
    """Record the current assigned Lab physician's approval for one immutable map."""
    if not actor.is_active or actor.role != "Lab":
        raise IntegrationProfileError("active_lab_physician_required", 403)
    version = db.scalar(
        select(LabEquipmentIntegrationProfileVersion)
        .where(LabEquipmentIntegrationProfileVersion.id == version_id)
        .with_for_update()
    )
    if version is None:
        raise IntegrationProfileError("profile_version_not_found", 404)
    if version.status != "DRAFT":
        raise IntegrationProfileError("profile_version_not_draft", 409)
    if version.clinical_approved_by_user_id is not None:
        raise IntegrationProfileError("analyzer_mapping_already_approved", 409)
    profile = db.get(LabEquipmentIntegrationProfile, version.profile_id)
    if profile is None:
        raise IntegrationProfileError("profile_not_found", 404)
    if profile.device_role != "analyzer":
        raise IntegrationProfileError("analyzer_profile_required", 409)

    configuration = get_current_approved_configuration(db)
    if configuration is None:
        raise IntegrationProfileError("approved_clinical_configuration_required", 409)
    if actor.id == configuration.primary_lab_physician_user_id:
        assignment = "primary"
    elif actor.id == configuration.substitute_lab_physician_user_id:
        assignment = "substitute"
    else:
        raise IntegrationProfileError("assigned_lab_physician_approval_required", 403)

    version.clinical_approved_by_user_id = actor.id
    version.clinical_approved_at = datetime.now(UTC)
    version.clinical_approval_configuration_version_id = configuration.id
    version.clinical_approval_authority_snapshot = {
        "actor_user_id": actor.id,
        "actor_role_code": actor.role,
        "assignment": assignment,
        "clinical_configuration_version_id": configuration.id,
        "clinical_configuration_version_no": configuration.version_no,
        "assigned_primary_user_id": configuration.primary_lab_physician_user_id,
        "assigned_substitute_user_id": configuration.substitute_lab_physician_user_id,
        "account_active_at_approval": True,
    }
    _audit(
        db,
        actor,
        event_type="LAB_ANALYZER_MAPPING_CLINICALLY_APPROVED",
        resource_type="lab_equipment_integration_profile_version",
        resource_id=version.id,
        action="approve",
        reason_code="assigned_lab_physician_approved_analyzer_mapping",
        extra_data={
            "version_no": version.version_no,
            "clinical_configuration_version_id": configuration.id,
            "assignment": assignment,
        },
    )
    db.commit()
    db.refresh(version)
    return version


def list_profiles(db: Session) -> list[LabEquipmentIntegrationProfile]:
    return list(
        db.scalars(
            select(LabEquipmentIntegrationProfile)
            .options(
                selectinload(LabEquipmentIntegrationProfile.versions)
            )
            .order_by(LabEquipmentIntegrationProfile.equipment_id)
        ).all()
    )
