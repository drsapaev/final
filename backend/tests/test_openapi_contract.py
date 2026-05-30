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
        ("/api/v1/queue/qr-tokens/{token}/info", "get"),
        ("/api/v1/queue/join/start", "post"),
        ("/api/v1/queue/join/complete", "post"),
        ("/api/v1/registrar/records/actions", "post"),
        ("/api/v1/payments/init", "post"),
        ("/api/v1/payments/{payment_id}", "get"),
        ("/api/v1/telegram/mini-app/onboarding/requests", "post"),
        ("/api/v1/telegram/mini-app/onboarding/status", "post"),
        ("/api/v1/telegram/onboarding/requests", "get"),
        ("/api/v1/telegram/onboarding/analytics/summary", "get"),
        ("/api/v1/telegram/onboarding/requests/export", "get"),
        ("/api/v1/telegram/onboarding/requests/{request_id}/search-patients", "post"),
        ("/api/v1/telegram/onboarding/requests/{request_id}/link-existing", "post"),
        ("/api/v1/telegram/onboarding/requests/{request_id}/create-patient", "post"),
        ("/api/v1/telegram/onboarding/requests/{request_id}/request-more-info", "post"),
        ("/api/v1/telegram/onboarding/requests/{request_id}/reject", "post"),
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


def test_openapi_qr_token_info_exposes_join_read_contract(client: TestClient) -> None:
    schema = _get_openapi_schema(client)
    operation = schema["paths"]["/api/v1/queue/qr-tokens/{token}/info"]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    schema_name = response_schema["$ref"].rsplit("/", 1)[-1]
    properties = schema["components"]["schemas"][schema_name]["properties"]

    for field_name in (
        "selectable_specialists",
        "queue_active",
        "allowed",
        "status",
        "message",
    ):
        assert field_name in properties


def test_openapi_telegram_onboarding_contract_has_stable_operation_ids(
    client: TestClient,
) -> None:
    schema = _get_openapi_schema(client)
    expected_operations = {
        ("/api/v1/telegram/mini-app/onboarding/requests", "post"): (
            "telegram_mini_app_submit_patient_onboarding_request"
        ),
        ("/api/v1/telegram/mini-app/onboarding/status", "post"): (
            "telegram_mini_app_read_patient_onboarding_status"
        ),
        ("/api/v1/telegram/onboarding/requests", "get"): (
            "telegram_registrar_list_patient_onboarding_requests"
        ),
        ("/api/v1/telegram/onboarding/analytics/summary", "get"): (
            "telegram_registrar_patient_onboarding_analytics_summary"
        ),
        ("/api/v1/telegram/onboarding/requests/export", "get"): (
            "telegram_registrar_export_patient_onboarding_requests_csv"
        ),
        ("/api/v1/telegram/onboarding/requests/{request_id}/search-patients", "post"): (
            "telegram_registrar_search_patient_onboarding_candidates"
        ),
        ("/api/v1/telegram/onboarding/requests/{request_id}/link-existing", "post"): (
            "telegram_registrar_link_existing_patient_onboarding_request"
        ),
        ("/api/v1/telegram/onboarding/requests/{request_id}/create-patient", "post"): (
            "telegram_registrar_create_patient_from_onboarding_request"
        ),
        ("/api/v1/telegram/onboarding/requests/{request_id}/request-more-info", "post"): (
            "telegram_registrar_request_more_info_onboarding_request"
        ),
        ("/api/v1/telegram/onboarding/requests/{request_id}/reject", "post"): (
            "telegram_registrar_reject_patient_onboarding_request"
        ),
    }

    for (path, method), operation_id in expected_operations.items():
        operation = schema["paths"][path][method]
        assert operation["operationId"] == operation_id
        assert "responses" in operation
        assert "payment_id" not in str(operation)
        assert "diagnosis" not in str(operation).lower()


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
