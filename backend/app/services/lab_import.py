"""Resolve import identities and reuse the canonical result-save transaction."""

import hashlib
import json
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.lab_import import LabImportReceipt
from app.repositories.lab_specimen_repository import SpecimenRepository
from app.schemas.lab_import import LabImportBatch, LabImportRow, LabImportRowOut
from app.services.lab_reporting import LabReportingDomainError, LabReportingService


class RowRejected(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


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
    payload["values"].sort(key=lambda value: value["field_key"])
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _duplicate(
    existing: LabImportReceipt, row: LabImportRow, digest: str
) -> LabImportRowOut:
    if existing.payload_digest != digest:
        raise RowRejected("message_conflict")
    return LabImportRowOut(
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
    seen: set[str] = set()
    for value in row.values:
        code = value.field_key
        if code in seen:
            raise RowRejected("duplicate_analyte")
        seen.add(code)
        definitions = fields_by_analyte.get(code, [])
        if source == "manual" and not definitions and code in field_map:
            definitions = [field_map[code]]
        if len(definitions) != 1:
            raise RowRejected("unknown_analyte")
        field = definitions[0]
        unit_code = service._resolve_field_unit_code(field)
        legacy_unit = service._resolve_field_unit(field) if unit_code is None else None
        expected_unit = unit_code or (legacy_unit if source == "manual" else None)
        if value.unit_code != expected_unit or (source == "csv" and legacy_unit):
            raise RowRejected("unit_mismatch")
        if (
            value.value_text is None
            and value.value_numeric is None
            and value.qualitative_code is None
            and value.result_kind != "absent"
        ):
            raise RowRejected("invalid_value")
        payload = value.model_dump(mode="json")
        payload["field_key"] = field.field_key
        payload["unit_code"] = unit_code
        payload["method_code"] = row.method_code
        mapped.append(payload)
    return mapped


def _process_row(
    db: Session,
    source: str,
    actor_id: int,
    row: LabImportRow,
    *,
    preview: bool,
) -> LabImportRowOut:
    digest = _digest(row)
    message_id = str(row.message_id)
    existing = _receipt(db, source, message_id)
    if existing:
        return _duplicate(existing, row, digest)

    service = LabReportingService(db)
    try:
        instance = service._get_locked_instance(row.report_instance_id)
    except LabReportingDomainError as exc:
        raise RowRejected("report_not_found") from exc

    existing = _receipt(db, source, message_id)
    if existing:
        return _duplicate(existing, row, digest)
    try:
        service._assert_instance_mutable_draft(instance)
    except LabReportingDomainError as exc:
        raise RowRejected("report_locked") from exc
    token = (
        row.expected_updated_at.astimezone(UTC).isoformat()
        if row.expected_updated_at
        else None
    )
    if not preview:
        if token is None:
            raise RowRejected("stale_report")
        try:
            service._assert_not_concurrently_modified(instance, token)
        except LabReportingDomainError as exc:
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
        definitions = service._field_map(instance.template_version)
        try:
            for value in mapped:
                service._normalize_value_payload(value, definitions[value["field_key"]])
        except LabReportingDomainError as exc:
            raise RowRejected("invalid_value") from exc
        updated_at = instance.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=UTC)
        return LabImportRowOut(
            message_id=row.message_id,
            report_instance_id=instance.id,
            status="ready",
            updated_at=updated_at,
            existing_values=existing_values,
        )
    if existing_values and not row.replace_existing:
        raise RowRejected("values_exist")
    try:
        saved, updated = service.bulk_upsert_values(
            instance.id,
            mapped,
            expected_updated_at=token,
            actor_user_id=actor_id,
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
        return _duplicate(existing, row, digest)

    response = LabImportRowOut(
        message_id=row.message_id,
        report_instance_id=saved.id,
        status="saved",
        receipt_id=receipt.id,
        updated_at=updated_at,
    )
    db.commit()
    return response


def process_import_batch(
    db: Session,
    batch: LabImportBatch,
    *,
    actor_id: int,
    preview: bool = False,
) -> list[LabImportRowOut]:
    responses = []
    for row in batch.rows:
        try:
            responses.append(
                _process_row(db, batch.source, actor_id, row, preview=preview)
            )
        except RowRejected as exc:
            responses.append(
                LabImportRowOut(
                    message_id=row.message_id,
                    report_instance_id=row.report_instance_id,
                    status="error",
                    error_code=exc.code,
                )
            )
        finally:
            if db.in_transaction():
                db.rollback()
    return responses
