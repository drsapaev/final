"""OpenAPI contract checks for critical clinic API flows."""

import warnings

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _get_openapi_schema(client: TestClient) -> dict:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    return response.json()


def test_openapi_schema_not_fallback_and_has_paths(client: TestClient) -> None:
    schema = _get_openapi_schema(client)

    assert schema.get("openapi", "").startswith("3.")
    assert schema.get("info", {}).get("title")
    assert isinstance(schema.get("paths"), dict)
    # Protect against accidental minimal/fallback schema generation in CI.
    assert len(schema["paths"]) >= 100


@pytest.mark.parametrize(
    ("path", "method"),
    [
        ("/api/v1/auth/login", "post"),
        ("/api/v1/auth/me", "get"),
        ("/api/v1/queue/join/start", "post"),
        ("/api/v1/queue/join/complete", "post"),
        ("/api/v1/payments/init", "post"),
        ("/api/v1/payments/{payment_id}", "get"),
        ("/api/v1/health", "get"),
    ],
)
def test_openapi_contains_critical_routes(
    client: TestClient,
    path: str,
    method: str,
) -> None:
    schema = _get_openapi_schema(client)
    assert path in schema["paths"], f"Missing route in OpenAPI: {path}"
    assert method in schema["paths"][path], f"Missing method in OpenAPI: {method.upper()} {path}"


def test_openapi_queue_join_contract_has_request_and_responses(client: TestClient) -> None:
    schema = _get_openapi_schema(client)
    operation = schema["paths"]["/api/v1/queue/join/complete"]["post"]

    assert "requestBody" in operation
    assert operation["requestBody"].get("required") is True
    assert "responses" in operation
    assert any(code in operation["responses"] for code in ("200", "201", "400", "422"))


def test_openapi_has_no_duplicate_operation_id_warnings() -> None:
    app.openapi_schema = None
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        app.openapi()

    duplicate_messages = [
        str(item.message)
        for item in captured
        if "Duplicate Operation ID" in str(item.message)
    ]
    assert not duplicate_messages, "Duplicate OpenAPI operation IDs found:\n" + "\n".join(
        duplicate_messages
    )


def test_openapi_marks_appointments_stats_as_deprecated(client: TestClient) -> None:
    schema = _get_openapi_schema(client)
    operation = schema["paths"]["/api/v1/appointments/stats"]["get"]

    assert operation.get("deprecated") is True


def test_openapi_marks_appointments_qrcode_as_deprecated(client: TestClient) -> None:
    schema = _get_openapi_schema(client)
    operation = schema["paths"]["/api/v1/appointments/qrcode"]["get"]

    assert operation.get("deprecated") is True


def test_openapi_marks_legacy_board_state_as_deprecated(client: TestClient) -> None:
    schema = _get_openapi_schema(client)
    operation = schema["paths"]["/api/v1/board/state"]["get"]

    assert operation.get("deprecated") is True


def test_openapi_marks_queues_stats_compatibility_fields_as_deprecated(
    client: TestClient,
) -> None:
    schema = _get_openapi_schema(client)
    operation = schema["paths"]["/api/v1/queues/stats"]["get"]
    schema_ref = operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    component_name = schema_ref.split("/")[-1]
    component = schema["components"]["schemas"][component_name]
    props = component["properties"]

    assert props["is_open"].get("deprecated") is True
    assert props["start_number"].get("deprecated") is True
    assert props["last_ticket"].get("deprecated") is not True
    assert props["waiting"].get("deprecated") is not True
