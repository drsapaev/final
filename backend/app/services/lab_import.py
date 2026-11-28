"""Resolve import identities and reuse the canonical result-save transaction."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.lab import (
    LabEquipmentIntegrationProfile,
    LabEquipmentIntegrationProfileVersion,
    LabReportInstance,
)
from app.models.lab_import import LabImportReceipt
from app.repositories.lab_specimen_repository import SpecimenRepository
from app.schemas.lab_import import LabImportBatch, LabImportRow, LabImportRowOut
from app.services.audit_service import log_audit_event
from app.services.lab_import_adapters import (
    ANALYZER_ADAPTERS,
    AnalyzerAdapterError,
    AnalyzerMappingProfile,
    to_lab_import_row,
)
from app.services.lab_reporting import LabReportingDomainError, LabReportingService


class RowRejected(Exception):
    def __init__(self, code: str, *, unmapped_analyte_code: str | None = None):
        super().__init__(code)
        self.code = code
        self.unmapped_analyte_code = unmapped_analyte_code


class AnalyzerIntegrationError(ValueError):
    """Safe integration error code; source message data is never included."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class _BatchReportWrite:
    approved_at: datetime
    updated_at: datetime
    field_keys: set[str]


def _receipt(db: Session, source: str, message_id: str) -> LabImportReceipt | None:
    return db.scalar(
        select(LabImportReceipt).where(
            LabImportReceipt.source == source,
            LabImportReceipt.message_id == message_id,
        )
    )


def _digest(row: LabImportRow) -> str:
    payload = row.model_dump(
        mode="json", exclude={"expected_updated_at", "replace_existing"}
    )
    payload["specimen_barcode"] = row.specimen_barcode.upper()
    for value in payload["values"]:
        if not value["instrument_flags"]:
            # Keep the existing receipt digest for requests without codes.
            del value["instrument_flags"]
    for value_model, value_payload in zip(row.values, payload["values"], strict=True):
        if value_model._source_analyte_code:
            value_payload["source_analyte_code"] = value_model._source_analyte_code
            value_payload["source_instrument_flags"] = list(
                value_model._source_instrument_flags
            )
    payload["values"].sort(key=lambda value: value["field_key"])
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _duplicate(
    existing: LabImportReceipt, row: LabImportRow, digest: str, *, row_index: int
) -> LabImportRowOut:
    if existing.payload_digest != digest:
        raise RowRejected("message_conflict")
    return LabImportRowOut(
        row_index=row_index,
        message_id=row.message_id,
        report_instance_id=row.report_instance_id,
        status="duplicate",
        receipt_id=existing.id,
        updated_at=existing.updated_at_token,
    )


def _map_values(
    service: LabReportingService, instance, row: LabImportRow, *, source: str
) -> list[dict]:
    context = instance.patient_snapshot or {}
    expected_method = context.get("method_code")
    if expected_method != row.method_code:
        raise RowRejected("method_mismatch")

    fields_by_analyte: dict[str, list] = {}
    field_map = service._field_map(instance.template_version)
    for field in field_map.values():
        if field.analyte_code:
            fields_by_analyte.setdefault(field.analyte_code, []).append(field)

    mapped = []
    seen_fields: set[str] = set()
    for value in row.values:
        code = value.field_key
        definitions = fields_by_analyte.get(code, [])
        if source == "manual" and not definitions and code in field_map:
            definitions = [field_map[code]]
        if len(definitions) != 1:
            raise RowRejected("unknown_analyte", unmapped_analyte_code=code)
        field = definitions[0]
        if field.field_key in seen_fields:
            raise RowRejected("duplicate_analyte")
        seen_fields.add(field.field_key)
        unit_code = service._resolve_field_unit_code(field)
        legacy_unit = service._resolve_field_unit(field) if unit_code is None else None
        expected_unit = unit_code or (legacy_unit if source == "manual" else None)
        if value.unit_code != expected_unit or (
            source in {"csv", "analyzer"} and legacy_unit
        ):
            raise RowRejected("unit_mismatch")
        if (
            value.value_text is None
            and value.value_numeric is None
            and value.qualitative_code is None
            and value.result_kind != "absent"
        ):
            raise RowRejected("invalid_value")
        payload = value.model_dump(mode="json", exclude={"instrument_flags"})
        if payload.get("method_code") not in {None, row.method_code}:
            raise RowRejected("method_mismatch")
        payload["field_key"] = field.field_key
        payload["unit_code"] = unit_code
        payload["method_code"] = row.method_code
        try:
            normalized = service._normalize_value_payload(payload, field)
        except LabReportingDomainError as exc:
            raise RowRejected("invalid_value") from exc
        if not normalized["result_payload"]:
            raise RowRejected("invalid_value")
        mapped.append(payload)
    return mapped


