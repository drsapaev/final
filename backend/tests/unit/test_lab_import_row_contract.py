from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.main import app
from app.models.audit import AuditLog
from app.models.lab_import import LabImportReceipt
from app.schemas.lab_import import LabImportBatch, LabImportRow
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


@pytest.mark.unit
def test_oversized_batch_stops_before_row_validation(monkeypatch):
    def reject_row_validation(*args, **kwargs):
        pytest.fail("An oversized batch attempted to validate an individual row")

    monkeypatch.setattr(LabImportRow, "model_validate", reject_row_validation)
    with pytest.raises(ValidationError) as raised:
        LabImportBatch.model_validate({"source": "manual", "rows": [{}] * 101})
    assert raised.value.errors(include_input=False)[0]["type"] == "too_long"
