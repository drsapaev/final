from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import settings
from app.main import app
from app.models.audit import AuditLog
from app.models.lab import LabReportValue
from app.models.lab_import import LabImportReceipt
from app.models.role_permission import Permission
from app.schemas.lab_import import LabImportBatch, LabImportRow
from app.schemas.lab_release import LabReportQCIn
from app.services.lab_import import _digest
from app.services.lab_reporting import LabReportingService
from tests.unit.test_lab_managed_release import _staff
from tests.unit.test_lab_v2_operations import accepted_specimen, synthetic_report

IMPORT_URL = "/api/v1/lab/imports"


@pytest.mark.unit
def test_malformed_import_rows_keep_position_and_valid_siblings_commit(
    client, db_session, admin_auth_headers, test_patient
):
    service, report = synthetic_report(db_session, test_patient.id)
    specimen = accepted_specimen(db_session, report, "SYNTHETIC-IMPORT-V2")
    field = service._field_map(report.template_version)["hgb"]
    observed_at = datetime(2026, 11, 24, 8, tzinfo=UTC)
    valid = {
        "message_id": str(uuid4()),
        "report_instance_id": report.id,
        "specimen_barcode": specimen.barcode,
        "observed_at": observed_at.isoformat(),
        "values": [
            {
                "analyte_code": field.field_key,
                "unit_code": service._resolve_field_unit_code(field)
                or service._resolve_field_unit(field),
                "value_text": "0",
            }
        ],
    }
    malformed = {
        **valid,
        "message_id": str(uuid4()),
        "unexpected": "SYNTHETIC-DO-NOT-ECHO",
    }
    raw_identifiers = {
        "message_id": "SYNTHETIC-NOT-A-UUID",
        "report_instance_id": 10**50,
        "values": [],
    }
    batch = {"source": "manual", "rows": [malformed, valid, None, raw_identifiers]}
    preview = client.post(
        f"{IMPORT_URL}/preview", json=batch, headers=admin_auth_headers
    )
    assert preview.status_code == 200
    assert preview.headers["Cache-Control"] == "private, no-store"
    assert "SYNTHETIC-DO-NOT-ECHO" not in preview.text
    assert "SYNTHETIC-NOT-A-UUID" not in preview.text
    outcomes = preview.json()["rows"]
    assert [row["row_index"] for row in outcomes] == [0, 1, 2, 3]
    assert [row["status"] for row in outcomes] == ["error", "ready", "error", "error"]
    assert [row["error_code"] for row in outcomes] == [
        "invalid_row",
        None,
        "invalid_row",
        "invalid_row",
    ]
    assert outcomes[0]["message_id"] == malformed["message_id"]
    assert outcomes[0]["report_instance_id"] == report.id
    for row in outcomes[2:]:
        assert row["message_id"] is None and row["report_instance_id"] is None
    assert db_session.scalar(select(LabImportReceipt.id)) is None
    rejection_query = select(AuditLog).where(
        AuditLog.event_type == "LAB_IMPORT_ROW_REJECTED"
    )
    assert not db_session.scalars(rejection_query).all()

    valid["expected_updated_at"] = outcomes[1]["updated_at"]
    applied = client.post(IMPORT_URL, json=batch, headers=admin_auth_headers)
    assert applied.status_code == 200
    outcomes = applied.json()["rows"]
    assert [row["row_index"] for row in outcomes] == [0, 1, 2, 3]
    assert [row["status"] for row in outcomes] == ["error", "saved", "error", "error"]
    receipt = db_session.scalar(select(LabImportReceipt))
    assert receipt.id == outcomes[1]["receipt_id"]
    assert receipt.source == "manual" and receipt.specimen_id == specimen.id
    assert receipt.observed_at.replace(tzinfo=UTC) == observed_at
    rejections = db_session.scalars(rejection_query).all()
    assert len(rejections) == 3
    for rejection in rejections:
        assert rejection.reason_code == {
            "source": "manual",
            "error_code": "invalid_row",
        }
        assert rejection.resource_id is None and rejection.payload is None

    replay = client.post(IMPORT_URL, json=batch, headers=admin_auth_headers)
    assert replay.status_code == 200
    assert replay.json()["rows"][1]["status"] == "duplicate"
    assert replay.json()["rows"][1]["receipt_id"] == receipt.id
    assert len(db_session.scalars(select(LabImportReceipt)).all()) == 1


