"""OpenAPI contract checks for critical clinic API flows."""

import ast
import warnings
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app

HTTP_ROUTE_METHODS = {"get", "post", "put", "patch", "delete"}
ENDPOINTS_DIR = Path(__file__).resolve().parents[1] / "app" / "api" / "v1" / "endpoints"


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


def _decorator_route(decorator: ast.expr) -> tuple[str, str] | None:
    if not isinstance(decorator, ast.Call):
        return None
    if not isinstance(decorator.func, ast.Attribute):
        return None
    if decorator.func.attr not in HTTP_ROUTE_METHODS:
        return None

    if decorator.args:
        first_arg = decorator.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            return decorator.func.attr.upper(), first_arg.value

    for keyword in decorator.keywords:
        if keyword.arg != "path":
            continue
        if isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
            return decorator.func.attr.upper(), keyword.value.value

    return None


def _route_parts(route: str) -> list[str]:
    stripped = route.strip("/")
    return stripped.split("/") if stripped else []


def _is_shadowed_static_route(previous_route: str, current_route: str) -> bool:
    previous_parts = _route_parts(previous_route)
    current_parts = _route_parts(current_route)
    if len(previous_parts) != len(current_parts):
        return False

    saw_previous_param = False
    for previous_part, current_part in zip(previous_parts, current_parts):
        if previous_part == current_part:
            continue
        if (
            previous_part.startswith("{")
            and previous_part.endswith("}")
            and not current_part.startswith("{")
        ):
            saw_previous_param = True
            continue
        return False

    return saw_previous_param


def test_fastapi_static_routes_are_declared_before_same_shape_parameter_routes() -> None:
    """A later static route can be swallowed by an earlier same-shape path parameter."""

    shadow_messages: list[str] = []

    for endpoint_file in sorted(ENDPOINTS_DIR.glob("*.py")):
        tree = ast.parse(
            endpoint_file.read_text(encoding="utf-8"),
            filename=str(endpoint_file),
        )
        routes: list[tuple[int, str, str]] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                route = _decorator_route(decorator)
                if route is not None:
                    method, route_path = route
                    routes.append((decorator.lineno, method, route_path))

        routes.sort()
        for index, (line_number, method, route_path) in enumerate(routes):
            for previous_line, previous_method, previous_route_path in routes[:index]:
                if method != previous_method:
                    continue
                if not _is_shadowed_static_route(previous_route_path, route_path):
                    continue
                shadow_messages.append(
                    f"{endpoint_file}:{line_number}: {method} {route_path} "
                    f"is shadowed by {previous_route_path} at {previous_line}"
                )

    assert not shadow_messages, "Static routes declared after parameter routes:\n" + "\n".join(
        shadow_messages
    )


def test_published_fastapi_routes_do_not_shadow_static_paths_across_routers() -> None:
    """Router include order must not hide static paths behind earlier path parameters."""

    published_routes: list[tuple[int, str, str, str]] = []
    for route_index, route in enumerate(app.routes):
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(route.methods or []):
            if method in {"HEAD", "OPTIONS"}:
                continue
            published_routes.append((route_index, method, route.path, route.name))

    shadow_messages: list[str] = []
    for index, method, route_path, route_name in published_routes:
        for previous_index, previous_method, previous_route_path, previous_route_name in (
            published_routes
        ):
            if previous_index >= index:
                break
            if method != previous_method:
                continue
            if not _is_shadowed_static_route(previous_route_path, route_path):
                continue
            shadow_messages.append(
                f"{index}: {method} {route_path} ({route_name}) is shadowed by "
                f"{previous_route_path} ({previous_route_name}) at {previous_index}"
            )

    assert not shadow_messages, "Published static routes shadowed by app order:\n" + "\n".join(
        shadow_messages
    )