def _process_row(
    db: Session,
    source: str,
    actor_id: int,
    row: LabImportRow,
    *,
    row_index: int,
    preview: bool,
    report_writes: dict[int, _BatchReportWrite],
    source_integration_profile_version_id: int | None = None,
) -> LabImportRowOut:
    digest = _digest(row)
    message_id = str(row.message_id)
    existing = _receipt(db, source, message_id)
    if existing:
        return _duplicate(existing, row, digest, row_index=row_index)

    service = LabReportingService(db)
    try:
        instance = service._get_locked_instance(row.report_instance_id)
    except LabReportingDomainError as exc:
        raise RowRejected("report_not_found") from exc

    existing = _receipt(db, source, message_id)
    if existing:
        return _duplicate(existing, row, digest, row_index=row_index)
    try:
        service._assert_instance_mutable_draft(instance)
    except LabReportingDomainError as exc:
        raise RowRejected("report_locked") from exc
    approved_at = row.expected_updated_at
    previous_write = report_writes.get(instance.id)
    token = None
    if not preview:
        if approved_at is None:
            raise RowRejected("stale_report")
        expected = approved_at
        if previous_write is not None and previous_write.approved_at == approved_at:
            # Advance only across commits made by this batch. An intervening
            # write elsewhere still fails the version check under the row lock.
            expected = previous_write.updated_at
        try:
            token = expected.astimezone(UTC).isoformat()
            service._assert_not_concurrently_modified(instance, token)
        except (LabReportingDomainError, OverflowError) as exc:
            raise RowRejected("stale_report") from exc

    specimen_repository = SpecimenRepository(db)
    specimens = specimen_repository.list_for_report(instance.id)
    specimen = next(
        (
            item
            for item in specimens
            if item.barcode == row.specimen_barcode.upper()
            and item.order_id == instance.order_id
            and item.status == "accepted"
        ),
        None,
    )
    if specimen is None:
        raise RowRejected("specimen_mismatch")
    locked = {
        item.id: item for item in specimen_repository.list_for_release(instance.id)
    }
    current = locked.get(specimen.id)
    while current is not None:
        if current.status != "accepted":
            raise RowRejected("specimen_mismatch")
        if current.parent_specimen_id is None:
            break
        current = locked.get(current.parent_specimen_id)
    if current is None:
        raise RowRejected("specimen_mismatch")
    mapped = _map_values(service, instance, row, source=source)
    field_keys = {value["field_key"] for value in mapped}
    existing_values = sum(
        value.field_key in field_keys
        and (
            value.value_text is not None
            or value.value_numeric is not None
            or (value.result_payload or {}).get("kind") == "absent"
        )
        for value in instance.values
    )
    if preview:
        updated_at = instance.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        return LabImportRowOut(
            row_index=row_index,
            message_id=row.message_id,
            report_instance_id=instance.id,
            status="ready",
            updated_at=updated_at,
            existing_values=existing_values,
        )
    assert approved_at is not None
    if previous_write is not None and not previous_write.field_keys.isdisjoint(
        field_keys
    ):
        raise RowRejected("values_exist")
    if existing_values and not row.replace_existing:
        raise RowRejected("values_exist")
    import_origins = {}
    for mapped_value, submitted in zip(mapped, row.values, strict=True):
        origin = {
            "source": source,
            "message_id": message_id,
            "submitted_analyte_code": (
                submitted._source_analyte_code or submitted.field_key
            ),
            "instrument_flags": submitted.instrument_flags,
        }
        if submitted._source_analyte_code:
            origin["source_instrument_flags"] = list(
                submitted._source_instrument_flags
            )
        import_origins[mapped_value["field_key"]] = origin
    try:
        saved, updated = service.bulk_upsert_values(
            instance.id,
            mapped,
            expected_updated_at=token,
            actor_user_id=actor_id,
            source_specimen_id=specimen.id,
            import_origins=import_origins,
            source_integration_profile_version_id=(
                source_integration_profile_version_id
            ),
            commit=False,
        )
    except LabReportingDomainError as exc:
        raise RowRejected("invalid_value") from exc
    updated_at = saved.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    receipt = LabImportReceipt(
        report_instance_id=saved.id,
        specimen_id=specimen.id,
        actor_user_id=actor_id,
        source=source,
        message_id=message_id,
        payload_digest=digest,
        field_keys=[value.field_key for value in updated],
        observed_at=row.observed_at,
        updated_at_token=updated_at.isoformat(),
    )
    db.add(receipt)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = _receipt(db, source, message_id)
        if existing is None:
            raise
        return _duplicate(existing, row, digest, row_index=row_index)

    response = LabImportRowOut(
        row_index=row_index,
        message_id=row.message_id,
        report_instance_id=saved.id,
        status="saved",
        receipt_id=receipt.id,
        updated_at=updated_at,
    )
    db.commit()
    if previous_write is not None:
        field_keys.update(previous_write.field_keys)
    report_writes[row.report_instance_id] = _BatchReportWrite(
        approved_at=approved_at, updated_at=updated_at, field_keys=field_keys
    )
    return response