@pytest.mark.unit
def test_warning_codes_follow_exact_imported_value_through_release_and_correction(
    client,
    db_session,
    admin_user,
    admin_auth_headers,
    test_patient,
    monkeypatch,
    caplog,
):
    monkeypatch.setattr(settings, "LAB_MANAGED_RELEASE_ENABLED", True)
    monkeypatch.setattr(settings, "LAB_RELEASE_REQUIRE_DISTINCT_REVIEWER", True)
    reviewer = _staff(
        db_session,
        "synthetic-import-reviewer",
        [
            Permission(name=code, codename=code)
            for code in ("lab:review", "lab:release", "lab:qc")
        ],
    )
    service = LabReportingService(db_session)
    monkeypatch.setattr(service, "_emit_lab_results_ready_notification", lambda _: None)
    template = next(item for item in service.list_templates() if item.code == "cbc_oak")
    report = service.create_instance(
        {"patient_id": test_patient.id, "template_id": template.id},
        actor_user_id=admin_user.id,
    )
    specimen = accepted_specimen(db_session, report, "SYNTHETIC-DEVICE-CODES")
    fields = service._field_map(report.template_version)
    codes = ["SYNTHETIC-B*", "SYNTHETIC-A"]
    values = [
        {
            "analyte_code": key,
            "unit_code": service._resolve_field_unit_code(fields[key])
            or service._resolve_field_unit(fields[key]),
            "value_text": number,
        }
        for key, number in (("hgb", "135"), ("wbc", "5.2"))
    ]
    values[0]["instrument_flags"] = codes
    observed_at = datetime(2026, 11, 24, 8, tzinfo=UTC)
    row = {
        "message_id": str(uuid4()),
        "report_instance_id": report.id,
        "specimen_barcode": specimen.barcode,
        "expected_updated_at": report.updated_at.replace(tzinfo=UTC).isoformat(),
        "observed_at": observed_at.isoformat(),
        "values": values,
    }
    invalid_flag = "SYNTHETIC free text"
    invalid = {
        **row,
        "message_id": str(uuid4()),
        "values": [{**values[0], "instrument_flags": [invalid_flag]}],
    }
    response = client.post(
        IMPORT_URL,
        json={"source": "manual", "rows": [invalid, row]},
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    rejected, saved = response.json()["rows"]
    assert rejected["error_code"] == "invalid_row"
    assert saved["status"] == "saved"
    assert invalid_flag not in response.text and invalid_flag not in caplog.text
    receipt = db_session.get(LabImportReceipt, saved["receipt_id"])
    assert (receipt.source, receipt.message_id) == ("manual", row["message_id"])
    assert receipt.actor_user_id == admin_user.id and receipt.specimen_id == specimen.id
    assert receipt.observed_at.replace(tzinfo=UTC) == observed_at

    def rendered_fields(instance_id):
        result = client.get(
            f"/api/v1/lab/report-instances/{instance_id}", headers=admin_auth_headers
        )
        assert result.status_code == 200
        return {
            field["field_key"]: field
            for section in result.json()["sections"]
            for field in section["fields"]
        }

    rendered = rendered_fields(report.id)
    assert rendered["hgb"]["instrument_flags"] == codes
    assert rendered["wbc"]["instrument_flags"] == []
    assert "import_origin" not in rendered["hgb"]

    changed_flags = dict(
        row, values=[{**values[0], "instrument_flags": ["OTHER"]}, values[1]]
    )
    replay = client.post(
        IMPORT_URL,
        json={"source": "manual", "rows": [row, changed_flags]},
        headers=admin_auth_headers,
    )
    assert replay.status_code == 200
    duplicate, conflict = replay.json()["rows"]
    assert duplicate["status"] == "duplicate" and duplicate["receipt_id"] == receipt.id
    assert conflict["error_code"] == "message_conflict"

    report, updated = service.bulk_upsert_values(
        report.id,
        [{"field_key": "hgb", "value_text": "135", "comment": "SYNTHETIC note"}],
        expected_updated_at=saved["updated_at"],
        actor_user_id=admin_user.id,
    )
    origin = updated[0].result_payload["import_origin"]
    assert origin == {
        "source": receipt.source,
        "message_id": receipt.message_id,
        "submitted_analyte_code": "hgb",
        "instrument_flags": codes,
    }
    report = service.record_report_qc(
        report.id,
        actor_user_id=reviewer.id,
        command=LabReportQCIn(
            expected_updated_at=report.updated_at.isoformat(),
            status="accepted",
            method="SYNTHETIC-QC",
            series_ref="SYNTHETIC-LOT",
        ),
    )
    report = service.submit_for_review(
        report.id,
        actor_user_id=admin_user.id,
        expected_updated_at=report.updated_at.isoformat(),
    )
    blocked = dict(
        changed_flags,
        message_id=str(uuid4()),
        expected_updated_at=report.updated_at.replace(tzinfo=UTC).isoformat(),
        replace_existing=True,
    )
    response = client.post(
        IMPORT_URL,
        json={"source": "manual", "rows": [blocked]},
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["rows"][0]["error_code"] == "report_locked"
    report = service.review_report(
        report.id,
        actor_user_id=reviewer.id,
        expected_updated_at=report.updated_at.isoformat(),
    )
    released = service.finalize(
        report.id,
        actor_user_id=reviewer.id,
        expected_updated_at=report.updated_at.isoformat(),
    )
    revision = service.revise(
        released.id,
        reason="SYNTHETIC correction",
        actor_user_id=admin_user.id,
        expected_updated_at=released.updated_at.isoformat(),
    )
    assert rendered_fields(released.id)["hgb"]["instrument_flags"] == codes
    assert rendered_fields(revision.id)["hgb"]["instrument_flags"] == codes

    revision, changed = service.bulk_upsert_values(
        revision.id,
        [{"field_key": "hgb", "value_text": "129"}],
        expected_updated_at=revision.updated_at.isoformat(),
        actor_user_id=admin_user.id,
    )
    assert "import_origin" not in changed[0].result_payload
    assert rendered_fields(revision.id)["hgb"]["instrument_flags"] == []
    historical = db_session.scalar(
        select(LabReportValue).where(
            LabReportValue.instance_id == released.id, LabReportValue.field_key == "hgb"
        )
    )
    assert historical.result_payload["import_origin"] == origin
    assert db_session.scalars(select(LabImportReceipt.id)).all() == [receipt.id]
    assert all(code not in caplog.text for code in codes)


@pytest.mark.unit
def test_optional_warning_codes_keep_historical_unflagged_receipt_digest():
    value = {"analyte_code": "hgb", "unit_code": "g_per_l", "value_text": "135"}
    row = {
        "message_id": "123e4567-e89b-42d3-a456-426614174000",
        "report_instance_id": 7,
        "specimen_barcode": "SYNTHETIC-PROVENANCE",
        "observed_at": "2026-11-24T04:02:00Z",
        "values": [value],
    }
    historical = "242209c18194e0333d078ac77fe1414b6e3cada9992ae42a317317819b91901e"
    assert _digest(LabImportRow.model_validate(row)) == historical
    value["instrument_flags"] = []
    assert _digest(LabImportRow.model_validate(row)) == historical
    value["instrument_flags"] = ["SYNTHETIC"]
    assert _digest(LabImportRow.model_validate(row)) != historical


@pytest.mark.unit
@pytest.mark.parametrize(
    "batch",
    [
        {"source": "instrument", "rows": [None]},
        {"source": "csv", "rows": []},
        {"source": "csv", "rows": [None] * 101},
        {"source": "csv", "rows": {}},
        {"source": "csv", "rows": [None], "unexpected": True},
    ],
)
def test_import_batch_envelope_stays_bounded(client, admin_auth_headers, batch):
    response = client.post(
        f"{IMPORT_URL}/preview", json=batch, headers=admin_auth_headers
    )
    assert response.status_code == 422


@pytest.mark.unit
def test_openapi_import_rows_retain_the_typed_input_contract():
    schemas = app.openapi()["components"]["schemas"]
    rows = schemas["LabImportBatch"]["properties"]["rows"]
    assert rows["items"] == {"$ref": "#/components/schemas/LabImportRow"}
    assert rows["minItems"] == 1 and rows["maxItems"] == 100
    assert "MalformedLabImportRow" not in schemas
    result = schemas["LabImportRowOut"]
    assert "row_index" in result["required"]
    assert {"type": "null"} in result["properties"]["message_id"]["anyOf"]
    for contract in ("LabImportValue", "LabReportRenderedFieldOut"):
        schema = schemas[contract]
        flags = schema["properties"]["instrument_flags"]
        assert "instrument_flags" not in schema["required"]
        assert flags["maxItems"] == 16 and flags["items"]["maxLength"] == 32
    assert "instrument_flags" not in schemas["LabReportValueIn"]["properties"]


@pytest.mark.unit
def test_oversized_batch_stops_before_row_validation(monkeypatch):
    def reject_row_validation(*args, **kwargs):
        pytest.fail("An oversized batch attempted to validate an individual row")

    monkeypatch.setattr(LabImportRow, "model_validate", reject_row_validation)
    with pytest.raises(ValidationError) as raised:
        LabImportBatch.model_validate({"source": "manual", "rows": [{}] * 101})
    assert raised.value.errors(include_input=False)[0]["type"] == "too_long"
