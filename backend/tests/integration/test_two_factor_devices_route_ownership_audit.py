from __future__ import annotations

from fastapi.routing import APIRoute
import pytest

from app.api.v1.endpoints import two_factor_auth as two_factor_auth_endpoints
from app.api.v1.endpoints import two_factor_devices as two_factor_devices_endpoints
from app.main import app


def _matching_api_routes(path: str, method: str) -> list[APIRoute]:
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path == path
        and method in (route.methods or set())
    ]


@pytest.mark.integration
def test_two_factor_devices_shadowed_routes_keep_current_first_match_runtime_owner():
    get_routes = _matching_api_routes("/api/v1/2fa/devices", "GET")
    delete_routes = _matching_api_routes("/api/v1/2fa/devices/{device_id}", "DELETE")

    assert len(get_routes) >= 2
    assert get_routes[0].endpoint is two_factor_auth_endpoints.get_trusted_devices
    assert get_routes[0].include_in_schema is True
    assert get_routes[1].endpoint is two_factor_devices_endpoints.get_trusted_devices
    assert get_routes[1].include_in_schema is False

    assert len(delete_routes) >= 2
    assert delete_routes[0].endpoint is two_factor_auth_endpoints.untrust_device
    assert delete_routes[0].include_in_schema is True
    assert delete_routes[1].endpoint is two_factor_devices_endpoints.revoke_device
    assert delete_routes[1].include_in_schema is False


@pytest.mark.integration
def test_two_factor_devices_openapi_now_publishes_runtime_owner_shape():
    app.openapi_schema = None
    schema = app.openapi()

    get_operation = schema["paths"]["/api/v1/2fa/devices"]["get"]
    delete_operation = schema["paths"]["/api/v1/2fa/devices/{device_id}"]["delete"]
    get_schema = get_operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    delete_schema = delete_operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]

    assert get_operation["tags"] == ["two-factor-auth"]
    assert get_schema["$ref"] == "#/components/schemas/TwoFactorDeviceListResponse"
    assert delete_operation["tags"] == ["two-factor-auth"]
    assert delete_operation["summary"] == "Untrust Device"
    assert delete_schema["$ref"] == "#/components/schemas/TwoFactorSuccessResponse"