def process_import_batch(
    db: Session,
    batch: LabImportBatch,
    *,
    actor_id: int,
    preview: bool = False,
    source_integration_profile_version_id: int | None = None,
) -> list[LabImportRowOut]:
    if batch.source == "analyzer" and source_integration_profile_version_id is None:
        raise ValueError("analyzer_profile_version_required")
    if batch.source != "analyzer" and source_integration_profile_version_id is not None:
        raise ValueError("analyzer_profile_version_not_allowed")
    responses = []
    report_writes: dict[int, _BatchReportWrite] = {}
    for row_index, row in enumerate(batch.rows):
        try:
            if isinstance(row, tuple):
                raise RowRejected("invalid_row")
            responses.append(
                _process_row(
                    db,
                    batch.source,
                    actor_id,
                    row,
                    row_index=row_index,
                    preview=preview,
                    report_writes=report_writes,
                    source_integration_profile_version_id=(
                        source_integration_profile_version_id
                    ),
                )
            )
        except RowRejected as exc:
            db.rollback()
            message_id, report_instance_id = (
                row
                if isinstance(row, tuple)
                else (row.message_id, row.report_instance_id)
            )
            if not preview:
                log_audit_event(
                    db,
                    event_type="LAB_IMPORT_ROW_REJECTED",
                    actor_user_id=actor_id,
                    resource_type="lab_import",
                    action="import",
                    outcome="error",
                    reason_code={"source": batch.source, "error_code": exc.code},
                )
            responses.append(
                LabImportRowOut(
                    row_index=row_index,
                    message_id=message_id,
                    report_instance_id=report_instance_id,
                    status="error",
                    error_code=exc.code,
                    unmapped_analyte_code=exc.unmapped_analyte_code,
                )
            )
        finally:
            if db.in_transaction():
                db.rollback()
    return responses


def _mapping_profile(profile_data: object) -> AnalyzerMappingProfile:
    if not isinstance(profile_data, dict):
        raise AnalyzerIntegrationError("invalid_mapping_profile")
    analyte_codes = profile_data.get("analyte_codes")
    unit_codes = profile_data.get("unit_codes")
    flag_codes = profile_data.get("flag_codes", {})
    specimen_id_source = profile_data.get("specimen_id_source", "specimen_id")
    if not isinstance(analyte_codes, dict) or not isinstance(unit_codes, dict):
        raise AnalyzerIntegrationError("invalid_mapping_profile")
    if not isinstance(flag_codes, dict):
        raise AnalyzerIntegrationError("invalid_mapping_profile")
    if not isinstance(specimen_id_source, str) or specimen_id_source not in {
        "specimen_id", "accession_id"
    }:
        raise AnalyzerIntegrationError("invalid_mapping_profile")
    flattened_units = {}
    for source_code, units in unit_codes.items():
        if not isinstance(source_code, str) or not isinstance(units, dict):
            raise AnalyzerIntegrationError("invalid_mapping_profile")
        for source_unit, target_unit in units.items():
            if not isinstance(source_unit, str) or not (
                target_unit is None or isinstance(target_unit, str)
            ):
                raise AnalyzerIntegrationError("invalid_mapping_profile")
            flattened_units[(source_code, source_unit)] = target_unit
    if any(
        not isinstance(source, str) or not isinstance(target, str)
        for source, target in analyte_codes.items()
    ) or any(
        not isinstance(source, str) or not isinstance(target, str)
        for source, target in flag_codes.items()
    ):
        raise AnalyzerIntegrationError("invalid_mapping_profile")
    try:
        return AnalyzerMappingProfile(
            analyte_codes=analyte_codes,
            unit_codes=flattened_units,
            flag_codes=flag_codes,
            specimen_id_source=specimen_id_source,
        )
    except (TypeError, ValueError) as exc:
        raise AnalyzerIntegrationError("invalid_mapping_profile") from exc


def import_analyzer_message(
    db: Session,
    *,
    profile_version_id: int,
    report_instance_id: int,
    payload: str | bytes,
    actor_id: int,
    expected_updated_at: datetime | None = None,
    preview: bool = False,
) -> list[LabImportRowOut]:
    """Parse one analyzer message and hand it to the established safe importer.

    Target reports are selected by the authenticated operator. Analyzer-supplied
    patient identifiers and accessions are never used to select a report; the
    canonical importer verifies the exact accepted specimen belongs to it.
    """
    profile_version = db.scalar(
        select(LabEquipmentIntegrationProfileVersion)
        .join(
            LabEquipmentIntegrationProfile,
            LabEquipmentIntegrationProfile.id
            == LabEquipmentIntegrationProfileVersion.profile_id,
        )
        .where(
            LabEquipmentIntegrationProfileVersion.id == profile_version_id,
            LabEquipmentIntegrationProfileVersion.status == "ACTIVE",
            LabEquipmentIntegrationProfile.device_role == "analyzer",
        )
    )
    if (
        profile_version is None
        or profile_version.simulator_validation_status != "PASS"
        or profile_version.physical_validation_status != "PASS"
    ):
        raise AnalyzerIntegrationError("analyzer_profile_not_ready")
    try:
        adapter = ANALYZER_ADAPTERS.get(profile_version.adapter_key)
        parsed = adapter.parse(payload)
        mapping = _mapping_profile(profile_version.mapping_profile)
    except AnalyzerAdapterError as exc:
        raise AnalyzerIntegrationError(exc.code) from exc

    report = db.get(LabReportInstance, report_instance_id)
    if report is None:
        raise AnalyzerIntegrationError("report_not_found")
    method_code = (report.patient_snapshot or {}).get("method_code")
    try:
        row = to_lab_import_row(
            parsed,
            mapping,
            report_instance_id=report_instance_id,
            method_code=method_code,
            expected_updated_at=expected_updated_at,
            profile_version_id=profile_version.id,
        )
    except (AnalyzerAdapterError, ValueError) as exc:
        code = exc.code if isinstance(exc, AnalyzerAdapterError) else "invalid_mapping_profile"
        raise AnalyzerIntegrationError(code) from exc
    from app.schemas.lab_import import LabImportBatch

    batch = LabImportBatch(source="analyzer", rows=[row])
    return process_import_batch(
        db,
        batch,
        actor_id=actor_id,
        preview=preview,
        source_integration_profile_version_id=profile_version.id,
    )
